"""
将 copy_translation_template.csv（或你另存的副本）中已填写的 translated_text 写回源码。

规则：仅在某个文件中 original_text 全文**恰好出现 1 次**时替换；否则跳过并打印原因。
跳过：original_text 为 <f-string>、translated_text 为空、与 original 相同。

用法（在项目根目录，先备份 git / 复制工程）：
  python tools/import_copy_translation.py
  python tools/import_copy_translation.py path/to/your_filled.csv

默认读取：项目根目录 copy_translation_filled.csv（若不存在则尝试 copy_translation_template.csv）
"""
from __future__ import annotations

import csv
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def apply_csv(csv_path: Path) -> tuple[int, int, list[str]]:
    if not csv_path.is_file():
        raise SystemExit(f"文件不存在: {csv_path}")

    backup_dir = ROOT / ".copy_import_backups"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    errors: list[str] = []
    ok = skip = 0

    rows: list[dict] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    # 按文件分组，减少重复读盘
    from collections import defaultdict

    by_file: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_file[row.get("file", "")].append(row)

    for rel, file_rows in sorted(by_file.items()):
        if not rel:
            continue
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"missing file: {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        original_full = text

        for row in file_rows:
            cid = row.get("copy_id", "")
            o = row.get("original_text", "")
            t = row.get("translated_text", "")
            if not t or not str(t).strip():
                skip += 1
                continue
            t = str(t).replace("\r\n", "\n")
            o = str(o).replace("\r\n", "\n")
            if o == "<f-string>":
                errors.append(f"{cid} skip f-string")
                skip += 1
                continue
            if o == t:
                skip += 1
                continue
            n = text.count(o)
            if n == 0:
                errors.append(f"{cid} original not found in {rel}")
                skip += 1
                continue
            if n > 1:
                errors.append(f"{cid} original appears {n}x in {rel}, skip")
                skip += 1
                continue
            text = text.replace(o, t, 1)
            ok += 1

        if text != original_full:
            bak = backup_dir / f"{stamp}_{path.name}"
            shutil.copy2(path, bak)
            path.write_text(text, encoding="utf-8")

    return ok, skip, errors


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg:
        p = Path(arg)
        if not p.is_absolute():
            p = ROOT / p
    else:
        p = ROOT / "copy_translation_filled.csv"
        if not p.is_file():
            p = ROOT / "copy_translation_template.csv"

    ok, skip, errors = apply_csv(p)
    print(f"Replaced: {ok}, skipped: {skip}")
    if errors:
        print("--- messages ---")
        for e in errors[:80]:
            print(e)
        if len(errors) > 80:
            print(f"... and {len(errors) - 80} more")


if __name__ == "__main__":
    main()
