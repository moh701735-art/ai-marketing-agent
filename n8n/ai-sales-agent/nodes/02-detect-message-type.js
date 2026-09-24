// 02 - Detect Message Type: normalizes the WAHA (WhatsApp HTTP API) webhook payload into one clean message object
const raw = $input.first().json || {};
const v = raw.body || raw;
const ev = v.event || '';
const p = v.payload || {};
if (!['message', 'message.any'].includes(ev) || p.fromMe) return []; // ignore non-message events and our own outgoing messages
const rawFrom = String(p.from || '');
const chatId = rawFrom.includes('@') ? rawFrom : rawFrom + '@c.us';
// WhatsApp's privacy LID addressing (@lid) hides the real number in `from`; the real number (when WhatsApp discloses it) is in _data.key.remoteJidAlt
const altJid = String((p._data && p._data.key && p._data.key.remoteJidAlt) || '');
const waFrom = (altJid ? altJid.split('@')[0] : '') || rawFrom.split('@')[0];
const media = p.media || null;
const mime = (media && media.mimetype) || '';
const hasMedia = !!p.hasMedia && !!media && !!media.url;
let messageType = 'OTHER';
if (p.location) messageType = 'LOCATION';
else if (hasMedia) {
  if (mime.indexOf('audio') === 0) messageType = 'VOICE';
  else if (mime.indexOf('image') === 0) messageType = 'IMAGE';
  else if (mime.indexOf('video') === 0) messageType = 'VIDEO';
  else messageType = 'DOCUMENT';
} else if ((p.body || '').trim()) messageType = 'TEXT';
if (messageType === 'OTHER') return [];
const text = messageType === 'TEXT' ? (p.body || '') : '';
const caption = hasMedia ? (p.body || '') : '';
const location = p.location ? { latitude: p.location.latitude, longitude: p.location.longitude, name: p.location.name || '', address: p.location.address || '' } : null;
return [{ json: {
  message_id: p.id || '',
  wa_from: waFrom,
  chat_id: chatId,
  profile_name: (p._data && (p._data.notifyName || p._data.pushName)) || '',
  phone_number_id: String(v.session || 'default'),
  display_phone: '',
  raw_type: messageType.toLowerCase(),
  message_type: messageType,
  text, media_id: '', media_url: (media && media.url) || '', mime_type: mime, caption, filename: (media && media.filename) || '', location,
  reply_to: (p.replyTo && p.replyTo.id) || '',
  timestamp: p.timestamp || '',
  received_at: new Date().toISOString()
} }];
