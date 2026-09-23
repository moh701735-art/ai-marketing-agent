C = {}

C['02'] = r'''// 02 - Detect Message Type: normalizes the WhatsApp Cloud API payload into one clean message object
const v = $input.first().json || {};
const msg = (v.messages || [])[0];
if (!msg) return []; // status updates (sent/delivered/read) have no messages -> stop silently
if (msg.type === 'reaction' || msg.type === 'system' || msg.type === 'unsupported') return [];
const contact = (v.contacts || [])[0] || {};
const t = msg.type;
let text = '', mediaId = '', mime = '', caption = '', filename = '', location = null;
switch (t) {
  case 'text': text = (msg.text && msg.text.body) || ''; break;
  case 'audio': mediaId = msg.audio.id; mime = msg.audio.mime_type || ''; break;
  case 'image': mediaId = msg.image.id; mime = msg.image.mime_type || ''; caption = msg.image.caption || ''; break;
  case 'video': mediaId = msg.video.id; mime = msg.video.mime_type || ''; caption = msg.video.caption || ''; break;
  case 'document': mediaId = msg.document.id; mime = msg.document.mime_type || ''; caption = msg.document.caption || ''; filename = msg.document.filename || ''; break;
  case 'location': location = { latitude: msg.location.latitude, longitude: msg.location.longitude, name: msg.location.name || '', address: msg.location.address || '' }; break;
  case 'interactive': text = (msg.interactive.button_reply && msg.interactive.button_reply.title) || (msg.interactive.list_reply && msg.interactive.list_reply.title) || ''; break;
  case 'button': text = (msg.button && msg.button.text) || ''; break;
}
const KIND = { text: 'TEXT', interactive: 'TEXT', button: 'TEXT', audio: 'VOICE', image: 'IMAGE', video: 'VIDEO', document: 'DOCUMENT', location: 'LOCATION' };
return [{ json: {
  message_id: msg.id,
  wa_from: String(msg.from || ''),
  profile_name: (contact.profile && contact.profile.name) || '',
  phone_number_id: String((v.metadata && v.metadata.phone_number_id) || ''),
  display_phone: String((v.metadata && v.metadata.display_phone_number) || ''),
  raw_type: t,
  message_type: KIND[t] || 'OTHER',
  text, media_id: mediaId || '', mime_type: mime, caption, filename, location,
  reply_to: (msg.context && msg.context.id) || '',
  timestamp: msg.timestamp || '',
  received_at: new Date().toISOString()
} }];
'''

C['05'] = r'''// 05 - Get Conversation State: builds the full context (store, customer, draft order, catalog, shipping)
const msg = $('02 - Detect Message Type').first().json;
const rows = (name) => $(name).all().map(i => i.json).filter(r => r && r.id !== undefined);
const safeJson = (s, fb) => { if (!s) return fb; if (typeof s === 'object') return s; try { return JSON.parse(s); } catch (e) { return fb; } };
const num = (v) => (v === null || v === undefined || v === '') ? null : Number(v);
const safe = (v) => String(v === null || v === undefined ? '' : v).replace(/[{}]/g, ' ').replace(/\s+/g, ' ').trim();

const stores = rows('04 - Get Store Settings').filter(r => r.active !== false);
let store = stores.find(r => String(r.phone_number_id) === String(msg.phone_number_id)) || stores.find(r => String(r.phone_number_id) === '*');
const storeMissing = !store;
store = Object.assign({ store_id: 'DEFAULT', store_name: '', currency: 'IQD', notify_channel: 'telegram', telegram_chat_id: '', team_whatsapp_numbers: '', handoff_hours: 12, default_product_id: '' }, store || {});
const storeId = String(store.store_id);

const products = rows('04c - Load Product Catalog').filter(p => String(p.store_id) === storeId && p.active !== false && p.product_id).map(p => ({
  row_id: p.id, product_id: String(p.product_id), product_name: p.product_name || '', aliases: p.aliases || '', description: p.description || '',
  price: num(p.price), currency: p.currency || store.currency || 'IQD', colors: p.colors || '', sizes: p.sizes || '', stock: num(p.stock),
  quantity_offers: p.quantity_offers || '', shipping_information: p.shipping_information || '', return_information: p.return_information || '', notes: p.notes || ''
}));

const shipping = rows('04d - Load Shipping Table').filter(s => String(s.store_id) === storeId && s.active !== false && s.province).map(s => ({
  province: s.province, aliases: s.aliases || '', fee: num(s.fee), delivery_days: s.delivery_days || ''
}));

const customerId = storeId + '-' + msg.wa_from;
const custRow = rows('04b - Get Customer').find(r => String(r.customer_id) === customerId);
const isNew = !custRow;
const customer = Object.assign({ customer_id: customerId, store_id: storeId, whatsapp_number: msg.wa_from, whatsapp_name: '', name: '', phone: '', province: '', area: '', landmark: '', last_product: '', last_order: '', conversation_state: 'NEW_CUSTOMER', draft_order: '', recent_messages: '', handoff_until: null }, custRow || {});
customer.whatsapp_name = msg.profile_name || customer.whatsapp_name || '';

let state = customer.conversation_state || 'NEW_CUSTOMER';
const handoffUntil = customer.handoff_until ? new Date(customer.handoff_until).getTime() : 0;
let handoffActive = false;
if (state === 'HUMAN_HANDOFF') { if (handoffUntil > Date.now()) handoffActive = true; else state = 'BROWSING'; }

const draft = safeJson(customer.draft_order, {}) || {};
const recent = safeJson(customer.recent_messages, []) || [];

const lines = [];
lines.push('store_name: ' + safe(store.store_name));
lines.push('conversation_state: ' + state);
lines.push('is_new_customer: ' + isNew);
lines.push('known_customer_data: name=' + safe(customer.name) + ' | phone=' + safe(customer.phone) + ' | province=' + safe(customer.province) + ' | area=' + safe(customer.area) + ' | landmark=' + safe(customer.landmark));
lines.push('last_product_id: ' + safe(customer.last_product));
lines.push('default_product_id: ' + safe(store.default_product_id));
const draftForAi = Object.keys(draft).filter(k => !['_meta', 'review_hash', 'price_rule'].includes(k) && draft[k] !== null && draft[k] !== '' && draft[k] !== undefined).map(k => k + '=' + safe(draft[k]));
lines.push('current_order_draft: ' + (draftForAi.length ? draftForAi.join(' | ') : 'none'));
lines.push('recent_conversation (oldest first):');
recent.slice(-8).forEach(m => lines.push('- ' + (m.r === 'agent' ? 'الوكيل' : 'الزبون') + ': ' + safe(m.t)));
lines.push('catalog:');
products.slice(0, 300).forEach(p => lines.push('- product_id=' + p.product_id + ' | name=' + safe(p.product_name) + ' | aliases=' + safe(p.aliases) + ' | colors=' + safe(p.colors) + ' | sizes=' + safe(p.sizes)));
lines.push('provinces: ' + shipping.map(s => s.province).join('، '));

return [{ json: {
  msg, store, store_missing: storeMissing, products, shipping, customer, state, is_new_customer: isNew,
  handoff_active: handoffActive, draft, recent, last_order_id: customer.last_order || '', ai_context_text: lines.join('\n')
} }];
'''

