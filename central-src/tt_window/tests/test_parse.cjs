const fs = require('fs'), assert = require('assert');
const BLOCK = fs.readFileSync(__dirname + '/../block.js', 'utf8');
let n = 0; const T = (name, f) => { try { f(); n++; console.log('ok   ' + name); } catch (e) { console.log('FAIL ' + name + '\n  ' + (e.stack || e.message).split('\n').slice(0, 4).join('\n  ')); process.exitCode = 1; } };
const FN = new Function('d', 'it', 'say', 'launch', BLOCK + '\n return { launch };');
const NOW = Date.UTC(2026, 10, 22, 12, 0, 0);               // 15:00 بغداد، 22-11-2026
const run = (text, it = {}, launch = { days: 1, budget: 30 }) => { const real = Date.now; Date.now = () => NOW; try { return FN({ text }, it, (m) => ({ say: m }), launch); } finally { Date.now = real; } };
const OK = (r) => { assert(!r.say, 'unexpected halt: ' + r.say); return r.launch; };
const HALT = (r, re) => { assert(r.say, 'expected halt'); if (re) assert(re.test(r.say), r.say); assert(/ما أنشأت أي حملة/.test(r.say)); };

T('00 block is valid JS and uses only ASCII-safe regex escapes', () => { new Function('d', 'it', 'say', 'launch', BLOCK); assert(!BLOCK.includes("'''")); });
T('01 owner sentence: روّجها الساعة 22:00 وقفها 10:00 صباحاً → 22:00 بغداد (19:00 UTC) → 10:00 (07:00 UTC) اليوم التالي', () => {
  const l = OK(run('ارفع حمله يدويه عميل محتمل رسائل واتساب / روّجها الساعة 22:00 وقفها الساعة 10:00 صباحاً / ميزانية 30 دولار / بحساب بنين', { budget: 30 }));
  assert.strictEqual(l.start_at, '2026-11-22 19:00:00'); assert.strictEqual(l.end_at, '2026-11-23 07:00:00'); });
