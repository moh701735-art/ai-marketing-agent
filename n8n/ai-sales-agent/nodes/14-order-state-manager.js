// 14 - Order State Manager: the business brain. Conversation state machine + order draft + actions.
const ctx = $('05 - Get Conversation State').first().json;
const clean = $('08 - Clean Transcript').first().json;
const ext = $('10 - Extract Customer Data').first().json;
const pl = $('11 - Product Lookup').first().json;
const pc = $('13 - Price Calculator').first().json;
const lastOrder = $('05e - Get Last Order').all().map(i => i.json).find(r => r && r.order_id) || null;

const parseOffers = (s) => {
  const out = {};
  if (!s) return out;
  let obj = null;
  if (typeof s === 'object') obj = s; else { try { obj = JSON.parse(s); } catch (e) { obj = null; } }
  if (obj && typeof obj === 'object') { Object.keys(obj).forEach(k => { const q = parseInt(k, 10); const v = Number(obj[k]); if (q > 0 && v >= 0) out[q] = v; }); return out; }
  String(s).split(/[,،;\n]/).forEach(part => { const m = part.match(/(\d+)\s*[=:]\s*(\d+)/); if (m) out[parseInt(m[1], 10)] = Number(m[2]); });
  return out;
};
// Optional per-color price/offer override, e.g. {"اسود":{"price":15000,"offers":{"2":25000}}}. Colors not listed use the product's own price/quantity_offers.
const parseColorPricing = (s) => {
  if (!s) return {};
  let obj = null;
  if (typeof s === 'object') obj = s; else { try { obj = JSON.parse(s); } catch (e) { obj = null; } }
  return (obj && typeof obj === 'object') ? obj : {};
};
// Pricing rule: exact quantity offer if defined, otherwise the biggest offer tier <= quantity + base price for the remaining pieces.
const calc = (p, q, color) => {
  if (!p || p.price === null || p.price === undefined || !(q >= 1)) return null;
  const override = color ? parseColorPricing(p.color_pricing)[color] : null;
  const offers = parseOffers(override ? override.offers : p.quantity_offers);
  const basePrice = override && override.price !== undefined ? Number(override.price) : Number(p.price);
  const base = offers[1] !== undefined ? offers[1] : basePrice;
  if (offers[q] !== undefined) return { quantity: q, total: offers[q], unit_price: base, offer_applied: q > 1, rule: 'exact_offer_' + q };
  const tiers = Object.keys(offers).map(Number).filter(t => t > 1 && t <= q).sort((a, b) => b - a);
  if (tiers.length) { const t = tiers[0]; return { quantity: q, total: offers[t] + (q - t) * base, unit_price: base, offer_applied: true, rule: 'tier_' + t + '_plus_base' }; }
  return { quantity: q, total: q * base, unit_price: base, offer_applied: false, rule: 'base_price' };
};

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
      // one combined answer to "المنطقة وأقرب نقطة دالة" covers both fields unless the customer clearly gave two different values
      if (has(draft.area) && !has(draft.landmark)) draft.landmark = draft.area;
      else if (has(draft.landmark) && !has(draft.area)) draft.area = draft.landmark;
      if (ext.phone_invalid) facts.invalid_phone = ext.phone_raw;
      if (ext.province_unmatched) facts.province_unmatched = ext.province_unmatched;
    }

    if (ordering) {
      const dp = productById(draft.product_id);
      CUSTOMER_FIELDS.forEach(k => { const src = k === 'customer_name' ? (ctx.customer.name || ctx.customer.whatsapp_name) : ctx.customer[k]; if (!has(draft[k]) && has(src)) draft[k] = src; });
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
        const pr = calc(dp, q, draft.color);
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

// ---- media to send (images / video from sa_product_media only) — staged reveal: featured colors first, then the rest
const FEATURED_COLORS = ['أسود', 'بني'];
const media = [];
if (action === 'reply' && ['ai', 'review'].includes(replyMode) && product) {
  const allColorNames = list(product.colors);
  const featuredNames = allColorNames.filter(c => FEATURED_COLORS.some(f => norm(f) === norm(c)));
  const otherNames = allColorNames.filter(c => !featuredNames.some(f => norm(f) === norm(c)));
  const colorPref = (pl.color && pl.color.value) || (draft.product_id === product.product_id ? draft.color : null);
  const imgs = (pc.images || []).slice();
  const stage = (meta.image_stage && meta.image_stage[product.product_id]) || null;
  const setStage = (s) => { meta.image_stage = Object.assign({}, meta.image_stage, { [product.product_id]: s }); };
  const wantsAllColors = ext.wants_images && /كل/.test(clean.customer_text || '') && /لون/.test(clean.customer_text || '');

  if (colorPref) {
    // a specific color was named -> just that color's images (or all, if none match), normal behaviour
    if (ext.wants_images) {
      const match = imgs.filter(m => norm(m.color) === norm(colorPref));
      const chosen = (match.length ? match : imgs).slice(0, 10);
      if (chosen.length) chosen.forEach(m => media.push({ media_type: 'image', url: m.url, caption: m.caption || '' }));
      else facts.no_images = true;
    } else if ((I.has('PRICE_INQUIRY') || I.has('PRODUCT_INQUIRY')) && imgs.length && !meta.images_sent_for.includes(product.product_id)) {
      const match = imgs.filter(m => norm(m.color) === norm(colorPref));
      const chosen = match.length ? match[0] : imgs[0];
      media.push({ media_type: 'image', url: chosen.url, caption: chosen.caption || '' });
    }
  } else if (wantsAllColors) {
    // customer explicitly asked for every color -> send everything at once, no staging
    imgs.forEach(m => media.push({ media_type: 'image', url: m.url, caption: m.caption || '' }));
    facts.pitch_stage = 'all_colors';
    setStage('remaining');
  } else if (ext.wants_images || I.has('COLOR_INQUIRY')) {
    // no specific color named: reveal featured colors first, then the rest on the next such request
    if (stage === 'featured' && otherNames.length) {
      const remainingImgs = imgs.filter(m => otherNames.some(c => norm(c) === norm(m.color)));
      remainingImgs.forEach(m => media.push({ media_type: 'image', url: m.url, caption: m.caption || '' }));
      facts.pitch_stage = 'remaining_colors';
      facts.other_colors_shown = otherNames.join('، ');
      setStage('remaining');
    } else if (stage !== 'remaining') {
      const featuredImgs = imgs.filter(m => featuredNames.some(c => norm(c) === norm(m.color)));
      featuredImgs.forEach(m => media.push({ media_type: 'image', url: m.url, caption: m.caption || '' }));
      facts.pitch_stage = 'featured_colors';
      facts.featured_colors = featuredNames.join('، ');
      facts.other_colors_available = otherNames.join('، ');
      setStage('featured');
    } else {
      imgs.slice(0, 10).forEach(m => media.push({ media_type: 'image', url: m.url, caption: m.caption || '' }));
    }
  } else if ((I.has('PRICE_INQUIRY') || I.has('PRODUCT_INQUIRY')) && imgs.length && !meta.images_sent_for.includes(product.product_id)) {
    // first unsolicited pitch for this product: lead with the featured colors only
    const featuredImgs = imgs.filter(m => featuredNames.some(c => norm(c) === norm(m.color)));
    (featuredImgs.length ? featuredImgs : imgs.slice(0, 1)).forEach(m => media.push({ media_type: 'image', url: m.url, caption: m.caption || '' }));
    facts.pitch_stage = 'featured_colors';
    facts.featured_colors = featuredNames.join('، ');
    facts.other_colors_available = otherNames.join('، ');
    if (!stage) setStage('featured');
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
else if (I.has('SHIPPING_INQUIRY')) facts.shipping_table = ctx.shipping.filter(s => s.fee !== null).slice(0, 20).map(s => s.province + ' ' + fmt(s.fee) + (s.delivery_days ? ' (' + s.delivery_days + ')' : '')).join(' | ') || 'غير محدد';
// delivery time is usually the same for every province -> surface it directly even before the customer's province is known
if (I.has('SHIPPING_INQUIRY') || priceAsked) {
  const uniqueDays = Array.from(new Set(ctx.shipping.map(s => s.delivery_days).filter(Boolean)));
  if (uniqueDays.length === 1 && !facts.shipping) facts.delivery_time = uniqueDays[0];
}
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