C['07e'] = r'''// 07e - Media Processing Failed: download / Gemini error -> mark as failed (no secrets are kept)
const j = $input.first().json || {};
const e = j.error;
const m = typeof e === 'string' ? e : (e && (e.message || e.description)) || 'media processing error';
return [{ json: { media_failed: true, media_error: String(m).slice(0, 300) } }];
'''

C['08'] = r'''// 08 - Clean Transcript: one clean customer_text regardless of message type (text / voice / image / video / document / location)
const msg = $('02 - Detect Message Type').first().json;
const inp = $input.first().json || {};
const AR = '٠١٢٣٤٥٦٧٨٩', FA = '۰۱۲۳۴۵۶۷۸۹';
const toWestern = (s) => String(s || '').replace(/[٠-٩]/g, d => String(AR.indexOf(d))).replace(/[۰-۹]/g, d => String(FA.indexOf(d)));
const clean = (s) => toWestern(s).replace(/[\u200B-\u200F\u202A-\u202E\u2066-\u2069]/g, '').replace(/[{}]/g, ' ').replace(/\s+/g, ' ').trim();
const pick = (j) => {
  if (!j) return '';
  if (typeof j === 'string') return j;
  if (typeof j.text === 'string') return j.text;
  if (j.content && Array.isArray(j.content.parts)) return j.content.parts.map(p => p.text || '').join(' ');
  if (Array.isArray(j.candidates) && j.candidates[0] && j.candidates[0].content && Array.isArray(j.candidates[0].content.parts)) return j.candidates[0].content.parts.map(p => p.text || '').join(' ');
  if (typeof j.output === 'string') return j.output;
  return '';
};
const isMedia = ['VOICE', 'IMAGE', 'VIDEO', 'DOCUMENT'].includes(msg.message_type);
let mediaFailed = !!inp.media_failed;
let mediaText = '';
if (isMedia && !mediaFailed) { mediaText = clean(pick(inp)); if (!mediaText) mediaFailed = true; }
const unclear = msg.message_type === 'VOICE' && (/\[?UNCLEAR\]?/i.test(mediaText) || mediaText.replace(/[^\p{L}\p{N}]/gu, '').length < 2);
const caption = clean(msg.caption);
let text = '';
switch (msg.message_type) {
  case 'TEXT': text = clean(msg.text); break;
  case 'VOICE': text = mediaText.replace(/\[?UNCLEAR\]?/ig, '').trim(); break;
  case 'IMAGE': text = (caption ? caption + ' ' : '') + (mediaFailed ? '[الزبون دز صورة وما كدرنا نحللها]' : '[الزبون دز صورة، وصفها: ' + mediaText + ']'); break;
  case 'VIDEO': text = (caption ? caption + ' ' : '') + (mediaFailed ? '[الزبون دز فيديو وما كدرنا نحلله]' : '[الزبون دز فيديو، محتواه: ' + mediaText + ']'); break;
  case 'DOCUMENT': text = (caption ? caption + ' ' : '') + (mediaFailed ? '[الزبون دز ملف ' + clean(msg.filename) + ' وما كدرنا نقراه]' : '[الزبون دز ملف ' + clean(msg.filename) + '، محتواه: ' + mediaText + ']'); break;
  case 'LOCATION': { const l = msg.location || {}; text = '[الزبون دز موقعه: ' + clean([l.name, l.address].filter(Boolean).join(' - ')) + ' (' + l.latitude + ', ' + l.longitude + ')]'; break; }
  default: text = '[الزبون دز رسالة من نوع ' + msg.raw_type + ']';
}
return [{ json: {
  customer_text: text.slice(0, 3000),
  input_source: msg.message_type,
  voice_failed: msg.message_type === 'VOICE' && (mediaFailed || unclear),
  media_failed: mediaFailed,
  media_error: String(inp.media_error || '').slice(0, 300),
  location: msg.location || null
} }];
'''

C['10'] = r'''// 10 - Extract Customer Data: validates / normalizes what the AI understood (AI never decides prices or orders)
const ctx = $('05 - Get Conversation State').first().json;
const raw = $input.first().json || {};
const o = (raw.output && typeof raw.output === 'object') ? raw.output : raw;
const ALLOWED = ['PRODUCT_INQUIRY', 'PRICE_INQUIRY', 'COLOR_INQUIRY', 'SIZE_INQUIRY', 'IMAGE_REQUEST', 'VIDEO_REQUEST', 'AVAILABILITY', 'SHIPPING_INQUIRY', 'DISCOUNT_INQUIRY', 'QUANTITY_INQUIRY', 'BUY_INTENT', 'ORDER_CONFIRMATION', 'ORDER_CANCEL', 'CHANGE_ORDER', 'CUSTOMER_SUPPORT', 'HUMAN_AGENT_REQUEST', 'OTHER'];
const norm = (s) => String(s || '').trim().toLowerCase().replace(/[أإآ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي').replace(/^ال/, '').replace(/\s+/g, ' ');
const str = (v) => { const s = String(v === null || v === undefined ? '' : v).trim(); return (s && s.toLowerCase() !== 'null' && s !== '-') ? s.slice(0, 200) : null; };

let intents = Array.isArray(o.intents) ? o.intents.map(x => String(x).toUpperCase().trim()).filter(x => ALLOWED.includes(x)) : [];
intents = Array.from(new Set(intents));
if (!intents.length) intents = ['OTHER'];

let qty = parseInt(String(o.quantity === null || o.quantity === undefined ? '' : o.quantity).replace(/[^0-9]/g, ''), 10);
if (!(qty >= 1 && qty <= 500)) qty = null;

let phoneRaw = String(o.phone || '').replace(/[^0-9]/g, '');
let phone = null, phoneInvalid = false;
if (phoneRaw) {
  if (phoneRaw.startsWith('00964')) phoneRaw = '0' + phoneRaw.slice(5);
  else if (phoneRaw.startsWith('964')) phoneRaw = '0' + phoneRaw.slice(3);
  else if (phoneRaw.length === 10 && phoneRaw.startsWith('7')) phoneRaw = '0' + phoneRaw;
  if (/^07[0-9]{9}$/.test(phoneRaw)) phone = phoneRaw; else phoneInvalid = true;
}

let province = null, provinceUnmatched = null;
if (str(o.province)) {
  const p = norm(o.province);
  if (!ctx.shipping.length) province = str(o.province);
  else {
    const hit = ctx.shipping.find(s => norm(s.province) === p || String(s.aliases || '').split(/[,،]/).map(norm).filter(Boolean).includes(p));
    if (hit) province = hit.province; else provinceUnmatched = str(o.province);
  }
}

const entities = {
  product_id: str(o.product_id), product_mentioned_text: str(o.product_mentioned_text), quantity: qty,
  color: str(o.color), size: str(o.size), customer_name: str(o.customer_name), phone, province,
  area: str(o.area), landmark: str(o.landmark)
};
return [{ json: {
  intents, entities,
  greeting: !!o.greeting,
  wants_images: !!o.wants_images || intents.includes('IMAGE_REQUEST'),
  wants_video: !!o.wants_video || intents.includes('VIDEO_REQUEST'),
  confirmation: !!o.confirmation,
  cancel: !!o.cancel || intents.includes('ORDER_CANCEL'),
  human_request: !!o.human_request || intents.includes('HUMAN_AGENT_REQUEST'),
  change_fields: Array.isArray(o.change_fields) ? o.change_fields.map(String) : [],
  question_summary: str(o.question_summary) || '',
  phone_invalid: phoneInvalid, phone_raw: phoneInvalid ? phoneRaw : '',
  province_unmatched: provinceUnmatched
} }];
'''

