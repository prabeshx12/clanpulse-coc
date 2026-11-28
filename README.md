# ⚔️ ClanPulse — Clash of Clans War & Activity Tracker

A web dashboard that tracks a clan's **wars and member war performance over time**, plus a simple standalone player lookup.

> The Clash of Clans API only shows the *present*: the current war disappears once the next one starts.
> ClanPulse polls it on a schedule, stores every war, and builds the *history* the game doesn't give you.

---

## 🎯 Learning Goals

- ⬜ Designing a clean API client: one wrapper, typed errors, IP-restricted keys
- ⬜ Resilience: retries with exponential backoff, rate limits, maintenance windows
- ⬜ Testing HTTP code without hitting the real API (mocked responses)
- ⬜ Polling a "present-only" API and turning it into history
- ⬜ Idempotent ingestion: re-polling the same war never creates duplicates
- ⬜ Relational modeling with SQLAlchemy 2.0 (wars → participants → attacks)
- ⬜ Building my own API on top of someone else's (FastAPI)
- ⬜ Server-rendered dashboards with charts
- ⬜ Deploying to a server with a fixed IP

---

## 🧰 Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Language | Python 3.11+ | Readable, great for learning |
| HTTP client | `httpx` | Modern, supports async |
| Backend API | FastAPI | Auto-generated docs at `/docs` |
| Database | SQLite + SQLAlchemy | Zero setup, easy to swap later |
| Scheduler | APScheduler | Runs the poller every few minutes |
| Frontend | Jinja2 templates + Chart.js | Simple, no build step |
| Config | `python-dotenv` | Keeps the API key out of code |
| Bot (stretch) | `discord.py` | War reminders |

---

## 📁 Project Structure (target)

```
clanpulse/
├── README.md
├── .env                   # Secrets (never commit!)
├── .env.example
├── .gitignore
├── requirements.txt
├── app/
│   ├── config.py          # Loads settings from .env
│   ├── coc_client.py      # Wrapper around the CoC API
│   ├── models.py          # Database tables
│   ├── db.py              # DB session/engine
│   ├── collector.py       # Polls API & saves snapshots
│   ├── scheduler.py       # Runs collector on a timer
│   ├── stats.py           # Calculates averages, ratios, etc.
│   ├── main.py            # FastAPI app
│   ├── routes/            # My API endpoints
│   └── templates/         # Dashboard HTML pages
├── bot/                   # (Stretch) Discord bot
├── scripts/               # One-off experiment scripts
└── tests/
```

---

## 🔑 Setup

### 1. Get an API key
1. Sign in at https://developer.clashofclans.com
2. Find your public IP (search "what is my ip").
3. Create a key and add that IP. **The key only works from the listed IPs.**
4. If your home IP changes, a request will fail with `403`. Update the key's IP when that happens.

### 2. Environment
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

`.env`:
```
COC_API_KEY=your_key_here
CLAN_TAG=#YOURTAG
DATABASE_URL=sqlite:///clanpulse.db
POLL_MINUTES=10
```

### 3. Run
```bash
uvicorn app.main:app --reload
# Dashboard: http://localhost:8000
# API docs:  http://localhost:8000/docs
```

---

## 📚 CoC API Cheat Sheet

**Base URL:** `https://api.clashofclans.com/v1`
**Header:** `Authorization: Bearer <COC_API_KEY>`
**Tags:** always URL-encode, so `#2PP` → `%232PP`

| Endpoint | What it gives |
|---|---|
| `GET /clans/{tag}` | Clan info + member list |
| `GET /clans/{tag}/members` | Members with donations, trophies, role |
| `GET /clans/{tag}/currentwar` | Current war state, attacks, stars |
| `GET /clans/{tag}/warlog` | Past war results (clan must make log public) |
| `GET /clans/{tag}/currentwar/leaguegroup` | CWL group and war tags |
| `GET /clanwarleagues/wars/{warTag}` | One CWL war's details |
| `GET /clans/{tag}/capitalraidseasons` | Raid weekend results |
| `GET /players/{tag}` | Player profile, troops, heroes |
| `POST /players/{tag}/verifytoken` | Verify account ownership |
| `GET /locations` | Location IDs |
| `GET /locations/{id}/rankings/clans` | Clan leaderboard for a region |
| `GET /leagues` | League list |
| `GET /goldpass/seasons/current` | Current Gold Pass season dates |

**War `state` values:** `notInWar`, `preparation`, `inWar`, `warEnded`

**Common errors:**

