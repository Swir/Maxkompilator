"""Build a Windows desktop bundle with a separate console worker executable."""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def create_icon(destination: Path) -> None:
    from PySide6.QtCore import QByteArray, QBuffer, QIODevice
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(str(ROOT / "assets" / "maxkompilator.svg"))
    if not renderer.isValid():
        raise RuntimeError("Invalid source SVG icon")
    images = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, "PNG"):
            raise RuntimeError("Cannot encode icon image")
        buffer.close()
        images.append((size, bytes(data)))
    offset = 6 + 16 * len(images)
    header = struct.pack("<HHH", 0, 1, len(images))
    directory = b""
    payload = b""
    for size, data in images:
        directory += struct.pack("<BBBBHHII", size if size < 256 else 0, size if size < 256 else 0,
                                 0, 0, 1, 32, len(data), offset)
        payload += data
        offset += len(data)
    destination.write_bytes(header + directory + payload)


def main() -> int:
    if sys.platform != "win32":
        raise SystemExit("Build the Windows distribution on Windows.")
    work = ROOT / "build" / "desktop"
    work.mkdir(parents=True, exist_ok=True)
    icon = work / "maxkompilator.ico"
    create_icon(icon)
    assets = ROOT / "maxkompilator" / "assets"
    assets.mkdir(exist_ok=True)
    shutil.copy2(ROOT / "assets" / "maxkompilator.svg", assets / "maxkompilator.svg")
    # Both entry points share one PYZ and one runtime directory. The worker has
    # a console subsystem so QProcess receives real stdout/stderr pipes, while
    # the desktop executable opens without a console window.
    spec = work / "Maxkompilator.spec"
    spec.write_text(
        "a = Analysis([" + repr(str(ROOT / "launcher.py")) + "], pathex=[" + repr(str(ROOT)) + "], "
        "binaries=[], datas=[(" + repr(str(ROOT / "assets" / "maxkompilator.svg")) + ", 'maxkompilator/assets')], "
        "hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtPdf'], noarchive=False)\n"
        "pyz = PYZ(a.pure)\n"
        "desktop = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Maxkompilator', debug=False, strip=False, upx=False, console=False, icon=" + repr(str(icon)) + ")\n"
        "worker = EXE(pyz, a.scripts, [], exclude_binaries=True, name='MaxkompilatorCLI', debug=False, strip=False, upx=False, console=True, icon=" + repr(str(icon)) + ")\n"
        "collection = COLLECT(desktop, worker, a.binaries, a.datas, strip=False, upx=False, name='Maxkompilator')\n",
        encoding="utf-8",
    )
    environment = {**os.environ, "PYINSTALLER_CONFIG_DIR": str(work / "cache")}
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(ROOT / "dist"),
                    "--workpath", str(work / "objects"), str(spec)], cwd=ROOT, env=environment, check=True)
    worker = ROOT / "dist" / "Maxkompilator" / "MaxkompilatorCLI.exe"
    subprocess.run([str(worker), "--cli", "--version"], cwd=work, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