C['11'] = r'''// 11 - Product Lookup: resolves the product from the message, the conversation context or store defaults
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
'''

PRICE_FUNCS = r'''
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
'''

C['13'] = r'''// 13 - Price Calculator: ALL prices come from sa_products (price + quantity_offers). The AI never calculates.
const ctx = $('05 - Get Conversation State').first().json;
const ext = $('10 - Extract Customer Data').first().json;
const pl = $('11 - Product Lookup').first().json;
const product = pl.product;
''' + PRICE_FUNCS + r'''
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
'''

C['14'] = r'''// 14 - Order State Manager: the business brain. Conversation state machine + order draft + actions.
const ctx = $('05 - Get Conversation State').first().json;
const clean = $('08 - Clean Transcript').first().json;
const ext = $('10 - Extract Customer Data').first().json;
const pl = $('11 - Product Lookup').first().json;
const pc = $('13 - Price Calculator').first().json;
const lastOrder = $('05e - Get Last Order').all().map(i => i.json).find(r => r && r.order_id) || null;
''' + PRICE_FUNCS + r'''
const I = new Set(ext.intents || []);
const e = ext.entities || {};
const product = pl.product || null;
const store = ctx.store;
const COLLECTING = ['COLLECTING_ORDER', 'WAITING_NAME', 'WAITING_PHONE', 'WAITING_PROVINCE', 'WAITING_AREA', 'WAITING_LANDMARK', 'WAITING_QUANTITY', 'WAITING_SIZE', 'WAITING_COLOR', 'ORDER_REVIEW', 'WAITING_CONFIRMATION'];
const CUSTOMER_FIELDS = ['customer_name', 'phone', 'province', 'area', 'landmark'];
const STATE_FOR = { product: 'COLLECTING_ORDER', color: 'WAITING_COLOR', size: 'WAITING_SIZE', quantity: 'WAITING_QUANTITY', customer_name: 'WAITING_NAME', phone: 'WAITING_PHONE', province: 'WAITING_PROVINCE', area: 'WAITING_AREA', landmark: 'WAITING_LANDMARK' };
const prevState = ctx.state;
let draft = JSON.parse(JSON.stringify(ctx.draft || {}));
const meta = Object.assign({ images_sent_for: [] }, draft._meta || {});
delete draft._meta;

const has = (v) => v !== null && v !== undefined && String(v).trim() !== '';
const fmt = (n) => (n === null || n === undefined || isNaN(Number(n))) ? '' : Number(n).toLocaleString('en-US');
const currency = (product && product.currency) || store.currency || 'IQD';
const curWord = currency === 'IQD' ? 'دينار' : currency;
const qtyText = (q) => Number(q) === 1 ? 'قطعة وحدة' : (Number(q) === 2 ? 'قطعتين' : q + ' قطع');
const norm = (s) => String(s || '').trim().toLowerCase().replace(/[أإآ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي').replace(/^ال/, '');
const list = (s) => String(s || '').split(/[,،]/).map(x => x.trim()).filter(Boolean);
const customerOnly = (d) => { const o = {}; CUSTOMER_FIELDS.forEach(k => { if (has(d[k])) o[k] = d[k]; }); return o; };
const findShipping = (prov) => ctx.shipping.find(s => s.province === prov) || null;
const productById = (id) => ctx.products.find(p => p.product_id === id) || null;

const facts = { notes: [] };
let action = 'reply';
let replyMode = 'ai';
let nextState = prevState === 'NEW_CUSTOMER' ? 'BROWSING' : prevState;
let handoffUntil = null, handoffReason = '';
let isEdit = false, ordering = false;
const wantsChange = I.has('CHANGE_ORDER') || (ext.change_fields || []).length > 0;
const locked = !!(lastOrder && draft.order_id && lastOrder.order_id === draft.order_id && ['PROCESSING', 'SHIPPED', 'DELIVERED'].includes(String(lastOrder.status)));
const setHandoff = (reason) => {
  action = 'handoff'; replyMode = 'handoff'; nextState = 'HUMAN_HANDOFF'; handoffReason = reason;
  handoffUntil = new Date(Date.now() + (Number(store.handoff_hours) || 12) * 3600000).toISOString();
};

if (ext.human_request) {
  setHandoff('customer_request');
} else if (ext.cancel) {
  if ((draft.status === 'CONFIRMED' || draft.status === 'EDITING') && draft.order_id) {
    if (locked) setHandoff('order_locked_cancel');
    else { action = 'cancel_order'; replyMode = 'cancelled_confirmed'; }
  } else if (has(draft.product_id) || has(draft.quantity) || draft.status === 'EDITING') {
    draft = customerOnly(draft); replyMode = 'cancelled_draft'; nextState = 'ORDER_CANCELLED';
  } else {
    facts.notes.push('الزبون كال يريد يلغي بس ماكو طلب مفتوح حالياً');
    nextState = 'BROWSING';
  }
} else {
  if (draft.status === 'CONFIRMED') {
    if (wantsChange) { if (locked) setHandoff('order_locked_change'); else { draft.status = 'EDITING'; } }
    else if (I.has('BUY_INTENT')) { draft = customerOnly(draft); }
  }
  isEdit = draft.status === 'EDITING';

  if (action !== 'handoff') {
    const writable = draft.status !== 'CONFIRMED';
    ordering = writable && (I.has('BUY_INTENT') || I.has('ORDER_CONFIRMATION') || wantsChange || isEdit || COLLECTING.includes(prevState));
    if (writable) {
      if (product) {
        const explicit = ['message', 'text_match'].includes(pl.product_source);
        if (!has(draft.product_id) || (explicit && draft.product_id !== product.product_id)) {
          if (has(draft.product_id) && draft.product_id !== product.product_id) { draft.color = null; draft.size = null; }
          draft.product_id = product.product_id; draft.product_name = product.product_name;
        }
      }
      if (has(e.quantity)) draft.quantity = e.quantity;
      if (pl.color && pl.color.value && product && draft.product_id === product.product_id) draft.color = pl.color.value;
      if (pl.color && pl.color.valid === false) facts.invalid_color = { said: pl.color.raw, options: pl.colors.join('، ') };
      if (pl.size && pl.size.value && product && draft.product_id === product.product_id) draft.size = pl.size.value;
      if (pl.size && pl.size.valid === false) facts.invalid_size = { said: pl.size.raw, options: pl.sizes.join('، ') };
      CUSTOMER_FIELDS.forEach(k => { if (has(e[k])) draft[k] = e[k]; });
      if (ext.phone_invalid) facts.invalid_phone = ext.phone_raw;
      if (ext.province_unmatched) facts.province_unmatched = ext.province_unmatched;
    }

    if (ordering) {
      const dp = productById(draft.product_id);
      CUSTOMER_FIELDS.forEach(k => { const src = k === 'customer_name' ? ctx.customer.name : ctx.customer[k]; if (!has(draft[k]) && has(src)) draft[k] = src; });
      draft.status = isEdit ? 'EDITING' : 'DRAFT';
      const colors = dp ? list(dp.colors) : [];
      const sizes = dp ? list(dp.sizes) : [];
      facts.colors_available = colors.join('، ');
      facts.sizes_available = sizes.join('، ');
      const missing = [];
      if (!dp) missing.push('product');
      if (dp && colors.length && !has(draft.color)) missing.push('color');
      if (dp && sizes.length && !has(draft.size)) missing.push('size');
      if (!has(draft.quantity)) missing.push('quantity');
      CUSTOMER_FIELDS.forEach(k => { if (!has(draft[k])) missing.push(k); });
      let blocked = false;
      if (dp && dp.stock !== null && dp.stock !== undefined) {
        if (dp.stock <= 0) { facts.out_of_stock = true; blocked = true; nextState = 'INTERESTED'; }
        else if (has(draft.quantity) && Number(draft.quantity) > dp.stock) { facts.insufficient_stock = { requested: draft.quantity, available: dp.stock }; blocked = true; nextState = 'WAITING_QUANTITY'; }
      }
      if (dp && (dp.price === null || dp.price === undefined)) { facts.price_missing = true; blocked = true; }
      if (!blocked && missing.length) {
        facts.missing_fields = missing.join(', ');
        facts.ask_field = (missing[0] === 'area' && missing.includes('landmark')) ? 'area_landmark' : missing[0];
        nextState = STATE_FOR[missing[0]];
      } else if (!blocked) {
        const q = Number(draft.quantity);
        const pr = calc(dp, q);
        const ship = findShipping(draft.province);
        const fee = (ship && ship.fee !== null && ship.fee !== undefined) ? Number(ship.fee) : null;
        draft.product_price = pr.total; draft.shipping_fee = fee; draft.total = pr.total + (fee || 0);
        draft.currency = currency; draft.price_rule = pr.rule; draft.product_name = dp.product_name;
        const hash = [draft.product_id, draft.color, draft.size, draft.quantity, draft.customer_name, draft.phone, draft.province, draft.area, draft.landmark, draft.total].join('|');
        const awaiting = ['WAITING_CONFIRMATION', 'ORDER_REVIEW'].includes(prevState);
        if (awaiting && ext.confirmation && draft.review_hash === hash) {
          action = isEdit ? 'update_order' : 'confirm_order';
          replyMode = 'confirmed';
          nextState = 'WAITING_CONFIRMATION';
        } else {
          draft.review_hash = hash; replyMode = 'review'; nextState = 'WAITING_CONFIRMATION';
        }
      }
    } else {
      if (I.has('PRICE_INQUIRY') || I.has('QUANTITY_INQUIRY') || I.has('DISCOUNT_INQUIRY')) nextState = 'ASKING_PRICE';
      else if (['PRODUCT_INQUIRY', 'COLOR_INQUIRY', 'SIZE_INQUIRY', 'IMAGE_REQUEST', 'VIDEO_REQUEST'].some(x => I.has(x))) nextState = 'ASKING_PRODUCT';
      else if (I.has('AVAILABILITY') || I.has('SHIPPING_INQUIRY')) nextState = 'INTERESTED';
      if (draft.status === 'CONFIRMED' && ['BROWSING', 'ORDER_CONFIRMED'].includes(nextState)) nextState = 'ORDER_CONFIRMED';
    }
  }
}

// ---- media to send (images / video from sa_product_media only)
const media = [];
if (action === 'reply' && ['ai', 'review'].includes(replyMode) && product) {
  const colorPref = (pl.color && pl.color.value) || (draft.product_id === product.product_id ? draft.color : null);
  const imgs = (pc.images || []).slice();
  if (colorPref) imgs.sort((a, b) => (norm(b.color) === norm(colorPref) ? 1 : 0) - (norm(a.color) === norm(colorPref) ? 1 : 0));
  if (ext.wants_images) {
    if (imgs.length) imgs.slice(0, 5).forEach(m => media.push({ media_type: 'image', url: m.url, caption: m.caption || '' }));
    else facts.no_images = true;
  } else if ((I.has('PRICE_INQUIRY') || I.has('PRODUCT_INQUIRY')) && replyMode === 'ai' && imgs.length && !meta.images_sent_for.includes(product.product_id)) {
    media.push({ media_type: 'image', url: imgs[0].url, caption: imgs[0].caption || '' });
  }
  if (ext.wants_video) {
    if ((pc.videos || []).length) media.push({ media_type: 'video', url: pc.videos[0].url, caption: pc.videos[0].caption || '' });
    else facts.no_video = true;
  }
  if (media.some(m => m.media_type === 'image') && !meta.images_sent_for.includes(product.product_id)) meta.images_sent_for.push(product.product_id);
} else if ((ext.wants_images || ext.wants_video) && !product) {
  facts.need_product = true;
}

// ---- facts for the response generator (only verified data from the database)
const priceAsked = I.has('PRICE_INQUIRY') || I.has('QUANTITY_INQUIRY') || I.has('DISCOUNT_INQUIRY') || has(e.quantity);
facts.greeting = !!ext.greeting;
facts.is_new_customer = !!ctx.is_new_customer;
facts.whatsapp_name = ctx.customer.whatsapp_name || '';
facts.intents = Array.from(I).join(', ');
facts.question_summary = ext.question_summary;
facts.customer_message = clean.customer_text;
facts.message_was_voice = clean.input_source === 'VOICE';
if (product) {
  facts.product_name = product.product_name;
  facts.product_description = product.description;
  facts.price_one_piece = pc.unit_quote ? fmt(pc.unit_quote.total) + ' ' + curWord : 'غير محدد';
  if (list(product.colors).length) facts.colors = list(product.colors).join('، ');
  if (list(product.sizes).length) facts.sizes = list(product.sizes).join('، ');
  facts.stock_status = pc.stock_status;
  if (product.shipping_information) facts.shipping_information = product.shipping_information;
  if (product.return_information) facts.return_information = product.return_information;
  if (product.notes) facts.product_notes = product.notes;
}
if (product && priceAsked && pc.quote && pc.quote.quantity > 1) facts.price_for_requested_quantity = qtyText(pc.quote.quantity) + ' = ' + fmt(pc.quote.total) + ' ' + curWord;
if (product && (priceAsked || I.has('DISCOUNT_INQUIRY')) && pc.offers.length > 1) facts.quantity_offers = pc.offers.map(x => qtyText(x.quantity) + ' = ' + fmt(x.total) + ' ' + curWord).join(' | ');
if (!product && ctx.products.length) facts.catalog_names = ctx.products.slice(0, 15).map(p => p.product_name).join('، ');
if (!ctx.products.length) facts.catalog_empty = true;
const provinceForShip = e.province || draft.province || ctx.customer.province;
const shipRow = provinceForShip ? findShipping(provinceForShip) : null;
if (shipRow) facts.shipping = shipRow.province + ': ' + (shipRow.fee === null ? 'السعر يتأكد من الفريق' : fmt(shipRow.fee) + ' ' + curWord) + (shipRow.delivery_days ? ' | مدة التوصيل: ' + shipRow.delivery_days : '');
else if (I.has('SHIPPING_INQUIRY')) facts.shipping_table = ctx.shipping.filter(s => s.fee !== null).slice(0, 20).map(s => s.province + ' ' + fmt(s.fee)).join(' | ') || 'غير محدد';
facts.sending_images = media.filter(m => m.media_type === 'image').length;
facts.sending_video = media.some(m => m.media_type === 'video');
const ASK = {
  product: 'يا منتج تريد حبيبي؟' + (facts.catalog_names ? ' (' + facts.catalog_names + ')' : ''),
  color: 'أي لون تريد؟' + (facts.colors_available ? ' المتوفر: ' + facts.colors_available : ''),
  size: 'شنو القياس؟' + (facts.sizes_available ? ' المتوفر: ' + facts.sizes_available : ''),
  quantity: 'شكد قطعة تريد؟',
  customer_name: 'حتى أثبتلك الطلب، شنو الاسم؟',
  phone: 'دزلي رقم الهاتف.',
  province: 'أي محافظة؟',
  area: 'شنو المنطقة؟',
  area_landmark: 'شنو المنطقة وأقرب نقطة دالة؟',
  landmark: 'شنو أقرب نقطة دالة؟'
};
if (facts.ask_field) facts.ask_question = ASK[facts.ask_field];
if (ordering && has(draft.product_id)) facts.order_so_far = ['product=' + (draft.product_name || ''), has(draft.color) ? 'color=' + draft.color : '', has(draft.size) ? 'size=' + draft.size : '', has(draft.quantity) ? 'quantity=' + draft.quantity : '', has(draft.province) ? 'province=' + draft.province : ''].filter(Boolean).join(' | ');
facts.next_state = nextState;

// ---- cost saver: simple data-entry turns during ordering get a fixed template (no second AI call)
const SIMPLE = ['OTHER', 'BUY_INTENT', 'CHANGE_ORDER', 'ORDER_CONFIRMATION'];
let templateReply = '';
if (replyMode === 'ai' && action === 'reply' && ordering && facts.ask_field && !ext.greeting && !ext.wants_images && !ext.wants_video
    && Array.from(I).every(x => SIMPLE.includes(x)) && !facts.out_of_stock && !facts.insufficient_stock && !facts.price_missing) {
  const t = [];
  if (facts.invalid_phone) t.push('حبيبي الرقم مو صحيح، دزلي رقم عراقي يبدي بـ 07 ويتكون من 11 رقم.');
  if (facts.province_unmatched) t.push('ما عرفت المحافظة حبيبي، اكتبلي اسمها بوضوح.');
  if (facts.invalid_color) t.push('اللون «' + facts.invalid_color.said + '» مو متوفر حاليًا، المتوفر: ' + facts.invalid_color.options + '.');
  if (facts.invalid_size) t.push('القياس «' + facts.invalid_size.said + '» مو متوفر حاليًا، المتوفر: ' + facts.invalid_size.options + '.');
  if (!t.length) { t.push('تمام حبيبي 🌹'); t.push(facts.ask_question); }
  templateReply = t.join('\n');
  replyMode = 'template';
}

const safe = (v) => String(v === null || v === undefined ? '' : (typeof v === 'object' ? Object.keys(v).map(k => k + '=' + v[k]).join(', ') : v)).replace(/[{}]/g, ' ').replace(/\s+/g, ' ').trim();
const factsText = Object.keys(facts).filter(k => { const v = facts[k]; return !(v === null || v === undefined || v === '' || v === false || (Array.isArray(v) && !v.length)); })
  .map(k => '- ' + k + ': ' + safe(Array.isArray(facts[k]) ? facts[k].join(' | ') : facts[k])).join('\n');

// ---- deterministic fallback reply (used if the AI response fails)
const fb = [];
if (ext.greeting) fb.push('هلا بيك حبيبي 🌹');
if (product && priceAsked && pc.quote) fb.push('سعر ' + (pc.quote.quantity > 1 ? qtyText(pc.quote.quantity) : 'القطعة') + ' ' + fmt(pc.quote.total) + ' ' + curWord + '.');
if (facts.sending_images) fb.push('وهاي صورته 👇');
if (facts.sending_video) fb.push('وهذا الفيديو 👇');
if (facts.no_video) fb.push('حبيبي حاليًا ما متوفر فيديو لهذا المنتج 🌹');
if (facts.ask_question) fb.push(facts.ask_question);
if (!fb.length) fb.push('هلا بيك حبيبي 🌹 شلون أكدر أساعدك؟');

// ---- stock movements (applied only after the order is saved / cancelled)
const dpFinal = productById(draft.product_id);
const stockUpdate = (dpFinal && dpFinal.stock !== null && has(draft.quantity)) ? { row_id: dpFinal.row_id, new_stock: Math.max(0, dpFinal.stock - Number(draft.quantity)) } : { row_id: dpFinal ? dpFinal.row_id : 0, new_stock: dpFinal ? dpFinal.stock : null };
const savedQty = (lastOrder && lastOrder.order_id === draft.order_id && has(lastOrder.quantity)) ? Number(lastOrder.quantity) : Number(draft.quantity);
const dpSaved = (lastOrder && lastOrder.order_id === draft.order_id && lastOrder.product_id) ? productById(lastOrder.product_id) : dpFinal;
const stockRestore = (dpSaved && dpSaved.stock !== null && savedQty > 0) ? { row_id: dpSaved.row_id, new_stock: dpSaved.stock + savedQty } : { row_id: dpSaved ? dpSaved.row_id : 0, new_stock: dpSaved ? dpSaved.stock : null };

const keepForSafety = ['confirm_order', 'update_order', 'cancel_order'].includes(action);
const savedDraft = keepForSafety && action === 'cancel_order' ? ctx.draft : Object.assign({}, draft, { _meta: meta });
if (keepForSafety && action === 'cancel_order') savedDraft._meta = meta;
const customerUpdate = {
  customer_id: ctx.customer.customer_id,
  store_id: ctx.store.store_id,
  whatsapp_number: ctx.msg.wa_from,
  whatsapp_name: ctx.customer.whatsapp_name || '',
  name: draft.customer_name || ctx.customer.name || '',
  phone: draft.phone || ctx.customer.phone || '',
  province: draft.province || ctx.customer.province || '',
  area: draft.area || ctx.customer.area || '',
  landmark: draft.landmark || ctx.customer.landmark || '',
  last_product: (product && product.product_id) || draft.product_id || ctx.customer.last_product || '',
  last_order: ctx.customer.last_order || '',
  conversation_state: action === 'cancel_order' ? prevState : nextState,
  draft_order: JSON.stringify(savedDraft),
  handoff_until: handoffUntil
};

return [{ json: {
  action, reply_mode: replyMode, next_state: nextState, prev_state: prevState, is_edit: isEdit, ordering,
  handoff_reason: handoffReason, handoff_until: handoffUntil,
  draft, meta, product, facts, facts_text: factsText, fallback_text: fb.join('\n'), template_reply: templateReply,
  media_to_send: media, customer_update: customerUpdate,
  stock_update: stockUpdate, stock_restore: stockRestore,
  currency_word: curWord
} }];
'''

