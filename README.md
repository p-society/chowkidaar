# 🤖 Chowkidaar | Discord Monitoring & Engagement Bot

<div align="center">

**Chowkidaar** is a modern, high-performance Discord automation and student activity tracking bot built using **Python (discord.py)**, **PostgreSQL**, and **Docker**. Developed for community events like *Days of Productivity*, it tracks daily progress, syncs badges, pings contest reminders, and renders premium cyber-themed profile cards for participants.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![Discord.py](https://img.shields.io/badge/Discord.py-v2.3-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discordpy.readthedocs.io)

<h3>
  <a href="https://dev-psoc.netlify.app/">Website</a> · 
  <a href="https://discord.gg/5Tj7DEED">Community Discord</a> · 
  <a href="https://github.com/p-society/chowkidaar/projects?type=classic">Contribute</a>
</h3>

</div>

---

## ✨ Features

*   🚀 **Modern Slash Commands**: Fully migrated to Discord's latest Application Commands architecture with instant guild synchronization.
*   📊 **Daily Submissions (`/submit`)**: Student activity logger with automatic streak tracking, custom time brackets, and validation guards.
*   🏆 **Milestone & Badge System**: Automatic badge rewards (e.g. Day 7, Day 14, Day 25) with dynamic Discord Role allocation.
*   🎨 **Premium Profile Cards**: Offline-renderable cyber-themed PNG cards showing student streaks, problems solved, progress bar, and high-resolution earned medals.
*   ⏰ **Contest Reminders**: Idempotent polling loop fetching LeetCode, Codeforces, and CodeChef contest updates with automatic role pings 12 hours, 15 minutes, and 0 minutes before start.
*   📈 **Real-Time Metrics**: Integrated Prometheus metrics server exporting event monitoring state on port `8000`.

---

## 📂 Project Structure

```
chowkidaar/
├── main.py                     # Bot Orchestrator & Setup Hook
├── cogs/                       # Interactive Slash Commands (Cogs)
│   ├── registration.py         # Handles /register, /profile
│   ├── submissions.py          # Handles /submit, /status, /edit_submission
│   ├── contests.py             # Handles /upcoming, contest pollers & reminders
│   ├── badges.py               # Handles admin sync helpers (/sync_badges)
│   └── help.py                 # Interactive Menu-Driven /help
├── db/                         # Database Access & Management
│   ├── db.py                   # Central connection pool & transaction utilities
│   ├── badges_config.py        # Centralized Badge Catalog & JSON Synchronization
│   ├── contest_calendar.py     # Upcoming contest schedule fetching & cache guards
│   └── contest_reminders.py    # Idempotent DB-backed reminder tracking
├── utils/                      # Core Utility Libraries
│   ├── card_generator.py       # Premium Profile Card canvas builder
│   ├── permissions.py          # Channel-specific execution guards
│   └── metrics.py              # Prometheus metric exporters
└── configs/                    # Static Configuration Files (Single Source of Truth)
    ├── event_config.json       # Start dates, duration, badge roles, branding templates
    ├── questions.json          # Maps event day numbers to coding challenges
    └── dev.json                # Daily resource links for development trackers
```

---

## ⚙️ Configuration Hub

All user-customizable parameters are maintained in **JSON config files** under `configs/`. You do not need to modify Python code to change event settings!

### 1. `configs/event_config.json`
Manages event durations, branding titles, and Discord Role mappings for earned badges:
```json
{
  "start_date": "2026-05-19",
  "bot_admins": [803101677460520990],
  "branding": {
    "title": "25 Days of Productivity",
    "subtitle": "by The Programming Society · IIIT-BH"
  },
  "cp": {
    "duration_days": 25,
    "announcement_intro": "**Day {day} Coding Challenge** 🚀\n\n",
    "announcement_outro": "\n⏰ **Log your progress using `/submit` before Noon!**"
  },
  "badge_roles": {
    "day7_done": 123456789012345678,
    "day14_done": 123456789012345678,
    "day25_done": 123456789012345678,
    "contest_participant": 123456789012345678,
    "contest_top_100": 123456789012345678,
    "contest_rating_climber": 123456789012345678
  }
}
```

### 2. Environment Variables (`.env.local`)
Create `.env.local` based on `.env.example` to store credentials. 

> [!NOTE]
> Bot slash commands are enabled **server-wide** (across all channels). However, automated daily challenges and contest reminders are routed to specific channels to prevent spam.

```ini
DISCORD_TOKEN=your_bot_token_here
NEON_DB_URL=postgresql://user:password@localhost:5433/db

# Channel for Daily Challenge announcements & Dev learning resources
WATCHED_CHANNEL_ID=123456789012345678

# Channel for Competitive Programming contest reminders (12h, 15m, 0m before start)
CONTEST_REMINDER_CHANNEL_ID=123456789012345678

# Discord Role ID to mention/tag during contest reminders
CONTEST_ROLE_ID=123456789012345678

# Clist.by credentials (needed for upcoming contest fetching)
CLIST_USERNAME=your_clist_username
CLIST_API_KEY=your_clist_api_key
```

---

## 🚀 Getting Started

Follow this quick guide to spin up Chowkidaar locally:

### 1. Set Up Virtual Environment
Chowkidaar uses `uv` for lightning-fast dependency loading and management:
```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Initialize and install dependencies
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 2. Spin Up Local PostgreSQL (Docker)
Start the pre-configured local PostgreSQL container:
```bash
sudo docker compose up -d
```

### 3. Initialize Schema & Migrations
Allow ~10 seconds for PostgreSQL to boot up fully, then run the database setup scripts:
```bash
uv run --python 3.12 scripts/init_db.py
uv run --python 3.12 scripts/init_badges_contests.py
uv run --python 3.12 scripts/init_badge_nicknames.py
```

### 4. Run the Bot!
```bash
uv run --python 3.12 main.py
```

---

## 🎨 Offline Profile Card Testing

You can generate and preview sample profile cards covering different milestone levels completely offline:
```bash
uv run --python 3.12 scripts/test_card.py
```
This renders 5 sample cards inside `outputs/`:
*   `outputs/card_no_badges.png` (Default state)
*   `outputs/card_early.png` (Intro progress)
*   `outputs/card_mid.png` (Bronze Medal unlocked)
*   `outputs/card_late.png` (Bronze + Silver Medals unlocked)
*   `outputs/card_done.png` (Bronze + Silver + Gold Medals unlocked)

---

## 📖 Developer Guide: Adding a Badge

To create a new event badge:
1.  **Add Assets**: Save a transparent square PNG image (e.g. `day30_done.png`) in `assets/badges/`.
2.  **Declare Badge**: Append the badge properties to the `BADGES_CATALOG` list in `db/badges_config.py`:
    ```python
    {
        "key": "day30_done",
        "name": "Day 30 Champion",
        "description": "Completed the extended 30-day coding marathon",
        "category": "milestone",
        "emoji": "👑",
        "display_priority": 40,
        "threshold": 30,
    }
    ```
3.  **Map Discord Role**: Open `configs/event_config.json` and add the role mapping under `"badge_roles"`:
    ```json
    "day30_done": 123456789012345678
    ```
On the next bot startup, the catalog is fully auto-synced into your database!

---

## 👥 Contributors

<a href="https://github.com/p-society/chowkidaar/graphs/contributors">
  <img src="https://contributors-img.web.app/image?repo=p-society/chowkidaar" />
</a>

