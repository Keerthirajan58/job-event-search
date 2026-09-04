#!/usr/bin/env bash
# Everything added in phase 8, in one command.
#
#   ./tests/run_tests.sh
#
# Python tests need nothing. The dashboard tests need jsdom and a built page; if
# either is missing the script says so and still runs the Python half.
set -u
cd "$(dirname "$0")/.."
rc=0

echo "=================================================================="
echo " Python:  history / triage / notify"
echo "=================================================================="
# No -t: tests/ is a plain directory, not a package.
if python3 -m unittest discover -s tests -p 'test_*.py'; then
  echo "  python suites passed"
else
  echo "  PYTHON SUITES FAILED"
  rc=1
fi

echo
echo "=================================================================="
echo " Dashboard:  jsdom"
echo "=================================================================="
if [ ! -f out/index.html ]; then
  echo "  SKIP: out/index.html missing - run 'python3 run.py' first."
  rc=1
elif ! node -e "require('jsdom')" 2>/dev/null; then
  echo "  SKIP: jsdom not installed. Enable with:  npm install --no-save jsdom"
  echo "        (node_modules/ is gitignored)"
  rc=1
else
  # A syntax error in the embedded script breaks the whole page silently.
  python3 - > /tmp/jes_dash_check.js <<'PY'
import re
s = open('jobevents/html_report.py').read()
print(re.search(r'^JS = r"""\n(.*?)\n"""', s, re.S | re.M).group(1))
PY
  if node --check /tmp/jes_dash_check.js; then
    echo "  ok   embedded dashboard script parses"
  else
    echo "  FAIL embedded dashboard script has a syntax error"
    rc=1
  fi
  rm -f /tmp/jes_dash_check.js
  node tests/dashboard.test.js || rc=1
fi

echo
echo "=================================================================="
echo " Real browser:  what is actually painted and clickable"
echo "=================================================================="
# jsdom reports element.hidden, not the CSS cascade. A shipped bug where
# #modal{display:flex} beat [hidden]{display:none} passed 100 jsdom assertions
# and still covered the whole page, so this suite is not optional.
if [ ! -f out/index.html ]; then
  echo "  SKIP: out/index.html missing."
else
  node tests/browser.test.js 2>/dev/null || rc=1
fi

echo
if [ $rc -eq 0 ]; then echo "ALL SUITES PASSED"; else echo "SOME SUITES FAILED"; fi
exit $rc
