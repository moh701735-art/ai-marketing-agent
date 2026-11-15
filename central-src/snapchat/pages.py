# -*- coding: utf-8 -*-
"""سناب شات (قراءة فقط) — أوامر /snapaccounts و/snapreport بنفس نمط premium_features و smart_audience:
build(b, w, sw, idx, reply, CRT) يضيف عقد: SN: accounts → SN: plan → (halt?) → SN: call info+campaigns → SN: plan2 → (need stats?) → SN: call stats → SN: render → SN: reply.
كل القراءة عبر الـBroker (عمليات snapchat.* القراءة فقط). ما ينشئ ولا يعدّل ولا يوقف شي. مبالغ سناب بوحدات ميكرو (÷1,000,000)."""

SQL_ACC = ("SELECT external_id::text AS id, coalesce(name, '') AS name, coalesce(currency::text, '') AS cur "
           "FROM api.list_ad_accounts($1) WHERE platform = 'snapchat' AND enabled ORDER BY linked_at LIMIT 8")

JS_PLAN = r"""
const d = $('Route').first().json;
const cmd = String(d.cmd || '').toLowerCase();
const rep = /report/.test(cmd) || /تقرير/.test(String(d.args || ''));
const a = String(d.args || '').trim();
let days = 7; if (/^(today|اليوم)$/i.test(a)) days = 1; else { const m = /(\d{1,2})/.exec(a); if (m) days = Math.min(30, Math.max(1, parseInt(m[1], 10))); }
const rows = $input.all().map(i => i.json).filter(r => r && r.id);
if (!rows.length) return [{ json: { ctx: d.ctx, chatId: d.chatId, halt: true, text: '👻 ما عندك حساب سناب شات مربوط بالنظام.\nاطلب من الإدارة ربط حسابك الإعلاني بسناب.' } }];
const base = { ctx: d.ctx, chatId: d.chatId, platform: 'snapchat', ad_account: '', rep, days };
const items = [];
rows.forEach(r => {
  const label = r.name || String(r.id).slice(0, 8);
  items.push({ json: { ...base, kind: 'info', acct: String(r.id), label, cur: r.cur || '', op: 'snapchat.adaccount', params: { oid: String(r.id) } } });
  items.push({ json: { ...base, kind: 'camps', acct: String(r.id), label, cur: r.cur || '', op: 'snapchat.campaigns', params: { oid: String(r.id), limit: 50 } } });
});
return items;
"""

JS_PLAN2 = r"""
const P = $('SN: plan').all().map(i => i.json); const R = $input.all().map(i => i.json);
const base = P[0];
const accts = {}; const order = [];
P.forEach((p, i) => {
  const r = R[i] || {}; const a = accts[p.acct] || (accts[p.acct] = { id: p.acct, label: p.label, cur: p.cur, tz: '', status: '', camps: [], errs: [] }); if (order.indexOf(p.acct) < 0) order.push(p.acct);
  if (!r.ok) { a.errs.push((p.kind === 'info' ? 'بيانات الحساب' : 'الحملات') + ': ' + String((r.error && (r.error.message || r.error.class)) || 'ما كدرت أقرأها').slice(0, 140)); return; }
  const dd = r.data || {};
  if (p.kind === 'info') { const ad = (((dd.adaccounts || [])[0]) || {}).adaccount || {}; a.tz = ad.timezone || ''; a.status = ad.status || ''; if (ad.currency) a.cur = ad.currency; if (ad.name) a.label = ad.name; }
  else a.camps = (dd.campaigns || []).map(x => (x || {}).campaign || {}).filter(c => c.id).map(c => ({ id: String(c.id), name: String(c.name || c.id), status: String(c.status || '') }));
});
const tzOff = (tz, dt) => { try { const p = new Intl.DateTimeFormat('en-US', { timeZone: tz, timeZoneName: 'longOffset' }).formatToParts(dt).find(x => x.type === 'timeZoneName'); const m = /GMT([+-]\d{2}):?(\d{2})?/.exec(p.value); return m ? m[1] + ':' + (m[2] || '00') : '+00:00'; } catch (e) { return '+00:00'; } };
const midnight = (tz, off) => { const z = tz || 'UTC'; let ymd; try { ymd = new Intl.DateTimeFormat('en-CA', { timeZone: z }).format(new Date()); } catch (e) { ymd = new Date().toISOString().slice(0, 10); }
  const b = ymd.split('-').map(Number); const t = new Date(Date.UTC(b[0], b[1] - 1, b[2] + off, 12)); const day = t.toISOString().slice(0, 10); let o; try { o = tzOff(z, t); } catch (e) { o = '+00:00'; } return day + 'T00:00:00.000' + o; };
const stat = [];
if (base.rep) {
  order.forEach(id => { const a = accts[id]; const act = a.camps.filter(c => c.status === 'ACTIVE'), oth = a.camps.filter(c => c.status !== 'ACTIVE');
    a.shown = act.concat(oth).slice(0, 6); a.hidden = Math.max(0, a.camps.length - a.shown.length);
    const st = midnight(a.tz, -base.days), en = midnight(a.tz, 1);
    a.shown.forEach(c => stat.push({ json: { ctx: base.ctx, chatId: base.chatId, platform: 'snapchat', ad_account: '', kind: 'stat', acct: id, cid: c.id, op: 'snapchat.stats', params: { oid: c.id, start_time: st, end_time: en } } })); });
}
const out = { ctx: base.ctx, chatId: base.chatId, rep: !!base.rep, days: base.days, need: stat.length > 0, order, accts };
if (!stat.length) return [{ json: out }];
return stat.map(s => ({ json: { ...s.json, _carry: out } }));
"""

