"""Central configuration. Edit this file to retarget the tool."""
import datetime as dt

# ---------------------------------------------------------------- time window
# Inclusive local-date window the tool reports on.
WINDOW_START = dt.date(2026, 9, 1)
WINDOW_DAYS = 61          # through 2026-10-31, so SF Tech Week (Oct 5-11) is covered
LOCAL_TZ = "America/Los_Angeles"

# ---------------------------------------------------------------- geography
# HOME = Ocean View / Balboa Park area, SF 94112 - a neighbourhood centroid rather
# than a street address, because this repo is public. The transit model only needs
# to know which station you walk to; using the area centroid instead of the exact
# address moves every estimate by about a minute. Set it precisely in a local
# override if you want, but do not commit that.
# Travel time and fare are computed from here, not from downtown - see
# jobevents/transit.py for why distance alone is misleading in the Bay Area.
HOME_LAT, HOME_LON = 37.7196, -122.4550

# Anchor for the geo gate and for "how central is this" reporting.
ANCHOR_LAT, ANCHOR_LON = 37.7893, -122.4013

# Concentric relevance rings. Beyond HARD_MAX_MI an event is gated out.
CORE_MI = 4.0     # walk / short transit from downtown  -> no travel penalty
NEAR_MI = 12.0    # within SF + immediate border        -> tiny penalty
REACH_MI = 30.0   # Peninsula / East Bay via Caltrain-BART -> real penalty
HARD_MAX_MI = 35.0

# Cities that count as "San Francisco proper" after normalization.
SF_PROPER = {"san francisco", "south san francisco", "daly city", "brisbane"}

# ---------------------------------------------------------------- sources
# Luma geo firehose: probe points. One point already covers ~50mi, but multiple
# anchors guard against per-query result caps.
LUMA_GEO_POINTS = [
    ("sf-downtown", 37.7893, -122.4013),
    ("sf-mission", 37.7599, -122.4148),
    ("peninsula", 37.4419, -122.1430),
]

# Luma *curated calendars* = high-precision tier. Slug -> why we trust it.
# These are resolved slug -> cal-id at runtime; unknown slugs are skipped safely.
# Each slug was probed live; only those that actually produced in-window Bay Area
# in-person events are kept. Adding a dead calendar costs a request and yields
# nothing, so the registry is validated rather than aspirational.
LUMA_TRUSTED_CALENDARS = {
    "sftw": "SF Tech Week (a16z), Oct 5-11 - highest-density networking week of the year",
    "ai-sf": "AI Events - San Francisco (community aggregator calendar)",
    "llamalounge": "Llama Lounge - AI startup series; hiring startups attend",
    "sfdevtools": "SF devtools founder community",
    "cerebras": "Cerebras developer events",
    "baseten": "Baseten (inference infra) events",
    "neo4j": "Neo4j developer events",
}

# Meetup discovery keywords (each is one robots-allowed /find/ page fetch).
MEETUP_KEYWORDS = [
    "machine learning", "artificial intelligence", "software engineering",
    "llm", "data science", "python", "developer", "startup", "hiring",
    "backend", "infrastructure", "nlp",
]
MEETUP_LOCATION = "us--ca--San Francisco"
MEETUP_DISTANCE = "tenMiles"

# Eventbrite browse slices (robots-allowed /d/ pages; /api/v3/destination is NOT used).
EVENTBRITE_SLICES = [
    ("ca--san-francisco", "tech--events"),
    ("ca--san-francisco", "business--events"),
]
EVENTBRITE_MAX_PAGES = 3

HACKERX_EVENTS_URL = "https://hackerx.org/events/"

# ---------------------------------------------------------------- politeness
# Identifies the tool without publishing a personal address. Sites that want to
# contact an operator can reach the repo.
HTTP_UA = ("JobEventSearch/1.0 (personal job-search tool; "
           "+https://github.com/topics/job-search)")
HTTP_MIN_INTERVAL = 0.6   # seconds between requests to the same host
HTTP_TIMEOUT = 40
HTTP_RETRIES = 3
CACHE_TTL_SECONDS = 6 * 3600

# ---------------------------------------------------------------- output
DB_PATH = "data/events.db"
# Your logged outcomes. Kept separate from events.db because events.db is a
# regenerable 5 MB cache (CI restores it from actions/cache) while this file is
# irreplaceable, tiny, and belongs in git.
ATTENDANCE_DB_PATH = "data/attendance.db"
CACHE_DIR = "data/cache"
OUT_DIR = "out"

