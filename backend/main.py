"""
Entry point for Cloud Functions (2nd gen) that simply forwards every
request to the Flask app defined in server.py.
"""

from firebase_functions import https_fn          # ✅  import the sub‑module
from server import app                           #  your existing Flask app

@https_fn.on_request()                           # decorator from the sub‑module
def social_ai_backend(req: https_fn.Request) -> https_fn.Response:
    """HTTP wrapper around the Flask app."""
    # Re‑use Flask’s request machinery so blueprints etc. keep working.
    with app.request_context(req.environ):
        return app.full_dispatch_request()       # already a Flask Response
