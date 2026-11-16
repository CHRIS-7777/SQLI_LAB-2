"""DailyDispatch - regional online newspaper (public pages only)."""
import base64
import binascii
import hashlib
import json
import random
import re
import secrets
import sqlite3
from datetime import datetime, timedelta

from flask import Blueprint, g, make_response, redirect, render_template_string, request

from ..common import sqlite_conn

META = {
    "slug": "dailydispatch",
    "title": "DailyDispatch",
    "tagline": "Regional news, analysis and opinion, updated through the day.",
    "prefix": "/news",
}
P = META["prefix"]
bp = Blueprint("dailydispatch", __name__)
DB = "dailydispatch"

EDITIONS = {"intl": "International", "us": "United States", "uk": "United Kingdom", "eu": "Europe", "asia": "Asia-Pacific"}
CATEGORIES = [("world", "World", "Global affairs and diplomacy"), ("politics", "Politics", "Government, elections and policy"),
              ("business", "Business", "Markets, companies and the economy"), ("tech", "Technology", "Science, software and gadgets"),
              ("sport", "Sport", "Results, transfers and analysis"), ("culture", "Culture", "Film, books, music and food")]
DISPLAY_MODES = ("standard", "compact", "large")
COLS = "id,title,summary,category,published"


def hp(pw):
    return hashlib.sha256(("dd$" + pw).encode()).hexdigest()


