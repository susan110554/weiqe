"""
导出「用户可见文案」为 CSV，供离线翻译 / 润色后回填。

输出：项目根目录 copy_translation_template.csv
列：copy_id, file, line, kind, note, original_text, translated_text
（translated_text 留空，你填好后可发回或用 import_copy_translation.py 尝试写回）

用法（在项目根目录）：
  python tools/export_copy_for_translation.py
"""
from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_TOOLS = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_copy_collect", _TOOLS / "_copy_collect.py")
_cc = importlib.util.module_from_spec(_spec)
assert _spec.loader
_spec.loader.exec_module(_cc)
collect_all = _cc.collect_all

OUT_CSV = ROOT / "copy_translation_template.csv"


def main() -> None:
    rows = collect_all()
    # utf-8-sig：Excel 可直接打开中文
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["copy_id", "file", "line", "kind", "note", "original_text", "translated_text"]
        )
        for i, r in enumerate(rows, 1):
            cid = f"C{i:06d}"
            w.writerow([cid, r.file, r.line, r.kind, r.note, r.text, ""])

    print(f"Wrote {OUT_CSV} ({len(rows)} rows)")
    print("说明：在 translated_text 列填写译文；勿改 copy_id/file/line/original_text，除非你知道后果。")
    print("f-string 行 original_text 为 <f-string> 的需在源码中手工改。")


if __name__ == "__main__":
    main()
