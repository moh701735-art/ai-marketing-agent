// 22p - Prepare Team Message: picks the notice produced by this run and the store's team channel
const ex = (n) => { try { return $(n).isExecuted; } catch (e) { return false; } };
let text = '';
for (const n of ['24 - Error Handler', '20 - Order Confirmation', '20y - Build Cancel Notice', '22h - Build Handoff Notice']) {
  if (ex(n)) { const j = $(n).first().json; if (j && j.team_message) { text = j.team_message; break; } }
}
if (!text) return [];
let store = {};
try { store = $('05 - Get Conversation State').first().json.store || {}; } catch (e) { store = {}; }
const channel = String(store.notify_channel || 'telegram').toLowerCase().trim();
const numbers = String(store.team_whatsapp_numbers || '').split(/[,،\s]+/).map(x => x.replace(/[^0-9]/g, '')).filter(Boolean);
return [{ json: { team_message: text.slice(0, 3900), channel, telegram_chat_id: String(store.telegram_chat_id || ''), team_numbers: numbers } }];
