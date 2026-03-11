"""Main routes for the web interface."""
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
import os
import threading
import time

from ...services.config_service import ConfigService
from ...services.group_service import GroupService
from ...services.report_service import ReportService
from ...services.stats_service import StatsService
from ...generate_reports import discover_groups

def init_main_routes(app, base_path: str):
    """Initialize main routes with dependencies."""
    main_bp = Blueprint('main', __name__)
    config_service = ConfigService(base_path)
    group_service = GroupService(base_path)
    stats_service = StatsService(base_path)

    @main_bp.route("/")
    def index():
        """Main dashboard showing analytics and statistics."""
        groups = group_service.discover_groups()
        cfg = config_service.load_general_config()
        stats_service.record_available_reports(len(groups))
        metrics = stats_service.dashboard_metrics()

        group_meta = [
            {
                "handle": g.handle,
                "tags": sorted(list(g.tags)) if g.tags else [],
            }
            for g in groups
        ]

        return render_template("generate.html", config=cfg, metrics=metrics, group_meta=group_meta,
                               updating=app.config.get("updating"),
                               update_error=app.config.get("update_error"))

    @main_bp.route("/generate", methods=["GET", "POST"])
    def generate():
        """Report generation form and submission handler."""
        if request.method == "POST":
            # Handle form submission
            if app.config.get("updating"):
                return "Update in progress, please wait and refresh after restart", 503

            groups = group_service.discover_groups()
            cfg = config_service.load_general_config()

            selected_handles = request.form.getlist("groups")
            selected = [g for g in groups if g.handle in selected_handles]

            tag_sel = request.form.getlist("tags")
            for t in tag_sel:
                for g in groups:
                    if t in g.tags and g not in selected:
                        selected.append(g)

            should_email = request.form.get("email") == "on"
            override = request.form.get("override_email") or None
            stats_service.record_run_started(
                selected_groups=selected,
                should_email=should_email,
                override_email=override,
                default_recipient=cfg.get("email_recipient"),
            )

            # Start processing in background
            tracker = start_jobs(app, selected, should_email, override)
            app.config["tracker"] = tracker

            return redirect(url_for("main.status"))
        
        # Handle GET - show form
        groups = group_service.discover_groups()
        cfg = config_service.load_general_config()

        # Get all tags for the UI, with per-tag group counts
        tag_counts = {}
        for g in groups:
            for tag in g.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        tags = sorted(tag_counts.keys())

        return render_template("report_generate.html", config=cfg, groups=groups, tags=tags, tag_counts=tag_counts,
                               updating=app.config.get("updating"),
                               update_error=app.config.get("update_error"))

    @main_bp.route("/status")
    def status():
        """Show processing status."""
        tracker = app.config.get("tracker")
        if not tracker:
            return redirect(url_for("main.index"))

        return render_template("status.html", tracker=tracker)

    @main_bp.route("/api/status")
    def api_status():
        """API endpoint for status polling."""
        tracker = app.config.get("tracker")
        if not tracker:
            return jsonify(error="No job running")

        return jsonify(status=tracker.status, done=tracker.done, total=tracker.total)

    @main_bp.route("/settings", methods=["GET", "POST"])
    def settings():
        """Settings page."""
        cfg = config_service.load_general_config()
        metrics = stats_service.dashboard_metrics()

        if request.method == "POST":
            if request.form.get("reset_stats") == "1":
                stats_service.reset_stats()
                return redirect(url_for("main.settings"))

            # Update general config based on form fields
            for key in [
                "oracle_tns",
                "ui_port",
                "output_dir",
                "max_workers",
                "email_method",
                "outlook_auto_send",
                "smtp_server",
                "smtp_port",
                "smtp_use_tls",
                "smtp_from",
                "email_recipient",
            ]:
                if key in request.form:
                    val = request.form.get(key)
                    if val == "":
                        cfg.pop(key, None)
                    else:
                        if key in ["ui_port", "max_workers", "smtp_port"]:
                            try:
                                cfg[key] = int(val)
                            except ValueError:
                                cfg[key] = val
                        elif key in ["smtp_use_tls", "outlook_auto_send"]:
                            cfg[key] = request.form.get(key) == "on"
                        else:
                            cfg[key] = val

            config_service.save_general_config(cfg)
            return redirect(url_for("main.settings"))

        groups = group_service.discover_groups()
        return render_template("settings.html", config=cfg, groups=groups, metrics=metrics,
                               updating=app.config.get("updating"),
                               update_error=app.config.get("update_error"))

    @main_bp.route("/api/dashboard-stats")
    def dashboard_stats():
        """Return dashboard metrics for chart rendering."""
        return jsonify(stats_service.dashboard_metrics())

    return main_bp


def start_jobs(app, selected, should_email, override_email):
    """Start background job processing."""
    from ...services.config_service import ConfigService
    from ...services.report_service import ReportService

    base = os.getcwd()
    config_service = ConfigService(base)
    cfg = config_service.load_general_config()
    report_service = ReportService(cfg)
    stats_service = StatsService(base)

    # create tracker that will be visible to the UI
    from ...db import ProgressTracker
    tracker = ProgressTracker(len(selected))

    def task():
        started = time.perf_counter()
        # pass the tracker so it gets updated during processing
        generated = report_service.process_groups(
            selected,
            should_email,
            override_email,
            tracker=tracker,
        )
        stats_service.record_run_completed(
            selected_handles=[g.handle for g in selected],
            generated_files=generated,
            duration_seconds=time.perf_counter() - started,
        )
        # Processing complete - tracker will be cleaned up by the UI

    threading.Thread(target=task, daemon=True).start()

    # Return the tracker for status monitoring
    return tracker