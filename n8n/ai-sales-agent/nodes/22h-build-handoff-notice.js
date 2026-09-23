// 22h - Build Handoff Notice: tells the team a customer needs a human (bot is paused for this customer)
const s = $('14 - Order State Manager').first().json;
const ctx = $('05 - Get Conversation State').first().json;
const clean = $('08 - Clean Transcript').first().json;
const REASON = { customer_request: 'الزبون طلب يحچي ويا موظف', order_locked_cancel: 'الزبون يريد يلغي طلب صار قيد التجهيز/الشحن', order_locked_change: 'الزبون يريد يعدل طلب صار قيد التجهيز/الشحن' };
const until = s.handoff_until ? new Date(s.handoff_until).toLocaleString('en-GB', { timeZone: 'Asia/Baghdad', hour12: false }) : '-';
const d = s.draft || {};
const team = ['🙋 تحويل لموظف بشري', 'السبب:', REASON[s.handoff_reason] || s.handoff_reason, '💬 واتساب:', ctx.msg.wa_from, '👤 الاسم:', ctx.customer.name || ctx.customer.whatsapp_name || '-', '📝 آخر رسالة:', clean.customer_text, '📦 الطلب الحالي:', d.order_id ? d.order_id + ' (' + (d.status || '') + ')' : (d.product_name ? d.product_name + ' x ' + (d.quantity || '?') : 'لا يوجد'), '⏳ الرد الآلي متوقف لهذا الزبون لحد:', until].join('\n');
return [{ json: { team_message: team } }];
