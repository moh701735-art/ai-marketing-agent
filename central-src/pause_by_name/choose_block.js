{   // p240b: رد «أنا طفيت الحملة X» (يتجاوز بقية العقدة)
  const _p = $('Stat: prep').first().json, _r = $input.first().json;
  if (_p && _p.op === 'tiktok.pause_by_name') {
    const T = (t) => [{ json: { ctx: _p.ctx, chatId: _p.chatId, text: t, halt: true } }];
    const nm = String(_p.askedName || (_p.params || {}).name || '').slice(0, 80);
    if (_r.ok !== true) { const e = _r.error; return T('⛔ ما كدرت أطفي الحملة «' + nm + '»: ' + String((e && (e.message || e.class)) || e || 'خطأ غير معروف').slice(0, 160) + '\nما تغيّر شي، تأكد من حالتها بتيك توك.'); }
    const d = _r.data || {}, f = d.accounts_failed || {}, fk = Object.keys(f), ac = (x) => '…' + String(x).slice(-6);
    const fnote = fk.length ? '\n⚠️ ما كدرت أقرأ ' + fk.length + ' حساب (' + fk.slice(0, 3).map(k => ac(k) + ': ' + String(f[k]).slice(0, 60)).join('، ') + ')' : '';
    const L = (a) => (a || []).slice(0, 15).map(x => '• ' + String(x.name).slice(0, 60) + ' (حساب ' + ac(x.account) + ')').join('\n');
    if (d.mode === 'ambiguous') return T('🤔 لقيت أكثر من حملة شغالة تحتوي «' + nm + '»:\n' + L(d.ambiguous) + '\nاكتب الاسم بالضبط وأطفيها. ما طفيت شي.' + fnote);
    if (d.mode === 'not_found') return T('ما لقيت حملة باسم «' + nm + '».' + ((d.similar || []).length ? '\nأقرب أسماء: ' + d.similar.slice(0, 5).map(x => '«' + String(x).slice(0, 40) + '»').join('، ') : '') + '\nما طفيت شي.' + fnote);
    const ok = d.paused || [], bad = d.failed || [], was = d.already_paused || [];
    let t = '';
    if (ok.length) {
      t += '⏸️ أنا طفيت الحملة «' + nm + '»' + (ok.length > 1 ? ' (' + ok.length + ' حملات)' : '') + ':\n' + L(ok);
      const un = ok.filter(x => x.verified !== true);
      if (un.length) t += '\n⚠️ ' + un.length + ' منها ما كدرت أتأكد من حالتها بتيك توك، راجعها.';
    }
    if (bad.length) t += (t ? '\n' : '') + '⛔ ما كدرت أطفي:\n' + bad.slice(0, 15).map(x => '• ' + String(x.name).slice(0, 60) + ' (حساب ' + ac(x.account) + '): ' + String(x.why || 'فشل').slice(0, 80)).join('\n');
    if (was.length) t += (t ? '\n' : '') + (ok.length || bad.length ? 'وموقوفة أصلاً:\n' : 'الحملة «' + nm + '» موقوفة أصلاً:\n') + L(was);
    if (d.mode === 'contains' && ok.length) t = 'ما لقيت اسم مطابق بالضبط، فطفيت الأقرب الوحيد الشغّال.\n' + t;
    return T((t || 'ما صار أي إيقاف للحملة «' + nm + '».') + fnote);
  }
}
