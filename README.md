# 🏋️ Workout Bot

A Discord bot for tracking workouts and supporting your crew on their fitness journey. Logs exercises, tracks progress, keeps streaks, and gives personalized coaching powered by a **local LLM via [Ollama](https://ollama.com)** — no API keys, no per-message costs, your data stays on your own machine.

**Features:**
- 💪 Log workouts with exercises, sets, reps, weight (fast, no AI noise)
- 🏋️ `/workout <focus>` — AI-generated routines for legs, arms, push, full body, etc.
- 🤖 On-demand AI coaching that references your real history (runs locally via Ollama)
- 📊 Personal stats and progress tracking
- 🔥 Daily streak tracking
- 🏆 Server leaderboards by volume
- 🎯 Goal setting with memory
- 💾 Full conversation memory in PostgreSQL
- ⚡ Async architecture with connection pooling

## Quick Start (Docker — recommended)

This is the easiest path: one command starts the bot, the database, **and** Ollama together.

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) + Docker Compose
- A Discord bot token (see below)
- A reasonably capable host (the default `llama3.2` model runs fine on CPU; a GPU is faster)

### Steps

1. **Clone the repo**
   ```bash
   git clone https://github.com/YOUR_USERNAME/workout-bot.git
   cd workout-bot
   ```

