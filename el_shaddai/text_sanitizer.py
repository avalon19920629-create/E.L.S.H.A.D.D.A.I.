"""出力成果物へ混入し得る端末UIメタデータの共通除去処理。"""

from __future__ import annotations

import re
from typing import Any

_CODEX_TERMINAL_CITATION = re.compile(
    r":?codex-terminal-citation(?:\[[^\]\r\n]*\]|\{[^}\r\n]*\}|\([^\)\r\n]*\))*",
    re.IGNORECASE,
)


def sanitize_output_text(value: Any) -> str:
    """codex terminal citation本体と直後のメタデータを出力前に完全除去する。"""
    text = str(value)
    previous = None
    while text != previous:
        previous = text
        text = _CODEX_TERMINAL_CITATION.sub("", text)
    return text


def safe_print(*values: Any, **kwargs: Any) -> None:
    """端末UIメタデータを除去してstdout/stderrへ出力する。"""
    print(*(sanitize_output_text(value) for value in values), **kwargs)
