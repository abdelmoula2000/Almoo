from techtube.captions import (Word, ass_color, ass_time, build_ass, estimate_words,
                               group_words, shift)


def test_estimate_words_fill_duration_in_order():
    words = estimate_words("Hello there, this is a test. Done!", 4.0)
    assert [w.text for w in words][0] == "Hello"
    assert all(w.end > w.start for w in words)
    assert all(a.start <= b.start for a, b in zip(words, words[1:]))
    assert words[-1].end <= 4.0
    assert estimate_words("", 3) == []


def test_group_words_limits():
    words = [Word(t, i * 0.3, i * 0.3 + 0.25) for i, t in
             enumerate("one two three four five. six seven".split())]
    groups = group_words(words, max_words=3)
    assert all(len(g) <= 3 for g in groups)
    assert [w.text for w in groups[1]] == ["four", "five."]   # break after punctuation


def test_ass_time_and_color():
    assert ass_time(0) == "0:00:00.00"
    assert ass_time(3725.456) == "1:02:05.46"
    assert ass_color("#FF8000") == "&H000080FF"


def _times(ass):
    out = []
    for line in ass.splitlines():
        if line.startswith("Dialogue:"):
            parts = line.split(",")
            out.append((parts[1], parts[2]))
    return out


def _sec(t):
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def test_build_ass_no_overlaps_and_highlight():
    words = estimate_words("Open Command Prompt and run this command to clear the cache.", 5)
    ass = build_ass(words, 1920, 1080, highlight="#FFD400")
    times = [(_sec(a), _sec(b)) for a, b in _times(ass)]
    assert times
    for (s1, e1), (s2, _) in zip(times, times[1:]):
        assert e1 <= s2 + 1e-6, "caption events must not overlap"
    assert "\\c&H0000D4FF" in ass
    assert "PlayResX: 1920" in ass


def test_build_ass_escapes_braces():
    ass = build_ass([Word("{bad}\\x", 0, 1)], 1080, 1920, vertical=True)
    body = ass.split("[Events]")[1]
    assert "(BAD)/X" in body


def test_shift():
    assert shift([Word("a", 1, 2)], 10)[0].start == 11
