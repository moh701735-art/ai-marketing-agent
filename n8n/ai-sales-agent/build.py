import json, sys
sys.path.insert(0, '.')
from codes import C
from prompts import P, INTENT_SCHEMA

T = {
    'stores': 'xgLdRjDHxAqa8JfA', 'products': 'JgIhtXO5KkyjPxQt', 'media': '8xCI4vhVI4ijtq9c', 'shipping': 'vUId3lHD5cML0m7f',
    'customers': 'Xw12SCMPxzHJtTBj', 'orders': 'RhEVlUgGjiFdO2js', 'processed': '3trgdy1rN6NGL306', 'logs': 'Nvn5UWRp7V6Phfg8',
}
WA = {'whatsAppApi': {'id': 'G5NjAl0hVWMzWzxb', 'name': 'WhatsApp account'}}
CLAUDE = {'anthropicApi': {'id': 'g9xVoJn4zzarniXM', 'name': 'Anthropic account'}}
GEM = {'googlePalmApi': {'id': 'hnxWgFPUTMlnvMhH', 'name': 'Google Gemini(PaLM) Api account'}}
TG = {'telegramApi': {'name': 'Telegram Bot - فريق المبيعات'}}
GEM_MODEL = {'__rl': True, 'mode': 'id', 'value': 'models/gemini-3.6-flash'}
CLAUDE_MODEL = {'__rl': True, 'mode': 'list', 'value': 'claude-sonnet-5', 'cachedResultName': 'Claude Sonnet 5'}
MSG = "$('02 - Detect Message Type').first().json"
PHONE_ID = "={{ " + MSG + ".phone_number_id }}"
TO = "={{ " + MSG + ".wa_from }}"

nodes, settings, conns = [], {}, []


def add(name, typ, ver, params, pos, creds=None, **st):
    n = {'name': name, 'type': typ, 'typeVersion': ver, 'parameters': params, 'position': pos}
    if creds:
        n['credentials'] = creds
    nodes.append(n)
    if st:
        settings[name] = st


def code(name, key, pos, **st):
    add(name, 'n8n-nodes-base.code', 2, {'mode': 'runOnceForAllItems', 'language': 'javaScript', 'jsCode': C[key]}, pos, **st)


def dt(table):
    return {'__rl': True, 'mode': 'id', 'value': T[table]}


def schema(cols):
    return [{'id': c, 'displayName': c, 'required': False, 'defaultMatch': False, 'display': True, 'type': t, 'canBeUsedToMatch': True, 'readOnly': False, 'removed': False} for c, t in cols]


def columns(values, cols):
    return {'mappingMode': 'defineBelow', 'value': values, 'matchingColumns': [], 'schema': schema(cols), 'attemptToConvertTypes': False, 'convertFieldsToString': False}


def cond_eq(left, right, typ='string'):
    return {'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'loose', 'version': 2},
            'conditions': [{'leftValue': left, 'rightValue': right, 'operator': {'type': typ, 'operation': 'equals'}}], 'combinator': 'and'}


