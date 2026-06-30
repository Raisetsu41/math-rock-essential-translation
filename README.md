# Math Rock Essentials · 数学摇滚精髓

> **Chinese Translation Project** — 中文翻译项目  
> Original by [Stephen Hazel](https://www.ultimate-guitar.com/contribution/StephenHazel/)  
> Translated by Raisetsu41

---

## About / 关于

**Math Rock Essentials** is a comprehensive guitar guide covering the core techniques of math rock — odd time signatures, syncopation, tapping, hybrid picking, alternate tunings, and more. This repository is its **Chinese translation**, presented bilingually alongside the original text.

《Math Rock Essentials》是一本系统讲解数学摇滚吉他技术的指南，涵盖奇数拍号、切分音、点弦、混合拨弦、特殊调弦等核心技巧。本仓库是其**中文翻译版**，原文与译文并列呈现，方便对照学习。

---

## Repository Structure / 仓库结构

```
.
├── Math-Rock-Essentials.pdf        # 编译输出的完整 PDF
├── Math-Rock-Essentials.tex        # 主 LaTeX 文件（xelatex 编译）
├── template-guide.pdf              # LaTeX 模板使用指南
├── chapters/                       # 各章翻译源文件（按章节独立）
│   ├── translators-note.tex        #   翻译说明
│   ├── strumming.tex              #   扫弦节奏
│   ├── fingerpicking.tex          #   指弹
│   ├── tapping.tex                #   点弦
│   ├── hybrid.tex                 #   混合拨弦
│   ├── tunings.tex                #   特殊调弦
│   ├── fretboard.tex              #   指板精通
│   └── glossary.tex               #   术语表
└── Original-Source/                # 原作 Guitar Pro / PDF 原档
    ├── Strumming Patterns/
    ├── Math Rock Techniques/
    ├── Tapping Section/
    ├── Alternative Tunings/
    └── Mastering The Fretboard/
```

### Translation Progress / 翻译进度

| Chapter | Status |
|---------|--------|
| Translator's Note / 翻译说明 | ✅ Done |
| Strumming Patterns / 扫弦节奏 | ✅ Done |
| Finger Picking / 指弹 | 🔜 Pending |
| Finger Tapping / 点弦 | 🔜 Pending |
| Hybrid Picking / 混合拨弦 | 🔜 Pending |
| Alternate Tunings / 特殊调弦 | 🔜 Pending |
| Mastering the Fretboard / 指板精通 | 🔜 Pending |
| Glossary / 术语表 | ✅ Done |

---

## Compilation / 编译

Requires **XeLaTeX** with `ctex` package.

```shell
xelatex Math-Rock-Essentials.tex
```

Or use any LaTeX editor (Overleaf, VS Code + LaTeX Workshop, TeXShop, etc.).

Each chapter is a separate file under `chapters/`, included into the main `.tex`. Edit them individually without touching the master file.

---

## Translation Style / 翻译规范

- **Deep blue** text = original English
- **Red** text = Chinese translation
- **Purple** terms = bilingual glossary entries
- Blue info boxes = tips & notes
- Exercise counter resets per chapter

See `translation-template.tex` for reusable commands like `\eng{}`, `\chn{}`, `\term{}{}`, `\enandcn{}{}`, and the `exercise` environment.

---

## Original Source Files / 原作原档

All original Guitar Pro files (`.gp`, `.gp5`, `.gpx`) and PDFs are preserved in `Original-Source/`, organized by topic:

| Category | Files |
|----------|-------|
| **Strumming Patterns** | `3-4 Strumming Patterns`, `4-4 Strumming Patterns`, `5-8 Strumming Patterns` |
| **Finger Picking** | `Math Rock Finger Picking Exercises` |
| **Finger Tapping** | `Math Rock Finger Tapping Exercises` |
| **Hybrid Picking** | `Math Rock Hybrid Picking Exercises` |
| **Tapping w/ Chords** | `Chords + Tapping Major & Minor Scale`, `Tapping With Chords Examples - Arpeggios` |
| **Alternate Tunings** | `FACGCE Tuning Example Ideas`, `DAEAC#E Tuning Example Ideas` |
| **Fretboard Mastery** | `Mastering The Fretboard Examples & Exercises` |
| **Full Book PDF** | `Math Rock Essentials - Stephen Hazel.pdf` |

---

## Acknowledgements / 致谢

All credit goes to **Stephen Hazel** for creating *Math Rock Essentials* and generously sharing it with the guitar community. This translation would not exist without his original work.

衷心感谢 **Stephen Hazel** 创作了《Math Rock Essentials》并与吉他社区慷慨分享。没有他的原作，就不会有这个翻译项目。

---

## License / 许可

All rights to the original content belong to Stephen Hazel. Please refer to the original work's licensing terms. The translation is provided for educational purposes.

