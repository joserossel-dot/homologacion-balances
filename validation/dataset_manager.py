from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

KNOWN_GROUPS = {"entrenamiento", "validacion", "edge_cases", "corruptos"}
IGNORED_PREFIXES = ("~$", ".")
IGNORED_SUFFIXES = (".tmp",)
VALID_EXTENSIONS = {".pdf", ".xls", ".xlsx"}


@dataclass
class DatasetFile:
    path: Path
    group: str
    file_type: str


def _detect_file_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in (".xls", ".xlsx"):
        return "excel"
    return "unknown"


def _should_ignore(name: str) -> bool:
    if name.startswith(IGNORED_PREFIXES):
        return True
    if name.endswith(IGNORED_SUFFIXES):
        return True
    return False


def _infer_group(path: Path, root: Path) -> str:
    for parent in path.parents:
        if parent == root:
            break
        name = parent.name.lower()
        if name in KNOWN_GROUPS:
            return name
    return "validacion"


class DatasetManager:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    @property
    def root(self) -> Path:
        return self._root

    def discover(self) -> list[DatasetFile]:
        files: list[DatasetFile] = []
        for p in self._iter_files():
            group = _infer_group(p, self._root)
            file_type = _detect_file_type(p)
            files.append(DatasetFile(path=p, group=group, file_type=file_type))
        return files

    def groups(self) -> dict[str, list[DatasetFile]]:
        result: dict[str, list[DatasetFile]] = {}
        for f in self.discover():
            result.setdefault(f.group, []).append(f)
        return result

    def _iter_files(self) -> Iterator[Path]:
        if not self._root.is_dir():
            logger.warning("Root is not a directory: %s", self._root)
            return
        for p in self._root.rglob("*"):
            if not p.is_file():
                continue
            if _should_ignore(p.name):
                continue
            if p.suffix.lower() not in VALID_EXTENSIONS:
                continue
            yield p
