"""Reads the Going / Saved / Hidden marks exported from the dashboard.

The dashboard is a static page on GitHub Pages, so it keeps your marks in the
browser's localStorage. That is the right call for a single-user tool - the
alternatives were embedding a write token in a public page, or paying for a
backend - but it leaves the Python side blind.

This module is the bridge. The dashboard's "Sync" button hands you a blob of JSON;
drop it in data/triage.json and commit, and the daily alerts start knowing which
events you have actually registered for.

Everything here degrades to "no marks" if the file is missing or malformed. A
broken sync file must never break a run.
"""
import json
import os

PATH = "data/triage.json"


def load(path=None):
    """{uid: {"s": "going"|"saved"|"hidden", "m": {...snapshot...}}}"""
    path = path or PATH
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (ValueError, OSError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out = {}
    for uid, rec in raw.items():
        if not isinstance(rec, dict):
            continue
        status = rec.get("s")
        if status in ("going", "saved", "hidden"):
            ts = rec.get("t")
            out[str(uid)] = {"s": status, "m": rec.get("m") or {},
                             "t": ts if isinstance(ts, (int, float)) else 0}
    return out


def by_status(marks, status):
    return {u for u, r in marks.items() if r["s"] == status}


def summary(marks):
    if not marks:
        return "no triage file (data/triage.json) - alerts cannot tell what you already registered for"
    n = {s: len(by_status(marks, s)) for s in ("going", "saved", "hidden")}
    return "triage: %d going, %d saved, %d hidden" % (n["going"], n["saved"], n["hidden"])
