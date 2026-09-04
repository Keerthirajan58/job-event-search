/* The page in a REAL browser.
 *
 * This suite exists because of a specific escape: `#modal{display:flex}` beat the
 * user-agent `[hidden]{display:none}` rule, so the dashboard shipped with an empty
 * modal and a blurred backdrop covering everything. jsdom reported the element as
 * hidden (the PROPERTY was true) and 100 assertions passed. Only a real cascade
 * catches that, so the checks here are deliberately about what is PAINTED and what
 * is CLICKABLE, not about DOM properties.
 *
 * Skips cleanly when no Chrome is installed.
 */
const fs = require('fs');
const path = require('path');

const CANDIDATES = [
  process.env.PUPPETEER_EXECUTABLE_PATH,
  process.env.CHROME_PATH,
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable',
  '/usr/bin/chromium', '/usr/bin/chromium-browser',
].filter(Boolean);

const exe = CANDIDATES.find(p => { try { return fs.existsSync(p); } catch (e) { return false; } });
const page = path.join(__dirname, '..', 'out', 'index.html');

let puppeteer = null;
try { puppeteer = require('puppeteer-core'); } catch (e) {}

if (!puppeteer) {
  console.log('  SKIP: puppeteer-core not installed (npm install --no-save puppeteer-core)');
  process.exit(0);
}
if (!exe) {
  console.log('  SKIP: no Chrome found. Set CHROME_PATH to enable.');
  process.exit(0);
}
if (!fs.existsSync(page)) {
  console.log('  SKIP: out/index.html missing - run `python3 run.py` first.');
  process.exit(0);
}

let fails = 0;
const ok = (c, l, x) => { if (!c) fails++;
  console.log((c ? '  ok   ' : '  FAIL ') + l + (x !== undefined ? '  -> ' + x : '')); };
