import unittest
from unittest.mock import MagicMock

from app.api.fields import generate_next_field_id


class FieldIdGenerationTests(unittest.TestCase):
    def test_uses_max_suffix_not_row_count(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [
            ("FLD-2026-000001",),
            ("FLD-2026-000003",),
        ]

        field_id = generate_next_field_id(db, year=2026)
        self.assertEqual(field_id, "FLD-2026-000004")

    def test_starts_at_one_when_no_existing_ids(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        field_id = generate_next_field_id(db, year=2026)
        self.assertEqual(field_id, "FLD-2026-000001")


if __name__ == "__main__":
    unittest.main()