# --------------------------------------------------------------------------- schema / seed
HEADLINES = {
    "world": [("Leaders agree framework for Baltic shipping lanes", "Ministers from eight countries signed a framework after two days of talks."),
              ("Flood relief reaches remote river districts", "Aid convoys crossed damaged bridges as water levels began to fall."),
              ("Summit ends with pledge on clean water access", "Delegates committed new funding for rural water projects."),
              ("Border crossing reopens after three-year closure", "Trade is expected to resume within weeks, officials said."),
              ("Fishing communities protest new quota rules", "Coastal towns say the limits threaten the winter season."),
              ("Earthquake survey finds fewer collapsed buildings", "Engineers credited stricter building codes introduced a decade ago."),
              ("Rail link between two capitals to be completed early", "Contractors say the high-speed line could open by spring."),
              ("Archaeologists uncover merchant harbour near old port", "The site dates to the second century and is remarkably intact.")],
    "politics": [("Parliament votes to extend local election terms", "The bill passed after a late-night debate with a narrow majority."),
                 ("Budget committee questions transport spending", "Members asked for a detailed breakdown of regional projects."),
                 ("New housing plan promises 40,000 affordable homes", "The scheme relies on partnerships with private developers."),
                 ("Mayor defends congestion charge expansion", "Critics argue the zone should wait for better public transport."),
                 ("Opposition unveils health service proposals", "The package focuses on waiting times and rural clinics."),
                 ("Council rejects plan for waterfront tower", "Residents cheered as the vote went against the developer."),
                 ("Cross-party group calls for voting reform", "The report recommends trialling ranked ballots in two regions."),
                 ("Minister announces review of school funding", "Findings will be published before the next spending round.")],
    "business": [("Retail sales rise for third straight month", "Online grocery and home improvement led the growth."),
                 ("Shipbuilder wins record order from northern operator", "The contract secures work for 2,000 employees."),
                 ("Central bank holds rates, flags cautious outlook", "Policymakers pointed to slowing wage growth."),
                 ("Local brewery expands into three export markets", "The family firm doubled output after upgrading its plant."),
                 ("Airline adds winter routes to coastal resorts", "Bookings are up sharply compared with last year."),
                 ("Energy prices ease as storage levels recover", "Analysts expect lower household bills by the new year."),
                 ("Startup raises funding for battery recycling plant", "The facility will process 10,000 tonnes a year."),
                 ("Port authority reports busiest quarter on record", "Container volumes climbed nine percent.")],
    "tech": [("Researchers demonstrate low-cost solar window coating", "Early tests show a meaningful gain in building efficiency."),
             ("City trials autonomous shuttle on university loop", "Passengers will ride free during the three-month pilot."),
             ("Open-source mapping project passes milestone", "Volunteers have now charted more than a billion features."),
             ("Telecom operator switches on new fibre network", "Speeds of up to 2 gigabits reach 120,000 homes."),
             ("Museum launches virtual tour of medieval library", "Visitors can browse high-resolution scans of rare manuscripts."),
             ("Hospital adopts AI tool to speed up scan reviews", "Clinicians remain responsible for every diagnosis."),
             ("Satellite imagery helps farmers plan irrigation", "A pilot cut water use by one fifth on test farms."),
             ("Students build weather balloon that reached the stratosphere", "The team recovered the equipment 80 miles away.")],
    "sport": [("Rovers stun league leaders with late winner", "A 90th-minute header sealed a famous away win."),
              ("Young sprinter breaks national indoor record", "The teenager clocked a time that surprised even her coach."),
              ("Cycling tour unveils route through mountain passes", "Organisers promise the toughest finish in a decade."),
              ("Rugby side names new captain for winter series", "The flanker takes over after a long injury absence."),
              ("City marathon sells out in under an hour", "Charity places remain open through the organisers."),
              ("Swimming federation backs revised qualifying times", "Coaches welcomed the change after a lengthy consultation."),
              ("Tennis veteran announces retirement after final season", "She will play her last tournament on home courts."),
              ("Cricket tour begins with comfortable warm-up victory", "The bowlers set the tone with three early wickets.")],
    "culture": [("Debut novel wins regional book prize", "Judges praised its patient, quietly funny prose."),
                ("Film festival opens with restored silent classic", "A live orchestra accompanied the screening."),
                ("Street food market moves to the old rail depot", "Forty vendors will trade there every weekend."),
                ("Theatre company announces open-air summer season", "Productions include a new adaptation of a folk tale."),
                ("Gallery acquires collection of early photography", "The prints document a century of harbour life."),
                ("Jazz weekender returns with expanded line-up", "Organisers added a second stage by the river."),
                ("Chef opens restaurant celebrating regional produce", "The menu changes with the market each week."),
                ("Library launches reading scheme for teenagers", "Authors will visit twelve schools this term.")],
}
PARAS = ["Officials said the details would be confirmed in the coming days, with further statements expected later in the week.",
         "Observers noted that the announcement followed months of negotiations and public pressure from several groups.",
         "Local residents gave a mixed response, with some welcoming the change and others calling for more consultation.",
         "A spokesperson declined to comment on figures but said the situation was being monitored closely.",
         "Experts cautioned that the long-term effects remain uncertain, and called for independent evaluation."]


