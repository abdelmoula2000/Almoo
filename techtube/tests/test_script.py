import pytest
from conftest import EXAMPLE, SMALL

from techtube.script import (load_script, parse_script, parse_shot, render_script,
                             script_from_json)


def test_parse_example():
    s = load_script(EXAMPLE)
    assert s.title.startswith("Laptop Overheating")
    assert s.problem == "laptop overheating"
    assert [x.visual for x in s.sections] == ["title", "terminal", "steps", "steps", "tip",
                                              "steps", "outro"]
    assert s.sections[1].code == ["Get-Process | Sort-Object CPU -Descending | Select-Object -First 5"]
    assert s.sections[2].bullets[0] == "Use a hard, flat surface"
    assert s.sections[2].short and not s.sections[1].short
    assert "<!--" not in s.narration


def test_roundtrip():
    s = parse_script(SMALL)
    again = parse_script(render_script(s))
    assert [x.heading for x in again.sections] == [x.heading for x in s.sections]
    assert again.sections[3].shot.box == (0.1, 0.1, 0.3, 0.2)
    assert again.sections[3].shot.zoom == 2
    assert again.sections[1].bullets == s.sections[1].bullets
    assert again.narration == s.narration


def test_parse_shot_clamps():
    shot = parse_shot("a.png focus=1.5,-1 zoom=9")
    assert shot.focus == (1, 0)
    assert shot.zoom == 4.0


def test_terminal_without_code_falls_back():
    s = parse_script("# T\n## A\n[visual: terminal]\nHello there.\n")
    assert s.sections[0].visual == "steps"


def test_unknown_visual_errors():
    with pytest.raises(ValueError):
        parse_script("# T\n## A\n[visual: hologram]\nHi.\n")


def test_no_sections_errors():
    with pytest.raises(ValueError):
        parse_script("# Only a title\n")


def test_script_from_json_validates():
    data = {
        "title": "Fix It",
        "sections": [
            {"heading": "Intro", "visual": "title", "narration": "Hello.", "short": True},
            {"heading": "Step 1: Run", "visual": "terminal", "code": [], "narration": "Do it."},
            {"heading": "Step 2: Cmd", "visual": "terminal", "code": "sfc /scannow",
             "narration": "Run it.", "bullets": "one; two"},
            {"heading": "Bad", "visual": "weird", "narration": "x"},
            {"heading": "Empty", "narration": "  "},
            "garbage",
        ],
    }
    s = script_from_json(data, "fix")
    assert len(s.sections) == 4
    assert s.sections[0].short is False           # title can't be a short
    assert s.sections[1].visual == "steps"        # terminal without code
    assert s.sections[2].code == ["sfc /scannow"]
    assert s.sections[2].bullets == ["one, two"]  # ';' is the bullet separator in script.md
    assert s.sections[3].visual == "steps"


def test_script_from_json_rejects_bad():
    with pytest.raises(ValueError):
        script_from_json({"nope": 1}, "x")
    with pytest.raises(ValueError):
        script_from_json({"sections": [{"narration": "only one"}]}, "x")
