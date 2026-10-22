const B = new Date(Date.now() + 3 * 3600 * 1000);
const dateB = B.toISOString().slice(0, 10), hmB = B.toISOString().slice(11, 16);
const addDays = (d, n) => new Date(Date.parse(d + 'T00:00:00Z') + n * 86400000).toISOString().slice(0, 10);
const t12 = (hm) => { const p = String(hm).split(':').map(Number); const h = p[0], m = p[1]; return (h % 12 || 12) + ':' + String(m).padStart(2, '0') + ' ' + (h < 12 ? 'ص' : 'م'); };
const normT = (v) => { const m = String(v || '').trim().match(/^([01]?\d|2[0-3]):([0-5]\d)$/); return m ? String(m[1]).padStart(2, '0') + ':' + m[2] : ''; };
function buildEvents(sch) {
  const evs = [];
  for (const s of (Array.isArray(sch) ? sch : [])) {
    if (!s) continue;
    const action = (s.action === 'on' || s.action === 'off') ? s.action : '';
    if (!action) continue;
    const isNow = String(s.time || '').trim() === 'now';
    let time = isNow ? hmB : normT(s.time);
    if (!time) continue;
    if (s.repeat === 'daily' && !isNow) {
      evs.push({ action, repeat: 'daily', time, run_date: '', last_run_date: time <= hmB ? dateB : '' });
    } else {
      let d;
      const day = String(s.day || '').trim();
      if (isNow) d = dateB;
      else if (/^\d{4}-\d{2}-\d{2}$/.test(day)) d = day;
      else if (day === 'tomorrow') d = addDays(dateB, 1);
      else d = time >= hmB ? dateB : addDays(dateB, 1);
      evs.push({ action, repeat: 'once', time, run_date: d, last_run_date: '' });
    }
  }
  const don = evs.find(e => e.repeat === 'daily' && e.action === 'on'), doff = evs.find(e => e.repeat === 'daily' && e.action === 'off');
  let enforce = '';
  if (don && doff) {
    const inW = don.time < doff.time ? (hmB >= don.time && hmB < doff.time) : (hmB >= don.time || hmB < doff.time);
    enforce = inW ? 'on' : 'off';
    evs.push({ action: enforce, repeat: 'once', time: hmB, run_date: dateB, last_run_date: '' });
  }
  return { evs, enforce };
}
function describe(evs, enforce) {
  const dayWord = (d) => d === dateB ? 'اليوم' : (d === addDays(dateB, 1) ? 'باجر' : d);
  return evs.map(e => {
    const w = e.action === 'on' ? '▶️ تشغيل' : '⏸️ إيقاف';
    if (e.repeat === 'daily') return w + ' — كل يوم الساعة ' + t12(e.time);
    if (enforce && e.time === hmB && e.run_date === dateB && e.action === enforce) return (e.action === 'on' ? '▶️ تشغيل' : '⏸️ إيقاف') + ' — هسه (لأن الوقت الحالي ' + (e.action === 'on' ? 'داخل' : 'خارج') + ' الفترة المحددة)';
    if (e.time === hmB && e.run_date === dateB) return w + ' — هسه';
    return w + ' — ' + dayWord(e.run_date) + ' الساعة ' + t12(e.time);
  });
}
const mkRow = (e, base) => ({ kind: 'row', sid: 'S' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6), phone: base.phone, client: base.client || '', platform: base.platform, advertiser_id: base.advertiser_id || '', campaign_id: String(base.campaign_id), campaign_name: base.campaign_name || '', action: e.action, repeat: e.repeat, time: e.time, run_date: e.run_date || '', last_run_date: e.last_run_date || '', status: 'active', last_result: '', created_at: new Date().toISOString() });
