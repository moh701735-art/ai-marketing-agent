// 08 - Clean Transcript: one clean customer_text regardless of message type (text / voice / image / video / document / location)
const msg = $('02 - Detect Message Type').first().json;
const inp = $input.first().json || {};
const AR = '٠١٢٣٤٥٦٧٨٩', FA = '۰۱۲۳۴۵۶۷۸۹';
const toWestern = (s) => String(s || '').replace(/[٠-٩]/g, d => String(AR.indexOf(d))).replace(/[۰-۹]/g, d => String(FA.indexOf(d)));
const clean = (s) => toWestern(s).replace(/[\u200B-\u200F\u202A-\u202E\u2066-\u2069]/g, '').replace(/[{}]/g, ' ').replace(/\s+/g, ' ').trim();
const pick = (j) => {
  if (!j) return '';
  if (typeof j === 'string') return j;
  if (typeof j.text === 'string') return j.text;
  if (j.content && Array.isArray(j.content.parts)) return j.content.parts.map(p => p.text || '').join(' ');
  if (Array.isArray(j.candidates) && j.candidates[0] && j.candidates[0].content && Array.isArray(j.candidates[0].content.parts)) return j.candidates[0].content.parts.map(p => p.text || '').join(' ');
  if (typeof j.output === 'string') return j.output;
  return '';
};
const isMedia = ['VOICE', 'IMAGE', 'VIDEO', 'DOCUMENT'].includes(msg.message_type);
let mediaFailed = !!inp.media_failed;
let mediaText = '';
if (isMedia && !mediaFailed) { mediaText = clean(pick(inp)); if (!mediaText) mediaFailed = true; }
const unclear = msg.message_type === 'VOICE' && (/\[?UNCLEAR\]?/i.test(mediaText) || mediaText.replace(/[^\p{L}\p{N}]/gu, '').length < 2);
const caption = clean(msg.caption);
let text = '';
switch (msg.message_type) {
  case 'TEXT': text = clean(msg.text); break;
  case 'VOICE': text = mediaText.replace(/\[?UNCLEAR\]?/ig, '').trim(); break;
  case 'IMAGE': text = (caption ? caption + ' ' : '') + (mediaFailed ? '[الزبون دز صورة وما كدرنا نحللها]' : '[الزبون دز صورة، وصفها: ' + mediaText + ']'); break;
  case 'VIDEO': text = (caption ? caption + ' ' : '') + (mediaFailed ? '[الزبون دز فيديو وما كدرنا نحلله]' : '[الزبون دز فيديو، محتواه: ' + mediaText + ']'); break;
  case 'DOCUMENT': text = (caption ? caption + ' ' : '') + (mediaFailed ? '[الزبون دز ملف ' + clean(msg.filename) + ' وما كدرنا نقراه]' : '[الزبون دز ملف ' + clean(msg.filename) + '، محتواه: ' + mediaText + ']'); break;
  case 'LOCATION': { const l = msg.location || {}; text = '[الزبون دز موقعه: ' + clean([l.name, l.address].filter(Boolean).join(' - ')) + ' (' + l.latitude + ', ' + l.longitude + ')]'; break; }
  default: text = '[الزبون دز رسالة من نوع ' + msg.raw_type + ']';
}
return [{ json: {
  customer_text: text.slice(0, 3000),
  input_source: msg.message_type,
  voice_failed: msg.message_type === 'VOICE' && (mediaFailed || unclear),
  media_failed: mediaFailed,
  media_error: String(inp.media_error || '').slice(0, 300),
  location: msg.location || null
} }];