T('02 colloquial: روج لها 22:00 وقف لها 10:00 صبح', () => { const l = OK(run('روج لها 22:00 وقف لها 10:00 صبح وانطي ميزانية 30', { budget: 30 })); assert.strictEqual(l.start_at, '2026-11-22 19:00:00'); assert.strictEqual(l.end_at, '2026-11-23 07:00:00'); });
T('03 "من 22:00 الى 6:00 صباحا" form B', () => { const l = OK(run('حمله من 22:00 الى 6:00 صباحا ميزانية 30 دولار', { budget: 30 })); assert.strictEqual(l.start_at, '2026-11-22 19:00:00'); assert.strictEqual(l.end_at, '2026-11-23 03:00:00'); });
T('04 "من الساعة 10 مساء الى الساعة 10 صباحا"', () => { const l = OK(run('من الساعة 10 مساء الى الساعة 10 صباحا', { budget: 30 })); assert.strictEqual(l.start_at, '2026-11-22 19:00:00'); assert.strictEqual(l.end_at, '2026-11-23 07:00:00'); });
T('05 Arabic-Indic digits ٢٢:٠٠ and ١٠:٠٠ صباحاً', () => { const l = OK(run('روجها الساعة ٢٢:٠٠ وقفها ١٠:٠٠ صباحاً', { budget: 30 })); assert.strictEqual(l.start_at, '2026-11-22 19:00:00'); assert.strictEqual(l.end_at, '2026-11-23 07:00:00'); });
T('06 minutes kept: 21:30 → 09:45 صباحاً', () => { const l = OK(run('روجها 21:30 وقفها 9:45 صباحا', { budget: 30 })); assert.strictEqual(l.start_at, '2026-11-22 18:30:00'); assert.strictEqual(l.end_at, '2026-11-23 06:45:00'); });
T('07 ambiguous START (الساعة 10 بدون صباح/مساء) halts and asks', () => { HALT(run('روجها الساعة 10 وقفها 6:00 صباحا'), /مو واضحة/); });
T('08 ambiguous END (10:00 بدون صباحاً) halts and asks', () => { HALT(run('روجها 22:00 وقفها 10:00'), /مو واضحة/); });
T('09 leading zero = 24h explicit: 08:30 accepted (tomorrow)', () => { const l = OK(run('روجها بكرة 08:30 وقفها 23:00', { budget: 30 })); assert.strictEqual(l.start_at, '2026-11-23 05:30:00'); assert.strictEqual(l.end_at, '2026-11-23 20:00:00'); });
T('10 start already passed today and no «بكرة» → halt (no silent roll to tomorrow)', () => { HALT(run('روجها 14:00 وقفها 23:00'), /فات أو أقل من 10 دقائق/); });
T('11 «بكرة» moves start to tomorrow; «بعد بكرة» two days', () => { assert.strictEqual(OK(run('روجها بكرة 14:00 وقفها 23:00')).start_at, '2026-11-23 11:00:00'); assert.strictEqual(OK(run('روجها بعد بكرة 14:00 وقفها 23:00')).start_at, '2026-11-24 11:00:00'); });
T('12 start less than 10 minutes ahead halts (15:05 بغداد)', () => { HALT(run('روجها 15:05 وقفها 23:00'), /أقل من 10 دقائق/); });
T('13 window under 30 minutes halts; exactly 30 ok', () => { HALT(run('روجها 22:00 وقفها 22:20'), /30 دقيقة/); assert.strictEqual(OK(run('روجها 22:00 وقفها 22:30')).end_at, '2026-11-22 19:30:00'); });
T('14 start-only (روّج بكرة الساعة 8 مساءً) → end = start + days', () => { const l = OK(run('روج بكرة الساعة 8 مساء ميزانية 30 دولار يومين', { budget: 30 }, { days: 2, budget: 30 })); assert.strictEqual(l.start_at, '2026-11-23 17:00:00'); assert.strictEqual(l.end_at, '2026-11-25 17:00:00'); });
T('15 no clock in the text → untouched (no start_at/end_at, no halt)', () => { const l = OK(run('ارفع حمله عميل محتمل واتساب 5000 يوم واحد بحساب بنين', { budget: 5000 })); assert(!('start_at' in l) && !('end_at' in l)); });
T('16 «شغلها 30 دولار لين 10 ايام» (no clock) → untouched', () => { const l = OK(run('ارفع حمله شغلها 30 دولار لين 10 ايام بحساب بنين', { budget: 30 })); assert(!('start_at' in l)); });
T('17 clock + cue but unreadable → halt with the example format', () => { HALT(run('شغلها الساعة 22:00 وبعدين وقف الساعة'), /روّج الساعة 22:00/); });
T('18 invalid hour 25:00 halts', () => { HALT(run('روجها 25:00 وقفها 10:00 صباحا'), /مو صالحة/); });
T('19 budget guard: LLM took the clock hour as budget (22) while the text has no other 22 → halt', () => { HALT(run('روجها 22:00 وقفها 10:00 صباحا ميزانية ثلاثين دولار', { budget: 22 }), /الميزانية/); });
T('20 budget guard passes when the same number is a real budget (10 دولار + window to 10:00)', () => { OK(run('روجها 22:00 وقفها 10:00 صباحا ميزانية 10 دولار', { budget: 10 })); });
T('21 12:00 مساء = noon, 12 ليلا = midnight, 12 صباحا = midnight', () => { assert.strictEqual(OK(run('روجها بكرة 12 مساء وقفها 6 مساء')).start_at, '2026-11-23 09:00:00'); assert.strictEqual(OK(run('روجها بكرة 12 ليلا وقفها 6 صباحا')).start_at, '2026-11-22 21:00:00'); });
T('22 ظهرا: 1 ظهرا = 13:00', () => { assert.strictEqual(OK(run('روجها بكرة 1 ظهرا وقفها 5 مساء')).start_at, '2026-11-23 10:00:00'); });
T('23 end earlier than start rolls to the next day (start 22:00, end 23:00 → same night, 1 hour)', () => { const l = OK(run('روجها 22:00 وقفها 23:00')); assert.strictEqual(l.end_at, '2026-11-22 20:00:00'); });
T('24 words sharing letters are not cues (التالي, العالي, الحالي do not act as «الى»)', () => { const l = OK(run('حمله الحالي 22:00 العالي', { budget: 30 })); assert(!('start_at' in l)); });
T('25 days from launch missing/zero → default 1 for start-only', () => { const l = OK(run('روج بكرة الساعة 8 مساء', {}, { budget: 30 })); assert.strictEqual(l.end_at, '2026-11-24 17:00:00'); });
T('26 launch object keeps its other fields untouched', () => { const l = OK(run('روجها 22:00 وقفها 10:00 صباحا', { budget: 30 }, { days: 1, budget: 30, campaign_name: 'x', countries: ['IQ'] })); assert.deepStrictEqual([l.days, l.budget, l.campaign_name, l.countries], [1, 30, 'x', ['IQ']]); });
T('27 real owner templates without a clock stay untouched (dress campaign, PUBG-style labels)', () => {
  for (const t of ['ارفع حمله يدويه عميل محتمل رسائل واتساب / 07829503973 / هوية: كوزمتك وملابس / يوم واحد / 20 الف / اختار جمهور 1 / سميها فستان هودي / بحساب بنين ودالية',
    'ارفع حمله هدف الحملة: مبيعات / الدول المستهدفة: السعودية الكويت / العمر 18-45 / الجنس رجال / اللغة عربي / ميزانية 30 دولار / 3 ايام / بحساب غزل وزينب سميها ببجي']) { const l = OK(run(t, { budget: 30 })); assert(!('start_at' in l)); } });