def cond_true(left):
    return {'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'loose', 'version': 2},
            'conditions': [{'leftValue': left, 'rightValue': '', 'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True}}], 'combinator': 'and'}


def rule(key, conditions):
    return {'conditions': conditions, 'renameOutput': True, 'outputKey': key}


def wa_text(name, text_expr, pos, **st):
    add(name, 'n8n-nodes-base.whatsApp', 1.1, {'resource': 'message', 'operation': 'send', 'phoneNumberId': PHONE_ID,
        'recipientPhoneNumber': TO, 'messageType': 'text', 'textBody': text_expr, 'additionalFields': {}}, pos, WA, **st)


def c(src, dst, out=0, typ='main'):
    conns.append((src, dst, out, typ))


RETRY = dict(retryOnFail=True, maxTries=3, waitBetweenTries=1500)
SAFE_SEND = dict(onError='continueRegularOutput', **RETRY)

CUSTOMER_COLS = [('customer_id', 'string'), ('store_id', 'string'), ('whatsapp_number', 'string'), ('whatsapp_name', 'string'), ('name', 'string'), ('phone', 'string'),
                 ('province', 'string'), ('area', 'string'), ('landmark', 'string'), ('last_product', 'string'), ('last_order', 'string'), ('conversation_state', 'string'),
                 ('draft_order', 'string'), ('recent_messages', 'string'), ('handoff_until', 'dateTime')]


def customer_upsert(name, pos):
    vals = {c0: "={{ $json.customer_update." + c0 + " }}" for c0, _ in CUSTOMER_COLS}
    vals['handoff_until'] = "={{ $json.customer_update.handoff_until || null }}"
    add(name, 'n8n-nodes-base.dataTable', 1.1, {'resource': 'row', 'operation': 'upsert', 'dataTableId': dt('customers'),
        'filters': {'conditions': [{'keyName': 'customer_id', 'condition': 'eq', 'keyValue': '={{ $json.customer_update.customer_id }}'}]},
        'columns': columns(vals, CUSTOMER_COLS), 'options': {}}, pos, onError='continueRegularOutput', **RETRY)


# ---------------- intake
code('02 - Detect Message Type', '02', [260, 400])
add('03 - Check Duplicate', 'n8n-nodes-base.dataTable', 1.1, {'resource': 'row', 'operation': 'rowNotExists', 'dataTableId': dt('processed'),
    'filters': {'conditions': [{'keyName': 'message_id', 'condition': 'eq', 'keyValue': '={{ $json.message_id }}'}]}}, [520, 400], retryOnFail=True, maxTries=2, waitBetweenTries=1000)
add('03b - Mark Message Processed', 'n8n-nodes-base.dataTable', 1.1, {'resource': 'row', 'operation': 'insert', 'dataTableId': dt('processed'),
    'columns': columns({'message_id': "={{ " + MSG + ".message_id }}", 'store_id': "={{ " + MSG + ".phone_number_id }}", 'whatsapp_number': "={{ " + MSG + ".wa_from }}", 'message_type': "={{ " + MSG + ".message_type }}"},
                       [('message_id', 'string'), ('store_id', 'string'), ('whatsapp_number', 'string'), ('message_type', 'string')]), 'options': {}}, [780, 400], onError='continueRegularOutput', **RETRY)
LOAD = dict(alwaysOutputData=True, executeOnce=True, retryOnFail=True, maxTries=2, waitBetweenTries=1000)
add('04 - Get Store Settings', 'n8n-nodes-base.dataTable', 1.1, {'resource': 'row', 'operation': 'get', 'dataTableId': dt('stores'), 'matchType': 'anyCondition',
    'filters': {'conditions': [{'keyName': 'phone_number_id', 'condition': 'eq', 'keyValue': "={{ " + MSG + ".phone_number_id }}"}, {'keyName': 'phone_number_id', 'condition': 'eq', 'keyValue': '*'}]}, 'returnAll': True}, [1040, 400], **LOAD)
add('04b - Get Customer', 'n8n-nodes-base.dataTable', 1.1, {'resource': 'row', 'operation': 'get', 'dataTableId': dt('customers'),
    'filters': {'conditions': [{'keyName': 'whatsapp_number', 'condition': 'eq', 'keyValue': "={{ " + MSG + ".wa_from }}"}]}, 'returnAll': True}, [1300, 400], **LOAD)
add('04c - Load Product Catalog', 'n8n-nodes-base.dataTable', 1.1, {'resource': 'row', 'operation': 'get', 'dataTableId': dt('products'), 'returnAll': True}, [1560, 400], **LOAD)
add('04d - Load Shipping Table', 'n8n-nodes-base.dataTable', 1.1, {'resource': 'row', 'operation': 'get', 'dataTableId': dt('shipping'), 'returnAll': True}, [1820, 400], **LOAD)
code('05 - Get Conversation State', '05', [2080, 400])
add('05b - Human Handoff Active?', 'n8n-nodes-base.if', 2.2, {'conditions': cond_true('={{ $json.handoff_active }}'), 'options': {}}, [2340, 400])
add('05e - Get Last Order', 'n8n-nodes-base.dataTable', 1.1, {'resource': 'row', 'operation': 'get', 'dataTableId': dt('orders'),
    'filters': {'conditions': [{'keyName': 'order_id', 'condition': 'eq', 'keyValue': "={{ $('05 - Get Conversation State').first().json.last_order_id || '__none__' }}"}]}, 'limit': 1}, [2600, 480], **LOAD)
MT = "={{ " + MSG + ".message_type }}"
add('05d - Route By Message Type', 'n8n-nodes-base.switch', 3.2, {'mode': 'rules', 'rules': {'values': [
    rule('media', {'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'loose', 'version': 2}, 'conditions': [{'leftValue': MT, 'rightValue': '^(VOICE|IMAGE|VIDEO|DOCUMENT)$', 'operator': {'type': 'string', 'operation': 'regex'}}], 'combinator': 'and'})]},
    'options': {'fallbackOutput': 'extra', 'renameFallbackOutput': 'text / location'}}, [2860, 480])

# ---------------- media / voice
add('06 - Get Media URL', 'n8n-nodes-base.whatsApp', 1.1, {'resource': 'media', 'operation': 'mediaUrlGet', 'mediaGetId': "={{ " + MSG + ".media_id }}"}, [3120, 700], WA, onError='continueErrorOutput', retryOnFail=True, maxTries=3, waitBetweenTries=1000)
add('06b - Download Voice / Media', 'n8n-nodes-base.httpRequest', 4.2, {'method': 'GET', 'url': '={{ $json.url }}', 'authentication': 'predefinedCredentialType', 'nodeCredentialType': 'whatsAppApi',
    'options': {'response': {'response': {'responseFormat': 'file', 'outputPropertyName': 'data'}}, 'timeout': 60000}}, [3380, 700], WA, onError='continueErrorOutput', retryOnFail=True, maxTries=3, waitBetweenTries=1500)
add('06c - Media Kind', 'n8n-nodes-base.switch', 3.2, {'mode': 'rules', 'rules': {'values': [rule(k, cond_eq(MT, k)) for k in ['VOICE', 'IMAGE', 'VIDEO', 'DOCUMENT']]}, 'options': {}}, [3640, 700])
GEM_ST = dict(onError='continueErrorOutput', retryOnFail=True, maxTries=2, waitBetweenTries=2000)
add('07 - Speech To Text', '@n8n/n8n-nodes-langchain.googleGemini', 1.2, {'resource': 'audio', 'operation': 'analyze', 'modelId': GEM_MODEL, 'text': P['stt'], 'inputType': 'binary', 'binaryPropertyName': 'data', 'simplify': True, 'options': {'maxOutputTokens': 1500}}, [3900, 560], GEM, **GEM_ST)
add('07b - Analyze Customer Image', '@n8n/n8n-nodes-langchain.googleGemini', 1.2, {'resource': 'image', 'operation': 'analyze', 'modelId': GEM_MODEL, 'text': P['image'], 'inputType': 'binary', 'binaryPropertyName': 'data', 'simplify': True, 'options': {'maxOutputTokens': 400}}, [3900, 720], GEM, **GEM_ST)
add('07c - Analyze Customer Video', '@n8n/n8n-nodes-langchain.googleGemini', 1.2, {'resource': 'video', 'operation': 'analyze', 'modelId': GEM_MODEL, 'text': P['video'], 'inputType': 'binary', 'binaryPropertyName': 'data', 'simplify': True, 'options': {'maxOutputTokens': 800}}, [3900, 880], GEM, **GEM_ST)
add('07d - Analyze Customer Document', '@n8n/n8n-nodes-langchain.googleGemini', 1.2, {'resource': 'document', 'operation': 'analyze', 'modelId': GEM_MODEL, 'text': P['document'], 'inputType': 'binary', 'binaryPropertyName': 'data', 'simplify': True, 'options': {'maxOutputTokens': 400}}, [3900, 1040], GEM, **GEM_ST)
code('07e - Media Processing Failed', '07e', [3900, 1200])
code('08 - Clean Transcript', '08', [4160, 480])
add('08b - Voice Unclear?', 'n8n-nodes-base.if', 2.2, {'conditions': cond_true('={{ $json.voice_failed }}'), 'options': {}}, [4420, 480])
wa_text('16b - Send Voice Retry Message', 'عذراً حبيبي، الصوت ما واضح عندي 🌹 ممكن تعيد البصمة؟', [4680, 280], **SAFE_SEND)

# ---------------- AI understanding
add('09a - Claude (Intent)', '@n8n/n8n-nodes-langchain.lmChatAnthropic', 1.6, {'model': CLAUDE_MODEL, 'options': {'maxTokensToSample': 900}}, [4620, 720], CLAUDE)
add('09b - Intent JSON Schema', '@n8n/n8n-nodes-langchain.outputParserStructured', 1.3, {'schemaType': 'manual', 'inputSchema': json.dumps(INTENT_SCHEMA, ensure_ascii=False, indent=2)}, [4780, 720])
add('09 - AI Intent Detection', '@n8n/n8n-nodes-langchain.chainLlm', 1.9, {'promptType': 'define', 'text': P['intent_user'], 'hasOutputParser': True,
    'messages': {'messageValues': [{'type': 'SystemMessagePromptTemplate', 'message': P['intent_system']}]}}, [4680, 480], onError='continueErrorOutput', retryOnFail=True, maxTries=2, waitBetweenTries=2000)
code('10 - Extract Customer Data', '10', [4940, 480])
code('11 - Product Lookup', '11', [5200, 480])
add('12 - Product Media Lookup', 'n8n-nodes-base.dataTable', 1.1, {'resource': 'row', 'operation': 'get', 'dataTableId': dt('media'), 'matchType': 'allConditions',
    'filters': {'conditions': [{'keyName': 'product_id', 'condition': 'eq', 'keyValue': "={{ $json.product_id || '__none__' }}"}, {'keyName': 'store_id', 'condition': 'eq', 'keyValue': "={{ $('05 - Get Conversation State').first().json.store.store_id }}"}]}, 'returnAll': True}, [5460, 480], **LOAD)
code('13 - Price Calculator', '13', [5720, 480])
code('14 - Order State Manager', '14', [5980, 480])
code('19 - Order Review', '19', [6240, 480])
add('14b - Needs AI Reply?', 'n8n-nodes-base.if', 2.2, {'conditions': cond_eq("={{ $('14 - Order State Manager').first().json.reply_mode }}", 'ai'), 'options': {}}, [6500, 480])
add('15a - Claude (Response)', '@n8n/n8n-nodes-langchain.lmChatAnthropic', 1.6, {'model': CLAUDE_MODEL, 'options': {'maxTokensToSample': 600}}, [6760, 540], CLAUDE)
add('15 - Generate AI Response', '@n8n/n8n-nodes-langchain.chainLlm', 1.9, {'promptType': 'define', 'text': P['reply_user'], 'hasOutputParser': False,
    'messages': {'messageValues': [{'type': 'SystemMessagePromptTemplate', 'message': P['reply_system']}]}}, [6760, 340], onError='continueErrorOutput', retryOnFail=True, maxTries=2, waitBetweenTries=2000)
code('15b - Compose Final Reply', '15b', [7020, 480])
customer_upsert('14c - Update Customer Record', [7280, 480])
ACT = "={{ $('15b - Compose Final Reply').first().json.action }}"
add('14d - Route Action', 'n8n-nodes-base.switch', 3.2, {'mode': 'rules', 'rules': {'values': [rule(k, cond_eq(ACT, k)) for k in ['confirm_order', 'update_order', 'cancel_order', 'handoff']]},
    'options': {'fallbackOutput': 'extra', 'renameFallbackOutput': 'reply'}}, [7540, 480])

# ---------------- reply + media
wa_text('16 - Send WhatsApp Text', "={{ $('15b - Compose Final Reply').first().json.reply_text }}", [7800, 900], **SAFE_SEND)
code('17a - Prepare Media Queue', '17a', [8060, 900])
add('17b - Media Type', 'n8n-nodes-base.switch', 3.2, {'mode': 'rules', 'rules': {'values': [rule('image', cond_eq('={{ $json.media_type }}', 'image')), rule('video', cond_eq('={{ $json.media_type }}', 'video'))]}, 'options': {}}, [8320, 900])
MEDIA_ST = dict(onError='continueErrorOutput', retryOnFail=True, maxTries=3, waitBetweenTries=2000)
for nm, mt, y in [('17 - Send Product Image', 'image', 820), ('18 - Send Product Video', 'video', 1000)]:
    add(nm, 'n8n-nodes-base.whatsApp', 1.1, {'resource': 'message', 'operation': 'send', 'phoneNumberId': PHONE_ID, 'recipientPhoneNumber': TO, 'messageType': mt,
        'mediaPath': 'useMediaLink', 'mediaLink': '={{ $json.url }}', 'additionalFields': {'mediaCaption': '={{ $json.caption }}'}}, [8580, y], WA, **MEDIA_ST)
code('17c - Media Send Failed', '17c', [8840, 900])

# ---------------- order confirmation
S14 = "$('14 - Order State Manager').first().json"
ORDER_COLS = [('order_id', 'string'), ('store_id', 'string'), ('customer_id', 'string'), ('whatsapp_number', 'string'), ('customer_name', 'string'), ('phone', 'string'), ('province', 'string'),
              ('area', 'string'), ('landmark', 'string'), ('product_id', 'string'), ('product_name', 'string'), ('color', 'string'), ('size', 'string'), ('quantity', 'number'),
              ('product_price', 'number'), ('shipping_fee', 'number'), ('total', 'number'), ('status', 'string'), ('notes', 'string')]


def order_values(status, order_id_expr):
    d = S14 + ".draft"
    v = {k: "={{ " + d + "." + k + " }}" for k in ['customer_name', 'phone', 'province', 'area', 'landmark', 'product_id', 'product_name', 'color', 'size']}
    v.update({'order_id': order_id_expr, 'store_id': "={{ " + S14 + ".customer_update.store_id }}", 'customer_id': "={{ " + S14 + ".customer_update.customer_id }}",
              'whatsapp_number': "={{ " + MSG + ".wa_from }}", 'quantity': "={{ Number(" + d + ".quantity) }}", 'product_price': "={{ " + d + ".product_price }}",
              'shipping_fee': "={{ " + d + ".shipping_fee }}", 'total': "={{ " + d + ".total }}", 'status': status,
              'notes': "={{ " + d + ".shipping_fee === null || " + d + ".shipping_fee === undefined ? 'shipping_fee_pending' : '' }}"})
    return v


ORD_ST = dict(onError='continueErrorOutput', retryOnFail=True, maxTries=3, waitBetweenTries=1000)
add('21 - Save Order', 'n8n-nodes-base.dataTable', 1.1, {'resource': 'row', 'operation': 'insert', 'dataTableId': dt('orders'), 'columns': columns(order_values('PENDING', ''), ORDER_COLS), 'options': {}}, [7800, -200], **ORD_ST)
code('21b - Generate Order ID', '21b', [8060, -200], onError='continueErrorOutput')
add('21c - Mark Order Confirmed', 'n8n-nodes-base.dataTable', 1.1, {'resource': 'row', 'operation': 'update', 'dataTableId': dt('orders'),
    'filters': {'conditions': [{'keyName': 'id', 'condition': 'eq', 'keyValue': '={{ $json.row_id }}'}]},
    'columns': columns({'order_id': '={{ $json.order_id }}', 'status': 'CONFIRMED'}, [('order_id', 'string'), ('status', 'string')]), 'options': {}}, [8320, -200], **ORD_ST)
STOCK_COLS = [('stock', 'number')]
add('21d - Update Stock', 'n8n-nodes-base.dataTable', 1.1, {'resource': 'row', 'operation': 'update', 'dataTableId': dt('products'),
    'filters': {'conditions': [{'keyName': 'id', 'condition': 'eq', 'keyValue': "={{ " + S14 + ".stock_update.row_id }}"}]},
    'columns': columns({'stock': "={{ " + S14 + ".stock_update.new_stock }}"}, STOCK_COLS), 'options': {}}, [8580, -200], onError='continueRegularOutput', retryOnFail=True, maxTries=2, waitBetweenTries=1000)
add('21u - Update Existing Order', 'n8n-nodes-base.dataTable', 1.1, {'resource': 'row', 'operation': 'update', 'dataTableId': dt('orders'),
    'filters': {'conditions': [{'keyName': 'order_id', 'condition': 'eq', 'keyValue': "={{ " + S14 + ".draft.order_id }}"}]},
    'columns': columns({k: v for k, v in order_values('CONFIRMED', "={{ " + S14 + ".draft.order_id }}").items()}, ORDER_COLS), 'options': {}}, [8060, 0], **ORD_ST)
code('20 - Order Confirmation', '20', [8840, -200])
customer_upsert('20b - Save Confirmed State', [9100, -200])
wa_text('16c - Send Order Confirmation', "={{ $('20 - Order Confirmation').first().json.customer_text }}", [9360, -340], **SAFE_SEND)

# ---------------- cancel
add('20x - Cancel Order', 'n8n-nodes-base.dataTable', 1.1, {'resource': 'row', 'operation': 'update', 'dataTableId': dt('orders'),
    'filters': {'conditions': [{'keyName': 'order_id', 'condition': 'eq', 'keyValue': "={{ " + S14 + ".draft.order_id }}"}]},
    'columns': columns({'status': 'CANCELLED'}, [('status', 'string')]), 'options': {}}, [7800, 200], **ORD_ST)
add('20z - Restore Stock', 'n8n-nodes-base.dataTable', 1.1, {'resource': 'row', 'operation': 'update', 'dataTableId': dt('products'),
    'filters': {'conditions': [{'keyName': 'id', 'condition': 'eq', 'keyValue': "={{ " + S14 + ".stock_restore.row_id }}"}]},
    'columns': columns({'stock': "={{ " + S14 + ".stock_restore.new_stock }}"}, STOCK_COLS), 'options': {}}, [8060, 200], onError='continueRegularOutput', retryOnFail=True, maxTries=2, waitBetweenTries=1000)
code('20y - Build Cancel Notice', '20y', [8320, 200])
customer_upsert('20w - Save Cancelled State', [8580, 200])
wa_text('16x - Send Cancel Confirmation', "={{ $('20y - Build Cancel Notice').first().json.customer_text }}", [8840, 300], **SAFE_SEND)

# ---------------- handoff
code('22h - Build Handoff Notice', '22h', [7800, 480])
wa_text('16h - Send Handoff Reply', "={{ $('15b - Compose Final Reply').first().json.reply_text }}", [8060, 560], **SAFE_SEND)

# ---------------- team notifications
code('22p - Prepare Team Message', '22p', [9620, 100])
add('22a - Route Team Channel', 'n8n-nodes-base.switch', 3.2, {'mode': 'rules', 'rules': {'values': [
    rule('telegram', cond_true("={{ ['telegram','both'].includes($json.channel) }}")),
    rule('whatsapp', cond_true("={{ ['whatsapp','both'].includes($json.channel) }}"))]}, 'options': {'allMatchingOutputs': True}}, [9880, 100])
TEAM_ST = dict(onError='continueErrorOutput', retryOnFail=True, maxTries=3, waitBetweenTries=3000)
add('22 - Send Order To Telegram', 'n8n-nodes-base.telegram', 1.2, {'resource': 'message', 'operation': 'sendMessage', 'chatId': '={{ $json.telegram_chat_id }}',
    'text': "={{ $json.team_message.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;') }}", 'additionalFields': {'appendAttribution': False, 'parse_mode': 'HTML'}}, [10140, 0], TG, **TEAM_ST)
code('23a - Split Team Numbers', '23a', [10140, 200])
add('23 - Send Order To WhatsApp Group', 'n8n-nodes-base.whatsApp', 1.1, {'resource': 'message', 'operation': 'send', 'phoneNumberId': PHONE_ID, 'recipientPhoneNumber': '={{ $json.to }}',
    'messageType': 'text', 'textBody': '={{ $json.text }}', 'additionalFields': {}}, [10400, 200], WA, **TEAM_ST)
code('24b - Team Notify Failed', '24b', [10660, 100])

# ---------------- errors + logging
code('24 - Error Handler', '24', [7800, 1300])
wa_text('24a - Send Fallback To Customer', "={{ $('24 - Error Handler').first().json.customer_text }}", [8060, 1300], **SAFE_SEND)
code('25a - Build Log Entry', '25a', [10920, 700])
LOG_COLS = [('message_id', 'string'), ('store_id', 'string'), ('customer_id', 'string'), ('message_type', 'string'), ('transcript', 'string'), ('intent', 'string'), ('extracted_data', 'string'),
            ('product', 'string'), ('price', 'number'), ('order_state', 'string'), ('order_id', 'string'), ('response', 'string'), ('error', 'string'), ('level', 'string')]
add('25 - Logging', 'n8n-nodes-base.dataTable', 1.1, {'resource': 'row', 'operation': 'insert', 'dataTableId': dt('logs'),
    'columns': columns({k: '={{ $json.' + k + ' }}' for k, _ in LOG_COLS}, LOG_COLS), 'options': {}}, [11180, 700], onError='continueRegularOutput', retryOnFail=True, maxTries=2, waitBetweenTries=1000)

# ---------------- sticky notes
STICKY = [
    ('Sticky - Setup', """## AI SALES AGENT — طريقة التشغيل
1. **المنتجات:** عبّي جدول `sa_products` (السعر + `quantity_offers` مثل `{"1":15000,"2":25000}`).
2. **الصور والفيديو:** جدول `sa_product_media` (روابط مباشرة https تنتهي بـ jpg/png/mp4).
3. **التوصيل:** جدول `sa_shipping` — اكتب `fee` لكل محافظة.
4. **المتجر:** جدول `sa_stores` — `telegram_chat_id` و `notify_channel` (telegram / whatsapp / both).
5. **Telegram:** اربط Credential بنود **22 - Send Order To Telegram**.
6. فعّل الـ Workflow (Publish).

الأسعار والطلبات والحالات كلها من قاعدة البيانات — الذكاء الاصطناعي بس يفهم ويكتب الرد.""", [-40, -260], 620, 420, 4),
    ('Sticky - Voice', """## 🎤 مسار البصمة الصوتية
Voice → Get Media URL → Download → **Gemini Speech To Text** (لهجة عراقية) → Clean Transcript → Claude Intent → Business Logic → Reply.
إذا الصوت ما واضح: رسالة إعادة البصمة.""", [3080, 1320], 520, 200, 5),
    ('Sticky - Business', """## 🧠 AI ↔ Business Logic
- **09 (Claude):** يفهم اللهجة والنية ويستخرج البيانات فقط.
- **11-14 (Code + DB):** المنتج، السعر، العروض، التوصيل، المخزون، حالة الطلب.
- **15 (Claude):** يكتب رد طبيعي من المعطيات الموثقة فقط.
- **19:** ملخص الطلب (قالب ثابت، بدون AI).""", [4600, 900], 560, 260, 6),
    ('Sticky - Orders', """## 🛍️ الطلبات
الطلب يتثبت فقط بعد: ملخص → الزبون يكتب «تأكيد» → حفظ ناجح بـ `sa_orders` → Order ID → إشعار الفريق.
إذا فشل الحفظ: ما يتأكد للزبون + تنبيه للفريق.""", [7760, -560], 560, 220, 3),
]
for nm, content, pos, w, h, color in STICKY:
    nodes.append({'name': nm, 'type': 'n8n-nodes-base.stickyNote', 'typeVersion': 1, 'parameters': {'content': content, 'width': w, 'height': h, 'color': color}, 'position': pos})

# ---------------- connections
TRIG = '01 - WhatsApp Webhook'
for a, b in [(TRIG, '02 - Detect Message Type'), ('02 - Detect Message Type', '03 - Check Duplicate'), ('03 - Check Duplicate', '03b - Mark Message Processed'),
             ('03b - Mark Message Processed', '04 - Get Store Settings'), ('04 - Get Store Settings', '04b - Get Customer'), ('04b - Get Customer', '04c - Load Product Catalog'),
             ('04c - Load Product Catalog', '04d - Load Shipping Table'), ('04d - Load Shipping Table', '05 - Get Conversation State'), ('05 - Get Conversation State', '05b - Human Handoff Active?')]:
    c(a, b)
c('05b - Human Handoff Active?', '25a - Build Log Entry', 0)
c('05b - Human Handoff Active?', '05e - Get Last Order', 1)
c('05e - Get Last Order', '05d - Route By Message Type')
c('05d - Route By Message Type', '06 - Get Media URL', 0)
c('05d - Route By Message Type', '08 - Clean Transcript', 1)
c('06 - Get Media URL', '06b - Download Voice / Media', 0); c('06 - Get Media URL', '07e - Media Processing Failed', 1)
c('06b - Download Voice / Media', '06c - Media Kind', 0); c('06b - Download Voice / Media', '07e - Media Processing Failed', 1)
for i, n in enumerate(['07 - Speech To Text', '07b - Analyze Customer Image', '07c - Analyze Customer Video', '07d - Analyze Customer Document']):
    c('06c - Media Kind', n, i); c(n, '08 - Clean Transcript', 0); c(n, '07e - Media Processing Failed', 1)
c('07e - Media Processing Failed', '08 - Clean Transcript')
c('08 - Clean Transcript', '08b - Voice Unclear?')
c('08b - Voice Unclear?', '16b - Send Voice Retry Message', 0); c('08b - Voice Unclear?', '09 - AI Intent Detection', 1)
c('16b - Send Voice Retry Message', '25a - Build Log Entry')
c('09a - Claude (Intent)', '09 - AI Intent Detection', 0, 'ai_languageModel')
c('09b - Intent JSON Schema', '09 - AI Intent Detection', 0, 'ai_outputParser')
c('09 - AI Intent Detection', '10 - Extract Customer Data', 0); c('09 - AI Intent Detection', '24 - Error Handler', 1)
for a, b in [('10 - Extract Customer Data', '11 - Product Lookup'), ('11 - Product Lookup', '12 - Product Media Lookup'), ('12 - Product Media Lookup', '13 - Price Calculator'),
             ('13 - Price Calculator', '14 - Order State Manager'), ('14 - Order State Manager', '19 - Order Review'), ('19 - Order Review', '14b - Needs AI Reply?')]:
    c(a, b)
c('14b - Needs AI Reply?', '15 - Generate AI Response', 0); c('14b - Needs AI Reply?', '15b - Compose Final Reply', 1)
c('15a - Claude (Response)', '15 - Generate AI Response', 0, 'ai_languageModel')
c('15 - Generate AI Response', '15b - Compose Final Reply', 0); c('15 - Generate AI Response', '15b - Compose Final Reply', 1)
c('15b - Compose Final Reply', '14c - Update Customer Record'); c('14c - Update Customer Record', '14d - Route Action')
c('14d - Route Action', '21 - Save Order', 0); c('14d - Route Action', '21u - Update Existing Order', 1); c('14d - Route Action', '20x - Cancel Order', 2)
c('14d - Route Action', '22h - Build Handoff Notice', 3); c('14d - Route Action', '16 - Send WhatsApp Text', 4)
c('16 - Send WhatsApp Text', '17a - Prepare Media Queue'); c('16 - Send WhatsApp Text', '25a - Build Log Entry')
c('17a - Prepare Media Queue', '17b - Media Type')
c('17b - Media Type', '17 - Send Product Image', 0); c('17b - Media Type', '18 - Send Product Video', 1)
c('17 - Send Product Image', '17c - Media Send Failed', 1); c('18 - Send Product Video', '17c - Media Send Failed', 1)
c('17c - Media Send Failed', '25a - Build Log Entry')
c('21 - Save Order', '21b - Generate Order ID', 0); c('21 - Save Order', '24 - Error Handler', 1)
c('21b - Generate Order ID', '21c - Mark Order Confirmed', 0); c('21b - Generate Order ID', '24 - Error Handler', 1)
c('21c - Mark Order Confirmed', '21d - Update Stock', 0); c('21c - Mark Order Confirmed', '24 - Error Handler', 1)
c('21d - Update Stock', '20 - Order Confirmation')
c('21u - Update Existing Order', '20 - Order Confirmation', 0); c('21u - Update Existing Order', '24 - Error Handler', 1)
c('20 - Order Confirmation', '20b - Save Confirmed State')
c('20b - Save Confirmed State', '22p - Prepare Team Message'); c('20b - Save Confirmed State', '16c - Send Order Confirmation')
c('16c - Send Order Confirmation', '25a - Build Log Entry')
c('20x - Cancel Order', '20z - Restore Stock', 0); c('20x - Cancel Order', '24 - Error Handler', 1)
c('20z - Restore Stock', '20y - Build Cancel Notice'); c('20y - Build Cancel Notice', '20w - Save Cancelled State')
c('20w - Save Cancelled State', '22p - Prepare Team Message'); c('20w - Save Cancelled State', '16x - Send Cancel Confirmation')
c('16x - Send Cancel Confirmation', '25a - Build Log Entry')
c('22h - Build Handoff Notice', '16h - Send Handoff Reply'); c('22h - Build Handoff Notice', '22p - Prepare Team Message')
c('16h - Send Handoff Reply', '25a - Build Log Entry')
c('22p - Prepare Team Message', '22a - Route Team Channel')
c('22a - Route Team Channel', '22 - Send Order To Telegram', 0); c('22a - Route Team Channel', '23a - Split Team Numbers', 1)
c('22 - Send Order To Telegram', '24b - Team Notify Failed', 1)
c('23a - Split Team Numbers', '23 - Send Order To WhatsApp Group'); c('23 - Send Order To WhatsApp Group', '24b - Team Notify Failed', 1)
c('24b - Team Notify Failed', '25a - Build Log Entry')
c('24 - Error Handler', '24a - Send Fallback To Customer')
c('24a - Send Fallback To Customer', '22p - Prepare Team Message'); c('24a - Send Fallback To Customer', '25a - Build Log Entry')
c('25a - Build Log Entry', '25 - Logging')

# sanity
names = {n['name'] for n in nodes} | {TRIG}
for s, d, o, t in conns:
    assert s in names and d in names, (s, d)
assert len(names) == len(nodes) + 1

OLD = ['رسائل نصية فقط', 'بيانات المنتج', 'وكيل المبيعات', 'Claude', 'ذاكرة المحادثة', 'send_product_image', 'create_order', 'notify_owner', 'إرسال الرد للزبون', 'Sticky Note c4c7dabc']
ops_remove = [{'type': 'removeNode', 'nodeName': n} for n in OLD]
ops_rename = [{'type': 'renameNode', 'oldName': 'استلام رسالة واتساب', 'newName': TRIG},
              {'type': 'setNodePosition', 'nodeName': TRIG, 'position': [0, 400]},
              {'type': 'setWorkflowMetadata', 'name': 'AI SALES AGENT', 'description': 'وكيل مبيعات واتساب متكامل: يفهم النص والبصمات والصور باللهجة العراقية، يرسل صور/فيديو المنتج، يحسب الأسعار والعروض من قاعدة البيانات، يجمع بيانات الزبون، يثبت الطلب ويرسله للفريق.'}]
ops_add = [{'type': 'addNode', 'node': n} for n in nodes]
ops_set = [{'type': 'setNodeSettings', 'nodeName': k, 'settings': v} for k, v in settings.items()]
ops_conn = [{'type': 'addConnection', 'source': s, 'target': d, 'sourceIndex': o, 'targetIndex': 0, 'connectionType': t} for s, d, o, t in conns]

batches = []
first = ops_remove + ops_rename
cur = first[:]
for op in ops_add:
    if len(cur) >= 100:
        batches.append(cur); cur = []
    cur.append(op)
batches.append(cur); cur = []
for op in ops_set + ops_conn:
    if len(cur) >= 100:
        batches.append(cur); cur = []
    cur.append(op)
if cur:
    batches.append(cur)
for i, b in enumerate(batches):
    json.dump(b, open('batch%d.json' % i, 'w'), ensure_ascii=False, separators=(',', ':'))
    print('batch', i, len(b), 'ops', len(json.dumps(b, ensure_ascii=False)), 'chars')
print('nodes', len(nodes), 'settings', len(settings), 'conns', len(conns))
json.dump([{'type': n['type'], 'typeVersion': n['typeVersion'], 'parameters': n['parameters'], 'name': n['name']} for n in nodes if n['type'] != 'n8n-nodes-base.stickyNote'], open('validate.json', 'w'), ensure_ascii=False, separators=(',', ':'))
