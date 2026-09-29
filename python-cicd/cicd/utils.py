"""通用工具。"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# 固定东八区，避免 zoneinfo 在 Python 3.8 不可用
_TZ_SHANGHAI = timezone(timedelta(hours=8))


def run_cmd(
    cmd: List[str],
    *,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    """执行 shell 命令，默认捕获 stdout/stderr。"""
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=check,
        capture_output=capture,
        text=True,
    )


def run_shell(
    script: str,
    *,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    check: bool = True,
) -> str:
    """执行 shell 脚本字符串，返回 stdout。"""
    result = subprocess.run(
        script,
        shell=True,
        cwd=cwd,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )
    return (result.stdout or "").strip()


def _resolve_tz(timezone_name: str) -> timezone:
    if timezone_name in ("Asia/Shanghai", "UTC+8", "CST"):
        return _TZ_SHANGHAI
    return _TZ_SHANGHAI


def now_str(timezone: str = "Asia/Shanghai", fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return datetime.now(_resolve_tz(timezone)).strftime(fmt)


def date_str(timezone: str = "Asia/Shanghai", fmt: str = "%Y%m%d") -> str:
    return datetime.now(_resolve_tz(timezone)).strftime(fmt)


def timestamp_tag(timezone: str = "Asia/Shanghai") -> str:
    return datetime.now(_resolve_tz(timezone)).strftime("%Y%m%d%H%M%S")


def normalize_branch(raw: str) -> str:
    if not raw:
        return ""
    b = raw.strip()
    if b.startswith("refs/heads/"):
        b = b[len("refs/heads/") :]
    if b.startswith("origin/"):
        b = b[len("origin/") :]
    return b


def sanitize_branch_for_image_tag(raw: str) -> str:
    if not raw:
        return "unknown"
    b = normalize_branch(raw)
    s = re.sub(r"/", "-", b)
    s = re.sub(r"[^a-zA-Z0-9._-]", "-", s)
    s = re.sub(r"-+", "-", s)
    s = re.sub(r"^[.-]+|[.-]+$", "", s)
    return s or "unknown"


def parse_tag(tag: str) -> Dict[str, str]:
    m = re.match(r"^([a-zA-Z-]+)-(\d{12})-v(\d+\.\d+\.\d+)$", tag or "")
    if m:
        return {"branch": m.group(1), "timestamp": m.group(2), "version": m.group(3)}
    return {"branch": "", "timestamp": "", "version": ""}


def load_json_file(path: str, default: Any = None) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else []


def save_json_file(path: str, data: Any) -> None:
    import os

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
