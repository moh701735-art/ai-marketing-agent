// p230: نافذة جدولة التيك توك (p230c: كلمة اليوم تنربط بالساعة اللي جنبها؛ للإيقاف يوم خاص؛ p230d: بدون فعل بداية + كلمة حملة) «روّج الساعة 22:00 وقف 10:00» (بغداد UTC+3 → UTC). صيغة غير مفهومة أو غامضة = توقف قبل أي حملة.
{
  const BG = 3 * 3600000, LET = '\\u0621-\\u064A';
  const s = String(d.text || '').replace(/[\u0660-\u0669]/g, c => String(c.charCodeAt(0) - 1632)).replace(/[\u064B-\u065F\u0640]/g, '').replace(/[أإآ]/g, 'ا').replace(/ى/g, 'ي').replace(/ة/g, 'ه').toLowerCase();
  const L1 = '(?<![' + LET + '])', L2 = '(?![' + LET + '])';
  const MKW = 'صباحا|صباح|صبح|الصبح|فجرا|فجر|مساءا|مساء|المساء|ليلا|ليل|الليل|عصرا|عصر|العصر|ظهرا|ظهر|الظهر';
  const TOK = new RegExp('^\\s*(?:(?:لها|ها|عند|في|من|ب|حمله|الحمله|اعلان|الاعلان|هاي|هذي|هذه|بعد\\s*بكر[هاة]|بعد\\s*يومين|بكر[هاة]|غدا|باجر|ثاني\\s*يوم|اليوم\\s*الثاني|اليوم)\\s*)*(?:(?:ب?الساعه|ساعه)\\s*(\\d{1,2})(?::(\\d{2}))?|(\\d{1,2}):(\\d{2})|(\\d{1,2})(?=\\s*ب?(?:' + MKW + ')' + L2 + '))(?:\\s*ب?(' + MKW + ')' + L2 + ')?');
  const DAYS = (t) => {   // p230c: كلمة يوم قرب الساعة → {abs: يوم من اليوم} أو {rel: يوم من يوم البداية}
    if (new RegExp(L1 + 'بعد\\s*(?:بكر[هاة]|غد)' + L2).test(t)) return { abs: 2 };
    if (new RegExp(L1 + 'بعد\\s*يومين' + L2).test(t)) return { rel: 2 };
    if (/ثاني\s*يوم|اليوم\s*الثاني|يوم\s*بعده/.test(t)) return { rel: 1 };
    if (new RegExp(L1 + '(?:بكر[هاة]|غدا|باجر)' + L2).test(t)) return { abs: 1 };
    if (new RegExp(L1 + '(?:هاليوم|اليوم|الليله|هالليله)' + L2).test(t)) return { abs: 0 };
    return null;
  };
  const DTAIL = new RegExp('^\\s*(?:بعد\\s*(?:بكر[هاة]|غد|يومين)|بكر[هاة]|غدا|باجر|ثاني\\s*يوم|اليوم\\s*الثاني|هاليوم|اليوم)' + L2);
  const tok = (str) => {
    const m = TOK.exec(str); if (!m) return null;
    let len = m[0].length, day = DAYS(m[0]);
    if (!day) { const mt = DTAIL.exec(str.slice(len, len + 20)); if (mt) { day = DAYS(mt[0]); len += mt[0].length; } }
    return { h: +(m[1] || m[3] || m[5]), mi: +(m[2] || m[4] || 0), mk: m[6] || '', len, raw: m[0], day };
  };
  const to24 = (t) => { if (!t.mk) return t.h; if (/صب|فجر/.test(t.mk)) return t.h === 12 ? 0 : t.h; if (/ظهر/.test(t.mk)) return t.h < 7 ? t.h + 12 : t.h; return t.h < 12 ? t.h + 12 : (/ليل/.test(t.mk) && t.h === 12 ? 0 : t.h); };
  const amb = (t) => !t.mk && t.h >= 1 && t.h <= 12 && !/(?:^|\D)0\d:/.test(t.raw);
  const fmtB = (ms) => new Date(ms + BG).toISOString().slice(0, 16).replace('T', ' ');
  const fmtU = (ms) => new Date(ms).toISOString().slice(0, 19).replace('T', ' ');
  const tail = ' ما أنشأت أي حملة.';
  const ERR_FMT = '⛔ فهمت أنك تريد جدولة الحملة بس ما قدرت أقرأ الوقت. اكتب مثل: «روّج الساعة 22:00 وقف الساعة 10:00 صباحاً».' + tail;
  const W = (() => {
    const cueS = new RegExp(L1 + '(?:روجها|روج|ابدا|ابدي|تبدا|تنطلق|شغلها|شغل|فعلها|فعل)' + L2);
    const cueE = new RegExp(L1 + '(?:اوقفها|اوقف|وقفها|وقف|ايقاف|توقف|تتوقف|تنتهي|تخلص|لين|لحد|حتي|الي)' + L2);
    const hasClock = /\d{1,2}:\d{2}/.test(s) || /(?:ب?الساعه|ساعه)\s*\d{1,2}/.test(s) || new RegExp('\\d{1,2}\\s*ب?(?:' + MKW + ')' + L2).test(s);
    const hasCue = new RegExp(L1 + '(?:روجها|روج|ابدا|ابدي|تبدا|تنطلق|شغلها|شغل|فعلها|فعل|وقفها|وقف|اوقفها|اوقف|ايقاف|توقف|تتوقف|تنتهي|تخلص)' + L2).test(s);
    if (!hasClock) return null;
    let t1 = null, t2 = null, span = null, endCue = false;
    const ms = cueS.exec(s);
    if (ms) {
      const a = ms.index + ms[0].length; t1 = tok(s.slice(a));
      if (t1 && !t1.day) { const pre = /(?:بعد\s*(?:بكر[هاة]|غد)|بكر[هاة]|غدا|باجر|اليوم)\s*$/.exec(s.slice(Math.max(0, ms.index - 14), ms.index)); if (pre) t1.day = DAYS(pre[0]); }
      if (t1) {
        const b = a + t1.len, rest = s.slice(b, b + 80), me = cueE.exec(rest);
        if (!me) span = [ms.index, b];
        else { endCue = true; t2 = tok(rest.slice(me.index + me[0].length)); if (t2) span = [ms.index, b + me.index + me[0].length + t2.len]; }
      }
    }
    if (!t1 || (endCue && !t2)) {
      t1 = null; t2 = null; span = null;
      const rb = new RegExp(L1 + 'من\\s*', 'g'); let mb;
      while ((mb = rb.exec(s))) {
        const a = mb.index + mb[0].length, x = tok(s.slice(a)); if (!x) continue;
        const rest = s.slice(a + x.len, a + x.len + 25), me = /^\s*(?:الي|لين|لحد|حتي)\s*/.exec(rest); if (!me) continue;
        const y = tok(rest.slice(me[0].length)); if (y) { t1 = x; t2 = y; span = [mb.index, a + x.len + me[0].length + y.len]; break; }
      }
    }
    if (!t1) {   // p230d: بدون فعل بداية («ارفع حمله ساعه 10 بليل وقفها ساعه 7 صبح»): آخر ساعة قبل كلمة الإيقاف
      const reE = new RegExp(L1 + '(?:اوقفها|اوقف|وقفها|وقف|ايقاف|توقف|تتوقف|تنتهي|تخلص)' + L2, 'g');
      const reC = new RegExp('(?:ب?الساعه|ساعه)\\s*\\d{1,2}(?::\\d{2})?|\\d{1,2}:\\d{2}|\\d{1,2}(?=\\s*ب?(?:' + MKW + ')' + L2 + ')', 'g');
      let me2;
      while ((me2 = reE.exec(s))) {
        const y = tok(s.slice(me2.index + me2[0].length)); if (!y) continue;
        const before = s.slice(0, me2.index); let x = null, mc; reC.lastIndex = 0;
        while ((mc = reC.exec(before))) { const c = tok(before.slice(mc.index)); if (c) { c.at = mc.index; x = c; } }
        if (x) {
          if (!x.day) { const pre = /(?:بعد\s*(?:بكر[هاة]|غد)|بكر[هاة]|غدا|باجر|اليوم)\s*$/.exec(before.slice(Math.max(0, x.at - 14), x.at)); if (pre) x.day = DAYS(pre[0]); }
          t1 = x; t2 = y; span = [x.at, me2.index + me2[0].length + y.len]; break;
        }
      }
    }
    if (!t1) return hasCue ? { err: ERR_FMT } : null;
    for (const t of (t2 ? [t1, t2] : [t1])) {
      if (t.h > 23 || t.mi > 59) return { err: '⛔ الساعة ' + t.h + ':' + String(t.mi).padStart(2, '0') + ' مو صالحة.' + tail };
      if (amb(t)) return { err: '⛔ الساعة ' + t.h + ' مو واضحة (صباحاً أم مساءً؟). اكتب ' + t.h + ' صباحاً أو ' + t.h + ' مساءً أو بنظام 24 ساعة مثل 22:00.' + tail };
    }
    const now = Date.now(), nb = new Date(now + BG);
    const dOff = t1.day ? (t1.day.abs != null ? t1.day.abs : t1.day.rel) : 0;
    const h1 = to24(t1), startMs = Date.UTC(nb.getUTCFullYear(), nb.getUTCMonth(), nb.getUTCDate() + dOff, h1, t1.mi, 0) - BG;
    if (startMs < now + 10 * 60000) return { err: '⛔ وقت البداية ' + fmtB(startMs) + ' (بغداد) فات أو أقل من 10 دقائق من الآن (الآن ' + fmtB(now) + '). اكتب «بكرة» أو ساعة أبعد.' + tail };
    if (startMs > now + 30 * 86400000) return { err: '⛔ وقت البداية بعيد أكثر من 30 يوم.' + tail };
    let endMs;
    if (t2) {
      const sb = new Date(startMs + BG);
      if (t2.day) {
        const base = t2.day.abs != null ? [nb, t2.day.abs] : [sb, t2.day.rel];
        endMs = Date.UTC(base[0].getUTCFullYear(), base[0].getUTCMonth(), base[0].getUTCDate() + base[1], to24(t2), t2.mi, 0) - BG;
        if (endMs <= startMs) return { err: '⛔ وقت الإيقاف ' + fmtB(endMs) + ' (بغداد) قبل وقت البداية ' + fmtB(startMs) + ' أو يساويه.' + tail };
      } else {
        endMs = Date.UTC(sb.getUTCFullYear(), sb.getUTCMonth(), sb.getUTCDate(), to24(t2), t2.mi, 0) - BG;
        while (endMs <= startMs) endMs += 86400000;
      }
    } else {
      endMs = startMs + Math.min(90, Math.max(1, Number(launch.days) || 1)) * 86400000;
    }
    const dur = endMs - startMs;
    if (dur < 30 * 60000 || dur > 7 * 86400000) return { err: '⛔ طول النافذة لازم يكون بين 30 دقيقة و7 أيام (الحالي ' + Math.round(dur / 60000) + ' دقيقة).' + tail };
    return { start_at: fmtU(startMs), end_at: fmtU(endMs), h1: t1.h, h2: t2 ? t2.h : null, span };
  })();
  if (W && W.err) return say(W.err);
  if (W) {
    const nBud = Number(it && it.budget);
    if (nBud && (nBud === W.h1 || nBud === W.h2)) {
      const restNums = (s.slice(0, W.span[0]) + ' ' + s.slice(W.span[1])).match(/\d+/g) || [];
      if (!restNums.map(Number).includes(nBud)) return say('⛔ ما قدرت أحدد الميزانية بوضوح (حسبت رقم الساعة ' + nBud + ' كميزانية). اكتب الميزانية بكلمة مثل «ميزانية 30 دولار».' + tail);
    }
    launch.start_at = W.start_at; launch.end_at = W.end_at;
  }
}