T('28 tonight/now words alone do not schedule (ابدأ الان، فعلها)', () => { for (const t of ['ابدا الان ميزانية 30 دولار يوم واحد', 'ارفع حمله وفعلها مباشرة 5 دولار']) assert(!('start_at' in OK(run(t, { budget: 5 })))); });
const E = (t, o = {}) => { const l = OK(run(t, { budget: 30 }, { days: 1, budget: 30, ...o })); return [l.start_at, l.end_at]; };
T('29 p230c: end day word «بكرة» is the END day only — start stays today (was shifting the start)', () => { assert.deepStrictEqual(E('روجها 22:00 وقفها بكرة 7 صباحا'), ['2026-11-22 19:00:00', '2026-11-23 04:00:00']); });
T('30 p230c: start tomorrow 10 AM, stop tomorrow 8 PM (10h, same day)', () => { assert.deepStrictEqual(E('روج بكرة 10 صباحا وقف بكرة 8 مساء'), ['2026-11-23 07:00:00', '2026-11-23 17:00:00']); });
T('31 p230c: multi-day window — stop «بعد بكرة 8 مساء» (34h)', () => { assert.deepStrictEqual(E('روج بكرة 10 صباحا وقف بعد بكرة 8 مساء'), ['2026-11-23 07:00:00', '2026-11-24 17:00:00']); });
T('32 p230c: «ثاني يوم» is relative to the start day', () => { assert.deepStrictEqual(E('روج بكرة 10 صباحا وقف ثاني يوم 8 مساء'), ['2026-11-23 07:00:00', '2026-11-24 17:00:00']); assert.deepStrictEqual(E('روجها الساعة 22:00 وقفها ثاني يوم الساعة 7 صباحا'), ['2026-11-22 19:00:00', '2026-11-23 04:00:00']); });
T('33 p230c: «بعد يومين» for the end is 2 days after the start day', () => { assert.deepStrictEqual(E('روج بكرة 10 صباحا وقف بعد يومين 8 مساء'), ['2026-11-23 07:00:00', '2026-11-25 17:00:00']); });
T('34 p230c: day word before the cue («بكرة روجها الساعة 8 مساء») and after the clock («8 مساء بكرة»)', () => { assert.strictEqual(E('بكرة روجها الساعة 8 مساء وقفها 11 مساء')[0], '2026-11-23 17:00:00'); assert.deepStrictEqual(E('روجها الساعة 8 مساء بكرة وقفها 11 مساء'), ['2026-11-23 17:00:00', '2026-11-23 20:00:00']); });
T('35 p230c: explicit end before the start halts', () => { HALT(run('روج بعد بكرة 10 صباحا وقف بكرة 8 مساء'), /قبل وقت البداية/); });
T('36 p230c: unrelated «بكرة» elsewhere in the text no longer moves the start', () => { assert.strictEqual(E('ارفع حمله بكرة اهم يوم ميزانية 30 دولار روجها 22:00 وقفها 7 صباحا')[0], '2026-11-22 19:00:00'); });
T('37 p230c: duration word «يومين» (not «بعد يومين») is not a day offset', () => { assert.deepStrictEqual(E('روج بكرة الساعة 8 مساء يومين', { days: 2 }), ['2026-11-23 17:00:00', '2026-11-25 17:00:00']); });
T('38 p230c: same-day end 20 minutes after start still refused (under 30 minutes)', () => { HALT(run('روج بكرة 10 صباحا وقف بكرة 10:20 صباحا'), /30 دقيقة/); });
T('39 p230d: owner message — «ارفع حمله ساعه ١٠ بليل / وقفها ساعه ٧ صبح» (no start verb, Arabic digits, بليل) → 22:00 → 07:00', () => {
  const l = OK(run('ارفع حمله ساعه ١٠ بليل\nوقفها ساعه ٧ صبح\n\nيوم واحد\nميزانيه ٢٠ الف\nبحساب boostpro13\n\n#TjqKk15B4dbIMrdXmm+zc3LHTHEdYUzFRmir2he0Az8XwKQErgHldu2HVjbcMZ0=\n\nعميل محتمل واتساب\n07829503973', { budget: 20000 }));
  assert.strictEqual(l.start_at, '2026-11-22 19:00:00'); assert.strictEqual(l.end_at, '2026-11-23 04:00:00'); });
