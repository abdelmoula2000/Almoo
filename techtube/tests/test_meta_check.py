import json

from conftest import SMALL

from techtube.check import FAIL, OK, WARN, Report, check_title, cosine, jaccard, run_check, shingles
from techtube.meta import chapters, fallback_meta, make_meta
from techtube.script import parse_script, render_script
from techtube.shorts import choose_sections, short_text
from techtube.util import Project, fmt_ts


def test_fmt_ts():
    assert fmt_ts(0) == "0:00"
    assert fmt_ts(75.9) == "1:15"
    assert fmt_ts(3661) == "1:01:01"


def seg(start, dur, heading, visual="steps"):
    return {"start": start, "duration": dur, "heading": heading, "visual": visual}


def test_chapters_rules():
    tl = [seg(0, 12, "Hook", "title"), seg(12, 4, "Tiny"), seg(16, 30, "Step 1"),
          seg(46, 20, "Step 2"), seg(66, 8, "Bye", "outro")]
    ch = chapters(tl)
    assert ch[0] == (0.0, "Intro")
    assert [c[1] for c in ch] == ["Intro", "Step 1", "Step 2"]   # short ones merged
    assert chapters(tl[:2]) == []                                 # fewer than 3 -> none


def test_fallback_meta_counts_steps():
    m = fallback_meta(parse_script(SMALL))
    assert "3 Fixes" in m["titles"][1]
    assert len(m["tags"]) <= 15


def test_make_meta_without_llm(small_project):
    (small_project.build_dir / "timeline_main.json").write_text(json.dumps([
        seg(0, 11, "Slow Wi-Fi?", "title"), seg(11, 15, "Step 1: Restart the router"),
        seg(26, 15, "Step 2: Flush DNS"), seg(41, 12, "Did it work?", "outro")]))
    small_project.assets_json.write_text(json.dumps(
        {"music/song.mp3": {"source": "YouTube Audio Library", "license": "free"}}))
    out = make_meta(small_project, parse_script(SMALL), llm=None)
    text = out.read_text()
    assert "0:00 Intro" in text and "0:26 Step 2: Flush DNS" in text
    assert "ipconfig /flushdns" in text
    assert "YouTube Audio Library" in text


def test_similarity_helpers():
    a = "open settings then go to system and choose power mode balanced"
    assert jaccard(shingles(a), shingles(a)) == 1.0
    assert jaccard(shingles(a), shingles("completely different words here today")) == 0.0
    assert cosine(a, a) > 0.99


def test_title_checks():
    s = parse_script(SMALL.replace("3 Quick Fixes", "3 Quick Fixes 100% guaranteed!!"))
    rep = Report()
    check_title(s, rep)
    fails = [t for st, t, _ in rep.items if st == FAIL]
    assert fails == ["العنوان فيه مبالغة (Clickbait)"]   # number matches the 3 steps


def test_title_number_mismatch():
    s = parse_script(SMALL.replace("3 Quick Fixes", "5 Quick Fixes"))
    rep = Report()
    check_title(s, rep)
    assert any("الرقم" in t for st, t, _ in rep.items if st == FAIL)


def test_run_check_flags_copy_and_unedited_draft(small_project, tmp_path):
    script = parse_script(SMALL)
    # an older project with the same script -> duplicate content
    other = Project(small_project.dir.parent / "older").ensure()
    other.script.write_text(SMALL, encoding="utf-8")
    other.write_info({"theme": "midnight", "created": "2025-12-01T00:00:00"})
    # draft identical to final -> creator didn't add a personal touch
    small_project.draft.write_text(render_script(script), encoding="utf-8")
    small_project.script.write_text(render_script(script), encoding="utf-8")
    path, rep = run_check(small_project, script)
    report = path.read_text(encoding="utf-8")
    assert rep.fails >= 3   # duplicate text, unedited draft, unlicensed screenshot
    assert "assets.json" in report
    assets = json.loads(small_project.assets_json.read_text())
    assert "shots/01.png" in assets           # template created for the creator to fill
    # fill license + edit script -> those problems go away
    assets["shots/01.png"] = {"source": "own", "license": "own"}
    small_project.assets_json.write_text(json.dumps(assets))
    other.script.write_text("# Other\n## A\nTotally different words about printers and ink "
                            "cartridges that jam every single morning.\n")
    _, rep2 = run_check(small_project, script)
    statuses = {t: st for st, t, _ in rep2.items}
    assert statuses.get("كل المواد مسجّل مصدرها وترخيصها") == OK
    assert statuses.get("النص مختلف عن فيديوهاتك السابقة") == OK
    assert WARN in statuses.values() or OK in statuses.values()


def test_choose_sections():
    s = parse_script(SMALL)
    assert choose_sections(s) == [2]                       # marked [short: yes]
    assert choose_sections(s, [3, 4]) == [3, 4]
    s.sections[1].short = False
    picks = choose_sections(s, durations={2: 20, 3: 15, 4: 70})
    assert 4 not in picks and 1 not in picks and 5 not in picks
    txt = short_text(s, 2, "Chan")
    assert "#shorts" in txt and "Restart the router" in txt
