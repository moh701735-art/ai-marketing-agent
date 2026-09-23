// 17c - Media Send Failed: log only (retries already happened on the send node)
const items = $input.all().map(i => i.json || {});
const msgs = items.map(j => { const e = j.error; return typeof e === 'string' ? e : (e && (e.message || e.description)) || 'unknown'; });
return [{ json: { log_error: ('MEDIA_SEND_FAILED: ' + msgs.join(' || ')).replace(/(Bearer\s+)\S+/g, '$1***').replace(/(access_token=)[^&\s]+/g, '$1***').slice(0, 1500), log_level: 'WARN' } }];
