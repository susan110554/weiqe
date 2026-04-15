"""
从 bot.py / bot_modules/*.py 收集静态用户可见字符串，供导出 CSV 与清单共用。
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TG_TEXT_METHODS = frozenset(
    {
        "reply_text",
        "send_message",
        "edit_message_text",
        "edit_text",
        "answer",
        "reply_photo",
        "reply_document",
        "send_document",
        "send_photo",
        "copy_message",
    }
)
TG_TEXT_KW = frozenset({"text", "caption"})


class CopyRecord:
    __slots__ = ("file", "line", "kind", "note", "text")

    def __init__(self, file: str, line: int, kind: str, note: str, text: str) -> None:
        self.file = file
        self.line = line
        self.kind = kind
        self.note = note
        self.text = text


def _str_from(node: ast.AST) -> tuple[str | None, str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, "literal"
    if isinstance(node, ast.JoinedStr):
        return None, "fstring"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return None, "concat"
    return None, "expr"


def collect_from_file(py: Path) -> list[CopyRecord]:
    rel = py.relative_to(ROOT).as_posix()
    out: list[CopyRecord] = []
    try:
        src = py.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(py))
    except SyntaxError:
        return out

    def add(line: int, kind: str, text: str, note: str) -> None:
        t = text.replace("\r\n", "\n")
        if not t.strip():
            return
        out.append(CopyRecord(rel, line, kind, note, t))

    class V(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            lineno = getattr(node, "lineno", 0)

            if isinstance(node.func, ast.Name) and node.func.id == "InlineKeyboardButton":
                if node.args:
                    s, note = _str_from(node.args[0])
                    if s is not None:
                        add(lineno, "InlineKeyboardButton", s, note)
                self.generic_visit(node)
                return

            if isinstance(node.func, ast.Name) and node.func.id == "BotCommand":
                if len(node.args) >= 2:
                    s, note = _str_from(node.args[1])
                    if s is not None:
                        add(lineno, "BotCommand.description", s, note)
                self.generic_visit(node)
                return

            if isinstance(node.func, ast.Attribute):
                name = node.func.attr
                if name in TG_TEXT_METHODS:
                    if node.args:
                        s, note = _str_from(node.args[0])
                        if s is not None:
                            add(lineno, f".{name} arg0", s, note)
                        elif note == "fstring":
                            add(lineno, f".{name} arg0", "<f-string>", note)
                    for kw in node.keywords:
                        if kw.arg in TG_TEXT_KW:
                            s, note = _str_from(kw.value)
                            ln = getattr(kw.value, "lineno", lineno)
                            if s is not None:
                                add(ln, f".{name} {kw.arg}", s, note)
                            elif note == "fstring" and kw.arg in TG_TEXT_KW:
                                add(ln, f".{name} {kw.arg}", "<f-string>", note)

            self.generic_visit(node)

        def visit_Assign(self, node: ast.Assign) -> None:
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper() and len(t.id) >= 4:
                    if len(node.targets) == 1 and isinstance(node.value, (ast.Constant, ast.JoinedStr)):
                        s, note = _str_from(node.value)
                        if s and len(s) > 30:
                            add(
                                getattr(node, "lineno", 0),
                                f"CONST {t.id}",
                                s,
                                note + " (assign)",
                            )
            self.generic_visit(node)

    V().visit(tree)
    return out


def iter_all_py() -> list[Path]:
    files: list[Path] = []
    if (ROOT / "bot.py").is_file():
        files.append(ROOT / "bot.py")
    mod = ROOT / "bot_modules"
    if mod.is_dir():
        files.extend(sorted(mod.glob("*.py")))
    return [f for f in files if not f.name.startswith("__")]


def collect_all() -> list[CopyRecord]:
    all_r: list[CopyRecord] = []
    for py in iter_all_py():
        all_r.extend(collect_from_file(py))
    return all_r
