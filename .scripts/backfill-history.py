"""Начальное заполнение поля history в index.json по истории git.

Проходит коммиты текущей ветки от старых к новым и собирает для каждого
материала все даты, которые стояли в его шапке («Создано» / «Обновлено»).
Дальше историю ведет generate-index.py (дописывает новую дату при каждой
генерации). Запуск из корня репозитория, один раз на ветку:

    python .scripts/backfill-history.py

После запуска index.json пересобирается generate-index.py, чтобы добавить
текущие даты. Материал опознается по корню и имени md-файла (id), поэтому
переносы между папками историю не обрывают."""
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROOTS = ("tips", "articles", "lessons")
HEADER = re.compile(r"(Создано|Обновлено)[^0-9<>]{0,4}(?:</b>)?[^0-9]{0,4}(\d\d)\.(\d\d)\.(\d{4})")  # «:</b> », «: », « »

spec = importlib.util.spec_from_file_location("gi", ROOT / ".scripts" / "generate-index.py")
gi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gi)


def header_line(line: str) -> bool:
    s = line.strip()
    return s.startswith("<table>") or "Время чтения" in s or s.startswith("*") or s.startswith("**")


def main() -> int:
    log = subprocess.run(
        ["git", "-c", "core.quotepath=false", "log", "--reverse", "--no-renames",
         "--format=@@COMMIT %H", "-p", "-U0", "--", "*.md"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    hist: dict[tuple[str, str], list[dict]] = {}
    key = None
    for line in log.splitlines():
        if line.startswith("+++ "):
            path = line[4:].rstrip()  # git дописывает табуляцию к путям с пробелами
            if path.startswith('"') and path.endswith('"'):
                path = path[1:-1]
            path = path[2:] if path.startswith("b/") else path
            parts = path.split("/")
            if path == "/dev/null" or parts[0] not in ROOTS or not path.endswith(".md") or parts[-1] == "README.md":
                key = None
            else:
                key = (parts[0], parts[-1][:-3])
            continue
        if key is None or not line.startswith("+") or line.startswith("+++"):
            continue
        body = line[1:]
        if not header_line(body):
            continue
        m = HEADER.search(body)
        if not m:
            continue
        kind = "created" if m.group(1) == "Создано" else "updated"
        date = f"{m.group(4)}-{m.group(3)}-{m.group(2)}"
        hist[key] = gi.merge_history(hist.get(key), date, kind)

    index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
    n = 0
    for m in index.get("materials", []):
        h = hist.get((m.get("type"), m.get("id")))
        if h:
            m["history"] = h
            n += 1
    (ROOT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"история заполнена у {n} материалов из {len(index.get('materials', []))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
