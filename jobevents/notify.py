"""Optional push notification. No-op unless env vars are set.

Deliberately the last thing built and the smallest possible implementation:
Telegram needs no SMTP, no OAuth and no paid tier - just a bot token.

    export TELEGRAM_TOKEN=123:abc
    export TELEGRAM_CHAT=456789
    python3 -m jobevents.notify
"""
import json
import os
import urllib.parse
import urllib.request


def build_message(digest_path="out/digest.json", max_events=4):
    with open(digest_path, encoding="utf-8") as fh:
        d = json.load(fh)
    days = d.get("days") or {}
    keys = sorted(days)
    if not keys:
        return "No digest data."
    lines = ["Job-Event Search - top picks"]
    shown = 0
    for k in keys:
        rec = days[k].get("recommended") or []
        if not rec:
            continue
        lines.append("")
        lines.append(k)
        for e in rec[:2]:
            c = e.get("cost") or {}
            trip = (" | %d min, $%.0f" % (c["one_way_min"], c["total_cash"])
                    if c.get("known") else "")
            jobs = sum(o["total"] for o in (e.get("openings") or []))
            lines.append("  [%s] %d/100 %s | %s%s"
                         % (e.get("verdict", "?"), e["score"], e["time"] or "TBD",
                            e["title"], trip))
            if jobs:
                names = ", ".join(o["company"].title() for o in e["openings"][:2])
                lines.append("      hiring now: %s (%d roles you match)" % (names, jobs))
            lines.append("  %s" % e["url"])
            shown += 1
        if shown >= max_events:
            break
    return "\n".join(lines) if shown else "No worthwhile events found in the window."


def main():
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT")
    if not token or not chat:
        print("TELEGRAM_TOKEN / TELEGRAM_CHAT not set - nothing to do.")
        return 0
    body = urllib.parse.urlencode({
        "chat_id": chat, "text": build_message(), "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request("https://api.telegram.org/bot%s/sendMessage" % token,
                                 data=body)
    with urllib.request.urlopen(req, timeout=30) as r:
        print("telegram:", r.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
