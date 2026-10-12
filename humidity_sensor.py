"""Simulated humidity sensor.

Publishes a reading to ``iot/humidity`` every ``INTERVAL`` seconds, with an
occasional injected anomaly so the IDS has something to detect.
"""

import os
import random
import signal
import sys
import time

BROKER = os.environ.get("MQTT_HOST", "localhost")
PORT = int(os.environ.get("MQTT_PORT", 1883))
TOPIC = "iot/humidity"

NORMAL_RANGE = (35, 65)
#: Every Nth reading is anomalous.
ANOMALY_EVERY = int(os.environ.get("ANOMALY_EVERY", 15))
ANOMALY_VALUE = int(os.environ.get("ANOMALY_VALUE", 95))
INTERVAL = float(os.environ.get("PUBLISH_INTERVAL", 2))

_running = True


def _stop(*_args):
    global _running
    _running = False


def main():
    import paho.mqtt.client as mqtt

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
        client_id=f"humidity-sensor-{os.getpid()}",
    )

    try:
        client.connect(BROKER, PORT, 60)
    except ConnectionRefusedError:
        print(f"[!] No broker listening on {BROKER}:{PORT}.", file=sys.stderr)
        return 1

    client.loop_start()

    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)

    print(f"[*] Humidity sensor publishing to '{TOPIC}' on {BROKER}:{PORT}")
    count = 0
    try:
        while _running:
            count += 1
            anomalous = ANOMALY_EVERY > 0 and count % ANOMALY_EVERY == 0
            value = ANOMALY_VALUE if anomalous else random.randint(*NORMAL_RANGE)
            client.publish(TOPIC, value)
            print(f"Humidity sent: {value}" + ("  <-- injected anomaly" if anomalous else ""))
            time.sleep(INTERVAL)
    finally:
        client.loop_stop()
        client.disconnect()
        print("[*] Humidity sensor stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())