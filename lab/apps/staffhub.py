"""StaffHub - corporate employee directory / intranet (public pages only)."""
import random

from flask import Blueprint, render_template_string, request

from ..common import mysql_conn

SLUG = "staffhub"
P = "/staff"
META = {
    "slug": SLUG,
    "title": "StaffHub",
    "tagline": "Company directory, announcements and helpdesk for Northwind Logistics employees.",
    "prefix": P,
}
bp = Blueprint("staffhub", __name__)

# --------------------------------------------------------------------------- helpers


def db():
    return mysql_conn(SLUG)


def errtext(e):
    return str(e.args[1]) if len(e.args) > 1 else str(e)


LAYOUT = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title or 'Home' }} - StaffHub</title>
<style>
*{box-sizing:border-box}
body{margin:0;font-family:'Segoe UI',system-ui,Roboto,sans-serif;background:#eef3f7;color:#1c2b3a;line-height:1.5}
a{color:#0d6e8a;text-decoration:none}a:hover{text-decoration:underline}
.top{background:#12365a;color:#dbe9f5}
.top .in{max-width:1040px;margin:auto;padding:14px 20px;display:flex;align-items:center;gap:24px;flex-wrap:wrap}
.logo{font-size:25px;font-weight:700;color:#fff;letter-spacing:.3px}.logo small{font-size:12px;color:#8fb7d6;font-weight:400;margin-left:8px;text-transform:uppercase;letter-spacing:1px}
.top nav a{color:#dbe9f5;margin-right:16px;font-size:15px}
.top form{margin-left:auto;display:flex;gap:6px}
.top input[type=text]{padding:7px 10px;border:1px solid #4d7ba3;border-radius:3px;background:#f6fbff;min-width:200px}
button,.btn{background:#1b8a8f;color:#fff;border:0;padding:8px 16px;border-radius:3px;cursor:pointer;font-family:inherit;font-size:14px}
button:hover{background:#146c70}
.wrap{max-width:1040px;margin:26px auto;padding:0 20px}
h1{font-size:27px;margin:0 0 6px}h2{font-size:20px;border-bottom:2px solid #c3d4e3;padding-bottom:5px;margin-top:30px}
.hero{background:#dbe8f3;border:1px solid #c3d4e3;padding:26px;border-radius:4px;margin-bottom:10px}
.hero p{margin:4px 0 0;color:#46607a}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(235px,1fr));gap:16px}
.card{background:#fff;border:1px solid #cddbe8;border-radius:4px;padding:14px}
.card h3{margin:0 0 4px;font-size:16px}.card .d{color:#6b7f92;font-size:13px}.card p{margin:8px 0 0;font-size:14px}
.cats a{display:inline-block;background:#fff;border:1px solid #c3d4e3;border-radius:20px;padding:4px 14px;margin:0 6px 8px 0;font-size:14px}
table{border-collapse:collapse;width:100%;background:#fff;border:1px solid #cddbe8}
th{background:#d9e6f1;text-align:left;padding:8px 10px;font-size:14px}td{padding:8px 10px;border-top:1px solid #e3ecf4;font-size:14px}
.msg{padding:10px 14px;border-radius:3px;margin:12px 0}.err{background:#fde8e6;border:1px solid #efb1aa;color:#8a1f12}
.ok{background:#e2f4ea;border:1px solid #a4d6b9;color:#175a36}.info{background:#e6f1fb;border:1px solid #b2d1ec}
label{display:block;margin:12px 0 4px;font-size:14px}
input[type=text],input[type=email],select,textarea{padding:8px 10px;border:1px solid #b5c7d8;border-radius:3px;width:100%;max-width:420px;background:#fcfeff;font-family:inherit;font-size:14px}
textarea{min-height:110px}
.panel{background:#fff;border:1px solid #cddbe8;border-radius:4px;padding:16px 18px;margin-bottom:14px}
.pill{display:inline-block;background:#d8eeee;color:#126a6e;border-radius:10px;padding:1px 10px;font-size:12px}
.kv{display:grid;grid-template-columns:130px 1fr;gap:6px 12px;font-size:14px}.kv b{color:#4b6277;font-weight:600}
.avatar{width:70px;height:70px;border-radius:50%;background:#1b8a8f;color:#fff;font-size:28px;display:flex;align-items:center;justify-content:center;margin-bottom:10px}
footer{background:#12365a;color:#9fbdd6;margin-top:50px;padding:22px 20px;font-size:13px;text-align:center}
footer a{color:#cfe4f5;margin:0 8px}
.pager a{margin-right:10px}.muted{color:#6b7f92;font-size:14px}
@media(max-width:700px){.top form{margin-left:0}}
</style></head><body>
<div class="top"><div class="in">
<a class="logo" href="{{ P }}/">StaffHub<small>Northwind Logistics</small></a>
<nav><a href="{{ P }}/">Home</a><a href="{{ P }}/directory">Directory</a><a href="{{ P }}/departments">Departments</a><a href="{{ P }}/news">News</a><a href="{{ P }}/helpdesk">Helpdesk</a><a href="{{ P }}/about">About</a></nav>
<form action="{{ P }}/search" method="get"><input type="text" name="q" placeholder="Find a colleague" value="{{ q or '' }}"><button type="submit">Search</button></form>
</div></div>
<div class="wrap">@@BODY@@</div>
<footer><div><a href="{{ P }}/about">About</a><a href="{{ P }}/contact">Contact</a><a href="{{ P }}/helpdesk/track">Track a request</a><a href="{{ P }}/handbook">Handbook</a></div>
<p>&copy; 2026 Northwind Logistics. 200 Freight Street, Chicago. Intranet open to all employees.</p></footer>
</body></html>"""


def render(body, **ctx):
    ctx.setdefault("title", None)
    ctx.setdefault("q", "")
    return render_template_string(LAYOUT.replace("@@BODY@@", body), P=P, **ctx)


# --------------------------------------------------------------------------- pages

HOME = """<div class="hero"><h1>Welcome to StaffHub</h1><p>Everything you need at Northwind Logistics in one place: find a colleague, read the latest news and raise a helpdesk request.</p></div>
<h2>Browse by department</h2>
<div class="cats">{% for d in depts %}<a href="{{ P }}/directory?dept={{ d|urlencode }}">{{ d }}</a>{% endfor %}</div>
<h2>Latest announcements</h2>
<div class="grid">{% for a in news %}<div class="card"><h3><a href="{{ P }}/news?id={{ a['id'] }}">{{ a['headline'] }}</a></h3><div class="d">{{ a['posted'] }} &middot; {{ a['author'] }}</div></div>{% endfor %}</div>
<h2>New starters</h2>
<table><tr><th>Name</th><th>Role</th><th>Department</th><th>Joined</th></tr>
{% for e in starters %}<tr><td><a href="{{ P }}/profile?id={{ e['id'] }}">{{ e['full_name'] }}</a></td><td>{{ e['job_title'] }}</td><td>{{ e['department'] }}</td><td>{{ e['hire_date'] }}</td></tr>{% endfor %}</table>"""


@bp.route("/")
def home():
    c = db()
    cur = c.cursor()
    cur.execute("SELECT name FROM departments ORDER BY name")
    depts = [r["name"] for r in cur.fetchall()]
    cur.execute("SELECT id, headline, author, posted FROM announcements ORDER BY posted DESC LIMIT 4")
    news = cur.fetchall()
    cur.execute("SELECT id, full_name, job_title, department, hire_date FROM employees ORDER BY hire_date DESC LIMIT 5")
    starters = cur.fetchall()
    c.close()
    return render(HOME, title="Home", depts=depts, news=news, starters=starters)


DIRECTORY = """<h1>Employee directory</h1>
<p>{% if dept %}Department: <b>{{ dept }}</b> &middot; <a href="{{ P }}/directory">show all</a>{% else %}<span class="muted">{{ total }} employees</span>{% endif %}</p>
{% if notice %}<div class="msg info">{{ notice }}</div>{% endif %}
<table><tr><th>Name</th><th>Title</th><th>Department</th><th>Office</th><th>Email</th></tr>
{% for e in rows %}<tr><td><a href="{{ P }}/profile?id={{ e['id'] }}">{{ e['full_name'] }}</a></td><td>{{ e['job_title'] }}</td><td><a href="{{ P }}/directory?dept={{ e['department']|urlencode }}">{{ e['department'] }}</a></td><td>{{ e['office'] }}</td><td>{{ e['email'] }}</td></tr>
{% else %}<tr><td colspan="5">No employees found.</td></tr>{% endfor %}</table>
{% if pages > 1 %}<p class="pager">Page: {% for n in range(1, pages+1) %}{% if n == page %}<b>{{ n }}</b> {% else %}<a href="{{ P }}/directory?page={{ n }}{% if dept %}&amp;dept={{ dept|urlencode }}{% endif %}">{{ n }}</a>{% endif %}{% endfor %}</p>{% endif %}
<p class="muted"><a href="{{ P }}/directory/print">Printable directory</a></p>"""


@bp.route("/directory")
def directory():
    dept = request.args.get("dept", "")
    notice = None
    page = 1
    raw = request.args.get("page", "1")
    if raw.isdigit() and 0 < int(raw) < 1000:
        page = int(raw)
    else:
        notice = "Invalid page number. Showing the first page."
    c = db()
    cur = c.cursor()
    if dept:
        cur.execute("SELECT COUNT(*) AS n FROM employees WHERE department = %s", (dept,))
    else:
        cur.execute("SELECT COUNT(*) AS n FROM employees")
    total = cur.fetchone()["n"]
    pages = max(1, (total + 14) // 15)
    page = min(page, pages)
    if dept:
        cur.execute("SELECT id, full_name, job_title, department, office, email FROM employees WHERE department = %s ORDER BY full_name LIMIT 15 OFFSET %s",
                    (dept, (page - 1) * 15))
    else:
        cur.execute("SELECT id, full_name, job_title, department, office, email FROM employees ORDER BY full_name LIMIT 15 OFFSET %s",
                    ((page - 1) * 15,))
    rows = cur.fetchall()
    c.close()
    return render(DIRECTORY, title="Directory", rows=rows, dept=dept, total=total, pages=pages, page=page, notice=notice)


@bp.route("/directory/print")
def directory_print():
    return render("<h1>Printable directory</h1><div class=\"msg info\">The printable edition is produced once a quarter. The next edition will be available in the new year.</div>"
                  "<p><a href=\"" + P + "/directory\">Back to the online directory</a></p>", title="Printable directory")


DEPTS = """<h1>Departments</h1>
<table><tr><th>Department</th><th>Head</th><th>Floor</th><th>Headcount</th></tr>
{% for d in rows %}<tr><td><a href="{{ P }}/directory?dept={{ d['name']|urlencode }}">{{ d['name'] }}</a></td><td>{{ d['head'] }}</td><td>{{ d['floor'] }}</td><td>{{ d['n'] }}</td></tr>{% endfor %}</table>"""


@bp.route("/departments")
def departments():
    c = db()
    cur = c.cursor()
    cur.execute("SELECT d.name, d.head, d.floor, (SELECT COUNT(*) FROM employees e WHERE e.department = d.name) AS n FROM departments d ORDER BY d.name")
    rows = cur.fetchall()
    c.close()
    return render(DEPTS, title="Departments", rows=rows)


PROFILE = """{% if emp %}
<div class="panel"><div class="avatar">{{ (emp['full_name'] or '?')[0] }}</div>
<h1>{{ emp['full_name'] }}</h1><p class="muted">{{ emp['job_title'] }} &middot; <span class="pill">{{ emp['department'] }}</span></p>
<div class="kv"><b>Employee ID</b><span>{{ emp['id'] }}</span><b>Email</b><span>{{ emp['email'] }}</span><b>Phone</b><span>{{ emp['phone'] }}</span><b>Office</b><span>{{ emp['office'] }}</span><b>About</b><span>{{ emp['bio'] }}</span></div></div>
<p><a href="{{ P }}/directory">&larr; Back to directory</a></p>
{% else %}<div class="msg {{ 'err' if error else 'info' }}">{{ error or 'No employee found with that reference.' }}</div>{% endif %}"""

BLACKLIST = ["union", "select", "from", "information_schema", "sleep", "benchmark", "load_file", "outfile", "--", "#"]


@bp.route("/profile")
def profile():
    ref = request.args.get("id", "1")
    if any(k in ref for k in BLACKLIST):
        return render(PROFILE, title="Profile", emp=None, error="Invalid employee reference."), 400
    emp, error = None, None
    c = db()
    try:
        cur = c.cursor()
        cur.execute(f"SELECT id, full_name, job_title, department, email, phone, office, bio FROM employees WHERE id = {ref}")
        emp = cur.fetchone()
    except Exception as e:  # noqa
        error = f"Could not load profile: {errtext(e)}"
    c.close()
    return render(PROFILE, title=emp["full_name"] if emp else "Profile", emp=emp, error=error)


SEARCH = """<h1>Search</h1>
{% if error %}<div class="msg err">{{ error }}</div>{% endif %}
{% if rows is not none %}<p class="muted">{{ rows|length }} result(s) for &ldquo;{{ q }}&rdquo;</p>
<table><tr><th>Name</th><th>Title</th><th>Department</th><th>Email</th></tr>
{% for e in rows %}<tr><td><a href="{{ P }}/profile?id={{ e['id'] }}">{{ e['full_name'] }}</a></td><td>{{ e['job_title'] }}</td><td>{{ e['department'] }}</td><td>{{ e['email'] }}</td></tr>{% endfor %}</table>{% endif %}"""


@bp.route("/search")
def search():
    q = request.args.get("q", "").strip()
    rows, error = None, None
    if q:
        if not all(ch.isalnum() or ch in " .-_@" for ch in q):
            error = "Search terms may only contain letters, numbers and spaces."
        else:
            c = db()
            cur = c.cursor()
            like = f"%{q}%"
            cur.execute("SELECT id, full_name, job_title, department, email FROM employees WHERE full_name LIKE %s OR email LIKE %s OR job_title LIKE %s ORDER BY full_name LIMIT 30",
                        (like, like, like))
            rows = cur.fetchall()
            c.close()
    return render(SEARCH, title="Search", q=q, rows=rows, error=error)


NEWS = """{% if item %}
<h1>{{ item['headline'] }}</h1><p class="muted">{{ item['posted'] }} &middot; {{ item['author'] }}</p><p>{{ item['body'] }}</p>
<p><a href="{{ P }}/news">&larr; All announcements</a></p>
{% elif items is not none %}
<h1>News and announcements</h1>
<table><tr><th>Date</th><th>Headline</th><th>From</th></tr>
{% for a in items %}<tr><td>{{ a['posted'] }}</td><td><a href="{{ P }}/news?id={{ a['id'] }}">{{ a['headline'] }}</a></td><td>{{ a['author'] }}</td></tr>{% endfor %}</table>
{% else %}<div class="msg info">That announcement could not be found.</div><p><a href="{{ P }}/news">&larr; All announcements</a></p>{% endif %}"""


@bp.route("/news")
def news():
    raw = request.args.get("id")
    c = db()
    cur = c.cursor()
    item, items = None, None
    if raw is None:
        cur.execute("SELECT id, headline, author, posted FROM announcements ORDER BY posted DESC")
        items = cur.fetchall()
    elif raw.isdigit() and len(raw) < 9:
        cur.execute("SELECT id, headline, body, author, posted FROM announcements WHERE id = %s", (int(raw),))
        item = cur.fetchone()
    c.close()
    return render(NEWS, title=item["headline"] if item else "News", item=item, items=items)


# --------------------------------------------------------------------------- helpdesk

HELPDESK = """<h1>IT &amp; facilities helpdesk</h1><p class="muted">Raise a request and we will get back to you within one working day.</p>
{% if error %}<div class="msg err">{{ error }}</div>{% endif %}
<form method="post" class="panel">
<label>Your name</label><input type="text" name="name" maxlength="250" required>
<label>Category</label><select name="category">{% for c in cats %}<option value="{{ c }}">{{ c }}</option>{% endfor %}</select>
<label>Subject</label><input type="text" name="subject" maxlength="300" required>
<label>Details</label><textarea name="message" maxlength="1000" required></textarea>
<br><br><button type="submit">Submit request</button></form>
<p class="muted">Already raised one? <a href="{{ P }}/helpdesk/track">Track a request</a>.</p>"""

DONE = """<h1>Request received</h1><div class="msg ok">Your request has been logged with reference <b>{{ ref }}</b>.</div>
<p>You can follow its progress on the <a href="{{ P }}/helpdesk/track?ref={{ ref|urlencode }}">tracking page</a>.</p>"""

CATS = ["IT support", "Facilities", "Access request", "Equipment", "Other"]


@bp.route("/helpdesk", methods=["GET", "POST"])
def helpdesk():
    error = None
    if request.method == "POST":
        name = request.form.get("name", "")[:250]
        subject = request.form.get("subject", "")[:300]
        message = request.form.get("message", "")[:1000]
        cat = request.form.get("category", "Other")
        if cat not in CATS:
            cat = "Other"
        c = db()
        try:
            cur = c.cursor()
            cur.execute("SELECT COALESCE(MAX(id), 1000) + 1 AS n FROM tickets")
            ref = "REQ-%d" % cur.fetchone()["n"]
            sql = ("INSERT INTO tickets (ref, requester, category, subject, message, status, created_at) "
                   f"VALUES ('{ref}', '{name}', '{cat}', '{subject}', '{message}', 'open', NOW())")
            cur.execute(sql)
            c.close()
            return render(DONE, title="Request received", ref=ref)
        except Exception as e:  # noqa
            error = f"We could not log your request: {errtext(e)}"
        c.close()
    return render(HELPDESK, title="Helpdesk", error=error, cats=CATS)


TRACK = """<h1>Track a request</h1>
<form method="get" class="panel"><label>Reference</label><input type="text" name="ref" value="{{ ref }}" placeholder="REQ-1001"><br><br><button type="submit">Look up</button></form>
{% if searched %}{% if t %}<div class="panel"><h3>{{ t['ref'] }} &middot; {{ t['subject'] }}</h3><div class="muted">{{ t['category'] }} &middot; opened {{ t['created_at'] }}</div>
<p>Status: <span class="pill">{{ t['status'] }}</span></p></div>
{% else %}<div class="msg info">No request found with that reference.</div>{% endif %}{% endif %}"""


@bp.route("/helpdesk/track")
def track():
    ref = request.args.get("ref", "").strip()
    t = None
    if ref:
        c = db()
        cur = c.cursor()
        cur.execute("SELECT ref, subject, category, status, created_at FROM tickets WHERE ref = %s", (ref,))
        t = cur.fetchone()
        c.close()
    return render(TRACK, title="Track a request", ref=ref, t=t, searched=bool(ref))


# --------------------------------------------------------------------------- static pages

ABOUT = """<h1>About StaffHub</h1>
<p>StaffHub is the Northwind Logistics intranet. It brings the staff directory, company announcements and the IT and facilities helpdesk together so that everyone can find what they need without leaving their desk.</p>
<p>Northwind Logistics runs depots in Chicago, Dallas, Atlanta and Denver and employs around four hundred people across eight departments.</p>"""


@bp.route("/about")
def about():
    return render(ABOUT, title="About")


CONTACT = """<h1>Contact</h1>
<div class="panel"><div class="kv"><b>Reception</b><span>555-0100</span><b>IT service desk</b><span>555-0142 (ext. 142)</span><b>Facilities</b><span>555-0177</span><b>Human Resources</b><span>555-0123</span><b>Address</b><span>200 Freight Street, Chicago</span></div></div>
<p>For anything that can wait, please use the <a href="{{ P }}/helpdesk">helpdesk</a>.</p>"""


@bp.route("/contact")
def contact():
    return render(CONTACT, title="Contact")


@bp.route("/handbook")
def handbook():
    return render("<h1>Employee handbook</h1><div class=\"msg info\">The handbook has moved to the new HR portal. This page is no longer maintained.</div>", title="Handbook")


@bp.route("/admin")
@bp.route("/admin/")
@bp.route("/backup")
@bp.route("/backup/")
def forbidden_area():
    return render("<h1>Access denied</h1><p>You do not have permission to view this page.</p>", title="Access denied"), 403


# --------------------------------------------------------------------------- data

FIRST = ["Alice", "Brian", "Carla", "Dmitri", "Elena", "Farid", "Grace", "Hector", "Ingrid", "Jamal", "Katya", "Liam", "Maya", "Nikhil", "Olga",
         "Pedro", "Quinn", "Rosa", "Samir", "Tessa", "Umar", "Vera", "Wendell", "Ximena", "Yusuf", "Zara", "Aaron", "Bianca", "Callum", "Daria",
         "Emeka", "Fiona", "Gareth", "Hana", "Ivan", "Jenna", "Kofi", "Lena", "Marco", "Nora"]
LAST = ["Anderson", "Baker", "Castillo", "Dvorak", "Eriksen", "Farouk", "Gallagher", "Hoffman", "Ibarra", "Jensen", "Kowalski", "Lindgren",
        "Mbeki", "Nakamura", "Okafor", "Petrov", "Quintero", "Rahman", "Sullivan", "Tanaka", "Underhill", "Vasquez", "Whitfield", "Xu", "Yilmaz",
        "Zielinski", "Abbott", "Brennan", "Chaudhry", "Delgado", "Ellison", "Fitzgerald", "Gupta", "Hendricks", "Iyer", "Jovanovic", "Kaplan", "Lombardi", "Moreau", "Novak"]
DEPTS_DATA = [("Operations", "Gareth Brennan", 1), ("Finance", "Hana Ellison", 2), ("Human Resources", "Rosa Delgado", 2), ("Information Technology", "Nikhil Iyer", 3),
              ("Sales", "Marco Lombardi", 1), ("Customer Support", "Fiona Abbott", 1), ("Warehouse", "Callum Hoffman", 0), ("Legal", "Vera Kaplan", 3)]
TITLES = {
    "Operations": ["Operations Manager", "Route Planner", "Fleet Coordinator", "Dispatch Lead"],
    "Finance": ["Accountant", "Payroll Specialist", "Financial Analyst", "Accounts Payable Clerk"],
    "Human Resources": ["HR Business Partner", "Recruiter", "Benefits Administrator"],
    "Information Technology": ["Systems Administrator", "Support Engineer", "Network Engineer", "Software Developer"],
    "Sales": ["Account Executive", "Sales Associate", "Regional Sales Manager"],
    "Customer Support": ["Support Agent", "Support Team Lead", "Claims Handler"],
    "Warehouse": ["Warehouse Supervisor", "Forklift Operator", "Inventory Controller", "Picker/Packer"],
    "Legal": ["Contracts Counsel", "Compliance Officer", "Paralegal"],
}
OFFICES = ["Chicago HQ", "Dallas Hub", "Atlanta Depot", "Denver Office", "Remote"]
BIOS = ["Joined from a regional courier and loves optimising routes.", "Enjoys cycling to work and hosting the Friday quiz.",
        "Keeps the team organised and the kettle full.", "Previously worked in retail logistics for eight years.",
        "Runs the monthly knowledge-sharing lunch.", "Fluent in three languages and one spreadsheet dialect.",
        "Volunteers with the community food bank.", "Always happy to help new starters find their feet."]


def init_db():
    rnd = random.Random(2026)
    c = mysql_conn(SLUG, admin=True)
    cur = c.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS=0")
    for t in ("employees", "departments", "accounts", "announcements", "leave_requests", "tickets", "it_secrets", "payroll_archive", "old_hr_logins"):
        cur.execute(f"DROP TABLE IF EXISTS `{t}`")
    cur.execute("SET FOREIGN_KEY_CHECKS=1")
    cur.execute("""CREATE TABLE departments (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(80), head VARCHAR(80), floor INT)""")
    cur.execute("""CREATE TABLE employees (id INT AUTO_INCREMENT PRIMARY KEY, full_name VARCHAR(100), job_title VARCHAR(100), department VARCHAR(80),
        email VARCHAR(120), phone VARCHAR(30), office VARCHAR(60), bio VARCHAR(255), hire_date DATE, salary INT, manager_id INT)""")
    cur.execute("""CREATE TABLE accounts (id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(60), password VARCHAR(64), role VARCHAR(40), employee_id INT)""")
    cur.execute("""CREATE TABLE announcements (id INT AUTO_INCREMENT PRIMARY KEY, headline VARCHAR(160), body TEXT, author VARCHAR(80), posted DATE)""")
    cur.execute("""CREATE TABLE leave_requests (id INT AUTO_INCREMENT PRIMARY KEY, employee_id INT, kind VARCHAR(30), starts DATE, ends DATE, status VARCHAR(20))""")
    cur.execute("""CREATE TABLE tickets (id INT AUTO_INCREMENT PRIMARY KEY, ref VARCHAR(20), requester VARCHAR(250), category VARCHAR(40),
        subject VARCHAR(300), message TEXT, status VARCHAR(20), created_at DATETIME) AUTO_INCREMENT=1001""")
    cur.execute("""CREATE TABLE it_secrets (id INT AUTO_INCREMENT PRIMARY KEY, system_name VARCHAR(80), account VARCHAR(80), secret VARCHAR(120))""")
    cur.execute("""CREATE TABLE payroll_archive (id INT AUTO_INCREMENT PRIMARY KEY, employee_ref VARCHAR(20), period VARCHAR(10), gross INT, iban VARCHAR(40))""")
    cur.execute("""CREATE TABLE old_hr_logins (id INT AUTO_INCREMENT PRIMARY KEY, login VARCHAR(60), passwd VARCHAR(60), disabled_on DATE)""")

    cur.executemany("INSERT INTO departments (name, head, floor) VALUES (%s,%s,%s)", DEPTS_DATA)
    emps = []
    for i in range(40):
        dept = DEPTS_DATA[i % len(DEPTS_DATA)][0]
        name = f"{FIRST[i]} {LAST[i]}"
        emps.append((name, rnd.choice(TITLES[dept]), dept, f"{FIRST[i].lower()}.{LAST[i].lower()}@northwind-logistics.example",
                     "555-01%02d" % rnd.randint(0, 99), rnd.choice(OFFICES), rnd.choice(BIOS),
                     "20%02d-%02d-%02d" % (rnd.randint(14, 26), rnd.randint(1, 12), rnd.randint(1, 28)), rnd.randint(38, 120) * 1000,
                     rnd.randint(1, 8)))
    cur.executemany("INSERT INTO employees (full_name, job_title, department, email, phone, office, bio, hire_date, salary, manager_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", emps)

    import hashlib as h
    md5 = lambda s: h.md5(s.encode()).hexdigest()  # noqa
    cur.executemany("INSERT INTO accounts (username, password, role, employee_id) VALUES (%s,%s,%s,%s)", [
        ("hr.admin", md5("Northw1nd#HR"), "hr_admin", 3), ("rdelgado", md5("Delgado-2024!"), "hr_admin", 3),
        ("niyer", md5("Sysadm1n$Iyer"), "it_admin", 4), ("svc_payroll", md5("Payr0ll-Svc-77"), "service", 2),
        ("fabbott", md5("Support#Lead5"), "manager", 6), ("gbrennan", md5("R0utes&Fleet"), "manager", 1),
    ])
    news = [
        ("Q1 all-hands meeting on Thursday", "Join us in the main atrium at 10:00 for the quarterly review and Q&A with the leadership team.", "Communications", "2026-03-02"),
        ("New parking arrangements at Chicago HQ", "From Monday the east lot is reserved for visitors. Staff permits are valid in the north and south lots.", "Facilities", "2026-02-26"),
        ("Benefits enrolment closes 15 March", "Please review your elections in the benefits portal before the deadline. Contact HR with any questions.", "Human Resources", "2026-02-20"),
        ("Scheduled maintenance this weekend", "The warehouse management system will be offline on Saturday between 22:00 and 02:00.", "IT", "2026-02-18"),
        ("Welcome to our February starters", "Please say hello to the new colleagues who joined across Operations and Customer Support this month.", "Human Resources", "2026-02-10"),
        ("Safety reminder: forklift certification", "Annual recertification sessions are open for booking until the end of the month.", "Warehouse", "2026-02-03"),
        ("Fleet vehicle replacement programme", "Twelve new vehicles will enter service in April. Driver briefings are scheduled for next month.", "Operations", "2026-01-28"),
        ("Holiday calendar published", "The company holiday calendar for the year is now available on the intranet.", "Human Resources", "2026-01-12"),
    ]
    cur.executemany("INSERT INTO announcements (headline, body, author, posted) VALUES (%s,%s,%s,%s)", news)
    kinds = ["annual", "sick", "personal", "training"]
    leaves = []
    for i in range(45):
        m = rnd.randint(3, 8)
        d = rnd.randint(1, 20)
        leaves.append((rnd.randint(1, 40), rnd.choice(kinds), f"2026-{m:02d}-{d:02d}", f"2026-{m:02d}-{d + rnd.randint(1, 7):02d}",
                       rnd.choice(["pending", "approved", "approved", "declined"])))
    cur.executemany("INSERT INTO leave_requests (employee_id, kind, starts, ends, status) VALUES (%s,%s,%s,%s,%s)", leaves)
    subs = ["Cannot connect to VPN", "Monitor flickering", "Request access to shared drive", "Printer on floor 2 jammed", "Replacement badge",
            "Laptop battery drains quickly", "Desk move request", "Software licence renewal", "Email signature template", "Conference room projector"]
    tix = []
    for i in range(18):
        tix.append((f"REQ-{1001 + i}", f"{FIRST[rnd.randint(0, 39)]} {LAST[rnd.randint(0, 39)]}", rnd.choice(CATS), rnd.choice(subs),
                    "Please assist when you can, thanks.", rnd.choice(["open", "in progress", "resolved", "resolved"]),
                    f"2026-02-{rnd.randint(1, 28):02d} {rnd.randint(8, 17):02d}:{rnd.randint(0, 59):02d}:00"))
    cur.executemany("INSERT INTO tickets (ref, requester, category, subject, message, status, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)", tix)
    cur.executemany("INSERT INTO it_secrets (system_name, account, secret) VALUES (%s,%s,%s)", [
        ("Payroll SFTP", "svc_payroll", "pr0llSFTP-k4Xz81"), ("Badge controller", "admin", "Bdg#Ctrl-2291"),
        ("Backup vault", "recovery", "FLAG{staffhub_granite_signal_ledger}"), ("Fleet telemetry", "api", "tlm_9b2e41c7d05a"),
        ("Wi-Fi guest", "guest", "NorthwindGuest!26"),
    ])
    cur.executemany("INSERT INTO payroll_archive (employee_ref, period, gross, iban) VALUES (%s,%s,%s,%s)",
                    [("E%04d" % rnd.randint(1, 999), f"2025-{rnd.randint(1, 12):02d}", rnd.randint(3000, 9000), "GB%02dNWLG%014d" % (rnd.randint(10, 99), rnd.randint(10**12, 10**13))) for _ in range(20)])
    cur.executemany("INSERT INTO old_hr_logins (login, passwd, disabled_on) VALUES (%s,%s,%s)", [
        ("hradmin", "hradmin123", "2022-05-01"), ("payroll", "Payroll2019", "2021-08-19"), ("itroot", "toor", "2020-12-01"), ("bkp_user", "backup!", "2023-01-15"),
    ])
    c.close()
