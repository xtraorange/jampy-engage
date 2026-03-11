"""Tag management routes."""
from flask import Blueprint, render_template, request, redirect, url_for

from ...services.group_service import GroupService
from ...utils.validation import validate_tag_name

def init_tags_routes(app, base_path: str):
    """Initialize tag routes with dependencies."""
    tags_bp = Blueprint('tags', __name__)
    group_service = GroupService(base_path)

    @tags_bp.route("/tags")
    def tags():
        """List all tags."""
        groups = group_service.discover_groups()
        all_tags = group_service.get_all_tags()

        # Group tags with their associated groups
        tags_with_groups = []
        for tag in all_tags:
            associated_groups = [g for g in groups if tag in g.tags]
            tags_with_groups.append({
                'name': tag,
                'groups': associated_groups
            })

        return render_template("tags.html", tags=tags_with_groups)

    @tags_bp.route("/tag/new", methods=["GET", "POST"])
    def new_tag():
        """Create a new tag and add it to selected groups."""
        groups = group_service.discover_groups()

        if request.method == "POST":
            tag_name = request.form.get("tag_name", "").strip()
            if not validate_tag_name(tag_name):
                return render_template("tag_new.html", groups=groups, error="Invalid tag name")

            selected_groups = request.form.getlist("groups")
            group_service.add_tag_to_groups(tag_name, selected_groups)

            return redirect(url_for("tags.tags"))

        return render_template("tag_new.html", groups=groups, error=None)

    @tags_bp.route("/tag/<tag>/edit", methods=["GET", "POST"])
    def edit_tag(tag):
        """Edit an existing tag by reassigning associated groups."""
        groups = group_service.discover_groups()
        all_tags = group_service.get_all_tags()
        if tag not in all_tags:
            return redirect(url_for("tags.tags"))

        selected_handles = [g.handle for g in groups if tag in g.tags]

        if request.method == "POST":
            tag_name = request.form.get("tag_name", "").strip()
            if not validate_tag_name(tag_name):
                return render_template(
                    "tag_edit.html",
                    groups=groups,
                    error="Invalid tag name",
                    original_tag=tag,
                    tag_name=tag,
                    selected_handles=selected_handles,
                )

            new_selected = request.form.getlist("groups")

            # If renamed, remove old tag first.
            if tag_name != tag:
                group_service.remove_tag_from_all_groups(tag)

            # Ensure selected groups have the final tag.
            group_service.add_tag_to_groups(tag_name, new_selected)

            # Remove final tag from unselected groups.
            for group in groups:
                if group.handle not in new_selected and tag_name in group.tags:
                    tags = [t for t in group.tags if t != tag_name]
                    group_service.update_group(group, tags=tags)

            return redirect(url_for("tags.tags"))

        return render_template(
            "tag_edit.html",
            groups=groups,
            error=None,
            original_tag=tag,
            tag_name=tag,
            selected_handles=selected_handles,
        )

    @tags_bp.route("/tag/<tag>/delete", methods=["POST"])
    def delete_tag(tag):
        """Remove a tag from all groups."""
        group_service.remove_tag_from_all_groups(tag)
        return redirect(url_for("tags.tags"))

    return tags_bp