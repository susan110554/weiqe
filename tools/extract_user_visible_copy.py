"""
扫描 bot.py 与 bot_modules 下 .py，提取可能面向 Telegram 用户的文案（静态字符串）。
与 _copy_collect 共用逻辑；本脚本输出为可读 .txt 清单。

用法：
  python tools/extract_user_visible_copy.py
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "user_visible_copy_inventory.txt"
_TOOLS = Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location("_copy_collect", _TOOLS / "_copy_collect.py")
_cc = importlib.util.module_from_spec(_spec)
assert _spec.loader
_spec.loader.exec_module(_cc)
collect_all = _cc.collect_all


def main() -> None:
    buf = io.StringIO()
    buf.write(
        "用户可见文案清单（静态提取）\n"
        "============================\n"
        "使用说明：\n"
        "1. 仅改 TEXT 段落中的自然语言；勿修改 FILE/LINE/KIND 行。\n"
        "2. 勿改动 callback_data、命令名、HTML 标签结构、{placeholder} 与 %s 类占位。\n"
        "3. KIND 含 fstring/concat 的请在源码对应行手工修改。\n"
        "4. 改后执行: python -m py_compile bot.py 及改动的模块。\n"
        "5. 批量翻译请用: python tools/export_copy_for_translation.py → copy_translation_template.csv\n\n"
    )
    for r in collect_all():
        one = r.text.replace("\r\n", "\n").strip()
        if len(one) > 1200:
            one = one[:1200] + "\n... [truncated]"
        buf.write(
            f"---\nFILE: {r.file}\nLINE: {r.line}\nKIND: {r.kind}\nNOTE: {r.note}\nTEXT:\n{one}\n\n"
        )

    OUT.write_text(buf.getvalue(), encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