2. **Create your Discord bot**
   - Go to the [Discord Developer Portal](https://discord.com/developers/applications)
   - **New Application** → **Bot** → **Reset Token** → copy the token
   - **Installation** (or **OAuth2 → URL Generator**): scopes `bot` + `applications.commands`; bot permissions: *Send Messages*, *Embed Links*
   - Open the generated URL to add the bot to your server

3. **Configure**
   ```bash
   cp .env.example .env
   # Edit .env and paste your DISCORD_TOKEN.
   # Everything else can stay at its defaults for Docker.
   ```

4. **Run**
   ```bash
   docker compose up -d
   ```
   On first launch the `ollama-pull` helper downloads the `llama3.2` model (~2 GB), so give it a few minutes. Watch progress with:
   ```bash
   docker compose logs -f
   ```

The bot should come online in Discord. Try:
```
/log_workout exercise:Bench Press sets:4 reps:8 weight:225
```

## Running without Docker (local Python)

1. Install and start [Ollama](https://ollama.com/download), then pull the model:
   ```bash
   ollama pull llama3.2
   ```
2. Have a PostgreSQL database ready (local, or a free one from [Neon](https://neon.tech) / [Railway](https://railway.app)).
3. Set up Python:
   ```bash
   python3 -m venv venv
   source venv/bin/activate        # macOS/Linux  (Windows: venv\Scripts\activate)
   pip install -r requirements.txt
   ```
4. Configure `.env` (note: outside Docker the hosts are `localhost`, not the container names):
   ```
   DISCORD_TOKEN=your_token
   DATABASE_URL=postgresql://user:password@localhost:5432/workout_bot
   OLLAMA_HOST=http://localhost:11434
   OLLAMA_MODEL=llama3.2
   ```
5. Run:
   ```bash
   python workout_bot.py
   ```

> **Tip:** Already have Ollama running on another machine (e.g. a homelab box)? Point `OLLAMA_HOST` at it, like `http://192.168.1.50:11434`, and skip the bundled Ollama container.

## Commands

### `/log_workout`
Log a workout. Saves it, updates your streak, and replies instantly with a clean stats card — **no AI chatter**.
```
/log_workout exercise:Bench Press sets:4 reps:8 weight:225 notes:Felt strong! duration:45
```
- `exercise` (required) — Exercise name
- `sets` (required) — Number of sets
- `reps` (required) — Reps per set
- `weight` (required) — Weight in lbs
- `notes` (optional) — Notes about the workout
- `duration` (optional) — Duration in minutes

### `/workout`
AI builds a full routine for the focus you pick (legs, arms, chest, back, shoulders, core, push, pull, full body, cardio), tailored to your recent history.
```
/workout focus:Legs
```

### `/advice`
Ask a fitness question. The bot answers using your workout history and goals.
```
/advice question:How should I program my bench to hit 315?
```

### `/stats`
Your total workouts, total volume, current streak, and recent lifts.

### `/leaderboard`
Top 10 in the server by total volume lifted.

### `/set_goal`
Set a goal the bot remembers.
```
/set_goal goal:Bench press 315 lbs days:90
```

## How the memory works

Everything lives in PostgreSQL, so the bot has real context when it coaches you:
- Your last workouts (exercise, weight, sets, reps, dates)
- Your recent conversation in that channel
- Your active goals

That context is fed to the local Ollama model only when you run `/workout` or `/advice`, so the AI references your actual training instead of being generic.

**The bot is command-only.** It has no message listener — it never reads or replies to your normal conversation in the server. It speaks only when someone runs one of its slash commands.

## Database schema

```
users               user_id (Discord ID), username, goals, preferences (JSON)
workouts            id, user_id, exercise, sets, reps, weight, notes, duration, logged_at
conversation_memory id, user_id, channel_id, message_role, message_content, timestamp
goals               id, user_id, goal_text, target_date, progress_notes, created_at
leaderboard         user_id, total_volume, total_workouts, streak, last_workout, updated_at
```

Tables are created automatically on first run.

## Deployment (24/7)

### Docker (recommended)
`docker compose up -d` already restarts on failure/reboot (`restart: always`). That's it.

### Systemd (bare-metal Python)
```ini
# /etc/systemd/system/workout-bot.service
[Unit]
Description=Workout Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/workout-bot
ExecStart=/path/to/venv/bin/python workout_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable --now workout-bot
```

> **Note on free cloud hosts:** Railway/Render/Replit can run the bot + Postgres easily, but they generally can't run Ollama (too much RAM / no GPU). On those, point `OLLAMA_HOST` at an Ollama instance you control (a home server). Self-hosting the whole stack with Docker is the simplest way to keep the AI local.

## Environment variables

| Variable        | Required | Default                  | Notes |
|-----------------|----------|--------------------------|-------|
| `DISCORD_TOKEN` | ✅       | —                        | From the Discord Developer Portal |
| `DATABASE_URL`  | ✅       | —                        | PostgreSQL connection string |
| `OLLAMA_HOST`   | —        | `http://localhost:11434` | Set to `http://ollama:11434` under Docker |
| `OLLAMA_MODEL`  | —        | `llama3.2`               | Any model you've pulled in Ollama |

See `.env.example` for a template.

## Customization

- **Different model** — pull another model (`ollama pull mistral`) and set `OLLAMA_MODEL`.
- **Coaching tone** — edit the `system_prompt` in `get_ai_response()` (`claude_fitness_prompt.txt` has a fuller reference version).
- **Memory depth** — change the `limit` in `get_user_context()`.
- **New commands** — copy the `@bot.slash_command` pattern.

## Troubleshooting

**Bot doesn't respond**
- Confirm `DISCORD_TOKEN` is correct and the bot was invited with `applications.commands`.
- Slash commands can take a few minutes (up to ~1 hour) to appear after first launch.

**Coaching replies say "Couldn't reach the coach"**
- The bot can't reach Ollama. Check `docker compose logs ollama`, confirm the model finished pulling (`docker compose logs ollama-pull`), and that `OLLAMA_HOST` matches where Ollama is running.

**Database connection error**
- Verify `DATABASE_URL`. Under Docker the host must be `postgres`, not `localhost`.

## Contributing

Fork it and add features — workout programs (PPL, 5/3/1), progress charts, achievement badges, group challenges, meal logging.

## License

MIT — use and modify freely.

---

Built with ❤️ for gym bros. Now go crush it! 💪
