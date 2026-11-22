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
console.log(n + ' passed');