T('40 p230d: no start verb with day words: «ارفع حمله بكرة ساعه 10 صباحا وقفها بعد بكرة ساعه 8 مساء»', () => { assert.deepStrictEqual(E('ارفع حمله بكرة ساعه 10 صباحا وقفها بعد بكرة ساعه 8 مساء'), ['2026-11-23 07:00:00', '2026-11-24 17:00:00']); });
T('41 p230d: noun words between the verb and the clock («روج الحملة بكرة ساعة 8 مساء») for start-only', () => { assert.strictEqual(E('روج الحملة بكرة ساعة 8 مساء')[0], '2026-11-23 17:00:00'); });
T('42 p230d: end only (no start clock) still halts with the format hint (no guessing)', () => { HALT(run('ارفع حمله وقفها الساعة 8 مساء'), /روّج الساعة 22:00/); });
T('43 p230d: phone, handle digits and budget words are never read as the start clock', () => { const l = OK(run('ارفع حمله عميل محتمل واتساب 07829503973 بحساب boostpro13 ميزانيه 20 الف', { budget: 20000 })); assert(!('start_at' in l)); });
T('44 p230d: ambiguous start in the no-verb form still asks (ساعه 10 وقفها ساعه 7 صبح)', () => { HALT(run('ارفع حمله ساعه 10 وقفها ساعه 7 صبح'), /مو واضحة/); });
console.log(n + ' passed');
