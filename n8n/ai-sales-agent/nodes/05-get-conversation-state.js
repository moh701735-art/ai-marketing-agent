// 05 - Get Conversation State: builds the full context (store, customer, draft order, catalog, shipping)
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
recent.slice(-12).forEach(m => lines.push('- ' + (m.r === 'agent' ? 'الوكيل' : 'الزبون') + ': ' + safe(m.t)));
lines.push('catalog:');
products.slice(0, 300).forEach(p => lines.push('- product_id=' + p.product_id + ' | name=' + safe(p.product_name) + ' | aliases=' + safe(p.aliases) + ' | colors=' + safe(p.colors) + ' | sizes=' + safe(p.sizes)));
lines.push('provinces: ' + shipping.map(s => s.province).join('، '));

return [{ json: {
  msg, store, store_missing: storeMissing, products, shipping, customer, state, is_new_customer: isNew,
  handoff_active: handoffActive, draft, recent, last_order_id: customer.last_order || '', ai_context_text: lines.join('\n')
} }];
