// 20 - Order Confirmation: runs ONLY after the order was saved successfully in sa_orders
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
