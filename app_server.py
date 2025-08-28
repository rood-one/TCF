import os
from flask import Flask

app = Flask(__name__)

@app.get("/")
def root():
    return {"ok": True, "service": "tg-compressor-bot", "status": "running"}


def run_flask():
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)