C['19'] = r'''// 19 - Order Review: deterministic templates (review summary / handoff / cancellation). No AI here.
const s = $('14 - Order State Manager').first().json;
const d = s.draft || {};
const fmt = (n) => (n === null || n === undefined || isNaN(Number(n))) ? '' : Number(n).toLocaleString('en-US');
const cur = s.currency_word;
const qtyText = (q) => Number(q) === 1 ? 'قطعة وحدة' : (Number(q) === 2 ? 'قطعتين' : q + ' قطع');
const qtyWord = (q) => Number(q) === 1 ? 'القطعة' : (Number(q) === 2 ? 'القطعتين' : 'الـ ' + q + ' قطع');
const shipUnknown = d.shipping_fee === null || d.shipping_fee === undefined;
let text = '';
if (s.reply_mode === 'review') {
  const L = [s.is_edit ? 'تمام حبيبي 🌹 هذا طلبك بعد التعديل:' : 'تمام حبيبي 🌹 هذا طلبك:', ''];
  L.push('المنتج: ' + d.product_name);
  L.push('الكمية: ' + qtyText(d.quantity));
  if (d.color) L.push('اللون: ' + d.color);
  if (d.size) L.push('القياس: ' + d.size);
  L.push('سعر ' + qtyWord(d.quantity) + ': ' + fmt(d.product_price) + ' ' + cur);
  L.push('التوصيل: ' + (shipUnknown ? 'يأكده الفريق وياك' : fmt(d.shipping_fee) + ' ' + cur));
  L.push('المجموع: ' + fmt(d.total) + ' ' + cur + (shipUnknown ? ' + التوصيل' : ''));
  L.push('');
  L.push('الاسم: ' + d.customer_name);
  L.push('الهاتف: ' + d.phone);
  L.push('المحافظة: ' + d.province);
  L.push('المنطقة: ' + d.area);
  L.push('أقرب نقطة: ' + d.landmark);
  L.push('');
  L.push('إذا كلشي صحيح اكتبلي:');
  L.push('تأكيد الطلب');
  L.push('');
  L.push('وإذا تريد تغيّر أي شي بس كلي 🌹');
  text = L.join('\n');
} else if (s.reply_mode === 'template') {
  text = s.template_reply;
} else if (s.reply_mode === 'handoff') {
  if (s.handoff_reason === 'order_locked_cancel' || s.handoff_reason === 'order_locked_change') text = 'حبيبي طلبك صار قيد التجهيز/الشحن 🌹 حولتك لموظف من فريقنا حتى يساعدك بالتعديل أو الإلغاء، راح يرد عليك بأقرب وقت.';
  else text = 'تمام حبيبي 🌹 حولتك لموظف من فريقنا، راح يرد عليك بأقرب وقت.';
} else if (s.reply_mode === 'cancelled_draft') {
  text = 'تمام حبيبي، لغيت الطلب 🌹 إذا احتجت أي شي آني حاضر.';
} else if (s.reply_mode === 'cancelled_confirmed') {
  text = 'جاري إلغاء الطلب...';
} else if (s.reply_mode === 'confirmed') {
  text = 'جاري تثبيت الطلب...';
}
return [{ json: { template_text: text } }];
'''

