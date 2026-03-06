"""Web UI package for the application."""
from flask import Flask
import os
import webbrowser
import time
import io
import sys
import threading

from .utils import setup_flask_app, load_version_info
from .routes.main import init_main_routes
from .routes.groups import init_groups_routes
from .routes.tags import init_tags_routes
from .routes.api import init_api_routes
from .routes.updates import init_updates_routes


def create_app():
    """Create and configure the Flask application."""
    base = os.getcwd()

    # Set up Flask app
    app = setup_flask_app(base)

    # Load version info
    __version__, GITHUB_REPO = load_version_info(base)

    # Initialize all route blueprints
    main_bp = init_main_routes(app, base)
    groups_bp = init_groups_routes(app, base)
    tags_bp = init_tags_routes(app, base)
    api_bp = init_api_routes(app, base)
    updates_bp = init_updates_routes(app, base)

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(tags_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(updates_bp)

    return app


def run_app():
    """Run the Flask application."""
    app = create_app()

    # Open browser after a brief delay to let the server start
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://localhost:5000")

    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    # Suppress Werkzeug banner by redirecting stdout during startup
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        app.run(host="0.0.0.0", port=5000, debug=False)
    finally:
        sys.stdout = old_stdout


if __name__ == "__main__":
    """Run the Flask application directly."""
    import threading
    run_app()