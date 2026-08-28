"""Deterministic signal extraction.

Every pattern is anchored with word boundaries and, where a bare word is
ambiguous, expressed as a *phrase*. This is not decoration: on the live SF data
a naive substring match for "fair" returns "Bayview Transit Fair Family Fun Day"
and "Berkeley FA26 Design Fair". Phrases + boundaries are what keep precision.

Each group returns the list of literal matched strings so the UI can show the
user the exact evidence behind a score.
"""
import re


# --------------------------------------------------------------------- helpers
def _rx(patterns):
    return [re.compile(p, re.I) for p in patterns]


def _hits(rxs, text, limit=6):
    out = []
    for r in rxs:
        m = r.search(text)
        if m:
            frag = m.group(0).strip()
            if frag.lower() not in [o.lower() for o in out]:
                out.append(frag)
        if len(out) >= limit:
            break
    return out

# ------------------------------------------- I. eligibility / audience mismatch
# Measured need: "Bay Area Experienced Operators -> AI Safety Mixer" scored 86 on
# hiring keywords alone, but its own text says it is for operations/bizops/legal
# people "with years of experience". A new-grad engineer would waste the evening.
# Likewise a members-only community night for senior women engineers is a real
# event with real hiring intent - just not one Keerthi can attend.
#
# We never silently drop these. We capture the restricting sentence verbatim so
# the report can quote it and let the user decide.

# Sentence starters that introduce an explicit audience definition.
_AUDIENCE_LEAD = re.compile(
    r"(?:"
    r"who\s+(?:this|the)(?:\s+\w+){0,3}\s+is\s+for"     # "Who This Is Event is For"
    r"|this(?:\s+\w+){0,3}\s+is\s+for"                   # "This event is for"
    r"|who\s+should\s+attend|who\s+attends?"
    r"|ideal\s+for|designed\s+for|intended\s+for|meant\s+for|built\s+for"
    r"|open\s+(?:only\s+)?to|restricted\s+to|limited\s+to|exclusive(?:ly)?\s+(?:to|for)"
    r"|audience\s*:|attendees\s*:|eligibility\s*:|for\s+whom"
    r")\s*[:\-]?\s*", re.I)

# Unambiguous gatekeeping phrases. These mean "you may not be able to get in"
# regardless of where they appear, so they are matched against the whole listing.
ELIG_HARD = _rx([
    r"\bmembers?\s+only\b", r"\bmembers-only\b", r"\bcurrent\s+members\b",
    r"\bprospective\s+members\b", r"\balumni\s+only\b", r"\binvite[- ]only\b",
    r"\bopen\s+only\s+to\b", r"\brestricted\s+to\b", r"\bmust\s+be\s+a\s+member\b",
    r"\bby\s+application\s+only\b", r"\bapplication\s+required\b",
    r"\bwomen\s+only\b", r"\bfor\s+women\s+only\b", r"\bveterans?\s+only\b",
    r"\bstudents\s+only\b", r"\bexecutives?\s+only\b", r"\bfounders?\s+only\b",
])

