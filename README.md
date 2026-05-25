<h1 align="center">
<!-- 	<img width="300" src="https://github.com/gCBS/gCBS_native/blob/stable/assets/gCBSColorPurp@3x.png?raw=true" alt="gCBS"> -->
      Chowkidaar | Discord Monitoring Bot
	<br>
</h1>


<div align="center">

Chowkidaar monitors the student activities during the 45 Days of Productivity - A PSoc Initiative.

<h3>P-Society Handles</h3>
<h3 align="center">
	<a href="https://dev-psoc.netlify.app/">Website</a>
	<span> | </span>
	<a href="https://discord.gg/5Tj7DEED">Community Discord</a>
	<span> | </span>
	<a href="https://github.com/gCBS/gCBS/projects?type=classic">Contribute</a>
</h3>

</div>

----------------------------------------
<div align="center">

**Chowkidaar** is a Automation & Monitoring Discord Bot. The application is built using Python, PostgreSQL, and Docker.
</div>
<div align="center">
<br/>
<img src='https://skillicons.dev/icons?i=py,postgresql,docker,prometheus' ></img>

</div>
<br/>

---

## 🛠️ Architecture & Core Components

Chowkidaar uses a modular, highly scalable, and clean Discord Cogs structure.

```
chowkidaar/
├── main.py (Bot Orchestrator)
├── cogs/ (Interactive Slash Commands)
│   ├── registration.py (/register, /profile commands)
│   ├── submissions.py (/submit, /status daily logger)
│   ├── contests.py (/upcoming command & auto-reminders)
│   ├── badges.py (/sync_badges admin helper)
│   └── help.py (Interactive Help Cog)
├── db/ (Database Management)
│   ├── db.py (Postgres Connection Pool)
│   ├── badges_config.py (Centralized Badge Catalog & Auto-Sync)
│   └── badges.py (Milestone & Attendance Interfaces)
└── utils/ (Core Bot Utilities)
    ├── card_generator.py (Premium Profile Card Renderer)
    ├── permissions.py (Custom Guild Channel Guards)
    └── metrics.py (Prometheus Exporter Endpoint)
```

### 1. Extracted Command Modules (Cogs)
All interactive slash commands are cleanly separated into extensions located in `cogs/`:
*   **`cogs/registration.py`**: Handles student registration (`/register`) and profile cards rendering (`/profile`). Downloads and buffers user avatar images on the fly.
*   **`cogs/submissions.py`**: Manages CP log submissions (`/submit`, `/edit_submission`, `/delete_submission`, `/status`). Automatically tracks user milestone thresholds and handles announcement logs.
*   **`cogs/contests.py`**: Fetches upcoming CP contests from Codeforces, LeetCode, and CodeChef using the Clist.by API. Automatically sends 12-hour, 15-minute, and 0-minute alerts to the progress channel and provides the `/upcoming` slash command.
*   **`cogs/badges.py`**: Provides administration tools for syncing milestone statuses and user roles (`/sync_badges`).
*   **`cogs/help.py`**: A clean, stylized interactive help menu showing available options.

### 2. Centralized Badge System & Auto-Sync
Badge catalogs are unified in **`db/badges_config.py`** via the `BADGES_CATALOG` list:
*   **Auto-Sync on Startup**: During bot booting inside `setup_hook()`, the function `sync_badges_to_db()` runs an idempotent `INSERT ON CONFLICT DO UPDATE` (UPSERT) query. Adding a badge only requires modifying the Python list; the database keeps itself perfectly in sync!
*   **Dynamic Threshold Mapping**: Milestone thresholds (e.g. Day 7, Day 14, Day 25) are dynamically loaded from the catalog catalog, avoiding hardcoded check loops.

### 3. Premium Profile Card Generator
The card builder (**`utils/card_generator.py`**) compiles a gorgeous cyber-themed card for users:
*   **Aesthetics**: Uses a classic high-end **Cyber Teal & Navy** color palette.
*   **Assets Paste Engine**: Renders custom high-resolution transparent circular PNG badges saved under `assets/badges/{key}.png` (e.g. `day7_done.png`, `day14_done.png`, `day25_done.png`). If earned, the card generator loads and pastes the high-res PNG directly onto the card. It automatically falls back to Unicode emojis if an asset file is not found.
*   **Stat Cards**: Renders detailed stat cards (`DAY STREAK`, `PROBLEMS SOLVED`) and a neon progress bar showing complete completion out of 25 days.

