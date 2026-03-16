"""Group management routes."""
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
import json
import os

from ...services.group_service import GroupService
from ...utils.validation import validate_group_handle
from ...utils.file_utils import safe_delete_directory

def init_groups_routes(app, base_path: str):
    """Initialize group routes with dependencies."""
    groups_bp = Blueprint('groups', __name__)
    group_service = GroupService(base_path)

    @groups_bp.route("/groups")
    def groups():
        """List all groups."""
        groups = group_service.discover_groups()
        all_tags = group_service.get_all_tags()
        return render_template("groups.html", groups=groups, all_tags=all_tags)

    @groups_bp.route("/group/<handle>", methods=["GET", "POST"])
    def edit_group(handle):
        """Edit a group."""
        group = group_service.get_group(handle)
        all_tags = group_service.get_all_tags()
        if group is None:
            return "Group not found", 404

        def _build_cfg():
            cfg = group.config.copy()
            cfg["tags_str"] = ",".join(cfg.get("tags", []))
            cfg["has_override_query"] = group.has_override_query()
            cfg["override_query"] = group.read_override_query() if cfg["has_override_query"] else ""
            cfg["query_builder"] = cfg.get("query_builder")
            cfg["query_builder_json"] = json.dumps(cfg.get("query_builder") or {})
            cfg["query_mode"] = cfg.get("query_mode") or ("manual" if cfg["has_override_query"] else "builder")
            return cfg

        def _copy_source_groups():
            sources = []
            for candidate in group_service.discover_groups():
                if candidate.handle == group.handle:
                    continue
                sources.append({
                    "handle": candidate.handle,
                    "display_name": candidate.display_name or candidate.handle,
                })
            sources.sort(key=lambda item: (item.get("display_name") or item.get("handle") or "").lower())
            return sources

        if request.method == "POST":
            is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
            save_scope = request.form.get("save_scope", "all").strip().lower()

            # Update group configuration
            display_name = request.form.get("display_name", "").strip()
            tags_str = request.form.get("tags", "").strip()
            email_recipient = request.form.get("email_recipient", "").strip()
            output_dir = request.form.get("output_dir", "").strip()
            query = request.form.get("query", "").strip()
            query_builder_raw = request.form.get("query_builder_json", "").strip()
            query_mode = request.form.get("query_mode", "").strip()

            query_builder = None
            if query_builder_raw:
                try:
                    query_builder = json.loads(query_builder_raw)
                except json.JSONDecodeError:
                    query_builder = None

            if save_scope == "query_mode":
                group_service.update_group(group=group, query_mode=query_mode)
                group = group_service.get_group(handle)
                cfg = _build_cfg()
                return jsonify(ok=True, config=cfg)

            if save_scope == "settings":
                tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                group_service.update_group(
                    group=group,
                    display_name=display_name,
                    tags=tags,
                    email_recipient=email_recipient or None,
                    output_dir=output_dir or None,
                    query_mode=query_mode,
                )
            elif save_scope == "query":
                if not query and not query_builder:
                    if is_ajax:
                        return jsonify(ok=False, error="Save either Query Builder parameters or an override SQL script."), 400
                    cfg = _build_cfg()
                    return render_template("group.html", group=group, config=cfg, error="Save either Query Builder parameters or an override SQL script.", all_tags=all_tags, copy_source_groups=_copy_source_groups(), edit_mode=True)
                group_service.update_group(
                    group=group,
                    query=query,
                    query_builder=query_builder,
                    query_mode=query_mode,
                )
            else:
                if not query and not query_builder:
                    if is_ajax:
                        return jsonify(ok=False, error="Save either Query Builder parameters or an override SQL script."), 400
                    cfg = _build_cfg()
                    return render_template("group.html", group=group, config=cfg, error="Save either Query Builder parameters or an override SQL script.", all_tags=all_tags, copy_source_groups=_copy_source_groups(), edit_mode=True)
                tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                group_service.update_group(
                    group=group,
                    display_name=display_name,
                    tags=tags,
                    query=query,
                    query_builder=query_builder,
                    email_recipient=email_recipient or None,
                    output_dir=output_dir or None,
                    query_mode=query_mode,
                )

            group = group_service.get_group(handle)
            cfg = _build_cfg()
            if is_ajax:
                return jsonify(ok=True, config=cfg)
            return render_template("group.html", group=group, config=cfg, all_tags=all_tags, copy_source_groups=_copy_source_groups(), edit_mode=False)

        # Prepare data for template
        cfg = _build_cfg()

        return render_template("group.html", group=group, config=cfg, all_tags=all_tags, copy_source_groups=_copy_source_groups(), edit_mode=False)

    @groups_bp.route("/group/<handle>/query-config-preview", methods=["GET"])
    def query_config_preview(handle):
        """Return active query configuration for a source group preview."""
        target = group_service.get_group(handle)
        if target is None:
            return jsonify(ok=False, error="Target group not found."), 404

        source_handle = request.args.get("source_handle", "").strip()
        source = group_service.get_group(source_handle)
        if source is None:
            return jsonify(ok=False, error="Source group not found."), 404
        if source.handle == target.handle:
            return jsonify(ok=False, error="Choose a different source group."), 400

        has_override = source.has_override_query()
        source_mode = source.config.get("query_mode")
        if source_mode not in {"manual", "builder"}:
            source_mode = "manual" if has_override else "builder"

        payload = {
            "ok": True,
            "source_handle": source.handle,
            "source_display_name": source.display_name or source.handle,
            "query_mode": source_mode,
            "query_builder": source.config.get("query_builder") or {},
            "override_query": source.read_override_query() if has_override else "",
        }
        return jsonify(payload)

    @groups_bp.route("/group/<handle>/copy-query-config", methods=["POST"])
    def copy_query_configuration(handle):
        """Copy only active query configuration from another group."""
        target = group_service.get_group(handle)
        if target is None:
            return jsonify(ok=False, error="Target group not found."), 404

        source_handle = request.form.get("source_handle", "").strip()
        source = group_service.get_group(source_handle)
        if source is None:
            return jsonify(ok=False, error="Source group not found."), 404
        if source.handle == target.handle:
            return jsonify(ok=False, error="Choose a different source group."), 400

        has_override = source.has_override_query()
        source_mode = source.config.get("query_mode")
        if source_mode not in {"manual", "builder"}:
            source_mode = "manual" if has_override else "builder"

        if source_mode == "manual":
            group_service.update_group(
                group=target,
                query=source.read_override_query(),
                query_mode="manual",
            )
        else:
            group_service.update_group(
                group=target,
                query_builder=source.config.get("query_builder") or {},
                query_mode="builder",
            )

        updated = group_service.get_group(handle)
        cfg = updated.config.copy()
        cfg["tags_str"] = ",".join(cfg.get("tags", []))
        cfg["has_override_query"] = updated.has_override_query()
        cfg["override_query"] = updated.read_override_query() if cfg["has_override_query"] else ""
        cfg["query_builder"] = cfg.get("query_builder")
        cfg["query_builder_json"] = json.dumps(cfg.get("query_builder") or {})
        cfg["query_mode"] = cfg.get("query_mode") or ("manual" if cfg["has_override_query"] else "builder")
        return jsonify(ok=True, config=cfg)

    @groups_bp.route("/group/<handle>/reset-query-configuration", methods=["POST"])
    def reset_query_configuration(handle):
        """Reset both manual SQL override and query-builder configuration."""
        group = group_service.get_group(handle)
        if group is None:
            return "Group not found", 404

        group_service.update_group(
            group=group,
            query="",
            query_builder={},
            query_mode="builder",
        )
        return redirect(url_for("groups.edit_group", handle=handle))

    @groups_bp.route("/group/new", methods=["GET", "POST"])
    def new_group():
        """Create a new group (settings first), then redirect to edit page."""
        all_tags = group_service.get_all_tags()
        duplicate_from = request.values.get("duplicate_from", "").strip()
        duplicate_source = group_service.get_group(duplicate_from) if duplicate_from else None

        form_data = {
            "handle": "",
            "display_name": "",
            "tags": "",
            "email_recipient": "",
            "output_dir": "",
            "duplicate_from": duplicate_source.handle if duplicate_source else "",
        }

        if request.method == "GET" and duplicate_source is not None:
            source_cfg = duplicate_source.config or {}
            form_data.update({
                "handle": "",
                "display_name": "",
                "tags": ",".join(source_cfg.get("tags", []) or []),
                "email_recipient": source_cfg.get("email_recipient", "") or "",
                "output_dir": source_cfg.get("output_dir", "") or "",
                "duplicate_from": duplicate_source.handle,
            })

        if request.method == "POST":
            handle = request.form.get("handle", "").strip()
            display_name = request.form.get("display_name", handle).strip()
            tags_raw = request.form.get("tags", "").strip()
            email_recipient = request.form.get("email_recipient", "").strip()
            output_dir = request.form.get("output_dir", "").strip()
            duplicate_from = request.form.get("duplicate_from", "").strip()
            duplicate_source = group_service.get_group(duplicate_from) if duplicate_from else None

            form_data = {
                "handle": handle,
                "display_name": display_name,
                "tags": tags_raw,
                "email_recipient": email_recipient,
                "output_dir": output_dir,
                "duplicate_from": duplicate_source.handle if duplicate_source else "",
            }

            if not validate_group_handle(handle):
                return render_template("group_create.html", error="Invalid group handle", all_tags=all_tags, form_data=form_data)

            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

            try:
                source_cfg = duplicate_source.config.copy() if duplicate_source is not None else {}
                source_has_override = duplicate_source.has_override_query() if duplicate_source is not None else False
                source_override_sql = duplicate_source.read_override_query() if source_has_override else ""
                source_query_builder = source_cfg.get("query_builder") if duplicate_source is not None else None
                source_query_mode = source_cfg.get("query_mode") if duplicate_source is not None else None

                group_service.create_group(
                    handle=handle,
                    display_name=display_name,
                    tags=tags,
                    query=source_override_sql if duplicate_source is not None else None,
                    query_builder=source_query_builder if duplicate_source is not None else None,
                    email_recipient=email_recipient or None,
                    output_dir=output_dir or None,
                )

                if duplicate_source is not None and source_query_mode in {"builder", "manual"}:
                    created_group = group_service.get_group(handle)
                    if created_group is not None:
                        group_service.update_group(group=created_group, query_mode=source_query_mode)

                return redirect(url_for("groups.edit_group", handle=handle))
            except ValueError as e:
                return render_template(
                    "group_create.html",
                    error=str(e),
                    all_tags=all_tags,
                    form_data=form_data,
                    duplicate_source=duplicate_source,
                )

        return render_template(
            "group_create.html",
            error=None,
            all_tags=all_tags,
            form_data=form_data,
            duplicate_source=duplicate_source,
        )

    @groups_bp.route("/group/<handle>/delete", methods=["POST"])
    def delete_group(handle):
        """Delete a group."""
        group = group_service.get_group(handle)
        if group is None:
            return "Group not found", 404

        try:
            group_service.delete_group(group)
            return redirect(url_for("groups.groups"))
        except Exception as e:
            return f"Error deleting group: {str(e)}", 500

    @groups_bp.route("/group/<handle>/remove-override", methods=["POST"])
    def remove_override(handle):
        """Remove override query.sql so group uses saved query builder params."""
        group = group_service.get_group(handle)
        if group is None:
            return "Group not found", 404

        group_service.update_group(group=group, query="")
        return redirect(url_for("groups.edit_group", handle=handle))

    return groups_bp