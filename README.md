# openvault

中文 | [English](README.en.md)

`openvault` 是一个本地优先的 agent skill，用来把浏览器书签、小红书、B站、X 收藏整理成同一个 Obsidian 可用的 Markdown 资源库。

它解决的不是“再导出一次文件”，而是把不同来源的收藏沉淀成可搜索、可分类、可长期维护的本地知识资产。给 agent 一个书签 HTML、小红书 HTML、本地 B站收藏或 X likes JSON，`openvault` 会自动路由到对应 workflow，优先保留你已有的本地 taxonomy，并把结果写进稳定的 Markdown 归档。

```text
书签 / 小红书 / B站 / X
        -> openvault
        -> <resources-root>/{书签,小红书,B站,X,搜索,废弃}
```

[安装](#安装) · [使用](#使用) · [支持来源](#支持来源) · [输出预览](#输出预览) · [开发](#开发)

---

## 安装

用 open agent skills CLI 安装：

```bash
npx skills add Ghibli1024/openvault -g -a codex
```

常用变体：

```bash
# 安装前先看这个仓库会暴露哪些 skill
npx skills add Ghibli1024/openvault --list

# 安装到所有检测到的兼容 agent
npx skills add Ghibli1024/openvault --all
```

安装后重启 Codex 或目标 agent，让新的 `openvault` skill 被重新发现。

## 使用

直接说自然语言：

```text
用 openvault 把这个书签 HTML 导入 <resources-root>。
用 openvault 把我的 B站收藏同步到 <resources-root>。
用 openvault 导入这两个小红书收藏和喜欢 HTML。
用 openvault 导入这个 X likes JSON。
用 openvault 在 <resources-root> 里搜索「AI design tools」。
用 openvault 清理 <resources-root>/废弃 里的人工删除队列。
```

根目录 [SKILL.md](SKILL.md) 是唯一 agent 入口。各来源细节放在 `sources/*/WORKFLOW.md`，只有路由命中后才需要读取。

## 支持来源

| 来源 | 输入 | 主要输出 | 最适合 |
|---|---|---|---|
| 书签 | Chrome、Edge、Firefox 等导出的 Netscape 风格 bookmark HTML | 带 `ROOT分类目录.md` 的 `书签/` 分类树 | 长期网页资源库 |
| 小红书 | 收藏 HTML，可选喜欢 HTML | `小红书/` 日期、作者、来源、领域、粗分类、仪表盘视图 | 灵感、生活方式、视觉参考 |
| B站 | 本地浏览器登录态下的当前收藏 | `B站/` 日期、UP主、收藏夹、领域、粗分类、仪表盘视图 | 视频资源库 |
| X Likes | 上游导出的 likes JSON | `X/` 日期、作者、领域视图 | 信息流沉淀 |

## 输出预览

`openvault` 面向一个共享 resources root：

```text
<resources-root>/
├── 书签/
│   ├── ROOT分类目录.md
│   ├── Index.md
│   └── <taxonomy folders>/
├── 小红书/
│   ├── 01 日期/
│   ├── 02 作者/
│   ├── 03 来源/
│   ├── 04 领域/
│   ├── 05 粗分类/
│   └── Dashboard.md
├── B站/
│   ├── 01 日期/
│   ├── 02 UP主/
│   ├── 03 收藏夹/
│   ├── 04 领域/
│   ├── 05 粗分类/
│   └── Dashboard.md
├── X/
│   ├── 01 Date/
│   ├── 02 Author/
│   ├── 03 Domain/
│   └── Dashboard.md
├── 搜索/
└── 废弃/
```

一次同步的摘要大致长这样：

```text
source: bookmarks
input: <path-to-export.html>
output: <resources-root>/书签
taxonomy: existing ROOT分类目录.md
mode: merge
created: 42
updated: 8
removed: 3
```

## 核心规则

### 一个 skill 入口

`openvault` 只暴露一个根 `SKILL.md`。它负责判断来源，然后读取对应来源 workflow：

- `sources/bookmarks/WORKFLOW.md`
- `sources/xhs/WORKFLOW.md`
- `sources/bilibili/WORKFLOW.md`
- `sources/x-likes/WORKFLOW.md`

### 保留本地 taxonomy

如果目标归档里已经有 `ROOT分类目录.md`，就把它当成事实来源。新导出可以提供证据，但不能静默替换用户已经建立的分类树。

优先级：

1. 用户显式给出的 taxonomy 或规则路径
2. 目标归档里已有的 `ROOT分类目录.md`
3. 来源 workflow 自带的默认 taxonomy fallback

### 全局搜索与废弃

搜索和人工废弃提升到 resources-root 层：

- `搜索/` 存放跨来源搜索结果笔记。
- `废弃/` 存放本地人工删除意图。

人工废弃不是上游权威删除。只有当用户明确要求本地与云端权威同步时，来源 workflow 才可以用另一套方式处理上游已消失的内容。默认情况下，`废弃/` 始终是人工整理队列。

## 隐私与安全

`openvault` 的设计原则是本地优先。

- 仓库示例统一使用 `<resources-root>`、`<path-to-export>` 这类占位符。
- 原始导出、生成笔记、账号名、URL、浏览历史都可能包含隐私信息。
- 除非明确脱敏，不要把个人导出、生成归档、状态文件或 vault 绝对路径提交到公开仓库。
- 书签、小红书、X workflow 使用用户提供的导出文件。
- B站 workflow 依赖本地浏览器登录态，不把账号凭据写进仓库。

## 仓库结构

```text
openvault/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   ├── managed-archive-policy.md
│   └── taxonomy-policy.md
├── scripts/
│   ├── detect_source.py
│   ├── search_resources.py
│   └── vault_runtime.py
├── sources/
│   ├── bilibili/
│   ├── bookmarks/
│   ├── x-likes/
│   └── xhs/
└── tests/
```

关键文件：

| 路径 | 用途 |
|---|---|
| `SKILL.md` | 唯一 agent 入口和 router |
| `sources/*/WORKFLOW.md` | 来源特有操作流程 |
| `references/taxonomy-policy.md` | 共享 taxonomy 优先级 |
| `references/managed-archive-policy.md` | 受管归档的共享清理预期 |
| `scripts/detect_source.py` | 轻量来源识别 helper |
| `scripts/vault_runtime.py` | resources-root 路径和迁移 helper |
| `scripts/search_resources.py` | 跨来源 Markdown 搜索 helper |

## 开发

使用标准库测试 runner：

```bash
GIT_TEST_DEFAULT_INITIAL_BRANCH_NAME=main python3 -m unittest discover -s tests
python3 -m unittest discover -s sources/bookmarks/tests
python3 -m unittest discover -s sources/x-likes/tests
python3 -m unittest discover -s sources/xhs/tests
python3 -m unittest discover -s sources/bilibili/tests
```

验证 skill 发现面：

```bash
npx skills add . --list
```

预期结果：只看到一个名为 `openvault` 的 skill。

## 当前限制

- 支持输入仍依赖对应来源的导出文件或本地浏览器状态。
- 默认不提供语义 RAG 搜索。
- skill 不会把所有来源规范成完全一致的 schema。
- 全局 `废弃/` 的语义依赖后续同步流程真正从生成视图中剔除内容。