def init_db():
    rnd = random.Random(7718)
    c = sqlite_conn(DB)
    cur = c.cursor()
    for t in ("wire_services", "page_views", "ad_campaigns", "subscribers", "comments", "articles", "categories", "editors", "messages"):
        cur.execute(f"DROP TABLE IF EXISTS {t}")
    cur.executescript("""
CREATE TABLE editors(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, email TEXT, password_hash TEXT,
    display_name TEXT, role TEXT, created_at TEXT);
CREATE TABLE categories(id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT UNIQUE, name TEXT, description TEXT);
CREATE TABLE articles(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, summary TEXT, body TEXT, category TEXT,
    edition TEXT, author_id INTEGER, published TEXT, views INTEGER DEFAULT 0, featured INTEGER DEFAULT 0);
CREATE TABLE subscribers(id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, plan TEXT, joined TEXT);
CREATE TABLE ad_campaigns(id INTEGER PRIMARY KEY AUTOINCREMENT, advertiser TEXT, budget INTEGER, starts TEXT, ends TEXT);
CREATE TABLE wire_services(id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT, api_user TEXT, api_key TEXT, notes TEXT);
CREATE TABLE messages(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, body TEXT, created_at TEXT);
""")
    now = datetime(2026, 11, 1, 7, 30)
    eds = [("a.moreno", "Ana Moreno", "editor-in-chief"), ("t.whitfield", "Tom Whitfield", "politics editor"), ("r.sato", "Reiko Sato", "world editor"),
           ("k.bello", "Kemi Bello", "business editor"), ("j.larsen", "Jonas Larsen", "tech editor"), ("m.dupont", "Marc Dupont", "sports editor"),
           ("l.haas", "Lena Haas", "culture editor"), ("webdesk", "Web Desk", "producer")]
    for u, n, r in eds:
        cur.execute("INSERT INTO editors(username,email,password_hash,display_name,role,created_at) VALUES (?,?,?,?,?,?)",
                    (u, f"{u}@dailydispatch-news.example", hp(f"{u.split('.')[-1]}-{rnd.randint(1000, 9999)}"), n, r, str(now - timedelta(days=rnd.randint(200, 1500)))[:10]))
    for s, n, d in CATEGORIES:
        cur.execute("INSERT INTO categories(slug,name,description) VALUES (?,?,?)", (s, n, d))
    i = 0
    items = [(cat, h, s) for cat, lst in HEADLINES.items() for h, s in lst]
    rnd.shuffle(items)
    for cat, h, s in items:
        ed = list(EDITIONS)[i % 5]
        body = "\n\n".join([s] + rnd.sample(PARAS, 3))
        when = now - timedelta(hours=i * 9 + rnd.randint(0, 5))
        if i >= 42:
            when -= timedelta(days=730)
        elif i >= 36:
            when -= timedelta(days=365)
        cur.execute("INSERT INTO articles(title,summary,body,category,edition,author_id,published,views,featured) VALUES (?,?,?,?,?,?,?,?,?)",
                    (h, s, body, cat, ed, rnd.randint(1, 7), when.strftime("%Y-%m-%d %H:%M"), rnd.randint(120, 9000), 1 if i % 11 == 0 else 0))
        i += 1
    for k in range(36):
        cur.execute("INSERT INTO subscribers(email,plan,joined) VALUES (?,?,?)",
                    (f"reader{k + 100}@mail.example", rnd.choice(["digital", "weekend", "print+digital"]), str(now - timedelta(days=rnd.randint(1, 800)))[:10]))
    for adv in ["Harbor Motors", "Northline Bank", "Greenway Energy", "Bluebird Travel", "Summit Outdoor", "Orchard Foods", "Pioneer Telecom",
                "City Savings", "Lakeview Hotels", "Brightside Insurance", "Metro Fitness", "Quill Books"]:
        cur.execute("INSERT INTO ad_campaigns(advertiser,budget,starts,ends) VALUES (?,?,?,?)",
                    (adv, rnd.randint(2, 90) * 1000, str(now - timedelta(days=rnd.randint(1, 60)))[:10], str(now + timedelta(days=rnd.randint(5, 90)))[:10]))
    for p, u, k, n in [("Continental Wire", "ddnews", "cw_" + secrets.token_hex(12), "Primary feed"), ("Pacific Press Link", "dd-apac", "pp_" + secrets.token_hex(12), "APAC desk"),
                       ("Sports Data Co", "dd_sports", "sd_" + secrets.token_hex(10), "Live scores"), ("Photo Archive", "dd_photo", "FLAG{dailydispatch_copper_heron_58bd}", "Licence renewal pending"),
                       ("Market Ticker", "dd_markets", "mk_" + secrets.token_hex(10), "Delayed quotes"), ("Weather Service", "dd_wx", "wx_" + secrets.token_hex(8), "Free tier")]:
        cur.execute("INSERT INTO wire_services(provider,api_user,api_key,notes) VALUES (?,?,?,?)", (p, u, k, n))
    c.commit()
    c.close()


# --------------------------------------------------------------------------- helpers
def run(sql, params=(), fetch="all"):
    c = sqlite_conn(DB)
    try:
        cur = c.cursor()
        cur.execute(sql, params)
        if fetch == "all":
            return cur.fetchall()
        if fetch == "one":
            return cur.fetchone()
        c.commit()
        return cur.lastrowid
    finally:
        c.close()


