"""Personalisation: why this fits Keerthirajan, who to meet, how to open.

Deterministic and template-driven on purpose. The inputs are the signals already
extracted from the listing, so every sentence traces back to text that actually
appears on the event page - no invented people, companies or claims.
"""
from .companies import display as _cdisp

PROFILE = {
    "name": "Keerthirajan",
    "headline": ("MS CS (George Washington University, 2026); Apple AI/ML intern on the "
                 "Siri org - LLM evaluation, LLM-as-judge, embeddings/semantic eval, and "
                 "LoRA/PEFT fine-tuning of Llama 3.1 8B for ambiguous queries"),
    "targets": ["Software Engineer", "ML Engineer", "AI Engineer", "Applied ML",
                "NLP / LLM Engineer", "Search / Retrieval Engineer"],
}

# Each value is a HOOK appended after INTRO - a specific, answerable question.
_OPENERS = {
    "LLM evaluation": ("Most of what I did was LLM-as-judge plus embedding-based "
                       "semantic scoring. How are you measuring quality on {topic}?"),
    "LLM fine-tuning (LoRA/PEFT)": ("I fine-tuned Llama 3.1 8B with LoRA there to handle "
                                    "ambiguous user queries. What's working for your team "
                                    "on {topic}?"),
    "Embeddings / semantic search": ("Retrieval quality is the part I still find hardest to "
                                     "measure. How are you approaching {topic}?"),
    "Voice / assistant AI (Siri background)": ("Ambiguity handling was the recurring problem "
                                              "for us on Siri, and it looks like the same issue "
                                              "in {topic} - is that your experience?"),
    "Agents & tooling": ("Agent reliability is what I keep coming back to after building "
                         "eval tooling. What's breaking for you in {topic}?"),
    "ML pipelines / MLOps": ("A lot of that was pipeline and tooling work. How is your team "
                             "handling {topic}?"),
    "Applied ML / NLP": ("Before that I built a real-time sentiment analysis system. What "
                         "does {topic} look like on your side?"),
    "Backend / full-stack (Python, FastAPI, React)": ("I do a lot of Python/FastAPI work "
                                                      "alongside the ML side. What's your stack "
                                                      "for {topic}?"),
    "Hackathon / competitive building": ("I've done a lot of hackathons and like building under "
                                         "time pressure - what are you planning to build?"),
}

# One sentence, ~25 words. Anything longer stops being a greeting and becomes a
# pitch, which is the failure mode to avoid at a meetup.
INTRO = ("I just finished my MS in CS at George Washington, and I was on Apple's Siri "
         "AI/ML team over the summer working on LLM evaluation.")

_DEFAULT_OPENER = INTRO + " What are you working on?"


def _compose(hook):
    """Self-introduction, then one specific question."""
    return INTRO + " " + hook


# Raw regex fragments read badly out loud ("How are you approaching embedding?").
_TOPIC_DISPLAY = {
    "embedding": "embeddings", "embeddings": "embeddings", "rag": "RAG",
    "llm": "LLMs", "llms": "LLMs", "eval": "evals", "evals": "evals",
    "evaluation": "evaluation", "nlp": "NLP", "mcp": "MCP", "gpu": "GPUs",
    "gpus": "GPUs", "mlops": "MLOps", "k8s": "Kubernetes", "agentic": "agents",
    "inference": "inference", "retrieval": "retrieval", "ranking": "ranking",
    "fine-tuning": "fine-tuning", "fine-tune": "fine-tuning",
    "distillation": "distillation", "quantization": "quantization",
}


def _topic(ev, sig):
    for frag in (sig.get("tech_depth") or []):
        f = frag.lower().strip()
        if f in _TOPIC_DISPLAY:
            return _TOPIC_DISPLAY[f]
    # Never echo a raw regex fragment - "What's your stack for api?" reads wrong.
    return "what you're building"


