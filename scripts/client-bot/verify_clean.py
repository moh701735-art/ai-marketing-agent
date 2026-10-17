#!/usr/bin/env python3
"""Handover gate for a client bot workflow: fails if anything that belongs to the owner,
the template, or another client is still inside the workflow, or if a known error pattern exists.

Usage:
  python3 verify_clean.py DETAILS_JSON [CONFIG_JSON]

DETAILS_JSON: output of n8n get_workflow_details (file saved by the tool is fine).
CONFIG_JSON (optional, all keys optional):
{
  "chat_id": "<client telegram id>",
  "tables": ["<table id>", ...],            # tables that belong to this client
  "credentials": ["<credential id>", ...],  # credentials allowed in this workflow
  "allow_ids": ["<literal id>", ...]        # platform constants allowed to stay (see PLATFORM_IDS)
}
Exit code 0 = clean, 1 = findings. Prints one line per finding.
"""
import json, re, sys

# Platform constants (not client data): Meta interest/behavior ids and the shared TikTok app id.
PLATFORM_IDS = {
    '6003279598823', '6003127206524', '6003389760112', '6003526234370',
    '6015683810783', '6020530281783', '6002714898572', '7688235455380193301',
}

det = json.load(open(sys.argv[1]))
cfg = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else {}
w = det['workflow']
nodes = w['nodes']
allow = PLATFORM_IDS | set(cfg.get('allow_ids', []))
findings = []

def bad(code, node, msg): findings.append(f"{code} | {node} | {msg}")
def dumps(o): return json.dumps(o, ensure_ascii=False)

for n in nodes:
    p, name, s = n['parameters'], n['name'], dumps(n['parameters'])
    # C1/C2 bot tokens anywhere (URL, code, bodies)
    if re.search(r'[0-9]{8,10}:[A-Za-z0-9_-]{30,}', s):
        bad('C1-TOKEN', name, 'Telegram bot token is written inside the node')
    # C3 literal 15-19 digit ids (pages, advertisers, business centers, pixels ...)
    for m in sorted(set(re.findall(r'(?<![0-9.])[0-9]{15,19}(?![0-9.])', s))):
        if m not in allow:
            bad('C3-FOREIGN-ID', name, f'literal id {m} (owner/template data)')
    # C4 literal chat ids (9-10 digits) that are not this client's
    chat = str(cfg.get('chat_id', ''))
    for m in sorted(set(re.findall(r"(?<![0-9.])[0-9]{9,10}(?![0-9.])", s))):
        if m in allow or m == chat or m.startswith('17') or m == '4294967296':
            continue
        if m in ('536870912', '1073741824'):
            continue
        bad('C4-CHAT-ID', name, f'literal number {m} (chat id of someone else?)')
    # C5 credentials
    for t, c in (n.get('credentials') or {}).items():
        if cfg.get('credentials') and c['id'] not in cfg['credentials']:
            bad('C5-CREDENTIAL', name, f"{t} '{c['name']}' ({c['id']}) is not one of this client's credentials")
    # C6 tables
    if n['type'].endswith('dataTable') and cfg.get('tables'):
        v = p.get('dataTableId')
        tid = v.get('value') if isinstance(v, dict) else v
        if tid not in cfg['tables']:
            bad('C6-TABLE', name, f'data table {tid} does not belong to this client')
    # C8 retry on reads
    if n['type'].endswith('httpRequest') and p.get('method', 'GET') == 'GET' and not n.get('retryOnFail'):
        bad('C8-NO-RETRY', name, 'GET request without retryOnFail (ECONNRESET kills the run)')
    # C9 known invalid combination
    if 'genericAuthType' in p and p.get('authentication') != 'genericCredentialType':
        bad('C9-INVALID-PARAM', name, 'genericAuthType set while authentication is not genericCredentialType')
    # C7 webhooks must not keep template/owner paths
    if n['type'].endswith('.webhook'):
        path = str(p.get('path', ''))
        if path in ('tiktok-oauth-callback', 'facebook-oauth-callback', 'wa-webhook'):
            bad('C7-WEBHOOK', name, f'webhook path {path} is the owner path')

# C10 orphans (no incoming connection, not a trigger/sticky/sub-node)
targets = set()
for src, v in w['connections'].items():
    for t, outs in v.items():
        for o in outs:
            for c in (o or []):
                targets.add(c['node'])
for src, v in w['connections'].items():
    if any(t.startswith('ai_') for t in v):
        targets.add(src)
for n in nodes:
    t = n['type']
    if n['name'] in targets or 'rigger' in t or t.endswith('.webhook') or t.endswith('stickyNote'):
        continue
    if t.startswith('@n8n/n8n-nodes-langchain'):
        continue
    bad('C10-ORPHAN', n['name'], 'node has no incoming connection and never runs')

for f in findings:
    print(f)
print(f"{len(findings)} finding(s) in {len(nodes)} nodes", file=sys.stderr)
sys.exit(1 if findings else 0)