# Softer audience descriptors. These are ONLY trusted inside the title or the
# listing's own audience definition. Measured reason: matched against full body
# text they fire on speaker bios and host credentials - "30+ years" in a host's
# blurb wrongly penalised "Meet the Other Side: Job Seekers x Hiring Teams", the
# single best-fitting event in the window.
ELIG_IDENTITY = _rx([
    r"\bwomen\s*(?:&|and|\+|/)?\s*(?:non-?binary|nonbinary|gnc)\b",
    r"\b(?:for|by)\s+women\b", r"\bwomen(?:'s)?\s+(?:only|network|community|circle)\b",
    r"\bwomxn\b", r"\bnon-?binary\b", r"\bfemale-?identifying\b",
    r"\bbipoc\b", r"\blatinx\b", r"\blgbtq\b", r"\bqueer\b", r"\btrans\b",
    r"\bveterans?\s+only\b", r"\bmembers?\s+only\b", r"\bcurrent\s+members\b",
    r"\bmembers\s+and\s+alums\b", r"\bnetwork\s+members\b",
])
ELIG_SENIORITY = _rx([
    r"\b\d+\+?\s*years?\s+(?:of\s+)?experience\b", r"\byears\s+of\s+experience\b",
    r"\bexperienced\s+(?:operators?|professionals?|engineers?|leaders?)\b",
    r"\bsenior\s+(?:engineers?|leaders?|only)\b", r"\bstaff\+?\s+engineers?\b",
    r"\bprincipal\s+engineers?\b", r"\bengineering\s+(?:leaders?|managers?|directors?)\b",
    r"\bexecutives?\b", r"\bdirectors?\s+and\s+above\b", r"\bvps?\s+of\b",
    r"\bc-?level\b", r"\bheads?\s+of\s+engineering\b", r"\bseasoned\b",
])
# Roles that are NOT what Keerthi is applying for. Only meaningful when these are
# named as the AUDIENCE and engineers are not.
ELIG_ROLE_NONENG = _rx([
    r"\boperators?\b", r"\bbiz\s?ops\b", r"\bbusiness\s+operations\b",
    r"\bchief\s+of\s+staff\b", r"\bpeople\s+ops\b", r"\bhr\b",
    r"\brecruiting\s+and\s+operations\b", r"\blegal\b", r"\bfinance\b",
    r"\baccounting\b", r"\bsales\s+(?:reps?|leaders?|professionals?)\b",
    r"\bmarketers?\b", r"\bproduct\s+marketing\b", r"\bcustomer\s+success\b",
    r"\baccount\s+executives?\b", r"\binvestors?\s+only\b",
])


def audience_section(text):
    """Return the sentence(s) where the listing defines its intended audience."""
    m = _AUDIENCE_LEAD.search(text or "")
    if not m:
        return ""
    return (text[m.end():m.end() + 320]).strip()




# ----------------------------------------------------- A. explicit hiring intent
HIRING_STRONG = _rx([
    r"\bjob fair\b", r"\bcareer fair\b", r"\bcareer expo\b", r"\bjob expo\b",
    r"\bhiring (?:event|fair|mixer|night|day|drive)\b",
    r"\brecruit(?:ing|ment) (?:event|fair|mixer|night|day)\b",
    r"\bwe(?:'re| are)\s+hiring\b", r"\bnow hiring\b", r"\bactively hiring\b",
    r"\bbring (?:your )?(?:a )?resumes?\b", r"\bresume (?:review|drop|clinic)\b",
    r"\bon-?site interviews?\b", r"\bspeed interview", r"\binterview loops?\b",
    r"\bjob seekers?\b", r"\bhiring (?:managers?|teams?|partners?)\b",
    r"\bmeet (?:the )?(?:hiring|recruiting) teams?\b",
    r"\btalent (?:mixer|night|showcase|fair)\b",
    r"\bopen (?:roles?|positions?|reqs?)\b", r"\bwho(?:'s| is) hiring\b",
])
HIRING_SOFT = _rx([
    r"\brecruiters?\b", r"\bhiring\b", r"\btalent\b", r"\bcareers?\b",
    r"\bjob opportunit", r"\bemployers?\b", r"\bcandidates?\b",
    r"\breferrals?\b", r"\binternships?\b", r"\bnew grad", r"\bentry-?level\b",
])

# ------------------------------------------------- B. engineer audience & format
AUDIENCE_ENG = _rx([
    r"\b(?:software|ml|ai|backend|front-?end|full-?stack|platform|infra(?:structure)?|"
    r"data|systems|research|forward-?deployed)\s+engineers?\b",
    r"\bengineers?\b", r"\bdevelopers?\b", r"\bdevs\b", r"\bbuilders?\b",
    r"\bpractitioners?\b", r"\bhackers?\b", r"\btechnical (?:folks|people|talent|audience)\b",
])
FORMAT_BUILD = _rx([
    r"\bdemo (?:night|day)\b", r"\bbuild(?:er)? night\b", r"\bhack(?:athon|night|day)\b",
    r"\bworkshop\b", r"\bhands-?on\b", r"\bcode\s?jam\b", r"\bcodelab\b",
    r"\blightning talks?\b", r"\btech talks?\b", r"\bdeep dive\b", r"\bshow ?& ?tell\b",
])
FORMAT_NETWORK = _rx([
    r"\bmixer\b", r"\bnetworking\b", r"\bhappy hour\b", r"\bdrink-?up\b",
    r"\bmeet-?up\b", r"\bsocial hour\b", r"\broundtable\b", r"\boffice hours\b",
    r"\bcoffee chat\b", r"\bfireside\b", r"\bcommunity (?:night|event|meetup)\b",
    r"\bafter-?party\b", r"\bmeet (?:other|fellow)\b",
])
FORMAT_TALKS_ONLY = _rx([
    r"\bwebinar\b", r"\blivestream\b", r"\bpanel discussion\b", r"\bkeynote\b",
    r"\bsymposium\b", r"\blecture\b", r"\bseminar\b", r"\bjournal club\b",
    r"\breading group\b", r"\bpaper (?:club|reading)\b",
])

