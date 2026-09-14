import unittest
from datetime import datetime, timedelta, timezone
from helpers import entity
from wartable.schema import load, validate
from wartable.signals import freshness, in_spec_window, seed_from_registry


def sig(source_type, received):
    return {"id": "sig-t", "received_at": received.strftime("%Y-%m-%dT%H:%M:%SZ"), "stage": "announced",
            "source": {"type": source_type, "name": "t", "as_of": "x"}}


class SignalTests(unittest.TestCase):
    def setUp(self):
        self.base = [entity("P-1", timing="proposed"), entity("P-2", timing="construction"),
                     entity("P-3", timing="operating"), entity("P-4", timing="construction", scope="out_of_portfolio")]

    def test_seed_is_deterministic_and_schema_valid(self):
        a, b = seed_from_registry(self.base), seed_from_registry(self.base)
        self.assertEqual([s["id"] for s in a], [s["id"] for s in b])
        schema = load("signal")
        for s in a:
            self.assertEqual(validate(s, schema), [], s["id"])

    def test_seed_only_covers_in_portfolio_project_statuses(self):
        ids = {s["entity_id"] for s in seed_from_registry(self.base)}
        self.assertEqual(ids, {"P-1", "P-2"})

    def test_registry_snapshots_never_glow_as_if_they_were_news(self):
        now = datetime(2026, 9, 13, tzinfo=timezone.utc)
        self.assertEqual(freshness(sig("registry_snapshot", now - timedelta(hours=1)), now), 0.0)

    def test_freshness_curve_for_arrivals(self):
        now = datetime(2026, 9, 13, tzinfo=timezone.utc)
        self.assertEqual(freshness(sig("trade_press", now - timedelta(hours=10)), now), 1.0)
        mid = freshness(sig("trade_press", now - timedelta(days=4)), now)
        self.assertTrue(0 < mid < 1)
        self.assertEqual(freshness(sig("trade_press", now - timedelta(days=8)), now), 0.0)

    def test_spec_window(self):
        self.assertTrue(in_spec_window({"stage": "permitting"}))
        self.assertFalse(in_spec_window({"stage": "construction"}))

    def test_seeded_signals_are_labelled_as_rule_generated_not_ai(self):
        self.assertTrue(all(s["generated_by"]["kind"] == "rule" for s in seed_from_registry(self.base)))


if __name__ == "__main__":
    unittest.main()