# Recommend at most this many per day; below MIN_SCORE we say "nothing worthwhile".
MAX_PER_DAY = 4
# CI safety net: if a source is blocked from a datacenter IP we would otherwise
# overwrite a good dashboard with an empty one. Below this many unique in-window
# events, run.py exits non-zero and the deploy step is skipped.
MIN_EVENTS_SANITY = 120
MIN_SCORE_RECOMMEND = 45
MIN_SCORE_REVIEW = 30      # between REVIEW and RECOMMEND -> shown in review queue

# ---------------------------------------------------------------- verdicts
# Shown as a badge so the dashboard answers "should I go?" before "what score?"
VERDICT_GO = 78            # clear yes
VERDICT_WORTH = 60         # worth the evening
VERDICT_MAYBE = 45         # only if nothing better

# ------------------------------------------------- public job-board (ATS) lookup
# Greenhouse and Ashby both serve public, keyless JSON job boards; Lever needs an
# exact org slug so only verified ones are listed. Company name -> (provider, slug).
# Used to answer "is this company actually hiring someone like me right now?"
# Every slug below was verified live to return postings. Slugs that 404'd were
# removed rather than left in to fail on every run.
ATS_BOARDS = {
    "anthropic": ("greenhouse", "anthropic"),
    "databricks": ("greenhouse", "databricks"),
    "openai": ("ashby", "openai"),
    "scale ai": ("greenhouse", "scaleai"),
    "stripe": ("greenhouse", "stripe"),
    "figma": ("greenhouse", "figma"),
    "notion": ("ashby", "notion"),
    "airbnb": ("greenhouse", "airbnb"),
    "pinterest": ("greenhouse", "pinterest"),
    "reddit": ("greenhouse", "reddit"),
    "discord": ("greenhouse", "discord"),
    "dropbox": ("greenhouse", "dropbox"),
    "instacart": ("greenhouse", "instacart"),
    "doordash": ("greenhouse", "doordashusa"),
    "robinhood": ("greenhouse", "robinhood"),
    "coinbase": ("greenhouse", "coinbase"),
    "cloudflare": ("greenhouse", "cloudflare"),
    "datadog": ("greenhouse", "datadog"),
    "mongodb": ("greenhouse", "mongodb"),
    "snowflake": ("ashby", "snowflake"),
    "gitlab": ("greenhouse", "gitlab"),
    "samsara": ("greenhouse", "samsara"),
    "verkada": ("greenhouse", "verkada"),
    "benchling": ("ashby", "benchling"),
    "waymo": ("greenhouse", "waymo"),
    "anduril": ("greenhouse", "andurilindustries"),
    "sierra": ("ashby", "sierra"),
    "glean": ("greenhouse", "gleanwork"),
    "harvey": ("ashby", "harvey"),
    "ramp": ("ashby", "ramp"),
    "cursor": ("ashby", "cursor"),
    "perplexity": ("ashby", "perplexity"),
    "modal": ("ashby", "modal"),
    "baseten": ("ashby", "baseten"),
    "fireworks ai": ("ashby", "fireworks"),
    "cerebras": ("ashby", "cerebras"),
    "vercel": ("ashby", "vercel"),
    "supabase": ("ashby", "supabase"),
    "temporal": ("ashby", "temporal"),
    "workos": ("ashby", "workos"),
    "langchain": ("ashby", "langchain"),
    "anyscale": ("ashby", "anyscale"),
    "clickhouse": ("ashby", "clickhouse"),
}

# Roles worth surfacing. Anything not matching is ignored rather than shown.
ATS_ROLE_PATTERNS = [
    r"software engineer", r"\bml engineer\b", r"machine learning engineer",
    r"\bai engineer\b", r"applied (?:ml|ai|scientist|research)", r"research engineer",
    r"\bnlp\b", r"\bllm\b", r"data engineer", r"backend engineer",
    r"full-?stack engineer", r"platform engineer", r"infrastructure engineer",
    r"member of technical staff", r"forward deployed engineer",
    r"\bsolutions engineer\b", r"\bsystems engineer\b", r"\bsearch engineer\b",
]
# Matched against a title that ALREADY passed ATS_ROLE_PATTERNS, purely to sort
# new-grad-friendly postings first.
ATS_NEWGRAD_PATTERNS = [r"new ?grad", r"early career", r"university grad",
                        r"\bentry[- ]level\b", r"\bi{1,2}\b$", r"\bjunior\b"]
ATS_LOCATION_HINTS = ["san francisco", "bay area", "palo alto", "mountain view",
                      "menlo park", "sunnyvale", "santa clara", "san jose",
                      "redwood city", "oakland", "berkeley", "remote - us",
                      "remote (us", "us remote", "united states"]
ATS_CACHE_TTL = 24 * 3600
