"""Tests for the IDS detection logic.

These import no MQTT library and open no socket, so they run anywhere:

    python -m unittest test_ids_monitor -v
"""

import unittest

from ids_monitor import (
    HUMIDITY_TOPIC,
    TEMP_TOPIC,
    AnomalyDetector,
    IDSMonitor,
    build_default_detectors,
)


class FakeMessage:
    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload


class TestThresholdDetection(unittest.TestCase):
    def setUp(self):
        self.detector = AnomalyDetector(low=0, high=45)

    def test_normal_reading_is_quiet(self):
        self.assertIsNone(self.detector.evaluate(TEMP_TOPIC, 25))

    def test_above_threshold_alerts(self):
        self.assertEqual(self.detector.evaluate(TEMP_TOPIC, 46), "threshold")

    def test_at_threshold_is_not_an_alert(self):
        self.assertIsNone(self.detector.evaluate(TEMP_TOPIC, 45))

    def test_below_low_bound_alerts(self):
        self.assertEqual(self.detector.evaluate(TEMP_TOPIC, -3), "threshold")


class TestChangeDetection(unittest.TestCase):
    def setUp(self):
        self.detector = AnomalyDetector(low=0, high=45, window=20, min_history=5)

    def prime(self, values):
        for v in values:
            self.detector.evaluate(TEMP_TOPIC, v)

    def test_warmup_does_not_alert(self):
        # Fewer than min_history samples: change detection must stay silent.
        self.prime([20, 30, 40])
        self.assertIsNone(self.detector.evaluate(TEMP_TOPIC, 35))

    def test_gradual_drift_is_not_an_alert(self):
        self.prime([20, 21, 22, 23, 24, 25])
        self.assertIsNone(self.detector.evaluate(TEMP_TOPIC, 26))

    def test_flat_sensor_does_not_alert_on_small_changes(self):
        # A perfectly flat history has zero spread; the baseline floor stops
        # that from turning any movement into an alert.
        self.prime([25, 25, 25, 25, 25])
        self.assertIsNone(self.detector.evaluate(TEMP_TOPIC, 26))

    def test_large_jump_within_range_is_an_alert(self):
        self.prime([20, 21, 22, 21, 20, 21])
        self.assertEqual(self.detector.evaluate(TEMP_TOPIC, 40), "sudden_change")

    def test_sudden_drop_is_also_an_alert(self):
        self.prime([30, 31, 30, 31, 30, 31])
        self.assertEqual(self.detector.evaluate(TEMP_TOPIC, 2), "sudden_change")


class TestMessageHandling(unittest.TestCase):
    """The regression that motivated this suite: a payload that is not an
    integer used to raise inside the paho callback and permanently stop the
    network loop, taking all monitoring with it."""

    def setUp(self):
        self.detectors = build_default_detectors()
        self.monitor = IDSMonitor(self.detectors, "localhost", 1883)

    def handle(self, topic, payload):
        self.monitor.on_message(None, None, FakeMessage(topic, payload))

    def test_valid_reading_does_not_raise(self):
        self.handle(TEMP_TOPIC, b"25")

    def test_non_numeric_payload_is_ignored_not_fatal(self):
        self.handle(TEMP_TOPIC, b"not-a-number")
        self.handle(TEMP_TOPIC, b"")  # still alive afterwards

    def test_invalid_utf8_payload_is_ignored(self):
        self.handle(TEMP_TOPIC, b"\xff\xfe\x00")

    def test_payload_with_surrounding_whitespace(self):
        self.handle(TEMP_TOPIC, b"  31  ")

    def test_unknown_topic_is_ignored_not_fatal(self):
        # iot/# also matches topics the IDS has no detector for.
        self.handle("iot/pressure", b"1013")
        self.handle("iot/config/reboot", b'{"cmd":"reboot"}')

    def test_unknown_topic_without_detector(self):
        self.handle("iot/temperature/extra", b"25")

    def test_monitoring_continues_after_a_bad_payload(self):
        for _ in range(3):
            self.handle(TEMP_TOPIC, b"garbage")
        self.handle(HUMIDITY_TOPIC, b"55")  # must not raise


class TestConfiguration(unittest.TestCase):
    def test_default_detectors_cover_both_topics(self):
        detectors = build_default_detectors()
        self.assertEqual(set(detectors), {TEMP_TOPIC, HUMIDITY_TOPIC})

    def test_humidity_threshold_default(self):
        self.assertEqual(build_default_detectors()[HUMIDITY_TOPIC].high, 70.0)

    def test_temperature_threshold_default(self):
        self.assertEqual(build_default_detectors()[TEMP_TOPIC].high, 45.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)