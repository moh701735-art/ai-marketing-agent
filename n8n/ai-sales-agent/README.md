# AI SALES AGENT — وكيل مبيعات واتساب

Workflow بـ n8n اسمه `AI SALES AGENT` (ID: `NH8o3rIdbrc56jLg`). يرد على زبائن واتساب باللهجة العراقية، ويفهم النص والبصمات الصوتية والصور والفيديو والملفات والموقع. يرسل صور وفيديو المنتج، ويحسب الأسعار والعروض من قاعدة البيانات، ويجمع بيانات الزبون، ويثبت الطلب ويرسله لفريق المبيعات.

## المبدأ الأساسي: AI مقابل Business Logic

| الذكاء الاصطناعي | الـ Workflow وقاعدة البيانات |
|---|---|
| **Gemini:** تحويل البصمة لنص، وتحليل الصور والفيديو والملفات | السعر والعروض (`13 - Price Calculator`) |
| **Claude (09):** فهم اللهجة والنوايا واستخراج البيانات | المخزون، التوصيل، حالة المحادثة (`14 - Order State Manager`) |
| **Claude (15):** كتابة رد طبيعي من معطيات موثقة فقط | ملخص الطلب (قالب ثابت `19`)، Order ID، حفظ الطلب، إشعار الفريق |

## المسار

```
01 WhatsApp Webhook → 02 Detect Message Type → 03 Check Duplicate (message_id)
→ 04 Store / Customer / Catalog / Shipping → 05 Conversation State
→ [Voice/Image/Video/Doc] 06 Get Media URL → 06b Download → 07 Gemini (STT / تحليل)
→ 08 Clean Transcript → 09 Claude Intent + Entities → 10 Validate → 11 Product Lookup
→ 12 Media Lookup → 13 Price Calculator → 14 Order State Manager → 19 Order Review
→ 15 Claude Reply → 14c Save Customer → 14d Route Action
   ├─ reply   → 16 Send Text → 17/18 Send Image/Video
   ├─ confirm → 21 Save Order → 21b Order ID → 21c CONFIRMED → 21d Stock → 20 → 16c + Team
   ├─ update  → 21u Update Order → 20 → 16c + Team
   ├─ cancel  → 20x CANCELLED → 20z Restore Stock → 20y → 16x + Team
   └─ handoff → 22h → 16h + Team
Team: 22p → 22a (telegram / whatsapp / both) → 22 Telegram / 23 WhatsApp
Errors: 24 Error Handler → 24a Fallback + Team     Logs: 25a → 25 sa_logs
```

## قاعدة البيانات (n8n Data Tables)

| الجدول | الغرض |
|---|---|
| `sa_stores` | إعدادات كل متجر: `phone_number_id` (`*` يعني الافتراضي)، `notify_channel`، `telegram_chat_id`، `team_whatsapp_numbers`، `handoff_hours`، `default_product_id` |
| `sa_products` | `product_id`، `product_name`، `aliases`، `description`، `price`، `colors`، `sizes`، `stock`، `quantity_offers` (مثل `{"1":15000,"2":25000}`)، `shipping_information`، `return_information`، `notes`، `active` |
| `sa_product_media` | `product_id`، `media_type` (image/video)، `url` (رابط https مباشر)، `caption`، `color`، `sort_order`، `active` |
| `sa_shipping` | `province`، `aliases`، `fee`، `delivery_days` (إذا `fee` فارغ، الفريق يأكد التوصيل) |
| `sa_customers` | سجل الزبون: البيانات، `conversation_state`، `draft_order`، `recent_messages`، `handoff_until` |
| `sa_orders` | الطلبات: `order_id`، بيانات الزبون والمنتج، `quantity`، `product_price`، `shipping_fee`، `total`، `status` |
| `sa_processed_messages` | منع معالجة نفس الرسالة مرتين |
| `sa_logs` | سجل كل رسالة (بدون مفاتيح أو توكنات) |

**قاعدة التسعير:** إذا موجود عرض بنفس الكمية يُطبق مباشرة. إذا ما موجود، يُطبق أكبر عرض أقل من الكمية، والقطع الباقية بالسعر الأساسي.

## حالات الطلب

`PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED` أو `CANCELLED`.
الفريق يغيّر `PROCESSING` / `SHIPPED` / `DELIVERED` من الجدول. إذا الطلب بهاي الحالات والزبون طلب تعديل أو إلغاء، المحادثة تتحول لموظف.

## الاختبار المحلي

```bash
python3 -c "import sys,json;sys.path.insert(0,'.');import codes;json.dump(codes.C,open('codes.json','w'),ensure_ascii=False)"
node tests/simulate-conversation.js
```

يشغّل منطق النودات (05→20) على سيناريوهات الاختبار السبعة، ويكمل مسار الطلب كامل: جمع البيانات، الملخص، التأكيد، التعديل، الإلغاء، والتحويل لموظف.

## الملفات

- `nodes/*.js`: كود كل Code Node.
- `nodes/prompt-*.txt`: الـ Prompts.
- `workflow.json`: نسخة من الـ Workflow.
- `build.py`: يولّد عمليات التحديث لـ n8n.
