import csv
import hashlib
import io
import random
import re
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, Response, jsonify, render_template_string, request

from ..common import mysql_conn

META = {
    "slug": "vaultdocs",
    "title": "VaultDocs",
    "tagline": "Secure document storage and sharing for teams.",
    "prefix": "/vault",
}
bp = Blueprint("vaultdocs", __name__)
DB = "vaultdocs"


def db():
    return mysql_conn(DB)


def hpw(p):
    return hashlib.md5(("vd:" + p).encode()).hexdigest()


def auth():
    key = request.headers.get("X-API-Key", "")
    if not key:
        return None, (jsonify(error="missing api key"), 401)
    c = db()
    try:
        cur = c.cursor()
        cur.execute("SELECT id, email, role, theme, notifications, legacy_export FROM users WHERE api_key=%s", (key,))
        u = cur.fetchone()
    finally:
        c.close()
    if not u:
        return None, (jsonify(error="invalid api key"), 401)
    return u, None


# ------------------------------------------------------------------ v2 auth
@bp.route("/api/v2/auth/register", methods=["POST"])
def register():
    d = request.get_json(silent=True) or {}
    email, pw = str(d.get("email", "")).strip().lower(), str(d.get("password", ""))
    if not re.fullmatch(r"[^@\s]{1,40}@[^@\s]{1,40}", email) or len(pw) < 6:
        return jsonify(error="invalid registration details"), 400
    key = "vk_" + secrets.token_hex(16)
    c = db()
    try:
        cur = c.cursor()
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            return jsonify(error="email already registered"), 409
        cur.execute("INSERT INTO users(email,password_hash,api_key,role) VALUES(%s,%s,%s,'member')", (email, hpw(pw), key))
        uid = cur.lastrowid
        cur.execute("INSERT INTO folders(owner_id,name) VALUES(%s,'My files')", (uid,))
        fid = cur.lastrowid
        for i, t in enumerate(["Welcome guide", "Getting started", "Sample contract"]):
            cur.execute("INSERT INTO documents(owner_id,folder_id,title,filename,size,mime,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                        (uid, fid, t, t.lower().replace(" ", "_") + ".pdf", 20000 + i * 1300, "application/pdf", datetime(2024, 5, 1 + i)))
    finally:
        c.close()
    return jsonify(api_key=key), 201


@bp.route("/api/v2/auth/login", methods=["POST"])
def login():
    d = request.get_json(silent=True) or {}
    c = db()
    try:
        cur = c.cursor()
        cur.execute("SELECT api_key FROM users WHERE email=%s AND password_hash=%s",
                    (str(d.get("email", "")).lower(), hpw(str(d.get("password", "")))))
        u = cur.fetchone()
    finally:
        c.close()
    if not u:
        return jsonify(error="invalid credentials"), 401
    return jsonify(api_key=u["api_key"])


@bp.route("/api/v2/me")
def me():
    u, err = auth()
    if err:
        return err
    return jsonify(id=u["id"], email=u["email"], role=u["role"])


SETTING_KEYS = {"theme": ("light", "dark"), "notifications": (True, False), "legacy_export": (True, False)}


@bp.route("/api/v2/settings", methods=["GET", "PATCH"])
def settings():
    u, err = auth()
    if err:
        return err
    if request.method == "PATCH":
        d = request.get_json(silent=True) or {}
        c = db()
        try:
            cur = c.cursor()
            for k, v in d.items():
                if k in SETTING_KEYS and v in SETTING_KEYS[k]:
                    cur.execute("UPDATE users SET " + k + "=%s WHERE id=%s", (v, u["id"]))  # k is allowlisted
            cur.execute("SELECT theme, notifications, legacy_export FROM users WHERE id=%s", (u["id"],))
            r = cur.fetchone()
        finally:
            c.close()
    else:
        r = u
    return jsonify(theme=r["theme"], notifications=bool(r["notifications"]), legacy_export=bool(r["legacy_export"]),
                   default_view="list", language="en")


# ------------------------------------------------------------------ v2 documents (safe)
SORTS = {"title": "d.title", "created": "d.created_at", "size": "d.size"}


@bp.route("/api/v2/documents", methods=["GET", "POST"])
def documents():
    u, err = auth()
    if err:
        return err
    c = db()
    try:
        cur = c.cursor()
        if request.method == "POST":
            d = request.get_json(silent=True) or {}
            title = str(d.get("title", "")).strip()[:120]
            if not title:
                return jsonify(error="title required"), 400
            cur.execute("INSERT INTO documents(owner_id,folder_id,title,filename,size,mime,created_at) VALUES(%s,%s,%s,%s,%s,%s,NOW())",
                        (u["id"], None, title, "upload.bin", 1024, "application/octet-stream"))
            return jsonify(id=cur.lastrowid), 201
        sql = ("SELECT d.id, d.title, d.filename, d.size, d.created_at FROM documents d WHERE d.owner_id=%s")
        args = [u["id"]]
        if request.args.get("folder"):
            sql += " AND d.folder_id=%s"
            args.append(request.args["folder"])
        if request.args.get("tag"):
            sql += " AND d.id IN (SELECT dt.document_id FROM document_tags dt JOIN tags t ON t.id=dt.tag_id WHERE t.name=%s)"
            args.append(request.args["tag"])
        sort = SORTS.get(request.args.get("sort", "created"))
        if not sort:
            return jsonify(error="invalid sort"), 400
        order = "ASC" if request.args.get("order", "desc").lower() == "asc" else "DESC"
        cur.execute(sql + " ORDER BY " + sort + " " + order + " LIMIT 100", tuple(args))
        return jsonify(documents=cur.fetchall())
    finally:
        c.close()


@bp.route("/api/v2/documents/<int:did>")
def document(did):
    u, err = auth()
    if err:
        return err
    c = db()
    try:
        cur = c.cursor()
        cur.execute("SELECT id, title, filename, size, mime, created_at FROM documents WHERE id=%s AND owner_id=%s", (did, u["id"]))
        r = cur.fetchone()
    finally:
        c.close()
    return (jsonify(r) if r else (jsonify(error="not found"), 404))


def _simple(table_sql, name):
    def view():
        u, err = auth()
        if err:
            return err
        c = db()
        try:
            cur = c.cursor()
            cur.execute(table_sql, (u["id"],))
            return jsonify({name: cur.fetchall()})
        finally:
            c.close()
    return view


bp.add_url_rule("/api/v2/folders", "folders", _simple("SELECT id, name FROM folders WHERE owner_id=%s", "folders"))
bp.add_url_rule("/api/v2/shares", "shares", _simple(
    "SELECT s.token, s.document_id, s.expires_at FROM share_links s JOIN documents d ON d.id=s.document_id WHERE d.owner_id=%s", "shares"))
bp.add_url_rule("/api/v2/tags", "tags", _simple(
    "SELECT DISTINCT t.name FROM tags t JOIN document_tags dt ON dt.tag_id=t.id JOIN documents d ON d.id=dt.document_id WHERE d.owner_id=%s", "tags"))


@bp.route("/api/v2/audit")
def audit():
    u, err = auth()
    if err:
        return err
    try:
        limit = max(1, min(int(request.args.get("limit", "20")), 100))
    except ValueError:
        return jsonify(error="invalid limit"), 400
    c = db()
    try:
        cur = c.cursor()
        cur.execute("SELECT action, at FROM audit_log WHERE user_id=%s ORDER BY id DESC LIMIT " + str(limit), (u["id"],))
        return jsonify(events=cur.fetchall())
    finally:
        c.close()


@bp.route("/api/v2/search")
def search():
    u, err = auth()
    if err:
        return err
    q = request.args.get("q", "")
    c = db()
    try:
        cur = c.cursor()
        cur.execute("SELECT id, title FROM documents WHERE owner_id=%s AND title LIKE %s LIMIT 50", (u["id"], "%" + q + "%"))
        return jsonify(results=cur.fetchall())
    finally:
        c.close()


V2_FIELDS = {"title": "title", "filename": "filename", "size": "size", "created": "created_at", "mime": "mime"}


@bp.route("/api/v2/export")
def export_v2():
    u, err = auth()
    if err:
        return err
    names = [f.strip() for f in request.args.get("fields", "title,created").split(",")]
    cols = []
    for n in names:
        if n not in V2_FIELDS:
            return jsonify(error="unknown field '%s'" % n[:30]), 400
        cols.append(V2_FIELDS[n])
    c = db()
    try:
        cur = c.cursor()
        cur.execute("SELECT " + ", ".join(cols) + " FROM documents WHERE owner_id=%s LIMIT 100", (u["id"],))
        return jsonify(rows=cur.fetchall(), fields=names)
    finally:
        c.close()


@bp.route("/api/v2/admin/<path:p>")
def v2_admin(p):
    return jsonify(error="forbidden"), 403


@bp.route("/api/v2/")
@bp.route("/api/v2")
def v2_index():
    return jsonify(service="vaultdocs", version="2")


# ------------------------------------------------------------------ v1 legacy export
LEGACY_OK = {"title", "filename", "size", "created_at", "mime", "id", "folder_id"}


@bp.route("/api/v1/export")
def export_v1():
    u, err = auth()
    if err:
        return err
    if not u["legacy_export"]:
        return jsonify(error="legacy export is not enabled for this account"), 403
    raw = request.args.get("fields", "title,created_at,size")
    if "'" in raw or '"' in raw or ";" in raw or "`" in raw or len(raw) > 600:
        return jsonify(error="invalid characters in fields"), 400
    # field names are checked against the allow-list (first three only: legacy clients never ask for more)
    for f in [x.strip() for x in raw.split(",")][:3]:
        if f not in LEGACY_OK:
            return jsonify(error="unknown field '%s'" % f[:30]), 400
    fmt = request.args.get("format", "json")
    c = db()
    try:
        cur = c.cursor()
        try:
            cur.execute("SELECT " + raw + " FROM documents WHERE owner_id=" + str(u["id"]) + " LIMIT 50")
            rows = cur.fetchall()
        except Exception:
            return jsonify(error="export failed"), 500
    finally:
        c.close()
    if fmt == "csv":
        buf = io.StringIO()
        if rows:
            w = csv.writer(buf)
            w.writerow(rows[0].keys())
            for r in rows:
                w.writerow(r.values())
        return Response(buf.getvalue(), mimetype="text/csv")
    return Response(__import__("json").dumps({"count": len(rows), "rows": rows}, default=str), mimetype="application/json")


@bp.route("/api/v1/")
@bp.route("/api/v1")
def v1_index():
    return jsonify(error="missing api key"), 401


# ------------------------------------------------------------------ decoy admin / misc
@bp.route("/admin", methods=["GET", "POST"])
def admin():
    msg = ""
    if request.method == "POST":
        c = db()
        try:
            cur = c.cursor()
            cur.execute("SELECT id FROM users WHERE email=%s AND password_hash=%s AND role='admin'",
                        (request.form.get("email", ""), hpw(request.form.get("password", ""))))
            cur.fetchone()
        finally:
            c.close()
        msg = "Access denied."
    return render_template_string(
        "<!doctype html><title>VaultDocs Admin</title><body style='font-family:sans-serif;background:#10151c;color:#dde;padding:60px'>"
        "<h2>Admin console</h2><form method=post><p><input name=email placeholder=email></p><p><input name=password type=password placeholder=password></p>"
        "<button>Sign in</button></form><p style='color:#f77'>{{m}}</p>", m=msg)


@bp.route("/robots.txt")
def robots():
    return ("User-agent: *\nDisallow: /vault/admin\nDisallow: /vault/api/v2/admin/\n", 200, {"Content-Type": "text/plain"})


@bp.route("/backup.sql")
@bp.route("/.git/config")
def nofile():
    return ("<h1>404 Not Found</h1>", 404)


APP_JS = r"""
const KEY='vd_key';
function k(){try{return localStorage.getItem(KEY)||''}catch(e){return ''}}
async function api(u,o){o=o||{};o.headers=Object.assign({'X-API-Key':k()},o.headers||{});
 if(o.body&&typeof o.body!=='string'){o.body=JSON.stringify(o.body);o.headers['Content-Type']='application/json'}
 const r=await fetch(u,o);let j=null;try{j=await r.json()}catch(e){}return {ok:r.ok,status:r.status,data:j}}
function row(tb,vals){const tr=document.createElement('tr');vals.forEach(v=>{const td=document.createElement('td');td.textContent=v==null?'':v;tr.appendChild(td)});tb.appendChild(tr)}
async function loadDocs(sort){const tb=document.getElementById('docs');tb.innerHTML='';
 const r=await api('/vault/api/v2/documents?sort='+(sort||'created'));if(!r.ok){location='/vault/';return}
 r.data.documents.forEach(d=>row(tb,[d.title,d.filename,Math.round(d.size/1024)+' KB',String(d.created_at).slice(0,10)]))}
async function loadFolders(){const r=await api('/vault/api/v2/folders');const ul=document.getElementById('folders');
 if(r.ok)r.data.folders.forEach(f=>{const li=document.createElement('li');li.textContent=f.name;ul.appendChild(li)})}
async function exportDocs(){const r=await api('/vault/api/v2/export?fields=title,filename,size');
 const o=document.getElementById('out');if(o)o.textContent=r.ok?(r.data.rows.length+' documents exported'):'Export failed'}
// legacy bulk export for enterprise tenants (v1)
async function legacyExport(fields){return api('/vault/api/v1/export?fields='+encodeURIComponent(fields||'title,created_at,size'))}
async function search(q){return api('/vault/api/v2/search?q='+encodeURIComponent(q))}
"""


@bp.route("/static/app.js")
def appjs():
    return Response(APP_JS, mimetype="application/javascript")


PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VaultDocs</title><style>
:root{--bg:#0e1420;--panel:#172033;--line:#27344d;--ink:#e4eaf5;--acc:#7c5cff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,system-ui,sans-serif}
header{padding:16px 28px;border-bottom:1px solid var(--line);display:flex;gap:20px;align-items:center}
header b{font-size:19px}header b i{color:var(--acc);font-style:normal}.sp{flex:1}a{color:#a99bff}
main{max-width:900px;margin:30px auto;padding:0 20px;display:grid;grid-template-columns:200px 1fr;gap:24px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px}
ul{list-style:none;padding:0;margin:0}li{padding:6px 0;color:#b8c3d9}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:9px;border-bottom:1px solid var(--line);text-align:left}th{color:#8a99b5}
input{width:100%;padding:10px;border-radius:6px;border:1px solid var(--line);background:#0e1420;color:var(--ink);margin:6px 0}
button{background:var(--acc);color:#fff;border:0;padding:10px 18px;border-radius:6px;cursor:pointer;margin:6px 6px 0 0}.err{color:#ff8a8a;font-size:14px}
.auth{max-width:380px;margin:60px auto;display:block}.sort a{margin-right:12px;font-size:13px;cursor:pointer}
</style></head><body>
<header><b>Vault<i>Docs</i></b><span class="sp"></span>{% if app %}<a href="#" id="lo">Sign out</a>{% endif %}</header>
{{ body|safe }}<script src="/vault/static/app.js"></script>{{ script|safe }}</body></html>"""


@bp.route("/")
def index():
    body = """<main class="auth"><div class="panel"><h2>Sign in to your vault</h2>
<input id="em" placeholder="Email"><input id="pw" type="password" placeholder="Password">
<button id="si">Sign in</button><button id="su" style="background:#27344d">Create account</button><div class="err" id="er"></div></div></main>"""
    script = """<script>
async function go(path){const r=await fetch('/vault/api/v2/auth/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:em.value,password:pw.value})});
const j=await r.json();if(r.ok){let key=j.api_key;if(path==='register'){const l=await fetch('/vault/api/v2/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:em.value,password:pw.value})});key=(await l.json()).api_key}
try{localStorage.setItem('vd_key',key)}catch(e){}location='/vault/app'}else er.textContent=j.error||'Error'}
si.onclick=()=>go('login');su.onclick=()=>go('register');</script>"""
    return render_template_string(PAGE, body=body, script=script, app=False)


@bp.route("/app")
def app_page():
    body = """<main><div class="panel"><b>Folders</b><ul id="folders" style="margin-top:10px"></ul></div>
<div class="panel"><h3 style="margin-top:0">Documents</h3><div class="sort">Sort by: <a onclick="loadDocs('title')">name</a><a onclick="loadDocs('size')">size</a><a onclick="loadDocs('created')">date</a></div>
<table style="margin-top:10px"><thead><tr><th>Title</th><th>File</th><th>Size</th><th>Created</th></tr></thead><tbody id="docs"></tbody></table>
<button onclick="exportDocs()">Export list</button><span id="out" style="margin-left:10px;color:#8a99b5"></span></div></main>"""
    script = """<script>loadDocs();loadFolders();document.getElementById('lo').onclick=e=>{e.preventDefault();try{localStorage.removeItem('vd_key')}catch(x){}location='/vault/'}</script>"""
    return render_template_string(PAGE, body=body, script=script, app=True)


# ------------------------------------------------------------------ seed
def init_db():
    c = mysql_conn(DB, admin=True)
    cur = c.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS=0")
    for t in ("document_tags", "tags", "share_links", "audit_log", "documents", "folders", "vault_secrets", "billing_accounts", "users"):
        cur.execute("DROP TABLE IF EXISTS `%s`" % t)
    cur.execute("""CREATE TABLE users(id INT AUTO_INCREMENT PRIMARY KEY, email VARCHAR(80) UNIQUE, password_hash CHAR(32),
        api_key VARCHAR(40) UNIQUE, role VARCHAR(12) DEFAULT 'member', theme VARCHAR(8) DEFAULT 'light',
        notifications TINYINT(1) DEFAULT 1, legacy_export TINYINT(1) DEFAULT 0)""")
    cur.execute("CREATE TABLE folders(id INT AUTO_INCREMENT PRIMARY KEY, owner_id INT, name VARCHAR(60))")
    cur.execute("""CREATE TABLE documents(id INT AUTO_INCREMENT PRIMARY KEY, owner_id INT, folder_id INT NULL, title VARCHAR(120),
        filename VARCHAR(80), size INT, mime VARCHAR(40), created_at DATETIME)""")
    cur.execute("CREATE TABLE tags(id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(30))")
    cur.execute("CREATE TABLE document_tags(document_id INT, tag_id INT)")
    cur.execute("CREATE TABLE share_links(id INT AUTO_INCREMENT PRIMARY KEY, document_id INT, token VARCHAR(32), expires_at DATETIME)")
    cur.execute("CREATE TABLE audit_log(id INT AUTO_INCREMENT PRIMARY KEY, user_id INT, action VARCHAR(80), at DATETIME)")
    cur.execute("CREATE TABLE billing_accounts(id INT AUTO_INCREMENT PRIMARY KEY, owner_id INT, plan VARCHAR(20), card_token VARCHAR(40))")
    cur.execute("CREATE TABLE vault_secrets(id INT AUTO_INCREMENT PRIMARY KEY, secret_name VARCHAR(50), secret_value VARCHAR(120))")

    rng = random.Random(1337)
    people = ["admin", "maria.lopez", "ken.watanabe", "priya.nair", "tom.becker", "sara.ali", "luca.rossi", "emma.stone",
              "omar.faruk", "nina.kraft", "paul.dumont", "iris.chen"]
    pws = ["Vault#Admin1", "Docs2024!", "Welcome#77", "Q3-report", "Fileshare9", "Secret!42"]
    for i, p in enumerate(people):
        cur.execute("INSERT INTO users(email,password_hash,api_key,role,legacy_export) VALUES(%s,%s,%s,%s,%s)",
                    (p + "@corp.example", hpw(rng.choice(pws)), "vk_%032x" % rng.getrandbits(128),
                     "admin" if i == 0 else "member", 1 if i in (0, 3) else 0))
    for uid in range(1, 13):
        for nm in rng.sample(["Contracts", "Invoices", "HR", "Legal", "Projects", "Archive", "Marketing"], 3):
            cur.execute("INSERT INTO folders(owner_id,name) VALUES(%s,%s)", (uid, nm))
    kinds = ["Contract", "Invoice", "Report", "Policy", "NDA", "Proposal", "Minutes", "Statement"]
    docs = 0
    for uid in range(1, 13):
        for _ in range(rng.randint(6, 11)):
            t = "%s %s-%03d" % (rng.choice(kinds), rng.choice(["Q1", "Q2", "Q3", "Q4"]), rng.randint(1, 400))
            cur.execute("INSERT INTO documents(owner_id,folder_id,title,filename,size,mime,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                        (uid, (uid - 1) * 3 + rng.randint(1, 3), t, t.lower().replace(" ", "_") + ".pdf",
                         rng.randint(8000, 4000000), "application/pdf", datetime(2024, 1, 1) + timedelta(days=rng.randint(0, 330))))
            docs += 1
    for t in ["finance", "legal", "draft", "final", "confidential", "hr", "2024", "client"]:
        cur.execute("INSERT INTO tags(name) VALUES(%s)", (t,))
    for d in range(1, docs + 1):
        for tg in rng.sample(range(1, 9), 2):
            cur.execute("INSERT INTO document_tags VALUES(%s,%s)", (d, tg))
        if rng.random() < 0.25:
            cur.execute("INSERT INTO share_links(document_id,token,expires_at) VALUES(%s,%s,%s)",
                        (d, secrets.token_hex(8), datetime(2025, 1, 1) + timedelta(days=rng.randint(0, 90))))
    for uid in range(1, 13):
        for a in rng.sample(["login", "download", "share", "upload", "delete", "rename", "export"], 5):
            cur.execute("INSERT INTO audit_log(user_id,action,at) VALUES(%s,%s,%s)",
                        (uid, a, datetime(2024, 6, 1) + timedelta(hours=rng.randint(0, 2000))))
        cur.execute("INSERT INTO billing_accounts(owner_id,plan,card_token) VALUES(%s,%s,%s)",
                    (uid, rng.choice(["free", "team", "enterprise"]), "tok_" + secrets.token_hex(8)))
    for n, v in (("kms_master_ref", "kms://eu-1/vault-master"), ("backup_bucket", "s3://vd-prod-backups"),
                 ("decoy_flag", "FLAG{keep_looking_nothing_to_see}"),
                 ("signing_secret", "FLAG{vaultdocs_the_legacy_door_was_never_locked}")):
        cur.execute("INSERT INTO vault_secrets(secret_name,secret_value) VALUES(%s,%s)", (n, v))
    cur.execute("SET FOREIGN_KEY_CHECKS=1")
    c.close()
