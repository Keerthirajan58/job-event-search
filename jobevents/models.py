"""Canonical event record + deterministic normalization helpers.

Everything that can be computed by ordinary code is computed here: dates,
timezones, distance, city names, URLs, text flattening. No LLM touches any of it.
"""
import datetime as dt
import math
import re
import unicodedata
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

try:
    from zoneinfo import ZoneInfo
    _TZ_OK = True
except Exception:                                       # pragma: no cover
    _TZ_OK = False

from . import config

_LOCAL = ZoneInfo(config.LOCAL_TZ) if _TZ_OK else dt.timezone(dt.timedelta(hours=-7))


# ------------------------------------------------------------------ text utils
_WS = re.compile(r"\s+")
_TAG = re.compile(r"<[^>]+>")
_EMOJI = re.compile(
    "[" "\U0001F000-\U0001FAFF" "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF" "\U00002190-\U000021FF" "\U0000FE0F" "]+")


def strip_html(s):
    if not s:
        return ""
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", s)
    s = _TAG.sub(" ", s)
    for a, b in (("&amp;", "&"), ("&nbsp;", " "), ("&#39;", "'"), ("&quot;", '"'),
                 ("&lt;", "<"), ("&gt;", ">"), ("&rsquo;", "'"), ("&mdash;", "-")):
        s = s.replace(a, b)
    return _WS.sub(" ", s).strip()


def clean_text(s):
    if not s:
        return ""
    return _WS.sub(" ", unicodedata.normalize("NFKC", str(s))).strip()


def ascii_ratio(s):
    """Fraction of letters that are ASCII. Low value => non-English title."""
    letters = [c for c in (s or "") if c.isalpha()]
    if not letters:
        return 1.0
    return sum(1 for c in letters if ord(c) < 128) / len(letters)


def prosemirror_text(node):
    """Flatten Luma's `description_mirror` ProseMirror doc into plain text."""
    out = []

    def walk(n):
        if isinstance(n, dict):
            if n.get("type") == "text" and n.get("text"):
                out.append(n["text"])
            if n.get("type") in ("paragraph", "heading", "listItem", "bulletList"):
                out.append("\n")
            for c in n.get("content") or []:
                walk(c)
        elif isinstance(n, list):
            for c in n:
                walk(c)

    walk(node)
    return _WS.sub(" ", " ".join(out)).strip()


def norm_title_key(title):
    """Aggressive title key used only for duplicate detection."""
    t = _EMOJI.sub(" ", clean_text(title)).lower()
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", t)                 # drop parentheticals
    t = re.split(r"\s+(?:@|at)\s+", t)[0]                  # drop "@ Venue" tail
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    stop = {"the", "a", "an", "and", "of", "in", "at", "on", "for", "with", "to",
            "sf", "san", "francisco", "bay", "area", "2026", "2027"}
    toks = [w for w in t.split() if w not in stop and len(w) > 1]
    return " ".join(toks)


def canon_url(u):
    if not u:
        return ""
    u = u.strip()
    p = urlsplit_safe(u)
    if not p:
        return u
    scheme, netloc, path, _query, _frag = p
    netloc = netloc.lower().replace("www.", "")
    path = re.sub(r"/+$", "", path)
    return "%s://%s%s" % (scheme or "https", netloc, path)


def urlsplit_safe(u):
    try:
        import urllib.parse as up
        s = up.urlsplit(u)
        return (s.scheme, s.netloc, s.path, s.query, s.fragment)
    except Exception:
        return None


# ------------------------------------------------------------------ geo / time
def miles(lat, lon, lat2=None, lon2=None):
    """Great-circle miles from the configured anchor (or between two points)."""
    if lat is None or lon is None:
        return None
    lat2 = config.ANCHOR_LAT if lat2 is None else lat2
    lon2 = config.ANCHOR_LON if lon2 is None else lon2
    r = 3958.8
    p1, p2 = math.radians(lat), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


# Approximate centroids for Bay Area cities. Many Meetup and Eventbrite listings
# publish a city but no coordinates; without this they fell through the distance
# gate entirely (a Santa Clara event 45 mi away was being recommended) and got no
# travel-cost estimate. Accurate to a mile or two, which is enough for both.
CITY_COORDS = {
    "san francisco": (37.7749, -122.4194), "south san francisco": (37.6547, -122.4077),
    "daly city": (37.6879, -122.4702), "brisbane": (37.6808, -122.3999),
    "oakland": (37.8044, -122.2712), "berkeley": (37.8715, -122.2730),
    "emeryville": (37.8313, -122.2852), "alameda": (37.7652, -122.2416),
    "albany": (37.8869, -122.2977), "el cerrito": (37.9155, -122.3108),
    "richmond": (37.9358, -122.3477), "san leandro": (37.7249, -122.1561),
    "hayward": (37.6688, -122.0808), "fremont": (37.5485, -121.9886),
    "union city": (37.5934, -122.0438), "newark": (37.5297, -122.0402),
    "palo alto": (37.4419, -122.1430), "east palo alto": (37.4688, -122.1411),
    "menlo park": (37.4530, -122.1817), "mountain view": (37.3861, -122.0839),
    "sunnyvale": (37.3688, -122.0363), "santa clara": (37.3541, -121.9552),
    "san jose": (37.3382, -121.8863), "cupertino": (37.3230, -122.0322),
    "los altos": (37.3852, -122.1141), "redwood city": (37.4852, -122.2364),
    "san carlos": (37.5072, -122.2605), "belmont": (37.5202, -122.2758),
    "san mateo": (37.5630, -122.3255), "foster city": (37.5585, -122.2711),
    "burlingame": (37.5779, -122.3480), "millbrae": (37.5985, -122.3872),
    "hillsborough": (37.5741, -122.3794), "atherton": (37.4613, -122.1977),
    "portola valley": (37.3841, -122.2352), "stanford": (37.4275, -122.1697),
    "milpitas": (37.4323, -121.8996), "campbell": (37.2872, -121.9500),
    "saratoga": (37.2638, -122.0230), "sausalito": (37.8591, -122.4853),
    "mill valley": (37.9060, -122.5450), "tiburon": (37.8735, -122.4566),
    "san rafael": (37.9735, -122.5311), "larkspur": (37.9341, -122.5353),
    "corte madera": (37.9255, -122.5275), "walnut creek": (37.9101, -122.0652),
    "pleasanton": (37.6624, -121.8747), "dublin": (37.7022, -121.9358),
    "livermore": (37.6819, -121.7680), "danville": (37.8216, -121.9999),
    "san ramon": (37.7799, -121.9780), "concord": (37.9780, -122.0311),
    "colma": (37.6769, -122.4597), "pacifica": (37.6138, -122.4869),
    "half moon bay": (37.4636, -122.4286), "treasure island": (37.8235, -122.3708),
}


