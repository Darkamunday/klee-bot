import os
import threading
from dotenv import load_dotenv

load_dotenv()

from src.bot import client
from src.web import run as run_web

token = os.getenv("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN not set in .env")

web_thread = threading.Thread(target=run_web, daemon=True)
web_thread.start()
print("Admin UI running at http://127.0.0.1:5001")

client.run(token)
