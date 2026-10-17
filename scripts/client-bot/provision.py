#!/usr/bin/env python3
"""Turn a DUPLICATE of the clean template ("TEMPLATE - عميل جديد") into a client's bot.

Usage:
  python3 provision.py DETAILS_JSON CONFIG_JSON OUT_PREFIX
      -> writes OUT_PREFIX.<n>.json  (update_workflow operations, <=100 per file)
      -> writes OUT_PREFIX.verify.json (config for verify_clean.py)

DETAILS_JSON: n8n get_workflow_details of the duplicate.
CONFIG_JSON:
{
  "name": "عميل أحمد",
  "chat_id": "123456789",                  # client's Telegram numeric id
  "limit_iqd": 262,                         # optional, max cost per message
  "tables": {"<template table id>": "<client table id>", ...},   # all 11, see tables.json
  "credentials": {
    "telegramApi":      {"id": "...", "name": "..."},
    "httpHeaderAuth":   {"id": "...", "name": "..."},     # TikTok Access-Token of THIS client
    "facebookGraphApi": {"id": "...", "name": "..."} | null,
    "shared": ["<gemini credential id>", "<tiktok app secret credential id>"]   # allowed shared ones
  }
}
Placeholders written by template_fixes.py are replaced here (chat id, webhook paths, media key).
"""
import json, re, sys, uuid, secrets

det = json.load(open(sys.argv[1]))
cfg = json.load(open(sys.argv[2]))
prefix = sys.argv[3]
nodes = det['workflow']['nodes']
ops = []

def need(key):
    if not cfg.get(key):
        sys.exit(f"config is missing '{key}'")
for k in ('name', 'chat_id', 'tables', 'credentials'): need(k)
creds = cfg['credentials']
for k in ('telegramApi', 'httpHeaderAuth'):
    if not creds.get(k): sys.exit(f"credentials.{k} is required")

media_key = cfg.get('media_key') or secrets.token_hex(12)
repl = {
    '__CLIENT_CHAT_ID__': str(cfg['chat_id']),
    '__MEDIA_KEY__': media_key,
    '__TT_OAUTH_PATH__': str(uuid.uuid4()),
    '__FB_OAUTH_PATH__': str(uuid.uuid4()),
    '__WA_PATH__': str(uuid.uuid4()),
}

def walk(o):
    if isinstance(o, str):
        for k, v in repl.items(): o = o.replace(k, v)
        return o
    if isinstance(o, list): return [walk(x) for x in o]
    if isinstance(o, dict): return {k: walk(v) for k, v in o.items()}
    return o

ops.append({"type": "setWorkflowMetadata", "name": cfg['name']})
used_tables, used_creds = set(), set()
for n in nodes:
    p = n['parameters']
    # data tables
    if n['type'].endswith('dataTable'):
        v = p.get('dataTableId'); old = v.get('value') if isinstance(v, dict) else v
        new = cfg['tables'].get(old)
        if not new: sys.exit(f"no table mapping for template table {old} (node '{n['name']}')")
        ops.append({"type": "setNodeParameter", "nodeName": n['name'], "path": "/dataTableId/value", "value": new})
        used_tables.add(new)
    # credentials
    for key, cur in (n.get('credentials') or {}).items():
        new = creds.get(key)
        if new:
            ops.append({"type": "setNodeCredential", "nodeName": n['name'], "credentialKey": key, "credentialId": new['id'], "credentialName": new['name']})
            used_creds.add(new['id'])
        elif key == 'facebookGraphApi' and key in creds:      # client without Meta: never keep the template's Meta credential
            ops.append({"type": "setNodeParameter", "nodeName": n['name'], "path": "/authentication", "value": "none"})
        elif cur['id'] in creds.get('shared', []):
            used_creds.add(cur['id'])
        else:
            sys.exit(f"credential type {key} on node '{n['name']}' has no mapping and is not in credentials.shared")
    # placeholders (and cost cap) inside parameters
    q = walk(p)
    if cfg.get('limit_iqd') and n['name'].startswith('سقف التكلفة') and isinstance(q.get('jsCode'), str) and 'LIMIT_IQD = ' in q['jsCode']:
        q['jsCode'] = re.sub(r"LIMIT_IQD = \d+", "LIMIT_IQD = %d" % int(cfg['limit_iqd']), q['jsCode'])
    if q != p:
        ops.append({"type": "updateNodeParameters", "nodeName": n['name'], "replace": True, "parameters": q})

for i in range(0, len(ops), 100):
    json.dump(ops[i:i+100], open(f"{prefix}.{i//100}.json", 'w'), ensure_ascii=False, separators=(',', ':'))
json.dump({"chat_id": str(cfg['chat_id']), "tables": sorted(used_tables),
           "credentials": sorted(used_creds | {c['id'] for c in creds.values() if isinstance(c, dict)})},
          open(prefix + '.verify.json', 'w'))
print(f"ops={len(ops)} files={(len(ops)+99)//100} media_key={media_key}", file=sys.stderr)