# --------------------------------------------- C. technical depth (anti-fluff AI)
TECH_DEPTH = _rx([
    r"\bllms?\b", r"\brag\b", r"\bretrieval\b", r"\bembeddings?\b", r"\bvector (?:db|database|search|store)\b",
    r"\bfine-?tun\w*", r"\bloras?\b", r"\bpeft\b", r"\bquantiz\w*", r"\bdistill\w*",
    r"\binference\b", r"\bthroughput\b", r"\blatency\b", r"\bbenchmark\w*", r"\bevals?\b",
    r"\bevaluation\b", r"\bllm-as-a?-?judge\b", r"\bguardrails?\b", r"\bobservability\b",
    r"\bagentic\b", r"\btool ?call\w*", r"\bmcp\b", r"\bcontext window\b",
    r"\btransformers?\b", r"\bpytorch\b", r"\btensorflow\b", r"\bjax\b", r"\bhugging ?face\b",
    r"\bkubernetes\b", r"\bk8s\b", r"\bdocker\b", r"\bterraform\b", r"\bdistributed systems?\b",
    r"\bmlops\b", r"\bdata pipelines?\b", r"\bstreaming\b", r"\bkafka\b", r"\bspark\b",
    r"\bgpus?\b", r"\bcuda\b", r"\btriton\b", r"\bcompilers?\b", r"\bruntime\b",
    r"\bopen ?source\b", r"\bapis?\b", r"\bsdks?\b", r"\bdatabases?\b", r"\bpostgres\b",
    r"\brust\b", r"\bgolang\b", r"\btypescript\b", r"\breact\b", r"\bpython\b",
    r"\bcomputer vision\b", r"\bnlp\b", r"\brecommender\b", r"\branking\b", r"\bsearch relevance\b",
    r"\brobotics\b", r"\bsimulation\b", r"\bsecurity\b", r"\bcryptograph\w*",
])

# ------------------------------------------------ D. investor / pitch (down-rank)
INVESTOR = _rx([
    r"\bpitch (?:competition|contest|night|event|day|off)\b", r"\bpitch your\b",
    r"\bdemo day\b", r"\bvcs?\b", r"\bventure (?:capital|capitalists?|firm)\b",
    r"\binvestors?\b", r"\blimited partners?\b", r"\blps\b", r"\bangel (?:investors?|round)\b",
    r"\bfundrais\w*", r"\bterm sheets?\b", r"\bcap table\b", r"\bdeal ?flow\b",
    r"\b(?:pre-?)?seed round\b", r"\bseries [ab]\b", r"\bvaluation\b", r"\bdue diligence\b",
    r"\bportfolio companies\b", r"\blimited spots for founders\b",
])
FOUNDER_ONLY = _rx([
    r"\bfounders? (?:only|dinner|breakfast|lunch|retreat|circle|mastermind)\b",
    r"\bfor founders\b", r"\bceos? (?:only|dinner|roundtable)\b",
    r"\bexecutives? (?:only|dinner)\b", r"\binvite-?only\b", r"\bapplication required\b",
])

# ------------------------------------- E. non-technical business (down-rank)
NONTECH_BIZ = _rx([
    r"\bgtm\b", r"\bgo-?to-?market\b", r"\bsales (?:team|leaders?|playbook|pipeline)\b",
    r"\bmarketing\b", r"\bseo\b", r"\bbrand(?:ing)?\b", r"\bcontent (?:strategy|marketing|creation)\b",
    r"\bgrowth hack\w*", r"\bsolopreneur\b", r"\bside hustle\b", r"\bpassive income\b",
    r"\bcoach(?:ing)?\b", r"\bmindset\b", r"\bmanifest\w*", r"\bwellness\b",
    r"\bproductivity hacks?\b", r"\bthought leader\w*", r"\bpersonal brand\b",
    r"\breal estate\b", r"\btrading (?:signals?|bots?)\b", r"\bcrypto (?:gains?|moon)\b",
    r"\bno-?code\b", r"\bautomation agency\b", r"\bai for (?:sales|marketing|realtors|coaches)\b",
])

