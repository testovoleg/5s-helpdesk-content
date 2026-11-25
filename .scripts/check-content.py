#!/usr/bin/env python3
"""Проверка материалов базы знаний без правок.

Что проверяется:
  * относительные ссылки и якоря, картинки и вложения;
  * цели строк в .order;
  * пути в .unpublished;
  * повторы id материалов;
  * адреса в строках «Опубликовано»;
  * актуальность index.json.

Ошибки дают код возврата 1. Предупреждения (вложения без ссылок,
абсолютные ссылки на kb.5systems.ru в тексте) печатаются, но не мешают.

    python3 .scripts/check-content.py           # проверка
    python3 .scripts/check-content.py --stats   # ещё и сводка по ссылкам
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOTS = ("articles", "tips", "lessons")
INDEX_PATH = ROOT / "index.json"

SKIP_PREFIXES = ("http://", "https://", "//", "mailto:", "tel:", "data:", "ftp://")
CALLOUTS = {"note", "tip", "important", "warning", "caution"}

# Ссылка на сайт базы знаний в тексте: по правилам должна быть относительной
SITE_HOST = "kb.5systems.ru"


def setup_streams() -> None:
    # На Windows консоль по умолчанию cp1251 и падает на кириллице
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def run_git(*args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-c", "core.quotepath=false", *args],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError):
        return None


def mask_code(text: str) -> str:
    """Заменить код пробелами, сохранив переносы строк: ссылки в примерах
    кода проверять не нужно, а номера строк должны остаться прежними."""

    def blank(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    text = re.sub(
        r"(?ms)^[ \t]*(`{3,}|~{3,}).*?^[ \t]*\1[^\n]*$", blank, text
    )
    return re.sub(r"`[^`\n]*`", blank, text)


def _close_bracket(text: str, start: int) -> int | None:
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "\\":
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return i
        elif ch == "\n" and depth == 0:
            return None
    return None


def _parse_destination(text: str, open_paren: int) -> tuple[str | None, int]:
    """Адрес внутри (...) с учётом вложенных скобок — они встречаются
    в именах папок, например «Ошибка авторизации код 9 (…)»."""
    depth = 1
    i = open_paren + 1
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "\n":
            return None, i
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    else:
        return None, i

    inner = text[open_paren + 1 : i].strip()
    if not inner:
        return "", i + 1
    if inner.startswith("<") and ">" in inner:
        return inner[1 : inner.index(">")], i + 1
    return inner.split()[0], i + 1


def iter_links(text: str) -> list[tuple[int, str, bool]]:
    """Ссылки и картинки: (номер строки, адрес, это картинка).

    Картинки разбираем отдельным проходом: постер видео оформлен вложенной
    ссылкой `[![подпись](постер.png)](ролик.mp4)`, и разбор «снаружи внутрь»
    пропустил бы картинку."""
    images: list[tuple[int, str, bool]] = []
    i = 0
    while i < len(text):
        if text[i] == "!" and i + 1 < len(text) and text[i + 1] == "[":
            close = _close_bracket(text, i + 1)
            if close is not None and close + 1 < len(text) and text[close + 1] == "(":
                url, end = _parse_destination(text, close + 1)
                if url is not None:
                    images.append((text.count("\n", 0, i) + 1, url, True))
                    i = end
                    continue
        i += 1

    links: list[tuple[int, str, bool]] = []
    i = 0
    while i < len(text):
        if text[i] == "[" and (i == 0 or text[i - 1] != "!"):
            close = _close_bracket(text, i)
            if close is not None and close + 1 < len(text) and text[close + 1] == "(":
                url, end = _parse_destination(text, close + 1)
                if url is not None:
                    links.append((text.count("\n", 0, i) + 1, url, False))
                    i = end
                    continue
        i += 1
    return images + links


def slug(heading: str) -> str:
    """Якорь заголовка по правилам GitHub: пунктуация убирается, каждый
    пробел становится дефисом (два пробела — два дефиса)."""
    value = heading.strip().lower()
    value = re.sub(r"[^\w\- ]", "", value, flags=re.UNICODE)
    return value.replace(" ", "-")


def anchors(text: str) -> set[str]:
    """Якоря файла: заголовки и явные `<a id="…">`.

    Повторяющийся заголовок получает суффикс, как на GitHub: второй —
    `-1`, третий — `-2`; на такие якоря ссылается «Содержание»."""
    found: set[str] = set()
    seen: dict[str, int] = {}
    for line in text.splitlines():
        match = re.match(r"^#{1,6}\s+(.*)$", line)
        if not match:
            continue
        base = slug(match.group(1))
        if base in seen:
            seen[base] += 1
            found.add(f"{base}-{seen[base]}")
        else:
            seen[base] = 0
            found.add(base)
    found |= set(re.findall(r'<a\s+(?:id|name)="([^"]+)"', text))
    return found


def material_dirs():
    """Папки материалов: в них есть .md, кроме README."""
    for root in CONTENT_ROOTS:
        root_path = ROOT / root
        if not root_path.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if d not in ("attachments", ".git")]
            mds = [
                f for f in filenames if f.endswith(".md") and f != "README.md"
            ]
            if not mds:
                continue
            yield Path(dirpath), mds


def check_links(
    md: Path, referenced: set[Path], errors: list[str], warnings: list[str]
) -> dict:
    """Ссылки и картинки одного материала."""
    stats = {"folder_links": 0, "site_links": 0}
    try:
        text = md.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{md.relative_to(ROOT)}: не читается ({exc})")
        return stats

    masked = mask_code(text)
    own = anchors(text)
    base = md.parent
    rel_md = md.relative_to(ROOT).as_posix()

    links = list(iter_links(masked))
    # HTML-ссылки и картинки
    for match in re.finditer(r'(?:src|href)="([^"]+)"', masked):
        links.append((masked.count("\n", 0, match.start()) + 1, match.group(1), match.group(0).startswith("src=")))

    for line, url, is_image in links:
        url = url.strip()
        if not url or url.startswith("#"):
            if url.startswith("#") and len(url) > 1:
                if unquote(url[1:]) not in own:
                    errors.append(f"{rel_md}:{line}: нет якоря {url}")
            continue
        if url.startswith(SKIP_PREFIXES):
            if SITE_HOST in url and not is_image:
                source_line = text.splitlines()[line - 1] if line <= len(text.splitlines()) else ""
                if "Опубликовано" not in source_line:
                    stats["site_links"] += 1
            continue

        path_part, _, fragment = url.partition("#")
        target = (base / unquote(path_part))
        try:
            target.resolve().relative_to(ROOT)
        except ValueError:
            errors.append(f"{rel_md}:{line}: ссылка выходит за пределы репозитория: {url}")
            continue

        if path_part.endswith("/"):
            stats["folder_links"] += 1
            if not target.is_dir():
                errors.append(f"{rel_md}:{line}: нет раздела {path_part}")
            continue

        if not target.exists():
            kind = "картинка" if is_image else "ссылка"
            errors.append(f"{rel_md}:{line}: {kind} ведёт в никуда: {path_part}")
            continue

        referenced.add(target.resolve())

        if is_image and target.is_dir():
            errors.append(f"{rel_md}:{line}: картинка указывает на папку: {path_part}")
            continue

        if fragment and target.is_file():
            try:
                target_text = target.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if unquote(fragment) not in anchors(target_text):
                errors.append(
                    f"{rel_md}:{line}: нет якоря #{unquote(fragment)} "
                    f"в {target.relative_to(ROOT).as_posix()}"
                )
    return stats


def check_orders(errors: list[str], warnings: list[str]) -> None:
    for order in ROOT.rglob(".order"):
        if ".git" in order.parts:
            continue
        if order.relative_to(ROOT).parts[0] not in CONTENT_ROOTS:
            continue
        rel = order.relative_to(ROOT).as_posix()
        for num, raw in enumerate(order.read_text(encoding="utf-8").splitlines(), 1):
            name = raw.strip()
            if not name or name.startswith("#"):
                continue
            hidden = name.startswith("-") and not name.startswith("- ")
            if hidden:
                name = name[1:].strip()
            target = order.parent / name
            if target.exists():
                continue
            message = f"{rel}:{num}: нет цели «{name}»"
            # В уроках .order — ещё и план переноса: отсутствующий урок нормален
            if order.relative_to(ROOT).parts[0] == "lessons":
                warnings.append(message)
            else:
                errors.append(message)


def check_unpublished(errors: list[str]) -> None:
    path = ROOT / ".unpublished"
    if not path.exists():
        return
    for num, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        name = raw.strip()
        if not name or name.startswith("#"):
            continue
        if not (ROOT / name).is_dir():
            errors.append(f".unpublished:{num}: нет папки «{name}»")


def check_duplicate_ids(errors: list[str]) -> None:
    seen: dict[tuple[str, str], str] = {}
    for folder, mds in material_dirs():
        main = "ARTICLE.md" if "ARTICLE.md" in mds else sorted(mds)[0]
        key = (folder.relative_to(ROOT).parts[0], main[:-3])
        rel = folder.relative_to(ROOT).as_posix()
        if key in seen:
            errors.append(f"повторяется id {key[0]}/{key[1]}: {seen[key]} и {rel}")
        else:
            seen[key] = rel


def section_paths(index: dict) -> dict[str, str]:
    """Путь раздела → цепочка id (для проверки адресов «Опубликовано»)."""

    def walk(nodes: list[dict], prefix: list[str], result: dict[str, str]) -> None:
        for node in nodes:
            chain = prefix + [node.get("id") or ""]
            result[node["path"]] = "/".join(chain)
            if node.get("sections"):
                walk(node["sections"], chain, result)

    result: dict[str, str] = {}
    for root, nodes in index.get("sections", {}).items():
        walk(nodes, [root], result)
    return result


PUBLISHED = re.compile(r"Опубликовано[^\n]*?\((https://kb\.5systems\.ru/[^)\s]+)\)")


def check_published(index: dict, errors: list[str]) -> None:
    chains = section_paths(index)
    for material in index.get("materials", []):
        folder = material["path"]
        chain = chains.get(folder)
        if not chain or "//" in chain:
            continue
        md = ROOT / folder / material["file"]
        try:
            text = md.read_text(encoding="utf-8")
        except OSError:
            continue
        match = PUBLISHED.search(text)
        if not match:
            continue
        expected = f"/{chain}/{material['id']}"
        actual = urlparse(match.group(1)).path.rstrip("/")
        if actual != expected:
            errors.append(
                f"{folder}: адрес «Опубликовано» {actual} не совпадает с текущим "
                f"{expected}"
            )


def check_index(errors: list[str]) -> None:
    script = ROOT / ".scripts" / "generate-index.py"
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    if proc.returncode != 0:
        detail = (proc.stdout + proc.stderr).strip()
        errors.append("index.json: " + detail.replace("\n", "\n  "))


def check_callouts(md: Path, warnings: list[str]) -> int:
    try:
        text = md.read_text(encoding="utf-8")
    except OSError:
        return 0
    count = 0
    for match in re.finditer(r"(?m)^>\s*\[!([A-Za-z]+)\]", text):
        count += 1
        if match.group(1).lower() not in CALLOUTS:
            line = text.count("\n", 0, match.start()) + 1
            warnings.append(
                f"{md.relative_to(ROOT).as_posix()}:{line}: неизвестный тип выноски "
                f"[!{match.group(1)}]"
            )
    return count


def unused_attachments(referenced: set[Path]) -> list[Path]:
    unused = []
    for folder in ROOT.rglob("attachments"):
        if ".git" in folder.parts:
            continue
        if folder.relative_to(ROOT).parts[0] not in CONTENT_ROOTS:
            continue
        for path in folder.rglob("*"):
            if path.is_file() and path.resolve() not in referenced:
                unused.append(path)
    return unused


def print_stats(
    index: dict,
    stats: dict,
    unused: list[Path],
    callouts: int,
) -> None:
    by_type: dict[str, int] = {}
    for material in index.get("materials", []):
        by_type[material["type"]] = by_type.get(material["type"], 0) + 1
    print("Сводка:")
    print(f"  материалов: {index.get('count', 0)} ({', '.join(f'{k} — {v}' for k, v in by_type.items())})")
    print(f"  ссылок на папки разделов: {stats['folder_links']}")
    print(f"  абсолютных ссылок на {SITE_HOST} в тексте: {stats['site_links']}")
    print(f"  блоков-выносок: {callouts}")
    print(f"  вложений без ссылок: {len(unused)}")
    if unused:
        size = sum(p.stat().st_size for p in unused) / 1024 / 1024
        print(f"  их объем: {size:.1f} МБ")


def main() -> int:
    setup_streams()
    errors: list[str] = []
    warnings: list[str] = []

    materials = list(material_dirs())
    referenced: set[Path] = set()
    stats = {"folder_links": 0, "site_links": 0}
    callouts = 0

    for folder, mds in materials:
        main_file = "ARTICLE.md" if "ARTICLE.md" in mds else sorted(mds)[0]
        md = folder / main_file
        found = check_links(md, referenced, errors, warnings)
        stats["folder_links"] += found["folder_links"]
        stats["site_links"] += found["site_links"]
        callouts += check_callouts(md, warnings)

    # Файл заметок «Что нового» тоже содержит ссылки
    notes_dir = ROOT / "whats-new"
    if notes_dir.is_dir():
        for md in notes_dir.glob("*.md"):
            check_links(md, referenced, errors, warnings)

    check_orders(errors, warnings)
    check_unpublished(errors)
    check_duplicate_ids(errors)

    index: dict = {}
    try:
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        errors.append("index.json не читается")
    else:
        check_published(index, errors)
        check_index(errors)

    unused = unused_attachments(referenced)
    tracked = set()
    listing = run_git("ls-files", "-z")
    if listing:
        tracked = {path for path in listing.split("\0") if path}
    untracked_unused = []
    for path in unused:
        rel = path.relative_to(ROOT).as_posix()
        if rel in tracked:
            warnings.append(f"вложение без ссылок: {rel}")
        else:
            untracked_unused.append(path)
    if untracked_unused:
        size = sum(p.stat().st_size for p in untracked_unused) / 1024 / 1024
        warnings.append(
            f"вложений без ссылок вне git: {len(untracked_unused)} ({size:.1f} МБ) — "
            "локальные файлы, на репозиторий не влияют"
        )

    if "--stats" in sys.argv:
        print_stats(index, stats, unused, callouts)
        print()

    print(f"Проверено материалов: {len(materials)}")
    for message in errors:
        print(f"ОШИБКА: {message}")
    for message in warnings:
        print(f"предупреждение: {message}")
    print(f"Итого: ошибок — {len(errors)}, предупреждений — {len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
