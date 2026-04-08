"""~/.ruyi72 下 USER.md / SOUL.md / MEMORY.md：覆盖默认系统提示片段。"""

from __future__ import annotations

from pathlib import Path

RUYI72_HOME: Path = Path.home() / ".ruyi72"
USER_FILE = RUYI72_HOME / "USER.md"
SOUL_FILE = RUYI72_HOME / "SOUL.md"
MEMORY_FILE = RUYI72_HOME / "MEMORY.md"

_MAX_READ_BYTES = 256 * 1024

_cache_sig: tuple[tuple[str, float | None], tuple[str, float | None], tuple[str, float | None]] | None = (
    None
)
_cache_result: tuple[str | None, str | None, str | None] | None = None


def _sig(path: Path) -> tuple[str, float | None]:
    try:
        st = path.stat()
        return (str(path.resolve()), st.st_mtime_ns)
    except OSError:
        return (str(path.resolve()), None)


def _read_one(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if len(raw) > _MAX_READ_BYTES:
        raw = raw[:_MAX_READ_BYTES]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    s = text.strip()
    return s if s else None


def invalidate_identity_cache() -> None:
    global _cache_sig, _cache_result
    _cache_sig = None
    _cache_result = None


def read_soul_user_memory() -> tuple[str | None, str | None, str | None]:
    """读取 SOUL / USER / MEMORY；缺失或空文件对应项为 None（调用方对 SOUL/USER 回退内置）。"""
    global _cache_sig, _cache_result
    sig = (_sig(SOUL_FILE), _sig(USER_FILE), _sig(MEMORY_FILE))
    if _cache_sig == sig and _cache_result is not None:
        return _cache_result
    soul = _read_one(SOUL_FILE)
    user = _read_one(USER_FILE)
    memory = _read_one(MEMORY_FILE)
    _cache_sig = sig
    _cache_result = (soul, user, memory)
    return _cache_result


def identity_paths() -> dict[str, str]:
    return {
        "user": str(USER_FILE.resolve()),
        "soul": str(SOUL_FILE.resolve()),
        "memory": str(MEMORY_FILE.resolve()),
    }


def file_exists_map() -> dict[str, bool]:
    return {
        "user": USER_FILE.is_file(),
        "soul": SOUL_FILE.is_file(),
        "memory": MEMORY_FILE.is_file(),
    }


def read_for_api() -> dict:
    """供 get_identity_prompt_files：含路径、是否存在、内容与是否截断。"""
    paths = identity_paths()
    exists = file_exists_map()
    out: dict[str, object] = {"ok": True, "paths": paths, "exists": exists}
    for key, path_str, p in (
        ("user", paths["user"], USER_FILE),
        ("soul", paths["soul"], SOUL_FILE),
        ("memory", paths["memory"], MEMORY_FILE),
    ):
        if not p.is_file():
            out[key] = ""
            out[f"{key}_truncated"] = False
            continue
        try:
            raw = p.read_bytes()
        except OSError as e:
            return {"ok": False, "error": f"读取失败 {path_str}: {e}"}
        truncated = len(raw) > _MAX_READ_BYTES
        if truncated:
            raw = raw[:_MAX_READ_BYTES]
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
        out[key] = text
        out[f"{key}_truncated"] = truncated
    return out


def save_partial(payload: dict[str, object]) -> None:
    """写入部分字段；目录不存在则创建。值 None 跳过。"""
    RUYI72_HOME.mkdir(parents=True, exist_ok=True)
    mapping = {
        "user": USER_FILE,
        "soul": SOUL_FILE,
        "memory": MEMORY_FILE,
    }
    for k, path in mapping.items():
        if k not in payload:
            continue
        val = payload[k]
        if val is None:
            continue
        text = val if isinstance(val, str) else str(val)
        path.write_text(text, encoding="utf-8")
    invalidate_identity_cache()
