"""
Tests for normalize_path() and portable_path().

normalize_path()  — converts a stored path to the OS-native form suitable
                    for filesystem calls.  On Linux/WSL it also translates
                    Windows drive-letter paths (Z:/...) to WSL mount paths
                    (/mnt/z/...) and vice versa on Windows.

portable_path()   — converts any path to a forward-slash form safe to store
                    in JSON without backslash escaping.

Round-trip invariant: normalize_path(portable_path(p)) should always yield
the correct OS-native path regardless of the input separator style.
"""
import sys
import pytest
import MusicScoreViewer as msv


# ---------------------------------------------------------------------------
# portable_path
# ---------------------------------------------------------------------------

class TestPortablePath:
    def test_empty_string_returns_empty(self):
        assert msv.portable_path("") == ""

    def test_backslashes_converted_to_forward_slashes(self):
        assert msv.portable_path(r"Z:\PARA\foo\bar.pdf") == "Z:/PARA/foo/bar.pdf"

    def test_forward_slashes_unchanged(self):
        assert msv.portable_path("Z:/PARA/foo/bar.pdf") == "Z:/PARA/foo/bar.pdf"

    def test_linux_path_unchanged(self):
        assert msv.portable_path("/mnt/z/PARA/foo/bar.pdf") == "/mnt/z/PARA/foo/bar.pdf"

    def test_mixed_slashes_all_become_forward(self):
        assert msv.portable_path(r"Z:/PARA\foo/bar.pdf") == "Z:/PARA/foo/bar.pdf"

    def test_deeply_nested_path(self):
        result = msv.portable_path(r"Z:\a\b\c\d\e.pdf")
        assert result == "Z:/a/b/c/d/e.pdf"
        assert "\\" not in result


# ---------------------------------------------------------------------------
# normalize_path  (platform-specific behaviour)
# ---------------------------------------------------------------------------

class TestNormalizePathCommon:
    """Behaviour that is the same on both platforms."""

    def test_empty_string_returns_empty(self):
        assert msv.normalize_path("") == ""

    def test_redundant_separators_collapsed(self):
        result = msv.normalize_path("Z://PARA//foo.pdf")
        assert "//" not in result and "\\\\" not in result


@pytest.mark.skipif(sys.platform == "win32", reason="WSL/Linux-only translation")
class TestNormalizePathOnLinux:
    def test_windows_drive_forward_slash_to_wsl(self):
        assert msv.normalize_path("Z:/PARA/foo.pdf") == "/mnt/z/PARA/foo.pdf"

    def test_windows_drive_backslash_to_wsl(self):
        assert msv.normalize_path(r"Z:\PARA\foo.pdf") == "/mnt/z/PARA/foo.pdf"

    def test_mixed_slashes_to_wsl(self):
        assert msv.normalize_path(r"Z:/PARA\foo.pdf") == "/mnt/z/PARA/foo.pdf"

    def test_uppercase_drive_letter_lowercased_in_mount(self):
        assert msv.normalize_path("C:/Users/test.pdf") == "/mnt/c/Users/test.pdf"

    def test_lowercase_drive_letter_accepted(self):
        assert msv.normalize_path("z:/foo.pdf") == "/mnt/z/foo.pdf"

    def test_linux_path_not_modified(self):
        assert msv.normalize_path("/home/user/score.pdf") == "/home/user/score.pdf"

    def test_wsl_mount_path_not_modified(self):
        assert msv.normalize_path("/mnt/z/PARA/foo.pdf") == "/mnt/z/PARA/foo.pdf"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only translation")
class TestNormalizePathOnWindows:
    def test_wsl_mount_path_to_windows_drive(self):
        assert msv.normalize_path("/mnt/z/PARA/foo.pdf") == r"Z:\PARA\foo.pdf"

    def test_wsl_lowercase_drive_letter_uppercased(self):
        result = msv.normalize_path("/mnt/c/Users/test.pdf")
        assert result.startswith("C:\\")

    def test_windows_path_unchanged(self):
        assert msv.normalize_path(r"Z:\PARA\foo.pdf") == r"Z:\PARA\foo.pdf"


# ---------------------------------------------------------------------------
# Round-trip: portable_path → normalize_path
# ---------------------------------------------------------------------------

class TestRoundTrip:
    """
    portable_path converts to forward-slash storage form.
    normalize_path converts to OS-native filesystem form.
    Together they should always yield the correct platform path.
    """

    @pytest.mark.skipif(sys.platform == "win32", reason="WSL round-trip")
    def test_windows_path_survives_round_trip_on_wsl(self):
        stored = msv.portable_path("Z:/PARA/Resources/Music/score.pdf")
        assert msv.normalize_path(stored) == "/mnt/z/PARA/Resources/Music/score.pdf"

    @pytest.mark.skipif(sys.platform == "win32", reason="WSL round-trip")
    def test_backslash_path_survives_round_trip_on_wsl(self):
        stored = msv.portable_path(r"Z:\PARA\Resources\Music\score.pdf")
        assert msv.normalize_path(stored) == "/mnt/z/PARA/Resources/Music/score.pdf"

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows round-trip")
    def test_wsl_path_survives_round_trip_on_windows(self):
        stored = msv.portable_path("/mnt/z/PARA/Resources/Music/score.pdf")
        assert msv.normalize_path(stored) == r"Z:\PARA\Resources\Music\score.pdf"

    def test_portable_then_normalize_has_no_backslashes_on_linux(self):
        if sys.platform == "win32":
            pytest.skip("Not applicable on Windows")
        result = msv.normalize_path(msv.portable_path(r"Z:\PARA\foo.pdf"))
        assert "\\" not in result
