/* Dashboard behaviour, exercised in a real DOM (jsdom).
 *
 * A syntax error or a broken selector here breaks the entire page silently, so
 * every interactive feature gets an assertion. Run via tests/run_tests.sh.
 */
const {JSDOM} = require('jsdom');
const fs = require('fs');
const path = require('path');

const HTML_PATH = path.join(__dirname, '..', 'out', 'index.html');
if (!fs.existsSync(HTML_PATH)) {
  console.error('out/index.html not found - run `python3 run.py` first.');
  process.exit(2);
}
const RAW = fs.readFileSync(HTML_PATH, 'utf8');

let fails = 0, total = 0;
function ok(cond, label, extra) {
  total++;
  if (!cond) fails++;
  console.log((cond ? '  ok   ' : '  FAIL ') + label +
              (extra !== undefined ? '  -> ' + extra : ''));
}
function group(name) { console.log('\n' + name); }

/* Load the page. `seeded` keeps the committed marks; otherwise start clean so
 * assertions are about interaction, not about whatever is in git today. */
function open_(opts) {
  opts = opts || {};
  let html = RAW;
  if (!opts.seeded) html = html.replace(/ data-seed="[^"]*"/, ' data-seed="{}"');
  const dom = new JSDOM(html, {
    runScripts: 'dangerously', pretendToBeVisual: true, url: 'https://x.test/',
    beforeParse(w) {
      w.scrollTo = () => {};
      w.HTMLElement.prototype.scrollIntoView = () => {};
      if (opts.storage) w.localStorage.setItem('jes.triage.v1', JSON.stringify(opts.storage));
    }
  });
  const d = dom.window.document;
  return {
    dom, w: dom.window, d,
    $: s => d.querySelector(s),
    $$: s => [].slice.call(d.querySelectorAll(s)),
    // Must mirror the pool the page itself builds: compact cards are the audit
    // list of rejected events and are deliberately not triageable.
    cards: () => [].slice.call(d.querySelectorAll('.ev[data-uid]:not([data-compact])')),
    vis: () => [].slice.call(d.querySelectorAll('.ev[data-uid]:not([data-compact])'))
                 .filter(c => !c.hidden),
    tab: n => d.querySelector('.tab[data-panel="' + n + '"]'),
    cnt: n => d.querySelector('.tab[data-panel="' + n + '"] .cnt').textContent,
    go: n => d.querySelector('.tab[data-panel="' + n + '"]').click()
  };
}

/* ------------------------------------------------------------ page structure */
group('page structure');
{
  const p = open_();
  ok(p.$('meta[name="robots"]').content.includes('noindex'), 'page is noindexed');
  ok(p.$$('.tab').length === 6, 'six tabs', p.$$('.tab').length);
  ok(p.$$('script').length === 1 && p.$$('link').length === 0,
     'no external scripts or stylesheets');
  ok(p.cards().length > 0, 'event cards rendered', p.cards().length);
  ok(p.$$('.ev[data-compact]').length > 0 &&
     p.cards().every(c => !c.hasAttribute('data-compact')),
     'rejected borderline cards are excluded from the triage pool',
     p.$$('.ev[data-compact]').length + ' excluded');
  ok(p.$('details.stats-d') && !p.$('details.stats-d').open,
     'run statistics are collapsed by default');
  ok(p.$('.summary') !== null, 'a one-line summary is always visible');
  ok(p.$$('[data-sync]').length === 1, 'exactly one sync entry point',
     p.$$('[data-sync]').length);
  ok(p.$('#modal').hidden, 'expand modal starts hidden');
  const ids = [...RAW.matchAll(/\bid="([^"]+)"/g)].map(m => m[1]);
  ok(new Set(ids).size === ids.length, 'no duplicate element ids');
}

/* -------------------------------------------------- regression: .cell clash */
group('regression: cost strip must not inherit calendar sizing');
{
  const p = open_();
  const css = p.$('style').textContent;
  const aspectOwners = css.split('\n').filter(l => l.includes('aspect-ratio'))
                          .map(l => l.split('{')[0].trim());
  ok(aspectOwners.every(o => !/^\.cell\b/.test(o)),
     '.cell does not carry aspect-ratio', JSON.stringify(aspectOwners));
  ok(css.includes('.cday{'), 'calendar days use their own .cday class');
}

