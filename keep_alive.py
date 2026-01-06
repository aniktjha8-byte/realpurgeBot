from flask import Flask
from threading import Thread
import logging

logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bunny CDN Cache Purge Bot is alive!"

@app.route('/health')
def health():
    return {"status": "healthy", "bot": "running"}

def run():
    """Run the Flask web server."""
    try:
        app.run(host='0.0.0.0', port=8080)
    except Exception as e:
        logger.error(f"Keep-alive server error: {e}")

def keep_alive():
    """Start the keep-alive web server in a separate thread."""
    t = Thread(target=run)
    t.daemon = True
    t.start()
    logger.info("Keep-alive server started on port 8080")