# --------------------------------- F2. hiring events in the wrong industry
# "California Sports & Ent. Career Expo" scored 67 as a top recruiting event. It
# is a genuine career expo - for sports and entertainment jobs. Hiring language is
# necessary but not sufficient; the hiring has to be for roles he is applying to.
INDUSTRY_MISMATCH = _rx([
    r"\bsports?\b", r"\bentertainment\b", r"\bhospitality\b", r"\bretail\b",
    r"\brestaurant\b", r"\bculinary\b", r"\bnursing\b", r"\bclinical\b",
    r"\bteaching\b", r"\beducators?\b", r"\bk-?12\b", r"\bsocial work\b",
    r"\breal estate\b", r"\binsurance\b", r"\bconstruction\b", r"\btrades\b",
    r"\bmilitary\b", r"\bveteran hiring\b", r"\blaw enforcement\b",
    r"\bfashion\b", r"\bbeauty\b", r"\bcannabis\b", r"\btravel industry\b",
    r"\bnonprofit\b", r"\bgovernment jobs?\b", r"\bpublic sector\b",
    r"\bdriver\b", r"\bwarehouse\b", r"\blogistics jobs?\b",
])

# ------------------------------------ F. hard noise -> irrelevant (gate, not score)
HARD_NOISE = _rx([
    r"\byoga\b", r"\bsound bath\b", r"\bbreathwork\b", r"\bmeditation\b", r"\bpilates\b",
    r"\brun club\b", r"\bbike ride\b", r"\bhik(?:e|ing) club\b", r"\bpickleball\b",
    r"\bbook club\b", r"\bwriting (?:group|workshop)\b", r"\bpoetry\b", r"\bopen mic\b",
    r"\bwine (?:tasting|night)\b", r"\bbeer tasting\b", r"\bbrunch\b", r"\bsupper club\b",
    r"\bspeed dating\b", r"\bsingles\b", r"\bdating\b", r"\bmatchmaking\b",
    r"\bkids?\b", r"\btoddler\b", r"\bsensory play\b", r"\bstory ?time\b", r"\bparenting\b",
    r"\bdogs?\b", r"\bcorgi\b", r"\bcats?\b", r"\bpuppy\b", r"\bpets?\b",
    r"\bkaraoke\b", r"\bdance (?:party|class)\b", r"\bcomedy\b", r"\bimprov\b",
    r"\bfilm screening\b", r"\bmovie night\b", r"\bart (?:gallery|show|opening)\b",
    r"\bcraft\b", r"\bstamp making\b", r"\bknitting\b", r"\bceramics\b", r"\bpainting\b",
    r"\bspa\b", r"\bmassage\b", r"\bsauna\b", r"\bice bath\b", r"\bcold plunge\b",
    r"\blongevity\b", r"\bbiohack\w*", r"\bpsychedelic\w*", r"\bastrology\b", r"\btarot\b",
    r"\bchurch\b", r"\bworship\b", r"\bbible\b", r"\bmeditation retreat\b",
    r"\bfarmers market\b", r"\bfood truck\b", r"\bpotluck\b", r"\bgolf clinic\b",
])

