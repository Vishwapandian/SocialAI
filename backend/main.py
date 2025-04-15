import firebase_functions
from server import app
from chat import chat_bp
from user_tracking import user_tracking_bp
from export_user_data import export_user_data_bp

# Register blueprints
app.register_blueprint(chat_bp)
app.register_blueprint(user_tracking_bp)
app.register_blueprint(export_user_data_bp)

@firebase_functions.https_fn.on_request()
def social_ai_backend(req: firebase_functions.Request) -> firebase_functions.Response:
    """HTTP Cloud Function.
    Args:
        req: The request object.
    Returns:
        The response object.
    """
    with app.request_context(req.environ):
        return app.full_dispatch_request() 