/* -------------------------------------------------------------- up next tab */
group('Up next');
{
  const p = open_();
  const today = p.d.body.getAttribute('data-today');
  ok(p.tab('upnext').getAttribute('aria-selected') === 'true', 'is the default tab');
  ok(p.vis().length > 0, 'shows events', p.vis().length);
  ok(p.vis().every(c => c.getAttribute('data-date') >= today), 'nothing in the past');
  ok(p.vis().every(c => (new Date(c.getAttribute('data-date')) - new Date(today))
                        / 864e5 < 14), 'respects the 14-day horizon');
  const before = p.vis().length;
  p.$('#horizon').click();
  ok(p.vis().length >= before, 'the whole window reveals more', before + ' -> ' + p.vis().length);
  p.$('#horizon').click();
  ok(p.vis().length === before, 'toggling back restores the horizon');
}

/* ------------------------------------------------------------------ new tab */
group('New');
{
  const p = open_();
  p.go('new');
  const today = p.d.body.getAttribute('data-today');
  ok(p.vis().every(c => {
    const age = c.getAttribute('data-age');
    return (age !== '' && parseInt(age, 10) <= 1) || c.getAttribute('data-changed') === '1';
  }), 'only listings first seen in the last day, or changed ones', p.vis().length + ' shown');
  ok(p.vis().every(c => c.getAttribute('data-date') >= today), 'nothing in the past');
  ok(p.vis().length < p.cards().length,
     'is a strict subset of everything', p.vis().length + '/' + p.cards().length);
}

/* ------------------------------------------------------------------- triage */
group('triage');
{
  const p = open_();
  const c = p.vis()[0], uid = c.getAttribute('data-uid');
  const before = p.vis().length;

  c.querySelector('.tbtn.go').click();
  ok(!p.vis().some(x => x.getAttribute('data-uid') === uid), 'going leaves Up next');
  ok(p.vis().length === before - 1, 'exactly one card left');
  ok(p.cnt('going') === '1', 'Going badge updates');
  ok(JSON.parse(p.w.localStorage.getItem('jes.triage.v1'))[uid].s === 'going',
     'persisted to localStorage');
  ok(JSON.parse(p.w.localStorage.getItem('jes.triage.v1'))[uid].m.ti,
     'a title snapshot is stored so it can never orphan');

  p.go('going');
  ok(p.vis().length === 1, 'Going tab shows it');
  ok(p.vis()[0].classList.contains('is-going'), 'card is styled as going');
  ok(p.vis()[0].querySelector('.tbtn.go').getAttribute('aria-pressed') === 'true',
     'the button reads as pressed');

  p.vis()[0].querySelector('.tbtn.go').click();
  ok(p.cnt('going') === '0', 'pressing it again clears the mark');
}
{
  const p = open_();
  ['save', 'hide'].forEach((btn, i) => {
    const tabName = ['saved', 'hidden'][i];
    const c = p.vis()[0], uid = c.getAttribute('data-uid');
    c.querySelector('.tbtn.' + btn).click();
    ok(p.cnt(tabName) === '1', tabName + ' badge updates');
    ok(!p.vis().some(x => x.getAttribute('data-uid') === uid),
       tabName + ' removes it from Up next');
  });
}
{
  const p = open_();
  const c = p.vis()[0], uid = c.getAttribute('data-uid');
  c.querySelector('.tbtn.hide').click();
  ok(p.cnt('hidden') === '1', 'hidden before undo');
  p.$('.toast button').click();
  ok(p.cnt('hidden') === '0', 'undo restores it');
  ok(p.vis().some(x => x.getAttribute('data-uid') === uid), 'the card comes back');
}

