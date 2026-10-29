"""History store tests."""
import csv

from anydownloader.core.history import History


def record(job_id="j1", title="Video", state="completed", **extra):
    base = {"job_id": job_id, "url": "https://example.com/v", "title": title,
            "state": state, "site": "YouTube", "profile_label": "1080p",
            "profile_id": "1080p", "created_at": 1700000000.0,
            "completed_at": 1700000100.0}
    base.update(extra)
    return base


class TestHistory:
    def test_add_and_all_newest_first(self, tmp_path):
        h = History(tmp_path / "h.json")
        h.add(record("a"))
        h.add(record("b"))
        assert [r["job_id"] for r in h.all()] == ["b", "a"]

    def test_persists_across_instances(self, tmp_path):
        h1 = History(tmp_path / "h.json")
        h1.add(record("a", title="Keep me"))
        h2 = History(tmp_path / "h.json")
        assert h2.all()[0]["title"] == "Keep me"

    def test_corrupt_file_starts_empty(self, tmp_path):
        (tmp_path / "h.json").write_text("nope", encoding="utf-8")
        h = History(tmp_path / "h.json")
        assert h.all() == []

    def test_search_text(self, tmp_path):
        h = History(tmp_path / "h.json")
        h.add(record("a", title="Cat video"))
        h.add(record("b", title="Dog video"))
        assert len(h.search("cat")) == 1
        assert len(h.search("")) == 2

    def test_search_kind(self, tmp_path):
        h = History(tmp_path / "h.json")
        h.add(record("a", profile_id="1080p"))
        h.add(record("b", profile_id="audio-mp3"))
        assert len(h.search("", kind="audio")) == 1
        assert len(h.search("", kind="video")) == 1
        assert len(h.search("", kind="all")) == 2

    def test_delete_and_clear(self, tmp_path):
        h = History(tmp_path / "h.json")
        h.add(record("a"))
        h.add(record("b"))
        h.delete("a")
        assert [r["job_id"] for r in h.all()] == ["b"]
        h.clear()
        assert h.all() == []

    def test_export_csv(self, tmp_path):
        h = History(tmp_path / "h.json")
        h.add(record("a", title="My video"))
        dest = tmp_path / "out.csv"
        count = h.export_csv(str(dest))
        assert count == 1
        with open(dest, encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh))
        assert rows[0][0] == "Title"
        assert rows[1][0] == "My video"

    def test_export_empty(self, tmp_path):
        h = History(tmp_path / "h.json")
        assert h.export_csv(str(tmp_path / "out.csv")) == 0

    def test_stats(self, tmp_path):
        h = History(tmp_path / "h.json")
        h.add(record("a", state="completed"))
        h.add(record("b", state="failed"))
        stats = h.stats()
        assert stats == {"total": 2, "completed": 1, "failed": 1}