const wait = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const b = await puppeteer.launch({executablePath: exe, headless: 'new',
                                    args: ['--no-sandbox', '--disable-gpu']});
  const p = await b.newPage();
  await p.setViewport({width: 1200, height: 950});
  const errors = [];
  p.on('pageerror', e => errors.push('pageerror: ' + e.message));
  p.on('console', m => {
    // The browser probes /favicon.ico by itself; that 404 is not a page fault.
    if (m.type() === 'error' && !/favicon/.test(m.text())) errors.push('console: ' + m.text());
  });
  await p.goto('file://' + page, {waitUntil: 'networkidle0'});

  console.log('\nnothing is covering the page');
  const centre = await p.evaluate(() => {
    const e = document.elementFromPoint(innerWidth / 2, innerHeight / 2);
    return e ? (e.id || e.className || e.tagName) : 'nothing';
  });
  ok(!/modal|backdrop|sheet/.test(String(centre)),
     'the element under the middle of the screen is page content', String(centre).slice(0, 40));
  for (const id of ['modal', 'calpanel', 'goingbar', 'syncbox']) {
    const shown = await p.evaluate(i => {
      const el = document.getElementById(i);
      return el ? getComputedStyle(el).display !== 'none' : null;
    }, id);
    ok(shown === false, '#' + id + ' is not painted on load');
  }
  const tabHit = await p.evaluate(() => {
    const t = document.querySelector('.tab[data-panel="calendar"]');
    const r = t.getBoundingClientRect();
    const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return t === hit || t.contains(hit);
  });
  ok(tabHit, 'tabs are reachable by a real click, not covered by an overlay');

  console.log('\ncalendar');
  await p.click('.tab[data-panel="calendar"]');
  await wait(350);
  const cal = await p.evaluate(() => ({
    painted: getComputedStyle(document.getElementById('calpanel')).display !== 'none',
    months: new Set([...document.querySelectorAll('.cday[data-cell]')]
             .map(c => c.getAttribute('data-cell').slice(0, 7))).size,
    cells: document.querySelectorAll('.cday[data-cell]').length,
    gridH: document.getElementById('calgrid').getBoundingClientRect().height,
    picks: !!document.getElementById('calmonth') && !!document.getElementById('calyear'),
  }));
  ok(cal.painted, 'calendar is painted');
  ok(cal.months === 1, 'exactly one month at a time', cal.months);
  ok(cal.cells >= 28, 'a full month of days', cal.cells);
  ok(cal.picks, 'month and year pickers present');
  ok(cal.gridH < 700, 'a whole month fits on screen', Math.round(cal.gridH) + 'px tall');

  const picked = await p.evaluate(() => {
    const c = [...document.querySelectorAll('.cday[data-cell]')]
                .find(x => x.querySelectorAll('.dot').length > 0);
    if (!c) return null;
    c.click();
    return c.getAttribute('data-cell');
  });
  await wait(250);
  const rows = await p.evaluate(() => document.querySelectorAll('.brow').length);
  ok(picked && rows > 0, 'picking a day shows brief rows', picked + ' -> ' + rows);
  const inlineCards = await p.evaluate(() =>
    [...document.querySelectorAll('.ev[data-uid]:not([data-compact])')]
      .filter(c => getComputedStyle(c).display !== 'none').length);
  ok(inlineCards === 0, 'brief rows only - no full cards inline', inlineCards);

  console.log('\nexpand modal');
  await p.click('[data-expand]');
  await wait(350);
  const m = await p.evaluate(() => {
    const el = document.getElementById('modal');
    const card = document.querySelector('#sheetbody .ev');
    const bd = document.querySelector('#modal .backdrop');
    return {
      painted: getComputedStyle(el).display !== 'none',
      hasCard: !!card,
      cardPainted: card ? getComputedStyle(card).display !== 'none' : false,
      chars: (document.getElementById('sheetbody').textContent || '').trim().length,
      blur: bd ? getComputedStyle(bd).backdropFilter || getComputedStyle(bd).webkitBackdropFilter : '',
      closeHit: (() => {
        const c = document.getElementById('modalclose');
        const r = c.getBoundingClientRect();
        const h = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        return c === h || c.contains(h);
      })(),
    };
  });
  ok(m.painted, 'modal is painted when expanded');
  ok(m.hasCard && m.cardPainted, 'the full card inside it is visible');
  ok(m.chars > 200, 'and is not empty', m.chars + ' chars');
  ok(/blur/.test(m.blur), 'the backdrop really blurs', m.blur || '(none)');
  ok(m.closeHit, 'the close button is clickable');

  await p.click('#modalclose');
  await wait(250);
  const closed = await p.evaluate(() =>
    getComputedStyle(document.getElementById('modal')).display === 'none' &&
    document.getElementById('sheetbody').children.length === 0);
  ok(closed, 'closing returns the card to the page');

  console.log('\ntriage');
  await p.click('.tab[data-panel="upnext"]');
  await wait(250);
  await p.evaluate(() => document.querySelector('.ev:not([hidden]) .tbtn.go').click());
  await wait(250);
  const badge = await p.evaluate(() =>
    document.querySelector('.tab[data-panel="going"] .cnt').textContent);
  ok(badge === '1', 'marking going updates the badge', badge);
  const btnLooks = await p.evaluate(() => {
    const b = document.querySelector('.tbtn.go');
    const s = getComputedStyle(b);
    return {cursor: s.cursor, border: parseFloat(s.borderTopWidth)};
  });
  ok(btnLooks.cursor === 'pointer' && btnLooks.border > 0,
     'triage controls read as buttons', JSON.stringify(btnLooks));

  console.log('\nno errors');
  ok(errors.length === 0, 'no javascript errors', errors.slice(0, 3).join(' | ') || 'none');

  console.log('\n' + (fails ? '*** ' + fails + ' BROWSER CHECKS FAILED ***'
                            : 'browser checks passed'));
  await b.close();
  process.exit(fails ? 1 : 0);
})().catch(e => { console.error('browser suite crashed:', e.message); process.exit(1); });
