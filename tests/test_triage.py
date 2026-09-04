"""The dashboard -> Python bridge. Must never break a run, whatever it contains."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jobevents import triage


class TestTriage(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "triage.json")

    def write(self, obj):
        with open(self.path, "w") as fh:
            json.dump(obj, fh)

    def test_missing_file(self):
        self.assertEqual(triage.load(self.path), {})

    def test_valid_marks(self):
        self.write({"u1": {"s": "going", "t": 5, "m": {"ti": "X"}},
                    "u2": {"s": "saved", "t": 6, "m": {}}})
        got = triage.load(self.path)
        self.assertEqual(got["u1"]["s"], "going")
        self.assertEqual(got["u1"]["t"], 5)
        self.assertEqual(got["u1"]["m"]["ti"], "X")

    def test_unknown_status_is_rejected(self):
        self.write({"u1": {"s": "maybe_later"}, "u2": {"s": "going"}})
        self.assertEqual(set(triage.load(self.path)), {"u2"})

    def test_by_status(self):
        self.write({"a": {"s": "going"}, "b": {"s": "going"}, "c": {"s": "hidden"}})
        m = triage.load(self.path)
        self.assertEqual(triage.by_status(m, "going"), {"a", "b"})
        self.assertEqual(triage.by_status(m, "hidden"), {"c"})
        self.assertEqual(triage.by_status(m, "saved"), set())

    def test_corrupt_and_wrong_shapes_do_not_raise(self):
        for junk in ("{oops", "[1,2,3]", '"a string"', "null"):
            with open(self.path, "w") as fh:
                fh.write(junk)
            self.assertEqual(triage.load(self.path), {})
        self.write({"u1": "not a dict"})
        self.assertEqual(triage.load(self.path), {})

    def test_missing_timestamp_defaults_to_zero(self):
        self.write({"u1": {"s": "going"}})
        self.assertEqual(triage.load(self.path)["u1"]["t"], 0)

    def test_summary_mentions_the_missing_file(self):
        self.assertIn("no triage file", triage.summary({}))
        self.assertIn("1 going", triage.summary({"a": {"s": "going"}}))


if __name__ == "__main__":
    unittest.main()
