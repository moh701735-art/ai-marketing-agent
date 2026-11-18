// يشغّل عقدة GD: render الحقيقية (من pages.py عبر dump.py) على كل صفحات الدليل. لا شبكة ولا n8n.
const fs = require('fs'); const D = JSON.parse(fs.readFileSync(process.env.GD_NODES || '/tmp/gd_nodes.json', 'utf8'));
let pass = 0, fail = 0; const ok = (n, c, x) => { if (c) pass++; else { fail++; console.log('FAIL', n, x === undefined ? '' : JSON.stringify(x).slice(0, 300)); } };
const J = a => a.map(x => ({ json: x }));
function run(code, route, input) { const $ = n => { if (n !== 'Route') throw new Error('no ' + n); return { first: () => ({ json: route }) }; };
  return new Function('$', '$input', code)($, { all: () => J(input || [{}]), first: () => ({ json: (input || [{}])[0] }) }).map(x => x.json); }
for (const k of ['render', 'reply']) { try { new Function('$', '$input', D[k]); pass++; } catch (e) { fail++; console.log('SYNTAX', k, e.message); } }
const CB = /^[a-z0-9_:-]{1,48}$/;
const checkKb = (n, kb) => { ok(n + ' kb rows<=8', kb.length <= 8 && kb.length >= 1); kb.forEach(r => { ok(n + ' row<=3', r.length >= 1 && r.length <= 3, r); r.forEach(b => ok(n + ' cb ok ' + b.c, CB.test(b.c) && typeof b.t === 'string' && b.t.length > 0 && b.t.length <= 40, b)); }); };
// 1) /guide (نص) → قائمة المواضيع، إرسال جديد
let r = run(D.render, { ctx: 'C', chatId: 7, cmd: 'guide' })[0];
ok('menu send (not edit)', r.edit === false && r.chatId === 7 && r.ctx === 'C');
ok('menu has intro', /دليل الاستخدام/.test(r.text) && /ربط حساباتك/.test(r.text), r.text);
checkKb('menu', r.keyboard);
const topics = r.keyboard.filter(x => /^gd:[a-z]+:0$/.test(x[0].c)).map(x => x[0].c.split(':')[1]);
ok('6 topics', topics.length === 6 && ['s', 't', 'f', 'n', 'r', 'q'].every(k => topics.includes(k)), topics);
ok('menu has home', r.keyboard[r.keyboard.length - 1][0].c === 'h');
// 2) gd:m من زر → تعديل
r = run(D.render, { ctx: 'C', chatId: 7, cb: 'gd:m' })[0]; ok('menu via cb edits', r.edit === true && /اختار الموضوع/.test(r.text), r.text);
// 3) كل صفحات كل موضوع: ضمن حد تلغرام + حواف التنقل + ربط الصفحات
let total = 0;
for (const t of topics) {
  let n = 0, guard = 0;
  while (guard++ < 60) {
    const x = run(D.render, { ctx: 'C', chatId: 7, cb: 'gd:' + t + ':' + n })[0]; total++;
    ok(t + n + ' edit', x.edit === true);
    ok(t + n + ' len', x.text.length > 80 && x.text.length < 3500, x.text.length);
    checkKb(t + n, x.keyboard);
    const flat = x.keyboard.flat().map(b => b.c);
    ok(t + n + ' prev edge', (n === 0) === !flat.includes('gd:' + t + ':' + (n - 1)), flat);
    const nxt = flat.includes('gd:' + t + ':' + (n + 1));
    ok(t + n + ' header', new RegExp('صفحة ' + (n + 1) + ' من \\d+').test(x.text));
    ok(t + n + ' menu+home', flat.includes('gd:m') && flat.includes('h'));
    if (!nxt) { ok(t + ' last page reached', /من (\d+)/.exec(x.text)[1] === String(n + 1), x.text.slice(0, 60)); break; }
    n++;
  }
}
ok('visited all pages (>=30)', total >= 30, total);
// 4) مدخلات غير صالحة لا تكسر
r = run(D.render, { ctx: 'C', chatId: 7, cb: 'gd:t:999' })[0]; ok('page clamp high', /صفحة \d+ من \d+/.test(r.text) && !/NaN/.test(r.text), r.text.slice(0, 40));
r = run(D.render, { ctx: 'C', chatId: 7, cb: 'gd:t:-5' })[0]; ok('page clamp low → 1', /صفحة 1 من/.test(r.text));
r = run(D.render, { ctx: 'C', chatId: 7, cb: 'gd:zzz:1' })[0]; ok('unknown topic → menu', /دليل الاستخدام/.test(r.text));
r = run(D.render, { ctx: 'C', chatId: 7, cb: 'gd' })[0]; ok('bare gd → menu', /دليل الاستخدام/.test(r.text));
// 5) reply يمرّر الحقول
const rp = run(D.reply, {}, [{ ctx: 'C', chatId: 7, text: 'x', keyboard: [[{ t: 'a', c: 'h' }]], edit: true }])[0]; ok('reply passthrough', rp.ctx === 'C' && rp.edit === true && rp.keyboard.length === 1 && rp.text === 'x');
// 6) لا رموز تكسر تلغرام (بدون HTML/Markdown خام)
const all = []; topics.forEach(t => { for (let n = 0; n < 12; n++) { const x = run(D.render, { ctx: 'C', chatId: 7, cb: 'gd:' + t + ':' + n })[0]; all.push(x.text); } });
ok('no html tags / markdown fences', all.every(s => !/<\/?[a-z]/i.test(s) && !/```/.test(s)));
console.log(pass + ' pass, ' + fail + ' fail'); process.exit(fail ? 1 : 0);
