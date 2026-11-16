"""RideShare - community carpool site (public pages only)."""
import hashlib
import random
import re
import secrets
from datetime import datetime, timedelta

import pymysql
from flask import Blueprint, make_response, redirect, render_template_string, request

from ..common import mysql_conn

META = {
    "slug": "rideshare",
    "title": "RideShare",
    "tagline": "Share a ride, split the cost. Community carpooling.",
    "prefix": "/rides",
}
P = META["prefix"]
bp = Blueprint("rideshare", __name__)
DB = "rideshare"
CITY_RE = re.compile(r"[A-Za-z .-]{0,60}")
SORTS = {"date": "depart_at", "price": "price", "seats": "seats"}
COLS = "id,driver_id,driver_name,origin,destination,depart_at,seats,price"


def hp(pw):
    return hashlib.sha256(("rs$" + pw).encode()).hexdigest()


# --------------------------------------------------------------------------- schema / seed
def init_db():
    rnd = random.Random(2209)
    c = mysql_conn(DB, admin=True)
    cur = c.cursor()
    for t in ("reviews", "bookings", "rides", "reports", "promo_codes", "driver_payouts", "admin_accounts",
              "ops_secrets", "cities", "users", "alerts", "messages"):
        cur.execute(f"DROP TABLE IF EXISTS `{t}`")
    cur.execute("""CREATE TABLE users(
        id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(150) NOT NULL UNIQUE, email VARCHAR(120) NOT NULL,
        password_hash CHAR(64) NOT NULL, full_name VARCHAR(100), home_city VARCHAR(80) DEFAULT '', phone VARCHAR(30) DEFAULT '',
        bio VARCHAR(300) DEFAULT '', rating DECIMAL(2,1) DEFAULT 4.5, joined_at DATETIME)""")
    cur.execute("""CREATE TABLE cities(id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(60), region VARCHAR(60))""")
    cur.execute("""CREATE TABLE rides(
        id INT AUTO_INCREMENT PRIMARY KEY, driver_id INT, driver_name VARCHAR(150), origin VARCHAR(60), destination VARCHAR(60),
        depart_at DATETIME, seats INT, price DECIMAL(6,2), car VARCHAR(80), notes VARCHAR(255), created_at DATETIME)""")
    cur.execute("""CREATE TABLE reviews(
        id INT AUTO_INCREMENT PRIMARY KEY, ride_id INT, author_id INT, rating INT, comment VARCHAR(255), created_at DATETIME)""")
    cur.execute("""CREATE TABLE promo_codes(
        id INT AUTO_INCREMENT PRIMARY KEY, code VARCHAR(30), discount INT, expires DATE, max_uses INT)""")
    cur.execute("""CREATE TABLE driver_payouts(
        id INT AUTO_INCREMENT PRIMARY KEY, driver_id INT, amount DECIMAL(8,2), iban_masked VARCHAR(40), paid_at DATETIME)""")
    cur.execute("""CREATE TABLE admin_accounts(
        id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(60), password_hash VARCHAR(64), role VARCHAR(30), last_login DATETIME)""")
    cur.execute("""CREATE TABLE ops_secrets(
        id INT AUTO_INCREMENT PRIMARY KEY, label VARCHAR(80), secret_value VARCHAR(160), owner VARCHAR(60))""")
    cur.execute("""CREATE TABLE alerts(
        id INT AUTO_INCREMENT PRIMARY KEY, email VARCHAR(120), from_city VARCHAR(255), to_city VARCHAR(255), created_at DATETIME)""")
    cur.execute("""CREATE TABLE messages(
        id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(80), email VARCHAR(120), body VARCHAR(500), created_at DATETIME)""")

    now = datetime(2026, 11, 1, 8, 0, 0)
    cities = ["Springfield", "Riverton", "Lakeside", "Brookfield", "Oakdale", "Fairview", "Hillcrest", "Maplewood",
              "Cedar Falls", "Stonebridge", "Westport", "Northgate", "Eastvale", "Pinecrest", "Harborview", "Kingsford",
              "Ashford", "Millbrook", "Redwood", "Silverlake"]
    regions = ["North", "South", "East", "West", "Central"]
    cur.executemany("INSERT INTO cities(name,region) VALUES (%s,%s)", [(n, rnd.choice(regions)) for n in cities])

    names = [("maya.chen", "Maya Chen"), ("liam.ortiz", "Liam Ortiz"), ("sofia.rossi", "Sofia Rossi"), ("noah.baker", "Noah Baker"),
             ("amira.khan", "Amira Khan"), ("ethan.cole", "Ethan Cole"), ("hannah.berg", "Hannah Berg"), ("omar.haddad", "Omar Haddad"),
             ("chloe.dubois", "Chloe Dubois"), ("jack.murphy", "Jack Murphy"), ("priya.nair", "Priya Nair"), ("lucas.silva", "Lucas Silva"),
             ("emma.wilson", "Emma Wilson"), ("kofi.mensah", "Kofi Mensah"), ("yuki.tanaka", "Yuki Tanaka"), ("ben.schmidt", "Ben Schmidt"),
             ("zara.ali", "Zara Ali"), ("tom.fischer", "Tom Fischer"), ("nina.ivanova", "Nina Ivanova"), ("sam.okafor", "Sam Okafor")]
    for u, n in names:
        cur.execute("INSERT INTO users(username,email,password_hash,full_name,home_city,phone,bio,rating,joined_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (u, f"{u}@mailbox.example", hp(f"{u.split('.')[0]}{rnd.randint(100, 999)}"), n, rnd.choice(cities),
                     f"+1-555-01{rnd.randint(10, 99)}", rnd.choice(["Commuter, music lover.", "Weekend trips mostly.", "Quiet rides please.", "Happy to chat or ride in silence."]),
                     round(rnd.uniform(3.8, 5.0), 1), now - timedelta(days=rnd.randint(30, 900))))
    cars = ["Toyota Corolla", "Honda Civic", "VW Golf", "Ford Focus", "Tesla Model 3", "Hyundai i30", "Skoda Octavia", "Mazda 3"]
    notes = ["No smoking.", "Small bags only.", "Happy to stop for coffee.", "Pets welcome.", "Leaving on time.", "Pick-up near the station.", ""]
    for i in range(44):
        d = rnd.randint(1, 20)
        o, t = rnd.sample(cities, 2)
        cur.execute("INSERT INTO rides(driver_id,driver_name,origin,destination,depart_at,seats,price,car,notes,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (d, names[d - 1][1], o, t, now + timedelta(days=rnd.randint(-8, 50), hours=rnd.randint(0, 12), minutes=rnd.choice([0, 15, 30, 45])),
                     rnd.randint(1, 4), round(rnd.uniform(4, 38), 2), rnd.choice(cars), rnd.choice(notes), now - timedelta(days=rnd.randint(5, 30))))
    # keep the random stream aligned with earlier versions of the seed
    for i in range(70):
        rnd.randint(1, 20), rnd.randint(1, 44), rnd.randint(1, 2), rnd.randint(0, 25)
    revs = ["Great driver, very punctual.", "Smooth ride and good conversation.", "Car was clean and comfortable.",
            "Slightly late but communicated well.", "Would ride again.", "Took a longer route than expected."]
    for i in range(50):
        cur.execute("INSERT INTO reviews(ride_id,author_id,rating,comment,created_at) VALUES (%s,%s,%s,%s,%s)",
                    (rnd.randint(1, 44), rnd.randint(1, 20), rnd.randint(3, 5), rnd.choice(revs), now - timedelta(days=rnd.randint(0, 40))))
    for code, disc in [("WELCOME10", 10), ("SUMMER15", 15), ("COMMUTE5", 5), ("FRIEND20", 20), ("WEEKEND8", 8), ("STUDENT12", 12),
                       ("NIGHTOWL7", 7), ("EARLYBIRD6", 6), ("HOLIDAY25", 25), ("LOYAL18", 18)]:
        cur.execute("INSERT INTO promo_codes(code,discount,expires,max_uses) VALUES (%s,%s,%s,%s)",
                    (code, disc, (now + timedelta(days=rnd.randint(-30, 200))).date(), rnd.randint(50, 500)))
    for i in range(15):
        cur.execute("INSERT INTO driver_payouts(driver_id,amount,iban_masked,paid_at) VALUES (%s,%s,%s,%s)",
                    (rnd.randint(1, 20), round(rnd.uniform(20, 400), 2), f"DE** **** **** {rnd.randint(1000, 9999)}", now - timedelta(days=rnd.randint(1, 120))))
    for u, r in [("ops.admin", "superadmin"), ("support.lead", "support"), ("finance.bot", "finance"), ("moderator1", "moderator")]:
        cur.execute("INSERT INTO admin_accounts(username,password_hash,role,last_login) VALUES (%s,%s,%s,%s)",
                    (u, secrets.token_hex(32), r, now - timedelta(days=rnd.randint(1, 90))))
    for lab, val, own in [("payment gateway key", "pk_live_" + secrets.token_hex(12), "finance.bot"),
                          ("sms provider token", "sms_" + secrets.token_hex(10), "ops.admin"),
                          ("map tiles api key", "mt_" + secrets.token_hex(10), "ops.admin"),
                          ("internal dashboard access", "FLAG{rideshare_velvet_compass_3e90}", "support.lead"),
                          ("backup bucket secret", "bk_" + secrets.token_hex(12), "ops.admin"),
                          ("push notification key", "pn_" + secrets.token_hex(10), "moderator1")]:
        cur.execute("INSERT INTO ops_secrets(label,secret_value,owner) VALUES (%s,%s,%s)", (lab, val, own))
    for i, (em, a, b) in enumerate([("maya.chen@mailbox.example", "Springfield", "Riverton"), ("liam.ortiz@mailbox.example", "Lakeside", "Oakdale"),
                                    ("sofia.rossi@mailbox.example", "Westport", "Hillcrest"), ("noah.baker@mailbox.example", "Kingsford", "Ashford"),
                                    ("amira.khan@mailbox.example", "Redwood", "Silverlake"), ("ethan.cole@mailbox.example", "Eastvale", "Northgate"),
                                    ("priya.nair@mailbox.example", "Millbrook", "Fairview"), ("sam.okafor@mailbox.example", "Pinecrest", "Maplewood")]):
        cur.execute("INSERT INTO alerts(email,from_city,to_city,created_at) VALUES (%s,%s,%s,%s)", (em, a, b, now - timedelta(days=i + 1)))
    c.close()


