import os
from threading import Thread
from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
    return "Culling Game Master is running."


def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    thread = Thread(target=run_web_server)
    thread.daemon = True
    thread.start()