"""UTF-16 码元偏移：与浏览器 JS 字符串索引对齐（含代理对）。"""

from __future__ import annotations


def utf16_code_units(ch: str) -> int:
    if not ch:
        return 0
    return 2 if ord(ch) > 0xFFFF else 1


def utf16_length(s: str) -> int:
    n = 0
    for ch in s:
        n += utf16_code_units(ch)
    return n


def char_index_to_utf16_offset(s: str, char_idx: int) -> int:
    if char_idx <= 0:
        return 0
    end = min(char_idx, len(s))
    return utf16_length(s[:end])


def utf16_offset_to_char_index(s: str, u16: int) -> int:
    if u16 <= 0:
        return 0
    acc = 0
    for i, ch in enumerate(s):
        w = utf16_code_units(ch)
        if acc + w > u16:
            return i
        acc += w
    return len(s)


def utf16_span_to_char_span(s: str, start16: int, end16: int) -> tuple[int, int]:
    """将 [start16, end16) UTF-16 半开区间转为 Python 字符下标半开区间。"""
    cs = utf16_offset_to_char_index(s, start16)
    ce = utf16_offset_to_char_index(s, end16)
    return (min(cs, ce), max(cs, ce))