C['15b'] = r'''// 15b - Compose Final Reply: picks AI text or template, falls back safely, appends to customer memory
const s = $('14 - Order State Manager').first().json;
const rv = $('19 - Order Review').first().json;
const ctx = $('05 - Get Conversation State').first().json;
const clean = $('08 - Clean Transcript').first().json;
let text = '', aiFailed = false;
if (s.reply_mode === 'ai') {
  let ai = null;
  try {
    const j = $('15 - Generate AI Response').first().json;
    if (j && !j.error && typeof j.text === 'string') ai = j.text;
  } catch (e) { ai = null; }
  if (ai && ai.trim() && !/تم تثبيت|تم تأكيد/.test(ai)) text = ai.trim();
  else { aiFailed = true; text = s.fallback_text; }
} else {
  text = rv.template_text;
}
if (!text) text = 'هلا بيك حبيبي 🌹 شلون أكدر أساعدك؟';
text = text.replace(/https?:\/\/\S+/g, '').trim().slice(0, 4000);
const recent = (ctx.recent || []).concat([
  { r: 'customer', t: String(clean.customer_text || '').slice(0, 400), at: new Date().toISOString() },
  { r: 'agent', t: text.slice(0, 400) }
]).slice(-16);
const cu = Object.assign({}, s.customer_update, { recent_messages: JSON.stringify(recent) });
return [{ json: { reply_text: text, ai_failed: aiFailed, action: s.action, customer_update: cu } }];
'''

