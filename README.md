# Meridian Web Services — SQL Injection Practice Lab (black-box)

Seven small web apps behind one hub, all vulnerable **only** to SQL injection.
Databases: **SQLite, MySQL, MSSQL** (no PostgreSQL / Oracle).
Difficulty runs from easy to extreme. No time-based or boolean-blind injection: every bug can be exploited
in-band (reflected rows or reflected DB errors). Expect rabbit holes: look-alike parameters, dead-end
pages and fake data that are *not* injectable.

**Goal for every app:** find the injection point, get the DB **version**, list **tables**, list **columns**,
and dump the dummy data (including the `FLAG{...}` string).

**Recon expectations:** the apps are public sites (no sign-up needed). Several have endpoints and
parameters that are not linked anywhere, so crawling alone is not enough. Use ffuf / brute forcing
with the usual Kali wordlists (`/usr/share/wordlists/dirb/common.txt`,
`/usr/share/seclists/Discovery/Web-Content/raft-small-words.txt`, `burp-parameter-names.txt`).
Every app also has several normal-looking `endpoint?param=value` pages that are decoys.

> This is a black-box exercise. Do not read `lab/apps/*.py` or the `solutions/` folder until you have
> given up on an app. The write-ups are in **`SOLUTIONS.md`** (kept separate on purpose).

## Requirements (already present on the Kali VM)
Docker + Docker Compose, Python 3 with Flask, PyMySQL and pymssql (`pip install -r requirements.txt` if missing).

## Run
```bash
cd /home/kali/SQLI/CLAUDE
./setup.sh      # first time only (safe to re-run): starts DB containers, creates DBs, seeds data
./run.sh        # starts the web app on port 5050 (Ctrl+C to stop)
```
Then browse to `http://<vm-ip>:5050/` (VM IP: `hostname -I`), or `http://127.0.0.1:5050/` from the VM.
Every app has its own prefix; start from the hub page and treat it as your scope.

Accounts: where an app has registration you can create your own account. There is no hint file with credentials.

## Maintenance
| Command | Purpose |
|---|---|
| `./reset.sh` | Restore all databases to their original data (use after a destructive payload) |
| `./stop.sh` | Stop the DB containers (frees ~1 GB RAM); `./run.sh` starts them again |
| `docker compose down -v` | Remove the lab containers *and* their data volumes completely |

Ports: web `5050` (all interfaces); MySQL `127.0.0.1:33071` and MSSQL `127.0.0.1:14341` are bound to
localhost only. The lab's containers are named `claude-sqli-*` and do not interfere with other labs on the VM.
The app connects with low-privilege DB users, so injection exposes data in the lab schemas only (no file or OS access).

## Memory note
The MSSQL container needs ~1 GB. If the VM runs low on RAM, stop other labs/containers you are not using.

## Layout
```
setup.sh run.sh reset.sh stop.sh docker-compose.yml requirements.txt
lab/            application code (spoilers!)
solutions/      per-app write-ups + self-test scripts (spoilers!)
SOLUTIONS.md    full walkthrough of every app (spoilers!)
```

Use only on your own VM, for practice.
