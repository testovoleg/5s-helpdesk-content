#!/usr/bin/env python3
"""Generate index.json with materials and their last update dates."""

from __future__ import annotations

import json
import os
import re
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
        dt = datetime.fromisoformat(value)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    # Даты из статей идут без времени и часового пояса, из git — с ними:
    # без общего знаменателя сравнение падает
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


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


def read_order(dir_path: Path) -> list[str]:
    order_file = dir_path / ".order"
    if not order_file.exists():
        return []
    names = []
    for line in order_file.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if name and not name.startswith("#"):
            names.append(name)
    return names


def is_material(dir_path: Path) -> bool:
    """Папка статьи, а не раздела: в ней лежат .md, кроме README."""
    return any(
        f.suffix == ".md" and f.name != "README.md"
        for f in dir_path.iterdir()
        if f.is_file()
    )


def collect_sections(dir_path: Path) -> list[dict]:
    """Дерево разделов в порядке из файлов .order.

    Порядок задается вручную, потому что он смысловой, а не алфавитный:
    он повторяет порядок разделов на сайте. Разделы, которых нет в .order,
    дописываются в конец по алфавиту — чтобы новая папка попала в индекс,
    даже если про список забыли."""
    if not dir_path.exists():
        return []

    present = {
        d.name: d
        for d in sorted(dir_path.iterdir(), key=lambda d: d.name)
        if d.is_dir() and d.name not in ("attachments", ".git") and not is_material(d)
    }

    wanted = read_order(dir_path)
    names = [n for n in wanted if n in present]
    names += [n for n in present if n not in wanted]

    sections = []
    for name in names:
        node: dict = {
            "name": name,
            "path": present[name].relative_to(ROOT).as_posix(),
        }
        children = collect_sections(present[name])
        if children:
            node["sections"] = children
        sections.append(node)
    return sections


RE_READING = re.compile(r"(?m)^\*\*Время чтения:\*\*\s*(\d+)")
RE_UPDATED = re.compile(r"(?m)^\*\*Обновлено:\*\*\s*(\d{2})\.(\d{2})\.(\d{4})")
# Тот же блок в одну строку: *11 мин. · Обновлено 25.08.2026*
RE_ONELINE = re.compile(
    r"(?m)^\*(?:(\d+) мин\. · )?Обновлено (\d{2})\.(\d{2})\.(\d{4})\*"
)
# ...и он же таблицей: время чтения и дата в двух колонках
RE_TABLE = re.compile(
    r"(?m)^<table><tr>"
    r"(?:<td><b>Время чтения:</b> (\d+) мин\.</td>)?"
    r"<td><b>Обновлено:</b> (\d{2})\.(\d{2})\.(\d{4})</td>"
    r"</tr></table>"
)


def extract_meta(md_path: Path) -> dict:
    """Служебные строки под заголовком: время чтения и дата обновления.
    Их ведет .scripts/update-meta.py."""
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return {}

    meta: dict = {}

    one = RE_ONELINE.search(text) or RE_TABLE.search(text)
    if one:
        mins, d, mo, y = one.groups()
        meta["updated_at"] = f"{y}-{mo}-{d}"
        if mins:
            meta["reading_time"] = int(mins)
        return meta

    m = RE_UPDATED.search(text)
    if m:
        d, mo, y = m.groups()
        meta["updated_at"] = f"{y}-{mo}-{d}"
    m = RE_READING.search(text)
    if m:
        meta["reading_time"] = int(m.group(1))
    return meta


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
            md_path = p / main_file
            title = extract_title(md_path, p.name)
            meta = extract_meta(md_path)

            # Дату берем из строки "**Обновлено:**" в самой статье: ее ведет
            # .scripts/update-meta.py и не поднимает на служебных правках,
            # тогда как git любую правку файла считает изменением
            updated_at = meta.get("updated_at")
            if not updated_at:
                if is_dirty(rel):
                    updated_at = now_iso()
                else:
                    updated_at = git_last_commit_date(rel) or fs_mtime_iso(p)

            material = {
                "path": rel,
                "title": title,
                "type": root,
                "updated_at": updated_at,
            }
            if meta.get("reading_time"):
                material["reading_time"] = meta["reading_time"]
            materials.append(material)

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
        "sections": {root: collect_sections(ROOT / root) for root in CONTENT_ROOTS},
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
