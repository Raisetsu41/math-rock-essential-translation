# Math Rock Essentials · 数学摇滚精髓

Stephen Hazel 原著, Raisetsu41 中文翻译与校订。

**[下载最新中文版](https://github.com/Raisetsu41/math-rock-essential-translation/releases/latest)** · [仓库内 PDF](Math-Rock-Essentials.pdf) · [英文原书](Math%20Rock%20Essentials%20-%20Stephen%20Hazel.pdf) · [版式说明](docs/FORMAT.md) · [校订记录](docs/EDITORIAL.md) · [验证结果](docs/verification.json)

本版本以英文原书为版面底稿, 对照旧译稿重新翻译正文、标题、图注和表格。保留原封面插画、作者署名、全部谱例、照片、指板图、和弦图和附件。当前成品与原书均为 **93 页**, 沿用原印刷页码和目录页码, 不另加双语对照页。

## 版式约定

- 图片内容及其位置、大小保持原样, 不重新截图或重画谱例。
- 正文使用原 PDF 测得的字号、起始坐标和逐行基线。译文较短时保留原有空白, 不拉伸段落, 不缩小字号凑页。
- 原书正文主要为 **Nirmala UI Semilight, 11.04 pt**。英文与数字使用原字体, 中文正文采用 **Microsoft YaHei 常规体**, 标题使用 Microsoft YaHei Bold。中文优先保证阅读性, 不跟随拉丁细体减轻字重; 字号与基线仍按原书保留。
- 封面是单张位图, 无法提取字体名称和字号。只覆盖标题、副标题的纯色区域, 按可见字面高度和位置匹配中文; 不把推测字号称作原版精确字号。
- 原图内部英文标签、曲名、乐队名、人名和音乐记号保留。图外文字均有中文翻译或明确的保留记录。
- 保留 119 个链接的目标; 行内链接的点击区域与下划线跟随译文。原附件仍在 `Original-Source/`。

## 构建

使用 Windows、Python 3.11 以上及 Windows 自带的 Nirmala UI、Malgun Gothic、Arial、Microsoft YaHei 字体。字体从系统加载, 不在仓库分发。

```powershell
python -m pip install -r requirements.txt
.\build.ps1
```

也可以分步运行:

```powershell
python tools/build.py
python tools/verify.py --render
```

输出为根目录的 `Math-Rock-Essentials.pdf`。`build/render/` 保存全部页面 PNG 和 8 张总览校样, `docs/verification.json` 保存最近一次成功验证的结果与 PDF 哈希。构建遇到漏译、未知段落、缺字或溢出会报错, 不自动缩字。

## 编辑与维护

```text
translation/
  zh-CN.tsv                以原书文字块 ID 对应的中文译文
  source.json              原书文件名、哈希与页数锁定
  preserved-blocks.json    明确保留的专名与音乐记号
  cell-terms.json          表格文字翻译
  cell-overrides.json      原书表格勘误
  inline-links.json        译文中带链接样式的词组
tools/
  build.py                 原位排版与构建
  inspect_source.py        提取原书证据
  verify.py                复核产物与渲染
Original-Source/           原 PDF / Guitar Pro 附件
```

`zh-CN.tsv` 每行包含段落 ID、一个制表符和译文。`\n` 表示原位置的列表换行, `\n\n` 表示独立段落区域。`@cells` 用于表格原位替换; `@tail:N|` 表示保留并校订前 N 个原始行区域后再排正文; `@url|` 保留网址位置。修改后重新构建并检查渲染。

坐标、字体、图片与链接信息在构建和验证时直接从原书提取, 不在仓库保存可重复生成的大型转储。需要检查原始布局时运行 `python tools/inspect_source.py`, 结果写入被忽略的 `build/` 目录。

不要在更换原书后直接更新 `source.json` 的哈希。更换版本前必须重新核对文字块 ID、图像与译文对应关系。

旧 LaTeX 模板、编译产物和旧稿迁移脚本已移除, 旧译稿仍可通过 [Full-Ver 历史版本](https://github.com/Raisetsu41/math-rock-essential-translation/tree/Full-Ver) 查看。英文原书只在根目录保留一份; `Original-Source/` 保留可独立练习的 PDF 与 Guitar Pro 文件。

开发检查:

```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check tools tests
python -m unittest discover -s tests -v
python tools/verify.py
```

负向集成测试确认验证器能拒绝丢图、缺页和漏字的产物。

原作及谱例均保留 Stephen Hazel 的创作署名。