C['17a'] = r'''// 17a - Prepare Media Queue: one item per image / video to send (from sa_product_media)
const s = $('14 - Order State Manager').first().json;
return (s.media_to_send || []).filter(m => m.url).map(m => ({ json: { media_type: m.media_type, url: m.url, caption: String(m.caption || '').slice(0, 900) } }));
'''

C['17c'] = r'''// 17c - Media Send Failed: log only (retries already happened on the send node)
const items = $input.all().map(i => i.json || {});
const msgs = items.map(j => { const e = j.error; return typeof e === 'string' ? e : (e && (e.message || e.description)) || 'unknown'; });
return [{ json: { log_error: ('MEDIA_SEND_FAILED: ' + msgs.join(' || ')).replace(/(Bearer\s+)\S+/g, '$1***').replace(/(access_token=)[^&\s]+/g, '$1***').slice(0, 1500), log_level: 'WARN' } }];
'''

C['21b'] = r'''// 21b - Generate Order ID: unique, sequential, derived from the database row id (ORD-YYYY-000123)
const row = $input.first().json || {};
if (!row.id) throw new Error('ORDER_INSERT_RETURNED_NO_ID');
const year = new Date().toLocaleString('en-US', { timeZone: 'Asia/Baghdad', year: 'numeric' });
return [{ json: { row_id: row.id, order_id: 'ORD-' + year + '-' + String(row.id).padStart(6, '0') } }];
'''

