FROM python:3.11-slim

WORKDIR /app

# asyncpg and ollama ship prebuilt wheels, so no system build deps are needed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY workout_bot.py .

# Create logs directory
RUN mkdir -p logs

# Run the bot
CMD ["python", "workout_bot.py"]
