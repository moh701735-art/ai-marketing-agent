const B = new Date(Date.now() + 3 * 3600 * 1000);
const dateB = B.toISOString().slice(0, 10), hmB = B.toISOString().slice(11, 16);
const t12 = (hm) => { const p = String(hm).split(':').map(Number); return (p[0] % 12 || 12) + ':' + String(p[1]).padStart(2, '0') + ' ' + (p[0] < 12 ? 'ص' : 'م'); };
const src = __SRC__;
const out = [];
$input.all().forEach((it, i) => {
  const pi = it.pairedItem;
  const k = (pi && typeof pi.item === 'number') ? pi.item : i;
  const r = src ? ((src[k] && src[k].json) || {}) : (it.json || {});
  const j = src ? (it.json || {}) : {};
  let ok, msg = '';
  if (r.api === 'skip') { ok = true; }
  else if (r.platform === 'tiktok') { ok = j.code === 0 && !j.error; msg = String(j.message || (typeof j.error === 'string' ? j.error : (j.error && j.error.message)) || ''); }
  else { ok = !j.error && (j.success === true || j.id != null); msg = String((j.error && (j.error.message || j.error.error_user_msg)) || ''); }
  const fails = Number((String(r.last_result || '').match(/^FAIL (\d)/) || [])[1]) || 0;
  let status = r.status, last_run_date = r.last_run_date, last_result, notify = false, finalMessage = '';
  const label = '"' + (r.campaign_name || r.campaign_id) + '" (' + (r.platform === 'tiktok' ? 'تيك توك' : 'فيسبوك') + ')';
  if (r.api === 'skip') {
    last_result = (r.skipReason === 'expired' ? 'EXPIRED ' : 'SUPERSEDED ') + dateB + ' ' + hmB;
    if (r.repeat === 'daily') last_run_date = dateB; else status = 'done';
  } else if (ok) {
    last_result = 'OK ' + dateB + ' ' + hmB;
    if (r.repeat === 'daily') last_run_date = dateB; else status = 'done';
    notify = true;
    finalMessage = '⏰ حسب الجدولة: ' + (r.action === 'on' ? '▶️ شغّلت' : '⏸️ وقفت') + ' حملة ' + label + ' الساعة ' + t12(hmB) + '.';
  } else {
    const n = fails + 1;
    last_result = 'FAIL ' + n + ': ' + msg.slice(0, 150);
    if (n >= 3) { if (r.repeat === 'daily') { last_run_date = dateB; last_result = 'FAIL 0 (gave up ' + dateB + '): ' + msg.slice(0, 120); } else status = 'failed'; }
    if (n === 1 || n >= 3) { notify = true; finalMessage = '⚠️ فشل تنفيذ الجدولة (' + (r.action === 'on' ? 'تشغيل' : 'إيقاف') + ' حملة ' + label + '): ' + msg.slice(0, 200) + (n >= 3 ? '\nوقفت المحاولات لهذا الموعد.' : '\nراح أعيد المحاولة بعد 5 دقائق.'); }
  }
  out.push({ json: { sid: r.sid, phone: r.phone, client: r.client, platform: r.platform, advertiser_id: r.advertiser_id, campaign_id: r.campaign_id, campaign_name: r.campaign_name, action: r.action, repeat: r.repeat, time: r.time, run_date: r.run_date, last_run_date, status, last_result, created_at: r.created_at, notify, finalMessage } });
});
return out;
