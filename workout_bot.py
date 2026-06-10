import os
import sys
from datetime import datetime, timedelta, date

import nextcord
from nextcord.ext import commands
from dotenv import load_dotenv
import asyncpg
from ollama import AsyncClient

load_dotenv()

# Configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

# Fail fast with a clear message if required config is missing
_missing = [
    name
    for name, value in (("DISCORD_TOKEN", DISCORD_TOKEN), ("DATABASE_URL", DATABASE_URL))
    if not value
]
if _missing:
    print(f"❌ Missing required environment variables: {', '.join(_missing)}")
    print("   Copy .env.example to .env and fill it in. See README.md.")
    sys.exit(1)

# Slash-command-only bot: no privileged message_content intent needed
intents = nextcord.Intents.default()
bot = commands.Bot(intents=intents)

# Local LLM client (Ollama)
ollama_client = AsyncClient(host=OLLAMA_HOST)


class WorkoutBot:
    """Main bot class with memory and workout tracking"""

    def __init__(self):
        self.pool = None

    async def init_db(self):
        """Initialize database connection pool and create tables"""
        self.pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            command_timeout=60,
        )

        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    goals TEXT,
                    preferences JSONB DEFAULT '{}'
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS workouts (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    exercise TEXT,
                    sets INT,
                    reps INT,
                    weight FLOAT,
                    notes TEXT,
                    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    duration_minutes INT
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_memory (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    channel_id BIGINT,
                    message_role TEXT,
                    message_content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS goals (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    goal_text TEXT,
                    target_date DATE,
                    progress_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS checkins (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    username TEXT,
                    note TEXT,
                    checkin_date DATE DEFAULT CURRENT_DATE,
                    checked_in_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (user_id, checkin_date)
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS leaderboard (
                    user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
                    total_volume FLOAT DEFAULT 0,
                    total_workouts INT DEFAULT 0,
                    streak INT DEFAULT 0,
                    last_workout DATE,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Indexes for performance
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_workouts_user_date
                ON workouts(user_id, logged_at DESC)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversation_user_channel
                ON conversation_memory(user_id, channel_id, timestamp DESC)
            """)

        print("✅ Database initialized")

    async def ensure_user(self, conn, user_id: int, username: str = None):
        """Insert the user if new, and keep their username current."""
        await conn.execute("""
            INSERT INTO users (user_id, username) VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE
                SET username = COALESCE(EXCLUDED.username, users.username)
        """, user_id, username)

    async def get_user_context(self, user_id: int, channel_id: int, limit: int = 10) -> str:
        """Retrieve recent conversation memory and user context"""
        async with self.pool.acquire() as conn:
            messages = await conn.fetch("""
                SELECT message_role, message_content, timestamp
                FROM conversation_memory
                WHERE user_id = $1 AND channel_id = $2
                ORDER BY timestamp DESC
                LIMIT $3
            """, user_id, channel_id, limit)

            workouts = await conn.fetch("""
                SELECT exercise, sets, reps, weight, notes, logged_at
                FROM workouts
                WHERE user_id = $1
                ORDER BY logged_at DESC
                LIMIT 5
            """, user_id)

            goals = await conn.fetch("""
                SELECT goal_text, target_date, progress_notes
                FROM goals
                WHERE user_id = $1 AND target_date >= CURRENT_DATE
                ORDER BY target_date
                LIMIT 3
            """, user_id)

            context = "=== USER CONTEXT ===\n"

            if messages:
                context += "\nRecent Conversation:\n"
                for msg in reversed(messages):
                    context += f"[{msg['timestamp'].strftime('%H:%M')}] {msg['message_role']}: {msg['message_content']}\n"

            if workouts:
                context += "\nRecent Workouts:\n"
                for w in workouts:
                    context += f"- {w['exercise']}: {w['sets']}x{w['reps']} @ {w['weight']}lbs ({w['logged_at'].strftime('%m/%d')})\n"

            if goals:
                context += "\nActive Goals:\n"
                for g in goals:
                    context += f"- {g['goal_text']} (by {g['target_date'].strftime('%m/%d')})\n"

            return context

    async def store_message(self, user_id: int, channel_id: int, role: str, content: str):
        """Store conversation message in memory"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO conversation_memory (user_id, channel_id, message_role, message_content)
                VALUES ($1, $2, $3, $4)
            """, user_id, channel_id, role, content)

    async def add_checkin(self, user_id: int, username: str, note: str = None) -> dict:
        """Record that a user checked in for their workout (once per day)."""
        async with self.pool.acquire() as conn:
            await self.ensure_user(conn, user_id, username)

            # One check-in per person per day; update the note if they re-check-in
            row = await conn.fetchrow("""
                INSERT INTO checkins (user_id, username, note, checkin_date)
                VALUES ($1, $2, $3, CURRENT_DATE)
                ON CONFLICT (user_id, checkin_date) DO UPDATE
                    SET note = COALESCE(EXCLUDED.note, checkins.note),
                        checked_in_at = CURRENT_TIMESTAMP
                RETURNING (xmax = 0) AS is_new
            """, user_id, username, note)

            total_today = await conn.fetchval(
                "SELECT COUNT(*) FROM checkins WHERE checkin_date = CURRENT_DATE"
            )
            return {"is_new": row["is_new"], "total_today": total_today}

    async def get_todays_checkins(self):
        """Return everyone who has checked in today, earliest first."""
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT user_id, username, note, checked_in_at
                FROM checkins
                WHERE checkin_date = CURRENT_DATE
                ORDER BY checked_in_at ASC
            """)

    async def generate_workout_plan(self, user_id: int, channel_id: int, focus: str) -> str:
        """Ask the local model to build a workout routine for a given focus area."""
        context = await self.get_user_context(user_id, channel_id, limit=10)

        system_prompt = f"""You are a knowledgeable strength coach for a Discord server of gym buddies.
Generate a single, ready-to-do workout session focused on: {focus}.

{context}

Rules for the workout you write:
- Tailor it to the user's recent history and goals above when relevant (progress their weights, avoid overtraining a muscle they just hit).
- Give 5-7 exercises. For each: name, sets x reps, and a short cue or target weight note.
- Include a quick warmup line and a finisher/optional line.
- Keep it scannable with one exercise per line. Use light emoji for energy.
- No long intros. Under 1500 characters total. End with one motivating sentence."""

        user_message = f"Give me a {focus} workout for today."

        try:
            result = await ollama_client.chat(
                model=OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                options={"num_predict": 700},
            )
            plan = result["message"]["content"].strip()
            if len(plan) > 4000:
                plan = plan[:3997] + "..."

            # Remember that we suggested this, so follow-up advice has context
            await self.store_message(user_id, channel_id, "assistant", f"[{focus} workout plan]\n{plan}")
            return plan
        except Exception as e:
            print(f"Error generating workout plan: {e}")
            return "Couldn't reach the coach to build a plan right now. Try again in a sec! 💪"

    async def log_workout(self, user_id: int, username: str, exercise: str, sets: int,
                          reps: int, weight: float, notes: str = None, duration: int = None) -> dict:
        """Log a workout to the database and update the leaderboard/streak"""
        async with self.pool.acquire() as conn:
            await self.ensure_user(conn, user_id, username)

            workout = await conn.fetchrow("""
                INSERT INTO workouts (user_id, exercise, sets, reps, weight, notes, duration_minutes)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id, logged_at
            """, user_id, exercise, sets, reps, weight, notes, duration)

            volume = sets * reps * weight

            # Compute streak based on the previous logged day
            existing = await conn.fetchrow(
                "SELECT streak, last_workout FROM leaderboard WHERE user_id = $1", user_id
            )
            today = date.today()
            if existing and existing["last_workout"]:
                last = existing["last_workout"]
                if last == today:
                    streak = existing["streak"]  # already worked out today
                elif last == today - timedelta(days=1):
                    streak = existing["streak"] + 1
                else:
                    streak = 1
            else:
                streak = 1

            await conn.execute("""
                INSERT INTO leaderboard (user_id, total_volume, total_workouts, streak, last_workout)
                VALUES ($1, $2, 1, $3, CURRENT_DATE)
                ON CONFLICT (user_id) DO UPDATE SET
                    total_volume = leaderboard.total_volume + $2,
                    total_workouts = leaderboard.total_workouts + 1,
                    streak = $3,
                    last_workout = CURRENT_DATE,
                    updated_at = CURRENT_TIMESTAMP
            """, user_id, volume, streak)

            return {
                "id": workout["id"],
                "exercise": exercise,
                "sets": sets,
                "reps": reps,
                "weight": weight,
                "volume": volume,
                "streak": streak,
                "logged_at": workout["logged_at"],
            }


workout_bot = WorkoutBot()
_db_ready = False


@bot.event
async def on_ready():
    """Initialize the database once, on first ready (not on every reconnect)."""
    global _db_ready
    if not _db_ready:
        await workout_bot.init_db()
        _db_ready = True
    print(f"✅ Logged in as {bot.user}")


@bot.slash_command(description="Log a workout")
async def log_workout(
    interaction: nextcord.Interaction,
    exercise: str = nextcord.SlashOption(description="Exercise name (e.g., Bench Press)"),
    sets: int = nextcord.SlashOption(description="Number of sets", min_value=1),
    reps: int = nextcord.SlashOption(description="Reps per set", min_value=1),
    weight: float = nextcord.SlashOption(description="Weight in lbs", min_value=0),
    notes: str = nextcord.SlashOption(description="Optional notes", required=False),
    duration: int = nextcord.SlashOption(description="Duration in minutes", required=False),
):
    """Log a workout with context awareness"""
    await interaction.response.defer()

    try:
        workout = await workout_bot.log_workout(
            interaction.user.id,
            interaction.user.name,
            exercise,
            sets,
            reps,
            weight,
            notes,
            duration,
        )

        # Logging stays fast and quiet — no AI paragraph here. Ask for a routine
        # explicitly with /workout when you want one.
        embed = nextcord.Embed(
            title="💪 Workout Logged!",
            color=nextcord.Color.green(),
            timestamp=workout["logged_at"],
        )
        embed.add_field(name="Exercise", value=exercise, inline=True)
        embed.add_field(name="Sets x Reps", value=f"{sets}x{reps}", inline=True)
        embed.add_field(name="Weight", value=f"{weight}lbs", inline=True)
        embed.add_field(name="Volume", value=f"{workout['volume']:.0f}lbs", inline=True)
        embed.add_field(name="Streak", value=f"🔥 {workout['streak']} days", inline=True)

        if notes:
            embed.add_field(name="Notes", value=notes, inline=False)

        embed.set_footer(text=f"Logged by {interaction.user.name}")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Error logging workout: {e}")
        await interaction.followup.send("❌ Something went wrong logging that workout. Try again in a sec.")


@bot.slash_command(description="Get an AI-generated workout for a body part or split")
async def workout(
    interaction: nextcord.Interaction,
    focus: str = nextcord.SlashOption(
        description="What are we training?",
        choices={
            "Legs": "legs",
            "Arms": "arms",
            "Chest": "chest",
            "Back": "back",
            "Shoulders": "shoulders",
            "Core / Abs": "core",
            "Push": "push (chest, shoulders, triceps)",
            "Pull": "pull (back, biceps)",
            "Full Body": "full body",
            "Cardio / Conditioning": "cardio and conditioning",
        },
    ),
):
    """Generate a workout routine for the chosen focus using the local AI."""
    await interaction.response.defer()

    try:
        async with workout_bot.pool.acquire() as conn:
            await workout_bot.ensure_user(conn, interaction.user.id, interaction.user.name)

        plan = await workout_bot.generate_workout_plan(
            interaction.user.id,
            interaction.channel_id,
            focus,
        )

        embed = nextcord.Embed(
            title=f"🏋️ {focus.split('(')[0].strip().title()} Workout",
            description=plan,
            color=nextcord.Color.teal(),
        )
        embed.set_footer(text=f"Built for {interaction.user.name}")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Error building workout: {e}")
        await interaction.followup.send("❌ Couldn't build a workout right now. Try again in a sec.")


@bot.slash_command(description="Check in for your workout so the crew sees you showed up")
async def checkin(
    interaction: nextcord.Interaction,
    note: str = nextcord.SlashOption(description="Optional: what are you training today?", required=False),
):
    """Mark that you checked in today and show who else has."""
    await interaction.response.defer()

    try:
        result = await workout_bot.add_checkin(
            interaction.user.id,
            interaction.user.name,
            note,
        )
        checkins = await workout_bot.get_todays_checkins()

        if result["is_new"]:
            title = "✅ Checked In!"
            desc = f"<@{interaction.user.id}> is in for today. 💪"
        else:
            title = "🔁 Already Checked In"
            desc = f"<@{interaction.user.id}>, you're already counted for today."

        roster = "\n".join([
            f"• <@{c['user_id']}>"
            + (f" — {c['note']}" if c["note"] else "")
            + f"  _( {c['checked_in_at'].strftime('%I:%M %p').lstrip('0')} )_"
            for c in checkins
        ])

        embed = nextcord.Embed(
            title=title,
            description=desc,
            color=nextcord.Color.green(),
        )
        embed.add_field(
            name=f"🏋️ Checked in today ({result['total_today']})",
            value=roster or "Nobody yet — be the first!",
            inline=False,
        )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Error on checkin: {e}")
        await interaction.followup.send("❌ Couldn't record your check-in right now. Try again in a sec.")


@bot.slash_command(description="View your workout stats")
async def stats(interaction: nextcord.Interaction):
    """Display personal workout statistics"""
    await interaction.response.defer()

    try:
        async with workout_bot.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT total_volume, total_workouts, streak, last_workout
                FROM leaderboard
                WHERE user_id = $1
            """, interaction.user.id)

            if not row:
                await interaction.followup.send("No workouts logged yet! Start with `/log_workout` 💪")
                return

            recent = await conn.fetch("""
                SELECT exercise, weight, sets, reps, logged_at
                FROM workouts
                WHERE user_id = $1
                ORDER BY logged_at DESC
                LIMIT 10
            """, interaction.user.id)

            embed = nextcord.Embed(
                title=f"📊 {interaction.user.name}'s Stats",
                color=nextcord.Color.gold(),
            )
            embed.add_field(name="Total Workouts", value=row["total_workouts"], inline=True)
            embed.add_field(name="Total Volume", value=f"{row['total_volume']:.0f} lbs", inline=True)
            embed.add_field(name="Current Streak", value=f"🔥 {row['streak']} days", inline=True)

            if recent:
                recent_text = "\n".join([
                    f"• {w['exercise']} - {w['sets']}x{w['reps']} @ {w['weight']}lbs"
                    for w in recent[:5]
                ])
                embed.add_field(name="Recent Workouts", value=recent_text, inline=False)

            await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Error getting stats: {e}")
        await interaction.followup.send("❌ Couldn't load your stats right now.")


@bot.slash_command(description="View the leaderboard")
async def leaderboard(interaction: nextcord.Interaction):
    """Display server leaderboard"""
    await interaction.response.defer()

    try:
        async with workout_bot.pool.acquire() as conn:
            volume_board = await conn.fetch("""
                SELECT lb.user_id, lb.total_volume, lb.total_workouts
                FROM leaderboard lb
                ORDER BY lb.total_volume DESC
                LIMIT 10
            """)

            volume_text = ""
            for i, row in enumerate(volume_board, 1):
                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
                volume_text += f"{medal} <@{row['user_id']}> - {row['total_volume']:.0f} lbs ({row['total_workouts']} workouts)\n"

            embed = nextcord.Embed(
                title="🏆 Leaderboard",
                color=nextcord.Color.gold(),
            )
            embed.add_field(name="💪 Total Volume", value=volume_text or "No data yet", inline=False)

            await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Error getting leaderboard: {e}")
        await interaction.followup.send("❌ Couldn't load the leaderboard right now.")


@bot.slash_command(description="Set a fitness goal")
async def set_goal(
    interaction: nextcord.Interaction,
    goal: str = nextcord.SlashOption(description="Your fitness goal"),
    days: int = nextcord.SlashOption(description="Days until goal target", min_value=1, max_value=365),
):
    """Set a fitness goal with memory"""
    await interaction.response.defer()

    try:
        async with workout_bot.pool.acquire() as conn:
            await workout_bot.ensure_user(conn, interaction.user.id, interaction.user.name)

            target_date = datetime.now() + timedelta(days=days)

            await conn.execute("""
                INSERT INTO goals (user_id, goal_text, target_date)
                VALUES ($1, $2, $3)
            """, interaction.user.id, goal, target_date.date())

        await workout_bot.store_message(
            interaction.user.id,
            interaction.channel_id,
            "system",
            f"Set goal: {goal} (target: {target_date.strftime('%m/%d/%Y')})",
        )

        embed = nextcord.Embed(
            title="🎯 Goal Set!",
            description=f"**{goal}**\n\nTarget: {target_date.strftime('%B %d, %Y')} ({days} days)",
            color=nextcord.Color.purple(),
        )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Error setting goal: {e}")
        await interaction.followup.send("❌ Couldn't set that goal right now.")


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