C['20'] = r'''// 20 - Order Confirmation: runs ONLY after the order was saved successfully in sa_orders
const s = $('14 - Order State Manager').first().json;
const msg = $('02 - Detect Message Type').first().json;
const fin = $('15b - Compose Final Reply').first().json;
const isUpdate = s.action === 'update_order';
const orderId = isUpdate ? s.draft.order_id : $('21b - Generate Order ID').first().json.order_id;
const d = Object.assign({}, s.draft, { order_id: orderId, status: 'CONFIRMED' });
delete d.review_hash;
const fmt = (n) => (n === null || n === undefined || isNaN(Number(n))) ? '' : Number(n).toLocaleString('en-US');
const cur = s.currency_word;
const shipUnknown = d.shipping_fee === null || d.shipping_fee === undefined;
const when = new Date().toLocaleString('en-GB', { timeZone: 'Asia/Baghdad', hour12: false });
const customerText = (isUpdate ? 'تم تعديل طلبك ✅ 🌹' : 'تم تثبيت طلبك ✅ 🌹') + '\n'
  + 'رقم الطلب: ' + orderId + '\n'
  + 'المجموع: ' + fmt(d.total) + ' ' + cur + (shipUnknown ? ' + التوصيل' : '') + '\n'
  + 'راح يتواصل وياك فريقنا للتوصيل. شكراً لثقتك 🌹';
const team = [
  isUpdate ? '✏️ تعديل طلب' : '🛍️ طلب جديد',
  'رقم الطلب:', orderId,
  '👤 الاسم:', d.customer_name,
  '📱 الهاتف:', d.phone,
  '💬 واتساب:', msg.wa_from,
  '📍 المحافظة:', d.province,
  '📍 المنطقة:', d.area,
  '📌 أقرب نقطة:', d.landmark,
  '🛍️ المنتج:', d.product_name + ' (' + d.product_id + ')',
  '🎨 اللون:', d.color || '-',
  '📏 القياس:', d.size || '-',
  '🔢 الكمية:', String(d.quantity),
  '💰 سعر المنتجات:', fmt(d.product_price),
  '🚚 التوصيل:', shipUnknown ? 'غير محدد - يتأكد مع الزبون' : fmt(d.shipping_fee),
  '💵 المجموع:', fmt(d.total) + (shipUnknown ? ' + التوصيل' : ''),
  '🕐 وقت الطلب:', when
].join('\n');
let recent = [];
try { recent = JSON.parse(fin.customer_update.recent_messages || '[]'); } catch (e) { recent = []; }
if (recent.length && recent[recent.length - 1].r === 'agent') recent[recent.length - 1].t = customerText.slice(0, 400);
const cu = Object.assign({}, fin.customer_update, {
  conversation_state: 'ORDER_CONFIRMED', last_order: orderId,
  draft_order: JSON.stringify(Object.assign({}, d, { _meta: s.meta })), recent_messages: JSON.stringify(recent)
});
return [{ json: { order_id: orderId, is_update: isUpdate, customer_text: customerText, team_message: team, customer_update: cu, draft: d } }];
'''

C['20y'] = r'''// 20y - Build Cancel Notice: runs ONLY after the order status was set to CANCELLED in sa_orders
const s = $('14 - Order State Manager').first().json;
const msg = $('02 - Detect Message Type').first().json;
const fin = $('15b - Compose Final Reply').first().json;
const d = s.draft || {};
const when = new Date().toLocaleString('en-GB', { timeZone: 'Asia/Baghdad', hour12: false });
const customerText = 'تم إلغاء طلبك رقم ' + d.order_id + ' ✅\nإذا احتجت أي شي آني حاضر 🌹';
const team = ['❌ إلغاء طلب', 'رقم الطلب:', d.order_id, '👤 الاسم:', d.customer_name || '-', '📱 الهاتف:', d.phone || '-', '💬 واتساب:', msg.wa_from, '🛍️ المنتج:', (d.product_name || '-'), '🔢 الكمية:', String(d.quantity || '-'), '🕐 وقت الإلغاء:', when].join('\n');
const keep = {};
['customer_name', 'phone', 'province', 'area', 'landmark'].forEach(k => { if (d[k]) keep[k] = d[k]; });
keep._meta = s.meta;
let recent = [];
try { recent = JSON.parse(fin.customer_update.recent_messages || '[]'); } catch (e) { recent = []; }
if (recent.length && recent[recent.length - 1].r === 'agent') recent[recent.length - 1].t = customerText.slice(0, 400);
const cu = Object.assign({}, fin.customer_update, { conversation_state: 'ORDER_CANCELLED', draft_order: JSON.stringify(keep), recent_messages: JSON.stringify(recent) });
return [{ json: { order_id: d.order_id, customer_text: customerText, team_message: team, customer_update: cu } }];
'''

C['22h'] = r'''// 22h - Build Handoff Notice: tells the team a customer needs a human (bot is paused for this customer)
const s = $('14 - Order State Manager').first().json;
const ctx = $('05 - Get Conversation State').first().json;
const clean = $('08 - Clean Transcript').first().json;
const REASON = { customer_request: 'الزبون طلب يحچي ويا موظف', order_locked_cancel: 'الزبون يريد يلغي طلب صار قيد التجهيز/الشحن', order_locked_change: 'الزبون يريد يعدل طلب صار قيد التجهيز/الشحن' };
const until = s.handoff_until ? new Date(s.handoff_until).toLocaleString('en-GB', { timeZone: 'Asia/Baghdad', hour12: false }) : '-';
const d = s.draft || {};
const team = ['🙋 تحويل لموظف بشري', 'السبب:', REASON[s.handoff_reason] || s.handoff_reason, '💬 واتساب:', ctx.msg.wa_from, '👤 الاسم:', ctx.customer.name || ctx.customer.whatsapp_name || '-', '📝 آخر رسالة:', clean.customer_text, '📦 الطلب الحالي:', d.order_id ? d.order_id + ' (' + (d.status || '') + ')' : (d.product_name ? d.product_name + ' x ' + (d.quantity || '?') : 'لا يوجد'), '⏳ الرد الآلي متوقف لهذا الزبون لحد:', until].join('\n');
return [{ json: { team_message: team } }];
'''

C['22p'] = r'''// 22p - Prepare Team Message: picks the notice produced by this run and the store's team channel
const ex = (n) => { try { return $(n).isExecuted; } catch (e) { return false; } };
let text = '';
for (const n of ['24 - Error Handler', '20 - Order Confirmation', '20y - Build Cancel Notice', '22h - Build Handoff Notice']) {
  if (ex(n)) { const j = $(n).first().json; if (j && j.team_message) { text = j.team_message; break; } }
}
if (!text) return [];
let store = {};
try { store = $('05 - Get Conversation State').first().json.store || {}; } catch (e) { store = {}; }
const channel = String(store.notify_channel || 'telegram').toLowerCase().trim();
const numbers = String(store.team_whatsapp_numbers || '').split(/[,،\s]+/).map(x => x.replace(/[^0-9]/g, '')).filter(Boolean);
return [{ json: { team_message: text.slice(0, 3900), channel, telegram_chat_id: String(store.telegram_chat_id || ''), team_numbers: numbers } }];
'''

