#!/usr/bin/env bash
# تشغيل/إيقاف «منشئ الجمهور الذكي» (smart_audience) وضبط عتبات التقييم، بثانية واحدة بدون إعادة تشغيل.
#   bash ops/smart-audience-sync.sh on|off                      يضبط SMART_AUDIENCE_ENABLED بـ deploy/.env + القاعدة (كل العملاء)
#   bash ops/smart-audience-sync.sh                              يزامن القيمة الموجودة بـ deploy/.env
#   bash ops/smart-audience-sync.sh tenant <slug> on|off         إيقاف/تشغيل انتقائي لعميل (features.smart_audience)
#   bash ops/smart-audience-sync.sh threshold <small> <medium> <large> <very_large>   عتبات تقييم الجمهور (AUDIENCE_*_THRESHOLD؛ تقييم بمنتصف نطاق تيك توك)
#   bash ops/smart-audience-sync.sh status
# OFF = يختفي الزر وأي sa:* و/audience ويرجع السلوك القديم بالضبط. الافتراضي بعد التثبيت = OFF.
set -euo pipefail
. "$(dirname "$0")/../deploy/cron/lib.sh"
J() { psql_c -d "$DB_CENTRAL" -c "$1"; }
case "${1:-sync}" in
  tenant)
    S="${2:?slug}"; V="${3:?on|off}"; [[ "$S" =~ ^[a-z0-9][a-z0-9-]{1,48}$ ]] || { echo "slug غير صالح"; exit 1; }
    case "$V" in on) B=true;; off) B=false;; *) echo "on|off"; exit 1;; esac
    N=$(J "UPDATE core.tenants SET features = features || '{\"smart_audience\": $B}'::jsonb WHERE slug='$S' RETURNING 1" | head -1)
    [ -n "$N" ] && echo "smart_audience للعميل $S: $V" || { echo "ما لقيت العميل $S"; exit 1; }; exit 0;;
  threshold)
    for i in 2 3 4 5; do [[ "${!i:-}" =~ ^[0-9]{1,12}$ ]] || { echo "الاستعمال: threshold <small> <medium> <large> <very_large> (أرقام)"; exit 1; }; done
    [ "$2" -lt "$3" ] && [ "$3" -lt "$4" ] && [ "$4" -lt "$5" ] || { echo "لازم small < medium < large < very_large"; exit 1; }
    J "INSERT INTO smart_audience.settings (key, value) VALUES ('thresholds', '{\"small\": $2, \"medium\": $3, \"large\": $4, \"very_large\": $5}'::jsonb) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()" >/dev/null
    echo "عتبات التقييم: ضيق < $2 ≤ متوسط < $3 ≤ جيد < $4 ≤ واسع < $5 ≤ واسع جداً (حسب منتصف نطاق تيك توك)"; exit 0;;
  status)
    J "SELECT key, value FROM smart_audience.settings ORDER BY 1"; exit 0;;
  on|off)
    V=$([ "$1" = on ] && echo true || echo false)
    if grep -q '^SMART_AUDIENCE_ENABLED=' deploy/.env; then sed -i "s/^SMART_AUDIENCE_ENABLED=.*/SMART_AUDIENCE_ENABLED=$V/" deploy/.env; else printf '\nSMART_AUDIENCE_ENABLED=%s\n' "$V" >> deploy/.env; fi;;
  *)
    V=$(grep -m1 '^SMART_AUDIENCE_ENABLED=' deploy/.env | cut -d= -f2 | tr -d "\"' " || true); V="${V:-false}";;
esac
case "$V" in true|false) ;; *) echo "SMART_AUDIENCE_ENABLED لازم true أو false (الحالي: $V)"; exit 1;; esac
J "INSERT INTO smart_audience.settings (key, value) VALUES ('enabled', '$V'::jsonb) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()" >/dev/null
echo "smart_audience: $V (شغّال فوراً لكل العملاء، إلا من أُوقف انتقائياً)"
