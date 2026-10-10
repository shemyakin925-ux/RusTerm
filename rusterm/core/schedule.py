"""launchd-расписание дневного прохода (ТЗ-110 B3).

`rusterm refresh --all` ставят в launchd macOS: plist генерируется
здесь целиком (метка, аргументы с явным --root, ежедневный запуск в
07:00), `schedule install` пишет файл в каталог агентов и зовёт
`launchctl load`, `schedule remove` разгружает и удаляет. В tests
генерация проверяется по содержимому в tmp_path; установка — с
подменённым каталогом и launchctl (сеть не трогается, P7 соблюдён:
путь базы в plist — тот, что назвал пользователь).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PLIST_LABEL = "com.equitylab.refresh"
DEFAULT_AGENT_DIR = Path.home() / "Library" / "LaunchAgents"


def plist_path(target_dir: Path | None = None) -> Path:
    return (target_dir or DEFAULT_AGENT_DIR) / f"{PLIST_LABEL}.plist"


def plist_content(root: str, python: str = sys.executable,
                  log_dir: str | None = None) -> str:
    """Содержимое plist: ежедневный `refresh --all` в 07:00. Путь базы —
    явный (правило 1), чтобы агент открыл ту же базу, что и окно."""
    logs = Path(log_dir) if log_dir else Path(root) / "logs"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{PLIST_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python}</string>
    <string>-m</string>
    <string>rusterm.cli</string>
    <string>--root</string>
    <string>{root}</string>
    <string>refresh</string>
    <string>--all</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>7</integer>
    <key>Minute</key><integer>0</integer>
  </dict>
  <key>StandardOutPath</key><string>{logs / "refresh-launchd.log"}</string>
  <key>StandardErrorPath</key><string>{logs / "refresh-launchd.err"}</string>
</dict>
</plist>
"""


def install(root: str, target_dir: Path | None = None,
            run_launchctl: bool = True) -> Path:
    """Записать plist и (по умолчанию) загрузить агент. Возвращает путь
    к файлу — его же печатает команда."""
    target = plist_path(target_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(plist_content(root), encoding="utf-8")
    if run_launchctl:
        subprocess.run(["launchctl", "load", str(target)], check=False)
    return target


def remove(target_dir: Path | None = None,
           run_launchctl: bool = True) -> bool:
    """Разгрузить и удалить plist. True — файл был и удалён."""
    target = plist_path(target_dir)
    if not target.exists():
        return False
    if run_launchctl:
        subprocess.run(["launchctl", "unload", str(target)], check=False)
    target.unlink()
    return True
