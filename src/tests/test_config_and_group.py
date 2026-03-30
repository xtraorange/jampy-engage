import os
import tempfile
import yaml
import shutil

from src.config import load_general_config, load_group_config
from src.group import Group
from src.services.report_service import _ensure_entra_members_shortcut
from src.services.group_service import GroupService
from src.services.config_service import ConfigService
from src.utils.validation import build_entra_members_url, extract_entra_group_id


def test_general_config_defaults(tmp_path):
    cfg_file = tmp_path / "general.yaml"
    cfg_file.write_text("oracle_tns: test_tns\n")
    cfg = load_general_config(str(cfg_file))
    assert cfg["oracle_tns"] == "test_tns"
    assert "output_dir" in cfg
    assert cfg["max_workers"] is None
    assert cfg["ui_port"] == 5000


def test_general_config_missing_file_uses_defaults(tmp_path):
    missing_cfg = tmp_path / "does-not-exist.yaml"
    cfg = load_general_config(str(missing_cfg))
    assert cfg["ui_port"] == 5000
    assert "output_dir" in cfg


def test_config_service_saves_without_existing_config_folder(tmp_path):
    svc = ConfigService(str(tmp_path))
    svc.save_general_config({"oracle_tns": "dummy", "ui_port": 5050})
    cfg = svc.load_general_config()
    assert cfg["oracle_tns"] == "dummy"
    assert cfg["ui_port"] == 5050


def test_group_config(tmp_path):
    folder = tmp_path / "myhandle"
    folder.mkdir()
    (folder / "group.yaml").write_text("handle: myhandle\ndisplay_name: Foo\ntags: [a,b]\n")
    (folder / "query.sql").write_text("select 1")
    g = Group(str(folder))
    assert g.handle == "myhandle"
    assert g.display_name == "Foo"
    assert g.tags == {"a", "b"}
    assert "select" in g.read_query().lower()


def test_group_matches():
    class Dummy(Group):
        pass
    g = Group(str(tmp_path)) if False else None

    # create fake group
    tmp = tempfile.mkdtemp()
    cfg = {
        "handle": "h1",
        "display_name": "H1",
        "tags": ["t1", "t2"],
    }
    with open(os.path.join(tmp, "group.yaml"), "w") as f:
        yaml.safe_dump(cfg, f)
    with open(os.path.join(tmp, "query.sql"), "w") as f:
        f.write("select 1")
    g = Group(tmp)
    assert g.matches(names=["h1"])
    assert g.matches(tags=["t2"])
    assert not g.matches(names=["other"])


