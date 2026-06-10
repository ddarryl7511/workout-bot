# 🏋️ Workout Bot - START HERE

Everything you need is in this folder.

## What You Have

```
workout-bot/
├── START_HERE.md              ← You are here
├── README.md                  ← Main documentation
├── GITHUB_SETUP.md            ← How to push to GitHub
├── workout_bot.py             ← Your bot (main file)
├── requirements.txt           ← Dependencies
├── .env.example               ← Config template
├── .gitignore                 ← Git settings (keeps secrets safe)
├── Dockerfile                 ← For Docker deployment
├── docker-compose.yml         ← Local development with database
└── claude_fitness_prompt.txt  ← System prompt reference
```

## Quick Start (Choose One)

### Option 1: Run with Docker (recommended)

```bash
cp .env.example .env
# Edit .env with just DISCORD_TOKEN (database + Ollama auto-configure)

docker compose up -d
```

Done! Database, Ollama, and bot run together. First launch pulls the
llama3.2 model (~2 GB), so give it a few minutes (`docker compose logs -f`).

### Option 2: Run Locally (Python)

```bash
# Install Ollama (https://ollama.com/download) and pull the model
ollama pull llama3.2

# Setup
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate     # Windows

pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env and set:
#   - DISCORD_TOKEN (from Discord Developer Portal)
#   - DATABASE_URL (PostgreSQL connection string)
#   - OLLAMA_HOST=http://localhost:11434

# Run
python workout_bot.py
```

### Option 3: Deploy to GitHub + Railway (for friends)

1. Follow `GITHUB_SETUP.md`
2. Push to GitHub
3. Friends deploy to Railway (free, 24/7)

## Get Your Keys

Before running, you need:

1. **Discord Token**
   - https://discord.com/developers/applications
   - Create app → Add Bot → Copy token

2. **Database URL** (only if NOT using Docker — Docker provides its own)
   - Local PostgreSQL: `postgresql://user:password@localhost:5432/dbname`
   - Neon (free): https://neon.tech
   - Railway (free): https://railway.app

3. **Ollama** (powers the AI coaching — runs locally, no API key)
   - Docker: included automatically, nothing to do
   - Local: install from https://ollama.com/download, then `ollama pull llama3.2`

## Commands

```
/log_workout exercise:Bench Press sets:4 reps:8 weight:225
  → Logs your workout (instant, no AI chatter)

/workout focus:Legs
  → AI builds a routine for that body part / split

/checkin
  → Mark you showed up; see who else checked in today

/stats
  → View your progress

/leaderboard
  → See server rankings

/set_goal goal:Bench 315 lbs days:90
  → Set a goal (bot remembers it)
```

## Next Steps

1. **Read `README.md`** for full documentation
2. **Read `GITHUB_SETUP.md`** when ready to share with friends
3. **Check `claude_fitness_prompt.txt`** to tweak the coaching tone

## Troubleshooting

**Bot not starting?**
- Check `.env` file exists and has correct tokens
- Verify PostgreSQL is running
- Check Python version: `python3 --version` (need 3.8+)

**Commands not appearing?**
- Invite bot with correct permissions
- May take 1 hour for slash commands to sync

**Database errors?**
- Verify `DATABASE_URL` format
- Test connection with `psql` command

See `README.md` for more help.

## File Sizes

- `workout_bot.py` - 20KB (main bot code)
- `requirements.txt` - 4 lines (4 dependencies)
- `README.md` - Full docs
- `GITHUB_SETUP.md` - GitHub instructions

That's it. You're ready! 💪