C['23a'] = r'''// 23a - Split Team Numbers: one WhatsApp message per team member number
const j = $input.first().json;
return (j.team_numbers || []).map(n => ({ json: { to: n, text: j.team_message } }));
'''

C['24'] = r'''// 24 - Error Handler: AI failure / database failure -> safe customer message + team alert + log. Never confirms an order.
const inp = $input.first().json || {};
const ex = (n) => { try { return $(n).isExecuted; } catch (e) { return false; } };
const raw = inp.error;
let err = typeof raw === 'string' ? raw : (raw && (raw.message || raw.description)) || 'unknown error';
err = String(err).replace(/(Bearer\s+)\S+/g, '$1***').replace(/(access_token=)[^&\s]+/g, '$1***').replace(/(key=)[^&\s]+/g, '$1***').slice(0, 800);
let stage = 'ai_intent';
if (ex('20x - Cancel Order')) stage = 'cancel_order';
else if (ex('21u - Update Existing Order')) stage = 'update_order';
else if (ex('21 - Save Order')) stage = 'save_order';
const msg = $('02 - Detect Message Type').first().json;
let clean = {};
try { clean = $('08 - Clean Transcript').first().json; } catch (e) { clean = {}; }
let d = {};
try { d = $('14 - Order State Manager').first().json.draft || {}; } catch (e) { d = {}; }
const CUSTOMER = {
  ai_intent: 'هلا بيك حبيبي 🌹 لحظات وراح يرد عليك واحد من فريقنا.',
  save_order: 'حبيبي صار خلل بسيط وما تثبت الطلب بعد 🌹 فريقنا وصله إشعار وراح يتواصل وياك حتى يثبته.',
  update_order: 'حبيبي صار خلل بسيط وما انحفظ التعديل بعد 🌹 فريقنا وصله إشعار وراح يتواصل وياك.',
  cancel_order: 'حبيبي صار خلل بسيط وما انلغى الطلب بعد 🌹 فريقنا وصله إشعار وراح يتابع وياك.'
};
const STAGE_AR = { ai_intent: 'فهم رسالة الزبون (AI)', save_order: 'حفظ طلب جديد', update_order: 'تعديل طلب', cancel_order: 'إلغاء طلب' };
const lines = ['⚠️ خطأ بنظام AI SALES AGENT', 'المرحلة:', STAGE_AR[stage], '💬 واتساب الزبون:', msg.wa_from, '📝 رسالته:', String(clean.customer_text || msg.text || '-').slice(0, 500)];
if (stage !== 'ai_intent') lines.push('📦 بيانات الطلب (يرجى تثبيتها يدوياً):', [d.order_id, d.product_name, d.color, d.size, d.quantity ? 'x' + d.quantity : '', d.total ? 'المجموع ' + d.total : '', d.customer_name, d.phone, d.province, d.area, d.landmark].filter(Boolean).join(' | '));
lines.push('الخطأ:', err);
return [{ json: { stage, customer_text: CUSTOMER[stage], team_message: lines.join('\n'), error_message: err, log_error: stage.toUpperCase() + '_FAILED: ' + err, log_level: 'ERROR' } }];
'''

C['24b'] = r'''// 24b - Team Notify Failed: Telegram / WhatsApp team notification failed after retries -> critical log
const j = $input.first().json || {};
const e = j.error;
const m = typeof e === 'string' ? e : (e && (e.message || e.description)) || 'unknown';
return [{ json: { log_error: ('TEAM_NOTIFY_FAILED: ' + m).replace(/(Bearer\s+)\S+/g, '$1***').replace(/(bot)[0-9]+:[A-Za-z0-9_-]+/g, '$1***').slice(0, 1000), log_level: 'CRITICAL' } }];
'''

C['25a'] = r'''// 25a - Build Log Entry: one structured log row per step outcome. Never logs tokens / keys / secrets.
const get = (n) => { try { return $(n).isExecuted ? $(n).first().json : null; } catch (e) { return null; } };
const msg = get('02 - Detect Message Type') || {};
const ctx = get('05 - Get Conversation State') || {};
const clean = get('08 - Clean Transcript') || {};
const ext = get('10 - Extract Customer Data') || {};
const osm = get('14 - Order State Manager') || {};
const fin = get('15b - Compose Final Reply') || {};
const conf = get('20 - Order Confirmation') || {};
const err = get('24 - Error Handler') || {};
const inj = $input.first().json || {};
const injErr = inj.log_error || (inj.error ? (typeof inj.error === 'string' ? inj.error : (inj.error.message || JSON.stringify(inj.error))) : '');
const scrub = (s) => String(s || '').replace(/(Bearer\s+)\S+/g, '$1***').replace(/(access_token=)[^&\s]+/g, '$1***').replace(/(key=)[^&\s]+/g, '$1***').replace(/(bot)[0-9]+:[A-Za-z0-9_-]+/g, '$1***');
let response = fin.reply_text || '';
if (conf.customer_text) response = conf.customer_text;
if (err.customer_text) response = err.customer_text;
if (ctx.handoff_active && !osm.action) response = '(silent - human handoff active)';
const voiceFailed = clean.voice_failed ? 'عذراً حبيبي، الصوت ما واضح عندي 🌹 ممكن تعيد البصمة؟' : '';
const errorText = injErr || err.log_error || (clean.voice_failed ? 'VOICE_UNCLEAR: ' + (clean.media_error || '') : '') || (fin.ai_failed ? 'AI_RESPONSE_FAILED_FALLBACK_USED' : '');
return [{ json: {
  message_id: msg.message_id || '',
  store_id: (ctx.store && ctx.store.store_id) || '',
  customer_id: (ctx.customer && ctx.customer.customer_id) || '',
  message_type: msg.message_type || '',
  transcript: scrub(clean.customer_text || msg.text || '').slice(0, 4000),
  intent: (ext.intents || []).join(','),
  extracted_data: scrub(JSON.stringify(ext.entities || {})).slice(0, 4000),
  product: (osm.product && osm.product.product_id) || '',
  price: (osm.draft && typeof osm.draft.total === 'number') ? osm.draft.total : null,
  order_state: conf.order_id ? 'ORDER_CONFIRMED' : (get('20y - Build Cancel Notice') ? 'ORDER_CANCELLED' : (osm.next_state || ctx.state || '')),
  order_id: conf.order_id || (osm.draft && osm.draft.order_id) || '',
  response: scrub(response || voiceFailed).slice(0, 4000),
  error: scrub(errorText).slice(0, 2000),
  level: inj.log_level || (errorText ? 'ERROR' : 'INFO')
} }];
'''
