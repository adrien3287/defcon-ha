"""Offline unit tests: family DEFCON grid and signal deduplication."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "defcon_ha"))
from signal_assessment import assess_context_signals


def signal(key, category="transport", title="Incident", **extra):
    return {
        "status": "active", "signal_class": "signal_faible", "signal_confirmed": True,
        "event_key": key, "phenomenon_key": key, "category": category, "title": title,
        "importance": 2, "source_class": "official", "analysis_confidence": 95,
        "confidence_score": 95, "corroboration_count": 1, "direct_relevance": "potential",
        **extra,
    }


class DefconScoringTest(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(assess_context_signals([]).level, 5)

    def test_one_weak(self):
        result = assess_context_signals([signal("one")])
        self.assertEqual((result.level, result.weak_count), (4, 1))

    def test_three_independent_weak(self):
        result = assess_context_signals([signal("one"), signal("two"), signal("three")])
        self.assertEqual((result.level, result.weak_count), (3, 3))

    def test_two_serious(self):
        a = signal("one")
        b = signal("two")
        a["signal_class"] = "signal_serieux"
        b["signal_class"] = "signal_serieux"
        self.assertEqual(assess_context_signals([a, b]).level, 2)

    def test_one_serious_plus_two_weak(self):
        values = [signal("one"), signal("two"), signal("three")]
        values[0]["signal_class"] = "signal_serieux"
        self.assertEqual(assess_context_signals(values).level, 2)

    def test_major_crisis(self):
        event = signal("gas", category="energy")
        event["signal_class"] = "signal_serieux"
        event["major_crisis"] = True
        self.assertEqual(assess_context_signals([event]).level, 2)

    def test_direct_official_protective_action(self):
        event = signal("chemical", category="fire")
        event.update(signal_class="signal_serieux", direct_relevance="direct", protective_action=True)
        self.assertEqual(assess_context_signals([event]).level, 1)

    def test_article_duplication_does_not_escalate(self):
        events = [signal("article-a", category="water", title="Rupture Marmstorf"),
                  signal("article-b", category="water", title="Rupture Westerheide"),
                  signal("hamburg-water-local", category="water", title="Rupture Marmstorf")]
        result = assess_context_signals(events)
        self.assertEqual((result.level, result.weak_count), (4, 1))

    def test_old_rss_without_confirmation_not_counted(self):
        event = signal("old")
        del event["signal_confirmed"]
        self.assertEqual(assess_context_signals([event]).level, 5)

    def test_unknown_inactive_or_rumor_excluded(self):
        events = [signal("stale", status="stale"), signal("rumor", signal_confirmed=False)]
        self.assertEqual(assess_context_signals(events).level, 5)

    def test_missing_primary_source_requires_corroboration(self):
        event = signal("suspicious")
        event["source_class"] = "rapid_media"
        event["corroboration_count"] = 1
        self.assertEqual(assess_context_signals([event]).level, 5)
        event["corroboration_count"] = 2
        self.assertEqual(assess_context_signals([event]).level, 4)


if __name__ == "__main__":
    unittest.main()