def execute_raw(sql):
    c = sqlite_conn(DB)
    try:
        return c.execute(sql).fetchall()
    finally:
        c.close()


def b64e(s):
    return base64.urlsafe_b64encode(s.encode()).decode()


def b64d(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)).decode()


def prefs_cookie_value(ed="intl", dm="standard"):
    return b64e(json.dumps({"ed": ed, "dm": dm}, separators=(",", ":")))


def read_prefs():
    """Return (edition_string, display_mode) from the preferences cookie."""
    raw = request.cookies.get("dd_prefs")
    ed, dm = "intl", "standard"
    if raw:
        try:
            p = json.loads(b64d(raw))
            if isinstance(p, dict):
                if isinstance(p.get("ed"), str):
                    ed = p["ed"]
                if p.get("dm") in DISPLAY_MODES:
                    dm = p["dm"]
        except (ValueError, binascii.Error, UnicodeDecodeError):
            pass
    return ed, dm


def sanitize_edition(v):
    """Edition codes are short lowercase tokens; reject anything that looks odd."""
    if len(v) > 400 or re.search(r"[ \t\r\n]", v):
        return "intl"
    return re.sub(r"union|select|from|where", "", v, flags=re.I)


@bp.after_request
def _cookies(resp):
    if "dd_prefs" not in request.cookies and not getattr(g, "prefs_set", False):
        resp.set_cookie("dd_prefs", prefs_cookie_value(), path=P, samesite="Lax", max_age=86400 * 365)
    return resp


