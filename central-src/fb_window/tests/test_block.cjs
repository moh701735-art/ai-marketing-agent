const fs = require('fs'), assert = require('assert');
const BLOCK = fs.readFileSync(__dirname + '/../block.js', 'utf8');
let n = 0; const T = (name, f) => { try { f(); n++; console.log('ok   ' + name); } catch (e) { console.log('FAIL ' + name + '\n  ' + (e.stack || e.message).split('\n').slice(0, 4).join('\n  ')); process.exitCode = 1; } };
const FN = new Function('body', 'days', 'halt', BLOCK + "\nlet startAt = '', startTxt = '';\nif (WIN) { startAt = WIN.start_at; endAt = WIN.end_at; startTxt = WIN.txt; days = WIN.days; }\nreturn { WIN, startAt, endAt, startTxt, days };");
const NOW = Date.UTC(2026, 10, 22, 12, 0, 0);   // 15:00 بغداد 22-11-2026
const run = (text, days = 3) => { const real = Date.now; Date.now = () => NOW; try { return FN(text, days, (m) => ({ halt: m })); } finally { Date.now = real; } };
const OK = (r) => { assert(!r.halt, 'unexpected halt: ' + r.halt); return r; };
const HALT = (r, re) => { assert(r.halt, 'expected halt'); if (re) assert(re.test(r.halt), r.halt); assert(/ما أنشأت أي حملة/.test(r.halt)); };
T('00 valid JS, no triple quotes, no template backticks', () => { assert(!BLOCK.includes('"""') && !BLOCK.includes("'''") && !BLOCK.includes('`')); });
T('01 owner: ارفعها الساعة 6 بالليل وقفها 6 الصبح → 18:00 → 06:00', () => { const r = OK(run('ارفع حمله فيس https://facebook.com/share/r/x/ ارفعها الساعة 6 بالليل وقفها 6 الصبح ميزانية 20 دولار')); assert.strictEqual(r.startAt, '2026-11-22T15:00:00+0000'); assert.strictEqual(r.endAt, '2026-11-23T03:00:00+0000'); assert.strictEqual(r.days, 1); assert(/من 2026-11-22 18:00 إلى 2026-11-23 06:00 \(بغداد\)/.test(r.startTxt)); });
T('02 owner: بكرة الساعة 7 الصبح وقفها الساعة 1 بالليل → 07:00 → 01:00 اليوم التالي (18 ساعة)', () => { const r = OK(run('ارفعها بكرة الساعة 7 الصبح وقفها الساعة 1 بالليل')); assert.strictEqual(r.startAt, '2026-11-23T04:00:00+0000'); assert.strictEqual(r.endAt, '2026-11-23T22:00:00+0000'); });
T('03 explicit verbs: روّج الساعة 22:00 وقف الساعة 10:00 صباحاً', () => { const r = OK(run('روّج الساعة 22:00 وقف الساعة 10:00 صباحاً')); assert.strictEqual(r.startAt, '2026-11-22T19:00:00+0000'); assert.strictEqual(r.endAt, '2026-11-23T07:00:00+0000'); });
T('04 «من 10 مساء الى 8 صباحا»', () => { const r = OK(run('حمله من الساعة 10 مساء الى الساعة 8 صباحا')); assert.strictEqual(r.startAt, '2026-11-22T19:00:00+0000'); assert.strictEqual(r.endAt, '2026-11-23T05:00:00+0000'); });
T('05 Arabic digits', () => { const r = OK(run('ابدأ الساعة ٢٢:٠٠ وقف ٠٦:٠٠')); assert.strictEqual(r.startAt, '2026-11-22T19:00:00+0000'); assert.strictEqual(r.endAt, '2026-11-23T03:00:00+0000'); });
T('06 start only (old path untouched): WIN null, days unchanged', () => { for (const t of ['روج بكرة الساعة 8 مساء ميزانية 30 دولار', 'تبدأ بكرة الساعة 8 مساءً', 'ابدأ الساعة 22:00']) { const r = OK(run(t, 3)); assert.strictEqual(r.WIN, null, t); assert.strictEqual(r.startAt, ''); assert.strictEqual(r.endAt, ''); assert.strictEqual(r.days, 3); } });
T('07 no clock → untouched; phone/ages/budget numbers never become windows', () => { for (const t of ['ارفع حملة فيس 07829503973 ميزانية 20 دولار يوم واحد', 'ارفع حملة من 18 الى 45 سنة ذكور 5 دولار', 'ميزانية 5 دولار لين 10 ايام', 'حمله الحالي العالي']) assert.strictEqual(OK(run(t)).WIN, null, t); });
T('08 ambiguous hour asks (no صباحاً/مساءً)', () => { HALT(run('ابدأ الساعة 6 وقف الساعة 7 صباحا'), /مو واضحة/); HALT(run('ابدأ 22:00 وقف الساعة 6'), /مو واضحة/); });
T('09 start already passed / <10 min', () => { HALT(run('ارفعها الساعة 2 العصر وقفها 6 مساء'), /فات أو أقل من 10 دقائق/); HALT(run('ابدأ 15:05 وقف 23:00'), /فات أو أقل/); });
T('10 window <30 min halts; exactly 30 ok; >7 days halts', () => { HALT(run('ابدأ 22:00 وقف 22:10'), /30 دقيقة/); assert.strictEqual(OK(run('ابدأ 22:00 وقف 22:30')).endAt, '2026-11-22T19:30:00+0000'); });
T('11 daily wording is refused with window (budget is total for the window)', () => { HALT(run('ابدأ 22:00 وقف 06:00 صباحا ميزانية 5 دولار يومي'), /إجمالية/); HALT(run('ابدأ 22:00 وقف 06:00 صباحا 5 دولار باليوم'), /إجمالية/); });
T('12 «يوم واحد» is not a daily-budget word', () => { OK(run('ابدأ 22:00 وقف 06:00 صباحا 5 دولار يوم واحد')); });
T('13 to24 table via endpoints: 12 ص=0, 12 ليلا=0, 12 م=12, 1 ليل=1, 5 ليلا=5, 6 ليلا=18, 11 ليلا=23', () => {
  const e = (a, b) => OK(run('ابدأ بكرة ' + a + ' وقف ' + b)).endAt;
  assert.strictEqual(OK(run('ابدأ بكرة الساعة 1 ظهرا وقف الساعة 12 بالليل')).endAt, '2026-11-23T21:00:00+0000');   // 13:00 → 00:00 BG = 21:00Z
  assert.strictEqual(e('الساعة 6 مساء', 'الساعة 5 ليلا'), '2026-11-24T02:00:00+0000');   // 5 ليلا = 05:00 صباحاً (اليوم التالي) = 02:00Z
  assert.strictEqual(e('الساعة 6 مساء', 'الساعة 11 ليلا'), '2026-11-23T20:00:00+0000');   // 23:00 BG = 20:00Z
  assert.strictEqual(e('الساعة 6 مساء', 'الساعة 12 مساء'), '2026-11-24T09:00:00+0000');   // 12 مساء = 12:00 ظهراً (بعد بداية 18:00 → اليوم التالي)
});
T('14 window longer than a day → days = ceil', () => { const r = OK(run('ابدأ بكرة الساعة 10 صباحا وقف بعد بكرة الساعة 4 مساء')); assert.strictEqual(r.days, 2); });
T('15 end day word after start day: «بعد يومين»', () => { const r = OK(run('روج بكرة الساعة 10 صباحا وقف بعد يومين الساعة 10 صباحا')); assert.strictEqual(r.startAt, '2026-11-23T07:00:00+0000'); assert.strictEqual(r.endAt, '2026-11-25T07:00:00+0000'); });
T('16 end before start with explicit day → halt', () => { HALT(run('تبدأ بكرة الساعة 8 مساءً وتوقف بكرة الساعة 6 مساءً'), /قبل وقت البداية/); });
T('17 «يومين» is not a daily word; «ثاني يوم» ok', () => { OK(run('ابدأ بكرة الساعة 10 صباحا وقف بعد يومين الساعة 10 صباحا')); });
console.log(n + ' passed'); 
