"""在原 PDF 上替换文字, 保留图片、矢量图、字号、基线和链接."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pymupdf as pdf
from fontTools.ttLib import TTCollection
from inspect_source import ROOT, SOURCE, load_locked_layout

BULLETS = {"\uf0a0", "•", "−", ""}
FORBIDDEN_START = set("，。；：！？、）》】”’,.!?;:%")
FORBIDDEN_END = set("（《【“‘(")


def load_translations() -> dict[str, str]:
    translations = {}
    for number, line in enumerate(
        (ROOT / "translation/zh-CN.tsv").read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line or line.startswith("#"):
            continue
        identifier, text = line.split("\t", 1)
        if identifier in translations:
            raise ValueError(f"Duplicate translation on line {number}: {identifier}")
        translations[identifier] = text.replace(r"\n", "\n")
    return translations


class Fonts:
    def __init__(self, directory: Path):
        self.fonts = {}
        collection = TTCollection(directory / "Nirmala.ttc")
        for index in (0, 1, 2):
            stream = BytesIO()
            collection.fonts[index].save(stream)
            self.fonts[collection.fonts[index]["name"].getDebugName(6)] = pdf.Font(
                fontbuffer=stream.getvalue()
            )
        for name, filename in {
            "MalgunGothic": "malgun.ttf",
            "MalgunGothicBold": "malgunbd.ttf",
            "ArialMT": "arial.ttf",
            "Arial-BoldMT": "arialbd.ttf",
        }.items():
            self.fonts[name] = pdf.Font(fontfile=str(directory / filename))
        self.regular = pdf.Font(fontfile=str(directory / "msyh.ttc"))
        self.bold = pdf.Font(fontfile=str(directory / "msyhbd.ttc"))

    def select(self, character: str, name: str) -> pdf.Font:
        latin = self.fonts.get(name, self.fonts["NirmalaUI-Semilight"])
        if ord(character) < 0x2E80 and latin.has_glyph(ord(character)):
            return latin
        # 中文采用常规字重, 避免沿用拉丁细体时笔画过淡.
        chinese = self.bold if "Bold" in name else self.regular
        if not chinese.has_glyph(ord(character)):
            raise ValueError(f"Missing glyph U+{ord(character):04X}: {character!r}")
        return chinese

    def width(self, text: str, name: str, size: float) -> float:
        return sum(
            self.select(char, name).glyph_advance(ord(char)) * size for char in text
        )


@dataclass
class Placement:
    identifier: str
    text: str
    x: float
    y: float
    size: float
    font: str
    color: int
    width: float


def content_lines(lines: list[dict]) -> list[dict]:
    return [
        line
        for line in lines
        if "".join(s["text"] for s in line["spans"]).strip() not in BULLETS
    ]


def line_text(line: dict) -> str:
    return "".join(span["text"] for span in line["spans"]).strip()


def inline_underlines(
    page: pdf.Page, blocks: list[dict], identifiers: set[str]
) -> list[dict]:
    rectangles = [
        pdf.Rect(block["bbox"]) for block in blocks if block["id"] in identifiers
    ]
    return [
        path
        for path in page.get_drawings()
        if path.get("fill")
        and path["fill"][2] > path["fill"][0] + 0.3
        and path["rect"].height < 1
        and path["rect"].width > 3
        and any(rectangle.intersects(path["rect"]) for rectangle in rectangles)
    ]


def style(lines: list[dict]) -> dict:
    spans = [span for line in lines for span in line["spans"] if span["text"].strip()]
    weights = Counter()
    for span in spans:
        weights[(span["font"], span["size"], span["color"])] += len(
            span["text"].strip()
        )
    font, size, color = weights.most_common(1)[0][0]
    return {"font": font, "size": size, "color": color}


def wrap(text: str, width: float, fonts: Fonts, name: str, size: float) -> list[str]:
    lines = []
    remaining = text.strip()
    while remaining:
        end = 0
        used = 0.0
        while end < len(remaining):
            advance = fonts.width(remaining[end], name, size)
            if used + advance > width + 0.01:
                break
            used += advance
            end += 1
        if end == 0:
            raise ValueError(f"Text frame narrower than one glyph: {remaining!r}")
        if end < len(remaining):
            # 英文单词不在中间断开; 中文避头尾禁则.
            if (
                remaining[end - 1].isascii()
                and remaining[end].isascii()
                and remaining[end - 1].isalnum()
                and remaining[end].isalnum()
            ):
                space = remaining.rfind(" ", 0, end)
                if space > end // 2:
                    end = space
            while end > 1 and (
                remaining[end] in FORBIDDEN_START or remaining[end - 1] in FORBIDDEN_END
            ):
                end -= 1
        lines.append(remaining[:end].rstrip())
        remaining = remaining[end:].lstrip()
    return lines


def text_regions(lines: list[dict]) -> list[list[dict]]:
    groups = []
    current = []
    for line in lines:
        if not line_text(line):
            if current:
                groups.append(current)
                current = []
            continue
        if current:
            previous = style([current[-1]])
            present = style([line])
            # 独立标题、链接与正文按原基线分别排版.
            if ("Bold" in previous["font"]) != ("Bold" in present["font"]) or previous[
                "color"
            ] != present["color"]:
                groups.append(current)
                current = []
        current.append(line)
    if current:
        groups.append(current)
    return groups


def list_regions(lines: list[dict]) -> list[list[dict]]:
    meaningful = content_lines(lines)
    bullets = sorted(
        {
            round(line["spans"][0]["origin"][1], 2)
            for line in lines
            if line_text(line) in BULLETS - {""}
        }
    )
    if not bullets:
        return [[line] for line in meaningful]
    first_y = meaningful[0]["spans"][0]["origin"][1]
    boundaries = ([first_y] if first_y < bullets[0] - 1 else []) + bullets
    return [
        [
            line
            for line in meaningful
            if start - 1 <= line["spans"][0]["origin"][1] < end - 1
        ]
        for start, end in zip(boundaries, boundaries[1:] + [float("inf")])
    ]


class Builder:
    def __init__(self, layout: dict, fonts: Fonts):
        self.layout = layout
        self.fonts = fonts
        self.placements = []
        self.removals = []
        self.records = []
        self.terms = json.loads(
            (ROOT / "translation/cell-terms.json").read_text(encoding="utf-8")
        )
        self.inline_links = json.loads(
            (ROOT / "translation/inline-links.json").read_text(encoding="utf-8")
        )
        self.cell_overrides = json.loads(
            (ROOT / "translation/cell-overrides.json").read_text(encoding="utf-8")
        )
        self.term_pattern = re.compile(
            "|".join(
                re.escape(term) for term in sorted(self.terms, key=len, reverse=True)
            )
        )

    def erase(self, lines: list[dict]) -> None:
        for line in lines:
            for span in line["spans"]:
                if span["text"].strip() in BULLETS:
                    continue
                x0, _, x1, _ = span["bbox"]
                y = span["origin"][1]
                size = span["size"]
                self.removals.append(
                    pdf.Rect(x0 + 0.01, y - size * 0.65, x1 - 0.01, y + size * 0.1)
                )

    def paragraph(
        self, identifier: str, text: str, lines: list[dict], *, erase: bool = True
    ) -> None:
        lines = content_lines(lines)
        if not lines:
            raise ValueError(f"No source frame for {identifier}")
        selected = style(lines)
        if identifier in self.inline_links:
            selected["color"] = 0
        first_span = next(span for span in lines[0]["spans"] if span["text"].strip())
        x = first_span["origin"][0]
        y = first_span["origin"][1]
        right = max(line["bbox"][2] for line in lines)
        # 单行标题保持原对齐方式; 正文使用原文字框, 不越过原页边距.
        centered = len(lines) == 1 and x > 140 and right < 510 and y < 180
        width = (
            (right - x)
            if len(lines) > 1
            else min(
                523.8 - x,
                max(
                    right - x,
                    self.fonts.width(text, selected["font"], selected["size"]),
                ),
            )
        )
        if centered:
            actual = self.fonts.width(text, selected["font"], selected["size"])
            x = (x + right - actual) / 2
            width = actual + 0.01
        rendered = wrap(text, width, self.fonts, selected["font"], selected["size"])
        baselines = sorted(
            {
                max(span["origin"][1] for span in line["spans"] if span["text"].strip())
                for line in lines
            }
        )
        if len(rendered) > len(baselines):
            raise ValueError(
                f"Overflow {identifier}: {len(rendered)} lines for {len(baselines)} source lines; {text}"
            )
        if erase:
            self.erase(lines)
        ranges = []
        for phrase in self.inline_links.get(identifier, []):
            offset = text.find(phrase)
            if offset < 0:
                raise ValueError(f"Inline link phrase missing: {identifier}: {phrase}")
            ranges.append((offset, offset + len(phrase)))
        cursor = 0
        for index, value in enumerate(rendered):
            start = text.find(value, cursor)
            cursor = start + len(value)
            segments = []
            for position, character in enumerate(value, start):
                color = (
                    353217
                    if any(a <= position < b for a, b in ranges)
                    else selected["color"]
                )
                if segments and segments[-1][1] == color:
                    segments[-1] = (segments[-1][0] + character, color)
                else:
                    segments.append((character, color))
            left = x
            for segment, color in segments:
                actual = self.fonts.width(segment, selected["font"], selected["size"])
                self.placements.append(
                    Placement(
                        identifier,
                        segment,
                        left,
                        baselines[index],
                        selected["size"],
                        selected["font"],
                        color,
                        actual,
                    )
                )
                left += actual

    def cells(self, identifier: str, lines: list[dict]) -> None:
        for line_index, line in enumerate(lines):
            source = "".join(span["text"] for span in line["spans"])
            override = self.cell_overrides.get(identifier, {}).get(str(line_index))
            if override:
                if source.strip() != override["source"]:
                    raise ValueError(
                        f"Cell correction source changed: {identifier}/{line_index}"
                    )
                self.paragraph(identifier, override["text"], [line])
                continue
            characters = []
            for span in line["spans"]:
                x = span["origin"][0]
                for character in span["text"]:
                    width = self.fonts.width(character, span["font"], span["size"])
                    characters.append((x, x + width, span))
                    x += width
            for match in self.term_pattern.finditer(source):
                original = match.group()
                translated = self.terms[original]
                selected = characters[match.start() : match.end()]
                x = selected[0][0]
                right = max(item[1] for item in selected)
                base = max(
                    (item[2] for item in selected), key=lambda item: item["size"]
                )
                for left, end, span in selected:
                    y = span["origin"][1]
                    self.removals.append(
                        pdf.Rect(
                            left + 0.01,
                            y - span["size"] * 0.65,
                            end - 0.01,
                            y + span["size"] * 0.1,
                        )
                    )
                actual = self.fonts.width(translated, base["font"], base["size"])
                if actual > right - x + 0.5:
                    raise ValueError(
                        f"Cell overflow {identifier}: {original!r} -> {translated!r}"
                    )
                self.placements.append(
                    Placement(
                        identifier,
                        translated,
                        x,
                        base["origin"][1],
                        base["size"],
                        base["font"],
                        base["color"],
                        actual,
                    )
                )

    def columns(self, identifier: str, text: str, lines: list[dict]) -> None:
        spans = sorted(
            (span for line in lines for span in line["spans"] if span["text"].strip()),
            key=lambda span: span["origin"][0],
        )
        columns = []
        for span in spans:
            if columns and span["bbox"][0] - columns[-1][-1]["bbox"][2] < 12:
                columns[-1].append(span)
            else:
                columns.append([span])
        translated = text.split(" || ")
        if len(columns) != len(translated):
            raise ValueError(
                f"Column mismatch {identifier}: {len(columns)}/{len(translated)}"
            )
        for column, value in zip(columns, translated):
            rectangle = pdf.Rect(column[0]["bbox"])
            for span in column[1:]:
                rectangle |= pdf.Rect(span["bbox"])
            self.paragraph(
                identifier, value, [{"spans": column, "bbox": list(rectangle)}]
            )

    def translate(self, block: dict, text: str) -> None:
        identifier = block["id"]
        lines = block["lines"]
        if text == "@cells":
            self.cells(identifier, lines)
        elif text.startswith("@url|"):
            values = text.split("|", 1)[1].split("\n")
            regions = []
            for line in lines:
                spans = [
                    span
                    for span in line["spans"]
                    if not span["text"].startswith("https://") and span["text"].strip()
                ]
                if spans:
                    regions.append({"spans": spans, "bbox": line["bbox"]})
            if len(values) != len(regions):
                raise ValueError(f"URL layout mismatch: {identifier}")
            for value, region in zip(values, regions):
                self.paragraph(identifier, value, [region])
        elif text.startswith("@tail:"):
            command, value = text.split("|", 1)
            offset = int(command.split(":")[1])
            self.cells(identifier, lines[:offset])
            self.paragraph(identifier, value, lines[offset:])
        elif " || " in text:
            self.columns(identifier, text, lines)
        elif "\n\n" in text:
            values = text.split("\n\n")
            regions = text_regions(lines)
            if len(values) != len(regions):
                raise ValueError(
                    f"Region mismatch {identifier}: {len(regions)}/{len(values)}; {[line_text(r[0]) for r in regions]}"
                )
            for value, region in zip(values, regions):
                self.paragraph(identifier, value, region)
        elif "\n" in text:
            values = text.split("\n")
            regions = list_regions(lines)
            if len(values) != len(regions):
                raise ValueError(
                    f"List mismatch {identifier}: {len(regions)}/{len(values)}"
                )
            for value, region in zip(values, regions):
                self.paragraph(identifier, value, region)
        else:
            self.paragraph(identifier, text, lines)

    def write(self, page: pdf.Page) -> None:
        for rectangle in self.removals:
            page.add_redact_annot(rectangle, fill=False, cross_out=False)
        if self.removals:
            page.apply_redactions(images=0, graphics=0, text=0)
        for placement in self.placements:
            writer = pdf.TextWriter(page.rect)
            x = placement.x
            for character in placement.text:
                font = self.fonts.select(character, placement.font)
                writer.append(
                    (x, placement.y), character, font=font, fontsize=placement.size
                )
                x += font.glyph_advance(ord(character)) * placement.size
            color = pdf.sRGB_to_pdf(placement.color)
            writer.write_text(page, color=color)
        self.records.extend(
            {"page": page.number + 1, **placement.__dict__}
            for placement in self.placements
        )
        self.placements.clear()
        self.removals.clear()

    def cover(self, page: pdf.Page) -> None:
        # 封面标题已经烘焙进位图, 仅覆盖两个纯色文字区, 插画与作者署名原样保留.
        green = (67 / 255, 169 / 255, 103 / 255)
        blue = (88 / 255, 113 / 255, 153 / 255)
        page.draw_rect(pdf.Rect(40, 65, 555, 250), color=None, fill=green, overlay=True)
        page.draw_rect(pdf.Rect(40, 725, 555, 830), color=None, fill=blue, overlay=True)
        for text, y, size, color in [
            ("数学摇滚", 141, 76, 0xFFFFFF),
            ("精髓", 232, 76, 0xFFF900),
            ("吉他手的", 764, 32, 0xFFFFFF),
            ("数学摇滚指南", 815, 32, 0xFFFFFF),
        ]:
            name = "NirmalaUI-Bold"
            width = self.fonts.width(text, name, size)
            x = 50 if size == 76 else (page.rect.width - width) / 2
            self.placements.append(
                Placement("cover", text, x, y, size, name, color, width)
            )
        self.write(page)


def build(output: Path, font_directory: Path) -> None:
    (ROOT / "build").mkdir(parents=True, exist_ok=True)
    expected = load_locked_layout()
    translations = load_translations()
    preserved = set(
        json.loads(
            (ROOT / "translation/preserved-blocks.json").read_text(encoding="utf-8")
        )["ids"]
    )
    known = {block["id"] for page in expected["pages"] for block in page["blocks"]}
    if set(translations) & preserved or (set(translations) | preserved) - known:
        raise ValueError("Overlapping or unknown block IDs")
    missing = [
        block["id"]
        for page in expected["pages"]
        for block in page["blocks"]
        if block["id"] not in translations
        and block["id"] not in preserved
        and not re.fullmatch(r"[\d\s.?]+", block["text"])
    ]
    if missing:
        raise ValueError(f"Missing translations: {missing}")
    fonts = Fonts(font_directory)
    builder = Builder(expected, fonts)
    document = pdf.open(SOURCE)
    errors = []
    for page_data, page in zip(expected["pages"], document):
        for block in page_data["blocks"]:
            if block["id"] in translations:
                try:
                    builder.translate(block, translations[block["id"]])
                except ValueError as error:
                    errors.append(str(error))
        if errors:
            builder.placements.clear()
            builder.removals.clear()
            continue
        underlines = inline_underlines(
            page, page_data["blocks"], set(builder.inline_links)
        )
        for path in underlines:
            rectangle = path["rect"] + (-0.05, -0.05, 0.05, 0.05)
            page.add_redact_annot(rectangle, fill=False, cross_out=False)
        if underlines:
            page.apply_redactions(images=0, graphics=1, text=1)
        inline_placements = {
            identifier: [
                placement
                for placement in builder.placements
                if placement.identifier == identifier and placement.color == 353217
            ]
            for identifier in builder.inline_links
        }
        builder.write(page)
        if underlines:
            affected = {
                block["id"]
                for block in page_data["blocks"]
                if any(
                    pdf.Rect(block["bbox"]).intersects(path["rect"])
                    for path in underlines
                )
            }
            for identifier in affected:
                for placement in inline_placements.get(identifier, []):
                    page.draw_rect(
                        pdf.Rect(
                            placement.x,
                            placement.y + 1.92,
                            placement.x + placement.width,
                            placement.y + 2.28,
                        ),
                        color=None,
                        fill=pdf.sRGB_to_pdf(353217),
                    )
        # 删除文字时 MuPDF 会清除重叠链接, 从原始证据恢复全部链接与目的地.
        for link in page.get_links():
            page.delete_link(link)
        for link in page_data["links"]:
            restored = {
                key: value for key, value in link.items() if key not in {"xref", "id"}
            }
            restored["from"] = pdf.Rect(restored["from"])
            for block in page_data["blocks"]:
                candidates = inline_placements.get(block["id"], [])
                if candidates and restored["from"].intersects(pdf.Rect(block["bbox"])):
                    rectangle = pdf.Rect()
                    for placement in candidates:
                        rectangle |= pdf.Rect(
                            placement.x,
                            placement.y - placement.size,
                            placement.x + placement.width,
                            placement.y + 3,
                        )
                    restored["from"] = rectangle
                    break
            if "to" in restored and isinstance(restored["to"], list):
                restored["to"] = pdf.Point(restored["to"])
            page.insert_link(restored)
    if errors:
        raise ValueError("Preflight failed:\n" + "\n".join(errors))
    builder.cover(document[0])
    document.set_metadata(
        {
            **document.metadata,
            "title": "数学摇滚精髓",
            "author": "Stephen Hazel",
            "subject": "中文译本; 翻译: Raisetsu41",
            "keywords": "math rock, guitar, 中文",
        }
    )
    document.subset_fonts()
    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(output, garbage=4, deflate=True)
    (ROOT / "build/placements.json").write_text(
        json.dumps(builder.records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"Built {output}: {len(document)} pages; {len(translations)} translated blocks"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "Math-Rock-Essentials.pdf"
    )
    parser.add_argument("--font-dir", type=Path, default=Path("C:/Windows/Fonts"))
    args = parser.parse_args()
    build(args.output, args.font_dir)
