#!/usr/bin/env bash
# One-command deploy to GitHub Actions + GitHub Pages.
#
# Prerequisite (only thing you must do by hand, because it opens a browser):
#     gh auth login
#
# Then:
#     ./deploy.sh
#
# Idempotent: safe to re-run. It creates the repo if missing, pushes, switches
# Pages to the Actions build, waits for the first run, and verifies the live page.
set -uo pipefail

REPO_NAME="${REPO_NAME:-job-event-search}"
BRANCH=main

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
ok()   { printf '    \033[32mok\033[0m  %s\n' "$*"; }
bad()  { printf '    \033[31mFAIL\033[0m %s\n' "$*"; }
info() { printf '    %s\n' "$*"; }

# ---------------------------------------------------------------- 1. preflight
say "Checking prerequisites"
command -v gh >/dev/null || { bad "gh CLI not found - install with: brew install gh"; exit 1; }
ok "gh $(gh --version | head -1 | awk '{print $3}')"

if ! gh auth status >/dev/null 2>&1; then
  bad "Not logged in to GitHub."
  info "Run this first, then re-run ./deploy.sh :"
  info "    gh auth login"
  exit 1
fi
USER_LOGIN=$(gh api user --jq .login)
ok "authenticated as $USER_LOGIN"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { bad "not a git repo"; exit 1; }
if [ -n "$(git status --porcelain)" ]; then
  info "uncommitted changes found - committing them"
  git add -A && git commit -q -m "Update digest tooling"
fi
ok "working tree clean, branch $(git rev-parse --abbrev-ref HEAD)"

# --------------------------------------------------------------- 2. the repo
say "Creating / locating the GitHub repository"
FULL="$USER_LOGIN/$REPO_NAME"
if gh repo view "$FULL" >/dev/null 2>&1; then
  ok "repo already exists: $FULL"
else
  gh repo create "$FULL" --public \
     --description "Ranks Bay Area tech events by realistic job-search value. Zero deps, \$0." \
     >/dev/null || { bad "could not create repo"; exit 1; }
  ok "created public repo $FULL"
fi

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "https://github.com/$FULL.git"
else
  git remote add origin "https://github.com/$FULL.git"
fi
ok "remote origin -> https://github.com/$FULL.git"

# ---------------------------------------------------------------- 3. Pages
# Done BEFORE the push: the workflow fires on push, and a run that builds before
# Pages is set to "GitHub Actions" fails at the deploy step.
enable_pages() {
  if gh api "repos/$FULL/pages" >/dev/null 2>&1; then
    gh api -X PUT "repos/$FULL/pages" -f build_type=workflow >/dev/null 2>&1
  else
    gh api -X POST "repos/$FULL/pages" -f build_type=workflow >/dev/null 2>&1
  fi
}

say "Configuring GitHub Pages to build from Actions"
if enable_pages; then
  ok "Pages source = GitHub Actions"
  PAGES_READY=1
else
  info "Pages could not be set yet (common on a brand-new empty repo) - retrying after the push"
  PAGES_READY=0
fi

say "Pushing $BRANCH"
git push -u origin "$BRANCH" 2>&1 | tail -3
ok "pushed"

if [ "$PAGES_READY" = "0" ]; then
  sleep 4
  if enable_pages; then
    ok "Pages source = GitHub Actions"
  else
    bad "Could not enable Pages via the API."
    info "Enable it once by hand, then re-run ./deploy.sh :"
    info "    https://github.com/$FULL/settings/pages  ->  Source: GitHub Actions"
    exit 1
  fi
fi

PAGE_URL="https://${USER_LOGIN}.github.io/${REPO_NAME}/"

# ------------------------------------------------------------ 4. wait for run
say "Waiting for the workflow run (a cold run takes ~6-7 minutes)"
sleep 10
RUN_ID=$(gh run list --repo "$FULL" --workflow daily-digest --limit 1 --json databaseId \
         --jq '.[0].databaseId' 2>/dev/null)
if [ -z "${RUN_ID:-}" ] || [ "$RUN_ID" = "null" ]; then
  info "no run detected - dispatching one"
  gh workflow run daily-digest --repo "$FULL" --ref "$BRANCH" >/dev/null 2>&1 || true
  sleep 15
  RUN_ID=$(gh run list --repo "$FULL" --workflow daily-digest --limit 1 --json databaseId \
           --jq '.[0].databaseId' 2>/dev/null)
fi
if [ -n "${RUN_ID:-}" ] && [ "$RUN_ID" != "null" ]; then
  info "run $RUN_ID - following it (Ctrl-C is safe, the run continues)"
  gh run watch "$RUN_ID" --repo "$FULL" --exit-status && ok "workflow succeeded" \
    || { bad "workflow failed - logs:"; gh run view "$RUN_ID" --repo "$FULL" --log-failed | tail -40; }
else
  bad "could not find a workflow run; check the Actions tab"
fi

# --------------------------------------------------------------- 5. verify
say "Verifying the live dashboard at $PAGE_URL"
for i in $(seq 1 24); do
  CODE=$(curl -sS -o /tmp/jes_live.html -w '%{http_code}' -L "$PAGE_URL" 2>/dev/null || echo 000)
  [ "$CODE" = "200" ] && break
  info "attempt $i: HTTP $CODE - Pages can take a minute to go live, retrying"
  sleep 10
done

if [ "$CODE" != "200" ]; then
  bad "dashboard not reachable (last HTTP $CODE)"
  info "Check: Settings -> Pages, and the Actions tab for the deploy job."
  exit 1
fi
ok "HTTP 200, $(wc -c < /tmp/jes_live.html) bytes"

fail=0
check() { grep -q "$1" /tmp/jes_live.html && ok "$2" || { bad "$2"; fail=1; }; }
check 'noindex'                 "noindex meta present (kept out of search results)"
check 'Where should I go'       "page title rendered"
check 'class="verdict'          "verdict badges rendered"
check 'Getting there'           "cost-of-attendance strip rendered"
check 'People to target'        "who-to-meet section rendered"
CARDS=$(grep -o 'class="ev' /tmp/jes_live.html | wc -l | tr -d ' ')
[ "$CARDS" -ge 5 ] && ok "$CARDS event cards" || { bad "only $CARDS event cards"; fail=1; }

RCODE=$(curl -sS -o /dev/null -w '%{http_code}' -L "${PAGE_URL}robots.txt")
[ "$RCODE" = "200" ] && ok "robots.txt served" || info "robots.txt HTTP $RCODE (meta tag still applies)"

say "Done"
if [ "$fail" = "0" ]; then
  printf '    \033[32mDashboard is live and verified.\033[0m\n\n'
else
  printf '    \033[33mDashboard is live but some checks failed (see above).\033[0m\n\n'
fi
info "Dashboard : $PAGE_URL"
info "Repo      : https://github.com/$FULL"
info "Actions   : https://github.com/$FULL/actions"
info "Refreshes daily at 06:00 America/Los_Angeles."
info "Run it now any time:  gh workflow run daily-digest --repo $FULL"
