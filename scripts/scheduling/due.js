const B = new Date(Date.now() + 3 * 3600 * 1000);
const dateB = B.toISOString().slice(0, 10), hmB = B.toISOString().slice(11, 16);
const nowTs = Date.parse(dateB + 'T' + hmB + ':00Z');
const rows = $input.all().map(i => i.json).filter(r => r && r.sid && r.status === 'active');
const due = [], out = [];
for (const r of rows) {
  const t = String(r.time || '');
  if (!/^\d{2}:\d{2}$/.test(t)) continue;
  if (r.repeat === 'daily') {
    if (String(r.last_run_date) !== dateB && hmB >= t) due.push({ r, ts: Date.parse(dateB + 'T' + t + ':00Z') });
  } else {
    const d = String(r.run_date || '');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) continue;
    const ts = Date.parse(d + 'T' + t + ':00Z');
    if (ts > nowTs) continue;
    if (nowTs - ts > 12 * 3600000) out.push({ json: { ...r, api: 'skip', skipReason: 'expired' } });
    else due.push({ r, ts });
  }
}
const byC = {};
for (const x of due) (byC[x.r.campaign_id] = byC[x.r.campaign_id] || []).push(x);
for (const arr of Object.values(byC)) {
  arr.sort((a, b) => a.ts - b.ts);
  arr.forEach((x, i) => out.push({ json: { ...x.r, api: i === arr.length - 1 ? 'apply' : 'skip', skipReason: i === arr.length - 1 ? '' : 'superseded' } }));
}
return out;
