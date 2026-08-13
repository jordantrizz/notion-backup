"""Helper utility functions."""

import asyncio
import functools
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)

    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1

    return f"{size:.1f} {size_names[i]}"


def get_timestamp_string(dt: datetime | None = None) -> str:
    """Get timestamp string in consistent format."""
    if dt is None:
        dt = datetime.now(UTC)
    return dt.strftime("%Y-%m-%d_%H-%M-%S")


def retry_async(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Decorator for retrying async functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if attempt == max_retries:
                        break

                    # Wait before retrying
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff

            # If we get here, all retries failed
            if last_exception is not None:
                raise last_exception
            msg = "Retry failed without exception"
            raise RuntimeError(msg)

        return wrapper

    return decorator


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")
    return filename.strip()


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate string to maximum length with suffix."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def _session_file(space_id: str) -> Path:
    """Build a per-workspace session file path so concurrent instances don't collide."""
    return Path.home() / f".notion-backup-session-{space_id}.json"


def save_session(space_id: str, task_id: str, started_at_ms: int) -> None:
    """Save export session state for resumption, scoped to a specific workspace."""
    data = {"task_id": task_id, "export_started_at_ms": started_at_ms}
    try:
        _session_file(space_id).write_text(json.dumps(data, indent=2))
    except OSError as e:
        logging.getLogger(__name__).warning("Failed to persist resume session: %s", e)
        return
    logging.getLogger(__name__).info("Session saved for task %s", task_id)


def load_session(space_id: str) -> dict[str, Any] | None:
    """Load saved session state for a specific workspace, if any."""
    session_path = _session_file(space_id)
    if not session_path.exists():
        return None
    try:
        data = json.loads(session_path.read_text())
    except (json.JSONDecodeError, OSError):
        # Corrupt or unreadable session file - discard it
        clear_session(space_id)
        return None
    else:
        task_id = data.get("task_id")
        started_at_ms = data.get("export_started_at_ms")
        if task_id and started_at_ms:
            return {"task_id": task_id, "export_started_at_ms": started_at_ms}
        # Incomplete session data - discard it
        clear_session(space_id)
        return None


def clear_session(space_id: str) -> None:
    """Clear the saved session state for a specific workspace."""
    try:
        session_path = _session_file(space_id)
        if session_path.exists():
            session_path.unlink()
            logging.getLogger(__name__).info("Session cleared")
    except OSError:
        pass
