// 24b - Team Notify Failed: Telegram / WhatsApp team notification failed after retries -> critical log
const j = $input.first().json || {};
const e = j.error;
const m = typeof e === 'string' ? e : (e && (e.message || e.description)) || 'unknown';
return [{ json: { log_error: ('TEAM_NOTIFY_FAILED: ' + m).replace(/(Bearer\s+)\S+/g, '$1***').replace(/(bot)[0-9]+:[A-Za-z0-9_-]+/g, '$1***').slice(0, 1000), log_level: 'CRITICAL' } }];