# --------------------------------------- G. company presence (engineers on site)
COMPANIES = [
    # big tech / FAANG-adjacent
    "apple", "google", "alphabet", "meta", "facebook", "microsoft", "amazon", "aws",
    "netflix", "nvidia", "tesla", "intel", "amd", "qualcomm", "adobe", "salesforce",
    "linkedin", "uber", "lyft", "airbnb", "doordash", "instacart", "pinterest",
    "reddit", "discord", "dropbox", "box", "roblox", "snap", "twitter", "x corp",
    "ibm", "oracle", "sap", "vmware", "cisco", "dell", "hp", "samsung", "sony",
    # AI labs & model companies
    "openai", "anthropic", "deepmind", "mistral", "cohere", "perplexity", "xai",
    "scale ai", "hugging face", "together ai", "fireworks ai", "groq", "cerebras",
    "sierra", "glean", "harvey", "cursor", "anysphere", "runway", "luma ai",
    "character ai", "inflection", "adept", "imbue", "essential ai", "reflection ai",
    # data / infra / devtools
    "databricks", "snowflake", "confluent", "mongodb", "elastic", "datadog",
    "cloudflare", "vercel", "netlify", "supabase", "planetscale", "neon",
    "pinecone", "weaviate", "chroma", "qdrant", "milvus", "lancedb",
    "langchain", "llamaindex", "weights & biases", "wandb", "modal", "replicate",
    "temporal", "workos", "github", "gitlab", "jetbrains", "docker", "hashicorp",
    "redis", "cockroach", "clickhouse", "duckdb", "dbt", "fivetran", "airbyte",
    "retool", "zapier", "airtable", "notion", "figma", "linear", "asana",
    "atlassian", "twilio", "stripe", "plaid", "brex", "ramp", "mercury",
    "robinhood", "coinbase", "block", "square", "affirm", "chime",
    "palantir", "samsara", "verkada", "rippling", "deel", "gusto", "benchling",
    "waymo", "cruise", "zoox", "applied intuition", "nuro", "skydio", "anduril",
    "sambanova", "lambda labs", "coreweave", "crusoe", "baseten", "anyscale",
    "sourcegraph", "codeium", "windsurf", "replit", "stackblitz",
    "okta", "auth0", "snyk", "wiz", "abnormal", "vanta", "drata",
]
# Company names that are also ordinary English words. Matching these bare
# produces real errors: "Dreamforce Lunch Cruise" was credited to Cruise the
# self-driving company, and scored +9 for "their engineers will be on site".
# For these we require a nearby corporate context marker.
AMBIGUOUS = {
    "block", "box", "cruise", "square", "expo", "ramp", "notion", "linear",
    "modal", "snap", "stripe", "plaid", "elastic", "replicate", "temporal",
    "sierra", "glean", "harvey", "cursor", "chime", "mercury", "intel",
    "discord", "reddit", "figma", "asana", "docker", "redis", "deel",
    "gusto", "affirm", "anduril", "brex", "nuro",
}
_CTX = (r"(?:@|\bat\b|\bhq\b|\bhosted\s+by\b|\boffices?\b|\bteam\b|\binc\b"
        r"|\blabs\b|\bby\b|\bwith\b|\bx\b|\bpresents?\b|\bsponsor(?:ed)?\b)")


def _company_pattern(name):
    esc = re.escape(name).replace(r"\ ", r"\s+")
    if name in AMBIGUOUS:
        # require a corporate marker within ~20 chars on either side
        return (r"(?:" + _CTX + r".{0,20}\b" + esc + r"\b"
                r"|\b" + esc + r"\b.{0,20}" + _CTX + r")")
    return r"\b" + esc + r"\b"


_COMPANY_RX = _rx([_company_pattern(c) for c in COMPANIES])

