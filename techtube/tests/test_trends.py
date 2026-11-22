from unittest import mock

from techtube import trends
from techtube.trends import Item, merge, write_report


def test_merge_combines_duplicates():
    items = [Item("How to fix WiFi", "youtube", 3.0), Item("how to fix wifi!", "youtube", 1.0),
             Item("Laptop slow", "reddit/r/x", 2.0)]
    out = merge(items)
    assert len(out) == 2
    assert out[0].text == "How to fix WiFi" and out[0].score == 3.5


class R:
    def __init__(self, data):
        self._d = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


def fake_get(url, params=None, headers=None, timeout=None):
    if "suggestqueries" in url:
        return R([params["q"], [params["q"] + " windows 11", params["q"] + " fast"]])
    if "reddit" in url:
        return R({"data": {"children": [
            {"data": {"title": "Why is my laptop so slow?", "score": 120, "num_comments": 40,
                      "permalink": "/r/x/1"}},
            {"data": {"title": "Look at my new setup", "score": 999, "num_comments": 5,
                      "permalink": "/r/x/2"}}]}})
    if "algolia" in url:
        return R({"hits": [{"title": "New Windows update", "points": 300, "url": "http://a"}]})
    raise AssertionError(url)


def test_run_trends_offline(tmp_path):
    with mock.patch("techtube.trends.requests.get", side_effect=fake_get), \
            mock.patch("techtube.trends.time.sleep"):
        path = trends.run_trends(tmp_path, ["wifi"], ["x"], llm=None)
    text = path.read_text(encoding="utf-8")
    assert "how to fix wifi windows 11" in text
    assert "Why is my laptop so slow?" in text
    assert "Look at my new setup" not in text        # not a problem/question
    assert "New Windows update" in text


def test_report_with_ideas(tmp_path):
    p = write_report(tmp_path, [Item("x", "youtube", 1, "u")],
                     [{"title": "Fix X", "problem": "x", "why": "many searches",
                       "evergreen": True, "difficulty": "easy"}])
    assert "Fix X" in p.read_text(encoding="utf-8")
