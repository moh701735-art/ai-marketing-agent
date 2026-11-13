// يشغّل عقد SA: plan / SA: render الحقيقية (من pages.py عبر dump.py) على بيانات اختبار. لا شبكة ولا n8n.
const fs = require('fs'); const D = JSON.parse(fs.readFileSync(process.env.SA_NODES || '/tmp/sa_nodes.json', 'utf8'));
const J = a => a.map(x => ({ json: x }));
function run(code, route, inputs, plan) {
  const $ = n => { if (n === 'Route') return { first: () => ({ json: route }) }; if (n === 'SA: plan') return { all: () => J(plan), first: () => ({ json: plan[0] }) }; throw new Error('node ' + n); };
  return new Function('$', '$input', code)($, { all: () => J(inputs), first: () => ({ json: inputs[0] }) }).map(x => x.json);
}
const PLAN = (route, rows) => run(D.plan, route, rows);
// results: دالة (plans) => نتائج Broker بنفس ترتيب العناصر
const RENDER = (route, rows, results) => { const plans = PLAN(route, rows); const out = run(D.render, route, plans[0].need ? results(plans) : [], plans); return { plans, out: out[0] }; };
// عقدة الرد: render = ناتج SA: render ، saveRes = ناتج عقدة الحفظ (فيه wr)
const REPLY = (render, saveRes) => new Function('$', D.reply)(n => { if (n === 'SA: render') return { first: () => ({ json: render }) }; if (n === 'SA: save state + cache') return { first: () => ({ json: saveRes }) }; throw new Error('node ' + n); })[0].json;
module.exports = { PLAN, RENDER, REPLY, D };
