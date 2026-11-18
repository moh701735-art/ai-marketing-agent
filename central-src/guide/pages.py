# -*- coding: utf-8 -*-
"""📘 دليل الاستخدام داخل البوت (ثابت، بدون Broker ولا قاعدة بيانات) بنفس نمط snapchat/pages.py:
build(b, w, sw, idx, reply, CRT) يضيف عقدتين: GD: render (كود) ← GD: reply، ويربط المخرج idx من عقدة Command.
callback_data: gd:m (المواضيع) | gd:<موضوع>:<رقم الصفحة>. الأمر النصي: /guide أو /دليل. يعدّل نفس الرسالة عند الضغط على زر."""
import importlib.util, json, os

_cp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'content.py')
_s = importlib.util.spec_from_file_location('guide_content', _cp); _m = importlib.util.module_from_spec(_s); _s.loader.exec_module(_m)
DATA = {'intro': _m.INTRO, 'topics': [{'k': k, 'e': e, 't': t, 'p': pages} for (k, e, t, pages) in _m.TOPICS]}

JS_RENDER = r"""
const G = __DATA__;
const d = $('Route').first().json;
const isCb = !!d.cb;
const parts = isCb ? String(d.cb).split(':') : ['gd', 'm'];
const op = parts[1] || 'm';
const home = [{ t: '🏠 الرئيسية', c: 'h' }];
const T = G.topics.find(x => x.k === op);
let text, kb;
if (!T) {
  text = G.intro;
  kb = G.topics.map(x => [{ t: x.e + ' ' + x.t, c: 'gd:' + x.k + ':0' }]);
  kb.push(home);
} else {
  const n = Math.min(T.p.length - 1, Math.max(0, parseInt(parts[2] || '0', 10) || 0));
  text = '📘 ' + T.t + ' — صفحة ' + (n + 1) + ' من ' + T.p.length + '\n\n' + T.p[n];
  const nav = [];
  if (n > 0) nav.push({ t: '◀️ السابق', c: 'gd:' + T.k + ':' + (n - 1) });
  if (n < T.p.length - 1) nav.push({ t: 'التالي ▶️', c: 'gd:' + T.k + ':' + (n + 1) });
  kb = [];
  if (nav.length) kb.push(nav);
  kb.push([{ t: '📘 المواضيع', c: 'gd:m' }, { t: '🏠 الرئيسية', c: 'h' }]);
}
return [{ json: { ctx: d.ctx, chatId: d.chatId, text: String(text).slice(0, 3800), keyboard: kb.slice(0, 8), edit: isCb } }];
""".replace('__DATA__', json.dumps(DATA, ensure_ascii=False))

JS_REPLY = r"""
const r = $input.first().json;
return [{ json: { ctx: r.ctx, chatId: r.chatId, text: r.text, keyboard: r.keyboard, edit: r.edit } }];
"""


def build(b, w, sw, idx, reply, CRT):
    code = b.code
    render = code(w, "GD: render", JS_RENDER)
    out = reply("GD: reply", JS_REPLY)
    w.link(sw, render, idx)
    w.chain(render, out)
