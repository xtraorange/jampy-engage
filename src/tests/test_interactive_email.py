"""Integration test for interactive prompt."""
from unittest.mock import patch
from src.generate_reports import prompt_choice
from src.group import Group
import tempfile
import os
import yaml


def test_interactive_with_selection():
    """Test interactive prompt selects correct group."""
    tmp = tempfile.mkdtemp()
    
    # Create 2 groups
    for handle in ["g1", "g2"]:
        gfolder = os.path.join(tmp, handle)
        os.makedirs(gfolder)
        with open(os.path.join(gfolder, "group.yaml"), "w") as f:
            yaml.safe_dump({"handle": handle, "display_name": handle.upper()}, f)
        with open(os.path.join(gfolder, "query.sql"), "w") as f:
            f.write("select 1")
    
    groups = [Group(os.path.join(tmp, h)) for h in ["g1", "g2"]]
    
    # Simulate user entering "1"
    with patch("builtins.input", return_value="1"):
        selected, should_email, override_email = prompt_choice(groups)
    
    assert len(selected) == 1
    assert selected[0].handle == "g1"
    assert should_email is False
    assert override_email is None


def test_interactive_with_email_flag():
    """Test interactive prompt with --email flag."""
    tmp = tempfile.mkdtemp()
    
    # Create 2 groups
    for handle in ["g1", "g2"]:
        gfolder = os.path.join(tmp, handle)
        os.makedirs(gfolder)
        with open(os.path.join(gfolder, "group.yaml"), "w") as f:
            yaml.safe_dump({"handle": handle, "display_name": handle.upper()}, f)
        with open(os.path.join(gfolder, "query.sql"), "w") as f:
            f.write("select 1")
    
    groups = [Group(os.path.join(tmp, h)) for h in ["g1", "g2"]]
    
    # Simulate user entering "1 --email"
    with patch("builtins.input", return_value="1 --email"):
        selected, should_email, override_email = prompt_choice(groups)
    
    assert len(selected) == 1
    assert selected[0].handle == "g1"
    assert should_email is True
    assert override_email is None


def test_interactive_with_email_override():
    """Test interactive prompt with --email and override address."""
    tmp = tempfile.mkdtemp()
    
    # Create 2 groups
    for handle in ["g1", "g2"]:
        gfolder = os.path.join(tmp, handle)
        os.makedirs(gfolder)
        with open(os.path.join(gfolder, "group.yaml"), "w") as f:
            yaml.safe_dump({"handle": handle, "display_name": handle.upper()}, f)
        with open(os.path.join(gfolder, "query.sql"), "w") as f:
            f.write("select 1")
    
    groups = [Group(os.path.join(tmp, h)) for h in ["g1", "g2"]]
    
    # Simulate user entering "1 --email admin@company.com"
    with patch("builtins.input", return_value="1 --email admin@company.com"):
        selected, should_email, override_email = prompt_choice(groups)
    
    assert len(selected) == 1
    assert selected[0].handle == "g1"
    assert should_email is True
    assert override_email == "admin@company.com"


def test_interactive_multiple_selection():
    """Test interactive prompt with multiple group selections."""
    tmp = tempfile.mkdtemp()
    
    for handle in ["g1", "g2", "g3"]:
        gfolder = os.path.join(tmp, handle)
        os.makedirs(gfolder)
        with open(os.path.join(gfolder, "group.yaml"), "w") as f:
            yaml.safe_dump({"handle": handle, "display_name": handle.upper()}, f)
        with open(os.path.join(gfolder, "query.sql"), "w") as f:
            f.write("select 1")
    
    groups = [Group(os.path.join(tmp, h)) for h in ["g1", "g2", "g3"]]
    
    # Simulate user entering "1, 3"
    with patch("builtins.input", return_value="1, 3"):
        selected, should_email, override_email = prompt_choice(groups)
    
    assert len(selected) == 2
    handles = {g.handle for g in selected}
    assert handles == {"g1", "g3"}
    assert should_email is False
    assert override_email is None


def test_interactive_multiple_with_email():
    """Test interactive prompt with multiple selections and --email."""
    tmp = tempfile.mkdtemp()
    
    for handle in ["g1", "g2", "g3"]:
        gfolder = os.path.join(tmp, handle)
        os.makedirs(gfolder)
        with open(os.path.join(gfolder, "group.yaml"), "w") as f:
            yaml.safe_dump({"handle": handle, "display_name": handle.upper()}, f)
        with open(os.path.join(gfolder, "query.sql"), "w") as f:
            f.write("select 1")
    
    groups = [Group(os.path.join(tmp, h)) for h in ["g1", "g2", "g3"]]
    
    # Simulate user entering "1, 3 --email"
    with patch("builtins.input", return_value="1, 3 --email"):
        selected, should_email, override_email = prompt_choice(groups)
    
    assert len(selected) == 2
    handles = {g.handle for g in selected}
    assert handles == {"g1", "g3"}
    assert should_email is True
    assert override_email is None


def test_interactive_single_entry():
    """Test interactive prompt with single entry."""
    tmp = tempfile.mkdtemp()
    
    gfolder = os.path.join(tmp, "test")
    os.makedirs(gfolder)
    with open(os.path.join(gfolder, "group.yaml"), "w") as f:
        yaml.safe_dump({"handle": "test", "display_name": "Test"}, f)
    with open(os.path.join(gfolder, "query.sql"), "w") as f:
        f.write("select 1")
    
    groups = [Group(gfolder)]
    
    # Simulate user entering just "1"
    with patch("builtins.input", return_value="1"):
        selected, should_email, override_email = prompt_choice(groups)
    
    assert len(selected) == 1
    assert selected[0].handle == "test"
    assert should_email is False
    assert override_email is None
