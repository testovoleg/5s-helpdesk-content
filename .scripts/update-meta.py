#!/usr/bin/env python3
"""Поддерживает в статьях служебные строки под заголовком:

    **Время чтения:** 15 мин.
    **Обновлено:** 25.08.2026

"Обновлено" проставляется автоматически. Дата меняется только тогда, когда
изменился сам текст статьи: правка одних служебных строк (или переименование
папки) обновлением не считается, иначе дата поднималась бы на пустом месте.

"Время чтения" скрипт не трогает — это редакторское решение. Он только
добавляет строку с расчетной оценкой, если ее еще нет, и только в articles/.
"""

from __future__ import annotations

import math
import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Время чтения показываем только у больших статей; советы читаются за минуту
READING_TIME_ROOTS = ("articles",)
CONTENT_ROOTS = ("tips", "articles", "lessons")

RE_READING = re.compile(r"(?m)^\*\*Время чтения:\*\* .*(?:\r?\n)?")
RE_UPDATED = re.compile(r"(?m)^\*\*Обновлено:\*\* .*(?:\r?\n)?")
# Тот же блок, свернутый в одну строку: *11 мин. · Обновлено 25.08.2026*
RE_ONELINE = re.compile(
    r"(?m)^\*(?:(\d+) мин\. · )?Обновлено (\d{2}\.\d{2}\.\d{4})\*.*(?:\r?\n)?"
)
# Строку источника забираем вместе с хвостовыми пробелами предыдущей строки:
# иначе там остается висячий перенос там, где ее приклеили к абзацу
RE_SOURCE = re.compile(r"(?m)[ \t]*\r?\n?^<sub>Источник: .*?</sub>[ \t]*")
RE_SOURCE_FIND = re.compile(r"(?m)^<sub>Источник: .*?</sub>")
RE_H1 = re.compile(r"(?m)^# .+$")


def run_git(*args: str) -> str:
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def body(text: str) -> str:
    """Текст статьи без служебных строк — по нему сравниваем версии.

    Переводы строк приводим к одному виду: в рабочей копии они CRLF, а git
    отдает LF, и без этого любой файл выглядел бы измененным."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for rx in (RE_ONELINE, RE_UPDATED, RE_READING, RE_SOURCE):
        text = rx.sub("", text)
    return text.strip()


def head_version(rel: str) -> str | None:
    out = run_git("show", f"HEAD:{rel}")
    return out or None


def git_content_date(rel: str) -> date | None:
    """Дата последней правки содержимого — без коммитов переименования."""
    out = run_git("log", "--follow", "--diff-filter=AM", "-1", "--format=%cI", "--", rel)
    if not out:
        return None
    try:
        return datetime.fromisoformat(out).date()
    except ValueError:
        return None


def estimate_minutes(text: str) -> int:
    images = len(re.findall(r"!\[[^\]]*\]\(", text))
    plain = re.sub(r"```.*?```", " ", text, flags=re.S)
    plain = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", plain)
    plain = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", plain)
    plain = re.sub(r"<[^>]+>", " ", plain)
    plain = re.sub(r"[#*_>`|]", " ", plain)
    words = len(plain.split())
    return max(1, math.ceil(words / 150 + images * 10 / 60))


def current_updated(text: str) -> str | None:
    m = RE_ONELINE.search(text)
    if m:
        return m.group(2)
    m = RE_UPDATED.search(text)
    return m.group(0).strip().split("**Обновлено:**")[-1].strip() if m else None


def current_reading(text: str) -> str | None:
    m = RE_ONELINE.search(text)
    if m and m.group(1):
        return f"{m.group(1)} мин."
    m = RE_READING.search(text)
    return m.group(0).strip().split("**Время чтения:**")[-1].strip() if m else None


def layout_of(text: str) -> str:
    """Какое оформление у статьи сейчас — его и сохраняем."""
    return "one" if RE_ONELINE.search(text) else "two"


def build_block(reading: str | None, updated: str, layout: str) -> str:
    if layout == "one":
        head = f"{reading} · " if reading else ""
        return f"*{head}Обновлено {updated}*"
    lines = []
    if reading:
        # два пробела на конце — иначе markdown склеит строки в одну
        lines.append(f"**Время чтения:** {reading}  ")
    lines.append(f"**Обновлено:** {updated}")
    return "\n".join(lines)


def apply(
    path: Path, today: date, keep_dates: bool = False, from_git: bool = False
) -> str | None:
    rel = path.relative_to(ROOT).as_posix()
    text = path.read_text(encoding="utf-8")

    old = head_version(rel)
    changed = old is None or body(old) != body(text)

    updated = current_updated(text)
    if from_git:
        updated = (git_content_date(rel) or today).strftime("%d.%m.%Y")
    elif changed and not (keep_dates and updated):
        updated = today.strftime("%d.%m.%Y")
    elif not updated:
        d = git_content_date(rel) or today
        updated = d.strftime("%d.%m.%Y")

    reading = None
    if rel.startswith(READING_TIME_ROOTS):
        reading = current_reading(text) or f"{estimate_minutes(text)} мин."

    layout = layout_of(text)

    # Строку источника всегда держим на одном месте — сразу под блоком,
    # где бы она ни лежала до этого
    src = RE_SOURCE_FIND.search(text)
    source = src.group(0) if src else None

    # Вырезаем старые строки и вставляем блок сразу после заголовка
    stripped = text
    for rx in (RE_SOURCE, RE_ONELINE, RE_UPDATED, RE_READING):
        stripped = rx.sub("", stripped)
    # После вырезания строк остаются лишние пустые строки — схлопываем,
    # иначе абзацы разъезжаются при каждом прогоне
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)

    h1 = RE_H1.search(stripped)
    if not h1:
        return None

    block = build_block(reading, updated, layout)
    if source:
        block = f"{block}\n\n{source}"
    head = stripped[: h1.end()].rstrip()
    tail = stripped[h1.end() :].lstrip("\r\n")
    new = f"{head}\n\n{block}\n\n{tail}"

    if new != text:
        path.write_text(new, encoding="utf-8", newline="")
        return f"{updated}  {rel}"
    return None


def main() -> int:
    # Массовая косметическая правка (переоформили строку, поправили опечатку
    # разом во всех статьях) — не повод поднимать дату обновления везде
    keep_dates = "--keep-dates" in sys.argv or os.environ.get("KEEP_DATES") == "1"
    # Обслуживание: заново проставить даты по истории git, что бы ни лежало
    # в файлах сейчас
    from_git = "--from-git" in sys.argv

    today = date.today()
    touched = []
    for root in CONTENT_ROOTS:
        for path in sorted((ROOT / root).rglob("*.md")):
            if path.name == "README.md":
                continue
            line = apply(path, today, keep_dates, from_git)
            if line:
                touched.append(line)
    for line in touched:
        print(line)
    print(f"Обновлено файлов: {len(touched)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