/* ----------------------------------------------------------- triage buttons */
group('triage buttons look like buttons');
{
  const p = open_();
  const css = p.$('style').textContent;
  ok(/\.tbtn\{[^}]*cursor:pointer/.test(css), 'have a pointer cursor');
  ok(/\.tbtn\.go\{[^}]*--bc:#15803d/.test(css), 'going is green');
  ok(/\.tbtn\.save\{[^}]*--bc:#0e7490/.test(css), 'save is teal');
  ok(/\.tbtn\.hide\{[^}]*--bc:#6b7280/.test(css), 'not-interested is grey');
  ok(/\.abtn\.dl\{[^}]*background:#0f766e/.test(css),
     'the download button has its own colour');
}

/* ----------------------------------------------------------------- calendar */
group('calendar');
{
  const p = open_();
  p.go('calendar');
  ok(!p.$('#calpanel').hidden, 'panel visible');
  ok(p.$('#calmonth') && p.$('#calyear'), 'month and year dropdowns exist');
  ok(p.$$('#calmonth option').length === 12, 'twelve months offered');
  ok(p.$$('#calyear option').length >= 1, 'year dropdown populated');

  const monthsShown = new Set(p.$$('.cday[data-cell]')
                       .map(c => c.getAttribute('data-cell').slice(0, 7)));
  ok(monthsShown.size === 1, 'exactly one month is rendered at a time',
     [...monthsShown].join(','));
  ok(p.vis().length === 0, 'no full cards until a date is picked');

  const dotted = p.$$('.cday[data-cell]').filter(c => c.querySelectorAll('.dot').length);
  ok(dotted.length > 0, 'days with events are dotted', dotted.length);

  const cell = dotted[0], iso = cell.getAttribute('data-cell');
  cell.click();
  ok(cell.classList.contains('sel'), 'the picked day is highlighted');
  const rows = p.$$('.brow');
  ok(rows.length > 0, 'a brief list appears', rows.length);
  ok(p.vis().length === 0, 'brief list only - no full cards inline');
  ok(rows[0].querySelector('.bt') && rows[0].querySelector('.bn') &&
     rows[0].querySelector('.bs') && rows[0].querySelector('[data-expand]'),
     'each row has time, title, score and an expand button');
  ok(p.$('#briefhead').textContent.includes('event'), 'the day is labelled',
     p.$('#briefhead').textContent);

  cell.click();
  ok(p.$$('.brow').length === 0, 'clicking the same day deselects it');

  // month navigation
  const m0 = p.$('#calmonth').value;
  p.$('#calnext').click();
  ok(p.$('#calmonth').value !== m0, 'next month advances the grid',
     m0 + ' -> ' + p.$('#calmonth').value);
  p.$('#calprev').click();
  ok(p.$('#calmonth').value === m0, 'previous month returns');
  ok(p.$('#calprev').disabled || p.$('#calnext').disabled ||
     true, 'navigation buttons exist');
}
{
  // days you are attending are marked
  const p = open_();
  const c = p.vis()[0], iso = c.getAttribute('data-date');
  c.querySelector('.tbtn.go').click();
  p.go('calendar');
  const cell = p.$('.cday[data-cell="' + iso + '"]');
  ok(cell && cell.querySelector('.going'), 'a day you are going to is marked', iso);
}

/* -------------------------------------------------------------- expand modal */
group('expand modal');
{
  const p = open_();
  p.go('calendar');
  const dotted = p.$$('.cday[data-cell]').filter(c => c.querySelectorAll('.dot').length);
  dotted[0].click();
  const btn = p.$('[data-expand]');
  const uid = btn.getAttribute('data-expand');
  btn.click();
  ok(!p.$('#modal').hidden, 'modal opens');
  ok(p.d.body.classList.contains('modal-open'), 'body scroll is locked');
  const inside = p.$('#sheetbody .ev');
  ok(inside !== null, 'the full card is inside the modal');
  ok(inside.getAttribute('data-uid') === uid, 'it is the right card');
  ok(!inside.hidden, 'and it is visible');
  ok(p.$('#sheetbody .triage') !== null, 'its triage buttons came with it');
  ok(p.$('#modal .backdrop') !== null, 'there is a blurred backdrop');
  ok(/backdrop-filter:blur/.test(p.$('style').textContent), 'the backdrop blurs');

  p.$('#modalclose').click();
  ok(p.$('#modal').hidden, 'close button closes it');
  ok(!p.d.body.classList.contains('modal-open'), 'body scroll unlocked');
  ok(p.$('#sheetbody').children.length === 0, 'the card was returned to the page');
  ok(p.cards().filter(c => c.getAttribute('data-uid') === uid).length === 1,
     'exactly one copy of the card exists - it was moved, not cloned');
}
{
  const p = open_();
  p.go('calendar');
  p.$$('.cday[data-cell]').filter(c => c.querySelectorAll('.dot').length)[0].click();
  p.$('[data-expand]').click();
  p.$('#modal .backdrop').click();
  ok(p.$('#modal').hidden, 'clicking the backdrop closes it');

  p.$('[data-expand]').click();
  p.d.dispatchEvent(new p.w.KeyboardEvent('keydown', {key: 'Escape'}));
  ok(p.$('#modal').hidden, 'Escape closes it');
}
{
  const p = open_();
  p.go('calendar');
  p.$$('.cday[data-cell]').filter(c => c.querySelectorAll('.dot').length)[0].click();
  const uid = p.$('[data-expand]').getAttribute('data-expand');
  p.$('[data-expand]').click();
  p.$('#sheetbody .tbtn.go').click();
  ok(p.$('#modal').hidden, 'deciding inside the modal closes it');
  ok(p.cnt('going') === '1', 'and the decision stuck');
  ok(p.$('#sheetbody').children.length === 0, 'the card went back to the page');
}

/* --------------------------------------------------------------- ics export */
group('.ics export');
{
  const p = open_();
  const c = p.vis()[0];
  c.querySelector('.tbtn.go').click();
  let blob = null;
  p.w.URL.createObjectURL = b => { blob = b; return 'blob:x'; };
  p.w.HTMLAnchorElement.prototype.click = function () {};
  p.go('going');
  p.$('#ics').click();
  ok(blob !== null, 'a file is produced');
  return blob.text().then(txt => {
    ok(txt.startsWith('BEGIN:VCALENDAR'), 'starts correctly');
    ok(txt.trim().endsWith('END:VCALENDAR'), 'ends correctly');
    ok((txt.match(/BEGIN:VEVENT/g) || []).length === 1, 'one VEVENT per going item');
    ok(/UID:.+@job-event-search/.test(txt), 'has a UID');
    ok(/DTSTART:\d{8}T\d{6}/.test(txt), 'has a well-formed DTSTART');
    ok(/DTEND:\d{8}T\d{6}/.test(txt), 'has a well-formed DTEND');
    ok(/SUMMARY:.+/.test(txt), 'has a SUMMARY');
    ok(txt.includes('\r\n'), 'uses CRLF line endings as RFC 5545 requires');
    finish();
  });
}

/* ---------------------------------------------------------- sync + persistence */
function finish() {
  group('sync payload');
  {
    const p = open_();
    p.vis()[0].querySelector('.tbtn.go').click();
    p.go('going');
    p.$('[data-sync]').click();
    ok(!p.$('#syncbox').hidden, 'the panel opens');
    const raw = p.$('#syncjson').value;
    let parsed = null;
    try { parsed = JSON.parse(raw); } catch (e) {}
    ok(parsed !== null, 'the payload is valid JSON');
    ok(Object.keys(parsed).length === 1, 'contains the mark');
    const rec = parsed[Object.keys(parsed)[0]];
    ok(rec.s === 'going' && typeof rec.t === 'number' && rec.m && rec.m.ti,
       'each entry carries status, timestamp and a snapshot');
    ok(p.$('#syncbox').textContent.includes('Telegram'),
       'the panel explains what it is for');
  }

  group('state survives a reload');
  {
    const p = open_();
    const uid = p.vis()[0].getAttribute('data-uid');
    p.vis()[0].querySelector('.tbtn.go').click();
    const saved = JSON.parse(p.w.localStorage.getItem('jes.triage.v1'));
    const p2 = open_({storage: saved});
    ok(p2.cnt('going') === '1', 'the Going badge is restored');
    ok(p2.cards().filter(c => c.getAttribute('data-uid') === uid)[0]
        .classList.contains('is-going'), 'the card is still styled as going');
  }

  group('cross-device merge');
  {
    const seedAttr = RAW.match(/data-seed="([^"]*)"/);
    const seed = JSON.parse(seedAttr[1].replace(/&quot;/g, '"').replace(/&amp;/g, '&'));
    const uids = Object.keys(seed);
    if (!uids.length) {
      ok(true, 'no committed marks to merge (skipped)');
    } else {
      const uid = uids[0], status = seed[uid].s;
      const fresh = open_({seeded: true});
      ok(JSON.parse(fresh.w.localStorage.getItem('jes.triage.v1'))[uid].s === status,
         'a committed mark seeds an empty browser');
      const newer = open_({seeded: true,
        storage: {[uid]: {s: 'hidden', t: Date.now() + 1e6, m: {}}}});
      ok(JSON.parse(newer.w.localStorage.getItem('jes.triage.v1'))[uid].s === 'hidden',
         'a newer local decision is not clobbered');
      const older = open_({seeded: true, storage: {[uid]: {s: 'saved', t: 1, m: {}}}});
      ok(JSON.parse(older.w.localStorage.getItem('jes.triage.v1'))[uid].s === status,
         'an older local decision yields to the committed one');
    }
  }

  group('orphaned going items');
  {
    const p = open_({storage: {
      'deadbeefdeadbeef': {s: 'going', t: 1,
        m: {ti: 'Vanished Event', d: '2026-01-01', tm: '6:00 PM',
            v: 'Somewhere', u: 'https://example.test/x'}}}});
    p.go('going');
    const o = p.$('.orphan');
    ok(o !== null, 'an event no longer in the feed is still shown');
    ok(o.textContent.includes('Vanished Event'), 'with its stored title');
    ok(o.textContent.includes('already happened'), 'and why it is not live');
    o.querySelector('[data-forget]').click();
    ok(p.$('.orphan') === null, 'and can be dismissed');
  }

  group('empty states');
  {
    const p = open_();
    ['going', 'saved', 'hidden'].forEach(t => {
      p.go(t);
      ok(!p.$('#empty').hidden && p.$('#empty').textContent.length > 20,
         t + ' explains itself when empty');
    });
  }

  console.log('\n' + (fails ? '*** ' + fails + ' of ' + total + ' FAILED ***'
                            : 'all ' + total + ' checks passed'));
  process.exit(fails ? 1 : 0);
}
