let r = $input.first().json;   /* p240b: «طفي حملة X» نية ثابتة تتجاوز الـAI (حتى لو فشل) */
{
  const _R = $('Route').first().json;
  const _t0 = String((_R && !_R.fromCb && _R.text) || '').replace(/[ً-ٟـ]/g, '').replace(/\s+/g, ' ').trim();
  const _m = /^(?:(?:لو سمحت|ممكن|من فضلك|يا بوت)\s+)*(?:[اأإ]?طفي|[اأإ]?وقف|[اأإ]يقاف)(?:\s*لي)?\s+(?:ال)?حمل[ةه]\s+(.+?)\s*[.!؟?]*$/.exec(_t0);
  const _n = _m ? _m[1].replace(/^[«"'“]+|[»"'”]+$/g, '').trim() : '';
  if (_n && _n.length <= 80 && !/ارفع|روج|ميزاني|بحساب|دولار|دينار|ساع[ةه]|\d{1,2}:\d{2}/.test(_n)) r = { ok: true, data: { intent: { intent: 'campaign_status', name: _n, act: 'pause' } } };
}
