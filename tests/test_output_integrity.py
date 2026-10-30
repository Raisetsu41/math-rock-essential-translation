"""负向集成检查: 验证器必须拒绝缺页、丢图和漏字的 PDF."""

from __future__ import annotations

import sys
import unittest
from collections.abc import Callable
from pathlib import Path

import pymupdf as pdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from verify import verify


class OutputIntegrityTests(unittest.TestCase):
    def check_damage(
        self, mutation: Callable[[pdf.Document], None], expected: str
    ) -> None:
        target = ROOT / "build" / "damaged-test.pdf"
        document = pdf.open(ROOT / "Math-Rock-Essentials.pdf")
        mutation(document)
        document.save(target)
        document.close()
        try:
            with self.assertRaisesRegex(ValueError, expected):
                verify(target, False)
        finally:
            target.unlink(missing_ok=True)

    def test_rejects_missing_page(self) -> None:
        self.check_damage(
            lambda document: document.delete_page(-1), "Page count differs"
        )

    def test_rejects_lost_image(self) -> None:
        self.check_damage(
            lambda document: document[0].delete_image(document[0].get_images()[0][0]),
            "image content or placement differs",
        )

    def test_rejects_missing_translation(self) -> None:
        def remove_text(document: pdf.Document) -> None:
            page = document[4]
            rectangles = page.search_for("如何练习？")
            self.assertTrue(rectangles)
            for rectangle in rectangles:
                page.add_redact_annot(rectangle)
            page.apply_redactions(images=0, graphics=0, text=0)

        self.check_damage(remove_text, "Text missing in output")


if __name__ == "__main__":
    unittest.main()
