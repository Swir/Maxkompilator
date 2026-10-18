"""Validated project-owned application metadata for native build adapters.

Reading a profile is side-effect-free: it never creates directories, runs SDKs,
or follows an icon outside the project root.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .config import load_config
from .models import MaxkompilatorError, PlanError


_SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
_WINDOWS_RESERVED = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?\Z", re.IGNORECASE)
_SAFE_VERSION = re.compile(r"[0-9]+(?:\.[0-9]+){1,3}(?:-[A-Za-z0-9][A-Za-z0-9.-]*)?\Z")


@dataclass(frozen=True)
class AppProfile:
    name: str
    version: str | None
    icon: Path | None
    explicit_name: bool = False


def load_app_profile(root: Path, default_name: str) -> AppProfile:
    """Read [app] settings; reject invalid metadata before invoking a compiler."""
    root = root.resolve()
    try:
        settings = load_config(root)
    except (MaxkompilatorError, OSError, ValueError) as exc:
        raise PlanError(f"Invalid application profile: {exc}") from exc
    app = settings.get("app", {})
    if not isinstance(app, dict):
        raise PlanError("[app] must be a TOML table.")
    unknown = set(app) - {"name", "version", "icon"}
    if unknown:
        raise PlanError(f"Unknown [app] settings: {', '.join(sorted(unknown))}.")
    name = app.get("name", default_name)
    if "name" in app and (not isinstance(name, str) or not _SAFE_NAME.fullmatch(name) or name in {".", ".."} or name.endswith(".") or _WINDOWS_RESERVED.fullmatch(name)):
        raise PlanError("[app].name must be 1-80 ASCII letters, numbers, dots, '-' or '_', starting with a letter or number, without reserved Windows names or a final dot.")
    version = app.get("version")
    if version is not None:
        if not isinstance(version, str) or len(version) > 64 or not _SAFE_VERSION.fullmatch(version):
            raise PlanError("[app].version must be a numeric version like 1.2.3 or 1.2.3-beta.1.")
        numeric = version.split("-", 1)[0].split(".")
        if any(int(part) > 65535 for part in numeric):
            raise PlanError("Each numeric [app].version component must be at most 65535.")
    icon = app.get("icon")
    resolved_icon = None
    if icon is not None:
        if not isinstance(icon, str) or not icon.strip():
            raise PlanError("[app].icon must be a relative path to an existing icon file.")
        relative = Path(icon)
        if relative.is_absolute() or ".." in relative.parts or relative == Path("."):
            raise PlanError("[app].icon must stay inside the project root.")
        candidate = root / relative
        if any(part.is_symlink() for part in (candidate, *candidate.parents) if part != root and part.is_relative_to(root)):
            raise PlanError("[app].icon cannot use symlinks.")
        resolved_icon = candidate.resolve()
        if not resolved_icon.is_relative_to(root) or not resolved_icon.is_file():
            raise PlanError("[app].icon must be a regular file inside the project root.")
        if ";" in str(resolved_icon) or "\n" in str(resolved_icon):
            raise PlanError("[app].icon path contains an unsupported MSBuild separator.")
        if resolved_icon.suffix.lower() not in {".ico", ".icns", ".png"}:
            raise PlanError("[app].icon must be a .ico, .icns or .png image.")
    return AppProfile(name=name, version=version, icon=resolved_icon, explicit_name="name" in app)


def native_icon(profile: AppProfile, target: str) -> Path | None:
    """Ensure the icon can be embedded by the target's native builder."""
    if profile.icon is None:
        return None
    family = target.split("-", 1)[0]
    expected = {"win": ".ico", "macos": ".icns", "osx": ".icns"}.get(family)
    if expected is None:
        raise PlanError(f"Native application icon embedding is not supported for {target}.")
    if profile.icon.suffix.lower() != expected:
        raise PlanError(f"Application icon for {target} must use {expected}.")
    return profile.icon
