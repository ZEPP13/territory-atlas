"""Integration tests against the REAL merged registry. Slower: runs the full merge once."""
import unittest
import warnings
from helpers import entity  # noqa: F401  (path setup)
from wartable.registry import build_base as _build_base


def build_base():
    # 04-outputs/merge.py is legacy and deliberately unmodified; it leaves files open
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        return _build_base()


class RealRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = build_base()
        cls.fac = [e for e in cls.base if e["kind"] == "facility"]

    def test_every_record_is_accounted_for_by_scope(self):
        scopes = {}
        for e in self.base:
            scopes[e["scope"]] = scopes.get(e["scope"], 0) + 1
        self.assertEqual(sum(scopes.values()), len(self.base))
        self.assertEqual(set(scopes) - {"core", "out_of_portfolio", "out_of_territory"}, set())

    def test_municipal_utilities_stay_out_of_portfolio(self):
        for e in self.base:
            if e["sector"] in ("municipal-water", "municipal-wastewater"):
                self.assertEqual(e["scope"], "out_of_portfolio", e["id"])

    def test_industry_alone_never_reaches_high(self):
        """No High unless the plant has a reported scale figure or an independently filed fact."""
        for e in self.fac:
            p = e["potential"]
            if p["band"] == "High":
                self.assertTrue(p["scale_verified"] or p["verified_facts"], e["id"])

    def test_missing_scale_is_not_scored_as_zero(self):
        for e in self.fac:
            if not e["potential"]["scale_verified"]:
                self.assertGreater(e["potential"]["factors"]["scale"], 0, e["id"])

    def test_placeholder_records_are_insufficient_information(self):
        for e in self.fac:
            if any(f["k"] == "placeholder" for f in e["flags"]):
                self.assertEqual(e["potential"]["band"], "Insufficient information", e["id"])

    def test_every_source_label_is_a_real_label_not_a_generic_epa(self):
        allowed = {"Industrial Info", "Virginia DEQ", "EPA TRI 2024", "EPA GHGRP 2023", "EPA eGRID 2023",
                   "Unverified research"}
        for e in self.base:
            for s in e["sources"]:
                self.assertIn(s["label"], allowed, e["id"])

    def test_no_solar_storage_or_wind_generation_remains(self):
        self.assertFalse([e["id"] for e in self.base if e["sector"] == "solar-storage"])
        self.assertFalse([e["name"] for e in self.base if "solar & storage" in e["name"].lower()])

    def test_waste_services_are_not_counted_as_power(self):
        for e in self.base:
            if e["sector"] == "waste-services":
                self.assertNotEqual(e["family"], "power", e["name"])

    def test_power_plant_types_respect_their_ceilings(self):
        ceiling = {"peaker": "Medium", "hydro": "Medium", "landfill_gas": "Low", "small_unit": "Low"}
        rank = {"Insufficient information": -1, "Low": 0, "Medium": 1, "High": 2}
        for e in self.fac:
            sub = e["potential"].get("subtype")
            if sub in ceiling:
                self.assertLessEqual(rank[e["potential"]["band"]], rank[ceiling[sub]], e["name"])

    def test_nuclear_plants_rate_high(self):
        nuc = [e for e in self.fac if "nuclear power station" in e["name"].lower()]
        self.assertGreaterEqual(len(nuc), 2)
        self.assertTrue(all(e["potential"]["band"] == "High" for e in nuc))

    def test_every_power_generation_record_has_a_subtype(self):
        for e in self.fac:
            if e["sector"] == "power-generation":
                self.assertIsNotNone(e["potential"].get("subtype"), e["name"])

    def test_ids_are_unique(self):
        self.assertEqual(len({e["id"] for e in self.base}), len(self.base))

    def test_id_repair_is_stable_and_uses_the_state_registration_number(self):
        ms = [e for e in self.base if e["id"].startswith("C9-DEQ-MICROSOFTC")]
        self.assertGreater(len(ms), 1)
        self.assertTrue(all(e["id"] != "C9-DEQ-MICROSOFTC" for e in ms))
        again = {e["id"] for e in build_base()}
        self.assertTrue({e["id"] for e in self.base} == again)


if __name__ == "__main__":
    unittest.main()
