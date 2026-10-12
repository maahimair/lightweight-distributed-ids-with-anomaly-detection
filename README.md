# Lightweight Distributed IDS for IoT

A lightweight intrusion detection system for IoT networks. Sensor simulators
publish telemetry over **MQTT**, and the monitor flags readings that breach a
plausible range or change faster than the sensor could physically manage.

Built to stay small enough to run on the low-resource devices typical of IoT
deployments — the whole detector is pure standard library.

## Tech stack

| Component | Tool |
|---|---|
| Telemetry transport | MQTT (`paho-mqtt`) |
| Detection logic | Python 3.8+, standard library |
| Rule-based detection | Snort |
| Packet inspection | Wireshark |

The Python side is the live detector. Snort and Wireshark are the lab
tooling for inspecting the same traffic at the packet and rule level — see
`commands_on_terminal_for_local.rules.pdf`.

## How it works

```
temperature_sensor.py  ──┐
                         ├──▶  [ MQTT broker :1883 ]  ──▶  ids_monitor.py  ──▶  console alerts
humidity_sensor.py    ──┘
```

1. Each sensor script publishes an integer reading to its topic every 2 seconds.
2. `ids_monitor.py` subscribes to `iot/#` and runs each reading through an
   `AnomalyDetector`.
3. The detector raises an alert when a reading either breaches a threshold or
   changes implausibly fast.

### Two kinds of anomaly

**Threshold breach** — a reading outside the operating range
(`TEMP_THRESHOLD`, `HUMIDITY_THRESHOLD`).

**Sudden change** — a jump larger than the sensor's recent behaviour allows.
The detector keeps a rolling window of the last 20 readings, computes the mean
and standard deviation of the recent deltas, and flags any step that exceeds
`mean + 6σ`. This catches an attacker who stays under the threshold but moves
the value implausibly fast.

Two guards keep this from producing noise:

- Change detection stays silent until 5 samples have arrived, so the first
  readings after start-up cannot alarm against an uninitialised mean.
- The baseline is floored at `1.0`, because a sensor that has produced a
  perfectly flat line has zero spread, which would otherwise make *any* change
  infinitely suspicious.

## Project structure

```
ids_monitor.py                          MQTT client + anomaly detection
temperature_sensor.py                   Simulated temperature sensor
humidity_sensor.py                      Simulated humidity sensor
requirements.txt                        paho-mqtt
test_ids_monitor.py                     Unit tests (no broker required)
commands_on_terminal_for_local.rules.pdf  Snort rules and setup commands
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

You also need an MQTT broker. On Debian/Ubuntu:

```bash
sudo apt install mosquitto mosquitto-clients
sudo systemctl start mosquitto
```

## Usage

Terminal 1 — the IDS:

```bash
python ids_monitor.py
```

Terminals 2 and 3 — the sensors:

```bash
python temperature_sensor.py
python humidity_sensor.py
```

The IDS will report normal readings, and roughly every 12th temperature and
15th humidity reading triggers an `ALERT:` line, because the simulators
inject an out-of-range value periodically. Without that injection nothing the
sensors produce would ever cross a threshold, and the demo would look broken.

Example output:

```
Temperature: 27
Temperature: 31
Temperature: 78  <-- injected anomaly
ALERT: iot/temperature out of range [0.0, 45.0] -> 78
```

Press `Ctrl+C` to stop any of the three; all three shut down cleanly.

## Configuration

All settings are environment variables, so nothing needs editing to change a
threshold or point at a remote broker.

| Variable | Default | Used by | Purpose |
| --- | --- | --- | --- |
| `MQTT_HOST` | `localhost` | all | Broker hostname |
| `MQTT_PORT` | `1883` | all | Broker port |
| `TEMP_THRESHOLD` | `45` | IDS | Upper plausible temperature |
| `TEMP_MIN` | `0` | IDS | Lower plausible temperature |
| `HUMIDITY_THRESHOLD` | `70` | IDS | Upper plausible humidity |
| `HUMIDITY_MIN` | `0` | IDS | Lower plausible humidity |
| `PUBLISH_INTERVAL` | `2` | sensors | Seconds between readings |
| `ANOMALY_EVERY` | `12` / `15` | sensors | Inject an anomaly every Nth reading |
| `ANOMALY_VALUE` | `78` / `95` | sensors | The anomalous reading to inject |

An unparseable value falls back to the default rather than crashing the
monitor.

## Tests

```bash
python -m unittest test_ids_monitor -v
```

19 tests, no broker and no network required. The detection logic is
deliberately separated from the MQTT wiring so it can be tested directly.

They cover threshold breaches on both bounds and the boundary itself, change
detection during warm-up, gradual drift, a flat sensor, and large jumps in both
directions — plus a regression test for the bug that motivated the split: a
non-numeric payload, invalid UTF-8, and an unknown topic each used to raise
inside the paho callback and permanently stop the network loop, silently
ending all monitoring. The tests assert that a valid reading still processes
after each of them.

## Limitations

- Single-process, in-memory state. Detection history resets when the monitor
  restarts, and nothing is shared between replicas.
- Both detectors are independent. A coordinated attack that keeps temperature
  and humidity individually plausible is not detected.
- Change detection needs enough history to estimate a baseline, so the first few
  readings after start-up only get threshold checking.
- The Snort rules in the PDF cover the packet layer; the Python detector covers
  the message layer. They are not correlated with each other.

## Future improvements

- Rate-of-change detection across topics, to catch coordinated tampering
- Persist alert history for later analysis
- A simple dashboard for live alerts
- Correlate the Python detector's verdicts with the Snort rules