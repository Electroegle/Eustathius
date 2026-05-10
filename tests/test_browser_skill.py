"""
test_browser_skill.py
---------------------
Unit tests for the browser skill — no live browser or Ollama required.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Detector ──────────────────────────────────────────────────────────────────

def test_detect_browser_returns_fallback_when_nothing_installed(tmp_path):
    """When no browser paths exist, falls back to bundled Chromium."""
    from skills.custom.browser_detector import detect_browser
    with patch("skills.custom.browser_detector.Path.exists", return_value=False):
        result = detect_browser()
    assert result.channel is None
    assert "bundled" in result.name.lower() or result.name == "Chromium (bundled)"


def test_list_available_browsers_never_empty():
    """list_available_browsers always returns at least one entry."""
    from skills.custom.browser_detector import list_available_browsers
    with patch("skills.custom.browser_detector.Path.exists", return_value=False):
        browsers = list_available_browsers()
    assert len(browsers) >= 1


# ── Session log ───────────────────────────────────────────────────────────────

def test_session_log_creates_dir_and_writes_json(tmp_path):
    with patch("skills.custom.browser_session._SESSION_ROOT", tmp_path):
        from skills.custom.browser_session import SessionLog
        log = SessionLog("test task")
        log.record_action(1, "testing", "click", "#btn", None, "ok", "https://example.com")
        log.close("done")

    sessions = list(tmp_path.iterdir())
    assert len(sessions) == 1
    actions_file = sessions[0] / "actions.json"
    assert actions_file.exists()
    import json
    data = json.loads(actions_file.read_text())
    assert data["task"] == "test task"
    assert any(a["action"] == "click" for a in data["actions"])


def test_session_log_saves_screenshot(tmp_path):
    with patch("skills.custom.browser_session._SESSION_ROOT", tmp_path):
        from skills.custom.browser_session import SessionLog
        log = SessionLog("screenshot test")
        saved = log.save_screenshot(b"\x89PNG fake", step=3)
        assert saved.name == "step_003.png"
        assert saved.read_bytes() == b"\x89PNG fake"
        log.close()


# ── Vision routing ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_model_has_vision_returns_true_for_llava():
    from skills.custom.browser_vision import _vision_cache, model_has_vision
    _vision_cache.clear()
    result = await model_has_vision("llava:7b")
    assert result is True


@pytest.mark.asyncio
async def test_model_has_vision_returns_false_for_text_model():
    from skills.custom.browser_vision import _vision_cache, model_has_vision
    _vision_cache.clear()
    # Mock Ollama returning no vision families
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"details": {"families": ["llama"]}})

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.post = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=mock_resp),
        __aexit__=AsyncMock(return_value=False),
    ))

    with patch("skills.custom.browser_vision.aiohttp.ClientSession", return_value=mock_session):
        result = await model_has_vision("qwen2:7b")
    assert result is False


# ── Cursor ────────────────────────────────────────────────────────────────────

def test_cursor_context_manager_does_not_raise_when_ctypes_fails():
    """agent_cursor() must not crash even if the Windows API call fails."""
    from skills.custom.browser_cursor import agent_cursor
    with patch("skills.custom.browser_cursor._user32") as mock_u32:
        mock_u32.LoadCursorW.return_value = 0   # simulate failure
        with agent_cursor():
            pass   # must not raise


# ── Actions dispatcher ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_unknown_action_returns_error_string():
    from skills.custom.browser_actions import dispatch
    page = AsyncMock()
    result = await dispatch(page, "teleport", None, None)
    assert "unknown" in result.lower()


@pytest.mark.asyncio
async def test_dispatch_wait_clamps_to_safe_range():
    import time

    from skills.custom.browser_actions import act_wait
    start = time.monotonic()
    await act_wait("0.1")   # minimum is 0.5
    elapsed = time.monotonic() - start
    assert elapsed >= 0.4   # 0.5 - small timing tolerance
