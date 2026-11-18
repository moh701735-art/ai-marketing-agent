// p213: جمهور محفوظ بالاسم في الطلب النصي (تيك توك). يُحقن داخل عقدة "AI: plan" بعد تعريف wantInt.
let SVA = null;
{
  const SVL = (() => { try { const r = $('AI: saved audiences').first().json; return JSON.parse((r && r.sv) || '[]'); } catch (e) { return []; } })()
    .filter(x => x && x.nm && Array.isArray(x.iv) && x.iv.length);
  const rawT = (typeof d !== 'undefined' && d && d.text) ? String(d.text) : String(ntx || '');
  const nz = s => String(s || '').replace(/[ً-ْـ]/g, '').replace(/[أإآ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي').replace(/[٠-٩]/g, c => String(c.charCodeAt(0) - 1632)).toLowerCase().replace(/[،,.؟?!:："'«»()]/g, ' ').replace(/\s+/g, ' ').trim();
  const NUMW = [['واحد', '1'], ['واحده', '1'], ['وحده', '1'], ['اثنين', '2'], ['اثنان', '2'], ['ثنين', '2'], ['ثلاثه', '3'], ['ثلاث', '3'], ['اربعه', '4'], ['اربع', '4'], ['خمسه', '5'], ['خمس', '5'], ['سته', '6'], ['ست', '6'], ['سبعه', '7'], ['سبع', '7'], ['ثمانيه', '8'], ['ثمان', '8'], ['تسعه', '9'], ['تسع', '9'], ['عشره', '10'], ['عشر', '10']];
  const nn = s => { let t = ' ' + nz(s) + ' '; NUMW.forEach(p => { t = t.split(' ' + p[0] + ' ').join(' ' + p[1] + ' '); }); return t.replace(/\s+/g, ' ').trim(); };
  const TRIG = /(?:^|[\s\n])(?:(?:اختار|اختر|استخدم|استعمل|خذ|حط|ضيف)\s+(?:ب)?(?:ال)?جمهور(?:\s+(?:ال)?محفوظ)?|(?:ب)?(?:ال)?جمهور\s+(?:ال)?محفوظ|(?:ب|ال)?جمهور\s*[:：])\s*[:：]?\s*([^\n]{1,80})/;
  const m0 = TRIG.exec(rawT.replace(/[ \t]+/g, ' '));
  if (m0 && SVL.length) {
    const words = nz(m0[1]).split(' ').filter(Boolean).slice(0, 6);
    const hit = [];
    for (let k = Math.min(words.length, 6); k >= 1 && !hit.length; k--) {
      const part = words.slice(0, k).join(' '), qa = nn(part), qb = nn('جمهور ' + part);
      const exact = SVL.filter(x => nn(x.nm) === qa || nn(x.nm) === qb);
      if (exact.length === 1) { hit.push(exact[0]); break; }
      if (exact.length > 1) { hit.push(null); break; }
    }
    if (!hit.length) {
      const q = nn(words.slice(0, 3).join(' ')); const part = (q && q.length >= 3) ? SVL.filter(x => nn(x.nm).includes(q)) : [];
      if (part.length === 1) hit.push(part[0]); else if (part.length > 1) hit.push(null);
    }
    const x = hit.length ? hit[0] : undefined;
    if (!x) {
      const lst = SVL.slice(0, 8).map((v, i) => (i + 1) + '. ' + String(v.nm).slice(0, 30) + ' (' + v.iv.length + ' اهتمام)').join('\n');
      return say('⚠️ طلبت جمهور محفوظ بس ما قدرت أحدد أي واحد' + (hit.length ? ' (أكثر من جمهور يطابق الاسم)' : ' (ما لقيت جمهور بهالاسم)') + ' «' + words.join(' ').slice(0, 40) + '».\nجماهيرك المحفوظة:\n' + lst + '\n\nما أنشأت أي حملة. أعد الطلب واكتب اسم الجمهور مثل ما هو: «اختار جمهور <الاسم>».');
    }
    const ids = x.iv.map(a => String(a[0])).filter(id => /^\d{3,25}$/.test(id)).slice(0, 50);
    if (!ids.length) return say('⚠️ الجمهور المحفوظ «' + String(x.nm).slice(0, 30) + '» ما فيه اهتمامات صالحة. ما أنشأت أي حملة. افتح 🎯 منشئ الجمهور وأعد حفظه.');
    SVA = { ids, names: x.iv.map(a => String(a[1] || a[0]).slice(0, 40)).slice(0, 8), nm: String(x.nm).slice(0, 30) };
  }
}
