// 19 - Order Review: deterministic templates (review summary / handoff / cancellation). No AI here.
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
