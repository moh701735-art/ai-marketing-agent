# TOKEN SAVING RULES

IMPORTANT:
Minimize usage and unnecessary context.

1. Do not scan the entire project unless necessary.
2. Do not reread files that have not changed.
3. Modify only the files directly related to the request.
4. Never rewrite an entire workflow when only one node needs modification.
5. Do not repeat large code blocks in the response.
6. Keep responses concise.
7. Do not explain code unless I ask for an explanation.
8. Before making changes, identify the smallest required change.
9. For debugging, inspect only the relevant file, node, function, or error.
10. Do not run unnecessary searches or commands.
11. Do not rebuild working parts of the project.
12. Preserve all existing working configurations.
13. If the task can be completed with a small edit, make only that edit.
14. Use the lowest reasonable reasoning effort for simple tasks.
15. Use higher reasoning only when the task genuinely requires complex debugging or architecture.

Priority:
CORRECT RESULT + MINIMUM TOKEN/USAGE CONSUMPTION.

# PROJECT MEMORY (read first when working on the central system)

- Full knowledge base: `out/central-knowledge.md` (architecture, commands, TikTok DM/Spark/video rules, fund transfer, open issues). New client checklist: `out/client-onboarding.md`.
- Central system code lives in `/home/user/ai-marketing-central` (VPS: `/opt/central`). Every change must be central so it applies to all current and future bots; client-specific values stay in the DB per tenant. Never touch the old n8n system.
- Deliver changes as `out/pNN.txt` patches (latest: p171) built from the server-state snapshot; send with SendUserFile; user pastes one command at a time.
- Standing rules: no fake success (separate created/enabled/delivering/results), no automatic audience/budget/bid optimizer, never ask users to paste secrets, keep answers short, Iraqi Arabic.
- Open items: fix `/addbalance` (Params invalid), auto top-up, set `bc_id` for mustafa-baghdad, delete partial campaigns 1881215143340242 and 1881222575499330, rotate TikTok App Secret, apply for Business Messaging API access, renew mohm (2026-12-01) and VPS (2026-11-30).
- Meta (Facebook) linking POSTPONED to tonight: apply out/p97.txt (includes the is_adset_budget_sharing_enabled fix; p95/p96 already applied), then `python3 ops/link-meta-web.py` (account 1143673748321865, tenant mohm). Ad account status was 3 (UNSETTLED): check Billing. Meta only supports reports + simple paused campaign creation so far.
- Pending welcome flow: p94 (flexible /welcome + owner detection) sent; zaid-hassan new central bot waiting for BotFather username/TG ID/duration.
- Clients and subscription dates: see `out/clients.md` (mohm ends 2026-12-01, mustafa-baghdad 2026-12-07, zaid-hassan 2026-12-09, ali-turki 2026-12-13, VPS 2026-11-30). Update it whenever a client is added/renewed. Reminders go out 2 days before expiry automatically.
- Moving a client from the old n8n system to central on the SAME bot: runbook `out/client-migration.md` (create tenant without --set-webhook, link TikTok via /tiktok-cb, turn old workflow off, then set-webhook).
- Facebook WhatsApp campaign from post link: p102 applied; p103 (fb.watch fix, multi-country, manual placements, page name, video list fallback) built, needs p102; details in out/central-knowledge.md.
