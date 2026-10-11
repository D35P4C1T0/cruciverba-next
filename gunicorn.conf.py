"""One worker with threaded requests and in-memory rate limiting."""

import os

from dotenv import load_dotenv

load_dotenv()

bind = "0.0.0.0:5000"
workers = 1
threads = int(os.getenv("GUNICORN_THREADS", "4"))
timeout = 30
graceful_timeout = 30
worker_tmp_dir = "/tmp"
control_socket_disable = True
accesslog = "-"
errorlog = "-"
preload_app = True


def on_starting(server):
    # Inspect final settings, including overrides through GUNICORN_CMD_ARGS.
    if server.cfg.workers != 1:
        raise RuntimeError(
            "Il rate limiting in memoria richiede un solo worker Gunicorn"
        )
