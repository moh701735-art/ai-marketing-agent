#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""أداة تشغيل رادار المنافسين على الـVPS (مثبّتة كـ ops/competitor-radar.py). لا تلمس أي شي خارج: مخطط competitor_radar، الدور radar_rt،
حاوية central-stg-radar، وملف competitor_radar/radar.env. أسرار (مفتاح التوقيع، كلمة سر الدور) تُولَّد هنا وتُكتب لملف 600؛ مفتاح الـLLM يُكتب مخفياً.
  install   : يطبّق الهجرة 80، يولّد الأسرار، يبني الصورة ويشغّل الحاوية (COMPETITOR_RADAR_ENABLED=false؛ لا تفعيل)
  on | off  : مفتاح التشغيل العام (DB + متغير الحاوية + إعادة تشغيلها)
  status    : حالة الحاوية/المفتاح/الهجرة
  tenant <slug> on|off : استثناء/تفعيل لعميل واحد (features.competitor_radar)
  down      : يوقف ويحذف الحاوية فقط (الهجرة تتراجع بـ db/80_competitor_radar_down.sql يدوياً بعد استرجاع ملفات n8n)"""
import getpass, os, re, secrets, subprocess, sys

ROOT = os.environ.get("RADAR_ROOT", "/opt/central/competitor_radar")
PG = os.environ.get("RADAR_PG_CONTAINER", "central-stg-pg")
NAME = "central-stg-radar"
IMAGE = "central-radar:1"
ENV = os.path.join(ROOT, "radar.env")


def run(cmd, input=None, check=True):
    """نقطة التنفيذ الوحيدة (تُستبدل بالاختبارات). يرجّع (rc, stdout, stderr)"""
    r = subprocess.run(cmd, input=input, capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit("FAIL: %s -> %s" % (" ".join(cmd[:4]), (r.stderr or r.stdout).strip()[-300:]))
    return r.returncode, r.stdout, r.stderr


def psql(sql, check=True):
    return run(["docker", "exec", "-i", PG, "psql", "-U", "postgres", "-d", "central", "-X", "-q", "-At", "-v", "ON_ERROR_STOP=1", "-f", "-"], input=sql, check=check)


def read_env():
    d = {}
    if os.path.exists(ENV):
        for l in open(ENV, encoding="utf-8").read().splitlines():
            if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); d[k] = v
    return d


def write_env(d):
    tmp = ENV + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("".join("%s=%s\n" % (k, v) for k, v in d.items()))
    os.replace(tmp, ENV); os.chmod(ENV, 0o600)


def network():
    _, out, _ = run(["docker", "inspect", PG, "--format", "{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}"])
    nets = out.split()
    if not nets: raise SystemExit("FAIL: could not find the docker network of %s" % PG)
    return nets[0]


def start_container():
    run(["docker", "rm", "-f", NAME], check=False)
    run(["docker", "run", "-d", "--name", NAME, "--network", network(), "--network-alias", "radar", "--restart", "unless-stopped", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
         "--memory", "256m", "--cpus", "0.5", "--pids-limit", "128", "--tmpfs", "/tmp", "--env-file", ENV, IMAGE])


def healthy():
    rc, out, _ = run(["docker", "exec", NAME, "python", "-c", "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8088/healthz',timeout=3).status)"], check=False)
    return rc == 0 and out.strip() == "200"


def cmd_install(prompt=getpass.getpass):
    for f in ("db/80_competitor_radar.sql", "deploy/Dockerfile", "service/app.py"):
        if not os.path.exists(os.path.join(ROOT, f)): raise SystemExit("FAIL: missing %s (apply p251 first)" % f)
    sql = open(os.path.join(ROOT, "db/80_competitor_radar.sql"), encoding="utf-8").read()
    psql(sql)                                                          # 1) الهجرة (idempotent)
    env = read_env()
    key = env.get("RADAR_HMAC_KEY") or secrets.token_hex(32)           # 2) أسرار (تُحفظ لو موجودة حتى ما ينكسر التوقيع)
    pw = secrets.token_urlsafe(24) if "RADAR_DB_DSN" not in env else None
    if pw:
        psql("ALTER ROLE radar_rt LOGIN PASSWORD '%s';\n" % pw)
        dsn = "postgresql://radar_rt:%s@%s:5432/central" % (pw, PG)
    else:
        dsn = env["RADAR_DB_DSN"]
    psql("INSERT INTO competitor_radar.settings (key, value) VALUES ('service_key', to_jsonb('%s'::text)) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now();\n" % key)
    llm_key = env.get("RADAR_LLM_API_KEY", "")
    if not llm_key:
        llm_key = (prompt("مفتاح Gemini للرادار (مخفي؛ Enter = بدون LLM، تحليل حتمي فقط): ") or "").strip()
    new = {"COMPETITOR_RADAR_ENABLED": env.get("COMPETITOR_RADAR_ENABLED", "false"), "RADAR_HMAC_KEY": key, "RADAR_DB_DSN": dsn, "RADAR_PORT": "8088",
           "RADAR_LLM_PROVIDER": "gemini" if llm_key else "", "RADAR_LLM_API_KEY": llm_key, "RADAR_LLM_MODEL": env.get("RADAR_LLM_MODEL", "gemini-2.5-flash")}
    write_env(new)
    run(["docker", "build", "-t", IMAGE, "-f", os.path.join(ROOT, "deploy/Dockerfile"), ROOT])      # 3) الصورة والحاوية
    start_container()
    for _ in range(20):
        if healthy(): break
        run(["sleep", "2"], check=False)
    print("INSTALL_OK container=%s healthy=%s global_flag=%s llm=%s (nothing enabled; run: python3 ops/competitor-radar.py on)" % (NAME, healthy(), new["COMPETITOR_RADAR_ENABLED"], "yes" if llm_key else "no"))


def set_global(on: bool):
    env = read_env()
    if "RADAR_HMAC_KEY" not in env: raise SystemExit("FAIL: not installed (run install first)")
    if on and not healthy(): raise SystemExit("FAIL: radar container is not healthy; refusing to enable")
    psql("UPDATE competitor_radar.settings SET value = '%s'::jsonb, updated_at = now() WHERE key = 'enabled';\n" % ("true" if on else "false"))
    env["COMPETITOR_RADAR_ENABLED"] = "true" if on else "false"; write_env(env)
    run(["docker", "restart", NAME])
    print("FLAG_OK global=%s (db + container env)" % ("on" if on else "off"))


def set_tenant(slug, on):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,40}", slug or ""): raise SystemExit("FAIL: bad slug")
    sql = ("UPDATE core.tenants SET features = coalesce(features, '{}'::jsonb) || jsonb_build_object('competitor_radar', %s) WHERE slug = '%s' RETURNING slug;\n" % ("true" if on else "false", slug))
    _, out, _ = psql(sql)
    if slug not in out: raise SystemExit("FAIL: tenant not found: %s" % slug)
    print("TENANT_OK %s competitor_radar=%s" % (slug, "on" if on else "off"))


def cmd_status():
    env = read_env()
    rc, out, _ = run(["docker", "inspect", NAME, "--format", "{{.State.Status}}"], check=False)
    _, flag, _ = psql("SELECT value::text FROM competitor_radar.settings WHERE key = 'enabled';\n", check=False)
    print("container=%s healthy=%s env_flag=%s db_flag=%s llm=%s" % (out.strip() if rc == 0 else "absent", healthy() if rc == 0 else False, env.get("COMPETITOR_RADAR_ENABLED", "-"), flag.strip() or "-", "yes" if env.get("RADAR_LLM_API_KEY") else "no"))


def main(argv):
    a = argv[1:]
    if a[:1] == ["install"]: return cmd_install()
    if a[:1] in (["on"], ["off"]): return set_global(a[0] == "on")
    if a[:1] == ["status"]: return cmd_status()
    if a[:1] == ["tenant"] and len(a) == 3 and a[2] in ("on", "off"): return set_tenant(a[1], a[2] == "on")
    if a[:1] == ["down"]: run(["docker", "rm", "-f", NAME], check=False); print("DOWN_OK container removed (DB schema untouched)"); return
    print(__doc__)
    raise SystemExit(2)


if __name__ == "__main__":
    main(sys.argv)
