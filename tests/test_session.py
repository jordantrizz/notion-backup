"""Tests for session persistence (save/load/clear) and download retry logic."""

import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from src.utils.helpers import _session_file, clear_session, load_session, save_session

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Unique space id for test isolation
SPACE_ID = "test-space-00000000-0000-0000-0000-000000000000"


@pytest.fixture(autouse=True)
def _cleanup_session() -> Generator[None]:
    """Ensure the session file is removed before and after every test."""
    session_path = _session_file(SPACE_ID)
    session_path.unlink(missing_ok=True)
    yield
    session_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# _session_file
# ---------------------------------------------------------------------------


class TestSessionFilePath:
    """Verify the session file naming convention."""

    def test_contains_space_id(self) -> None:
        """Session path must embed the space_id to isolate concurrent workspaces."""
        path = _session_file(SPACE_ID)
        assert SPACE_ID in path.name

    def test_is_dotfile(self) -> None:
        """Session file should be a hidden dotfile in the user's home directory."""
        path = _session_file(SPACE_ID)
        assert path.name.startswith(".")

    def test_lives_in_home(self) -> None:
        """Session file should reside in the home directory."""
        path = _session_file(SPACE_ID)
        assert path.parent == Path.home()

    def test_different_spaces_different_files(self) -> None:
        """Two different space_ids must produce different file paths."""
        path_a = _session_file("space-a")
        path_b = _session_file("space-b")
        assert path_a != path_b


# ---------------------------------------------------------------------------
# save_session / load_session round-trip
# ---------------------------------------------------------------------------


class TestSaveLoadSession:
    """Test basic save -> load round-trip."""

    def test_round_trip(self) -> None:
        """Saving and then loading should return the same task_id and timestamp."""
        save_session(SPACE_ID, "task-abc", 1700000000000)
        session = load_session(SPACE_ID)
        assert session is not None
        assert session["task_id"] == "task-abc"
        assert session["export_started_at_ms"] == 1700000000000

    def test_load_returns_none_when_no_file(self) -> None:
        """load_session should return None when no session file exists."""
        assert load_session(SPACE_ID) is None

    def test_overwrite_previous_session(self) -> None:
        """A second save should overwrite the first session's data."""
        save_session(SPACE_ID, "task-1", 1000)
        save_session(SPACE_ID, "task-2", 2000)
        session = load_session(SPACE_ID)
        assert session is not None
        assert session["task_id"] == "task-2"
        assert session["export_started_at_ms"] == 2000


# ---------------------------------------------------------------------------
# clear_session
# ---------------------------------------------------------------------------


class TestClearSession:
    """Test session file deletion."""

    def test_clear_removes_file(self) -> None:
        """After clearing, load_session should return None."""
        save_session(SPACE_ID, "task-xyz", 9999)
        clear_session(SPACE_ID)
        assert load_session(SPACE_ID) is None

    def test_clear_when_no_file_is_noop(self) -> None:
        """Clearing without a session file should not raise."""
        # Should not raise
        clear_session(SPACE_ID)

    def test_clear_suppresses_os_error(self) -> None:
        """clear_session should swallow OSError during unlink."""
        save_session(SPACE_ID, "task-xyz", 9999)
        with patch.object(Path, "unlink", side_effect=OSError("disk error")):
            # Should not raise
            clear_session(SPACE_ID)


# ---------------------------------------------------------------------------
# Corrupt / malformed session files
# ---------------------------------------------------------------------------


class TestCorruptSession:
    """load_session must handle corrupt or incomplete session files gracefully."""

    def test_invalid_json(self) -> None:
        """load_session should return None and clean up a non-JSON file."""
        _session_file(SPACE_ID).write_text("this is not json!!!")
        assert load_session(SPACE_ID) is None
        # File should be cleaned up
        assert not _session_file(SPACE_ID).exists()

    def test_missing_task_id(self) -> None:
        """load_session should return None when task_id is missing."""
        _session_file(SPACE_ID).write_text(json.dumps({"export_started_at_ms": 1234}))
        assert load_session(SPACE_ID) is None

    def test_missing_started_at(self) -> None:
        """load_session should return None when export_started_at_ms is missing."""
        _session_file(SPACE_ID).write_text(json.dumps({"task_id": "abc"}))
        assert load_session(SPACE_ID) is None

    def test_empty_json_object(self) -> None:
        """load_session should return None for an empty JSON object."""
        _session_file(SPACE_ID).write_text("{}")
        assert load_session(SPACE_ID) is None


# ---------------------------------------------------------------------------
# save_session error handling
# ---------------------------------------------------------------------------


class TestSaveSessionErrors:
    """save_session must not crash on filesystem errors."""

    def test_write_failure_is_swallowed(self) -> None:
        """save_session should log a warning but not raise on write failure."""
        with patch.object(Path, "write_text", side_effect=OSError("read-only fs")):
            # Should not raise
            save_session(SPACE_ID, "task-abc", 1234)
        # Nothing was persisted
        assert load_session(SPACE_ID) is None


# ---------------------------------------------------------------------------
# Workspace isolation
# ---------------------------------------------------------------------------


class TestWorkspaceIsolation:
    """Concurrent workspaces must not interfere with each other's sessions."""

    OTHER_SPACE = "other-space-11111111-1111-1111-1111-111111111111"

    @pytest.fixture(autouse=True)
    def _cleanup_other(self) -> Generator[None]:
        """Clean up the other workspace's session file too."""
        other_path = _session_file(self.OTHER_SPACE)
        other_path.unlink(missing_ok=True)
        yield
        other_path.unlink(missing_ok=True)

    def test_save_does_not_affect_other_space(self) -> None:
        """Saving for one space should not create a session for another."""
        save_session(SPACE_ID, "task-a", 1000)
        assert load_session(self.OTHER_SPACE) is None

    def test_clear_does_not_affect_other_space(self) -> None:
        """Clearing one space should leave another space's session intact."""
        save_session(SPACE_ID, "task-a", 1000)
        save_session(self.OTHER_SPACE, "task-b", 2000)
        clear_session(SPACE_ID)
        assert load_session(SPACE_ID) is None
        session = load_session(self.OTHER_SPACE)
        assert session is not None
        assert session["task_id"] == "task-b"