LAYOUT = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{{ title or 'Home' }} | DailyDispatch</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}body{margin:0;background:#fbf8f1;color:#1c1c1c;font-family:Georgia,"Times New Roman",serif;line-height:1.55}
body.compact{font-size:14px}body.large{font-size:19px}
a{color:#a11d18;text-decoration:none}a:hover{text-decoration:underline}
.mast{border-bottom:3px double #1c1c1c;text-align:center;padding:16px 10px 8px;background:#fff}
.mast .date{font:12px/1 Arial,sans-serif;color:#777;letter-spacing:1px;text-transform:uppercase}
.mast h1{font-size:44px;margin:6px 0 2px;letter-spacing:-1px;font-weight:700}.mast h1 a{color:#1c1c1c;text-decoration:none}.mast h1 span{color:#b3201b}
.mast .tag{font:italic 14px Georgia;color:#666}
nav.sec{background:#1c1c1c;font-family:Arial,sans-serif;font-size:13px}nav.sec .in{max-width:1080px;margin:auto;display:flex;flex-wrap:wrap;align-items:center;gap:2px;padding:0 12px}
nav.sec a{color:#eee;text-decoration:none;padding:11px 12px;text-transform:uppercase;letter-spacing:.8px}nav.sec a:hover{background:#b3201b;text-decoration:none}
nav.sec form{margin-left:auto;display:flex;gap:6px}nav.sec form+form{margin-left:8px}
nav.sec select,nav.sec input{padding:5px 7px;font:12px Arial;border:0;border-radius:2px}nav.sec button{background:#b3201b;color:#fff;border:0;padding:5px 10px;font:12px Arial;cursor:pointer}
.wrap{max-width:1080px;margin:26px auto;padding:0 16px;display:grid;grid-template-columns:2fr 1fr;gap:34px}
.wrap.one{grid-template-columns:1fr}
@media(max-width:800px){.wrap{grid-template-columns:1fr}.mast h1{font-size:32px}}
h2.sh{font:700 13px Arial,sans-serif;text-transform:uppercase;letter-spacing:1.5px;color:#b3201b;border-bottom:2px solid #1c1c1c;padding-bottom:5px;margin:0 0 14px}
.story{border-bottom:1px solid #ddd5c4;padding:12px 0}.story h3{margin:2px 0 4px;font-size:21px}.story h3 a{color:#1c1c1c}.story h3 a:hover{color:#b3201b}
.story .k{font:11px Arial;text-transform:uppercase;color:#b3201b;letter-spacing:1px}.story .m{font:12px Arial;color:#888}.story p{margin:4px 0;color:#444}
.side .story h3{font-size:16px}.box{background:#fff;border:1px solid #ddd5c4;padding:14px;margin-bottom:22px}
article h1{font-size:34px;line-height:1.15;margin:4px 0 8px}article .m{font:13px Arial;color:#777;margin-bottom:16px}article p{font-size:18px}
.chips a{display:inline-block;background:#fff;border:1px solid #ddd5c4;padding:4px 14px;margin:0 6px 8px 0;font:14px Arial}
form.f label{display:block;font:13px Arial;margin:8px 0 3px}form.f input,form.f select{width:100%;max-width:360px;padding:8px;font:inherit;border:1px solid #bbb}
button.b{background:#1c1c1c;color:#fff;border:0;padding:9px 18px;font:13px Arial;cursor:pointer;margin-top:10px}
.msg{padding:9px 12px;font:14px Arial;margin-bottom:14px;background:#fde8e6;color:#8a1c1c}.msg.ok{background:#e3f4e8;color:#1a5c36}.muted{color:#888;font:13px Arial}
table{border-collapse:collapse;width:100%;background:#fff;font:14px Arial}th{text-align:left;background:#eee;padding:7px}td{padding:7px;border-top:1px solid #ddd5c4}
footer{border-top:3px double #1c1c1c;text-align:center;padding:22px;font:12px Arial;color:#777;margin-top:30px}footer a{color:#777;margin:0 6px}
</style></head><body class="{{ dm }}">
<div class="mast"><div class="date">{{ today }}</div><h1><a href="{{ P }}/">Daily<span>Dispatch</span></a></h1><div class="tag">Regional news, analysis and opinion</div></div>
<nav class="sec"><div class="in">{% for c in cats %}<a href="{{ P }}/section?cat={{ c['slug'] }}">{{ c['name'] }}</a>{% endfor %}<a href="{{ P }}/archive">Archive</a>
<form action="{{ P }}/search" method="get"><input name="q" placeholder="Search" value="{{ q or '' }}"><button>Go</button></form>
<form method="post" action="{{ P }}/prefs"><select name="edition">{% for k,v in editions.items() %}<option value="{{ k }}"{% if k == cur_ed %} selected{% endif %}>{{ v }}</option>{% endfor %}</select><button>Set</button></form>
</div></nav>
<div class="wrap{{ ' one' if single else '' }}">@@BODY@@</div>
<footer><a href="{{ P }}/about">About</a><a href="{{ P }}/contact">Contact</a><a href="{{ P }}/subscribe">Subscribe</a><a href="{{ P }}/feed.xml">RSS</a>
<div style="margin-top:8px">&copy; 2026 DailyDispatch Media Group</div></footer></body></html>"""

STORY = """{% macro story(a, show_summary=true) %}<div class="story"><div class="k">{{ a['category'] }}</div><h3><a href="{{ P }}/article?id={{ a['id'] }}">{{ a['title'] }}</a></h3>
{% if show_summary %}<p>{{ a['summary'] }}</p>{% endif %}<div class="m">{{ a['published'] }}</div></div>{% endmacro %}"""


def render(body, status=200, **ctx):
    ed, dm = read_prefs()
    ctx.setdefault("title", None)
    ctx.setdefault("q", "")
    ctx.setdefault("single", False)
    out = render_template_string(LAYOUT.replace("@@BODY@@", STORY + body), P=P, cats=run("SELECT slug,name FROM categories ORDER BY id"),
                                 editions=EDITIONS, cur_ed=ed if ed in EDITIONS else "intl", dm=dm,
                                 today=datetime(2026, 11, 13).strftime("%A, %d %B %Y"), **ctx)
    return make_response(out, status)


# --------------------------------------------------------------------------- pages
HOME = """<main><h2 class="sh">Latest news</h2>
{% for a in latest %}{{ story(a) }}{% endfor %}</main>
<aside class="side"><div class="box"><h2 class="sh">Top stories for your edition</h2>
{% for a in top %}{{ story(a, false) }}{% else %}<p class="muted">{{ 'Top stories are not showing right now.' if top_err else 'No stories for this edition yet.' }}</p>{% endfor %}</div>
<div class="box"><h2 class="sh">Newsletter</h2><p class="muted">Get the morning briefing in your inbox.</p><a href="{{ P }}/subscribe">Sign up</a></div></aside>"""


@bp.route("/")
def home():
    latest = run("SELECT " + COLS + " FROM articles ORDER BY published DESC LIMIT 10")
    ed, _ = read_prefs()
    ed = sanitize_edition(ed)
    sql = ("SELECT id, title, summary, category, published FROM articles WHERE edition = '" + ed +
           "' ORDER BY published DESC LIMIT 6")
    try:
        top = execute_raw(sql)
        top_err = False
    except sqlite3.Error:
        top, top_err = [], True
    return render(HOME, latest=latest, top=top, top_err=top_err)


SECTION = """<main>{% if cat %}<h2 class="sh">{{ cat['name'] }}</h2><p class="muted">{{ cat['description'] }}</p>
{% for a in rows %}{{ story(a) }}{% endfor %}{% else %}<h2 class="sh">Section</h2><p class="muted">No such section.</p>{% endif %}</main><aside class="side"></aside>"""


@bp.route("/section")
def section():
    slug = request.args.get("cat", "")
    cat = run("SELECT slug,name,description FROM categories WHERE slug = ?", (slug,), "one")
    rows = run("SELECT " + COLS + " FROM articles WHERE category = ? ORDER BY published DESC", (slug,)) if cat else []
    return render(SECTION, title=cat["name"] if cat else "Section", cat=cat, rows=rows)


ARTICLE = """<main>{% if a %}<article><div class="story" style="border:0;padding:0"><div class="k">{{ a['category'] }}</div></div><h1>{{ a['title'] }}</h1>
<div class="m">By <a href="{{ P }}/author?name={{ a['author']|urlencode }}">{{ a['author'] }}</a> &middot; {{ a['published'] }} &middot; {{ a['views'] }} views</div>
{% for p in paras %}<p>{{ p }}</p>{% endfor %}</article>
{% else %}<h2 class="sh">Article</h2><p class="muted">That article could not be found.</p>{% endif %}</main>
<aside class="side">{% if more %}<div class="box"><h2 class="sh">More in {{ a['category'] }}</h2>{% for m in more %}{{ story(m, false) }}{% endfor %}</div>{% endif %}</aside>"""


@bp.route("/article")
def article():
    raw = request.args.get("id", "")
    a, more = None, []
    if raw.isdigit() and len(raw) < 9:
        a = run("SELECT a.*, e.display_name AS author FROM articles a JOIN editors e ON e.id = a.author_id WHERE a.id = ?", (int(raw),), "one")
    if a:
        more = run("SELECT " + COLS + " FROM articles WHERE category = ? AND id != ? ORDER BY published DESC LIMIT 4", (a["category"], a["id"]))
    return render(ARTICLE, title=a["title"] if a else "Article", a=a, more=more, paras=a["body"].split("\n\n") if a else [])


SEARCH = """<main><h2 class="sh">Search</h2>{% if error %}<div class="msg">{{ error }}</div>{% endif %}
{% if q and not error %}<p class="muted">{{ rows|length }} result(s) for "{{ q }}"</p>{% endif %}
{% for a in rows %}{{ story(a) }}{% endfor %}</main><aside class="side"></aside>"""


@bp.route("/search")
def search():
    q = request.args.get("q", "").strip()
    rows, error = [], None
    if q:
        if len(q) > 80 or re.search(r"['\";\\]", q):
            error = "Search terms contain unsupported characters."
        else:
            rows = run("SELECT " + COLS + " FROM articles WHERE title LIKE ? OR summary LIKE ? ORDER BY published DESC LIMIT 30", ("%" + q + "%", "%" + q + "%"))
    return render(SEARCH, title="Search", q=q, rows=rows, error=error)


ARCHIVE = """<main><h2 class="sh">Archive</h2>
<div class="chips">{% for y in years %}<a href="{{ P }}/archive?year={{ y }}">{{ y }}</a>{% endfor %}</div>
{% if year %}<p class="muted">{{ rows|length }} stories from {{ year }}</p>{% for a in rows %}{{ story(a) }}{% endfor %}{% endif %}</main><aside class="side"></aside>"""


@bp.route("/archive")
def archive():
    year = request.args.get("year", "")
    rows = []
    if year:
        if re.fullmatch(r"\d{4}", year):
            rows = run("SELECT " + COLS + " FROM articles WHERE substr(published, 1, 4) = ? ORDER BY published DESC", (year,))
        else:
            year = ""
    return render(ARCHIVE, title="Archive", years=[2026, 2025, 2024], year=year, rows=rows)


AUTHOR = """<main>{% if e %}<h2 class="sh">{{ e['display_name'] }}</h2><p class="muted">{{ e['role'] }}</p>
{% for a in rows %}{{ story(a) }}{% endfor %}{% else %}<h2 class="sh">Author</h2><p class="muted">No author by that name.</p>{% endif %}</main><aside class="side"></aside>"""


@bp.route("/author")
def author():
    name = request.args.get("name", "").strip()
    e = run("SELECT id, display_name, role FROM editors WHERE display_name = ?", (name,), "one") if name and len(name) <= 80 else None
    rows = run("SELECT " + COLS + " FROM articles WHERE author_id = ? ORDER BY published DESC LIMIT 20", (e["id"],)) if e else []
    return render(AUTHOR, title="Author", e=e, rows=rows)


@bp.route("/prefs", methods=["POST"])
def set_prefs():
    ed = request.form.get("edition", "")
    if ed not in EDITIONS:
        ed = "intl"
    _, dm = read_prefs()
    g.prefs_set = True
    resp = redirect(P + "/")
    resp.set_cookie("dd_prefs", prefs_cookie_value(ed, dm), path=P, samesite="Lax", max_age=86400 * 365)
    return resp


SUBSCRIBE = """<main><h2 class="sh">Subscribe</h2>{% if done %}<div class="msg ok">Thank you for subscribing.</div>{% endif %}{% if error %}<div class="msg">{{ error }}</div>{% endif %}
<form class="f" method="post" action="{{ P }}/subscribe"><label>Email address</label><input name="email" required><label>Plan</label>
<select name="plan"><option>digital</option><option>weekend</option><option>print+digital</option></select><br><button class="b">Subscribe</button></form></main><aside class="side"></aside>"""


@bp.route("/subscribe", methods=["GET", "POST"])
def subscribe():
    done = error = None
    if request.method == "POST":
        em, plan = request.form.get("email", "").strip(), request.form.get("plan", "")
        if not re.fullmatch(r"[^@\s]{1,60}@[^@\s]{3,60}", em) or plan not in ("digital", "weekend", "print+digital"):
            error = "Please enter a valid email address and plan."
        else:
            run("INSERT INTO subscribers(email,plan,joined) VALUES (?,?,?)", (em, plan, datetime.utcnow().strftime("%Y-%m-%d")), "id")
            done = True
    return render(SUBSCRIBE, title="Subscribe", done=done, error=error)


@bp.route("/about")
def about():
    return render("""<main><h2 class="sh">About DailyDispatch</h2><p>DailyDispatch has reported on the region since 1921. Our newsroom of fewer than forty journalists covers
politics, business, technology, sport and culture, with an editorial line that answers to readers rather than shareholders.</p>
<p>Every story on this site is written, checked and edited in-house. Browse the <a href="{{ P }}/archive">archive</a> for earlier years.</p></main><aside class="side"></aside>""", title="About")


@bp.route("/contact", methods=["GET", "POST"])
def contact():
    sent = False
    if request.method == "POST":
        run("INSERT INTO messages(name,email,body,created_at) VALUES (?,?,?,?)",
            (request.form.get("name", "")[:80], request.form.get("email", "")[:120], request.form.get("message", "")[:500], datetime.utcnow().strftime("%Y-%m-%d %H:%M")), "id")
        sent = True
    return render("""<main><h2 class="sh">Contact the newsroom</h2>{% if sent %}<div class="msg ok">Thanks, your message has been received.</div>{% endif %}
<form class="f" method="post" action="{{ P }}/contact"><label>Name</label><input name="name" required><label>Email</label><input name="email" required>
<label>Message</label><input name="message" required><br><button class="b">Send</button></form></main><aside class="side"></aside>""", title="Contact", sent=sent)


@bp.route("/feed.xml")
def feed():
    cat = request.args.get("cat", "")
    if cat:
        rows = run("SELECT id,title,summary,published FROM articles WHERE category = ? ORDER BY published DESC LIMIT 20", (cat,))
    else:
        rows = run("SELECT id,title,summary,published FROM articles ORDER BY published DESC LIMIT 20")
    xml = render_template_string("""<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>DailyDispatch</title><link>/news/</link><description>Latest stories</description>
{% for r in rows %}<item><title>{{ r['title'] }}</title><link>/news/article?id={{ r['id'] }}</link><description>{{ r['summary'] }}</description><pubDate>{{ r['published'] }}</pubDate></item>{% endfor %}</channel></rss>""", rows=rows)
    return make_response(xml, 200, {"Content-Type": "application/rss+xml; charset=utf-8"})


# --------------------------------------------------------------------------- dead ends
@bp.route("/old")
def old():
    return render("""<main><h2 class="sh">This page has moved</h2><p>Please start again from the <a href="{{ P }}/">front page</a>.</p></main><aside class="side"></aside>""", title="Moved")


@bp.route("/admin")
@bp.route("/admin/<path:p>")
@bp.route("/backup.zip")
@bp.route("/db.sqlite")
def forbidden(p=None):
    return make_response("<h1>403 Forbidden</h1>", 403)


# --------------------------------------------------------------------------- unlisted pages (not linked anywhere)
IDLE = """<main><h2 class="sh">Nothing to show</h2><p class="muted">There is nothing to display here right now.</p></main><aside class="side"></aside>"""
MISSING = """<main><h2 class="sh">No match</h2><p class="muted">We could not find anything for that request.</p></main><aside class="side"></aside>"""
LIST = """<main><h2 class="sh">{{ heading }}</h2>{% for a in rows %}{{ story(a) }}{% else %}<p class="muted">No stories.</p>{% endfor %}</main><aside class="side"></aside>"""


@bp.route("/popular")
def popular():
    slug = request.args.get("section")
    if slug is None:
        return render(IDLE, title="Most read")
    cat = run("SELECT slug,name FROM categories WHERE slug = ?", (slug,), "one")
    if not cat:
        return render(MISSING, title="Most read")
    rows = run("SELECT " + COLS + " FROM articles WHERE category = ? ORDER BY views DESC LIMIT 5", (slug,))
    return render(LIST, title="Most read", heading="Most read in " + cat["name"], rows=rows)


@bp.route("/weekly")
def weekly():
    raw = request.args.get("issue")
    if raw is None:
        return render(IDLE, title="Weekly")
    if not (raw.isdigit() and 1 <= int(raw) <= 53) or len(raw) > 2:
        return render(MISSING, title="Weekly")
    rows = run("SELECT " + COLS + " FROM articles WHERE strftime('%W', published) = ? AND substr(published,1,4) = '2026' ORDER BY published DESC", ("%02d" % int(raw),))
    return render(LIST, title="Weekly", heading="Week " + raw, rows=rows)
