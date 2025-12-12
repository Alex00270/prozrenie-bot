import os

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN not set in environment variables!")
