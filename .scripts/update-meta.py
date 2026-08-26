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

# Подпись у даты: "Создано", если материал с тех пор не правили, иначе
# "Обновлено". Читателю важно понимать, на какое число статья актуальна
LABEL_NEW = "Создано"
LABEL_OLD = "Обновлено"
LABELS = f"(?:{LABEL_NEW}|{LABEL_OLD})"

RE_READING = re.compile(r"(?m)^\*\*Время чтения:\*\* .*(?:\r?\n)?")
RE_UPDATED = re.compile(rf"(?m)^\*\*{LABELS}:\*\* .*(?:\r?\n)?")
# Тот же блок, свернутый в одну строку: *11 мин. · Обновлено 25.08.2026*
RE_ONELINE = re.compile(
    rf"(?m)^\*(?:(\d+) мин\. · )?({LABELS}) (\d{{2}}\.\d{{2}}\.\d{{4}})\*.*(?:\r?\n)?"
)
# ...и он же таблицей в одну строку, время чтения и дата — в двух колонках
RE_TABLE = re.compile(
    rf"(?m)^<table><tr>"
    rf"(?:<td><b>Время чтения:</b> (\d+) мин\.</td>)?"
    rf"<td><b>({LABELS}):</b> (\d{{2}}\.\d{{2}}\.\d{{4}})</td>"
    rf"</tr></table>[ \t]*(?:\r?\n)?"
)
# Строку источника забираем вместе с хвостовыми пробелами предыдущей строки:
# иначе там остается висячий перенос там, где ее приклеили к абзацу
RE_SOURCE = re.compile(r"(?m)[ \t]*\r?\n?^<sub>Источник: .*?</sub>[ \t]*")
RE_SOURCE_FIND = re.compile(r"(?m)^<sub>Источник: .*?</sub>")
# Как строка источника выглядела раньше — нужна только при сравнении версий
RE_SOURCE_OLD = re.compile(r"(?m)^\*\*Источник:\*\* .*(?:\r?\n)?")
# Признак переноса со старой базы знаний
RE_SOURCE_SITE = re.compile(r"(?m)^<sub>Источник: https?://(?:www\.)?5systems\.ru/help/")
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
    for rx in (
        RE_TABLE,
        RE_ONELINE,
        RE_UPDATED,
        RE_READING,
        RE_SOURCE,
        RE_SOURCE_OLD,
    ):
        text = rx.sub("", text)
    # Пустые строки и хвостовые пробелы к общему виду: их двигало
    # переоформление шапки, а текст статьи при этом не менялся
    text = "\n".join(ln.rstrip() for ln in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def head_version(rel: str) -> str | None:
    out = run_git("show", f"HEAD:{rel}")
    return out or None


def content_history(rel: str) -> list[date]:
    """Даты коммитов, в которых реально менялся текст материала.

    Служебные строки и строку источника не считаем: их правили разом во всех
    статьях, и без такой фильтрации любой материал выглядел бы обновленным.
    Путь берем на момент каждого коммита — до переименования он был другим."""
    out = run_git(
        "log", "--follow", "--diff-filter=AM", "--format=%x00%H %cI", "--name-only",
        "--", rel,
    )
    commits: list[tuple[str, str, str]] = []
    for chunk in out.split("\x00"):
        lines = [ln for ln in chunk.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        sha, iso = lines[0].split(" ", 1)
        commits.append((sha, iso, lines[1]))

    dates: list[date] = []
    prev: str | None = None
    for sha, iso, path in reversed(commits):  # от старых к новым
        blob = run_git("show", f"{sha}:{path}")
        current = body(blob)
        if current != prev:
            try:
                dates.append(datetime.fromisoformat(iso).date())
            except ValueError:
                pass
            prev = current
    return dates


def git_content_date(rel: str) -> date | None:
    """Дата последней правки содержимого."""
    dates = content_history(rel)
    return dates[-1] if dates else None


def estimate_minutes(text: str) -> int:
    images = len(re.findall(r"!\[[^\]]*\]\(", text))
    plain = re.sub(r"```.*?```", " ", text, flags=re.S)
    plain = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", plain)
    plain = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", plain)
    plain = re.sub(r"<[^>]+>", " ", plain)
    plain = re.sub(r"[#*_>`|]", " ", plain)
    words = len(plain.split())
    return max(1, math.ceil(words / 150 + images * 10 / 60))


RE_TWOLINE = re.compile(rf"(?m)^\*\*({LABELS}):\*\* (\d{{2}}\.\d{{2}}\.\d{{4}})")


def current_date_and_label(text: str) -> tuple[str | None, str | None]:
    for rx in (RE_ONELINE, RE_TABLE):
        m = rx.search(text)
        if m:
            return m.group(3), m.group(2)
    m = RE_TWOLINE.search(text)
    return (m.group(2), m.group(1)) if m else (None, None)


def current_reading(text: str) -> str | None:
    for rx in (RE_ONELINE, RE_TABLE):
        m = rx.search(text)
        if m and m.group(1):
            return f"{m.group(1)} мин."
    m = RE_READING.search(text)
    return m.group(0).strip().split("**Время чтения:**")[-1].strip() if m else None


def layout_of(text: str, rel: str) -> str:
    """Оформление блока: какое стоит в файле, такое и сохраняем.

    Для новых материалов — вид по умолчанию: таблица. В статьях в ней две
    колонки (время чтения и дата), в советах одна — только дата."""
    if RE_TABLE.search(text):
        return "table"
    if RE_ONELINE.search(text):
        return "one"
    if RE_UPDATED.search(text) or RE_READING.search(text):
        return "two"
    return "table"


def build_block(reading: str | None, updated: str, label: str, layout: str) -> str:
    if layout == "one":
        head = f"{reading} · " if reading else ""
        return f"*{head}{label} {updated}*"
    if layout == "table":
        cells = ""
        if reading:
            cells += f"<td><b>Время чтения:</b> {reading}</td>"
        cells += f"<td><b>{label}:</b> {updated}</td>"
        return f"<table><tr>{cells}</tr></table>"
    lines = []
    if reading:
        # два пробела на конце — иначе markdown склеит строки в одну
        lines.append(f"**Время чтения:** {reading}  ")
    lines.append(f"**{label}:** {updated}")
    return "\n".join(lines)


def apply(
    path: Path, today: date, keep_dates: bool = False, from_git: bool = False
) -> str | None:
    rel = path.relative_to(ROOT).as_posix()
    text = path.read_text(encoding="utf-8")

    old = head_version(rel)
    changed = old is None or body(old) != body(text)

    # У статьи, перенесенной со старой базы знаний, своя история: там ее уже
    # правили. Поэтому подпись всегда "Обновлено", а дата — сайтовая, пока мы
    # текст не тронули
    transferred = bool(RE_SOURCE_SITE.search(text))

    updated, label = current_date_and_label(text)

    # первый коммит перенесенной статьи — не наша правка, а перенос:
    # дату оставляем сайтовую, ее проставили руками при переносе
    first_transfer = transferred and old is None and bool(updated)

    if from_git:
        history = content_history(rel)
        updated = (history[-1] if history else today).strftime("%d.%m.%Y")
        label = LABEL_OLD if len(history) > 1 else LABEL_NEW
    elif changed and not (keep_dates and updated) and not first_transfer:
        updated = today.strftime("%d.%m.%Y")
        # текст поправили — значит материал уже не просто создан
        label = LABEL_OLD if old is not None else LABEL_NEW
    elif not updated:
        history = content_history(rel)
        updated = (history[-1] if history else today).strftime("%d.%m.%Y")
        label = LABEL_OLD if len(history) > 1 else LABEL_NEW

    label = LABEL_OLD if transferred else (label or LABEL_NEW)

    reading = None
    if rel.startswith(READING_TIME_ROOTS):
        reading = current_reading(text) or f"{estimate_minutes(text)} мин."

    layout = layout_of(text, rel)

    # Строку источника всегда держим на одном месте — сразу под блоком,
    # где бы она ни лежала до этого
    src = RE_SOURCE_FIND.search(text)
    source = src.group(0) if src else None

    # Вырезаем старые строки и вставляем блок сразу после заголовка
    stripped = text
    for rx in (RE_SOURCE, RE_TABLE, RE_ONELINE, RE_UPDATED, RE_READING):
        stripped = rx.sub("", stripped)
    # После вырезания строк остаются лишние пустые строки — схлопываем,
    # иначе абзацы разъезжаются при каждом прогоне
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)

    h1 = RE_H1.search(stripped)
    if not h1:
        return None

    block = build_block(reading, updated, label, layout)
    if source:
        block = f"{block}\n\n{source}"
    head = stripped[: h1.end()].rstrip()
    tail = stripped[h1.end() :].lstrip("\r\n")
    new = f"{head}\n\n{block}\n\n{tail}"

    if new != text:
        path.write_text(new, encoding="utf-8", newline="")
        return f"{label} {updated}  {rel}"
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
