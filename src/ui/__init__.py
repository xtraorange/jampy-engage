"""Web UI package for the application."""
from flask import Flask
from flask import g
import os
import webbrowser
import time
import io
import sys
import threading
import socket
import json

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

    @app.before_request
    def _start_request_perf_tracking():
        g.request_started_at = time.perf_counter()
        g.db_query_timings = []
        g.db_query_total_ms = 0.0

    @app.context_processor
    def _inject_perf_footer_data():
        started_at = getattr(g, "request_started_at", None)
        request_elapsed_ms = 0.0
        if started_at is not None:
            request_elapsed_ms = (time.perf_counter() - started_at) * 1000.0

        db_queries = list(getattr(g, "db_query_timings", []))
        return {
            "perf_footer": {
                "server_request_ms": round(request_elapsed_ms, 2),
                "db_query_count": len(db_queries),
                "db_total_ms": round(float(getattr(g, "db_query_total_ms", 0.0)), 2),
                "db_queries": db_queries,
            }
        }

    @app.after_request
    def _add_perf_headers(response):
        started_at = getattr(g, "request_started_at", None)
        if started_at is not None:
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            response.headers["X-App-Request-Ms"] = f"{elapsed_ms:.2f}"

        db_queries = list(getattr(g, "db_query_timings", []))
        response.headers["X-App-Db-Query-Count"] = str(len(db_queries))
        response.headers["X-App-Db-Total-Ms"] = f"{float(getattr(g, 'db_query_total_ms', 0.0)):.2f}"
        return response

    return app


def _resolve_ui_port(base: str) -> int:
    from ..services.config_service import ConfigService
    cfg = ConfigService(base).load_general_config()
    configured = cfg.get("ui_port", 5000)
    try:
        return int(configured)
    except (TypeError, ValueError):
        return 5000


def _find_available_port(preferred_port: int, host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, preferred_port))
            return preferred_port
        except OSError:
            sock.bind((host, 0))
            return int(sock.getsockname()[1])


def run_app():
    """Run the Flask application."""
    base = os.getcwd()
    app = create_app()
    preferred_port = _resolve_ui_port(base)
    port = _find_available_port(preferred_port)
    app_url = f"http://127.0.0.1:{port}"
    runtime_dir = os.path.join(base, ".runtime")
    runtime_info_path = os.path.join(runtime_dir, "ui.json")

    try:
        os.makedirs(runtime_dir, exist_ok=True)
        with open(runtime_info_path, "w", encoding="utf-8") as runtime_file:
            json.dump({"port": port, "preferred_port": preferred_port, "url": app_url}, runtime_file)
    except OSError:
        pass

    if port != preferred_port:
        print(
            f"Configured port {preferred_port} is in use; starting on available port {port} instead."
        )

    skip_browser_flag = (
        os.environ.get("VIVA_ENGAGE_TOOLS_SKIP_BROWSER", "")
        or os.environ.get("JAMPY_SKIP_BROWSER", "")
    )
    skip_browser = str(skip_browser_flag).strip().lower() in {"1", "true", "yes"}

    # Open browser after a brief delay to let the server start.
    # For UI-triggered restarts we skip this so the existing tab can reconnect.
    if not skip_browser:
        def open_browser():
            time.sleep(1.5)
            webbrowser.open(app_url)

        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()

    # Reset one-shot skip flag for any future non-restart launches in this shell.
    os.environ["VIVA_ENGAGE_TOOLS_SKIP_BROWSER"] = ""
    os.environ["JAMPY_SKIP_BROWSER"] = ""

    # Suppress Werkzeug banner by redirecting stdout during startup
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        app.run(host="0.0.0.0", port=port, debug=False)
    finally:
        sys.stdout = old_stdout


if __name__ == "__main__":
    """Run the Flask application directly."""
    import threading
    run_app()