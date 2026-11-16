"""TicketDesk - public IT support site with a small JSON API behind the pages."""
import hashlib
import random
import re
from datetime import datetime, timedelta

import pymssql
from flask import Blueprint, jsonify, render_template_string, request

from ..common import mssql_conn

META = {
    "slug": "ticketdesk",
    "title": "TicketDesk",
    "tagline": "Internal IT support requests, assets and knowledge base.",
    "prefix": "/desk",
}
P = "/desk"
bp = Blueprint("ticketdesk", __name__)
DB = "ticketdesk"

STATUSES = ("open", "in_progress", "resolved", "closed")
PERIODS = {"7d": 7, "30d": 30, "90d": 90, "1y": 365, "all": None}
BLOCK = re.compile(
    r";|--|/\*|\bunion\b|\bwaitfor\b|\bexec\b|\bxp_|\binsert\b|\bupdate\b|\bdelete\b|\bdrop\b|\bshutdown\b",
    re.I,
)


def hp(pw):
    return hashlib.sha256(("td$" + pw).encode()).hexdigest()


# --------------------------------------------------------------------------- schema / seed
def init_db():
    rnd = random.Random(4417)
    c = mssql_conn(DB, admin=True)
    cur = c.cursor()
    for t in ("api_tokens", "comments", "tickets", "assets", "knowledge_base", "api_keys", "contact_messages",
              "audit_log", "service_accounts", "categories", "tickets_archive", "users"):
        cur.execute(f"IF OBJECT_ID('dbo.{t}','U') IS NOT NULL DROP TABLE dbo.{t}")
    cur.execute("""CREATE TABLE dbo.users(
        id INT IDENTITY(1,1) PRIMARY KEY, username NVARCHAR(40) NOT NULL UNIQUE, email NVARCHAR(120),
        full_name NVARCHAR(80), password_hash NVARCHAR(64), role NVARCHAR(20), department NVARCHAR(40),
        team NVARCHAR(40) NULL, job_title NVARCHAR(60) NULL, created_at DATETIME2)""")
    cur.execute("""CREATE TABLE dbo.categories(
        id INT IDENTITY(1,1) PRIMARY KEY, name NVARCHAR(60), description NVARCHAR(200))""")
    cur.execute("""CREATE TABLE dbo.tickets(
        id INT IDENTITY(1,1) PRIMARY KEY, subject NVARCHAR(200), description NVARCHAR(MAX), status NVARCHAR(20),
        priority INT, category_id INT, requester_id INT, assignee_id INT NULL, created_at DATETIME2, updated_at DATETIME2)""")
    cur.execute("""CREATE TABLE dbo.comments(
        id INT IDENTITY(1,1) PRIMARY KEY, ticket_id INT, author_id INT, body NVARCHAR(MAX), created_at DATETIME2)""")
    cur.execute("""CREATE TABLE dbo.assets(
        id INT IDENTITY(1,1) PRIMARY KEY, tag NVARCHAR(20), kind NVARCHAR(30), model NVARCHAR(60),
        assigned_to NVARCHAR(40), location NVARCHAR(40), purchased DATE)""")
    cur.execute("""CREATE TABLE dbo.knowledge_base(
        id INT IDENTITY(1,1) PRIMARY KEY, title NVARCHAR(120), body NVARCHAR(MAX), views INT)""")
    cur.execute("""CREATE TABLE dbo.api_keys(
        id INT IDENTITY(1,1) PRIMARY KEY, owner NVARCHAR(60), key_value NVARCHAR(64), scope NVARCHAR(40), active BIT)""")
    cur.execute("""CREATE TABLE dbo.audit_log(
        id INT IDENTITY(1,1) PRIMARY KEY, actor NVARCHAR(40), action NVARCHAR(120), created_at DATETIME2)""")
    cur.execute("""CREATE TABLE dbo.tickets_archive(
        id INT IDENTITY(1,1) PRIMARY KEY, subject NVARCHAR(200), closed_on DATE, resolution NVARCHAR(200))""")
    cur.execute("""CREATE TABLE dbo.service_accounts(
        id INT IDENTITY(1,1) PRIMARY KEY, system_name NVARCHAR(60), account NVARCHAR(60),
        secret NVARCHAR(120), notes NVARCHAR(200))""")
    cur.execute("""CREATE TABLE dbo.contact_messages(
        id INT IDENTITY(1,1) PRIMARY KEY, name NVARCHAR(80), email NVARCHAR(120), body NVARCHAR(500), created_at DATETIME2)""")

    now = datetime(2026, 11, 1, 9, 0, 0)

    def ago(days_max):
        return now - timedelta(days=rnd.randint(0, days_max), hours=rnd.randint(0, 23), minutes=rnd.randint(0, 59))

    # (username, full name, role, department, team, job title)
    people = [
        ("admin", "Priya Raman", "admin", "IT Operations", "Service Desk", "Service Desk Manager"),
        ("agent.lee", "Daniel Lee", "agent", "IT Operations", "Service Desk", "Support Engineer"),
        ("agent.novak", "Elena Novak", "agent", "IT Operations", "Network", "Network Engineer"),
        ("agent.osei", "Kwame Osei", "agent", "IT Operations", "Infrastructure", "Systems Administrator"),
        ("agent.silva", "Marta Silva", "agent", "IT Operations", "Applications", "Application Support Analyst"),
        ("agent.tanaka", "Ken Tanaka", "agent", "IT Operations", "Network", "Wireless Specialist"),
        ("tbrooks", "Tessa Brooks", "user", "Finance", None, None), ("mhall", "Marcus Hall", "user", "Sales", None, None),
        ("jwong", "Jia Wong", "user", "Engineering", None, None), ("sfarouk", "Sara Farouk", "user", "HR", None, None),
        ("rpetrov", "Roman Petrov", "user", "Engineering", None, None), ("lcosta", "Luisa Costa", "user", "Marketing", None, None),
        ("dkim", "David Kim", "user", "Legal", None, None), ("anguyen", "Anh Nguyen", "user", "Support", None, None),
        ("bturner", "Bella Turner", "user", "Finance", None, None), ("cmoreau", "Camille Moreau", "user", "Sales", None, None),
        ("ewalsh", "Ethan Walsh", "user", "Facilities", None, None), ("fibrahim", "Farah Ibrahim", "user", "Engineering", None, None),
        ("gadler", "Gil Adler", "user", "Operations", None, None), ("hkhan", "Hamza Khan", "user", "Procurement", None, None),
    ]
    for u, n, role, dept, team, jt in people:
        pw = f"{u}!{rnd.randint(1000, 9999)}"
        cur.execute("INSERT INTO dbo.users(username,email,full_name,password_hash,role,department,team,job_title,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (u, f"{u}@northwind-corp.example", n, hp(pw), role, dept, team, jt, ago(400)))
    cats = [("Hardware", "Laptops, monitors, peripherals"), ("Software", "Installs, licences, updates"),
            ("Network", "Wi-Fi, VPN, connectivity"), ("Accounts & Access", "Passwords, MFA, permissions"),
            ("Email & Calendar", "Mailboxes, shared calendars"), ("Printing", "Printers, scanners, toner"),
            ("Facilities", "Desk moves, badges, rooms")]
    cur.executemany("INSERT INTO dbo.categories(name,description) VALUES (%s,%s)", cats)

    subjects = [
        ("Laptop will not boot after update", 1), ("Request: second monitor for desk 4B", 1), ("Docking station drops USB devices", 1),
        ("Keyboard keys sticking", 1), ("Install Adobe Acrobat Pro", 2), ("Visual Studio licence expired", 2),
        ("Excel crashes on large workbook", 2), ("Need Python 3.12 on build server", 2), ("VPN disconnects every 10 minutes", 3),
        ("Wi-Fi unavailable on 3rd floor east", 3), ("Cannot reach shared drive from home", 3), ("Slow internet in meeting room 2", 3),
        ("Password reset needed", 4), ("MFA token lost", 4), ("Access to finance share folder", 4), ("Account locked after holiday", 4),
        ("Shared mailbox not appearing in Outlook", 5), ("Calendar invites arriving twice", 5), ("Mailbox over quota", 5),
        ("Printer on floor 2 jams constantly", 6), ("Scanner not sending to email", 6), ("Toner low in print room", 6),
        ("Badge reader at side door not working", 7), ("Move my desk to the engineering pod", 7), ("Meeting room display blank", 7),
        ("Outlook signature reset itself", 5), ("New starter laptop setup", 1), ("Leaver: disable account and collect kit", 4),
        ("Teams audio echo in calls", 2), ("Phone handset has no dial tone", 3), ("Browser certificate warning on intranet", 3),
        ("Request admin rights for dev VM", 4), ("Webcam not detected", 1), ("OneDrive sync stuck at 99%", 2),
        ("Barcode scanner pairing fails", 1), ("Projector HDMI flickers", 7), ("Shared calendar permissions", 5),
        ("Backup restore request for lost file", 2), ("Conference phone needs firmware update", 3), ("Mouse cursor jumping", 1),
        ("Software centre shows no apps", 2), ("Guest Wi-Fi code for visitors", 3), ("Printer driver for new MFP", 6),
        ("Lost laptop charger", 1), ("Screen flickers on external display", 1),
    ]
    stat_w = ["open", "open", "in_progress", "in_progress", "resolved", "closed", "closed"]
    bodies = ["Started happening yesterday. Restarting did not help.", "This is blocking my work, please advise.",
              "Raised on behalf of the whole team, several people affected.", "Intermittent issue, hard to reproduce.",
              "Please let me know what details you need from my side.", "Needed before the end of the week if possible."]
    for s, cat in subjects:
        d = ago(120)
        cur.execute("INSERT INTO dbo.tickets(subject,description,status,priority,category_id,requester_id,assignee_id,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (s, rnd.choice(bodies), rnd.choice(stat_w), rnd.randint(1, 4), cat, rnd.randint(7, 20),
                     rnd.choice([2, 3, 4, 5, 6, None]), d, d + timedelta(hours=rnd.randint(1, 72))))
    replies = ["Thanks for raising this, looking into it now.", "Could you confirm the asset tag of the device?",
               "I have escalated this to the network team.", "A fix has been applied, please test and confirm.",
               "Still happening for me after the change.", "Resolved on our side, closing unless you object.",
               "Booked a visit for tomorrow morning.", "Waiting on a replacement part from the vendor."]
    for _ in range(95):
        cur.execute("INSERT INTO dbo.comments(ticket_id,author_id,body,created_at) VALUES (%s,%s,%s,%s)",
                    (rnd.randint(1, len(subjects)), rnd.randint(2, 6), rnd.choice(replies), ago(100)))
    kinds = [("Laptop", "ThinkPad T14 Gen 4"), ("Laptop", "Dell Latitude 7440"), ("Monitor", "Dell U2723QE"),
             ("Dock", "Lenovo ThinkPad Thunderbolt 4"), ("Printer", "HP LaserJet M507"), ("Phone", "Yealink T54W"),
             ("Laptop", "MacBook Pro 14"), ("Scanner", "Fujitsu fi-8170")]
    locs = ["HQ-2F", "HQ-3F", "HQ-4F", "Annex", "Remote", "Warehouse"]
    for i in range(1, 31):
        k, m = rnd.choice(kinds)
        cur.execute("INSERT INTO dbo.assets(tag,kind,model,assigned_to,location,purchased) VALUES (%s,%s,%s,%s,%s,%s)",
                    (f"NW-{1000 + i * 7}", k, m, rnd.choice(people)[0], rnd.choice(locs), (now - timedelta(days=rnd.randint(60, 1500))).date()))
    kb = [("Resetting your password", "Use the self-service portal and verify with your authenticator app."),
          ("Connecting to the corporate VPN", "Install the client from Software Centre and sign in with your network ID."),
          ("Setting up a shared mailbox", "Open Outlook, choose Account Settings and add the mailbox address."),
          ("Requesting new hardware", "Raise a Hardware ticket with your manager's approval attached."),
          ("Printer troubleshooting basics", "Check paper path, restart the device, then reinstall the queue."),
          ("Wi-Fi networks in the office", "Use the staff SSID. Visitors must request a guest code at reception."),
          ("What to do if your laptop is lost", "Report it immediately so the device can be locked and wiped."),
          ("Installing approved software", "Open Software Centre; anything else needs a ticket."),
          ("Multi-factor authentication guide", "Register your phone and keep two backup methods."),
          ("Meeting room equipment guide", "Use the wireless presenter or the HDMI cable in the drawer."),
          ("Using OneDrive safely", "Keep work files in the synced folder; do not share links externally."),
          ("Booking IT onboarding for new starters", "Submit the starter form five working days in advance.")]
    for t, b in kb:
        cur.execute("INSERT INTO dbo.knowledge_base(title,body,views) VALUES (%s,%s,%s)", (t, b, rnd.randint(40, 2400)))
    for i in range(10):
        cur.execute("INSERT INTO dbo.api_keys(owner,key_value,scope,active) VALUES (%s,%s,%s,%s)",
                    (rnd.choice(["monitoring", "hr-sync", "badge-system", "backup-agent", "chatops"]),
                     "tdk_%028x" % rnd.getrandbits(112), rnd.choice(["read", "tickets:write", "assets:read"]), rnd.randint(0, 1)))
    acts = ["login", "ticket.update", "ticket.assign", "asset.update", "user.create", "token.issue", "config.view"]
    for i in range(40):
        cur.execute("INSERT INTO dbo.audit_log(actor,action,created_at) VALUES (%s,%s,%s)",
                    (rnd.choice(people)[0], rnd.choice(acts), ago(60)))
    for i in range(14):
        cur.execute("INSERT INTO dbo.tickets_archive(subject,closed_on,resolution) VALUES (%s,%s,%s)",
                    (rnd.choice(subjects)[0], (now - timedelta(days=rnd.randint(200, 900))).date(), "Closed after no response from requester"))
    hx = lambda: "%010x" % rnd.getrandbits(40)  # noqa
    svc = [("Backup Controller", "svc_backup", "Bk!" + hx(), "Nightly job owner"),
           ("Badge System", "svc_badge", "Bd#" + hx(), "Door controller sync"),
           ("HR Sync", "svc_hrsync", "Hr$" + hx(), "Directory import"),
           ("Monitoring", "svc_nagios", "Mn@" + hx(), "Read-only checks"),
           ("Domain Join", "svc_join", "FLAG{ticketdesk_amber_lantern_7c41}", "Rotate before next audit"),
           ("Print Server", "svc_print", "Pr%" + hx(), "Spooler restart rights")]
    cur.executemany("INSERT INTO dbo.service_accounts(system_name,account,secret,notes) VALUES (%s,%s,%s,%s)", svc)
    c.close()


