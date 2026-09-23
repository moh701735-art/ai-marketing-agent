// 15b - Compose Final Reply: picks AI text or template, falls back safely, appends to customer memory
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
