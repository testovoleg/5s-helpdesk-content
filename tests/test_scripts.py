"""Тесты вспомогательных функций скриптов обслуживания.

Запуск из корня репозитория:

    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_script(filename: str):
    spec = importlib.util.spec_from_file_location(
        filename.replace("-", "_").removesuffix(".py"), ROOT / ".scripts" / filename
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gi = load_script("generate-index.py")
um = load_script("update-meta.py")
cc = load_script("check-content.py")


class EstimateMinutesTest(unittest.TestCase):
    def test_minutes_by_words(self):
        text = " ".join(["слово"] * 150)
        self.assertEqual(um.estimate_minutes(text), 1)
        self.assertEqual(um.estimate_minutes(text + " ещё"), 2)

    def test_screenshot_adds_ten_seconds(self):
        text = " ".join(["слово"] * 150) + " ![подпись](attachments/a.png)"
        self.assertEqual(um.estimate_minutes(text), 2)

    def test_markdown_markup_is_not_words(self):
        text = "**Жирный** текст [ссылка](https://example.com) `<b>`"
        self.assertEqual(um.estimate_minutes(text), 1)


class BuildBlockTest(unittest.TestCase):
    def test_table_with_reading_time(self):
        self.assertEqual(
            um.build_block("11 мин.", "25.08.2026", "Обновлено", "table"),
            "<table><tr><td><b>Время чтения:</b> 11 мин.</td>"
            "<td><b>Обновлено:</b> 25.08.2026</td></tr></table>",
        )

    def test_one_line_without_reading_time(self):
        self.assertEqual(
            um.build_block(None, "24.08.2026", "Обновлено", "one"),
            "*Обновлено 24.08.2026*",
        )

    def test_two_lines(self):
        self.assertEqual(
            um.build_block(None, "24.08.2026", "Создано", "two"),
            "**Создано:** 24.08.2026",
        )


class ExtractMetaTest(unittest.TestCase):
    def write(self, text: str) -> Path:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "a.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_table(self):
        path = self.write(
            "# Заголовок\n\n<table><tr><td><b>Время чтения:</b> 11 мин.</td>"
            "<td><b>Обновлено:</b> 25.08.2026</td></tr></table>\n"
        )
        meta = gi.extract_meta(path)
        self.assertEqual(meta["updated_at"], "2026-08-25")
        self.assertEqual(meta["reading_time"], 11)
        self.assertEqual(meta["date_kind"], "updated")

    def test_one_line(self):
        path = self.write("# Заголовок\n\n*5 мин. · Создано 01.02.2026*\n")
        meta = gi.extract_meta(path)
        self.assertEqual(meta["updated_at"], "2026-02-01")
        self.assertEqual(meta["reading_time"], 5)
        self.assertEqual(meta["date_kind"], "created")

    def test_two_lines(self):
        path = self.write(
            "# Заголовок\n\n**Время чтения:** 3 мин.  \n**Обновлено:** 07.09.2026\n"
        )
        meta = gi.extract_meta(path)
        self.assertEqual(meta["updated_at"], "2026-09-07")
        self.assertEqual(meta["reading_time"], 3)

    def test_test_time(self):
        path = self.write(
            "# Тест\n\n"
            "<table><tr><td><b>Время прохождения:</b> 30 мин.</td></tr></table>\n"
        )
        self.assertEqual(gi.extract_meta(path)["test_time"], 30)

        unlimited = self.write(
            "# Тест\n\n"
            "<table><tr><td><b>Время прохождения:</b> не ограничено</td></tr></table>\n"
        )
        self.assertIsNone(gi.extract_meta(unlimited)["test_time"])


class HistoryTest(unittest.TestCase):
    def test_new_date_is_added(self):
        old = [{"date": "2026-10-27", "kind": "updated"}]
        self.assertEqual(
            gi.merge_history(old, "2026-10-29", "updated"),
            [
                {"date": "2026-10-27", "kind": "updated"},
                {"date": "2026-10-29", "kind": "updated"},
            ],
        )

    def test_rolled_back_date_drops_later_entries(self):
        old = [
            {"date": "2026-10-27", "kind": "updated"},
            {"date": "2026-10-29", "kind": "updated"},
        ]
        self.assertEqual(
            gi.merge_history(old, "2026-10-27", "created"),
            [{"date": "2026-10-27", "kind": "created"}],
        )


class FileHelpersTest(unittest.TestCase):
    def test_blob_sha_normalizes_crlf(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "a.md"
        path.write_bytes(b"hello\r\n")
        expected = hashlib.sha1(b"blob 6\0hello\n").hexdigest()
        self.assertEqual(gi.blob_sha(path), expected)

    def test_read_order_skips_comments_hidden_and_preserves_paths(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        order = Path(folder.name) / ".order"
        order.write_text("# id: section\n\nA\n- B\n../c\n", encoding="utf-8")
        self.assertEqual(gi.read_order(Path(folder.name)), ["A", "../c"])


class LinkParserTest(unittest.TestCase):
    def test_balanced_parentheses_in_path(self):
        url = "../Ошибка%20код%209%20(служба%20Dual)/file.md"
        links = list(cc.iter_links(f"[текст]({url})"))
        self.assertEqual(links, [(1, url, False)])

    def test_title_is_dropped(self):
        self.assertEqual(list(cc.iter_links('[x](a.md "заголовок")'))[0][1], "a.md")

    def test_images_are_marked(self):
        self.assertEqual(list(cc.iter_links("![alt](a.png)"))[0][2], True)

    def test_code_is_masked(self):
        text = "```\n[x](missing.md)\n```\n[y](ok.md)"
        masked = cc.mask_code(text)
        self.assertNotIn("missing.md", masked)
        self.assertIn("ok.md", masked)

    def test_anchor_slug_keeps_double_hyphen(self):
        found = cc.anchors('## Работа с документами "Приобретение товаров / в пути"')
        self.assertIn("работа-с-документами-приобретение-товаров--в-пути", found)

    def test_duplicate_heading_gets_suffix(self):
        found = cc.anchors("# Печать этикеток\n\n## Печать этикеток")
        self.assertIn("печать-этикеток", found)
        self.assertIn("печать-этикеток-1", found)

    def test_explicit_anchor(self):
        self.assertIn("param_serv", cc.anchors('<a id="param_serv"></a>\n## Раздел'))

    def test_poster_image_inside_link(self):
        links = cc.iter_links("[![подпись](attachments/video-1.png)](https://x/y.mp4)")
        self.assertIn((1, "attachments/video-1.png", True), links)
        self.assertIn((1, "https://x/y.mp4", False), links)


class StagedMaterialsTest(unittest.TestCase):
    def test_only_existing_materials_are_kept(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        (root / "tips" / "A").mkdir(parents=True)
        (root / "tips" / "A" / "a.md").write_text("# A\n", encoding="utf-8")
        old_root = um.ROOT
        um.ROOT = root
        self.addCleanup(lambda: setattr(um, "ROOT", old_root))
        result = um.relevant_staged(
            ["tips/A/a.md", "README.md", "lessons/b.md", "other/x.md"]
        )
        self.assertEqual(
            [p.relative_to(root).as_posix() for p in result], ["tips/A/a.md"]
        )


class IndexContentTest(unittest.TestCase):
    def test_generated_at_is_ignored(self):
        self.assertTrue(
            gi.same_content(
                {"generated_at": "2026-11-25T10:00:00+03:00", "count": 1},
                {"generated_at": "2026-11-25T11:00:00+03:00", "count": 1},
            )
        )

    def test_content_change_is_detected(self):
        self.assertFalse(
            gi.same_content(
                {"generated_at": "2026-11-25T10:00:00+03:00", "count": 1},
                {"generated_at": "2026-11-25T10:00:00+03:00", "count": 2},
            )
        )


if __name__ == "__main__":
    unittest.main()
