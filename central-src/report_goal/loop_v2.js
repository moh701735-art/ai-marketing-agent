for (const g of Object.values(groups)) {   // p229+p269b: تقرير الحملات الشغالة (الصرف الكلي + تجميع حسب الحساب + تسمية النتيجة حسب هدف التحسين)
  const N = v => { const x = Number(v); return isFinite(x) ? x : 0; };
  const capv = (typeof CAP === 'number') ? CAP : 0.40;
  const OFFRE = /DISABLE|PAUSE|DELETE|BUDGET_EXCEED|TIME_DONE|NOT_START|NOT_ENOUGH|AUDIT_DENY|BALANCE/i;
  const isOff = k => OFFRE.test(String(k.status || '')) || OFFRE.test(String(k.sec_status || ''));
  const stopped = g.camps.filter(isOff);
  g.camps = g.camps.filter(k => !isOff(k));
  const money = (k, v) => k.currency === 'IQD' ? Math.round(N(v)).toLocaleString('en-US') + ' د.ع' : '$' + (Math.round(N(v) * 100) / 100).toFixed(2);
  const num = v => Math.round(N(v)).toLocaleString('en-US');
  const small = (k, d) => k.currency === 'IQD' ? Math.abs(d) < 1 : Math.abs(d) < 0.01;
  const dtxt = (k, d) => (d === null || d === undefined || small(k, d)) ? '' : ' (' + (d > 0 ? '+' : '-') + money(k, Math.abs(d)) + ' آخر ساعة)';
  const GL = k => String(k.goal || '').split(',').filter(Boolean);
  const kind = k => { const g = GL(k); if (!g.length) return 'UNK'; if (g.every(x => x === 'CONVERSATION')) return 'CONV'; if (g.every(x => x === 'CLICK')) return 'CLICK'; if (g.every(x => x === 'CONVERT' || x === 'SHOP')) return 'CONVERT'; return 'OTHER'; };
  const LBL = { CONV: ['💬 محادثات اليوم', 'سعر المحادثة'], CLICK: ['🖱 نقرات اليوم (ليست محادثات)', 'سعر النقرة'], CONVERT: ['🎯 تحويلات اليوم (حدث تيك توك، ليست محادثات)', 'سعر التحويل'], OTHER: ['📊 نتائج اليوم (ليست محادثات)', 'سعر النتيجة'], UNK: ['📊 نتائج تيك توك اليوم (النوع غير معروف)', 'سعر النتيجة'] };
  const sumR = (list, conv) => list.reduce((s, c) => s + ((kind(c.k) === 'CONV') === conv ? N(c.k.results) : 0), 0);
  const resTxt = list => '💬 محادثات اليوم ' + sumR(list, true) + (sumR(list, false) ? ' | 📊 نتائج أخرى (ليست محادثات) ' + sumR(list, false) : '');
  const vrd = k => {
    const r = N(k.results), su = N(k.spend_usd); const cpr = r > 0 ? su / r : null;
    if (r === 0) return su >= 1.93 ? ['❌', 'فاشلة'] : ['⏳', 'جمع بيانات'];
    if (kind(k) !== 'CONV' && kind(k) !== 'UNK') return ['➖', 'ليست محادثات'];
    if (r < 2 && su < 1.93) return ['⏳', 'جمع بيانات'];
    if (cpr <= capv) return ['✅', 'ناجحة'];
    return cpr <= 0.60 ? ['⚠️', 'ضعيفة'] : ['❌', 'فاشلة'];
  };
  const RANK = { '✅': 0, '⚠️': 1, '⏳': 2, '➖': 2, '❌': 3 };
  const cards = g.camps.map(k => {
    const key = g.chatId + '|' + k.campaign_id;
    const lifeOk = k.spend_life_local !== null && k.spend_life_local !== undefined;
    const life = lifeOk ? N(k.spend_life_local) : N(k.spend_local);
    const lifeUsd = (k.spend_life_usd !== null && k.spend_life_usd !== undefined) ? N(k.spend_life_usd) : N(k.spend_usd);
    const today = N(k.spend_local);
    const prevL = sd.snap[key + '|L'], prev = sd.snap[key];
    const dS = (prevL && lifeOk) ? life - N(prevL.sp) : null;
    const dM = prev ? N(k.results) - N(prev.m) : null;
    sd.snap[key + '|L'] = { sp: life }; sd.snap[key] = { sp: today, m: N(k.results) };
    const v = vrd(k); const ctr = N(k.impressions) > 0 ? N(k.clicks) / N(k.impressions) * 100 : 0;
    const cprL = N(k.results) > 0 ? (k.cost_per_result_local !== null && k.cost_per_result_local !== undefined ? N(k.cost_per_result_local) : today / N(k.results)) : null;
    const L = [];
    L.push(v[0] + ' ' + String(k.name || k.campaign_id).slice(0, 40) + ' — ' + v[1]);
    L.push('💰 الصرف الكلي: ' + money(k, life) + (lifeOk ? '' : ' (اليوم فقط، الكلي غير متوفر)') + dtxt(k, dS));
    L.push('📅 صرف اليوم: ' + money(k, today));
    const lb = LBL[kind(k)];
    L.push(lb[0] + ': ' + num(k.results) + (dM ? ' (' + (dM > 0 ? '+' : '') + dM + ')' : '') + (cprL !== null ? ' | ' + lb[1] + ' ' + money(k, cprL) : ''));
    L.push((N(k.reach) ? '👁 وصول ' + num(k.reach) + ' | ' : '') + 'CTR ' + ctr.toFixed(2) + '%');
    if (v[0] === '❌') L.push('↪ أقترح توقفها: /pause_' + k.campaign_id); else if (v[0] === '✅') L.push('↪ ناجحة، تكدر تكرّرها: /duplicate_' + k.campaign_id);
    return { k, v, life, lifeUsd, text: L.join('\n') };
  });
  cards.sort((a, b) => (RANK[a.v[0]] - RANK[b.v[0]]) || (b.life - a.life));
  const byAcc = {}; const order = [];
  for (const c of cards) { const a = c.k.account_name || c.k.ad_account || ''; if (!byAcc[a]) { byAcc[a] = []; order.push(a); } byAcc[a].push(c); }
  const totUsd = cards.reduce((a, c) => a + c.lifeUsd, 0);
  const stamp = new Date(Date.now() + 3 * 3600000).toISOString().slice(11, 16);
  const blocks = [];
  if (cards.length) {
    blocks.push('📊 الحملات الشغالة الحين (' + cards.length + ') — ' + stamp + '\n💰 الصرف الكلي ≈ $' + (Math.round(totUsd * 100) / 100).toFixed(2) + ' | ' + resTxt(cards));
    for (const a of order) {
      const list = byAcc[a]; const sub = list.reduce((s, c) => s + c.life, 0);
      blocks.push('━━━━━━━━━━━━━━━\n👤 ' + (a || 'حساب') + ' — ' + list.length + ' حملة | الصرف الكلي ' + money(list[0].k, sub) + ' | ' + resTxt(list) + '\n━━━━━━━━━━━━━━━');
      for (const c of list) blocks.push(c.text);
    }
  } else if (!(g.fb && g.fb.length) && !g.meta.length) {
    blocks.push('📊 ما في حملات شغالة حالياً.');
  }
  const tail = [];
  if (stopped.length) tail.push('⏸ ' + stopped.length + ' حملة متوقفة أو منتهية (ما انعرضت)');
  if (g.fb && g.fb.length) { const f = g.fb.sort((a, b) => b.sp - a.sp); tail.push(f.slice(0, 12).map(x => x.t).join('\n\n') + (f.length > 12 ? '\n\n… و' + (f.length - 12) + ' حملة ثانية' : '')); }
  if (g.meta.length) tail.push(g.meta.join('\n'));
  if (g.bad.length) tail.push(g.bad.join('\n'));
  if (g.failed) tail.push('⚠️ ' + g.failed + ' حساب ما جاوبوا');
  const msgs = []; let cur = '';
  for (const b of blocks) { if (cur && (cur + '\n\n' + b).length > 3500) { msgs.push(cur); cur = b; } else cur += (cur ? '\n\n' : '') + b; }
  if (tail.length) { const t = tail.join('\n\n'); if (cur && (cur + '\n\n' + t).length > 3800) { msgs.push(cur); cur = t; } else cur += (cur ? '\n\n' : '') + t; }
  if (cur) msgs.push(cur);
  for (const text of msgs) out.push({ json: { ctx: g.ctx, chatId: g.chatId, platform: 'telegram', op: 'telegram.send_message', ad_account: g.chatId, params: { text: text.slice(0, 3900) } } });
}
