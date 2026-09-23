// 25a - Build Log Entry: one structured log row per step outcome. Never logs tokens / keys / secrets.
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
