import os
import tempfile
import yaml

from src.config import load_general_config, load_group_config
from src.group import Group


def test_general_config_defaults(tmp_path):
    cfg_file = tmp_path / "general.yaml"
    cfg_file.write_text("oracle_tns: test_tns\n")
    cfg = load_general_config(str(cfg_file))
    assert cfg["oracle_tns"] == "test_tns"
    assert "output_dir" in cfg
    assert cfg["max_workers"] is None


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