def test_group_generates_query_from_saved_builder_params(tmp_path):
    folder = tmp_path / "generated_group"
    folder.mkdir()
    cfg = {
        "handle": "generated_group",
        "display_name": "Generated Group",
        "tags": ["x"],
        "query_builder": {
            "version": 2,
            "blocks": [
                {
                    "type": "hierarchy_by_role",
                    "attributes": {
                        "job_code": "000545",
                        "department_id": "02SA23",
                    },
                    "filters": {
                        "job_titles_display": [],
                        "job_codes": [],
                        "bu_codes": [],
                        "companies": [],
                        "tree_branches": [],
                        "department_ids": [],
                        "full_part_time": "",
                    },
                }
            ],
        },
    }
    (folder / "group.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    g = Group(str(folder))
    sql = g.read_query()
    assert "JOB_CODE = '000545'" in sql


def test_group_override_query_takes_precedence(tmp_path):
    folder = tmp_path / "override_group"
    folder.mkdir()
    cfg = {
        "handle": "override_group",
        "display_name": "Override Group",
        "tags": ["x"],
        "query_builder": {
            "mode": "by_role",
            "attributes_job_code": "000545",
        },
    }
    (folder / "group.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    (folder / "query.sql").write_text("SELECT USERNAME FROM manual_source", encoding="utf-8")
    g = Group(str(folder))
    assert g.read_query().strip() == "SELECT USERNAME FROM manual_source"


def test_remove_override_keeps_query_builder_params(tmp_path):
    base = tmp_path
    groups_dir = base / "groups"
    groups_dir.mkdir()
    group_dir = groups_dir / "keep_params"
    group_dir.mkdir()

    cfg = {
        "handle": "keep_params",
        "display_name": "Keep Params",
        "tags": [],
        "query_builder": {
            "version": 2,
            "blocks": [
                {
                    "type": "hierarchy_by_role",
                    "attributes": {
                        "job_code": "000545",
                    },
                }
            ],
        },
    }
    (group_dir / "group.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    (group_dir / "query.sql").write_text("SELECT USERNAME FROM override", encoding="utf-8")

    svc = GroupService(str(base))
    g = svc.get_group("keep_params")
    assert g is not None
    assert g.has_override_query()

    svc.update_group(group=g, query="")

    g2 = svc.get_group("keep_params")
    assert g2 is not None
    assert not g2.has_override_query()
    blocks = g2.config.get("query_builder", {}).get("blocks", [])
    assert blocks
    assert blocks[0].get("attributes", {}).get("job_code") == "000545"


def test_delete_group_retries_after_transient_permission_error(tmp_path, monkeypatch):
    base = tmp_path
    groups_dir = base / "groups"
    groups_dir.mkdir()
    group_dir = groups_dir / "retry_delete"
    group_dir.mkdir()
    (group_dir / "group.yaml").write_text(
        yaml.safe_dump({"handle": "retry_delete", "display_name": "Retry", "tags": []}),
        encoding="utf-8",
    )
    (group_dir / "query.sql").write_text("SELECT 1", encoding="utf-8")

    svc = GroupService(str(base))
    group = svc.get_group("retry_delete")
    assert group is not None

    real_rmtree = shutil.rmtree
    attempts = {"count": 0}

    def flaky_rmtree(path, onerror=None):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise PermissionError("transient lock")
        return real_rmtree(path, onerror=onerror)

    monkeypatch.setattr("src.services.group_service.shutil.rmtree", flaky_rmtree)

    svc.delete_group(group)

    assert attempts["count"] >= 3
    assert not group_dir.exists()


def test_extract_entra_group_id_from_guid_or_link():
    guid = "1b447e90-6f3a-4ab4-aa09-64ad80861b43"
    assert extract_entra_group_id(guid) == guid

    link = (
        "https://entra.microsoft.com/?pwa=1#view/Microsoft_AAD_IAM/"
        "GroupDetailsMenuBlade/~/Members/groupId/1B447E90-6F3A-4AB4-AA09-64AD80861B43/menuId/"
    )
    assert extract_entra_group_id(link) == guid


def test_build_entra_members_url_uses_members_blade():
    guid = "1b447e90-6f3a-4ab4-aa09-64ad80861b43"
    assert build_entra_members_url(guid) == (
        "https://entra.microsoft.com/?pwa=1#view/Microsoft_AAD_IAM/"
        "GroupDetailsMenuBlade/~/Members/groupId/1b447e90-6f3a-4ab4-aa09-64ad80861b43/menuId/"
    )


def test_ensure_entra_members_shortcut_creates_and_refreshes_file(tmp_path):
    group_dir = tmp_path / "groups" / "entra_group"
    group_dir.mkdir(parents=True)
    (group_dir / "group.yaml").write_text(
        yaml.safe_dump(
            {
                "handle": "entra_group",
                "display_name": "Entra Group",
                "tags": [],
                "entra_group_id": "1b447e90-6f3a-4ab4-aa09-64ad80861b43",
            }
        ),
        encoding="utf-8",
    )
    (group_dir / "query.sql").write_text("SELECT 1", encoding="utf-8")
    group = Group(str(group_dir))

    out_dir = tmp_path / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    shortcut = out_dir / "Entra Members.url"
    shortcut.write_text("[InternetShortcut]\nURL=https://example.invalid/\n", encoding="utf-8")

    _ensure_entra_members_shortcut(str(out_dir), group)

    contents = shortcut.read_text(encoding="utf-8")
    assert "[InternetShortcut]" in contents
    assert "URL=https://entra.microsoft.com/?pwa=1#view/Microsoft_AAD_IAM/GroupDetailsMenuBlade/~/Members/groupId/1b447e90-6f3a-4ab4-aa09-64ad80861b43/menuId/" in contents
