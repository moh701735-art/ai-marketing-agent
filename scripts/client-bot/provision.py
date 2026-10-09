#!/usr/bin/env python3
"""Build update_workflow operations that turn a DUPLICATE of the template client bot
(workflow "عميل احمد فوريفر") into a new client's bot.

Usage:
  python3 provision.py DETAILS_JSON CONFIG_JSON > ops.json   # then apply ops.json in batches of <=100

DETAILS_JSON: output of n8n get_workflow_details for the duplicated workflow.
CONFIG_JSON (see docs/new-client-bot.md):
{
  "name": "عميل مسلم",
  "chat_id": "<client telegram numeric id>",
  "bot_token": "<client bot token>",
  "limit_iqd": 262,
  "tables": {"<template table id>": "<new table id>", ...},
  "credentials": {
    "telegramApi":       {"id": "...", "name": "..."},
    "httpHeaderAuth":    {"id": "...", "name": "..."},
    "facebookGraphApi":  {"id": "...", "name": "..."} | null
  }
}
Template values are auto-detected from the details file (old chat id, bot token, limit).
"""
import json, re, sys

det = json.load(open(sys.argv[1]))
cfg = json.load(open(sys.argv[2]))
nodes = det['workflow']['nodes']
ops = [{"type": "setWorkflowMetadata", "name": cfg["name"]}]

def dumps(o): return json.dumps(o, ensure_ascii=False)

# 1) data tables
for n in nodes:
    if n['type'] == 'n8n-nodes-base.dataTable':
        v = n['parameters'].get('dataTableId', {})
        old = v.get('value') if isinstance(v, dict) else v
        if old in cfg['tables']:
            ops.append({"type": "setNodeParameter", "nodeName": n['name'], "path": "/dataTableId/value", "value": cfg['tables'][old]})
        elif old:
            sys.stderr.write(f"WARN table {old} in node '{n['name']}' has no mapping\n")

# 2) credentials per type (+ Meta isolation)
for n in nodes:
    for key, cred in (n.get('credentials') or {}).items():
        new = cfg['credentials'].get(key)
        if new:
            ops.append({"type": "setNodeCredential", "nodeName": n['name'], "credentialKey": key, "credentialId": new['id'], "credentialName": new['name']})
        elif key == 'facebookGraphApi':
            # no Meta for this client: never leave the template's Meta credential working
            ops.append({"type": "setNodeParameter", "nodeName": n['name'], "path": "/authentication", "value": "none"})

# 3) chat id / bot token / cost cap
old_chat = None
old_token = None
for n in nodes:
    s = dumps(n['parameters'])
    m = re.search(r"\"chatId\": \"=\{\{ String\('(\d+)'\) \}\}\"", s)
    if m:
        old_chat = m.group(1)
        ops.append({"type": "setNodeParameter", "nodeName": n['name'], "path": "/chatId", "value": "={{ String('%s') }}" % cfg['chat_id']})
    code = n['parameters'].get('jsCode')
    if not code: continue
    new_code = code
    t = re.search(r"BOT_TOKEN = '(\d+:[\w-]+)'", code)
    if t:
        old_token = t.group(1)
        new_code = new_code.replace(old_token, cfg['bot_token'])
    if 'LIMIT_IQD = ' in new_code and n['name'].startswith('سقف التكلفة'):
        new_code = re.sub(r"LIMIT_IQD = \d+", "LIMIT_IQD = %d" % cfg['limit_iqd'], new_code)
    if new_code != code:
        ops.append({"type": "updateNodeParameters", "nodeName": n['name'], "replace": True, "parameters": {**n['parameters'], "jsCode": new_code}})

sys.stderr.write(f"template chat id={old_chat}, bot token node patched={'yes' if old_token else 'NO'}, ops={len(ops)}\n")
print(json.dumps({"operations": ops}, ensure_ascii=False))
