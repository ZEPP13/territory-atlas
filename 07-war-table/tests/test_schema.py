import unittest
from helpers import entity
from wartable.schema import SchemaError, check_schema, load, validate


class SchemaValidatorTests(unittest.TestCase):
    def test_all_project_schemas_load_and_use_only_supported_keywords(self):
        for name in ("entity", "ledger_change", "signal", "logbook_event"):
            self.assertIsInstance(load(name), dict)

    def test_unsupported_keyword_is_refused_not_ignored(self):
        with self.assertRaises(SchemaError):
            check_schema({"type": "object", "oneOf": [{"type": "string"}]})

    def test_types_and_bool_is_not_a_number(self):
        self.assertTrue(validate(True, {"type": "number"}))
        self.assertFalse(validate(3, {"type": "integer"}))
        self.assertTrue(validate(3.5, {"type": "integer"}))

    def test_additional_properties_false_rejects_unknown_fields(self):
        errs = validate({"a": 1, "b": 2}, {"type": "object", "properties": {"a": {}}, "additionalProperties": False})
        self.assertTrue(any("unexpected field 'b'" in e for e in errs))

    def test_date_time_format(self):
        s = {"type": "string", "format": "date-time"}
        self.assertFalse(validate("2026-09-13T08:00:00Z", s))
        self.assertTrue(validate("2026-13-40T08:00:00Z", s))
        self.assertTrue(validate("yesterday", s))

    def test_valid_entity_passes_and_bad_cluster_fails(self):
        self.assertEqual(validate(entity("X-1"), load("entity")), [])
        bad = entity("X-2"); bad["cluster"] = "C13"
        self.assertTrue(validate(bad, load("entity")))

    def test_role_field_refuses_emails_and_phone_numbers(self):
        s = load("logbook_event")
        base = {"id": "lb-000000000001", "ts": "2026-09-13T08:00:00Z", "actor": "joe", "action": "met", "entity_id": "X-1"}
        self.assertFalse(validate({**base, "role": "E&I maintenance supervisor"}, s))
        self.assertTrue(validate({**base, "role": "jane@example.com"}, s))
        self.assertTrue(validate({**base, "role": "call 804 555 0100"}, s))


if __name__ == "__main__":
    unittest.main()