| Code | Meaning | Usual cause |
|---|---|---|
| 400 | Bad request | Malformed parameters |
| 403 | Forbidden | Wrong key, or IP not on the key's list |
| 404 | Not found | Wrong tag or forgot to encode `#` |
| 429 | Too many requests | Hit the rate limit, so slow down |
| 503 | Maintenance | Game servers are under maintenance |

---

## 🗄️ Data Model (draft)

**Core (war tracker)**
- **members**: tag (PK), name, town_hall, role, first_seen, last_seen, in_clan
- **wars**: id, opponent_tag, opponent_name, team_size, attacks_per_member, preparation_start_time, start_time, end_time, state, result, is_cwl, clan/opponent stars + destruction, *unique on (opponent_tag, start_time)*
- **war_participants**: war_id, member_tag, map_position, town_hall, attacks_used, attacks_allowed (2 normal / 1 CWL → missed attacks)
- **war_attacks**: id, war_id, attacker_tag, defender_tag, stars, destruction, order, duration, *unique on (war_id, order)*

**Later**
- **member_snapshots**: donations / trophies over time
- **raid_seasons**, **raid_contributions**: raid weekends

Player lookup is **live only**: proxied straight from `/players/{tag}`, nothing stored.

---

## 🗺️ Daily Roadmap

One focused task per day.

### Phase 1: API Client (Days 1–4)
- ✅ **Day 1:** API key, venv, `.env`; `scripts/hello.py` prints clan info and members table
- ✅ **Day 2:** Dump raw JSON from `/currentwar`, `/warlog`, `/players/{tag}` into `scripts/samples/`; study the war shape (states, `attacks`, `order`, `bestOpponentAttack`)
- ✅ **Day 3:** `app/config.py` + `app/coc_client.py`: one class, shared `httpx.Client`, tag encoding, typed exceptions for 403/404/429/503 using the error `reason`
- ✅ **Day 4:** Retries with exponential backoff on 429/503; first tests with mocked HTTP

### Phase 2: War Data (Days 5–9)
- ✅ **Day 5:** `app/db.py` + `app/models.py`: `members`, `wars`, `war_participants`, `war_attacks`
- ⬜ **Day 6:** `collector.py`: parse `/currentwar` and upsert the war through `preparation → inWar → warEnded`
- ⬜ **Day 7:** Idempotent attacks: re-polling mid-war never duplicates; finalize result and missed attacks at `warEnded`
- ⬜ **Day 8:** `scheduler.py`: APScheduler runs the collector every `POLL_MINUTES` (≥ 5), with logging and error tolerance
- ⬜ **Day 9:** Backfill past results from `/warlog` (summary only; it has no per-attack data)

### Phase 3: My Own API (Days 10–13)
- ⬜ **Day 10:** FastAPI app; `GET /api/wars` and `GET /api/wars/{id}`
- ⬜ **Day 11:** `stats.py`: per-member avg stars, avg destruction, triple rate, missed attacks (with tests)
- ⬜ **Day 12:** `GET /api/members/{tag}/wars` and `GET /api/leaderboard?sort=stars|triples|missed`
- ⬜ **Day 13:** Player lookup (separate, live): `GET /api/players/{tag}` proxies `/players/{tag}`, no storage

### Phase 4: Dashboard (Days 14–17)
- ⬜ **Day 14:** Base Jinja2 layout + war history page
- ⬜ **Day 15:** War detail page: per-attack breakdown, missed attacks highlighted
- ⬜ **Day 16:** Member war-performance page with Chart.js (stars per war over time)
- ⬜ **Day 17:** Player lookup page (search by tag); polish: empty states, "last updated"

### Phase 5: CWL & Ship (Days 18–21)
- ⬜ **Day 18:** CWL: `/currentwar/leaguegroup` + each `/clanwarleagues/wars/{warTag}`, stored with `is_cwl`
- ⬜ **Day 19:** Small VPS + new API key locked to the server's IP
- ⬜ **Day 20:** Deploy with systemd (or Docker), add HTTPS
- ⬜ **Day 21:** Short project retrospective

### Later / Stretch
- ⬜ Member snapshots: donations, trophies, joins/leaves
- ⬜ Raid weekends
- ⬜ Discord bot: ping members with unused attacks before war ends
- ⬜ Track multiple clans / move to PostgreSQL

---

## ⚖️ Disclaimer

This material is unofficial and is not endorsed by Supercell. For more information see
Supercell's Fan Content Policy: https://supercell.com/en/fan-content-policy/
