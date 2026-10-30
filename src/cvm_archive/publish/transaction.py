"""Stage every byte before promotion; roll back completed writes on failure."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory


def safe_target(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative)
    if (not isinstance(relative, str) or "\\" in relative or ":" in relative or
            parts.is_absolute() or ".." in parts.parts or not parts.parts or
            parts.parts[0] not in {"reguladores", "cobertura", "catalogo"}):
        raise ValueError("unsafe publication path")
    target = root.joinpath(*parts.parts)
    for ancestor in (target, *target.parents):
        if ancestor.is_symlink() or ancestor.is_junction():
            raise ValueError("publication through a symlink or junction is forbidden")
        if ancestor == root:
            break
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("publication escapes data root")
    return target


def promote(root: Path, updates: dict[str, bytes | None]) -> bool:
    """Replace changed files only. None deletes a previously published candidate."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    targets = {name: safe_target(root, name) for name in updates}
    for value in updates.values():
        if value is not None and not isinstance(value, bytes):
            raise TypeError("publication values must be immutable bytes or None")
    previous = {name: path.read_bytes() if path.is_file() else None for name, path in targets.items()}
    changed = [name for name in updates if previous[name] != updates[name]]
    if not changed:
        return False
    completed = []
    with TemporaryDirectory(prefix=".cvm-transaction-", dir=root) as temporary:
        stage = Path(temporary)
        for index, name in enumerate(changed):
            for suffix, value in (("new", updates[name]), ("old", previous[name])):
                if value is not None:
                    (stage / f"{index}.{suffix}").write_bytes(value)
        try:
            for index, name in enumerate(changed):
                target = targets[name]
                target.parent.mkdir(parents=True, exist_ok=True)
                if updates[name] is None:
                    target.unlink(missing_ok=True)
                else:
                    os.replace(stage / f"{index}.new", target)
                completed.append((index, name))
        except BaseException:
            for index, name in reversed(completed):
                if previous[name] is None:
                    targets[name].unlink(missing_ok=True)
                else:
                    os.replace(stage / f"{index}.old", targets[name])
            raise
    return True
