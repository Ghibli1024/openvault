# html-bookmarks-to-markdown

[![README-English](https://img.shields.io/badge/README-English-555555?style=for-the-badge)](README.md)
[![README-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87](https://img.shields.io/badge/README-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-2d6cdf?style=for-the-badge)](README.zh-CN.md)

把浏览器导出的书签 HTML 转换成一个本地 Markdown 归档，支持保留分类、增量同步、批量补注释，以及把第二份外部 HTML 安全导入到现有归档中。

这个仓库同时包含：

- 一份 Codex skill 定义（`SKILL.md`）
- 一组可独立运行的 Python 脚本

输出是普通 Markdown，但结构专门针对 Obsidian 这种工作流做了优化。

## 项目能力

给定一份 Chrome、Edge、Firefox 或 Netscape 风格的书签 HTML 导出文件，这个工具可以：

- 解析书签条目并保留原始分类结构
- 把 HTML 同步成 Markdown 归档
- 在后续同步中维持 URL 级别去重
- 用紧凑索引代替“一条 URL 一个文件”
- 在 merge 时保留已有描述、备注和标签
- 为新增 URL 生成待补注释模板
- 给大型归档生成第一轮自动说明
- 把第二份外部 HTML 导入到现有归档，同时跳过重复 URL
- 在同步结束后检查归档结构是否健康

## 仓库结构

```text
html-bookmarks-to-markdown/
├── README.md
├── README.zh-CN.md
├── LICENSE
├── SKILL.md
├── .gitignore
├── agents/
│   └── openai.yaml
├── references/
│   └── annotations.example.json
└── scripts/
    ├── sync_bookmark_html.py
    ├── autofill_annotations.py
    ├── filter_pending_annotations.py
    ├── import_external_bookmark_html.py
    └── check_bookmark_archive.py
```

## 运行要求

- Python 3
- 一份书签 HTML 导出文件

不需要额外安装第三方 Python 包。

## 主要工作流

### 1. 标准 HTML 同步

当一份书签 HTML 是当前真相源时，用这个流程把它同步成 Markdown。

支持：

- `create`：只按当前 HTML 重建
- `merge`：保留已有说明并增量同步

### 2. 分批补注释

当新增 URL 很多时，可以先同步，再按 `pending_annotations.json` 分批补说明。

仓库里已经附带两个辅助脚本：

- `autofill_annotations.py`
- `filter_pending_annotations.py`

### 3. 外部 HTML 导入到现有归档

当你已经有一个 `Bookmarks/` 归档，又拿到另一份外部 HTML，希望把其中的新链接并进来时，用这个流程。

它的规则是：

- 现有归档是重复 URL 的唯一真相源
- 重复 URL 不改、不扩展分类路径
- 只有新增 URL 才导入
- 新增 URL 会通过现有重复项学到的分类映射落到当前分类体系里

### 4. 结构健康检查

用结构检查脚本验证顶层目录和 `_state` 是否还正确。

## 输出结构

归档根目录：

```text
<target-root>/<container-name>/
```

### 紧凑布局（compact）

用户可见结构通常是：

```text
Bookmarks/
├── 00 Reports/
├── 01 Categories/
├── 02 Links/
├── 03 Domains/
├── Dashboard.md
└── _state/           # 单文件夹方案下的机器状态目录
```

常见状态文件包括：

```text
state.json
latest-summary.json
pending_annotations.json
excluded_links.json
```

### 顶层目录含义

- `00 Reports/`
  每次同步/导入后的结果报告，比如新增、变更、移除、过滤链接。
- `01 Categories/`
  按书签分类浏览的主入口。
- `02 Links/`
  以链接为中心的分片索引。
- `03 Domains/`
  以域名/网站为中心的分片索引。
- `Dashboard.md`
  总览页，展示统计和导航入口。
- `_state/`
  增量同步和结构检查依赖的机器状态。

## 核心脚本

### `scripts/sync_bookmark_html.py`

主同步入口，用于标准 HTML -> Markdown 转换。

示例：

```bash
python3 scripts/sync_bookmark_html.py \
  --input-html "/path/to/bookmarks.html" \
  --target-root "/path/to/archive-root" \
  --container-name "Bookmarks" \
  --layout compact \
  --mode merge \
  --title-language zh \
  --state-root "/path/to/archive-root/Bookmarks/_state"
```

### `scripts/autofill_annotations.py`

给所有待补注释 URL 生成启发式第一轮说明。

示例：

```bash
python3 scripts/autofill_annotations.py \
  --pending-json "/path/to/Bookmarks/_state/pending_annotations.json" \
  --output "/path/to/Bookmarks/_state/batches/autofill-all.json"
```

### `scripts/filter_pending_annotations.py`

按分类分支把待补注释切成小批次。

示例：

```bash
python3 scripts/filter_pending_annotations.py \
  --pending-json "/path/to/Bookmarks/_state/pending_annotations.json" \
  --category-prefix "Research/AI Tools" \
  --output "/path/to/batches/ai-tools.json"
```

### `scripts/import_external_bookmark_html.py`

把另一份 HTML 导入现有归档，自动跳过重复 URL，并尽量沿用当前分类体系。

示例：

```bash
python3 scripts/import_external_bookmark_html.py \
  --input-html "/path/to/external-bookmarks.html" \
  --target-root "/path/to/archive-root" \
  --container-name "Bookmarks" \
  --state-root "/path/to/archive-root/Bookmarks/_state" \
  --title-language zh
```

### `scripts/check_bookmark_archive.py`

检查归档顶层结构和状态文件是否完整。

示例：

```bash
python3 scripts/check_bookmark_archive.py \
  --target-root "/path/to/archive-root" \
  --container-name "Bookmarks" \
  --state-root "/path/to/archive-root/Bookmarks/_state"
```

## 注释工作流

大型归档推荐按下面这条链路走：

1. 先跑同步脚本
2. 看 `pending_annotations.json`
3. 二选一：
   - 直接全量自动补说明
   - 先按分类分批过滤，再人工补
4. 带上 `--annotations-file` 再跑一次同步

示例注释文件：

- [references/annotations.example.json](references/annotations.example.json)

## 作为 Codex Skill 使用

skill 定义在：

- [SKILL.md](SKILL.md)

agent 注册配置在：

- [agents/openai.yaml](agents/openai.yaml)

推荐交互顺序：

1. 确认 HTML 路径
2. 确认目标根目录
3. 选择 `merge` 或 `create`
4. 选择布局（默认 `compact`）
5. 跑同步
6. 看 summary JSON
7. 如果有 pending，再补注释
8. 最后检查结构是否健康

## 为什么要做结构检查

如果归档放在 iCloud/Obsidian 这类目录里，顶层如果冒出：

- `01 Categories 2`
- `03 Domains 2`
- `Dashboard 2.md`

这类东西，应该视为冲突副本，不是合法产物。

所以这个仓库既提供了单独的健康检查命令，也在同步/导入流程里尽量把顶层保持在 canonical 结构。

## 常见用法

### 首次生成

```bash
python3 scripts/sync_bookmark_html.py \
  --input-html "/path/to/bookmarks.html" \
  --target-root "/path/to/output" \
  --container-name "Bookmarks" \
  --layout compact \
  --mode create \
  --title-language zh \
  --state-root "/path/to/output/Bookmarks/_state"
```

### 后续增量更新

```bash
python3 scripts/sync_bookmark_html.py \
  --input-html "/path/to/new-bookmarks.html" \
  --target-root "/path/to/output" \
  --container-name "Bookmarks" \
  --layout compact \
  --mode merge \
  --title-language zh \
  --state-root "/path/to/output/Bookmarks/_state"
```

### 导入第二份书签 HTML

```bash
python3 scripts/import_external_bookmark_html.py \
  --input-html "/path/to/external-bookmarks.html" \
  --target-root "/path/to/output" \
  --container-name "Bookmarks" \
  --title-language zh \
  --state-root "/path/to/output/Bookmarks/_state"
```

## 备注

- 输出首先是 Markdown；Obsidian 是重点目标，但不是硬依赖
- 大型归档推荐默认使用 `compact`
- `per-url` 仍然是可选 legacy 布局，只适合明确想要“一链接一文件”的场景
- 当你需要“重复 URL 不许动，只导入新增”时，优先使用 external import 流程，而不是普通 merge

## 许可证

本项目使用 MIT License。

见：

- [LICENSE](LICENSE)