# --------------------------------------------------------------------------- helpers
def run(sql, params=None, fetch="all"):
    """Parameterised unless params is None (then the SQL string is sent as-is)."""
    c = mysql_conn(DB)
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
        if fetch == "id":
            return cur.lastrowid
        return None
    finally:
        c.close()


LAYOUT = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title or 'RideShare' }} - RideShare</title>
<style>
*{box-sizing:border-box}
body{margin:0;font-family:"Trebuchet MS",Verdana,sans-serif;background:#eef5ef;color:#223028;line-height:1.5}
a{color:#176a45;text-decoration:none}a:hover{text-decoration:underline}
.top{background:#14452f;color:#e3f3e8}
.top .in{max-width:1040px;margin:auto;padding:14px 20px;display:flex;align-items:center;gap:24px;flex-wrap:wrap}
.logo{font-size:25px;font-weight:bold;color:#fff;letter-spacing:.3px}.logo b{color:#ffb347}.logo small{font-size:12px;color:#a8d6bb;font-weight:normal;margin-left:6px}
.top nav a{color:#e3f3e8;margin-right:16px;font-size:15px}
.top form{margin-left:auto;display:flex;gap:6px}
.top input[type=text]{padding:7px 10px;border:1px solid #7fb897;border-radius:4px;background:#f7fcf8;width:120px}
button,.btn{background:#e8890c;color:#fff;border:0;padding:8px 16px;border-radius:4px;cursor:pointer;font-family:inherit;font-size:14px;display:inline-block}
button:hover,.btn:hover{background:#c97506;text-decoration:none}
.wrap{max-width:1040px;margin:26px auto;padding:0 20px}
h1{font-size:28px;margin:0 0 6px;color:#14452f}h2{font-size:21px;border-bottom:2px solid #bcd9c6;padding-bottom:5px;margin-top:32px;color:#14452f}
.hero{background:#d3ebdb;border:1px solid #bcd9c6;padding:28px;border-radius:6px;margin-bottom:10px}
.hero p{margin:4px 0 12px;color:#42594b}
.hero form{display:flex;gap:8px;flex-wrap:wrap}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:16px}
.card{background:#fbfefb;border:1px solid #c8dfd0;border-radius:6px;padding:14px}
.card h3{margin:0 0 4px;font-size:16px}.card .sub{color:#587062;font-size:14px}.card .pr{color:#176a45;font-weight:bold;margin-top:6px}
.chips a{display:inline-block;background:#fbfefb;border:1px solid #bcd9c6;border-radius:20px;padding:4px 14px;margin:0 6px 8px 0;font-size:14px}
table{border-collapse:collapse;width:100%;background:#fbfefb;border:1px solid #c8dfd0}
th{background:#d3ebdb;text-align:left;padding:8px 10px;font-size:14px}td{padding:8px 10px;border-top:1px solid #dcebe0;font-size:15px}
.msg{padding:10px 14px;border-radius:4px;margin:12px 0}.err{background:#fbe3dd;border:1px solid #e2a595;color:#7a2512}
.ok{background:#e0f2d8;border:1px solid #a4cc8f;color:#2c5a1a}.info{background:#fff3cf;border:1px solid #e3cc82}
label{display:block;margin:12px 0 4px;font-size:14px}
input[type=text],input[type=email]{padding:8px 10px;border:1px solid #9cc3ad;border-radius:4px;width:100%;max-width:360px;background:#fcfffc;font-family:inherit}
footer{background:#14452f;color:#a8d6bb;margin-top:50px;padding:22px 20px;font-size:13px;text-align:center}
footer a{color:#d3ebdb;margin:0 8px}
.pager a{margin-right:10px}.muted{color:#587062;font-size:14px}
</style></head><body>
<div class="top"><div class="in">
<a class="logo" href="{{ P }}/">Ride<b>Share</b><small>community carpooling</small></a>
<nav><a href="{{ P }}/">Home</a><a href="{{ P }}/browse">Rides</a><a href="{{ P }}/cities">Cities</a><a href="{{ P }}/drivers">Drivers</a><a href="{{ P }}/subscribe">Ride alerts</a><a href="{{ P }}/about">About</a><a href="{{ P }}/contact">Contact</a></nav>
<form action="{{ P }}/search" method="get"><input type="text" name="from" placeholder="From" value="{{ o or '' }}"><input type="text" name="to" placeholder="To" value="{{ d or '' }}"><button type="submit">Search</button></form>
</div></div>
<div class="wrap">@@BODY@@</div>
<footer><div><a href="{{ P }}/about">About us</a><a href="{{ P }}/contact">Contact</a><a href="{{ P }}/timetable">Printable timetable</a><a href="{{ P }}/terms">Terms</a></div>
<p>&copy; 2026 RideShare Community Cooperative. Share the road, share the cost.</p></footer>
</body></html>"""


def render(body, status=200, **ctx):
    ctx.setdefault("title", None)
    ctx.setdefault("o", "")
    ctx.setdefault("d", "")
    out = render_template_string(LAYOUT.replace("@@BODY@@", body), P=P, **ctx)
    return make_response(out, status)


RIDE_TABLE = """{% macro ride_table(rows) %}<table><tr><th>Route</th><th>Departs</th><th>Seats</th><th>Price</th><th>Driver</th><th></th></tr>
{% for r in rows %}<tr><td>{{ r['origin'] }} &rarr; {{ r['destination'] }}</td><td>{{ r['depart_at'] }}</td><td>{{ r['seats'] }}</td><td>${{ r['price'] }}</td>
<td><a href="{{ P }}/driver?name={{ r['driver_name']|urlencode }}">{{ r['driver_name'] }}</a></td><td><a href="{{ P }}/ride?id={{ r['id'] }}">Details</a></td></tr>
{% else %}<tr><td colspan="6">No rides to show.</td></tr>{% endfor %}</table>{% endmacro %}"""


# --------------------------------------------------------------------------- public pages
HOME = RIDE_TABLE + """
<div class="hero"><h1>Going the same way? Share the ride.</h1><p>Find a lift or offer your empty seats and split the fuel with your neighbours.</p>
<form action="{{ P }}/search" method="get"><input type="text" name="from" placeholder="Leaving from"><input type="text" name="to" placeholder="Going to"><button type="submit">Find rides</button></form></div>
<h2>Popular cities</h2>
<div class="chips">{% for c in cities %}<a href="{{ P }}/city?name={{ c['name']|urlencode }}">{{ c['name'] }}</a>{% endfor %}</div>
<h2>Newly posted rides</h2>
{{ ride_table(rows) }}
<h2>Never miss a ride</h2>
<p>Tell us where you travel from and we will keep you posted. <a href="{{ P }}/subscribe">Set up ride alerts</a>.</p>
"""


@bp.route("/")
def home():
    rows = run("SELECT " + COLS + " FROM rides ORDER BY id DESC LIMIT 8", ())
    cities = run("SELECT name FROM cities ORDER BY name LIMIT 12", ())
    return render(HOME, rows=rows, cities=cities)


BROWSE = RIDE_TABLE + """<h1>All rides</h1>
<p class="muted">Sort by: {% for k in ['date','price','seats'] %}{% if k == sort %}<b>{{ k }}</b>{% else %}<a href="{{ P }}/browse?sort={{ k }}">{{ k }}</a>{% endif %} {% endfor %}</p>
{{ ride_table(rows) }}
{% if pages > 1 %}<p class="pager">{% for n in range(1, pages+1) %}{% if n == page %}<b>{{ n }}</b> {% else %}<a href="{{ P }}/browse?page={{ n }}&sort={{ sort }}">{{ n }}</a>{% endif %}{% endfor %}</p>{% endif %}"""


@bp.route("/browse")
def browse():
    sort = request.args.get("sort", "date")
    if sort not in SORTS:
        sort = "date"
    try:
        page = max(1, min(int(request.args.get("page", "1")), 500))
    except ValueError:
        page = 1
    total = run("SELECT COUNT(*) AS n FROM rides", (), "one")["n"]
    rows = run("SELECT " + COLS + " FROM rides ORDER BY " + SORTS[sort] + " LIMIT 12 OFFSET %s", ((page - 1) * 12,))
    return render(BROWSE, title="Rides", rows=rows, sort=sort, page=page, pages=(total + 11) // 12)


SEARCH = RIDE_TABLE + """<h1>Find a ride</h1>
{% if error %}<div class="msg err">{{ error }}</div>{% endif %}
{% if rows is not none %}<p class="muted">Rides from &ldquo;{{ o or 'anywhere' }}&rdquo; to &ldquo;{{ d or 'anywhere' }}&rdquo;</p>{{ ride_table(rows) }}{% endif %}"""


@bp.route("/search")
def search():
    o, d = request.args.get("from", "").strip(), request.args.get("to", "").strip()
    if not CITY_RE.fullmatch(o) or not CITY_RE.fullmatch(d):
        return render(SEARCH, title="Search", rows=None, error="Please enter a valid city name.", o="", d="")
    rows = run("SELECT " + COLS + " FROM rides WHERE origin LIKE %s AND destination LIKE %s ORDER BY depart_at LIMIT 40", (o + "%", d + "%"))
    return render(SEARCH, title="Search", rows=rows, error=None, o=o, d=d)


RIDE = """{% if r %}
<h1>{{ r['origin'] }} &rarr; {{ r['destination'] }}</h1>
<p class="muted">Departs {{ r['depart_at'] }} &middot; {{ r['seats'] }} seat(s) &middot; ${{ r['price'] }} per seat</p>
<div class="card"><p><b>Driver:</b> <a href="{{ P }}/driver?name={{ r['driver_name']|urlencode }}">{{ r['driver_name'] }}</a> (rating {{ r['rating'] }})<br>
<b>Car:</b> {{ r['car'] }}</p>{% if r['notes'] %}<p class="muted">{{ r['notes'] }}</p>{% endif %}
<p class="muted">To join this ride, message the driver through our <a href="{{ P }}/contact">contact page</a>.</p></div>
<h2>Reviews</h2>
{% for v in revs %}<div class="card" style="margin-bottom:10px"><b>{{ v['username'] }}</b> &middot; {{ v['rating'] }}/5<br>{{ v['comment'] }}</div>
{% else %}<p class="muted">No reviews yet.</p>{% endfor %}
{% else %}<div class="msg info">That ride could not be found.</div>{% endif %}"""


@bp.route("/ride")
def ride():
    raw = request.args.get("id", "")
    r, revs = None, []
    if raw.isdigit() and len(raw) < 9:
        r = run("SELECT r.*, u.rating FROM rides r JOIN users u ON u.id = r.driver_id WHERE r.id = %s", (int(raw),), "one")
        if r:
            revs = run("SELECT v.rating, v.comment, u.username FROM reviews v JOIN users u ON u.id = v.author_id WHERE v.ride_id = %s ORDER BY v.id DESC", (r["id"],))
    return render(RIDE, title="Ride", r=r, revs=revs)


CITIES = """<h1>Cities</h1><p class="muted">Pick a city to see rides leaving from or arriving there.</p>
<table><tr><th>City</th><th>Region</th></tr>{% for c in rows %}<tr><td><a href="{{ P }}/city?name={{ c['name']|urlencode }}">{{ c['name'] }}</a></td><td>{{ c['region'] }}</td></tr>{% endfor %}</table>"""


@bp.route("/cities")
def cities():
    return render(CITIES, title="Cities", rows=run("SELECT name, region FROM cities ORDER BY name", ()))


CITY = RIDE_TABLE + """{% if city %}<h1>{{ city['name'] }}</h1><p class="muted">{{ city['region'] }} region</p>
<h2>Rides leaving from {{ city['name'] }}</h2>{{ ride_table(rows) }}
{% else %}<div class="msg info">We do not have a city by that name.</div>{% endif %}"""


@bp.route("/city")
def city():
    name = request.args.get("name", "").strip()
    c, rows = None, []
    if CITY_RE.fullmatch(name) and name:
        c = run("SELECT name, region FROM cities WHERE name = %s", (name,), "one")
        if c:
            rows = run("SELECT " + COLS + " FROM rides WHERE origin = %s OR destination = %s ORDER BY depart_at LIMIT 30", (name, name))
    return render(CITY, title="City", city=c, rows=rows)


DRIVERS = """<h1>Our drivers</h1><p class="muted">Every driver is a neighbour. Pick a name to see their profile and rides.</p>
<div class="grid">{% for u in rows %}<div class="card"><h3><a href="{{ P }}/driver?name={{ u['full_name']|urlencode }}">{{ u['full_name'] }}</a></h3>
<div class="sub">{{ u['home_city'] }} &middot; rating {{ u['rating'] }}</div></div>{% endfor %}</div>"""


@bp.route("/drivers")
def drivers():
    return render(DRIVERS, title="Drivers", rows=run("SELECT full_name, home_city, rating FROM users ORDER BY full_name", ()))


DRIVER = RIDE_TABLE + """{% if d %}<h1>{{ d['full_name'] }}</h1>
<div class="card"><p>Based in {{ d['home_city'] or 'n/a' }} &middot; rating {{ d['rating'] }}<br><span class="muted">Member since {{ d['joined_at'] }}</span></p><p>{{ d['bio'] }}</p></div>
<h2>Rides offered</h2>{{ ride_table(rows) }}
{% else %}<div class="msg info">No driver found with that name.</div>{% endif %}"""


@bp.route("/driver")
def driver():
    name = request.args.get("name", "").strip()
    d, rows = None, []
    if name and len(name) <= 100:
        d = run("SELECT id, full_name, home_city, bio, rating, joined_at FROM users WHERE full_name = %s", (name,), "one")
        if d:
            rows = run("SELECT " + COLS + " FROM rides WHERE driver_id = %s ORDER BY depart_at DESC", (d["id"],))
    return render(DRIVER, title="Driver", d=d, rows=rows)


SUBSCRIBE = """<h1>Ride alerts</h1>
<p>Leave your route and we will keep you posted about new rides on it.</p>
{% if done %}<div class="msg ok">You are on the list. Your alert number is {{ done }}.</div>{% endif %}
{% if error %}<div class="msg err">{{ error }}</div>{% endif %}
<form method="post" action="{{ P }}/subscribe"><label>Email address</label><input type="email" name="email" required>
<label>Leaving from</label><input type="text" name="from_city" required><label>Going to</label><input type="text" name="to_city"><br><br><button type="submit">Create alert</button></form>"""


@bp.route("/subscribe", methods=["GET", "POST"])
def subscribe():
    done = error = None
    if request.method == "POST":
        em = (request.form.get("email") or "").strip()
        a = (request.form.get("from_city") or "").strip()
        b = (request.form.get("to_city") or "").strip()
        if not re.fullmatch(r"[^@\s]{1,60}@[^@\s]{3,60}", em) or not a or len(a) > 200 or len(b) > 200:
            error = "Please check your details and try again."
        else:
            done = run("INSERT INTO alerts(email,from_city,to_city,created_at) VALUES (%s,%s,%s,%s)", (em, a, b, datetime.utcnow()), "id")
    return render(SUBSCRIBE, title="Ride alerts", done=done, error=error)


ABOUT = """<h1>About RideShare</h1>
<p>RideShare is a not-for-profit cooperative that helps neighbours travel together. Drivers post spare seats, passengers chip in for fuel, and everybody saves a little money and a lot of traffic.</p>
<p>Our drivers are community members who have been part of the cooperative for months or years. Browse the <a href="{{ P }}/drivers">driver list</a> to see who is on the road near you.</p>"""


@bp.route("/about")
def about():
    return render(ABOUT, title="About")


CONTACT = """<h1>Contact</h1>
{% if sent %}<div class="msg ok">Thanks, your message has been received. We aim to reply within two working days.</div>{% endif %}
<form method="post" action="{{ P }}/contact"><label>Your name</label><input type="text" name="name" required>
<label>Email</label><input type="email" name="email" required>
<label>Message</label><input type="text" name="message" required><br><br><button type="submit">Send</button></form>"""


@bp.route("/contact", methods=["GET", "POST"])
def contact():
    sent = False
    if request.method == "POST":
        run("INSERT INTO messages(name,email,body,created_at) VALUES (%s,%s,%s,%s)",
            ((request.form.get("name") or "")[:80], (request.form.get("email") or "")[:120], (request.form.get("message") or "")[:500], datetime.utcnow()), "id")
        sent = True
    return render(CONTACT, title="Contact", sent=sent)


@bp.route("/terms")
def terms():
    return render("<h1>Terms of use</h1><p>RideShare connects members; it does not operate vehicles. Please travel responsibly, agree costs in advance and respect your fellow members.</p>", title="Terms")


@bp.route("/timetable")
def timetable():
    return render("<h1>Printable timetable</h1><p>Our weekly timetable is being redesigned. Please use the <a href=\"" + P + "/browse\">ride list</a> in the meantime.</p>", title="Timetable")


@bp.route("/old")
def old():
    return render("<h1>This page has moved</h1><p>Please start again from the <a href=\"" + P + "/\">home page</a>.</p>", title="Moved")


@bp.route("/admin")
@bp.route("/admin/<path:p>")
@bp.route("/backup")
@bp.route("/backup/<path:p>")
def forbidden(p=None):
    return make_response("<h1>403 Forbidden</h1>", 403)


# --------------------------------------------------------------------------- unlisted pages (not linked anywhere)
IDLE = "<h1>Nothing to show</h1><p class=\"muted\">There is nothing to display here right now.</p>"
MISSING = "<h1>No match</h1><p class=\"muted\">We could not find anything for that request.</p>"


DIGEST = """<h1>Route alert</h1>
<p class="muted">Alert for {{ a['email'] }}: leaving from &ldquo;{{ a['from_city'] }}&rdquo;{% if a['to_city'] %} to &ldquo;{{ a['to_city'] }}&rdquo;{% endif %}</p>
{% if error %}<div class="msg err">This listing could not be prepared right now.</div>{% else %}
<table><tr><th>#</th><th>From</th><th>To</th><th>Departs</th><th>Seats</th><th>Price</th></tr>
{% for r in rows %}<tr><td>{{ r['c1'] }}</td><td>{{ r['c2'] }}</td><td>{{ r['c3'] }}</td><td>{{ r['c4'] }}</td><td>{{ r['c5'] }}</td><td>{{ r['c6'] }}</td></tr>
{% else %}<tr><td colspan="6">No upcoming rides on this route.</td></tr>{% endfor %}</table>{% endif %}"""


@bp.route("/digest")
def digest():
    raw = request.args.get("ref")
    if raw is None:
        return render(IDLE, title="Alert")
    a = None
    if raw.isdigit() and len(raw) < 9:
        a = run("SELECT id, email, from_city, to_city FROM alerts WHERE id = %s", (int(raw),), "one")
    if not a:
        return render(MISSING, title="Alert")
    # the saved route is turned into a listing query
    sql = ("SELECT id AS c1, origin AS c2, destination AS c3, depart_at AS c4, seats AS c5, price AS c6 FROM rides "
           "WHERE origin = '" + a["from_city"] + "' LIMIT 10")
    rows, error = [], False
    try:
        rows = run(sql)
    except pymysql.MySQLError:
        error = True
    return render(DIGEST, title="Alert", a=a, rows=rows, error=error)


REVIEWS = """<h1>Ride reviews</h1>{% if r %}<p class="muted">{{ r['origin'] }} &rarr; {{ r['destination'] }}</p>
{% for v in revs %}<div class="card" style="margin-bottom:10px"><b>{{ v['username'] }}</b> &middot; {{ v['rating'] }}/5<br>{{ v['comment'] }}</div>{% else %}<p class="muted">No reviews yet.</p>{% endfor %}{% endif %}"""


@bp.route("/reviews")
def reviews():
    raw = request.args.get("id")
    if raw is None:
        return render(IDLE, title="Reviews")
    r = None
    if raw.isdigit() and len(raw) < 9:
        r = run("SELECT id, origin, destination FROM rides WHERE id = %s", (int(raw),), "one")
    if not r:
        return render(MISSING, title="Reviews")
    revs = run("SELECT v.rating, v.comment, u.username FROM reviews v JOIN users u ON u.id = v.author_id WHERE v.ride_id = %s", (r["id"],))
    return render(REVIEWS, title="Reviews", r=r, revs=revs)


STATS = """<h1>City figures</h1>{% if c %}<div class="card"><b>{{ c['name'] }}</b><br>{{ out }} ride(s) leaving, {{ inc }} ride(s) arriving, region {{ c['region'] }}.</div>{% endif %}"""


@bp.route("/stats")
def stats():
    name = request.args.get("city")
    if name is None:
        return render(IDLE, title="Figures")
    c = None
    if name and CITY_RE.fullmatch(name):
        c = run("SELECT name, region FROM cities WHERE name = %s", (name,), "one")
    if not c:
        return render(MISSING, title="Figures")
    out = run("SELECT COUNT(*) AS n FROM rides WHERE origin = %s", (name,), "one")["n"]
    inc = run("SELECT COUNT(*) AS n FROM rides WHERE destination = %s", (name,), "one")["n"]
    return render(STATS, title="Figures", c=c, out=out, inc=inc)
