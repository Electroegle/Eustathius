import asyncio
from pathlib import Path
from unittest.mock import patch

from skills.filesystem import FilesystemSkill


def run(coro):
    return asyncio.run(coro)


def test_filesystem_skill_handles_messy_frame_copy_request(tmp_path):
    src = tmp_path / "frames" / "nested"
    src.mkdir(parents=True)
    (src / "key_frame_001.png").write_bytes(b"fake image")
    (src / "notes.txt").write_text("ignore me", encoding="utf-8")

    skill = FilesystemSkill()
    task = (
        "make a directory under downloades folder called new framea and "
        "copy key farames stored somewhere in folder frames"
    )

    with patch.object(Path, "home", return_value=tmp_path), patch(
        "skills.filesystem.Confirm.ask", return_value=True
    ):
        result = run(skill.execute(task, "local"))

    dest = tmp_path / "Downloads" / "new frames"
    assert dest.exists()
    assert (dest / "key_frame_001.png").exists()
    assert "Copied 1 file" in result


def test_filesystem_skill_cancels_without_copying(tmp_path):
    src = tmp_path / "frames"
    src.mkdir()
    (src / "key_frame_001.png").write_bytes(b"fake image")

    skill = FilesystemSkill()

    with patch.object(Path, "home", return_value=tmp_path), patch(
        "skills.filesystem.Confirm.ask", return_value=False
    ):
        result = run(skill.execute("create folder called new frames in downloads and copy frames from frames", "local"))

    assert result == "Cancelled. No files were copied."
    assert not (tmp_path / "Downloads" / "new frames").exists()