# ------------------------- H. Keerthirajan-specific fit (profile personalization)
PROFILE_FIT = {
    "LLM evaluation": _rx([r"\bevals?\b", r"\bevaluation\b", r"\bllm-as-a?-?judge\b",
                           r"\bbenchmark\w*", r"\bobservability\b", r"\bguardrails?\b",
                           r"\bquality\b.{0,20}\bmodels?\b"]),
    "LLM fine-tuning (LoRA/PEFT)": _rx([r"\bfine-?tun\w*", r"\bloras?\b", r"\bpeft\b",
                                        r"\bpost-?training\b", r"\brlhf\b", r"\bsft\b"]),
    "Embeddings / semantic search": _rx([r"\bembeddings?\b", r"\bsemantic search\b",
                                        r"\bvector (?:db|database|search|store)\b",
                                        r"\bretrieval\b", r"\brag\b", r"\branking\b",
                                        r"\bsearch relevance\b", r"\brecommender\b"]),
    "Applied ML / NLP": _rx([r"\bnlp\b", r"\bapplied (?:ml|ai)\b", r"\bmachine learning\b",
                             r"\bsentiment\b", r"\btext classification\b"]),
    "Voice / assistant AI (Siri background)": _rx([r"\bvoice (?:ai|agents?|assistants?)\b",
                                                  r"\bspeech\b", r"\basr\b", r"\btts\b",
                                                  r"\bassistants?\b", r"\bsiri\b", r"\balexa\b"]),
    "Agents & tooling": _rx([r"\bagentic\b", r"\bai agents?\b", r"\btool ?call\w*",
                             r"\bmcp\b", r"\borchestrat\w*"]),
    "ML pipelines / MLOps": _rx([r"\bmlops\b", r"\bml (?:pipelines?|platform|infra\w*)\b",
                                 r"\bdata pipelines?\b", r"\bfeature store\b"]),
    "Backend / full-stack (Python, FastAPI, React)": _rx([r"\bpython\b", r"\bfastapi\b",
                                                          r"\bflask\b", r"\breact\b",
                                                          r"\bbackend\b", r"\bfull-?stack\b",
                                                          r"\bapis?\b"]),
    "Hackathon / competitive building": _rx([r"\bhack(?:athon|night|day)\b", r"\bcompetition\b",
                                            r"\bdemo (?:night|day)\b", r"\bbuild night\b"]),
}


def extract(event):
    """Return a dict of named signals + the literal evidence for each."""
    title = event.title or ""
    blob = event.text_blob()
    # Company named in the title/venue/host is far stronger evidence that that
    # company's engineers are physically present than a mention in body prose.
    headline = " ".join([title, event.venue or "", event.organizer or ""])
    # Title carries more intent than body text; weight it by scanning separately.
    sig = {
        "hiring_strong": _hits(HIRING_STRONG, blob),
        "hiring_strong_title": _hits(HIRING_STRONG, title),
        "hiring_soft": _hits(HIRING_SOFT, blob),
        "audience_eng": _hits(AUDIENCE_ENG, blob),
        "format_build": _hits(FORMAT_BUILD, blob),
        "format_network": _hits(FORMAT_NETWORK, blob),
        "format_talks_only": _hits(FORMAT_TALKS_ONLY, blob),
        "tech_depth": _hits(TECH_DEPTH, blob, limit=12),
        "investor": _hits(INVESTOR, blob),
        "investor_title": _hits(INVESTOR, title),
        "founder_only": _hits(FOUNDER_ONLY, blob),
        "nontech_biz": _hits(NONTECH_BIZ, blob),
        "industry_mismatch": _hits(INDUSTRY_MISMATCH, title) or
                             (_hits(INDUSTRY_MISMATCH, blob)
                              if not _hits(TECH_DEPTH, blob) else []),
        "hard_noise_title": _hits(HARD_NOISE, title),
        "hard_noise_body": _hits(HARD_NOISE, blob),
        "companies": _hits(_COMPANY_RX, blob, limit=8),
        "companies_title_venue": _hits(_COMPANY_RX, headline, limit=6),
        "ascii_ratio": round(_ascii_ratio(title), 2),
        "desc_len": len(event.description or ""),
    }
    # --- eligibility. Scope matters more than the patterns here.
    aud = audience_section(blob)
    sig["audience_section"] = aud[:320]
    # Title + explicit audience definition only. Never the full body prose.
    scope = (title + " " + aud).strip()
    sig["elig_identity"] = _hits(ELIG_HARD, blob) + _hits(ELIG_IDENTITY, scope)
    sig["elig_seniority"] = _hits(ELIG_SENIORITY, scope)
    # A non-engineering role is a mismatch only when the listing defines its
    # audience as those roles AND does not also name engineers.
    noneng = _hits(ELIG_ROLE_NONENG, aud) if aud else []
    sig["elig_role_mismatch"] = noneng if (noneng and not _hits(AUDIENCE_ENG, aud)) else []

    fit = {}
    for label, rxs in PROFILE_FIT.items():
        h = _hits(rxs, blob, limit=3)
        if h:
            fit[label] = h
    sig["profile_fit"] = fit
    return sig


def _ascii_ratio(s):
    letters = [c for c in (s or "") if c.isalpha()]
    if not letters:
        return 1.0
    return sum(1 for c in letters if ord(c) < 128) / len(letters)
