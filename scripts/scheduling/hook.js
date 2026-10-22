//__LIB__
const ctx = $('تحقق قبل التنفيذ').first().json;
const saved = $json || {};
const sch = Array.isArray(ctx.schedule) ? ctx.schedule : [];
const okCreate = ctx.action === 'create' && sch.length && saved.campaign_id && /^(true|1)$/i.test(String(saved.success));
if (!okCreate) return [];
const chat = String($('قراءة رسالة تليجرام').first().json.chatId || '');
const platform = /tik/i.test(String(saved.platform || '')) ? 'tiktok' : 'meta';
const advertiser = platform === 'tiktok' ? String(ctx.tiktokAdvertiserId || '').replace(/\D/g, '') : '';
if (platform === 'tiktok' && !advertiser) return [];
const { evs, enforce } = buildEvents(sch);
if (!evs.length) return [];
const name = saved.name || ctx.campaign_name || '';
const base = { phone: chat, client: ctx.client || saved.client || '', platform, advertiser_id: advertiser, campaign_id: saved.campaign_id, campaign_name: name };
const msg = '⏰ سجّلت جدولة للحملة "' + (name || saved.campaign_id) + '":\n' + describe(evs, enforce).join('\n') + '\n\nيتنفذ تلقائياً بدقة ±5 دقائق بتوقيت العراق. للعرض: "شنو المجدول"، وللإلغاء: "الغ جدولة حملة ' + (name || 'X') + '".';
return evs.map(e => ({ json: { ...mkRow(e, base), finalMessage: msg } }));
