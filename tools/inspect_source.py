"""提取原书的文字、排版和图片证据, 不修改原书."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Math Rock Essentials - Stephen Hazel.pdf"


def inspect() -> dict:
    document = pymupdf.open(SOURCE)
    pages = []
    for page_index, page in enumerate(document):
        blocks = []
        for block in page.get_text(
            "dict", flags=pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES
        )["blocks"]:
            if block["type"] != 0:
                continue
            lines = block["lines"]
            spans = [span for line in lines for span in line["spans"]]
            text = "\n".join(
                "".join(span["text"] for span in line["spans"]).rstrip()
                for line in lines
            ).strip()
            if not text:
                continue
            blocks.append(
                {
                    "id": f"p{page_index + 1:03d}-b{block['number']:02d}",
                    "text": text,
                    "bbox": list(block["bbox"]),
                    "spans": spans,
                    "lines": lines,
                }
            )
        images = [
            {
                "bbox": list(item["bbox"]),
                "digest": item["digest"].hex(),
                "width": item["width"],
                "height": item["height"],
            }
            for item in page.get_image_info(hashes=True)
        ]
        links = [
            {
                key: list(value)
                if isinstance(value, (pymupdf.Rect, pymupdf.Point))
                else value
                for key, value in link.items()
            }
            for link in page.get_links()
        ]
        pages.append(
            {
                "page": page_index + 1,
                "size": list(page.rect),
                "blocks": blocks,
                "images": images,
                "links": links,
            }
        )
    return {
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "pages": pages,
    }


def load_locked_layout() -> dict:
    lock = json.loads((ROOT / "translation/source.json").read_text(encoding="utf-8"))
    if (
        SOURCE.name != lock["file"]
        or hashlib.sha256(SOURCE.read_bytes()).hexdigest() != lock["sha256"]
    ):
        raise ValueError(
            "Source PDF changed. Review the new source and translations before updating source.json."
        )
    layout = inspect()
    if len(layout["pages"]) != lock["pages"]:
        raise ValueError("Source page count differs from source.json")
    return layout


if __name__ == "__main__":
    data = inspect()
    target = ROOT / "build" / "source-layout.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    text_path = ROOT / "build" / "source-text.txt"
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text(
        "\n\n".join(
            f"[{block['id']}] {block['text']}"
            for page in data["pages"]
            for block in page["blocks"]
        ),
        encoding="utf-8",
    )
    print(
        f"{len(data['pages'])} pages; {sum(len(page['blocks']) for page in data['pages'])} text blocks"
    )
