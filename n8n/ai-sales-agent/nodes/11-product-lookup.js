// 11 - Product Lookup: resolves the product from the message, the conversation context or store defaults
const ctx = $('05 - Get Conversation State').first().json;
const ext = $('10 - Extract Customer Data').first().json;
const norm = (s) => String(s || '').trim().toLowerCase().replace(/[أإآ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي').replace(/^ال/, '').replace(/\s+/g, ' ');
const list = (s) => String(s || '').split(/[,،]/).map(x => x.trim()).filter(Boolean);
const products = ctx.products;
const byId = (id) => products.find(p => String(p.product_id) === String(id)) || null;
const e = ext.entities;
const draft = ctx.draft || {};
let product = null, source = null;
if (e.product_id && byId(e.product_id)) { product = byId(e.product_id); source = 'message'; }
if (!product && e.product_mentioned_text) {
  const t = norm(e.product_mentioned_text);
  product = products.find(p => [p.product_name].concat(list(p.aliases)).map(norm).filter(Boolean).some(n => t.includes(n) || n.includes(t))) || null;
  if (product) source = 'text_match';
}
if (!product && draft.product_id && draft.status !== 'CONFIRMED' && byId(draft.product_id)) { product = byId(draft.product_id); source = 'draft'; }
if (!product && ctx.customer.last_product && byId(ctx.customer.last_product)) { product = byId(ctx.customer.last_product); source = 'last_product'; }
if (!product && ctx.store.default_product_id && byId(ctx.store.default_product_id)) { product = byId(ctx.store.default_product_id); source = 'store_default'; }
if (!product && products.length === 1) { product = products[0]; source = 'only_product'; }

const matchOption = (val, options) => {
  if (!val) return { value: null, valid: true };
  if (!options.length) return { value: val, valid: true };
  const v = norm(val);
  const hit = options.find(x => norm(x) === v) || options.find(x => norm(x).includes(v) || v.includes(norm(x)));
  return hit ? { value: hit, valid: true } : { value: null, valid: false, raw: val };
};
const colors = product ? list(product.colors) : [];
const sizes = product ? list(product.sizes) : [];
return [{ json: {
  product, product_source: source, product_id: product ? product.product_id : '',
  colors, sizes, color: matchOption(e.color, colors), size: matchOption(e.size, sizes),
  product_not_found: !!(e.product_mentioned_text && !['message', 'text_match'].includes(source) && products.length > 1)
} }];
