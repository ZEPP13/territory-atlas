import unittest
from helpers import change, entity
from wartable.registry import LedgerError, apply_ledger, is_visible, resolve


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.base = [entity("A-1"), entity("A-2"), entity("A-3")]

    def test_no_changes_leaves_registry_untouched(self):
        ents, audit = apply_ledger(self.base, [])
        self.assertEqual(audit, [])
        self.assertTrue(all(is_visible(e) for e in ents.values()))

    def test_base_is_never_mutated(self):
        apply_ledger(self.base, [change(1, "2026-09-13T01:00:00Z", "mark_defunct", "A-1")])
        self.assertEqual(self.base[0]["status"]["value"], "active")

    def test_defunct_hides_but_keeps_the_record(self):
        ents, _ = apply_ledger(self.base, [change(1, "2026-09-13T01:00:00Z", "mark_defunct", "A-1")])
        self.assertIn("A-1", ents)
        self.assertFalse(is_visible(ents["A-1"]))
        self.assertEqual(ents["A-1"]["status"]["reason"], "test reason")

    def test_latest_change_wins_regardless_of_file_order(self):
        later = change(2, "2026-09-13T02:00:00Z", "reinstate", "A-1")
        earlier = change(1, "2026-09-13T01:00:00Z", "mark_not_a_fit", "A-1")
        ents, _ = apply_ledger(self.base, [later, earlier])
        self.assertTrue(is_visible(ents["A-1"]))

    def test_same_timestamp_changes_apply_in_file_order(self):
        ts = "2026-09-13T01:00:00.000Z"
        ents, _ = apply_ledger(self.base, [change("f", ts, "mark_not_a_fit", "A-1"),
                                           change("0", ts, "reinstate", "A-1")])
        self.assertTrue(is_visible(ents["A-1"]))
        ents, _ = apply_ledger(self.base, [change("0", ts, "reinstate", "A-1"),
                                           change("f", ts, "mark_not_a_fit", "A-1")])
        self.assertFalse(is_visible(ents["A-1"]))

    def test_duplicate_redirects_to_target(self):
        ents, _ = apply_ledger(self.base, [change(1, "2026-09-13T01:00:00Z", "mark_duplicate", "A-2", duplicate_of="A-1")])
        self.assertEqual(resolve(ents, "A-2"), "A-1")
        self.assertFalse(is_visible(ents["A-2"]))

    def test_duplicate_loops_are_refused(self):
        with self.assertRaises(LedgerError):
            apply_ledger(self.base, [
                change(1, "2026-09-13T01:00:00Z", "mark_duplicate", "A-1", duplicate_of="A-2"),
                change(2, "2026-09-13T02:00:00Z", "mark_duplicate", "A-2", duplicate_of="A-1")])

    def test_unknown_entity_is_refused(self):
        with self.assertRaises(LedgerError):
            apply_ledger(self.base, [change(1, "2026-09-13T01:00:00Z", "mark_defunct", "NOPE")])

    def test_correct_only_accepts_whitelisted_fields(self):
        ok = change(1, "2026-09-13T01:00:00Z", "correct", "A-1", field="name", value="Renamed")
        ents, _ = apply_ledger(self.base, [ok])
        self.assertEqual(ents["A-1"]["name"], "Renamed")
        with self.assertRaises(LedgerError):
            apply_ledger(self.base, [change(2, "2026-09-13T01:00:00Z", "correct", "A-1", field="potential", value="High")])

    def test_add_entity_requires_a_schema_valid_entity(self):
        good = change(1, "2026-09-13T01:00:00Z", "add_entity", "OEM-1", entity=entity("OEM-1", kind="oem"))
        ents, _ = apply_ledger(self.base, [good])
        self.assertEqual(ents["OEM-1"]["kind"], "oem")
        bad_ent = entity("OEM-2", kind="oem"); bad_ent["lat"] = 99
        with self.assertRaises(LedgerError):
            apply_ledger(self.base, [change(2, "2026-09-13T01:00:00Z", "add_entity", "OEM-2", entity=bad_ent)])


if __name__ == "__main__":
    unittest.main()
