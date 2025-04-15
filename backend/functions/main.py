# Welcome to Cloud Functions for Firebase for Python!
# To get started, simply uncomment the below code or create your own.
# Deploy with `firebase deploy`

from firebase_functions import https_fn
from server import app

@https_fn.on_request()
def social_ai_backend(req: https_fn.Request) -> https_fn.Response:
    """HTTP Cloud Function that serves as the main entry point for the SocialAI backend.
    Args:
        req: The request object.
    Returns:
        The response object.
    """
    with app.request_context(req.environ):
        return app.full_dispatch_request()

#
#
# @https_fn.on_request()
# def on_request_example(req: https_fn.Request) -> https_fn.Response:
#     return https_fn.Response("Hello world!")