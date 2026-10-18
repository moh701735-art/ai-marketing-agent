const BOTS = __BOTS__;
const sd = $getWorkflowStaticData('global');
const now = Date.now();
const bagh = new Date(now + 3 * 3600 * 1000);
const lines = [], bad = [];
for (const b of BOTS) {
  const rows = $(b.n + ': العملاء').all().map(x => x.json || {}).filter(r => r.tiktok_advertiser_id);
  const tt = $(b.n + ': تيك توك').first().json || {};
  let ttOk = false, ttMsg = '';
  if (!rows.length) ttMsg = 'ماكو حسابات تيك توك بجدول العملاء';
  else if (tt.error) ttMsg = 'فشل الاتصال: ' + String(tt.error.message || tt.error.description || '').slice(0, 80);
  else if (tt.code !== 0) {
    const m = String(tt.message || '');
    const np = m.match(/No permission to operate advertiser:\s*([0-9,\s]+)/);
    const gone = m.match(/The advertiser (\d+) doesn't exist/);
    const nameOf = id => { const r = rows.find(x => String(x.tiktok_advertiser_id) === id); return (r && r.client) || id; };
    if (np) { const ids = np[1].split(',').map(x => x.trim()).filter(Boolean); ttMsg = 'التوكن شغال لكن ' + ids.length + ' حساب بالجدول بدون صلاحية (' + ids.slice(0, 3).map(nameOf).join('، ') + (ids.length > 3 ? '…' : '') + ') — احذفها من جدول العملاء أو اربطها'; }
    else if (gone) { ttMsg = 'حساب محذوف بتيك توك: ' + nameOf(gone[1]) + ' — احذفه من جدول العملاء'; }
    else ttMsg = 'التوكن مرفوض: ' + m.slice(0, 80);
  }
  else {
    const list = (tt.data && tt.data.list) || [];
    const ids = new Set(list.map(a => String(a.advertiser_id)));
    const missing = rows.filter(r => !ids.has(String(r.tiktok_advertiser_id)));
    const off = list.filter(a => a.status && a.status !== 'STATUS_ENABLE');
    ttOk = !missing.length && !off.length;
    ttMsg = list.length + ' حساب' + (missing.length ? ' | ' + missing.length + ' ما ظهر بالتوكن (' + missing.slice(0, 3).map(r => r.client || r.tiktok_advertiser_id).join('، ') + (missing.length > 3 ? '…' : '') + ')' : '') + (off.length ? ' | ' + off.length + ' مو فعّال (' + off.slice(0, 3).map(a => a.name || a.advertiser_id).join('، ') + ')' : '');
  }
  const me = $(b.n + ': ميتا').first().json || {};
  const fbOk = !!me.id && !me.error;
  const fbMsg = fbOk ? 'سليم' : String((me.error && (me.error.message || me.error.description)) || 'ما رجع رد').slice(0, 90);
  let tgOk = true, tgMsg = '';
  if (b.tg) {
    const tg = $(b.n + ': تيليجرام').first().json || {};
    tgOk = !tg.error && Object.keys(tg).length > 0;
    tgMsg = tgOk ? 'سليم' : String((tg.error && (tg.error.message || tg.error.description)) || 'ما رجع رد').slice(0, 90);
  } else { tgMsg = 'ما انفحص'; }
  const ok = ttOk && fbOk && tgOk;
  lines.push((ok ? '✅ ' : '⚠️ ') + b.n + '\n   تيك توك: ' + (ttOk ? '✓ ' : '❌ ') + ttMsg + '\n   ميتا: ' + (fbOk ? '✓' : '❌ ' + fbMsg) + '\n   تيليجرام: ' + (b.tg ? (tgOk ? '✓' : '❌ ' + tgMsg) : '—'));
  if (!ok) bad.push(lines[lines.length - 1]);
}
const sig = bad.map(x => x.replace(/\d+ حساب/g, '')).join('|');
const day = bagh.toISOString().slice(0, 10);
const stamp = day + ' ' + String(bagh.getUTCHours()).padStart(2, '0') + ':00';
let text = '';
if (bagh.getUTCHours() === 8 && sd.boardDay !== day) {
  sd.boardDay = day;
  text = '🩺 لوحة صحة البوتات — ' + stamp + '\n\n' + lines.join('\n\n') + '\n\n(المشكلة الثابتة تنرسل مرة وحدة بس وتتذكر باللوحة الصباحية. الأعطال أثناء التشغيل توصلك من تنبيه الأعطال)';
  sd.sig = sig; sd.sigAt = now;
} else if (bad.length && sig !== sd.sig) {
  sd.sig = sig; sd.sigAt = now;
  text = '🚨 مشاكل بالبوتات — ' + stamp + '\n\n' + bad.join('\n\n');
} else if (!bad.length && sd.sig) {
  sd.sig = ''; sd.sigAt = 0;
  text = '✅ رجعت كل البوتات سليمة — ' + stamp;
}
return text ? [{ json: { text } }] : [];
