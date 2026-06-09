"""出力成果物へ混入し得る端末UIメタデータの共通除去処理。"""

from __future__ import annotations

import re
from typing import Any

# 引用トークンの直前に付与されることがある不可視文字も一緒に除去する。
_INVISIBLE_PREFIX = r"[\u200b\u200c\u200d\u2060\ufeff]*"
_CODEX_TERMINAL_CITATION = re.compile(
    _INVISIBLE_PREFIX
    + r":?codex-terminal-citation(?:\[[^\]\r\n]*\])?"
    + r"(?:\{[^}】\r\n]*[}】]|\{[^\r\n]*$)?",
    re.IGNORECASE,
)
# 引用トークンだけが先に除去された出力や、不完全な閉じ括弧を含むメタデータも除去する。
_ORPHAN_TERMINAL_METADATA = re.compile(
    _INVISIBLE_PREFIX
    + r"(?:\{[^}】\r\n]*(?:line_range_start|line_range_end|terminal_chunk_id)[^}】\r\n]*[}】]|\{[^\r\n]*(?:line_range_start|line_range_end|terminal_chunk_id)[^\r\n]*$)",
    re.IGNORECASE,
)


def sanitize_output_text(value: Any) -> str:
    """Codex端末引用と後続メタデータを、不可視文字を含めて完全除去する。"""
    text = str(value)
    previous = None
    while text != previous:
        previous = text
        text = _CODEX_TERMINAL_CITATION.sub("", text)
        text = _ORPHAN_TERMINAL_METADATA.sub("", text)
    return text


def safe_print(*values: Any, **kwargs: Any) -> None:
    """端末UIメタデータを除去してstdout/stderrへ出力する。"""
    print(*(sanitize_output_text(value) for value in values), **kwargs)
