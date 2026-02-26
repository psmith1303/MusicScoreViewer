"""
Tests for SafeJSON.load() and SafeJSON.save().

These tests mock tkinter.messagebox so they run without a display.
"""
import json
import os
from unittest.mock import patch, MagicMock

import pytest
import MusicScoreViewer as msv


# ---------------------------------------------------------------------------
# SafeJSON.load
# ---------------------------------------------------------------------------

class TestSafeJSONLoad:
    def test_missing_file_returns_empty_dict(self, tmp_path):
        result = msv.SafeJSON.load(str(tmp_path / "nonexistent.json"))
        assert result == {}

    def test_missing_file_returns_provided_default(self, tmp_path):
        default = {"key": "value", "num": 42}
        result = msv.SafeJSON.load(str(tmp_path / "nonexistent.json"), default=default)
        assert result == default

    def test_valid_json_loaded_correctly(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text('{"title": "Sonata", "pages": 4}', encoding="utf-8")
        assert msv.SafeJSON.load(str(f)) == {"title": "Sonata", "pages": 4}

    def test_valid_json_with_nested_structure(self, tmp_path):
        data = {"setlist": [{"path": "Z:/foo.pdf", "start_page": 1}]}
        f = tmp_path / "setlists.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        assert msv.SafeJSON.load(str(f)) == data

    def test_valid_json_null_values_preserved(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text('{"end_page": null}', encoding="utf-8")
        assert msv.SafeJSON.load(str(f)) == {"end_page": None}

    def test_corrupt_json_shows_warning_dialog(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{this is not valid json}", encoding="utf-8")
        with patch.object(msv.messagebox, "showwarning") as mock_warn:
            result = msv.SafeJSON.load(str(f))
        assert result == {}
        mock_warn.assert_called_once()

    def test_corrupt_json_returns_provided_default(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{bad}", encoding="utf-8")
        default = {"fallback": True}
        with patch.object(msv.messagebox, "showwarning"):
            result = msv.SafeJSON.load(str(f), default=default)
        assert result == default

    def test_corrupt_json_original_file_not_modified(self, tmp_path):
        f = tmp_path / "bad.json"
        bad_content = "{this is not valid json}"
        f.write_text(bad_content, encoding="utf-8")
        with patch.object(msv.messagebox, "showwarning"):
            msv.SafeJSON.load(str(f))
        assert f.read_text(encoding="utf-8") == bad_content

    def test_unreadable_file_returns_empty_dict(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text('{"key": "val"}', encoding="utf-8")
        # Make unreadable
        os.chmod(str(f), 0o000)
        try:
            with patch.object(msv.messagebox, "showwarning"):
                result = msv.SafeJSON.load(str(f))
            assert result == {}
        finally:
            os.chmod(str(f), 0o644)


# ---------------------------------------------------------------------------
# SafeJSON.save
# ---------------------------------------------------------------------------

class TestSafeJSONSave:
    def test_save_returns_true_on_success(self, tmp_path):
        f = tmp_path / "out.json"
        assert msv.SafeJSON.save(str(f), {"key": "value"}) is True

    def test_saved_data_is_valid_json(self, tmp_path):
        f = tmp_path / "out.json"
        data = {"title": "Sonata", "pages": 4, "tags": ["baroque", "solo"]}
        msv.SafeJSON.save(str(f), data)
        assert json.loads(f.read_text(encoding="utf-8")) == data

    def test_null_values_round_trip(self, tmp_path):
        f = tmp_path / "out.json"
        msv.SafeJSON.save(str(f), {"end_page": None})
        assert json.loads(f.read_text(encoding="utf-8")) == {"end_page": None}

    def test_overwrites_existing_file(self, tmp_path):
        f = tmp_path / "out.json"
        msv.SafeJSON.save(str(f), {"v": 1})
        msv.SafeJSON.save(str(f), {"v": 2})
        assert json.loads(f.read_text(encoding="utf-8")) == {"v": 2}

    def test_no_leftover_temp_files(self, tmp_path):
        f = tmp_path / "out.json"
        msv.SafeJSON.save(str(f), {"key": "val"})
        files = list(tmp_path.iterdir())
        assert len(files) == 1
        assert files[0].name == "out.json"

    def test_missing_directory_returns_false(self, tmp_path):
        f = tmp_path / "no_such_dir" / "out.json"
        with patch.object(msv.messagebox, "showerror"):
            result = msv.SafeJSON.save(str(f), {})
        assert result is False

    def test_missing_directory_shows_error_dialog(self, tmp_path):
        f = tmp_path / "no_such_dir" / "out.json"
        with patch.object(msv.messagebox, "showerror") as mock_err:
            msv.SafeJSON.save(str(f), {})
        mock_err.assert_called_once()

    def test_missing_directory_does_not_create_partial_file(self, tmp_path):
        f = tmp_path / "no_such_dir" / "out.json"
        with patch.object(msv.messagebox, "showerror"):
            msv.SafeJSON.save(str(f), {})
        assert not (tmp_path / "no_such_dir").exists()

    def test_nested_data_preserved(self, tmp_path):
        f = tmp_path / "out.json"
        data = {"setlist": [{"path": "Z:/foo.pdf", "start_page": 1, "end_page": None}]}
        msv.SafeJSON.save(str(f), data)
        assert json.loads(f.read_text(encoding="utf-8")) == data


# ---------------------------------------------------------------------------
# Round-trip: save then load
# ---------------------------------------------------------------------------

class TestSafeJSONRoundTrip:
    def test_simple_dict_survives_round_trip(self, tmp_path):
        f = tmp_path / "rt.json"
        data = {"composer": "Bach", "pages": 12, "tags": ["baroque"]}
        msv.SafeJSON.save(str(f), data)
        assert msv.SafeJSON.load(str(f)) == data

    def test_unicode_strings_survive_round_trip(self, tmp_path):
        f = tmp_path / "rt.json"
        data = {"title": "Sonate für Trompete", "symbol": "♩"}
        msv.SafeJSON.save(str(f), data)
        assert msv.SafeJSON.load(str(f)) == data

    def test_setlist_structure_survives_round_trip(self, tmp_path):
        f = tmp_path / "setlists.json"
        data = {
            "Concert": [
                {"path": "Z:/PARA/Music/Bach.pdf", "start_page": 1, "end_page": 4},
                {"path": "Z:/PARA/Music/Clarke.pdf", "start_page": 7, "end_page": None},
            ]
        }
        msv.SafeJSON.save(str(f), data)
        assert msv.SafeJSON.load(str(f)) == data
