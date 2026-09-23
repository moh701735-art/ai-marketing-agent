// 10 - Extract Customer Data: validates / normalizes what the AI understood (AI never decides prices or orders)
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
