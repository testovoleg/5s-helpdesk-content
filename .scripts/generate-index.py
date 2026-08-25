#!/usr/bin/env python3
"""Generate index.json with materials and their last update dates."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOTS = ("tips", "articles", "lessons")
INDEX_PATH = ROOT / "index.json"


def run_git(*args: str) -> str:
    # core.quotepath=false: иначе git отдаёт кириллические пути экранированными
    # и в кавычках, и подставить их обратно в git log уже нельзя
    return subprocess.check_output(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=ROOT,
        stderr=subprocess.DEVNULL,
        text=True,
        # git отдаёт пути в UTF-8; на Windows без этого Python декодирует их
        # системной кодировкой (cp1251) и падает на кириллице
        encoding="utf-8",
    ).strip()


def is_dirty(path: str) -> bool:
    """Есть ли незакоммиченные правки содержимого. Переименования и удаления
    не в счёт: при переезде раздела содержимое статьи не меняется, а дата
    обновления не должна прыгать на сегодня."""
    try:
        for args in (
            ("diff", "--cached", "--diff-filter=AM", "--name-only"),
            ("diff", "--diff-filter=AM", "--name-only"),
            ("ls-files", "--others", "--exclude-standard"),
        ):
            if run_git(*args, "--", path):
                return True
        return False
    except subprocess.CalledProcessError:
        return False


def git_last_commit_date(path: str) -> str | None:
    """Дата последней правки содержимого материала.

    Считаем по каждому файлу отдельно с --follow, чтобы история не обрывалась
    на переименовании, и с --diff-filter=AM, чтобы сам коммит переименования
    не выдавался за обновление статьи."""
    try:
        files = run_git("ls-files", "--", path).splitlines()
    except subprocess.CalledProcessError:
        return None

    newest: str | None = None
    for rel in files:
        try:
            out = run_git(
                "log", "--follow", "--diff-filter=AM", "-1", "--format=%cI", "--", rel
            )
        except subprocess.CalledProcessError:
            continue
        if out and (newest is None or sort_ts(out) > sort_ts(newest)):
            newest = out
    return newest


def fs_mtime_iso(path: Path) -> str | None:
    newest = 0.0
    for fp in path.rglob("*"):
        if fp.is_file():
            newest = max(newest, fp.stat().st_mtime)
    if not newest:
        return None
    return (
        datetime.fromtimestamp(newest, tz=timezone.utc)
        .astimezone()
        .isoformat(timespec="seconds")
    )


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sort_ts(value: str | None) -> datetime:
    """Дата для сортировки. Разбираем строку, а не сравниваем её посимвольно:
    иначе даты с разными часовыми поясами встанут не в том порядке."""
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def pick_main_file(article_mds: list[str]) -> str:
    if "ARTICLE.md" in article_mds:
        return "ARTICLE.md"
    return sorted(article_mds)[0]


def extract_title(md_path: Path, fallback: str) -> str:
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return fallback
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def collect_sections(root: str) -> list[str]:
    """Разделы верхнего уровня в порядке из файла .order.

    Порядок задается вручную, потому что он смысловой (сначала основной
    продукт, дальше остальные), а не алфавитный. Разделы, которых нет
    в .order, дописываются в конец по алфавиту — чтобы новая папка
    попала в индекс, даже если про список забыли."""
    root_path = ROOT / root
    if not root_path.exists():
        return []

    present = sorted(d.name for d in root_path.iterdir() if d.is_dir())

    wanted: list[str] = []
    order_file = root_path / ".order"
    if order_file.exists():
        for line in order_file.read_text(encoding="utf-8").splitlines():
            name = line.strip()
            if name and not name.startswith("#"):
                wanted.append(name)

    ordered = [name for name in wanted if name in present]
    ordered += [name for name in present if name not in wanted]
    return ordered


def collect_materials() -> list[dict]:
    materials: list[dict] = []

    for root in CONTENT_ROOTS:
        root_path = ROOT / root
        if not root_path.exists():
            continue

        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if d not in ("attachments", ".git")]
            p = Path(dirpath)
            rel = p.relative_to(ROOT).as_posix()
            if rel in CONTENT_ROOTS:
                continue

            article_mds = [
                f for f in filenames if f.endswith(".md") and f != "README.md"
            ]
            if not article_mds:
                continue

            main_file = pick_main_file(article_mds)
            title = extract_title(p / main_file, p.name)

            if is_dirty(rel):
                updated_at = now_iso()
            else:
                updated_at = git_last_commit_date(rel) or fs_mtime_iso(p)

            materials.append(
                {
                    "path": rel,
                    "title": title,
                    "type": root,
                    "updated_at": updated_at,
                }
            )

    # Сначала по пути, затем — устойчивой сортировкой — по дате изменения
    # (свежие вверху). Материалы с одинаковой датой остаются упорядоченными
    # по пути, поэтому порядок не «прыгает» между генерациями.
    materials.sort(key=lambda m: m["path"])
    materials.sort(key=lambda m: sort_ts(m["updated_at"]), reverse=True)
    return materials


def main() -> int:
    materials = collect_materials()
    index = {
        "generated_at": now_iso(),
        "count": len(materials),
        "sections": {root: collect_sections(root) for root in CONTENT_ROOTS},
        "materials": materials,
    }
    INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {INDEX_PATH.relative_to(ROOT)} ({len(materials)} materials)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
