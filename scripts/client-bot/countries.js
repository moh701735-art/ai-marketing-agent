// Country targeting from the user's message. Used by the TikTok group prep and the Meta ad-set prep.
// ids = TikTok location_id (tool/region, TO_COUNTRY); iso = Meta country code. null id = TikTok does not offer it.
const COUNTRIES = [
  { ar: ['العراق', 'عراق'], iso: 'IQ', id: '99237', name: 'العراق' },
  { ar: ['السعودية', 'السعوديه', 'المملكة العربية السعودية', 'saudi'], iso: 'SA', id: '102358', name: 'السعودية' },
  { ar: ['الكويت', 'kuwait'], iso: 'KW', id: '285570', name: 'الكويت' },
  { ar: ['الإمارات', 'الامارات', 'emirates', 'uae'], iso: 'AE', id: '290557', name: 'الإمارات' },
  { ar: ['قطر', 'qatar'], iso: 'QA', id: '289688', name: 'قطر' },
  { ar: ['البحرين', 'bahrain'], iso: 'BH', id: '290291', name: 'البحرين' },
  { ar: ['سلطنة عمان', 'عُمان', 'oman'], iso: 'OM', id: '286963', name: 'عمان' },
  { ar: ['مصر', 'egypt'], iso: 'EG', id: '357994', name: 'مصر' },
  { ar: ['لبنان', 'lebanon'], iso: 'LB', id: '272103', name: 'لبنان' },
  { ar: ['المغرب', 'morocco'], iso: 'MA', id: '2542007', name: 'المغرب' },
  { ar: ['الجزائر', 'algeria'], iso: 'DZ', id: '2589581', name: 'الجزائر' },
  { ar: ['تركيا', 'turkey'], iso: 'TR', id: '298795', name: 'تركيا' },
  { ar: ['امريكا', 'أمريكا', 'الولايات المتحدة', 'usa'], iso: 'US', id: '6252001', name: 'أمريكا' },
  { ar: ['بريطانيا', 'المملكة المتحدة'], iso: 'GB', id: '2635167', name: 'بريطانيا' },
  { ar: ['المانيا', 'ألمانيا', 'germany'], iso: 'DE', id: '2921044', name: 'ألمانيا' },
  { ar: ['السويد', 'sweden'], iso: 'SE', id: '2661886', name: 'السويد' },
  { ar: ['هولندا', 'netherlands'], iso: 'NL', id: '2750405', name: 'هولندا' },
  { ar: ['كندا', 'canada'], iso: 'CA', id: '6251999', name: 'كندا' },
  { ar: ['فرنسا', 'france'], iso: 'FR', id: '3017382', name: 'فرنسا' },
  // known to Meta but not offered by TikTok for this placement
  { ar: ['الأردن', 'الاردن'], iso: 'JO', id: null, name: 'الأردن' },
  { ar: ['اليمن'], iso: 'YE', id: null, name: 'اليمن' },
  { ar: ['السودان'], iso: 'SD', id: null, name: 'السودان' },
  { ar: ['ليبيا'], iso: 'LY', id: null, name: 'ليبيا' },
  { ar: ['تونس'], iso: 'TN', id: null, name: 'تونس' },
  { ar: ['فلسطين'], iso: 'PS', id: null, name: 'فلسطين' },
  { ar: ['سوريا'], iso: null, id: null, name: 'سوريا' },
  { ar: ['ايران', 'إيران'], iso: null, id: null, name: 'إيران' }
];
const GULF = ['SA', 'KW', 'AE', 'QA', 'BH', 'OM'];
function parseCountries(ctx) {
  const norm = (s) => String(s || '').toLowerCase().replace(/[ًٌٍَُِّْ]/g, '').replace(/[أإآ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي');
  const raw = String(ctx.rawText || '');
  const lines = raw.split(/\n+/).filter(l => /(الدول|الدوله|دولة|دول|بلد|البلد|الموقع|المواقع|الاستهداف|استهداف|location|countries|الخليج)/i.test(l));
  const text = norm([ctx.location || '', ...lines].join(' \n '));
  const found = [];
  if (/(دول\s*)?الخليج/.test(text) && !/(الخليج)\s*(العربي)?\s*(ما|عدا)/.test(text)) GULF.forEach(c => { const x = COUNTRIES.find(k => k.iso === c); if (x && !found.includes(x)) found.push(x); });
  for (const c of COUNTRIES) {
    if (found.includes(c)) continue;
    if (c.ar.some(k => { const n = norm(k); return n && new RegExp('(^|[^\\u0621-\\u064Aa-z])(?:و|ل|ب|ف)?' + n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '($|[^\\u0621-\\u064Aa-z])').test(text); })) found.push(c);
  }
  return found;
}
