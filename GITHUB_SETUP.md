# GitHub Setup Guide

Get your workout bot on GitHub so your friends can clone and host it.

## Step 1: Create GitHub Repository

1. Go to [github.com](https://github.com) and log in
2. Click **+** in top right → **New repository**
3. Name it: `workout-bot` (or whatever you want)
4. Description: "Discord bot for tracking workouts with conversation memory"
5. Choose **Public** (so friends can clone it)
6. Click **Create repository** (DON'T initialize with README - we have one)

You'll get a page with commands. Use these:

## Step 2: Initialize Local Repository

```bash
cd workout-bot

# Initialize git
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: Workout bot with memory system"

# Add GitHub remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/workout-bot.git

# Push to GitHub
git branch -M main
git push -u origin main
```

Done! Your repo is on GitHub.

## Step 3: Share with Friends

Send them this link:
```
https://github.com/YOUR_USERNAME/workout-bot
```

They can then:
```bash
git clone https://github.com/YOUR_USERNAME/workout-bot.git
cd workout-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with their Discord token and database URL
python workout_bot.py
```

## Step 4: Deploy to Railway (Easiest for Friends)

1. Go to [railway.app](https://railway.app)
2. Sign in with GitHub
3. Click "New Project" → "Deploy from GitHub repo"
4. Select `YOUR_USERNAME/workout-bot`
5. Railway auto-detects it's a Python app
6. Add environment variables:
   - `DISCORD_TOKEN` = their Discord bot token
   - `DATABASE_URL` = their PostgreSQL connection (Railway can provide one)
7. Deploy!

Friend's bot will be running 24/7 for free (Railway free tier).

## Step 5: Using Docker-Compose (Local Testing)

For friends who want to run it locally with Docker:

```bash
git clone https://github.com/YOUR_USERNAME/workout-bot.git
cd workout-bot

# Create .env file
cp .env.example .env
# Edit .env with just DISCORD_TOKEN (database will auto-configure)

# Run with Docker Compose (includes PostgreSQL)
docker-compose up -d

# Bot will start + database will initialize automatically
```

To stop:
```bash
docker-compose down
```

## Making Updates

When you fix bugs or add features:

```bash
# Make your changes, then:
git add .
git commit -m "Add feature: [what you added]"
git push origin main
```

Friends can update their clones:
```bash
cd workout-bot
git pull origin main
```

## GitHub Tips

### Add a .github/workflows folder for CI/CD (Optional)

This automatically tests code when you push:

```bash
mkdir -p .github/workflows
cat > .github/workflows/test.yml << 'EOF'
name: Python Lint

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Lint with flake8
        run: |
          pip install flake8
          flake8 workout_bot.py --count --select=E9,F63,F7,F82 --show-source --statistics
EOF

git add .github/
git commit -m "Add GitHub Actions CI"
git push origin main
```

### Create Releases (Optional)

When you have a stable version:

1. Go to GitHub repo
2. Click "Releases" on the right
3. Click "Create a new release"
4. Tag: `v1.0.0`
5. Title: "Version 1.0 - Initial Release"
6. Description: List features/fixes
7. Publish

Friends can easily see what changed.

## Full Checklist

- [ ] Create GitHub repo (public)
- [ ] Push all files to GitHub
- [ ] Test that `.env.example` works
- [ ] Verify `.gitignore` is in place
- [ ] Check README renders correctly on GitHub
- [ ] Share link with friends: `https://github.com/YOUR_USERNAME/workout-bot`
- [ ] Friend clones and tests locally
- [ ] Friend deploys to Railway or Docker

## What Friends Will See on GitHub

```
workout-bot/
├── README.md                    (shows first on GitHub)
├── workout_bot.py              (main bot code)
├── requirements.txt            (dependencies)
├── .env.example               (config template)
├── Dockerfile                 (for containerization)
├── docker-compose.yml         (run locally with database)
├── .gitignore                 (keeps secrets safe)
└── claude_fitness_prompt.txt  (the system prompt)
```

They'll see:
- Your README as the main landing page
- Green "Code" button to clone
- Instructions to get started

## Troubleshooting GitHub

**"fatal: not a git repository"**
```bash
cd workout-bot
git init
```

**"fatal: remote origin already exists"**
```bash
git remote remove origin
git remote add origin https://github.com/YOUR_USERNAME/workout-bot.git
```

**Want to make bot private later?**
- Go to repo settings → "Danger Zone" → Change to private
- Friends can still access if given permission

**Friends forked it and want to contribute?**
- They make changes in their fork
- Submit pull request
- You review and merge

---

**You're all set!** Your bot is on GitHub and ready for your crew to deploy. 🚀
