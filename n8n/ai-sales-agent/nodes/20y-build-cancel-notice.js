// 20y - Build Cancel Notice: runs ONLY after the order status was set to CANCELLED in sa_orders
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
