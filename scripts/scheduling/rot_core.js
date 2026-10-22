const inp = $input.first().json;
const BR = ['25-34', '35-44', '18-24', '45-65'];
const rotBase = (n) => String(n || '').replace(/\s*-\s*جمهور\s*\d+$/, '');
function rotCopy() {
  const out = [];
  (inp.dec || []).forEach((d, i) => {
    const rot = d.rot || {};
    if (!rot.on || d.stop === false) return;
    const st = (inp.stops || [])[i] || {};
    if (st.success !== true) return;
    const gen = Number(rot.gen) || 1, max = Number(rot.max) || 3;
    const c = { campaign_id: String(d.campaign_id), name: d.campaign_name || '', gen, max, root: rot.root || String(d.campaign_id), used: rot.used || [], acct: d.account_id || rot.acct || '', limit: d.limit, cpr: d.cpr, msgs: d.msgs, spend: d.spend };
    if (gen >= max) out.push({ kind: 'msg', text: '🔚 حملة "' + c.name + '" تعدّت سقف ' + Math.round(c.limit * 100) + ' سنت (سعر الرسالة ' + Math.round(c.cpr * 100) + ' سنت) وانطفت.\nوصلت آخر حملة بالسلسلة (' + gen + ' من ' + max + ') فما رفعت بديلة. شوف الجمهور/الإعلان وقرر.' });
    else out.push({ ...c, kind: 'copy' });
  });
  return out;
}
function rotTarget() {
  const out = [];
  (inp.ctx || []).forEach((c, i) => {
    const cp = (inp.copies || [])[i] || {}, ad = (inp.adsets || [])[i] || {};
    const nid = String(cp.copied_campaign_id || ((cp.ad_object_ids || []).find(x => x.ad_object_type === 'campaign') || {}).copied_id || '');
    if (!nid) { out.push({ kind: 'msg', text: '❌ توقفت حملة "' + c.name + '" بس فشل نسخها للجمهور البديل: ' + String((cp.error && cp.error.message) || 'سبب غير معروف').slice(0, 200) }); return; }
    const sets = Array.isArray(ad.data) ? ad.data : [];
    if (!sets.length) { out.push({ kind: 'msg', text: '⚠️ نسخت حملة "' + c.name + '" (' + nid + ') بس ما لكيت مجموعات إعلانية بيها، تركتها متوقفة. راجعها بمدير الإعلانات.' }); return; }
    const t0 = sets[0].targeting || {};
    const src = (t0.age_min || 18) + '-' + (t0.age_max || 65);
    const used = [...new Set([...(c.used || []), src])];
    const br = BR.find(b => !used.includes(b));
    if (!br) { out.push({ kind: 'msg', text: '⚠️ ما بقت فئة عمرية جديدة لحملة "' + c.name + '"، تركت النسخة (' + nid + ') متوقفة.' }); return; }
    const [mn, mx] = br.split('-').map(Number);
    sets.forEach(s => {
      const t = { ...(s.targeting || {}) };
      t.age_min = mn; t.age_max = mx; delete t.age_range;
      t.targeting_automation = { ...(t.targeting_automation || {}), advantage_audience: 0 };
      out.push({ ...c, kind: 'upd', adset_id: s.id, targeting: t, new_id: nid, bracket: br, used: [...used, br] });
    });
  });
  return out;
}
function rotCheck() {
  const g = {};
  (inp.ctx || []).forEach((c, i) => {
    const r = (inp.res || [])[i] || {};
    const x = g[c.new_id] || (g[c.new_id] = { ...c, kind: 'act', ok: true, err: '' });
    if (r.success !== true) { x.ok = false; x.err = String((r.error && r.error.message) || 'فشل تعديل الاستهداف').slice(0, 200); }
  });
  return Object.values(g).map(x => { const { adset_id, targeting, ...rest } = x; return rest; });
}
function rotFinal() {
  const out = [];
  (inp.ctx || []).forEach((c, i) => {
    const r = (inp.res || [])[i] || {};
    const act = c.ok && r.success === true;
    const base = rotBase(c.name);
    if (!act) { out.push({ kind: 'msg', text: '⚠️ توقفت حملة "' + c.name + '" وسويت نسخة بديلة (' + c.new_id + ') بس ما كملت تفعيلها: ' + (c.err || String((r.error && r.error.message) || '')) + '\nالنسخة متوقفة، راجعها بمدير الإعلانات.' }); return; }
    const cap = String(c.limit);
    out.push({ kind: 'row', row: { campaign_id: c.new_id, name: base + ' - جمهور ' + (c.gen + 1), cap_usd: cap, auto_stop: '1', stopped_at: '', warned_at: '', rot: JSON.stringify({ on: 1, gen: c.gen + 1, max: c.max, root: c.root, used: c.used, acct: c.acct }) } });
    out.push({ kind: 'row', row: { campaign_id: c.campaign_id, name: c.name, cap_usd: cap, auto_stop: '1', stopped_at: new Date().toISOString(), warned_at: '', rot: JSON.stringify({ on: 1, gen: c.gen, max: c.max, root: c.root, used: c.used, acct: c.acct, next: c.new_id }) } });
    out.push({ kind: 'msg', text: '🔄 حملة "' + c.name + '": سعر الرسالة ' + Math.round(c.cpr * 100) + ' سنت (السقف ' + Math.round(c.limit * 100) + ') بعد ' + c.msgs + ' رسالة وصرف $' + Number(c.spend).toFixed(2) + ' — انطفت.\n✅ رفعت حملة بديلة "' + base + ' - جمهور ' + (c.gen + 1) + '" بجمهور أعمار ' + c.bracket + ' (الحملة ' + (c.gen + 1) + ' من ' + c.max + '). نفس السقف، وإذا تعدّته أبدّل الجمهور مرة ثانية.' });
  });
  return out;
}
const out = ({ rotCopy, rotTarget, rotCheck, rotFinal }[inp.mode] || (() => []))();
return out.map(json => ({ json }));