def city_coords(city):
    return CITY_COORDS.get((city or "").strip().lower())


def norm_city(raw):
    """'San Francisco, California' / 'SF, CA' -> 'san francisco'."""
    if not raw:
        return ""
    c = clean_text(raw).lower()
    c = re.split(r",", c)[0]
    c = re.sub(r"\b(ca|california|usa|us)\b", "", c).strip(" .,-")
    return {"sf": "san francisco", "s.f.": "san francisco"}.get(c, c)


def to_local(value, tzname=None):
    """Parse an ISO-8601 string (UTC 'Z' or with offset) into local aware dt."""
    if not value:
        return None
    s = str(value).strip().replace("Z", "+00:00")
    s = re.sub(r"\.(\d{3})\d+", r".\1", s)                 # trim micro-precision
    try:
        d = dt.datetime.fromisoformat(s)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                d = dt.datetime.strptime(s, fmt)
                break
            except ValueError:
                d = None
        if d is None:
            return None
    if d.tzinfo is None:
        tz = _LOCAL
        if tzname and _TZ_OK:
            try:
                tz = ZoneInfo(tzname)
            except Exception:
                pass
        d = d.replace(tzinfo=tz)
    target = _LOCAL
    if tzname and _TZ_OK:
        try:
            target = ZoneInfo(tzname)
        except Exception:
            pass
    return d.astimezone(target)


def local_now():
    return dt.datetime.now(tz=_LOCAL)


# ------------------------------------------------------------------ the record
@dataclass
class Event:
    # identity / provenance
    uid: str = ""
    sources: List[Dict[str, str]] = field(default_factory=list)  # [{source,url,id}]
    # core facts
    title: str = ""
    description: str = ""
    start: Optional[dt.datetime] = None
    end: Optional[dt.datetime] = None
    venue: str = ""
    address: str = ""
    city: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    is_online: bool = False
    # organiser / people (public only)
    organizer: str = ""
    organizer_bio: str = ""
    speakers: List[str] = field(default_factory=list)
    # registration
    url: str = ""
    is_free: Optional[bool] = None
    price: Optional[float] = None
    sold_out: bool = False
    requires_approval: bool = False
    registration_open: bool = True
    attendee_count: Optional[int] = None
    capacity: Optional[int] = None
    # derived
    distance_mi: Optional[float] = None
    coords_approx: bool = False
    # scoring output
    score: int = 0
    category: str = ""
    confidence: str = ""
    reasons: List[str] = field(default_factory=list)
    penalties: List[str] = field(default_factory=list)
    signals: Dict[str, Any] = field(default_factory=dict)
    fit_notes: List[str] = field(default_factory=list)
    who_to_meet: List[str] = field(default_factory=list)
    opener: str = ""
    followup: str = ""
    verified: bool = False
    verify_note: str = ""
    # enrichment (jobevents/enrich.py)
    verdict: str = ""
    cost: Dict[str, Any] = field(default_factory=dict)
    companies: List[Dict[str, str]] = field(default_factory=list)
    openings: List[Dict[str, Any]] = field(default_factory=list)
    opening_summary: str = ""
    changed_note: str = ""
    gate: str = ""                      # non-empty => excluded, with the reason

    # ---- convenience
    @property
    def date_key(self):
        return self.start.date().isoformat() if self.start else ""

    @property
    def time_str(self):
        if not self.start:
            return ""
        s = self.start.strftime("%-I:%M %p") if _pct_dash() else self.start.strftime("%I:%M %p").lstrip("0")
        return s

    def text_blob(self):
        parts = [self.title, self.description, self.organizer, self.organizer_bio,
                 self.venue, " ".join(self.speakers)]
        return clean_text(" \n ".join(p for p in parts if p))

    def to_dict(self):
        d = asdict(self)
        d["start"] = self.start.isoformat() if self.start else None
        d["end"] = self.end.isoformat() if self.end else None
        d["date"] = self.date_key
        d["time"] = self.time_str
        return d


def _pct_dash():
    try:
        dt.datetime(2026, 9, 1, 18, 0).strftime("%-I")
        return True
    except Exception:
        return False
