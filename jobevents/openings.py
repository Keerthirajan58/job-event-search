"""Verified job openings from public, keyless ATS job boards.

The point of this module is to turn "I should attend this" into "I should attend
this because Company X is there and has 3 ML Engineer openings in SF."

Only two providers are used, because only these two serve a genuinely public,
keyless JSON board (both verified live):
  * Greenhouse  https://boards-api.greenhouse.io/v1/boards/<slug>/jobs
  * Ashby       https://api.ashbyhq.com/posting-api/job-board/<slug>

Lever is deliberately excluded: its endpoint needs an exact org slug and every
guess 404'd, and guessing slugs to see what sticks is not a reliable design.

Hard rule: a company is only reported as hiring when a real posting came back
from its own board. If the lookup fails, we say the lookup failed. We never infer
"they're probably hiring" - that is exactly the kind of invented fact that would
make the tool untrustworthy.
"""
import json
import re

from . import config, http

_ROLE_RX = [re.compile(p, re.I) for p in config.ATS_ROLE_PATTERNS]
_NEWGRAD_RX = [re.compile(p, re.I) for p in config.ATS_NEWGRAD_PATTERNS]
# Titles a 2026 new grad should not be shown; "Sr" needed adding after a live
# "Sr Software Engineer- CXI" slipped through.
_SENIOR_RX = re.compile(
    r"\b(?:staff|principal|senior|sr\.?|distinguished|lead|director|vp|"
    r"head of|manager|architect|fellow)\b", re.I)
_cache = {}


def _relevant_location(text):
    t = (text or "").lower()
    return any(h in t for h in config.ATS_LOCATION_HINTS)


def _fetch_greenhouse(slug):
    d = http.get_json("https://boards-api.greenhouse.io/v1/boards/%s/jobs" % slug,
                      ttl=config.ATS_CACHE_TTL)
    out = []
    for j in d.get("jobs") or []:
        out.append({"title": j.get("title") or "",
                    "location": ((j.get("location") or {}).get("name") or ""),
                    "url": j.get("absolute_url") or ""})
    return out


def _fetch_ashby(slug):
    d = http.get_json("https://api.ashbyhq.com/posting-api/job-board/%s" % slug,
                      ttl=config.ATS_CACHE_TTL)
    out = []
    for j in d.get("jobs") or []:
        out.append({"title": j.get("title") or "",
                    "location": j.get("location") or "",
                    "url": j.get("jobUrl") or j.get("applyUrl") or ""})
    return out


def lookup(company, max_roles=4):
    """Return {'status':..., 'roles':[...], 'total':n, 'board':url} for a company."""
    key = (company or "").strip().lower()
    if key in _cache:
        return _cache[key]

    board = config.ATS_BOARDS.get(key)
    if not board:
        res = {"status": "no_board", "roles": [], "total": 0,
               "note": "no public job board mapped for %s" % company}
        _cache[key] = res
        return res

    provider, slug = board
    board_url = ("https://job-boards.greenhouse.io/%s" % slug if provider == "greenhouse"
                 else "https://jobs.ashbyhq.com/%s" % slug)
    try:
        jobs = _fetch_greenhouse(slug) if provider == "greenhouse" else _fetch_ashby(slug)
    except http.Blocked as exc:
        res = {"status": "blocked", "roles": [], "total": 0, "note": str(exc)}
        _cache[key] = res
        return res
    except Exception as exc:
        res = {"status": "error", "roles": [], "total": 0,
               "note": "%s lookup failed (%s)" % (provider, type(exc).__name__)}
        _cache[key] = res
        return res

    matched = []
    for j in jobs:
        title = j["title"]
        if not any(r.search(title) for r in _ROLE_RX):
            continue
        if not _relevant_location(j["location"]):
            continue
        # New-grad relevance: keep IC roles, drop management/staff+ titles.
        if _SENIOR_RX.search(title):
            continue
        matched.append(j)

    matched.sort(key=lambda j: (0 if any(r.search(j["title"]) for r in _NEWGRAD_RX)
                                else 1, len(j["title"])))
    res = {"status": "ok", "roles": matched[:max_roles], "total": len(matched),
           "board": board_url, "provider": provider, "scanned": len(jobs)}
    _cache[key] = res
    return res


def enrich(companies, log=None):
    """Look up several companies; returns list of results that found openings."""
    found = []
    for c in companies:
        r = lookup(c)
        if r["status"] == "ok" and r["total"] > 0:
            r["company"] = c
            found.append(r)
        elif log and r["status"] in ("error", "blocked"):
            log("      openings lookup %s: %s" % (c, r.get("note")))
    found.sort(key=lambda r: -r["total"])
    return found
