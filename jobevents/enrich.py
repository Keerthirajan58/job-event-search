"""Post-scoring enrichment: travel cost, company roles, live openings, your history.

Kept separate from score.py so the scoring rules stay readable and so anything
requiring network access (job-board lookups) is clearly isolated.
"""
from . import companies as comp
from . import config, openings, score, transit


def attach_companies(ev):
    """Resolve companies and the role each plays. Cheap, no network."""
    cmap = comp.extract(ev)
    ev.signals["company_roles"] = cmap
    ev.companies = [{"name": c, "role": m["role"], "evidence": m["evidence"]}
                    for c, m in sorted(cmap.items(),
                                       key=lambda kv: -{"venue": 4, "host": 3,
                                                        "sponsor": 2, "speaker": 1,
                                                        "mention": 0}[kv[1]["role"]])]
    return ev


def attach_cost(ev):
    """Door-to-door travel time, fare, and the resulting score adjustment."""
    ev.cost = transit.cost_of_attendance(ev)
    delta, reasons = transit.cost_penalty(ev.cost, ev.score)
    ev.score = max(0, min(100, ev.score + delta))
    for r in reasons:
        (ev.reasons if r.startswith("+") else ev.penalties).append(r)
    return ev


def attach_openings(ev, log=None):
    """Look up verified openings for companies actually involved in the event.

    Only 'strong' roles are looked up (venue/host/sponsor/speaker). A passing
    mention of Google in a description is not a reason to check Google's board.
    """
    strong = [c["name"] for c in getattr(ev, "companies", []) if c["role"] != "mention"]
    if not strong:
        ev.openings = []
        return ev
    ev.openings = openings.enrich(strong[:5], log=log)
    if ev.openings:
        total = sum(o["total"] for o in ev.openings)
        names = ", ".join("%s (%d)" % (o["company"].title(), o["total"])
                          for o in ev.openings[:3])
        bump = min(10, 3 + 2 * len(ev.openings))
        ev.score = min(100, ev.score + bump)
        ev.reasons.append(
            "+%d  Verified open roles you qualify for at companies involved: %s"
            % (bump, names))
        ev.opening_summary = "%d relevant openings across %d companies" % (
            total, len(ev.openings))
    return ev


def finalize(ev, priors=None):
    """Apply the learned organiser prior, then compute the verdict."""
    if priors:
        from . import feedback
        feedback.apply_prior(ev, priors)
    ev.verdict = score.verdict(ev)
    return ev