### 4. Prometheus Metrics Monitoring
An HTTP metrics endpoint is built into the bot via **`utils/metrics.py`**:
*   An independent metrics web server starts on port `8000` automatically.
*   Tracks message processing speed, submission attempts (`message_new_attempts_total`), command triggers, and database transaction latency.

---

## 🚀 Getting Started

Follow these steps to run Chowkidaar in your local environment:

### 1. Install `uv`
Chowkidaar uses `uv` for extremely fast Python packaging and dependency resolution:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install Project Dependencies
Run `uv` to automatically initialize a virtual environment and install all packages:
```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 3. Environment Setup
Create your configuration file by copying the template:
```bash
cp .env.example .env.local
```
Add your respective `DISCORD_TOKEN`, `NEON_DB_URL` (database string), `DEV_GUILD_ID` (for instant guild slash command syncing), `WATCHED_CHANNEL_ID`, `CONTEST_ROLE_ID`, `CLIST_USERNAME`, and `CLIST_API_KEY` to `.env.local`.

### 4. Boot Up Local Database (Docker Compose)
Start a local PostgreSQL instance:
```bash
sudo docker compose up -d
```

### 5. Initialize Schema & Migrations
Wait ~10 seconds for the database to fully initialize, then run the migrations in order:
```bash
uv run --python 3.12 scripts/init_db.py
uv run --python 3.12 scripts/init_badges_contests.py
uv run --python 3.12 scripts/init_badge_nicknames.py
```

### 6. Run the Bot!
```bash
uv run --python 3.12 main.py
```

---

## 🎨 How to Test Profile Cards locally
You can generate and preview sample profile cards covering different tier progress levels completely offline without booting Discord:
```bash
uv run --python 3.12 scripts/test_card.py
```
This generates five sample cards in `outputs/`:
*   `outputs/card_early.png`
*   `outputs/card_mid.png` (displays the new Cyber-Bronze Medal)
*   `outputs/card_late.png` (displays Bronze + Silver Medals)
*   `outputs/card_done.png` (displays Bronze, Silver, + Gold Medals)
*   `outputs/card_no_badges.png`

---

## 📖 Developer Guide: Adding a New Badge

Adding a new badge is fully automated and requires zero manual database modifications:

1.  **Create your Badge Asset**: Make a transparent square PNG image (e.g. `day30_done.png`) and save it inside the `assets/badges/` folder.
2.  **Add to Config Catalog**: Open `db/badges_config.py` and add a dictionary entry to the `BADGES_CATALOG` list:
    ```python
    {
        "key": "day30_done",
        "name": "Day 30 Champion",
        "description": "Completed the extended 30-day coding marathon",
        "category": "milestone",
        "emoji": "👑",
        "display_priority": 40,
        "threshold": 30,  # Auto-mapped threshold!
    }
    ```
3.  **Boot the Bot**: That's it! On startup, the bot will automatically create and sync the badge inside the database, and the profile card generator will automatically paste your transparent PNG asset when a user achieves the threshold!

---

## ⚙️ Maintenance & Configuration

To update the bot's content for a new year or season, you will need to modify the JSON configuration files located in the `configs/` directory. You do not need to edit any Python code!

*   **`configs/event_config.json`**: Edit this to change the `start_date`, the `duration_days` of the event, and the template text for daily announcements.
*   **`configs/questions.json`**: This JSON file maps the Day number to the specific LeetCode/CodeForces questions required for that day.
*   **`configs/dev.json`**: This JSON file contains the daily resource links and descriptions sent to the Development channel.

---

### Current contributors <a name="Current contributors"></a>

<a href="https://github.com/p-society/chowkidaar/graphs/contributors">
  <img src="https://contributors-img.web.app/image?repo=p-society/chowkidaar" />
</a>

Made with [contributors-img](https://contributors-img.web.app).

<!--
## Subscribe to updates
<!--
Join our [Discord Server](https://gCBS.com/joincommunity) and subscribe to this repository[Developer Newsletter](https://gCBS.com/newsletter/?utm_medium=community&utm_source=github&utm_campaign=gCBS%20repo) to get updates, information about gCBS 
-->

# License <a name="License"></a>

PSoc/Chowkidaar is licensed under [GPL-3.0 License](https://github.com/p-society/chowkidaar/blob/main/LICENSE)
