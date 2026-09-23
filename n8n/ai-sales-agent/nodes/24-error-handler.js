// 24 - Error Handler: AI failure / database failure -> safe customer message + team alert + log. Never confirms an order.
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
