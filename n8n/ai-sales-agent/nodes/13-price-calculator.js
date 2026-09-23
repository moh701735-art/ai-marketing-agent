// 13 - Price Calculator: ALL prices come from sa_products (price + quantity_offers). The AI never calculates.
const ctx = $('05 - Get Conversation State').first().json;
const ext = $('10 - Extract Customer Data').first().json;
const pl = $('11 - Product Lookup').first().json;
const product = pl.product;

const parseOffers = (s) => {
  const out = {};
  if (!s) return out;
  let obj = null;
  if (typeof s === 'object') obj = s; else { try { obj = JSON.parse(s); } catch (e) { obj = null; } }
  if (obj && typeof obj === 'object') { Object.keys(obj).forEach(k => { const q = parseInt(k, 10); const v = Number(obj[k]); if (q > 0 && v >= 0) out[q] = v; }); return out; }
  String(s).split(/[,،;\n]/).forEach(part => { const m = part.match(/(\d+)\s*[=:]\s*(\d+)/); if (m) out[parseInt(m[1], 10)] = Number(m[2]); });
  return out;
};
// Pricing rule: exact quantity offer if defined, otherwise the biggest offer tier <= quantity + base price for the remaining pieces.
const calc = (p, q) => {
  if (!p || p.price === null || p.price === undefined || !(q >= 1)) return null;
  const offers = parseOffers(p.quantity_offers);
  const base = offers[1] !== undefined ? offers[1] : Number(p.price);
  if (offers[q] !== undefined) return { quantity: q, total: offers[q], unit_price: base, offer_applied: q > 1, rule: 'exact_offer_' + q };
  const tiers = Object.keys(offers).map(Number).filter(t => t > 1 && t <= q).sort((a, b) => b - a);
  if (tiers.length) { const t = tiers[0]; return { quantity: q, total: offers[t] + (q - t) * base, unit_price: base, offer_applied: true, rule: 'tier_' + t + '_plus_base' }; }
  return { quantity: q, total: q * base, unit_price: base, offer_applied: false, rule: 'base_price' };
};

const media = $('12 - Product Media Lookup').all().map(i => i.json)
  .filter(m => m && m.url && m.active !== false && String(m.store_id) === String(ctx.store.store_id) && String(m.product_id) === String(pl.product_id))
  .sort((a, b) => (Number(a.sort_order) || 0) - (Number(b.sort_order) || 0));
const images = media.filter(m => String(m.media_type).toLowerCase() === 'image');
const videos = media.filter(m => String(m.media_type).toLowerCase() === 'video');

const draft = ctx.draft || {};
const e = ext.entities;
const qty = e.quantity || ((draft.status !== 'CONFIRMED' && product && draft.product_id === product.product_id) ? Number(draft.quantity) || null : null) || 1;
const quote = calc(product, qty);
const unitQuote = calc(product, 1);
const offers = product ? Object.keys(parseOffers(product.quantity_offers)).map(Number).sort((a, b) => a - b).map(q => ({ quantity: q, total: parseOffers(product.quantity_offers)[q] })) : [];

const provinceName = e.province || (draft.status !== 'CONFIRMED' ? draft.province : null) || ctx.customer.province || null;
const ship = provinceName ? ctx.shipping.find(s => s.province === provinceName) : null;
const shippingFee = ship && ship.fee !== null ? ship.fee : null;

let stockStatus = 'unknown';
if (product && product.stock !== null) stockStatus = product.stock <= 0 ? 'out_of_stock' : (qty > product.stock ? 'insufficient' : 'in_stock');
else if (product) stockStatus = 'available';

return [{ json: {
  product, images, videos, quote, unit_quote: unitQuote, offers, quantity: qty,
  province: provinceName, shipping_fee: shippingFee, delivery_days: ship ? ship.delivery_days : '',
  stock_status: stockStatus, stock: product ? product.stock : null
} }];
