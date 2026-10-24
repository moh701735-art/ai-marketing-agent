#!/usr/bin/env bash
# يشغّل اختبارات الـ Broker داخل venv معزول (حزمة cryptography من pip، لتفادي تعارض حزمة النظام).
set -euo pipefail
cd "$(dirname "$0")"
V="${BROKER_VENV:-/tmp/broker_venv}"
[ -x "$V/bin/python" ] || { python3 -m venv "$V" && "$V/bin/pip" install -q cryptography; }
"$V/bin/python" -m unittest discover -s tests -v 2>&1 | tail -n 40
