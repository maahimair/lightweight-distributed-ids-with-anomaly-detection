"""Lightweight distributed intrusion detection system for IoT telemetry.

Subscribes to every topic under ``iot/#`` and flags two kinds of anomaly:

* **Threshold breach** - a reading outside the plausible operating range.
* **Sudden change** - a jump far larger than the sensor normally produces,
  which catches an attacker who stays under the threshold but moves the
  value implausibly fast.

The detection logic lives in :class:`AnomalyDetector` and is deliberately free
of any MQTT import, so it can be unit tested without a broker. Everything below
``run()`` is the transport layer.
"""

import os
import signal
import statistics
import sys
from collections import defaultdict, deque

TEMP_TOPIC = "iot/temperature"
HUMIDITY_TOPIC = "iot/humidity"

#: Topics whose readings are plain integers. Anything else under ``iot/#`` is
#: logged and ignored rather than being allowed to kill the network loop.
NUMERIC_TOPICS = (TEMP_TOPIC, HUMIDITY_TOPIC)


def _env_float(name, default):
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


def _env_int(name, default):
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


class AnomalyDetector:
    """Stateful per-topic detector: threshold plus sudden-change detection.

    ``history`` holds the last ``window`` readings for a topic so that both the
    mean and the spread can be estimated. ``window`` readings are required
    before change detection engages, so the first few samples after start-up
    cannot trigger a false alarm against an uninitialised mean.
    """

    def __init__(self, low, high, window=20, sigma=6.0, min_history=5,
                 min_jump=5.0):
        self.low = low
        self.high = high
        self.window = max(2, window)
        self.sigma = sigma
        self.min_history = max(2, min_history)
        #: Smallest absolute jump treated as implausible, regardless of history.
        self.min_jump = min_jump
        self._history = defaultdict(lambda: deque(maxlen=self.window))
        self._previous = {}

    def evaluate(self, topic, value):
        """Return a reason string if *value* is anomalous, else ``None``."""
        history = self._history[topic]
        previous = self._previous.get(topic)

        reason = None
        if value < self.low or value > self.high:
            reason = "threshold"
        elif len(history) >= self.min_history and previous is not None:
            deltas = [
                abs(b - a) for a, b in zip(list(history)[:-1], list(history)[1:])
            ]
            # A sensor that has produced a perfectly flat line has zero spread,
            # which would make any change infinitely suspicious. Floor the
            # baseline so a flat sensor is judged against a sane tolerance.
            baseline = max(statistics.fmean(deltas), 1.0)
            spread = statistics.pstdev(deltas) if len(deltas) > 1 else 0.0
            tolerance = baseline + self.sigma * spread
            if abs(value - previous) > max(tolerance, self.min_jump):
                reason = "sudden_change"

        history.append(value)
        self._previous[topic] = value
        return reason


class IDSMonitor:
    """MQTT transport wrapper around :class:`AnomalyDetector`."""

    def __init__(self, detectors, host, port, keepalive=60, subscribe="iot/#"):
        self.detectors = detectors
        self.host = host
        self.port = port
        self.keepalive = keepalive
        self.subscribe = subscribe
        self.client = None
        self._running = False

    # ── callbacks ──────────────────────────────────────────────────────────
    def on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            # A non-zero rc means the broker refused us; subscribing here would
            # silently never deliver anything.
            print(f"[!] Connection refused by broker: rc={rc}", file=sys.stderr)
            self._running = False
            return
        print(f"[*] Connected to {self.host}:{self.port}")
        client.subscribe(self.subscribe)
        print(f"[*] Subscribed to '{self.subscribe}'")

    def on_disconnect(self, client, userdata, rc, properties=None):
        if self._running and rc != 0:
            print(f"[!] Unexpected disconnect (rc={rc}); paho will retry.", file=sys.stderr)

    def on_message(self, client, userdata, msg):
        topic = msg.topic

        if topic not in NUMERIC_TOPICS:
            # Previously this fell through to int() and raised ValueError on any
            # non-numeric payload, which terminated the network loop and
            # silently stopped all monitoring.
            print(f"[i] Ignoring non-numeric topic '{topic}'")
            return

        try:
            value = int(msg.payload.decode("utf-8").strip())
        except (UnicodeDecodeError, ValueError):
            print(f"[!] Non-numeric payload on {topic}: {msg.payload!r}")
            return

        detector = self.detectors.get(topic)
        if detector is None:
            print(f"[i] No detector configured for '{topic}'")
            return

        print(f"{topic.split('/')[-1].capitalize()}: {value}")
        reason = detector.evaluate(topic, value)
        if reason == "threshold":
            print(f"ALERT: {topic} out of range "
                  f"[{detector.low}, {detector.high}] -> {value}")
        elif reason == "sudden_change":
            print(f"ALERT: {topic} implausible rate of change -> {value}")

    # ── lifecycle ──────────────────────────────────────────────────────────
    def _shutdown(self, *_args):
        self._running = False

    def run(self):
        import paho.mqtt.client as mqtt

        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
            client_id=f"ids-monitor-{os.getpid()}",
        )
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.on_disconnect = self.on_disconnect
        self.client = client

        signal.signal(signal.SIGINT, self._shutdown)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, self._shutdown)

        print(f"[*] Connecting to broker at {self.host}:{self.port}")
        self._running = True
        try:
            # loop_forever handles reconnect with backoff, which a bare
            # connect() followed by a manual loop does not.
            client.connect_async(self.host, self.port, self.keepalive)
            client.loop_forever(retry_first_connection=True)
        except KeyboardInterrupt:
            pass
        except ConnectionRefusedError:
            print(f"[!] No broker listening on {self.host}:{self.port}. "
                  f"Start mosquitto, or run the sensor scripts.", file=sys.stderr)
            return 1
        finally:
            self._running = False
            client.disconnect()
            print("[*] IDS stopped.")
        return 0


def build_default_detectors():
    return {
        TEMP_TOPIC: AnomalyDetector(
            low=_env_float("TEMP_MIN", 0.0),
            high=_env_float("TEMP_THRESHOLD", 45.0),
        ),
        HUMIDITY_TOPIC: AnomalyDetector(
            low=_env_float("HUMIDITY_MIN", 0.0),
            high=_env_float("HUMIDITY_THRESHOLD", 70.0),
        ),
    }


def main():
    monitor = IDSMonitor(
        detectors=build_default_detectors(),
        host=os.environ.get("MQTT_HOST", "localhost"),
        port=_env_int("MQTT_PORT", 1883),
    )
    print("IDS started...")
    return monitor.run()


if __name__ == "__main__":
    sys.exit(main())