"""Extract companies from an event listing, WITH the role they play.

"Sponsored by Anthropic", "speakers from Scale AI", "hosted at Datadog" and a
passing mention of Kubernetes-at-Google are four different facts. Only the first
three mean people from that company are likely in the room, which is the only
reason a job seeker cares.

Roles, strongest first:
  venue    - the event is physically at their office; their engineers walk in
  host     - they organise it; their staff run it
  sponsor  - they pay for it; they send people and often recruit
  speaker  - at least one of their engineers is presenting
  mention  - named somewhere in the body. Weak. Reported, never scored highly.

Nothing here is inferred. If the listing does not say it, we do not claim it.
"""
import re

from .features import COMPANIES, _company_pattern

_RX = [(c, re.compile(_company_pattern(c), re.I)) for c in COMPANIES]

# Phrases that introduce a company in a particular role. The captured window
# after the phrase is scanned for company names.
_ROLE_LEADS = [
    ("sponsor", re.compile(
        r"(?:sponsor(?:ed|s)?\s+by|sponsors?\s*:|brought\s+to\s+you\s+by|"
        r"in\s+partnership\s+with|partnered\s+with|powered\s+by|"
        r"with\s+support\s+from|thanks\s+to)\s*:?\s*", re.I)),
    ("speaker", re.compile(
        r"(?:speakers?\s+from|speakers?\s*:|talks?\s+(?:from|by)|"
        r"featuring|guest\s+speakers?\s*:?|presented\s+by|panelists?\s*:?|"
        r"joining\s+us\s+from|engineers?\s+from)\s*:?\s*", re.I)),
    ("host", re.compile(
        r"(?:hosted\s+by|co-?hosted\s+(?:by|with)|organi[sz]ed\s+by|"
        r"in\s+collaboration\s+with)\s*:?\s*", re.I)),
    ("venue", re.compile(
        r"(?:hosted\s+at|located\s+at|venue\s*:|at\s+the\s+offices?\s+of|"
        r"we(?:'re| are)\s+at)\s*:?\s*", re.I)),
]
# Sponsors and speakers are listed in ONE sentence. A wide window bleeds into the
# next sentence: at 180 chars, "Sponsored by Anthropic, Modal and Vercel." was
# also claiming Scale AI, Snowflake and Uber from the sentences after it.
WINDOW = 110
_SENT_END = re.compile(r"[.!?\n;]")


def _segment(text, start):
    """Text after a role phrase, cut at the first sentence boundary."""
    seg = text[start:start + WINDOW]
    m = _SENT_END.search(seg)
    return seg[:m.start()] if m else seg


def _find_in(text):
    out = []
    for name, rx in _RX:
        if rx.search(text or ""):
            out.append(name)
    return out


def extract(ev):
    """Return {company: {'role':..., 'evidence':...}} strongest role per company."""
    blob = ev.text_blob()
    headline = " ".join([ev.title or "", ev.venue or "", ev.organizer or ""])
    rank = {"venue": 4, "host": 3, "sponsor": 2, "speaker": 1, "mention": 0}
    found = {}

    def offer(company, role, evidence):
        cur = found.get(company)
        if cur is None or rank[role] > rank[cur["role"]]:
            found[company] = {"role": role, "evidence": evidence[:120].strip()}

    # title / venue / organiser -> the company is structurally involved
    for c in _find_in(headline):
        role = "venue" if c in (ev.venue or "").lower() else "host"
        offer(c, role, headline)

    # role-phrase windows in the body
    for role, lead in _ROLE_LEADS:
        for m in lead.finditer(blob):
            seg = _segment(blob, m.end())
            if not seg.strip():
                continue
            # Scan the lead phrase together with the segment: "Sponsored by" is
            # itself the corporate context that ambiguous names like Modal, Box
            # and Block require, and it sits outside the window.
            scan = m.group(0) + seg
            for c in _find_in(scan):
                offer(c, role, scan.strip())

    # speaker bios often name the employer directly
    for sp in ev.speakers or []:
        for c in _find_in(sp):
            offer(c, "speaker", "listed guest: %s" % sp)

    # remaining body mentions, explicitly weak
    for c in _find_in(blob):
        offer(c, "mention", "named in the description")

    return found


# .title() mangles camelCase and acronyms: "workos" -> "Workos", "openai" ->
# "Openai". Only names that need it are listed; everything else falls back to title().
DISPLAY = {
    "workos": "WorkOS", "openai": "OpenAI", "github": "GitHub", "gitlab": "GitLab",
    "mongodb": "MongoDB", "clickhouse": "ClickHouse", "llamaindex": "LlamaIndex",
    "langchain": "LangChain", "nvidia": "NVIDIA", "aws": "AWS", "ibm": "IBM",
    "sap": "SAP", "hp": "HP", "amd": "AMD", "xai": "xAI", "deepmind": "DeepMind",
    "scale ai": "Scale AI", "hugging face": "Hugging Face", "together ai": "Together AI",
    "fireworks ai": "Fireworks AI", "luma ai": "Luma AI", "character ai": "Character.AI",
    "essential ai": "Essential AI", "reflection ai": "Reflection AI",
    "weights & biases": "Weights & Biases", "wandb": "W&B", "duckdb": "DuckDB",
    "dbt": "dbt", "planetscale": "PlanetScale", "lancedb": "LanceDB",
    "jetbrains": "JetBrains", "hashicorp": "HashiCorp", "cockroach": "Cockroach Labs",
    "stackblitz": "StackBlitz", "sourcegraph": "Sourcegraph", "auth0": "Auth0",
    "okta": "Okta", "sambanova": "SambaNova", "coreweave": "CoreWeave",
    "lambda labs": "Lambda Labs", "applied intuition": "Applied Intuition",
    "x corp": "X", "anysphere": "Anysphere", "vanta": "Vanta", "snyk": "Snyk",
}


def display(name):
    return DISPLAY.get((name or "").lower(), (name or "").title())


def strong(companies):
    """Companies whose people are actually likely present."""
    return [c for c, m in sorted(companies.items(),
                                 key=lambda kv: -{"venue": 4, "host": 3, "sponsor": 2,
                                                  "speaker": 1, "mention": 0}[kv[1]["role"]])
            if m["role"] != "mention"]