def annotate(ev):
    """Fill fit_notes, who_to_meet and opener on the event."""
    sig = ev.signals or {}
    fit = sig.get("profile_fit") or {}
    cat = ev.category

    # ---- eligibility warnings go FIRST, quoting the listing verbatim, because
    #      an event you cannot attend is worse than a low-value one.
    notes = []
    restrictions = (sig.get("elig_identity") or []) + (sig.get("elig_seniority") or [])
    if restrictions:
        quote = (sig.get("audience_section") or "").strip()
        notes.append("ELIGIBILITY CHECK: the listing restricts its audience (%s)."
                     % ", ".join(restrictions[:3])
                     + (' It says: "%s"' % quote[:200] if quote else "")
                     + " Confirm you qualify before committing the evening.")
    if sig.get("elig_role_mismatch"):
        notes.append("AUDIENCE MISMATCH: the listing's audience is %s, not engineers - "
                     "the hiring here is probably for roles you are not applying to."
                     % ", ".join(sig["elig_role_mismatch"][:3]))

    for label, evidence in list(fit.items())[:4]:
        notes.append("The listing mentions %s (%s) - direct overlap with your %s work."
                     % (", ".join(evidence[:2]), label, label.split(" (")[0].lower()))
    comp = sig.get("companies_title_venue") or sig.get("companies") or []
    if comp:
        notes.append("%s appears in the listing, so engineers from there are likely present - "
                     "your Apple internship gives you a peer-level opening with them."
                     % ", ".join(_cdisp(c) for c in comp[:3]))
    if sig.get("hiring_strong"):
        notes.append("The organiser states hiring intent (%s), which means asking about open "
                     "roles is expected rather than awkward." % ", ".join(sig["hiring_strong"][:2]))
    if len(notes) == 0:
        notes.append("General fit only: no specific overlap with your background was found in "
                     "the listing text.")
    ev.fit_notes = notes

    # ---- who to meet
    who = []
    if cat == "A":
        who += ["Recruiters and sourcers staffing the event",
                "Hiring managers for SWE / ML roles",
                "Engineers on the teams you would join (ask who to talk to next)"]
    elif cat == "B":
        who += ["ML / AI and platform engineers doing the work you want to do",
                "The speakers - they are usually senior and can refer",
                "The organiser, who knows who in the room is hiring"]
    elif cat == "C":
        who += ["Technical founders and early engineers (first 10 hires often happen here)",
                "Anyone who mentions they are building a team"]
    elif cat == "D":
        who += ["Speakers and the two or three most engaged people asking questions",
                "The organiser"]
    else:
        who += ["Low expected value - only go if you have nothing better that day"]
    hiring_now = [o for o in (getattr(ev, "openings", None) or []) if o.get("total")]
    for o in hiring_now[:3]:
        titles = ", ".join(r["title"] for r in o["roles"][:2]) or "engineering roles"
        who.insert(0, "Anyone from %s - they have %d relevant openings right now (%s)"
                      % (_cdisp(o["company"]), o["total"], titles))
    strong_co = [c for c in (getattr(ev, "companies", None) or []) if c["role"] != "mention"]
    if strong_co and not hiring_now:
        who.insert(0, "People from %s (%s at this event)"
                      % (", ".join(_cdisp(c["name"]) for c in strong_co[:3]),
                         strong_co[0]["role"]))
    if ev.speakers:
        who.insert(0, "Listed speakers/guests: " + ", ".join(ev.speakers[:5]))
    if ev.organizer:
        who.append("Organiser: %s" % ev.organizer)
    ev.who_to_meet = who

    # ---- opener
    opener = _DEFAULT_OPENER
    for label in fit:
        if label in _OPENERS:
            opener = _compose(_OPENERS[label].format(topic=_topic(ev, sig)))
            break

    ev.opener = opener

    # The company-specific ask is kept SEPARATE from the opener. Saying all of it
    # in one breath reads as a pitch; this is the thing to raise once the
    # conversation is going.
    live = [o for o in (getattr(ev, "openings", None) or []) if o.get("total")]
    if live:
        o = live[0]
        role = o["roles"][0]["title"] if o["roles"] else "engineering roles"
        ev.followup = ("Once it's flowing: \"I saw %s is hiring a %s - is anyone from "
                       "that team here, or would you be open to pointing me to them?\" "
                       "You are on OPT and available immediately; say so."
                       % (_cdisp(o["company"]), role))
    elif cat == "A":
        ev.followup = ("Ask directly: \"Are you hiring new-grad software or ML engineers "
                       "right now? I'm on OPT and available immediately.\"")
    else:
        ev.followup = ("Close with: \"Who else here should I be talking to?\" - it is the "
                       "highest-yield question at any of these and costs nothing.")
    return ev


def action(ev):
    """One-line recommended action."""
    cost = getattr(ev, "cost", None) or {}
    if cost.get("late_warning", "").startswith("ends too late"):
        return ("Only go if you can leave early or arrange a ride - %s"
                % cost["late_warning"])
    if ev.sold_out:
        return "Join the waitlist now and message the organiser - sold-out events still admit no-shows' spots."
    if ev.requires_approval:
        return "Register today; approval is required so late requests often get declined."
    if ev.score >= 75:
        return "Register now. Treat this as a priority for that day."
    if ev.score >= 60:
        return "Register - solid use of an evening."
    if ev.score >= 45:
        return "Register only if nothing better appears for that day."
    return "Skip unless the day is otherwise empty."
