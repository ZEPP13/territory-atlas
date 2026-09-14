import unittest
from helpers import change, entity, tap
from wartable.progression import config, derive, rank_for, rank_table


def run(base, ledger=(), log=(), signals=()):
    return derive({e["id"]: e for e in base}, list(ledger), list(log), list(signals))


class RankTableTests(unittest.TestCase):
    def test_table_is_22_levels_strictly_increasing_starting_at_zero(self):
        t = rank_table()
        self.assertEqual(len(t), 22)
        self.assertEqual(t[0][2], 0)
        self.assertTrue(all(b[2] > a[2] for a, b in zip(t, t[1:])))
        self.assertEqual(t[-1][1], config()["ranks"]["final"])

    def test_rank_boundaries(self):
        t = rank_table()
        self.assertEqual(rank_for(0)["level"], 1)
        self.assertEqual(rank_for(t[1][2] - 1)["level"], 1)
        self.assertEqual(rank_for(t[1][2])["level"], 2)
        top = rank_for(10 ** 7)
        self.assertEqual(top["level"], 22)
        self.assertIsNone(top["next_at"])


class ProgressionTests(unittest.TestCase):
    def setUp(self):
        cfg = config()
        self.stage_pts = {s["id"]: s["points"] for s in cfg["stages"]}
        self.w = cfg["opportunity_weight"]
        self.base = [entity("H-1", band="High"), entity("L-1", band="Low")] + \
                    [entity(f"F-{i}", band="Low") for i in range(18)]

    def test_nothing_logged_means_zero_and_everything_uncharted(self):
        s = run(self.base)
        self.assertEqual(s["points"]["total"], 0)
        self.assertEqual(s["stages"], {})

    def test_stage_is_the_highest_reached_and_points_are_cumulative_and_weighted(self):
        s = run(self.base, log=[tap(1, "2026-09-13T01:00:00Z", "quoted", "H-1"),
                                tap(2, "2026-09-13T02:00:00Z", "surveyed", "H-1")])
        self.assertEqual(s["stages"]["H-1"], "established")
        expected = (self.stage_pts["surveyed"] + self.stage_pts["landfall"] + self.stage_pts["established"]) * self.w["High"]
        self.assertEqual(s["points"]["total"] - s["points"]["milestones"], expected)

    def test_high_opportunity_counts_for_more_than_low(self):
        hi = run(self.base, log=[tap(1, "2026-09-13T01:00:00Z", "visited", "H-1")])
        lo = run(self.base, log=[tap(1, "2026-09-13T01:00:00Z", "visited", "L-1")])
        self.assertGreater(hi["points"]["total"] - hi["points"]["milestones"],
                           lo["points"]["total"] - lo["points"]["milestones"])

    def test_undo_removes_the_tap_entirely(self):
        s = run(self.base, log=[tap(1, "2026-09-13T01:00:00Z", "won", "H-1"),
                                tap(2, "2026-09-13T01:05:00Z", "undo", "H-1", undo_of="lb-000000000001")])
        self.assertEqual(s["points"]["total"], 0)
        self.assertNotIn("H-1", s["stages"])

    def test_rescoring_a_facility_later_does_not_change_points_already_earned(self):
        log = [tap(1, "2026-09-13T01:00:00Z", "visited", "H-1", band="High")]
        before = run(self.base, log=log)["points"]["total"]
        rescored = [entity("H-1", band="Low")] + self.base[1:]
        self.assertEqual(run(rescored, log=log)["points"]["total"], before)

    def test_retiring_an_account_later_keeps_points_already_earned(self):
        log = [tap(1, "2026-09-13T01:00:00Z", "visited", "H-1")]
        before = run(self.base, log=log)["points"]["total"]
        after = run(self.base, ledger=[change(1, "2026-09-14T01:00:00Z", "mark_defunct", "H-1")], log=log)
        self.assertEqual(after["points"]["total"], before)

    def test_engagement_on_a_duplicate_counts_toward_the_real_record_once(self):
        led = [change(1, "2026-09-13T00:00:00Z", "mark_duplicate", "L-1", duplicate_of="H-1")]
        s = run(self.base, ledger=led, log=[tap(1, "2026-09-13T01:00:00Z", "surveyed", "L-1"),
                                            tap(2, "2026-09-13T02:00:00Z", "surveyed", "H-1")])
        self.assertEqual(s["stages"].get("H-1"), "surveyed")
        self.assertNotIn("L-1", s["stages"])
        self.assertEqual(s["points"]["total"] - s["points"]["milestones"], self.stage_pts["surveyed"] * self.w["High"])

    def test_cluster_milestone_awarded_once_and_stays_awarded(self):
        cfg = config()
        first = cfg["cluster_milestones"][0]
        need = int(len(self.base) * first["share"] + 0.999)
        log = [tap(i + 1, f"2026-09-13T01:{i:02d}:00Z", "surveyed", f"F-{i}") for i in range(need)]
        s = run(self.base, log=log)
        self.assertIn(first["share"], s["clusters"]["C1"]["milestones"])
        # retiring surveyed accounts afterwards drops the share, but the milestone stays
        led = [change(i + 1, "2026-09-14T00:00:00Z", "mark_defunct", f"F-{i}") for i in range(need)]
        s2 = run(self.base, ledger=led, log=log)
        self.assertEqual(s2["points"]["milestones"], s["points"]["milestones"])

    def test_signal_review_points_only_inside_the_window(self):
        sig = {"id": "sig-x", "received_at": "2026-09-10T00:00:00Z"}
        fast = run(self.base, log=[tap(1, "2026-09-11T00:00:00Z", "signal_reviewed", signal_id="sig-x")], signals=[sig])
        slow = run(self.base, log=[tap(1, "2026-09-20T00:00:00Z", "signal_reviewed", signal_id="sig-x")], signals=[sig])
        self.assertEqual(fast["points"]["signal_reviews"], config()["signal_review"]["points"])
        self.assertEqual(slow["points"]["signal_reviews"], 0)


if __name__ == "__main__":
    unittest.main()
