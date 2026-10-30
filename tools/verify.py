"""验证全书图片、矢量图、字号、链接、页面几何与文字覆盖率, 并渲染校样."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pymupdf as pdf
from inspect_source import ROOT, SOURCE, load_locked_layout
from PIL import Image, ImageChops, ImageDraw

from build import inline_underlines, load_translations


def image_signature(page: pdf.Page) -> list:
    return sorted(
        (info["digest"].hex(), tuple(round(value, 3) for value in info["bbox"]))
        for info in page.get_image_info(hashes=True)
    )


def link_signature(page: pdf.Page) -> list:
    return sorted(
        repr(
            {
                key: (
                    tuple(round(v, 3) for v in value)
                    if isinstance(value, (pdf.Rect, pdf.Point))
                    else value
                )
                for key, value in sorted(link.items())
                if key not in {"xref", "id", "from"}
            }
        )
        for link in page.get_links()
    )


def drawing_signature(page: pdf.Page, excluded: list[dict] | None = None) -> list:
    excluded = excluded or []
    return [
        repr(
            {key: value for key, value in path.items() if key not in {"seqno", "layer"}}
        )
        for path in page.get_drawings()
        if path not in excluded
    ]


def cover_changes_outside_titles(original: pdf.Page, translated: pdf.Page) -> bool:
    images = []
    for page in (original, translated):
        pixmap = page.get_pixmap()
        images.append(
            Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        )
    difference = ImageChops.difference(*images)
    draw = ImageDraw.Draw(difference)
    draw.rectangle((39, 64, 556, 251), fill="black")
    draw.rectangle((39, 724, 556, 831), fill="black")
    return difference.getbbox() is not None


def verify(target: Path, render: bool) -> dict:
    source = pdf.open(SOURCE)
    result = pdf.open(target)
    layout = load_locked_layout()
    placements = json.loads(
        (ROOT / "build/placements.json").read_text(encoding="utf-8")
    )
    translations = load_translations()
    errors = []
    if len(source) != len(result):
        errors.append("Page count differs")
    cover_unchanged = not cover_changes_outside_titles(source[0], result[0])
    if not cover_unchanged:
        errors.append("Cover changed outside translated title areas")
    image_count = 0
    link_count = 0
    vector_count = 0
    moved_underlines = 0
    inline_identifiers = set(
        json.loads((ROOT / "translation/inline-links.json").read_text(encoding="utf-8"))
    )
    for page_index, (original, translated) in enumerate(zip(source, result), 1):
        if (
            original.mediabox != translated.mediabox
            or original.cropbox != translated.cropbox
            or original.rotation != translated.rotation
        ):
            errors.append(f"Page {page_index}: page geometry differs")
        if image_signature(original) != image_signature(translated):
            errors.append(f"Page {page_index}: image content or placement differs")
        if link_signature(original) != link_signature(translated):
            errors.append(f"Page {page_index}: links differ")
        original_underlines = inline_underlines(
            original, layout["pages"][page_index - 1]["blocks"], inline_identifiers
        )
        translated_underlines = inline_underlines(
            translated, layout["pages"][page_index - 1]["blocks"], inline_identifiers
        )
        original_paths = drawing_signature(original, original_underlines)
        translated_paths = drawing_signature(translated, translated_underlines)
        if page_index == 1:
            translated_paths = translated_paths[: len(original_paths)]
        if original_paths != translated_paths:
            errors.append(f"Page {page_index}: original vector paths differ")
        image_count += len(original.get_image_info())
        link_count += len(original.get_links())
        vector_count += len(original_paths)
        moved_underlines += len(original_underlines)
        if "\ufffd" in translated.get_text():
            errors.append(f"Page {page_index}: replacement character found")
    block_map = {
        block["id"]: block for page in layout["pages"] for block in page["blocks"]
    }
    for placement in placements:
        if placement["identifier"] == "cover":
            continue
        block = block_map[placement["identifier"]]
        if not any(
            abs(span["size"] - placement["size"]) < 0.001 for span in block["spans"]
        ):
            errors.append(f"Font size differs: {placement['identifier']}")
        if not any(
            abs(span["origin"][1] - placement["y"]) < 0.15 for span in block["spans"]
        ):
            errors.append(f"Baseline differs: {placement['identifier']}")
        if placement["x"] < 71 and placement["identifier"] not in {"p002-b06"}:
            errors.append(f"Left margin exceeded: {placement['identifier']}")
        if placement["x"] + placement["width"] > max(block["bbox"][2], 523.8) + 0.15:
            errors.append(f"Right margin exceeded: {placement['identifier']}")
    # 对实际输出重新提字, 检查每一条排入的译文, 不只检查内存中的排版计划.
    chinese_fonts = set()
    for page_number in range(1, len(result) + 1):
        extracted = re.sub(r"\s+", "", result[page_number - 1].get_text()).replace(
            "‐", "-"
        )
        actual_spans = [
            span
            for block in result[page_number - 1].get_text(
                "dict", flags=pdf.TEXTFLAGS_DICT & ~pdf.TEXT_PRESERVE_IMAGES
            )["blocks"]
            if block["type"] == 0
            for line in block["lines"]
            for span in line["spans"]
        ]
        chinese_fonts.update(
            span["font"]
            for span in actual_spans
            if re.search(r"[\u3400-\u9fff]", span["text"])
        )
        for placement in (item for item in placements if item["page"] == page_number):
            text = re.sub(r"\s+", "", placement["text"])
            if text not in extracted:
                errors.append(
                    f"Text missing in output: {placement['identifier']}: {text[:45]}"
                )
            if placement["text"].strip() and not any(
                abs(span["origin"][0] - placement["x"]) < 0.1
                and abs(span["origin"][1] - placement["y"]) < 0.1
                and abs(span["size"] - placement["size"]) < 0.01
                for span in actual_spans
            ):
                errors.append(
                    f"Actual output font size or position differs: {placement['identifier']}"
                )
    report = {
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "pages": len(result),
        "image_instances_preserved": image_count,
        "links_preserved": link_count,
        "vector_paths_preserved": vector_count,
        "inline_link_underlines_relocated": moved_underlines,
        "cover_unchanged_outside_title_areas": cover_unchanged,
        "translated_blocks": len(translations),
        "typeset_lines_or_cells": len(placements),
        "chinese_fonts": sorted(chinese_fonts),
        "font_sizes_pt": sorted(
            {
                round(item["size"], 2)
                for item in placements
                if item["identifier"] != "cover"
            }
        ),
        "errors": errors,
    }
    (ROOT / "build/qa.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if render:
        directory = ROOT / "build/render"
        directory.mkdir(parents=True, exist_ok=True)
        for index, page in enumerate(result, 1):
            page.get_pixmap(matrix=pdf.Matrix(1.5, 1.5)).save(
                directory / f"page-{index:03d}.png"
            )
        for start in range(0, len(result), 12):
            sheet = Image.new("RGB", (4 * 360, 3 * 530), "#ddd")
            draw = ImageDraw.Draw(sheet)
            for offset, index in enumerate(range(start, min(start + 12, len(result)))):
                image = Image.open(directory / f"page-{index + 1:03d}.png")
                image.thumbnail((350, 500))
                x, y = (offset % 4) * 360 + 5, (offset // 4) * 530 + 25
                sheet.paste(image, (x, y))
                draw.text((x, y - 20), f"PDF {index + 1} / book {index}", fill="black")
            sheet.save(directory / f"contact-{start // 12 + 1:02d}.png")
    if errors:
        raise ValueError("Verification failed:\n" + "\n".join(errors))
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs/verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=ROOT / "Math-Rock-Essentials.pdf")
    parser.add_argument("--render", action="store_true")
    arguments = parser.parse_args()
    print(
        json.dumps(
            verify(arguments.pdf, arguments.render), ensure_ascii=False, indent=2
        )
    )
