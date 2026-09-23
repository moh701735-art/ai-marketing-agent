// 07e - Media Processing Failed: download / Gemini error -> mark as failed (no secrets are kept)
const j = $input.first().json || {};
const e = j.error;
const m = typeof e === 'string' ? e : (e && (e.message || e.description)) || 'media processing error';
return [{ json: { media_failed: true, media_error: String(m).slice(0, 300) } }];
