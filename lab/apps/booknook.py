"""BookNook - small online bookshop."""
import base64
import hashlib
import hmac
import json
import random

from flask import Blueprint, make_response, redirect, render_template_string, request

from ..common import sqlite_conn

SLUG = "booknook"
P = "/books"
META = {
    "slug": SLUG,
    "title": "BookNook",
    "tagline": "Independent bookshop - new releases, classics and staff picks.",
    "prefix": P,
}
bp = Blueprint("booknook", __name__)

COOKIE = "bn_staff"
KEY = b"bn-store-cookie-key-71c0"

# --------------------------------------------------------------------------- helpers


def _sign(data):
    raw = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
    mac = hmac.new(KEY, raw.encode(), hashlib.sha256).hexdigest()[:32]
    return raw + "." + mac


def _unsign(val):
    try:
        raw, mac = val.rsplit(".", 1)
        good = hmac.new(KEY, raw.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(mac, good):
            return None
        return json.loads(base64.urlsafe_b64decode(raw.encode()))
    except Exception:  # noqa
        return None


def current_staff():
    v = request.cookies.get(COOKIE)
    return _unsign(v) if v else None


LAYOUT = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title or 'BookNook' }} - BookNook</title>
<style>
*{box-sizing:border-box}
body{margin:0;font-family:Georgia,'Times New Roman',serif;background:#f7f1e6;color:#33271c;line-height:1.5}
a{color:#8a3b12;text-decoration:none}a:hover{text-decoration:underline}
.top{background:#3b2a1d;color:#f3e6cf}
.top .in{max-width:1040px;margin:auto;padding:14px 20px;display:flex;align-items:center;gap:24px;flex-wrap:wrap}
.logo{font-size:26px;font-weight:bold;color:#f3e6cf;letter-spacing:.5px}.logo small{font-size:13px;color:#d2b48c;font-weight:normal;margin-left:6px}
.top nav a{color:#f3e6cf;margin-right:16px;font-size:15px}
.top form{margin-left:auto;display:flex;gap:6px}
.top input[type=text]{padding:7px 10px;border:1px solid #c9a97b;border-radius:3px;background:#fffaf0;min-width:200px}
button,.btn{background:#8a3b12;color:#fff;border:0;padding:8px 16px;border-radius:3px;cursor:pointer;font-family:inherit;font-size:14px}
button:hover{background:#6f2e0d}
.wrap{max-width:1040px;margin:26px auto;padding:0 20px}
h1{font-size:28px;margin:0 0 6px}h2{font-size:21px;border-bottom:2px solid #d9c3a1;padding-bottom:5px;margin-top:32px}
.hero{background:#ead8b8;border:1px solid #d9c3a1;padding:28px;border-radius:4px;margin-bottom:10px}
.hero p{margin:4px 0 0;color:#5a4636}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:16px}
.card{background:#fffaf0;border:1px solid #dcc8a6;border-radius:4px;padding:14px}
.card h3{margin:0 0 4px;font-size:16px}.card .au{color:#6d5a47;font-size:14px}.card .pr{color:#8a3b12;font-weight:bold;margin-top:6px}
.cats a{display:inline-block;background:#fffaf0;border:1px solid #d9c3a1;border-radius:20px;padding:4px 14px;margin:0 6px 8px 0;font-size:14px}
table{border-collapse:collapse;width:100%;background:#fffaf0;border:1px solid #dcc8a6}
th{background:#e7d3b0;text-align:left;padding:8px 10px;font-size:14px}td{padding:8px 10px;border-top:1px solid #eadcc2;font-size:15px}
.msg{padding:10px 14px;border-radius:3px;margin:12px 0}.err{background:#fbe3dd;border:1px solid #e2a595;color:#7a2512}
.ok{background:#e4f0dc;border:1px solid #a9cc94;color:#2f5a1a}.info{background:#fff3cf;border:1px solid #e3cc82}
label{display:block;margin:12px 0 4px;font-size:14px}
input[type=text],input[type=password],input[type=email]{padding:8px 10px;border:1px solid #c9a97b;border-radius:3px;width:100%;max-width:340px;background:#fffdf8;font-family:inherit}
footer{background:#3b2a1d;color:#cdb892;margin-top:50px;padding:22px 20px;font-size:13px;text-align:center}
footer a{color:#e8cf9f;margin:0 8px}
.pager a{margin-right:10px}.muted{color:#7d6a56;font-size:14px}
.stat{display:inline-block;background:#fffaf0;border:1px solid #dcc8a6;padding:12px 20px;margin:0 10px 10px 0;border-radius:4px}.stat b{font-size:22px;display:block}
</style></head><body>
<div class="top"><div class="in">
<a class="logo" href="{{ P }}/">BookNook<small>est. 1994</small></a>
<nav><a href="{{ P }}/">Home</a><a href="{{ P }}/catalogue">Catalogue</a><a href="{{ P }}/about">About</a><a href="{{ P }}/contact">Contact</a></nav>
<form action="{{ P }}/catalogue" method="get"><input type="text" name="q" placeholder="Title or author" value="{{ q or '' }}"><button type="submit">Search</button></form>
</div></div>
<div class="wrap">@@BODY@@</div>
<footer><div><a href="{{ P }}/about">About us</a><a href="{{ P }}/contact">Contact</a><a href="{{ P }}/staff/login">Staff login</a></div>
<p>&copy; 2026 BookNook Ltd. 14 Mill Lane, Harrowgate. Open Mon-Sat 9-6.</p></footer>
</body></html>"""


def render(body, **ctx):
    ctx.setdefault("title", None)
    ctx.setdefault("q", "")
    return render_template_string(LAYOUT.replace("@@BODY@@", body), P=P, **ctx)


def db():
    return sqlite_conn(SLUG)


# --------------------------------------------------------------------------- public pages

HOME = """
<div class="hero"><h1>Welcome to BookNook</h1><p>Thirty years of putting the right book in the right hands. Browse the shelves online and collect in store.</p></div>
<h2>Browse by category</h2>
<div class="cats">{% for c in cats %}<a href="{{ P }}/catalogue?category={{ c|urlencode }}">{{ c }}</a>{% endfor %}</div>
<h2>Staff picks</h2>
<div class="grid">{% for b in picks %}<div class="card"><h3><a href="{{ P }}/book?id={{ b['id'] }}">{{ b['title'] }}</a></h3>
<div class="au">{{ b['author'] }}</div><div class="pr">&pound;{{ '%.2f'|format(b['price']) }}</div></div>{% endfor %}</div>
<h2>Newsletter</h2>
{% if note %}<div class="msg ok">{{ note }}</div>{% endif %}
<form method="post" action="{{ P }}/newsletter"><label>Email address</label><input type="email" name="email" required> <button type="submit">Subscribe</button></form>
"""


@bp.route("/")
def home():
    c = db()
    cats = [r[0] for r in c.execute("SELECT DISTINCT category FROM books ORDER BY category")]
    picks = c.execute("SELECT id,title,author,price FROM books WHERE featured=1 ORDER BY id LIMIT 8").fetchall()
    c.close()
    return render(HOME, cats=cats, picks=picks, note=request.args.get("subscribed") and "Thanks, you are on the list.")


@bp.route("/newsletter", methods=["POST"])
def newsletter():
    email = (request.form.get("email") or "").strip()[:120]
    if "@" in email:
        c = db()
        c.execute("INSERT INTO subscribers (email) VALUES (?)", (email,))
        c.commit()
        c.close()
    return redirect(P + "/?subscribed=1")


CATALOGUE = """
<h1>Catalogue</h1>
{% if q %}<p class="muted">Showing results for &ldquo;{{ q }}&rdquo;</p>{% elif category %}<p class="muted">Category: {{ category }}</p>{% endif %}
{% if error %}<div class="msg err">Search failed: {{ error }}</div>{% endif %}
{% if rows is not none %}
{% if rows %}
<table><tr><th>Title</th><th>Author</th><th>Category</th><th>Price</th></tr>
{% for r in rows %}<tr><td><a href="{{ P }}/book?id={{ r[0] }}">{{ r[1] }}</a></td><td>{{ r[2] }}</td><td>{{ r[3] }}</td><td>{{ r[4] }}</td></tr>{% endfor %}
</table>
{% elif not error %}<div class="msg info">No titles matched your search.</div>{% endif %}
{% endif %}
{% if pages and pages > 1 %}<p class="pager">{% for n in range(1, pages+1) %}{% if n == page %}<b>{{ n }}</b> {% else %}<a href="{{ P }}/catalogue?page={{ n }}&sort={{ sort }}">{{ n }}</a>{% endif %}{% endfor %}</p>{% endif %}
"""

SORTS = {"title": "title", "author": "author", "price": "price", "newest": "published DESC"}


@bp.route("/catalogue")
def catalogue():
    q = request.args.get("q", "")
    category = request.args.get("category", "")
    sort = request.args.get("sort", "title")
    if sort not in SORTS:
        sort = "title"
    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1
    rows, error, pages = None, None, 0
    c = db()
    try:
        if q:
            sql = ("SELECT id, title, author, category, price FROM books "
                   f"WHERE title LIKE '%{q}%' OR author LIKE '%{q}%'")
            rows = c.execute(sql).fetchall()
        elif category:
            rows = c.execute("SELECT id, title, author, category, price FROM books WHERE category = ? ORDER BY " + SORTS[sort],
                             (category,)).fetchall()
        else:
            total = c.execute("SELECT COUNT(*) FROM books").fetchone()[0]
            pages = (total + 11) // 12
            rows = c.execute("SELECT id, title, author, category, price FROM books ORDER BY " + SORTS[sort] + " LIMIT 12 OFFSET ?",
                             ((page - 1) * 12,)).fetchall()
    except Exception as e:  # noqa
        error = str(e)
        rows = None
    c.close()
    return render(CATALOGUE, title="Catalogue", q=q, category=category, rows=rows, error=error,
                  pages=pages, page=page, sort=sort)


BOOK = """
{% if book %}
<h1>{{ book['title'] }}</h1><p class="au">by {{ book['author'] }} &middot; {{ book['category'] }} &middot; published {{ book['published'] }}</p>
<p>{{ book['description'] }}</p>
<p><b>&pound;{{ '%.2f'|format(book['price']) }}</b> &nbsp; <span class="muted">ISBN {{ book['isbn'] }} &middot; {{ 'In stock' if book['stock'] > 0 else 'Out of stock' }}</span></p>
<h2>Reviews</h2>
{% for r in reviews %}<div class="card" style="margin-bottom:10px"><b>{{ r['reviewer'] }}</b> &middot; {{ r['rating'] }}/5<br>{{ r['body'] }}</div>
{% else %}<p class="muted">No reviews yet.</p>{% endfor %}
{% else %}<div class="msg info">That book could not be found.</div>{% endif %}
"""


@bp.route("/book")
def book():
    raw = request.args.get("id", "")
    b, reviews = None, []
    if raw.isdigit() and len(raw) < 9:
        c = db()
        b = c.execute("SELECT * FROM books WHERE id = ?", (int(raw),)).fetchone()
        if b:
            reviews = c.execute("SELECT reviewer, rating, body FROM reviews WHERE book_id = ?", (b["id"],)).fetchall()
        c.close()
    return render(BOOK, title=b["title"] if b else "Book", book=b, reviews=reviews)


ABOUT = """<h1>About BookNook</h1>
<p>BookNook opened in 1994 in a single room above a bakery. Today we stock more than twenty thousand titles across two floors, run weekly reading groups and ship across the country.</p>
<p>Everything on this site mirrors what is on our shelves. Reserve online and collect within two working days.</p>"""


@bp.route("/about")
def about():
    return render(ABOUT, title="About")


CONTACT = """<h1>Contact</h1>
{% if sent %}<div class="msg ok">Thanks, your message has been received. We aim to reply within two working days.</div>{% endif %}
<form method="post"><label>Your name</label><input type="text" name="name" required>
<label>Email</label><input type="email" name="email" required>
<label>Message</label><input type="text" name="message" required><br><br><button type="submit">Send</button></form>"""


@bp.route("/contact", methods=["GET", "POST"])
def contact():
    sent = False
    if request.method == "POST":
        c = db()
        c.execute("INSERT INTO messages (name, email, body) VALUES (?,?,?)",
                  ((request.form.get("name") or "")[:80], (request.form.get("email") or "")[:120],
                   (request.form.get("message") or "")[:500]))
        c.commit()
        c.close()
        sent = True
    return render(CONTACT, title="Contact", sent=sent)


# --------------------------------------------------------------------------- staff area

LOGIN = """<h1>Staff sign in</h1>
<p class="muted">Authorised BookNook staff only.</p>
{% if error %}<div class="msg err">{{ error }}</div>{% endif %}
<form method="post"><label>Username</label><input type="text" name="username" autocomplete="off">
<label>Password</label><input type="password" name="password"><br><br><button type="submit">Sign in</button></form>"""


@bp.route("/staff/login", methods=["GET", "POST"])
def staff_login():
    error = None
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        c = db()
        try:
            sql = f"SELECT id, username, fullname, role FROM staff WHERE username = '{u}' AND password = '{p}'"
            row = c.execute(sql).fetchone()
            if row:
                resp = make_response(redirect(P + "/staff/"))
                resp.set_cookie(COOKIE, _sign({"n": str(row[2]), "r": str(row[3])}), path=P, httponly=True, samesite="Lax")
                c.close()
                return resp
            error = "Invalid username or password."
        except Exception as e:  # noqa
            error = f"Sign in failed: {e}"
        c.close()
    return render(LOGIN, title="Staff sign in", error=error)


@bp.route("/staff/logout")
def staff_logout():
    resp = make_response(redirect(P + "/staff/login"))
    resp.delete_cookie(COOKIE, path=P)
    return resp


DASH = """<h1>Staff dashboard</h1>
<p class="muted">Signed in as {{ me['n'] }} ({{ me['r'] }}) &middot; <a href="{{ P }}/staff/logout">Sign out</a></p>
<div><div class="stat"><b>{{ stats[0] }}</b>titles</div><div class="stat"><b>{{ stats[1] }}</b>open orders</div><div class="stat"><b>{{ stats[2] }}</b>low stock</div></div>
<p><a href="{{ P }}/staff/orders">Orders</a> &middot; <a href="{{ P }}/staff/inventory">Inventory</a> &middot; <a href="{{ P }}/staff/backup">Backups</a></p>
<h2>Recent orders</h2>
<table><tr><th>#</th><th>Customer</th><th>Title</th><th>Qty</th><th>Status</th></tr>
{% for o in orders %}<tr><td>{{ o['id'] }}</td><td>{{ o['name'] }}</td><td>{{ o['title'] }}</td><td>{{ o['qty'] }}</td><td>{{ o['status'] }}</td></tr>{% endfor %}</table>"""

ORDERS = """<h1>Orders</h1><p class="muted"><a href="{{ P }}/staff/">&larr; Dashboard</a></p>
<p>Filter: {% for s in ['all','pending','packed','shipped','collected'] %}<a href="{{ P }}/staff/orders?status={{ s }}">{{ s }}</a> {% endfor %}</p>
<table><tr><th>#</th><th>Customer</th><th>Title</th><th>Qty</th><th>Status</th><th>Placed</th></tr>
{% for o in orders %}<tr><td>{{ o['id'] }}</td><td>{{ o['name'] }}</td><td>{{ o['title'] }}</td><td>{{ o['qty'] }}</td><td>{{ o['status'] }}</td><td>{{ o['placed'] }}</td></tr>
{% else %}<tr><td colspan="6">No orders.</td></tr>{% endfor %}</table>"""

INVENTORY = """<h1>Inventory</h1><p class="muted"><a href="{{ P }}/staff/">&larr; Dashboard</a></p>
<table><tr><th>Title</th><th>Author</th><th>Stock</th><th>Price</th></tr>
{% for b in books %}<tr><td>{{ b['title'] }}</td><td>{{ b['author'] }}</td><td>{{ b['stock'] }}</td><td>{{ b['price'] }}</td></tr>{% endfor %}</table>"""

BACKUP = """<h1>Backups</h1><p class="muted"><a href="{{ P }}/staff/">&larr; Dashboard</a></p>
<table><tr><th>Archive</th><th>Taken</th><th>Size</th><th></th></tr>
{% for f in files %}<tr><td>{{ f[0] }}</td><td>{{ f[1] }}</td><td>{{ f[2] }}</td><td><a href="{{ P }}/staff/backup/download?file={{ f[0]|urlencode }}">Download</a></td></tr>{% endfor %}</table>
<p class="muted">Offsite sync is currently paused. Contact the store manager to restore an archive.</p>"""


def _need_staff():
    me = current_staff()
    if not me:
        return None, redirect(P + "/staff/login")
    return me, None


@bp.route("/staff/")
def staff_home():
    me, bad = _need_staff()
    if bad:
        return bad
    c = db()
    stats = (c.execute("SELECT COUNT(*) FROM books").fetchone()[0],
             c.execute("SELECT COUNT(*) FROM orders WHERE status IN ('pending','packed')").fetchone()[0],
             c.execute("SELECT COUNT(*) FROM books WHERE stock < 5").fetchone()[0])
    orders = c.execute("SELECT o.id, cu.name, b.title, o.qty, o.status FROM orders o JOIN customers cu ON cu.id=o.customer_id "
                       "JOIN books b ON b.id=o.book_id ORDER BY o.id DESC LIMIT 8").fetchall()
    c.close()
    return render(DASH, title="Staff", me=me, stats=stats, orders=orders)


@bp.route("/staff/orders")
def staff_orders():
    me, bad = _need_staff()
    if bad:
        return bad
    status = request.args.get("status", "all")
    c = db()
    base = ("SELECT o.id, cu.name, b.title, o.qty, o.status, o.placed FROM orders o JOIN customers cu ON cu.id=o.customer_id "
            "JOIN books b ON b.id=o.book_id")
    if status != "all":
        rows = c.execute(base + " WHERE o.status = ? ORDER BY o.id DESC", (status,)).fetchall()
    else:
        rows = c.execute(base + " ORDER BY o.id DESC").fetchall()
    c.close()
    return render(ORDERS, title="Orders", orders=rows)


@bp.route("/staff/inventory")
def staff_inventory():
    me, bad = _need_staff()
    if bad:
        return bad
    c = db()
    rows = c.execute("SELECT title, author, stock, price FROM books ORDER BY stock, title").fetchall()
    c.close()
    return render(INVENTORY, title="Inventory", books=rows)


@bp.route("/staff/backup")
def staff_backup():
    me, bad = _need_staff()
    if bad:
        return bad
    files = [("catalogue-2026-03-01.zip", "2026-03-01 02:00", "4.1 MB"), ("catalogue-2026-02-01.zip", "2026-02-01 02:00", "4.0 MB"),
             ("orders-2026-03-01.zip", "2026-03-01 02:05", "1.8 MB"), ("full-2026-01-01.zip", "2026-01-01 02:10", "12.6 MB")]
    return render(BACKUP, title="Backups", files=files)


@bp.route("/staff/backup/download")
def staff_backup_dl():
    me, bad = _need_staff()
    if bad:
        return bad
    return render("<h1>Archive unavailable</h1><p>This archive has been moved to cold storage.</p>", title="Backups"), 404


@bp.route("/admin")
@bp.route("/admin/")
def admin_redirect():
    return redirect(P + "/staff/login")


@bp.route("/backup")
@bp.route("/backup/")
def backup_public():
    return render("<h1>Forbidden</h1><p>You do not have permission to view this page.</p>", title="Forbidden"), 403


# --------------------------------------------------------------------------- data

BOOKS = [
    ("Pride and Prejudice", "Jane Austen", "Fiction", 7.99, 1813), ("Jane Eyre", "Charlotte Bronte", "Fiction", 8.49, 1847),
    ("Great Expectations", "Charles Dickens", "Fiction", 8.99, 1861), ("Moby-Dick", "Herman Melville", "Fiction", 10.99, 1851),
    ("The Picture of Dorian Gray", "Oscar Wilde", "Fiction", 6.99, 1890), ("Middlemarch", "George Eliot", "Fiction", 11.49, 1871),
    ("The Hound of the Baskervilles", "Arthur Conan Doyle", "Mystery", 7.49, 1902), ("The Moonstone", "Wilkie Collins", "Mystery", 8.25, 1868),
    ("The Thirty-Nine Steps", "John Buchan", "Mystery", 6.50, 1915), ("The Big Sleep", "Raymond Chandler", "Mystery", 9.99, 1939),
    ("Rebecca", "Daphne du Maurier", "Mystery", 9.49, 1938), ("The Murder of Roger Ackroyd", "Agatha Christie", "Mystery", 8.75, 1926),
    ("The Time Machine", "H. G. Wells", "Science Fiction", 5.99, 1895), ("The War of the Worlds", "H. G. Wells", "Science Fiction", 6.49, 1898),
    ("Frankenstein", "Mary Shelley", "Science Fiction", 6.99, 1818), ("Twenty Thousand Leagues Under the Sea", "Jules Verne", "Science Fiction", 8.99, 1870),
    ("Brave New World", "Aldous Huxley", "Science Fiction", 9.99, 1932), ("The Left Hand of Darkness", "Ursula K. Le Guin", "Science Fiction", 10.49, 1969),
    ("A Short History of Nearly Everything", "Bill Bryson", "Science", 12.99, 2003), ("The Selfish Gene", "Richard Dawkins", "Science", 11.99, 1976),
    ("Cosmos", "Carl Sagan", "Science", 12.49, 1980), ("The Structure of Scientific Revolutions", "Thomas Kuhn", "Science", 13.99, 1962),
    ("Silent Spring", "Rachel Carson", "Science", 10.99, 1962), ("The Guns of August", "Barbara Tuchman", "History", 13.49, 1962),
    ("SPQR", "Mary Beard", "History", 14.99, 2015), ("A People's History of England", "A. L. Morton", "History", 12.99, 1938),
    ("The Rise and Fall of the Third Reich", "William Shirer", "History", 15.99, 1960), ("Salt: A World History", "Mark Kurlansky", "History", 11.49, 2002),
    ("The Diary of a Young Girl", "Anne Frank", "Biography", 8.99, 1947), ("Long Walk to Freedom", "Nelson Mandela", "Biography", 12.99, 1994),
    ("Educated", "Tara Westover", "Biography", 10.99, 2018), ("I Know Why the Caged Bird Sings", "Maya Angelou", "Biography", 9.49, 1969),
    ("The Joy of Cooking", "Irma Rombauer", "Cookery", 24.99, 1931), ("Salt Fat Acid Heat", "Samin Nosrat", "Cookery", 22.50, 2017),
    ("Mastering the Art of French Cooking", "Julia Child", "Cookery", 27.00, 1961), ("Ottolenghi Simple", "Yotam Ottolenghi", "Cookery", 21.00, 2018),
    ("Alice's Adventures in Wonderland", "Lewis Carroll", "Children", 5.49, 1865), ("The Wind in the Willows", "Kenneth Grahame", "Children", 6.25, 1908),
    ("Treasure Island", "Robert Louis Stevenson", "Children", 6.99, 1883), ("Peter Pan", "J. M. Barrie", "Children", 5.99, 1911),
    ("The Secret Garden", "Frances Hodgson Burnett", "Children", 6.49, 1911), ("Black Beauty", "Anna Sewell", "Children", 5.75, 1877),
]
DESC = {
    "Fiction": "A cornerstone of the English novel, beautifully set and wonderfully readable. Our paperback edition includes an introduction and notes.",
    "Mystery": "A gripping puzzle with an unforgettable atmosphere. Perfect for a long evening and a pot of tea.",
    "Science Fiction": "Imaginative, thought-provoking and still startlingly fresh. A staple of any serious bookshelf.",
    "Science": "Clear, curious and engaging. Written for the interested reader rather than the specialist.",
    "History": "Thoroughly researched and compellingly told. A reliable guide to the period.",
    "Biography": "A powerful personal account, honest and moving from the first page.",
    "Cookery": "Hundreds of tested recipes and practical advice from the kitchen. Hardback with colour plates.",
    "Children": "A timeless story for young readers and read-aloud sessions. Illustrated edition.",
}
FIRST = ["Olivia", "Liam", "Emma", "Noah", "Ava", "Oliver", "Sophia", "Elijah", "Isabella", "James", "Mia", "Henry", "Amelia", "Lucas",
         "Harper", "Ethan", "Evelyn", "Mason", "Ella", "Logan", "Grace", "Jacob", "Chloe", "Daniel", "Lily", "Samuel", "Zoe", "Jack", "Ruby", "Leo", "Freya", "Arthur", "Isla", "Theo", "Hannah"]
LAST = ["Walker", "Hughes", "Patel", "Edwards", "Turner", "Clarke", "Hill", "Bennett", "Morris", "Foster", "Reid", "Grant", "Fisher", "Webb",
        "Hayes", "Marsh", "Cole", "Ward", "Price", "Lowe", "Barker", "Dixon", "Knight", "Rowe", "Shaw", "Banks", "Nash", "Bell", "Stone", "Lane", "Pearce", "Fox", "Gill", "Ellis", "Hart"]
CITIES = ["Harrowgate", "Leeds", "York", "Manchester", "Sheffield", "Bristol", "Bath", "Norwich", "Exeter", "Durham"]
WORDS = ["maple", "river", "copper", "lantern", "harbor", "willow", "amber", "falcon", "meadow", "pebble", "cedar", "ember"]


def init_db():
    rnd = random.Random(1994)
    c = db()
    for t in ("books", "customers", "orders", "reviews", "staff", "legacy_staff", "coupons", "partner_keys", "subscribers", "messages"):
        c.execute(f"DROP TABLE IF EXISTS {t}")
    c.executescript("""
    CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, author TEXT, category TEXT, price REAL, isbn TEXT,
                        description TEXT, stock INTEGER, published INTEGER, featured INTEGER DEFAULT 0);
    CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, email TEXT, password TEXT, city TEXT, joined TEXT);
    CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, book_id INTEGER, qty INTEGER, status TEXT, placed TEXT);
    CREATE TABLE reviews (id INTEGER PRIMARY KEY, book_id INTEGER, reviewer TEXT, rating INTEGER, body TEXT);
    CREATE TABLE staff (id INTEGER PRIMARY KEY, username TEXT, password TEXT, fullname TEXT, role TEXT);
    CREATE TABLE legacy_staff (id INTEGER PRIMARY KEY, login TEXT, passwd TEXT, left_on TEXT);
    CREATE TABLE coupons (id INTEGER PRIMARY KEY, code TEXT, discount INTEGER, expires TEXT);
    CREATE TABLE partner_keys (id INTEGER PRIMARY KEY, partner TEXT, api_key TEXT, note TEXT);
    CREATE TABLE subscribers (id INTEGER PRIMARY KEY, email TEXT);
    CREATE TABLE messages (id INTEGER PRIMARY KEY, name TEXT, email TEXT, body TEXT);
    """)
    for i, (t, a, cat, pr, yr) in enumerate(BOOKS, 1):
        c.execute("INSERT INTO books VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (i, t, a, cat, pr, "978-0-%03d-%05d-%d" % (rnd.randint(100, 999), rnd.randint(10000, 99999), rnd.randint(0, 9)),
                   DESC[cat], rnd.randint(0, 40), yr, 1 if i % 5 == 1 else 0))
    for i in range(1, 36):
        n = f"{FIRST[i - 1]} {LAST[i - 1]}"
        c.execute("INSERT INTO customers VALUES (?,?,?,?,?,?)",
                  (i, n, f"{FIRST[i - 1].lower()}.{LAST[i - 1].lower()}@example.com",
                   f"{rnd.choice(WORDS).capitalize()}{rnd.randint(10, 99)}!", rnd.choice(CITIES),
                   "2025-%02d-%02d" % (rnd.randint(1, 12), rnd.randint(1, 28))))
    for i in range(1, 51):
        c.execute("INSERT INTO orders VALUES (?,?,?,?,?,?)",
                  (i, rnd.randint(1, 35), rnd.randint(1, len(BOOKS)), rnd.randint(1, 3),
                   rnd.choice(["pending", "packed", "shipped", "collected", "collected", "shipped"]),
                   "2026-%02d-%02d" % (rnd.randint(1, 3), rnd.randint(1, 28))))
    bodies = ["Lovely edition, arrived quickly.", "A classic for a reason.", "Not what I expected but I enjoyed it.", "Beautiful cover and good paper.",
              "Bought as a gift and it was a hit.", "Slow start, strong finish.", "Re-read this every winter.", "Great value for the price."]
    for i in range(1, 61):
        c.execute("INSERT INTO reviews VALUES (?,?,?,?,?)", (i, rnd.randint(1, len(BOOKS)), FIRST[rnd.randint(0, 34)] + " " + LAST[rnd.randint(0, 34)][0] + ".",
                                                             rnd.randint(3, 5), rnd.choice(bodies)))
    c.executemany("INSERT INTO staff VALUES (?,?,?,?,?)", [
        (1, "admin", "Bk-Adm1n#2026", "Margaret Ellison", "Store Manager"),
        (2, "jpatel", "Pa7el-Stock22", "Jay Patel", "Inventory Lead"),
        (3, "cwhite", "Ch1ldren$Corner", "Claire White", "Bookseller"),
        (4, "tgraham", "Tom-Gr4ham!", "Tom Graham", "Bookseller"),
    ])
    c.executemany("INSERT INTO legacy_staff VALUES (?,?,?,?)", [
        (1, "hbarlow", "b00ksRus", "2019-06-30"), (2, "sdavies", "welcome1", "2021-02-14"), (3, "admin", "changeme", "2018-11-02"),
        (4, "pnorris", "Norris#2020", "2022-09-01"),
    ])
    c.executemany("INSERT INTO coupons VALUES (?,?,?,?)", [
        (1, "SPRING10", 10, "2026-04-30"), (2, "READMORE15", 15, "2025-12-31"), (3, "WELCOME5", 5, "2026-12-31"), (4, "BOOKCLUB20", 20, "2026-06-30"),
    ])
    c.executemany("INSERT INTO partner_keys VALUES (?,?,?,?)", [
        (1, "Harrowgate Distribution", "hd_live_8f3a1c9d27e4b605", "Wholesale ordering"),
        (2, "Pagewise Metadata", "pw_live_52b7e0a4c1d93f68", "ISBN lookups"),
        (3, "CourierHub", "ch_live_a90d4e7b3c1f5286", "Shipping labels"),
        (4, "Internal archive", "FLAG{booknook_paper_lantern_ledger}", "Master recovery token - do not share"),
        (5, "Cardstream Payments", "cs_live_71e8b2d5a0f439c6", "Card processing"),
    ])
    c.commit()
    c.close()