# --------------------------------------------------------------------------- helpers
def run(sql, params=None, fetch="all"):
    c = mssql_conn(DB)
    try:
        cur = c.cursor()
        if params is None:
            cur.execute(sql)
        else:
            cur.execute(sql, params)
        if fetch == "all":
            return cur.fetchall()
        if fetch == "one":
            return cur.fetchone()
        return None
    finally:
        c.close()


def ser(row):
    out = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            v = v.isoformat(sep=" ", timespec="seconds")
        elif hasattr(v, "isoformat"):
            v = v.isoformat()
        out[k] = v
    return out


def jerr(msg, code=400, **extra):
    d = {"error": msg}
    d.update(extra)
    return jsonify(d), code


def dberr(e):
    try:
        m = e.args[1] if len(e.args) > 1 else e.args[0]
        if isinstance(m, bytes):
            m = m.decode("utf-8", "replace")
        return str(m).split("DB-Lib")[0].strip()
    except Exception:  # noqa
        return "database error"


def is_int(s, maxlen=9):
    return isinstance(s, str) and s.isascii() and s.isdigit() and len(s) <= maxlen


# --------------------------------------------------------------------------- page layout
LAYOUT = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title or 'Home' }} - TicketDesk</title>
<style>
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,'Segoe UI',Roboto,sans-serif;background:#f3f3f9;color:#23233a;line-height:1.5}
a{color:#4338ca;text-decoration:none}a:hover{text-decoration:underline}
.top{background:#262a5c;color:#e0e1f5}
.top .in{max-width:1040px;margin:auto;padding:14px 20px;display:flex;align-items:center;gap:24px;flex-wrap:wrap}
.logo{font-size:24px;font-weight:700;color:#fff;letter-spacing:.3px}.logo small{font-size:12px;color:#a9acdf;font-weight:400;margin-left:8px}
.top nav a{color:#e0e1f5;margin-right:16px;font-size:15px}
.top form{margin-left:auto;display:flex;gap:6px}
.top input[type=text]{padding:7px 10px;border:1px solid #6b70b3;border-radius:3px;background:#f8f8ff;min-width:200px}
button,.btn{background:#e0702a;color:#fff;border:0;padding:8px 16px;border-radius:3px;cursor:pointer;font-family:inherit;font-size:14px}
button:hover{background:#bf5a1b}
.wrap{max-width:1040px;margin:26px auto;padding:0 20px}
h1{font-size:27px;margin:0 0 6px}h2{font-size:20px;border-bottom:2px solid #cfd0ea;padding-bottom:5px;margin-top:30px}
.hero{background:#e3e4f6;border:1px solid #cfd0ea;padding:26px;border-radius:4px;margin-bottom:10px}
.hero p{margin:4px 0 0;color:#515378}
.tiles{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}
.tile{background:#fff;border:1px solid #d6d7ee;border-radius:4px;padding:12px 20px;min-width:130px}.tile b{font-size:24px;display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px}
.card{background:#fff;border:1px solid #d6d7ee;border-radius:4px;padding:14px}
.card h3{margin:0 0 4px;font-size:16px}.card p{margin:6px 0 0;font-size:14px;color:#4b4d6e}.card .d{color:#7a7c9c;font-size:13px}
.chips a{display:inline-block;background:#fff;border:1px solid #cfd0ea;border-radius:20px;padding:4px 14px;margin:0 6px 8px 0;font-size:14px}
table{border-collapse:collapse;width:100%;background:#fff;border:1px solid #d6d7ee}
th{background:#e1e2f4;text-align:left;padding:8px 10px;font-size:14px}td{padding:8px 10px;border-top:1px solid #e8e9f6;font-size:14px}
.msg{padding:10px 14px;border-radius:3px;margin:12px 0}.err{background:#fde8e6;border:1px solid #efb1aa;color:#8a1f12}
.ok{background:#e2f4ea;border:1px solid #a4d6b9;color:#175a36}.info{background:#e8eafb;border:1px solid #b8bdee}
label{display:block;margin:12px 0 4px;font-size:14px}
input[type=text],input[type=email],textarea{padding:8px 10px;border:1px solid #b9bbdd;border-radius:3px;width:100%;max-width:420px;background:#fdfdff;font-family:inherit;font-size:14px}
.pill{display:inline-block;background:#e0e1f5;color:#34379a;border-radius:10px;padding:1px 10px;font-size:12px}
.panel{background:#fff;border:1px solid #d6d7ee;border-radius:4px;padding:16px 18px;margin-bottom:14px}
.kv{display:grid;grid-template-columns:130px 1fr;gap:6px 12px;font-size:14px}.kv b{color:#505279;font-weight:600}
footer{background:#262a5c;color:#a9acdf;margin-top:50px;padding:22px 20px;font-size:13px;text-align:center}
footer a{color:#d6d8f5;margin:0 8px}
.pager a,.pager b{margin-right:10px}.muted{color:#7a7c9c;font-size:14px}
@media(max-width:700px){.top form{margin-left:0}}
</style></head><body>
<div class="top"><div class="in">
<a class="logo" href="{{ P }}/">TicketDesk<small>IT support</small></a>
<nav><a href="{{ P }}/">Home</a><a href="{{ P }}/tickets">Tickets</a><a href="{{ P }}/kb">Knowledge base</a><a href="{{ P }}/agents">Agents</a><a href="{{ P }}/stats">Stats</a><a href="{{ P }}/about">About</a></nav>
<form action="{{ P }}/tickets" method="get"><input type="text" name="q" placeholder="Search tickets" value="{{ q or '' }}"><button type="submit">Search</button></form>
</div></div>
<div class="wrap">@@BODY@@</div>
<footer><div><a href="{{ P }}/about">About</a><a href="{{ P }}/contact">Contact</a><a href="{{ P }}/status">Service status</a></div>
<p>&copy; 2026 Northwind Corporate IT. Service desk hours: Mon-Fri 07:00-19:00.</p></footer>
{% raw %}<script>
function E(t,x,c){var e=document.createElement(t);if(x!==undefined&&x!==null)e.textContent=x;if(c)e.className=c;return e}
function A(x,h){var a=E('a',x);a.href=h;return a}
function note(box,x,c){box.textContent='';box.appendChild(E('div',x,'msg '+(c||'info')))}
function getJSON(url,ok,box){
  fetch(url).then(function(r){return r.json().then(function(j){return {s:r.status,j:j}})}).then(function(o){
    if(o.s>=400){note(box,o.j.error||'Something went wrong.','err')}else{ok(o.j)}
  }).catch(function(){note(box,'The service could not be reached.','err')})
}
function grid(heads,rows){
  var t=E('table'),h=E('tr');heads.forEach(function(x){h.appendChild(E('th',x))});t.appendChild(h);
  rows.forEach(function(r){var tr=E('tr');r.forEach(function(c){var td=E('td');
    if(c&&c.nodeType){td.appendChild(c)}else{td.textContent=(c===null||c===undefined)?'':c}tr.appendChild(td)});t.appendChild(tr)});
  return t
}
function params(keys){var q=new URLSearchParams(location.search),p=new URLSearchParams();
  keys.forEach(function(k){if(q.has(k))p.set(k,q.get(k))});return p}
</script>{% endraw %}
</body></html>"""


def render(body, **ctx):
    ctx.setdefault("title", None)
    ctx.setdefault("q", "")
    return render_template_string(LAYOUT.replace("@@BODY@@", body), P=P, **ctx)


# --------------------------------------------------------------------------- pages
HOME = """<div class="hero"><h1>IT support, one place</h1><p>Check on an existing ticket, read a how-to article or find the right person on the service desk.</p></div>
<div class="tiles" id="tiles"></div>
<h2>Recently opened tickets</h2>
<div id="recent"><p class="muted">Loading&hellip;</p></div>
<p><a href="{{ P }}/tickets">All tickets &rarr;</a></p>
<h2>Where to start</h2>
<div class="grid">
<div class="card"><h3><a href="{{ P }}/kb">Knowledge base</a></h3><p>Step-by-step guides for passwords, VPN, printers and more.</p></div>
<div class="card"><h3><a href="{{ P }}/agents">Our agents</a></h3><p>Meet the teams who look after your devices and accounts.</p></div>
<div class="card"><h3><a href="{{ P }}/stats">Service statistics</a></h3><p>How many tickets we handle and how quickly they close.</p></div>
</div>
{% raw %}<script>
getJSON('/desk/api/stats?period=30d',function(d){var t=document.getElementById('tiles');
  [['Tickets (30 days)',d.total],['Open',d.by_status.open||0],['In progress',d.by_status.in_progress||0],['Resolved',d.by_status.resolved||0]].forEach(function(x){
    var b=E('div',null,'tile');b.appendChild(E('b',x[1]));b.appendChild(document.createTextNode(x[0]));t.appendChild(b)})},document.getElementById('tiles'));
getJSON('/desk/api/tickets?status=open',function(d){var r=document.getElementById('recent');r.textContent='';
  r.appendChild(grid(['#','Subject','Category','Priority','Opened'],d.items.slice(0,6).map(function(i){
    return [String(i.id),A(i.subject,'/desk/ticket?id='+i.id),i.category,String(i.priority),i.created_at]})))},document.getElementById('recent'));
</script>{% endraw %}"""


@bp.route("/")
def home():
    return render(HOME, title="Home")


TICKETS = """<h1>Tickets</h1>
<p class="chips"><a href="{{ P }}/tickets">All</a><a href="{{ P }}/tickets?status=open">Open</a><a href="{{ P }}/tickets?status=in_progress">In progress</a><a href="{{ P }}/tickets?status=resolved">Resolved</a><a href="{{ P }}/tickets?status=closed">Closed</a></p>
<p class="chips"><span class="muted">Priority:</span> <a href="{{ P }}/tickets?priority=1">1</a><a href="{{ P }}/tickets?priority=2">2</a><a href="{{ P }}/tickets?priority=3">3</a><a href="{{ P }}/tickets?priority=4">4</a></p>
<div id="out"><p class="muted">Loading&hellip;</p></div><p class="pager" id="pager"></p>
{% raw %}<script>
var box=document.getElementById('out'),p=params(['status','priority','q','page']);
getJSON('/desk/api/tickets?'+p.toString(),function(d){
  box.textContent='';
  if(!d.items.length){note(box,'No tickets matched.');return}
  box.appendChild(grid(['#','Subject','Status','Priority','Category','Requester','Opened'],d.items.map(function(i){
    return [String(i.id),A(i.subject,'/desk/ticket?id='+i.id),i.status,String(i.priority),i.category,i.requester,i.created_at]})));
  var n=Math.ceil(d.total/d.per_page),pg=document.getElementById('pager');
  if(n>1){for(var k=1;k<=n;k++){if(k===d.page){pg.appendChild(E('b',String(k)))}else{var q=params(['status','priority','q']);q.set('page',k);pg.appendChild(A(String(k),'/desk/tickets?'+q.toString()))}}}
},box);
</script>{% endraw %}"""


@bp.route("/tickets")
def tickets_page():
    return render(TICKETS, title="Tickets", q=request.args.get("q", "")[:60])


TICKET = """<div id="out"><p class="muted">Loading&hellip;</p></div>
<p><a href="{{ P }}/tickets">&larr; Back to tickets</a></p>
{% raw %}<script>
var box=document.getElementById('out'),id=new URLSearchParams(location.search).get('id');
if(!id){note(box,'No ticket was specified.')}else{
getJSON('/desk/api/ticket?id='+encodeURIComponent(id),function(d){
  box.textContent='';box.appendChild(E('h1','#'+d.id+' '+d.subject));
  var pn=E('div',null,'panel'),kv=E('div',null,'kv');
  [['Status',d.status],['Priority',String(d.priority)],['Category',d.category],['Requester',d.requester],['Assigned to',d.assignee||'Unassigned'],['Opened',d.created_at],['Updated',d.updated_at],['Details',d.description]].forEach(function(x){
    kv.appendChild(E('b',x[0]));kv.appendChild(E('span',x[1]))});
  pn.appendChild(kv);box.appendChild(pn);box.appendChild(E('h2','Conversation'));
  if(!d.comments.length){box.appendChild(E('p','No replies yet.','muted'))}
  d.comments.forEach(function(c){var cd=E('div',null,'card');cd.style.marginBottom='10px';cd.appendChild(E('b',c.author));cd.appendChild(E('span',' - '+c.created_at,'muted'));cd.appendChild(E('p',c.body));box.appendChild(cd)})
},box)}
</script>{% endraw %}"""


@bp.route("/ticket")
def ticket_page():
    return render(TICKET, title="Ticket")


KB = """<h1>Knowledge base</h1>
<form method="get" class="panel"><label>Search articles</label><input type="text" name="q" value="{{ q }}" placeholder="e.g. password"><br><br><button type="submit">Search</button></form>
<div id="out"><p class="muted">Loading&hellip;</p></div>
{% raw %}<script>
var box=document.getElementById('out'),p=params(['q']);
getJSON('/desk/api/kb?'+p.toString(),function(d){
  box.textContent='';
  if(!d.items.length){note(box,'No articles matched your search.');return}
  d.items.forEach(function(a){var c=E('div',null,'card');c.style.marginBottom='10px';c.appendChild(E('h3',a.title));c.appendChild(E('p',a.body));c.appendChild(E('div',a.views+' views','d'));box.appendChild(c)})
},box);
</script>{% endraw %}"""


@bp.route("/kb")
def kb_page():
    return render(KB, title="Knowledge base", q=request.args.get("q", "")[:60])


AGENTS = """<h1>Service desk agents</h1>
<p class="chips" id="teams"></p>
<div id="out"><p class="muted">Loading&hellip;</p></div>
{% raw %}<script>
var box=document.getElementById('out'),p=params(['team']);
getJSON('/desk/api/agents?'+p.toString(),function(d){
  var tm=document.getElementById('teams');tm.appendChild(A('All teams','/desk/agents'));
  d.teams.forEach(function(t){tm.appendChild(A(t,'/desk/agents?team='+encodeURIComponent(t)))});
  box.textContent='';
  if(!d.items.length){note(box,'No agents found for that team.');return}
  box.appendChild(grid(['Name','Role','Team','Email'],d.items.map(function(a){return [a.full_name,a.job_title,a.team,a.email]})));
},box);
</script>{% endraw %}"""


@bp.route("/agents")
def agents_page():
    return render(AGENTS, title="Agents")


STATS = """<h1>Service statistics</h1>
<p class="chips"><a href="{{ P }}/stats?period=7d">7 days</a><a href="{{ P }}/stats?period=30d">30 days</a><a href="{{ P }}/stats?period=90d">90 days</a><a href="{{ P }}/stats?period=1y">1 year</a><a href="{{ P }}/stats?period=all">All time</a></p>
<div id="out"><p class="muted">Loading&hellip;</p></div>
{% raw %}<script>
var box=document.getElementById('out'),p=params(['period']);
getJSON('/desk/api/stats?'+p.toString(),function(d){
  box.textContent='';box.appendChild(E('p','Tickets in period: '+d.total,'muted'));
  var h=function(t,o){box.appendChild(E('h2',t));box.appendChild(grid([t.replace('By ',''),'Tickets'],Object.keys(o).map(function(k){return [k,String(o[k])]})))};
  h('By status',d.by_status);h('By category',d.by_category);h('By priority',d.by_priority);
},box);
</script>{% endraw %}"""


@bp.route("/stats")
def stats_page():
    return render(STATS, title="Stats")


ABOUT = """<h1>About TicketDesk</h1>
<p>TicketDesk is the support portal run by Northwind Corporate IT. Every request, from a forgotten password to a new laptop, is logged here so that nothing gets lost and everyone can see how things are going.</p>
<p>The service desk is staffed by six agents across four teams and handles around forty requests a month.</p>"""


@bp.route("/about")
def about():
    return render(ABOUT, title="About")


CONTACT = """<h1>Contact the service desk</h1>
{% if sent %}<div class="msg ok">Thanks, your message has been received. An agent will reply within one working day.</div>{% endif %}
<form method="post" class="panel"><label>Your name</label><input type="text" name="name" required>
<label>Email</label><input type="email" name="email" required>
<label>Message</label><textarea name="message" required></textarea><br><br><button type="submit">Send</button></form>
<p class="muted">Urgent? Call ext. 142.</p>"""


@bp.route("/contact", methods=["GET", "POST"])
def contact():
    sent = False
    if request.method == "POST":
        try:
            run("INSERT INTO dbo.contact_messages(name,email,body,created_at) VALUES (%s,%s,%s,%s)",
                ((request.form.get("name") or "")[:80], (request.form.get("email") or "")[:120],
                 (request.form.get("message") or "")[:500], datetime.utcnow()), None)
            sent = True
        except pymssql.Error:
            pass
    return render(CONTACT, title="Contact", sent=sent)


@bp.route("/status")
def status_page():
    return render("<h1>Service status</h1><div class=\"msg ok\">All systems operational.</div>"
                  "<p class=\"muted\">No incidents have been reported in the last 30 days.</p>", title="Service status")


@bp.route("/admin")
@bp.route("/admin/")
@bp.route("/backup")
@bp.route("/backup/")
def forbidden_page():
    return render("<h1>Access denied</h1><p>You do not have permission to view this page.</p>", title="Access denied"), 403


# --------------------------------------------------------------------------- JSON API (used by the pages)
@bp.get("/api/tickets")
def tickets_list():
    a = request.args
    where = ["1=1"]
    st = a.get("status")
    if st:
        if st not in STATUSES:
            return jerr("Invalid status filter")
        where.append(f"t.status = '{st}'")
    pr = a.get("priority")
    if pr:
        if not re.fullmatch(r"[1-4]", pr):
            return jerr("Invalid priority filter")
        where.append(f"t.priority = {int(pr)}")
    q = a.get("q")
    if q:
        if not re.fullmatch(r"[A-Za-z0-9_ .@#-]{1,60}", q):
            return jerr("Invalid search term")
        where.append(f"t.subject LIKE '%{q}%'")
    try:
        page = int(a.get("page", "1"))
    except ValueError:
        return jerr("Invalid pagination")
    per = 10
    if not 1 <= page <= 1000:
        return jerr("Invalid pagination")

    custom = "orderby" in a
    order = "t.created_at DESC, t.id DESC"
    if custom:
        order = a.get("orderby", "")
        if len(order) > 250 or BLOCK.search(order):
            return jerr("Invalid ordering")
    w = " AND ".join(where)
    sql = ("SELECT t.id AS id, t.subject AS subject, t.status AS status, t.priority AS priority, "
           "c.name AS category, r.full_name AS requester, t.created_at AS created_at "
           "FROM dbo.tickets t JOIN dbo.categories c ON c.id = t.category_id JOIN dbo.users r ON r.id = t.requester_id "
           f"WHERE {w} ORDER BY {order} OFFSET {(page - 1) * per} ROWS FETCH NEXT {per} ROWS ONLY")
    try:
        rows = run(sql)
        total = run(f"SELECT COUNT(*) AS n FROM dbo.tickets t WHERE {w}", None, "one")["n"]
    except pymssql.Error as e:
        if custom:
            return jerr("Unable to load tickets", 500, detail=dberr(e))
        return jerr("Unable to load tickets", 500)
    out = {"items": [ser(r) for r in rows], "page": page, "per_page": per, "total": total}
    if custom:
        out["order_by"] = order
    return jsonify(out)


@bp.get("/api/ticket")
def ticket_get():
    raw = request.args.get("id")
    if not is_int(raw):
        return jerr("Invalid ticket id")
    tid = int(raw)
    try:
        t = run("SELECT t.id,t.subject,t.description,t.status,t.priority,c.name AS category,r.full_name AS requester,a.full_name AS assignee,t.created_at,t.updated_at "
                "FROM dbo.tickets t JOIN dbo.categories c ON c.id=t.category_id JOIN dbo.users r ON r.id=t.requester_id "
                "LEFT JOIN dbo.users a ON a.id=t.assignee_id WHERE t.id=%s", (tid,), "one")
        if not t:
            return jerr("Ticket not found", 404)
        cm = run("SELECT cm.id,us.full_name AS author,cm.body,cm.created_at FROM dbo.comments cm JOIN dbo.users us ON us.id=cm.author_id WHERE cm.ticket_id=%s ORDER BY cm.id", (tid,))
    except pymssql.Error:
        return jerr("Unable to load ticket", 500)
    out = ser(t)
    out["comments"] = [ser(x) for x in cm]
    return jsonify(out)


@bp.get("/api/kb")
def kb_api():
    q = request.args.get("q", "")
    if len(q) > 60:
        return jerr("Search term too long")
    try:
        rows = run("SELECT TOP 25 id,title,body,views FROM dbo.knowledge_base WHERE title LIKE %s OR body LIKE %s ORDER BY views DESC",
                   ("%" + q + "%", "%" + q + "%"))
    except pymssql.Error:
        return jerr("Search failed", 500)
    return jsonify({"items": [ser(r) for r in rows]})


@bp.get("/api/agents")
def agents_api():
    team = request.args.get("team")
    try:
        teams = [r["team"] for r in run("SELECT DISTINCT team FROM dbo.users WHERE team IS NOT NULL ORDER BY team")]
        if team:
            rows = run("SELECT full_name,job_title,team,email FROM dbo.users WHERE role IN ('agent','admin') AND team = %s ORDER BY full_name", (team,))
        else:
            rows = run("SELECT full_name,job_title,team,email FROM dbo.users WHERE role IN ('agent','admin') ORDER BY full_name")
    except pymssql.Error:
        return jerr("Unable to load agents", 500)
    return jsonify({"items": [ser(r) for r in rows], "teams": teams})


@bp.get("/api/stats")
def stats_api():
    period = request.args.get("period", "30d")
    if period not in PERIODS:
        return jerr("Invalid period")
    try:
        mx = run("SELECT MAX(created_at) AS m FROM dbo.tickets", None, "one")["m"]
        days = PERIODS[period]
        cutoff = (mx - timedelta(days=days)) if days else datetime(2000, 1, 1)
        by_status = run("SELECT status, COUNT(*) AS n FROM dbo.tickets WHERE created_at >= %s GROUP BY status", (cutoff,))
        by_cat = run("SELECT c.name AS k, COUNT(*) AS n FROM dbo.tickets t JOIN dbo.categories c ON c.id=t.category_id WHERE t.created_at >= %s GROUP BY c.name ORDER BY c.name", (cutoff,))
        by_pri = run("SELECT priority AS k, COUNT(*) AS n FROM dbo.tickets WHERE created_at >= %s GROUP BY priority ORDER BY priority", (cutoff,))
    except pymssql.Error:
        return jerr("Unable to load statistics", 500)
    return jsonify({"period": period, "total": sum(r["n"] for r in by_status),
                    "by_status": {r["status"]: r["n"] for r in by_status},
                    "by_category": {r["k"]: r["n"] for r in by_cat},
                    "by_priority": {"P%s" % r["k"]: r["n"] for r in by_pri}})


# --------------------------------------------------------------------------- hidden API endpoints (decoys, all safe)
ASSET_SORTS = {"tag": "tag", "kind": "kind", "model": "model", "location": "location", "purchased": "purchased DESC"}


@bp.get("/api/assets")
def assets_api():
    a = request.args
    sort = a.get("sort", "tag")
    if sort not in ASSET_SORTS:
        return jerr("Unknown sort field")
    tag = a.get("tag")
    try:
        if tag:
            rows = run("SELECT TOP 50 id,tag,kind,model,assigned_to,location,purchased FROM dbo.assets WHERE tag = %s ORDER BY " + ASSET_SORTS[sort], (tag,))
        else:
            rows = run("SELECT TOP 50 id,tag,kind,model,assigned_to,location,purchased FROM dbo.assets ORDER BY " + ASSET_SORTS[sort])
    except pymssql.Error:
        return jerr("Unable to load assets", 500)
    return jsonify({"items": [ser(r) for r in rows]})


@bp.get("/api/categories")
def categories_api():
    try:
        rows = run("SELECT id,name,description FROM dbo.categories ORDER BY name")
    except pymssql.Error:
        return jerr("Unable to load categories", 500)
    return jsonify({"items": [ser(r) for r in rows]})


@bp.get("/api/users")
def users_api():
    raw = request.args.get("id")
    try:
        if raw is None:
            rows = run("SELECT id,full_name,department FROM dbo.users ORDER BY id")
            return jsonify({"items": [ser(r) for r in rows]})
        if not is_int(raw):
            return jerr("Invalid user id")
        r = run("SELECT id,full_name,department,job_title FROM dbo.users WHERE id=%s", (int(raw),), "one")
    except pymssql.Error:
        return jerr("Unable to load users", 500)
    if not r:
        return jerr("User not found", 404)
    return jsonify(ser(r))


@bp.get("/api/export")
def export_api():
    raw = request.args.get("id")
    fmt = request.args.get("format", "json")
    if not is_int(raw):
        return jerr("A numeric id is required")
    if fmt not in ("json", "csv"):
        return jerr("Unsupported format")
    try:
        r = run("SELECT id,subject,status,priority,created_at FROM dbo.tickets WHERE id=%s", (int(raw),), "one")
    except pymssql.Error:
        return jerr("Export failed", 500)
    if not r:
        return jerr("Ticket not found", 404)
    return jsonify(ser(r))


@bp.get("/api/health")
def health_api():
    return jsonify({"status": "ok"})


@bp.route("/api/reports")
@bp.route("/api/reports/<path:rest>")
@bp.route("/api/config")
@bp.route("/api/internal")
@bp.route("/api/internal/<path:rest>")
def restricted_api(rest=None):
    return jerr("Access denied", 403)


@bp.route("/api/v1")
@bp.route("/api/v1/<path:rest>")
def retired_api(rest=None):
    return jerr("This API version has been retired", 410)
