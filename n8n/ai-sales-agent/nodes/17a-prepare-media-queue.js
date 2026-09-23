// 17a - Prepare Media Queue: one item per image / video to send (from sa_product_media)
const s = $('14 - Order State Manager').first().json;
return (s.media_to_send || []).filter(m => m.url).map(m => ({ json: { media_type: m.media_type, url: m.url, caption: String(m.caption || '').slice(0, 900) } }));
