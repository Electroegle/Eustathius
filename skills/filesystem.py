import re
import shutil
from pathlib import Path

from rich.prompt import Confirm

from . import SkillBase


IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff",
}


class FilesystemSkill(SkillBase):
    name = "filesystem"
    description = "Create folders, find local files, and copy files using safe local filesystem actions."
    keywords = [
        "copy", "folder", "directory", "mkdir", "make directory", "create folder",
        "downloads", "downloades", "file", "files", "frames", "key frames",
    ]

    async def execute(self, task, model, council=False, **kwargs):
        intent = self._parse_task(task)
        if not intent["supported"]:
            return (
                "I recognized this as a filesystem request, but I could not infer a safe action. "
                "Try naming the source folder and destination folder explicitly."
            )

        source_dir = intent["source_dir"]
        dest_dir = intent["dest_dir"]
        if not source_dir or not source_dir.exists():
            return f"Source folder not found: {source_dir or 'unknown'}"

        files = self._select_files(source_dir, prefer_key_frames=intent["prefer_key_frames"])
        if not files:
            return f"No matching frame/image files found under: {source_dir}"

        preview = "\n".join(f"  - {path}" for path in files[:10])
        if len(files) > 10:
            preview += f"\n  ... and {len(files) - 10} more"

        message = (
            f"Create destination:\n  {dest_dir}\n\n"
            f"Copy {len(files)} file(s) from:\n  {source_dir}\n\n"
            f"Preview:\n{preview}\n\n"
            "Proceed?"
        )
        if not Confirm.ask(message, default=False):
            return "Cancelled. No files were copied."

        dest_dir.mkdir(parents=True, exist_ok=True)
        copied = []
        skipped = []
        for src in files:
            try:
                copied.append(self._copy_with_collision_suffix(src, dest_dir))
            except Exception as exc:
                skipped.append(f"{src}: {exc}")

        lines = [
            f"Created/verified: {dest_dir}",
            f"Copied {len(copied)} file(s) from {source_dir}.",
        ]
        if copied:
            lines.append("First copied files:")
            lines.extend(f"  - {path.name}" for path in copied[:10])
            if len(copied) > 10:
                lines.append(f"  ... and {len(copied) - 10} more")
        if skipped:
            lines.append("Skipped:")
            lines.extend(f"  - {item}" for item in skipped[:5])
        return "\n".join(lines)

    def _parse_task(self, task: str):
        normalized = self._normalize(task)
        home = Path.home()
        dest_parent = self._infer_parent(normalized)
        dest_name = self._infer_destination_name(normalized)
        source_dir = self._infer_source_dir(normalized, home)

        return {
            "supported": bool(("copy" in normalized or "create" in normalized or "make" in normalized) and dest_name),
            "dest_dir": dest_parent / dest_name if dest_parent and dest_name else None,
            "source_dir": source_dir,
            "prefer_key_frames": "key frame" in normalized or "keyframe" in normalized,
        }

    def _normalize(self, task: str) -> str:
        text = task.lower()
        replacements = {
            "downloades": "downloads",
            "downloade": "downloads",
            "framea": "frames",
            "farames": "frames",
            "folde": "folder",
            "direcotry": "directory",
        }
        for wrong, right in replacements.items():
            text = text.replace(wrong, right)
        return re.sub(r"\s+", " ", text).strip()

    def _infer_parent(self, text: str) -> Path:
        home = Path.home()
        if "downloads" in text:
            return home / "Downloads"
        if "desktop" in text:
            return home / "Desktop"
        if "documents" in text:
            return home / "Documents"
        return Path.cwd()

    def _infer_destination_name(self, text: str) -> str | None:
        patterns = [
            r"(?:called|named)\s+['\"]?([^,'\"]+?)(?:['\"]?\s+(?:and|then|copy|from|in|under)\b|$)",
            r"(?:folder|directory)\s+['\"]([^'\"]+)['\"]",
            r"(?:folder|directory)\s+called\s+(.+?)(?:\s+and\b|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip(" .")
                if name:
                    return self._sanitize_name(name)
        if "new frames" in text:
            return "new frames"
        return None

    def _infer_source_dir(self, text: str, home: Path) -> Path | None:
        explicit = self._extract_path_like_source(text)
        candidates = []
        if explicit:
            candidates.extend(self._path_candidates(explicit, home))
        if "ranit/frames" in text or "ranit\\frames" in text:
            candidates.append(Path("C:/Users/ranit/frames"))
        if "frames" in text:
            candidates.extend([
                home / "frames",
                home / "Frames",
                Path.cwd() / "frames",
                Path.cwd() / "Frames",
            ])

        seen = set()
        for candidate in candidates:
            resolved = candidate.expanduser()
            key = str(resolved).lower()
            if key in seen:
                continue
            seen.add(key)
            if resolved.exists() and resolved.is_dir():
                return resolved
        return candidates[0].expanduser() if candidates else None

    def _extract_path_like_source(self, text: str) -> str | None:
        match = re.search(r"(?:from|inside|under|in folder|in)\s+([a-z]:[\\/][^,]+|[~\w .-]+[\\/][\w .\\/:-]+)", text)
        if not match:
            return None
        raw = match.group(1).strip(" .")
        raw = re.split(r"\s+(?:to|into|and then|then)\b", raw)[0].strip()
        return raw

    def _path_candidates(self, raw: str, home: Path) -> list[Path]:
        cleaned = raw.replace("/", "\\")
        path = Path(cleaned)
        candidates = [path]
        if not path.is_absolute():
            candidates.append(home / cleaned)
            if cleaned.lower().startswith("ranit\\"):
                candidates.append(Path("C:/Users") / cleaned)
            candidates.append(Path.cwd() / cleaned)
        return candidates

    def _select_files(self, source_dir: Path, prefer_key_frames: bool) -> list[Path]:
        all_files = [
            path for path in source_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        ]
        if prefer_key_frames:
            key_files = [
                path for path in all_files
                if "key" in path.stem.lower() or "frame" in path.stem.lower()
            ]
            if key_files:
                return sorted(key_files)
        return sorted(all_files)

    def _copy_with_collision_suffix(self, src: Path, dest_dir: Path) -> Path:
        target = dest_dir / src.name
        if target.exists():
            stem = src.stem
            suffix = src.suffix
            index = 1
            while True:
                candidate = dest_dir / f"{stem}_{index}{suffix}"
                if not candidate.exists():
                    target = candidate
                    break
                index += 1
        shutil.copy2(src, target)
        return target

    def _sanitize_name(self, name: str) -> str:
        cleaned = re.sub(r'[<>:"/\\|?*]', "_", name).strip()
        return cleaned or "new folder"
