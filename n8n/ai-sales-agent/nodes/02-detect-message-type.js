// 02 - Detect Message Type: normalizes the WhatsApp Cloud API payload into one clean message object
const v = $input.first().json || {};
const msg = (v.messages || [])[0];
if (!msg) return []; // status updates (sent/delivered/read) have no messages -> stop silently
if (msg.type === 'reaction' || msg.type === 'system' || msg.type === 'unsupported') return [];
const contact = (v.contacts || [])[0] || {};
const t = msg.type;
let text = '', mediaId = '', mime = '', caption = '', filename = '', location = null;
switch (t) {
  case 'text': text = (msg.text && msg.text.body) || ''; break;
  case 'audio': mediaId = msg.audio.id; mime = msg.audio.mime_type || ''; break;
  case 'image': mediaId = msg.image.id; mime = msg.image.mime_type || ''; caption = msg.image.caption || ''; break;
  case 'video': mediaId = msg.video.id; mime = msg.video.mime_type || ''; caption = msg.video.caption || ''; break;
  case 'document': mediaId = msg.document.id; mime = msg.document.mime_type || ''; caption = msg.document.caption || ''; filename = msg.document.filename || ''; break;
  case 'location': location = { latitude: msg.location.latitude, longitude: msg.location.longitude, name: msg.location.name || '', address: msg.location.address || '' }; break;
  case 'interactive': text = (msg.interactive.button_reply && msg.interactive.button_reply.title) || (msg.interactive.list_reply && msg.interactive.list_reply.title) || ''; break;
  case 'button': text = (msg.button && msg.button.text) || ''; break;
}
const KIND = { text: 'TEXT', interactive: 'TEXT', button: 'TEXT', audio: 'VOICE', image: 'IMAGE', video: 'VIDEO', document: 'DOCUMENT', location: 'LOCATION' };
return [{ json: {
  message_id: msg.id,
  wa_from: String(msg.from || ''),
  profile_name: (contact.profile && contact.profile.name) || '',
  phone_number_id: String((v.metadata && v.metadata.phone_number_id) || ''),
  display_phone: String((v.metadata && v.metadata.display_phone_number) || ''),
  raw_type: t,
  message_type: KIND[t] || 'OTHER',
  text, media_id: mediaId || '', mime_type: mime, caption, filename, location,
  reply_to: (msg.context && msg.context.id) || '',
  timestamp: msg.timestamp || '',
  received_at: new Date().toISOString()
} }];
