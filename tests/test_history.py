"""first_seen persistence - the thing whose loss made the New tab useless."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jobevents import history


class TestHistory(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "first_seen.json")
        self.today = dt.date(2026, 9, 10)

    def test_missing_file_is_empty_not_an_error(self):
        self.assertEqual(history.load(self.path), {})

    def test_roundtrip(self):
        history.save({}, {"a", "b"}, today=self.today, path=self.path)
        self.assertEqual(history.load(self.path),
                         {"a": "2026-09-10", "b": "2026-09-10"})

    def test_existing_dates_are_never_overwritten(self):
        """The whole point: a uid keeps the date it was FIRST seen."""
        history.save({"a": "2026-08-01"}, {"a", "b"}, today=self.today, path=self.path)
        got = history.load(self.path)
        self.assertEqual(got["a"], "2026-08-01")   # preserved
        self.assertEqual(got["b"], "2026-09-10")   # new

    def test_age_days(self):
        k = {"a": "2026-09-08", "b": "2026-09-10"}
        self.assertEqual(history.age_days(k, "a", self.today), 2)
        self.assertEqual(history.age_days(k, "b", self.today), 0)
        self.assertIsNone(history.age_days(k, "nope", self.today))

    def test_old_unseen_entries_are_pruned_but_seen_ones_survive(self):
        old = (self.today - dt.timedelta(days=history.KEEP_DAYS + 5)).isoformat()
        kept = history.save({"stale": old, "ancient_but_live": old},
                            {"ancient_but_live"}, today=self.today, path=self.path)
        self.assertNotIn("stale", kept)
        self.assertIn("ancient_but_live", kept)

    def test_recent_unseen_entries_survive(self):
        recent = (self.today - dt.timedelta(days=3)).isoformat()
        kept = history.save({"r": recent}, set(), today=self.today, path=self.path)
        self.assertIn("r", kept)

    def test_corrupt_file_does_not_raise(self):
        with open(self.path, "w") as fh:
            fh.write("{not json")
        self.assertEqual(history.load(self.path), {})

    def test_garbage_values_are_dropped(self):
        with open(self.path, "w") as fh:
            json.dump({"ok": "2026-09-01", "bad": "nonsense",
                       "wrongtype": 5, "empty": ""}, fh)
        self.assertEqual(history.load(self.path), {"ok": "2026-09-01"})

    def test_write_is_atomic_no_tmp_left_behind(self):
        history.save({}, {"a"}, today=self.today, path=self.path)
        self.assertFalse(os.path.exists(self.path + ".tmp"))


if __name__ == "__main__":
    unittest.main()