JS_RENDER = r"""
const P1 = $('SN: plan').all().map(i => i.json);
if (P1[0].halt) return [{ json: { ctx: P1[0].ctx, chatId: P1[0].chatId, text: P1[0].text } }];
const P2 = $('SN: plan2').all().map(i => i.json);
const O = P2[0]._carry || P2[0];
const R = O.need ? $input.all().map(i => i.json) : [];
const LINE = '━━━━━━━━━━━━━━';
const num = n => Number(n || 0).toLocaleString('en-US');
const money = (m, cur) => (Number(m || 0) / 1e6).toFixed(2) + ' ' + (cur || '');
const ST = { ACTIVE: '▶️ شغّالة', PAUSED: '⏸️ متوقفة' };
const stt = s => ST[s] || (s ? ('❔ ' + s) : '');
const L = [];
if (!O.rep) {
  L.push('👻 سناب شات — الحسابات الإعلانية'); L.push(LINE);
  O.order.forEach(id => { const a = O.accts[id];
    const act = a.camps.filter(c => c.status === 'ACTIVE').length;
    L.push('💼 ' + a.label + (a.cur ? ' (' + a.cur + ')' : '') + (a.status ? ' — ' + (a.status === 'ACTIVE' ? 'نشط ✅' : a.status) : ''));
    L.push('   📣 الحملات: ' + a.camps.length + ' | ▶️ شغّالة: ' + act + ' | ⏸️ غيرها: ' + (a.camps.length - act));
    a.camps.slice(0, 8).forEach(c => L.push('   • ' + c.name.slice(0, 40) + ' — ' + stt(c.status)));
    if (a.camps.length > 8) L.push('   … و' + (a.camps.length - 8) + ' حملة ثانية');
    a.errs.forEach(e => L.push('   ⚠️ ' + e));
    L.push(''); });
  L.push('للتقرير بالصرف والنتائج: /snapreport');
} else {
  L.push('👻 تقرير سناب شات — آخر ' + O.days + (O.days === 1 ? ' يوم' : ' أيام')); L.push(LINE);
  let k = 0;
  O.order.forEach(id => { const a = O.accts[id]; L.push('💼 ' + a.label + (a.cur ? ' (' + a.cur + ')' : '')); a.errs.forEach(e => L.push('   ⚠️ ' + e));
    if (!(a.shown || []).length && !a.errs.length) L.push('   ما عندك حملات بهذا الحساب.');
    (a.shown || []).forEach(c => { const r = R[k++] || {}; L.push('📣 ' + c.name.slice(0, 40) + ' — ' + stt(c.status));
      if (!r.ok) { L.push('   ⚠️ ما كدرت أقرأ الأرقام: ' + String((r.error && (r.error.message || r.error.class)) || '?').slice(0, 120)); return; }
      const ts = (((r.data || {}).total_stats || [])[0] || {}).total_stat || {}; const s = ts.stats || {};
      const sp = Number(s.spend || 0), im = Number(s.impressions || 0), sw = Number(s.swipes || 0);
      L.push('   💰 الصرف: ' + money(sp, a.cur)); L.push('   👁️ الظهور: ' + num(im)); L.push('   👆 السحبات (Swipes): ' + num(sw));
      if (sw > 0 && sp > 0) L.push('   💵 سعر السحبة: ' + money(sp / sw, a.cur));
      else if (sp > 0) L.push('   ⏳ صرف بدون سحبات لحد الآن');
      else if (im === 0) L.push('   ⏳ ما صار توزيع بهالفترة'); });
    if (a.hidden) L.push('   … و' + a.hidden + ' حملة ثانية ما انعرضت (الحد 6 لكل حساب)');
    L.push(''); });
  L.push('ملاحظة: سناب ما عنده «رسائل» مثل تيك توك وفيسبوك، فالحكم ناجحة/فاشلة غير متاح هنا بعد. الأرقام من سناب مباشرة وقد تتأخر شوي.');
}
return [{ json: { ctx: O.ctx, chatId: O.chatId, text: L.join('\n').slice(0, 3800) } }];
"""

JS_REPLY = r"""
const r = $input.first().json;
return [{ json: { ctx: r.ctx, chatId: r.chatId, text: r.text, edit: false } }];
"""


def build(b, w, sw, idx, reply, CRT):
    code, pg, call_broker = b.code, b.pg, b.call_broker
    acc = pg(w, "SN: accounts", SQL_ACC, "={{ [$('Route').first().json.ctx] }}", CRT, always=True)
    w.nodes[-1]["onError"] = "continueRegularOutput"
    plan = code(w, "SN: plan", JS_PLAN)
    halt = w.add("SN: halt?", "n8n-nodes-base.switch", 3.5, {"mode": "expression", "numberOutputs": 2, "output": "={{ $json.halt ? 0 : 1 }}"})
    call1 = call_broker(w, "SN: read accounts+campaigns", mode="each")
    plan2 = code(w, "SN: plan2", JS_PLAN2)
    need = w.add("SN: need stats?", "n8n-nodes-base.switch", 3.5, {"mode": "expression", "numberOutputs": 2, "output": "={{ $json.need ? 1 : 0 }}"})
    call2 = call_broker(w, "SN: read stats", mode="each")
    render = code(w, "SN: render", JS_RENDER)
    out = reply("SN: reply", JS_REPLY)
    w.chain(acc, plan, halt)
    w.link(halt, render, 0)
    w.link(halt, call1, 1)
    w.chain(call1, plan2, need)
    w.link(need, render, 0)
    w.link(need, call2, 1)
    w.chain(call2, render)
    w.chain(render, out)
    w.link(sw, acc, idx)
