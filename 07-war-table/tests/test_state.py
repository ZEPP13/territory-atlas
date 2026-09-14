import unittest
from datetime import datetime, timezone
from helpers import entity
from wartable.state import compose


def sig(sid, eid, stage="announced"):
    return {"id": sid, "received_at": "2026-09-09T00:00:00Z", "published_at": None, "kind": "project_status",
            "stage": stage, "headline": "x project", "summary": "", "url": None,
            "source": {"type": "registry_snapshot", "name": "Industrial Info plant export", "as_of": "2026-09-09"},
            "entity_id": eid, "match": {"method": "exact_id", "confidence": "high", "reason": "t"},
            "generated_by": {"kind": "rule", "detail": "test"}}


class StateTests(unittest.TestCase):
    def test_signals_for_excluded_facilities_are_counted_not_shown(self):
        base = [entity("K-1")]
        st = compose(base, now=datetime(2026, 9, 13, tzinfo=timezone.utc), ledger=[], logbook=[],
                     signals=[sig("sig-a", "K-1"), sig("sig-b", "GONE-1"), sig("sig-c", None)])
        shown = {s["id"] for s in st["signals"]}
        self.assertEqual(shown, {"sig-a", "sig-c"})
        self.assertEqual(st["counts"]["signals_orphaned"], 1)
        self.assertEqual(st["counts"]["signals_unplaced"], 1)
        self.assertEqual(st["counts"]["signals"], 3)


if __name__ == "__main__":
    unittest.main()
