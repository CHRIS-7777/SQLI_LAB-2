import hashlib
import random
import re
import urllib.parse
from datetime import date, timedelta

from flask import Blueprint, jsonify, render_template_string, request

from ..common import mssql_conn

META = {
    "slug": "securebank",
    "title": "SecureBank",
    "tagline": "Personal and business banking, rates and branch locator.",
    "prefix": "/bank",
}
bp = Blueprint("securebank", __name__)
DB = "securebank"


def db():
    return mssql_conn(DB)


def hash_pw(p):
    return hashlib.sha256(("sb$" + p).encode()).hexdigest()


# --------------------------------------------------------------------------- WAF (api only)
_WAF = re.compile(r"union|select|--|/\*|;|exec|xp_|sp_|insert|update|delete|drop|waitfor|declare", re.I)


@bp.before_request
def waf():
    if not request.path.startswith("/bank/api/"):
        return None
    blob = request.get_data(as_text=True) + " " + urllib.parse.unquote_plus(request.query_string.decode("latin-1"))
    if _WAF.search(blob):
        return jsonify(error="Request blocked by security policy"), 403
    return None


# --------------------------------------------------------------------------- layout
BASE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }} | SecureBank</title><style>
:root{--navy:#0b2545;--teal:#13a89e;--bg:#f2f5f9;--ink:#1c2733}
*{box-sizing:border-box}body{margin:0;font-family:Segoe UI,system-ui,sans-serif;background:var(--bg);color:var(--ink)}
header{background:var(--navy);color:#fff;padding:0 28px;display:flex;align-items:center;height:60px;gap:30px}
header a.logo{font-size:21px;font-weight:700;color:#fff;text-decoration:none}header a.logo i{color:var(--teal);font-style:normal}
nav a{color:#c9d6ea;text-decoration:none;margin-right:20px;font-size:14px}nav a:hover{color:#fff}
.hero{background:linear-gradient(120deg,#0b2545,#134074);color:#fff;padding:46px 28px}.hero h1{margin:0 0 8px;font-size:32px}.hero p{margin:0;color:#c9d6ea}
main{max-width:980px;margin:26px auto;padding:0 20px}
.card{background:#fff;border-radius:10px;box-shadow:0 1px 4px rgba(11,37,69,.12);padding:22px;margin-bottom:20px}
h2{margin-top:0;color:var(--navy)}table{width:100%;border-collapse:collapse;font-size:14px}
th,td{padding:9px 10px;border-bottom:1px solid #e3e9f1;text-align:left}th{color:#51627a}
form.inl{display:flex;gap:10px;flex-wrap:wrap}input,select{padding:9px 10px;border:1px solid #c5d0de;border-radius:6px;font-size:14px}
button{background:var(--teal);color:#fff;border:0;padding:9px 18px;border-radius:6px;cursor:pointer}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}.muted{color:#6c7b90;font-size:13px}
footer{text-align:center;color:#7a8799;font-size:12px;padding:30px}a{color:#0b6e99}
</style></head><body>
<header><a class="logo" href="/bank/">Secure<i>Bank</i></a><nav><a href="/bank/">Home</a><a href="/bank/rates">Rates</a><a href="/bank/branches">Branches</a><a href="/bank/atm">ATM finder</a><a href="/bank/exchange">Currency</a><a href="/bank/about">About</a></nav></header>
{% if hero %}<div class="hero"><h1>{{ hero[0] }}</h1><p>{{ hero[1] }}</p></div>{% endif %}
<main>{{ body|safe }}</main><footer>&copy; SecureBank N.A. &middot; Member FDIC</footer></body></html>"""


def page(title, body, hero=None, status=200):
    return render_template_string(BASE, title=title, body=body, hero=hero), status


def esc(s):
    return render_template_string("{{ s }}", s="" if s is None else s)


# --------------------------------------------------------------------------- public pages
@bp.route("/")
def home():
    c = db()
    try:
        cur = c.cursor()
        cur.execute("SELECT TOP 4 type, term, apr FROM rates ORDER BY id")
        rates = cur.fetchall()
    finally:
        c.close()
    rows = "".join("<tr><td>%s</td><td>%s</td><td>%s%%</td></tr>" % (esc(r["type"]), esc(r["term"]), esc(r["apr"])) for r in rates)
    body = ('<div class="grid"><div class="card"><h2>Featured rates</h2><table><tr><th>Product</th><th>Term</th><th>APR</th></tr>' + rows +
            '</table><p><a href="/bank/rates">All rates &rarr;</a></p></div>'
            '<div class="card"><h2>Find us</h2><p>Over 40 branches and 900 ATMs nationwide.</p><p><a href="/bank/branches">Branch directory</a><br><a href="/bank/atm">ATM finder</a></p></div>'
            '<div class="card"><h2>Travelling?</h2><p>Check today\'s indicative exchange rates.</p><p><a href="/bank/exchange">Currency converter</a></p></div></div>')
    return page("Home", body, hero=("Banking that stays out of your way", "Savings, loans and cards for everyone."))


@bp.route("/rates")
def rates():
    t = request.args.get("type", "")
    c = db()
    try:
        cur = c.cursor()
        if t:
            cur.execute("SELECT type, term, apr FROM rates WHERE type=%s ORDER BY id", (t,))
        else:
            cur.execute("SELECT type, term, apr FROM rates ORDER BY id")
        rows = cur.fetchall()
    finally:
        c.close()
    opts = "".join('<option>%s</option>' % esc(x) for x in ("savings", "mortgage", "auto", "personal", "business"))
    body = ('<div class="card"><h2>Rates</h2><form class="inl" method="get"><select name="type"><option value="">All products</option>' + opts +
            '</select><button>Filter</button></form></div><div class="card"><table><tr><th>Product</th><th>Term</th><th>APR</th></tr>' +
            "".join("<tr><td>%s</td><td>%s</td><td>%s%%</td></tr>" % (esc(r["type"]), esc(r["term"]), esc(r["apr"])) for r in rows) +
            ("" if rows else "<tr><td colspan=3>No rates found.</td></tr>") + "</table></div>")
    return page("Rates", body)


@bp.route("/branches")
def branches():
    city = request.args.get("city", "").strip()
    c = db()
    try:
        cur = c.cursor()
        cur.execute("SELECT id, name, city, phone FROM branches WHERE city LIKE %s ORDER BY name", ("%" + city + "%",))
        rows = cur.fetchall()
    finally:
        c.close()
    body = ('<div class="card"><h2>Branch directory</h2><form class="inl" method="get"><input name="city" placeholder="City" value="' + esc(city) +
            '"><button>Search</button></form></div><div class="card"><table><tr><th>Branch</th><th>City</th><th>Phone</th></tr>' +
            "".join('<tr><td><a href="/bank/branch?id=%s">%s</a></td><td>%s</td><td>%s</td></tr>' % (r["id"], esc(r["name"]), esc(r["city"]), esc(r["phone"])) for r in rows) +
            ("" if rows else "<tr><td colspan=3>No branches found.</td></tr>") + "</table></div>")
    return page("Branches", body)


@bp.route("/branch")
def branch():
    try:
        bid = int(request.args.get("id", ""))
    except ValueError:
        return page("Branch", '<div class="card"><h2>Branch not found</h2></div>', status=404)
    c = db()
    try:
        cur = c.cursor()
        cur.execute("SELECT name, city, address, phone, hours FROM branches WHERE id=%s", (bid,))
        r = cur.fetchone()
    finally:
        c.close()
    if not r:
        return page("Branch", '<div class="card"><h2>Branch not found</h2></div>', status=404)
    body = '<div class="card"><h2>%s</h2><p>%s, %s</p><p>Phone: %s<br>Hours: %s</p></div>' % tuple(esc(r[k]) for k in ("name", "address", "city", "phone", "hours"))
    return page(r["name"], body)


@bp.route("/atm")
def atm():
    z = request.args.get("zip", "")
    rows, msg = [], ""
    if z:
        if "'" in z or not re.fullmatch(r"\d{5}", z):
            return page("ATM finder", '<div class="card"><h2>ATM finder</h2><p>Service unavailable. Please try again later.</p></div>', status=500)
        c = db()
        try:
            cur = c.cursor()
            cur.execute("SELECT location, status FROM atms WHERE zip=%s", (z,))
            rows = cur.fetchall()
        finally:
            c.close()
        msg = "" if rows else "<p>No ATMs found in that area.</p>"
    body = ('<div class="card"><h2>ATM finder</h2><form class="inl" method="get"><input name="zip" placeholder="ZIP code" value="' + esc(z) +
            '"><button>Find</button></form>' + msg + '</div>' +
            ('<div class="card"><table><tr><th>Location</th><th>Status</th></tr>' +
             "".join("<tr><td>%s</td><td>%s</td></tr>" % (esc(r["location"]), esc(r["status"])) for r in rows) + "</table></div>" if rows else ""))
    return page("ATM finder", body)


@bp.route("/exchange")
def exchange():
    frm, to, amt = request.args.get("from", "USD"), request.args.get("to", "EUR"), request.args.get("amount", "100")
    cur_ok = ("USD", "EUR", "GBP", "JPY", "CAD", "AUD")
    out = ""
    if frm in cur_ok and to in cur_ok:
        try:
            a = float(amt)
        except ValueError:
            a = 0.0
        c = db()
        try:
            cur = c.cursor()
            cur.execute("SELECT rate FROM fx_rates WHERE base=%s AND quote=%s", (frm, to))
            r = cur.fetchone()
        finally:
            c.close()
        if r:
            out = "<p><b>%.2f %s = %.2f %s</b></p>" % (a, esc(frm), a * float(r["rate"]), esc(to))
    elif request.args.get("from") or request.args.get("to"):
        out = "<p>Unsupported currency.</p>"
    o = lambda sel: "".join('<option%s>%s</option>' % (" selected" if x == sel else "", x) for x in cur_ok)
    body = ('<div class="card"><h2>Currency converter</h2><form class="inl" method="get"><input name="amount" value="' + esc(amt) +
            '" size=8><select name="from">' + o(frm) + '</select><select name="to">' + o(to) + '</select><button>Convert</button></form>' + out + '</div>')
    return page("Currency", body)


@bp.route("/about")
def about():
    return page("About", '<div class="card"><h2>About SecureBank</h2><p>Founded in 1987, SecureBank serves over two million customers. '
                         'Online account access is being upgraded; please visit a branch for account services.</p></div>')


@bp.route("/admin")
@bp.route("/admin/")
@bp.route("/backup")
@bp.route("/backup.zip")
@bp.route("/login")
def closed():
    return page("Forbidden", '<div class="card"><h2>403 Forbidden</h2><p>This area is not available.</p></div>', status=403)


# --------------------------------------------------------------------------- hidden API
@bp.route("/api/")
@bp.route("/api")
def api_root():
    return jsonify(service="securebank", status="ok")


@bp.route("/api/status")
def api_status():
    return jsonify(status="ok", uptime=86400)


@bp.route("/api/history")
def api_history():
    """Hidden but safe: last five transactions for an account."""
    try:
        acct = int(request.args.get("account", ""))
    except ValueError:
        return jsonify(error="invalid request"), 400
    c = db()
    try:
        cur = c.cursor()
        cur.execute("SELECT TOP 5 CONVERT(varchar(10), tx_date, 23) AS d, description, amount FROM transactions "
                    "WHERE account_id=%s ORDER BY tx_date DESC", (acct,))
        return jsonify([{"date": r["d"], "description": r["description"], "amount": float(r["amount"])} for r in cur.fetchall()])
    finally:
        c.close()


@bp.route("/api/statement", methods=["POST"])
def statement():
    """Hidden endpoint. Body (JSON): account (required), from, to, type, q."""
    d = request.get_json(silent=True)
    if not isinstance(d, dict) or "account" not in d:
        return jsonify(error="invalid request"), 400
    try:
        acct = int(d.get("account"))
    except (TypeError, ValueError):
        return jsonify(error="invalid account"), 400
    d_from = str(d.get("from", "2000-01-01"))
    d_to = str(d.get("to", "2999-12-31"))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d_from):
        return jsonify(error="invalid date"), 400
    if not re.match(r"\d{4}-\d{2}-\d{2}", d_to):
        return jsonify(error="invalid date"), 400
    kind = str(d.get("type", "all"))
    if kind not in ("all", "credit", "debit"):
        return jsonify(error="invalid type"), 400
    q = str(d.get("q", ""))[:40].replace("'", "''")
    c = db()
    try:
        cur = c.cursor()
        cur.execute("SELECT id FROM accounts WHERE id=%s", (acct,))
        if not cur.fetchone():
            return jsonify(error="account not found"), 404
        sql = ("SELECT CONVERT(varchar(10), t.tx_date, 23) AS tx_date, t.description, t.amount, t.ref "
               "FROM transactions t WHERE t.account_id = " + str(acct))
        if kind != "all":
            sql += " AND t.kind = '" + kind + "'"
        if q:
            sql += " AND t.description LIKE '%" + q + "%'"
        sql += " AND t.tx_date >= '" + d_from + "' AND t.tx_date <= '" + d_to + "' ORDER BY 1"
        try:
            cur.execute(sql)
            rows = cur.fetchall()
        except Exception:
            return jsonify(error="unable to retrieve statement"), 500
        return jsonify([{"date": r["tx_date"], "description": r["description"],
                         "amount": (float(r["amount"]) if r["amount"] is not None else None), "ref": r["ref"]} for r in rows])
    finally:
        c.close()


@bp.route("/robots.txt")
def robots():
    return ("User-agent: *\nDisallow: /bank/admin\nDisallow: /bank/backup\n", 200, {"Content-Type": "text/plain"})


# --------------------------------------------------------------------------- seed
TX = [
    ("Salary - Northwind Logistics", 4200.00), ("Grocery - FreshMart", -86.40), ("Rent - Harbor Estates", -1450.00),
    ("Electric bill - CityPower", -92.15), ("Coffee - Bean There", -4.75), ("Transfer from savings", 500.00),
    ("Online order - Shopsy", -129.99), ("Gym membership", -39.00), ("Refund - Shopsy", 129.99),
    ("Fuel - GasGo", -54.20), ("Restaurant - Luigi's", -63.80), ("Insurance premium", -118.00),
    ("Freelance invoice #2231", 850.00), ("Streaming subscription", -15.99), ("ATM withdrawal", -100.00),
    ("Interest credit", 3.42), ("Pharmacy - HealthPlus", -22.60), ("Phone bill - Teleo", -45.00),
]
FIRST = ["Alice", "Bob", "Carla", "Dmitri", "Elena", "Farid", "Grace", "Hiro", "Ines", "Jamal", "Kira", "Liam",
         "Maya", "Noah", "Olga", "Pedro", "Quinn", "Rosa", "Sven", "Tara", "Uma", "Victor", "Wen", "Xavier", "Yara"]
LAST = ["Nguyen", "Okafor", "Silva", "Petrov", "Haddad", "Brandt", "Kowalski", "Tanaka", "Moreau", "Singh"]
CITIES = ["Boston", "Denver", "Austin", "Seattle", "Chicago", "Miami", "Phoenix", "Portland", "Atlanta", "Dallas"]


def init_db():
    c = mssql_conn(DB, admin=True)
    cur = c.cursor()
    for t in ("transactions", "accounts", "internal_notes", "audit_trail", "staff_users", "customers",
              "rates", "branches", "atms", "fx_rates", "transfers", "cards", "payees"):
        cur.execute("IF OBJECT_ID('dbo.%s','U') IS NOT NULL DROP TABLE dbo.%s" % (t, t))
    cur.execute("CREATE TABLE customers(id INT IDENTITY(1,1) PRIMARY KEY, username VARCHAR(40) UNIQUE, "
                "password_hash VARCHAR(64), full_name NVARCHAR(80), email VARCHAR(80))")
    cur.execute("CREATE TABLE accounts(id INT IDENTITY(1,1) PRIMARY KEY, customer_id INT, number VARCHAR(20), "
                "type VARCHAR(20), balance DECIMAL(12,2), currency CHAR(3))")
    cur.execute("CREATE TABLE transactions(id INT IDENTITY(1,1) PRIMARY KEY, account_id INT, tx_date DATE, "
                "description NVARCHAR(120), amount DECIMAL(12,2), ref VARCHAR(30), kind VARCHAR(10))")
    cur.execute("CREATE TABLE staff_users(id INT IDENTITY(1,1) PRIMARY KEY, username VARCHAR(40), password_hash VARCHAR(64), role VARCHAR(20))")
    cur.execute("CREATE TABLE audit_trail(id INT IDENTITY(1,1) PRIMARY KEY, actor VARCHAR(40), action VARCHAR(80), at DATETIME)")
    cur.execute("CREATE TABLE internal_notes(id INT IDENTITY(1,1) PRIMARY KEY, note_key VARCHAR(40), note_value NVARCHAR(200))")
    cur.execute("CREATE TABLE rates(id INT IDENTITY(1,1) PRIMARY KEY, type VARCHAR(20), term VARCHAR(30), apr DECIMAL(5,2))")
    cur.execute("CREATE TABLE branches(id INT IDENTITY(1,1) PRIMARY KEY, name NVARCHAR(60), city NVARCHAR(40), address NVARCHAR(100), phone VARCHAR(20), hours VARCHAR(40))")
    cur.execute("CREATE TABLE atms(id INT IDENTITY(1,1) PRIMARY KEY, zip CHAR(5), location NVARCHAR(80), status VARCHAR(12))")
    cur.execute("CREATE TABLE fx_rates(id INT IDENTITY(1,1) PRIMARY KEY, base CHAR(3), quote CHAR(3), rate DECIMAL(10,5))")

    rng = random.Random(77)
    for i in range(25):
        user = (FIRST[i] + "." + LAST[i % len(LAST)]).lower()
        pw = rng.choice(["Winter2024!", "Passw0rd#1", "Bank$ecure9", "Summer!2023", "Welcome123"])
        cur.execute("INSERT INTO customers(username,password_hash,full_name,email) OUTPUT INSERTED.id VALUES(%s,%s,%s,%s)",
                    (user, hash_pw(pw), FIRST[i] + " " + LAST[i % len(LAST)], user + "@mail.example"))
        cid = cur.fetchone()["id"]
        for kind in (["checking", "savings"] if i % 2 == 0 else ["checking"]):
            cur.execute("INSERT INTO accounts(customer_id,number,type,balance,currency) OUTPUT INSERTED.id VALUES(%s,%s,%s,%s,'USD')",
                        (cid, "SB%010d" % rng.randint(10**9, 10**10 - 1), kind, round(rng.uniform(300, 48000), 2)))
            aid = cur.fetchone()["id"]
            for _ in range(rng.randint(25, 45)):
                d0 = date(2024, 1, 1) + timedelta(days=rng.randint(0, 360))
                desc, amt = rng.choice(TX)
                cur.execute("INSERT INTO transactions(account_id,tx_date,description,amount,ref,kind) VALUES(%s,%s,%s,%s,%s,%s)",
                            (aid, d0.isoformat(), desc, amt, "TX%07d" % rng.randint(0, 9999999), "credit" if amt > 0 else "debit"))
    for u, r in (("teller01", "teller"), ("auditor", "audit"), ("sysadmin", "admin")):
        cur.execute("INSERT INTO staff_users(username,password_hash,role) VALUES(%s,%s,%s)", (u, hash_pw(u + "#Staff77"), r))
    for a in ("login teller01", "export ledger", "reset limits", "close account 4412"):
        cur.execute("INSERT INTO audit_trail(actor,action,at) VALUES('sysadmin',%s,GETDATE())", (a,))
    for k, v in (("swift_gateway_user", "svc_swift"), ("hsm_pin_hint", "ask security team"),
                 ("decoy_token", "FLAG{wrong_vault_nothing_here}"),
                 ("core_banking_secret", "FLAG{securebank_unicode_escapes_slip_past_the_gate}")):
        cur.execute("INSERT INTO internal_notes(note_key,note_value) VALUES(%s,%s)", (k, v))
    for t, term, apr in (("savings", "Standard", 0.45), ("savings", "12-month CD", 4.10), ("savings", "24-month CD", 4.35),
                         ("mortgage", "15-year fixed", 5.89), ("mortgage", "30-year fixed", 6.42), ("auto", "60 months", 6.99),
                         ("auto", "72 months", 7.49), ("personal", "36 months", 10.90), ("business", "Line of credit", 9.25)):
        cur.execute("INSERT INTO rates(type,term,apr) VALUES(%s,%s,%s)", (t, term, apr))
    for i, city in enumerate(CITIES):
        for j in range(1 + i % 3):
            cur.execute("INSERT INTO branches(name,city,address,phone,hours) VALUES(%s,%s,%s,%s,%s)",
                        ("%s %s" % (city, ["Main", "Plaza", "Heights"][j]), city, "%d %s St" % (100 + i * 37 + j * 11, rng.choice(["Oak", "Maple", "Cedar", "Pine"])),
                         "555-01%02d" % (i * 3 + j), "Mon-Fri 9-5, Sat 9-1"))
    for z in range(10001, 10021):
        cur.execute("INSERT INTO atms(zip,location,status) VALUES(%s,%s,%s)", (str(z), rng.choice(["Mall entrance", "Gas station", "Main lobby", "Airport T1"]), rng.choice(["online", "online", "offline"])))
    for b in ("USD", "EUR", "GBP", "JPY", "CAD", "AUD"):
        for q, rate in (("USD", 1.0), ("EUR", 0.92), ("GBP", 0.79), ("JPY", 151.2), ("CAD", 1.36), ("AUD", 1.52)):
            if b != q:
                cur.execute("INSERT INTO fx_rates(base,quote,rate) VALUES(%s,%s,%s)", (b, q, round(rate / {"USD": 1.0, "EUR": 0.92, "GBP": 0.79, "JPY": 151.2, "CAD": 1.36, "AUD": 1.52}[b], 5)))
    c.close()
