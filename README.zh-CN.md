# openvault

[![README-English](https://img.shields.io/badge/README-English-555555?style=for-the-badge)](README.md)
[![README-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87](https://img.shields.io/badge/README-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-2d6cdf?style=for-the-badge)](README.zh-CN.md)

`openvault` 是一个本地优先的 Codex 插件，用来把浏览器书签导出和社交平台收藏整理成一套结构化的 Markdown 资源库。

它当前采用的是“一个可见入口 + 少量内部 canonical workflow”的模型：

- 一个可见 router skill：`archive-router`
- 四个内部 canonical source skill：
  - `bookmarks`
  - `xhs`
  - `bilibili`
  - `x-likes`

插件的核心运行方式是：

- Codex UI 只显示一个 `openvault` 入口
- 所有来源共用一个 resources root
- 各来源仍使用自己的同步/导入引擎
- 搜索与废弃行为在资源根层统一

## 插件能做什么

`openvault` 适合把不同来源的导出内容收进同一个资源库，而不是各管各的。

针对支持的输入，它可以：

- 把浏览器书签 HTML 导入 Markdown 归档
- 把小红书收藏或喜欢导出同步成 Markdown
- 把 B站收藏同步成 Markdown
- 把 X likes JSON 导入 Markdown
- 在需要的地方保留来源特有的浏览视图
- 尽量复用已有 taxonomy，而不是静默改写
- 把搜索结果统一写入全局 `搜索/`
- 把人工删除意图统一写入全局 `废弃/`
- 整个流程尽量只在本地机器与本地 vault 内完成

## 当前信息架构

插件默认面向类似下面这样的 resources root：

```text
<resources-root>/
├── 书签/
├── 小红书/
├── B站/
├── X/
├── 搜索/
└── 废弃/
```

四个来源根继续保留各自有价值的主视图。例如：

- `书签/` 继续保留书签归档结构和 taxonomy 文件
- `小红书/` 继续保留日期、作者、来源、领域、粗分类、仪表盘等视图
- `B站/` 继续保留日期、UP主、收藏夹、领域、粗分类、仪表盘等视图
- `X/` 继续保留日期、作者、领域、仪表盘等视图

但下面两个目录会被提升为全局根：

- `搜索/`
  用于存放跨来源搜索结果
- `废弃/`
  用于存放人工删除队列，例如移动进去的帖子、URL 清单或说明笔记

## 支持的输入

### 书签

输入：

- Chrome、Edge、Firefox 等浏览器导出的 bookmark HTML
- 或其他 Netscape 风格的书签导出

输出：

- `书签/` 下的 Markdown 归档
- 以本地 taxonomy 为主的分类结构
- 更适合在 vault 中长期维护的紧凑分类视图

### 小红书

输入：

- 收藏 HTML 导出
- 可选的喜欢 HTML 导出

输出：

- `小红书/` 下的 Markdown 归档
- 日期、作者、来源、领域、粗分类、仪表盘等视图

### B站

输入：

- 本地浏览器已登录环境中的当前 B站收藏

输出：

- `B站/` 下的 Markdown 归档
- 日期、UP主、收藏夹、领域、粗分类、仪表盘等视图

### X Likes

输入：

- 上游导出的 likes JSON

输出：

- `X/` 下的 Markdown 归档
- 日期、作者、领域、仪表盘等视图

## 核心行为

### 1. 单一可见入口

Codex UI 里应该只保留一个可见入口：

- `archive-router`

这个入口负责把导入、同步、搜索、清理废弃等请求路由到正确的 canonical workflow。

### 2. 来源特有引擎，共享资源库语义

插件不会强行把所有来源都压成一个完全一致的磁盘结构。

它做的是：

- 来源内部继续保留各自真正有用的视图
- 资源根层统一共享规则

例如：

- 搜索结果统一放到全局 `搜索/`
- 人工删除意图统一放到全局 `废弃/`
- 未指定来源的搜索默认跨整个资源库

### 3. 人工废弃 vs 上游权威删除

`openvault` 明确区分两种“删除”：

- 人工废弃
  本地编辑决策。只要某个帖子或 URL 被放进全局 `废弃/`，后续同步时就会从生成视图里剔除。
- 上游权威删除
  只有当用户明确要求“本地与云端权威同步”时，缺失的本地内容才可以进入系统废纸篓，而不是写进共享 `废弃/`。

这样做是为了让共享 `废弃/` 始终保持“人工删除队列”的语义，而不是沦为同步差异垃圾桶。

### 4. taxonomy 保留优先

插件会优先保留已经存在的本地 taxonomy。

典型行为：

- 如果已有本地 `ROOT分类目录.md`，优先沿用
- 不轻易在已有归档旁边再造一棵平行分类树
- 只有在本地完全没有 taxonomy 时，才回退到来源默认值

## 隐私与安全

这个插件的设计原则是本地优先。

### 隐私原则

- 文档示例统一使用 `<resources-root>`、`<path-to-export>` 这类占位符
- 不在 README 中写入个人绝对路径
- 原始导出、个人收藏、生成笔记都可能包含敏感兴趣、账号名、URL 和浏览历史
- 资源库应保存在自己可控的位置
- 除非明确做过脱敏，不建议把原始导出、生成归档或状态文件提交到公开仓库

### 凭据处理

- 书签、小红书、X 相关流程都以用户提供的导出文件为输入
- B站流程依赖本地已登录浏览器环境，而不是把凭据写进仓库
- 仓库本身不应该存储账号密钥或登录信息

### cache 刷新安全

本地 cache 刷新脚本只会更新 Codex 的插件缓存 clone，并输出：

- 刷新前 cache commit
- 刷新后 cache commit
- 目标 commit
- 当前可见 skill 数量

这样可以验证插件是否真的刷新到了最新结构，同时避免把个人 vault 路径写进 README。

## 仓库结构

```text
openvault/
├── .codex-plugin/
│   └── plugin.json
├── README.md
├── README.zh-CN.md
├── references/
│   ├── managed-archive-policy.md
│   └── taxonomy-policy.md
├── scripts/
│   ├── detect_source.py
│   ├── refresh_openvault_cache.py
│   ├── search_resources.py
│   └── vault_runtime.py
├── skills/
│   ├── archive-router/
│   ├── bilibili/
│   ├── bookmarks/
│   ├── x-likes/
│   └── xhs/
└── tests/
```

### 关键文件

- `.codex-plugin/plugin.json`
  插件元数据与 UI 暴露规则
- `scripts/detect_source.py`
  router 用的轻量来源识别脚本
- `scripts/vault_runtime.py`
  共享运行时，负责资源根迁移、全局搜索/废弃规则和共享路径逻辑
- `scripts/search_resources.py`
  跨来源全局搜索脚本
- `scripts/refresh_openvault_cache.py`
  明确的本地 Codex cache 刷新脚本

## 如何使用插件

### 在 Codex UI 中

使用唯一可见的 `openvault` 入口处理这类请求：

- 把书签 HTML 导入资源根
- 把小红书收藏同步到资源根
- 把 B站收藏同步到资源根
- 把 X likes JSON 导入资源根
- 跨整个资源库搜索
- 清理全局 `废弃/`

### 典型请求

router 主要面向这类意图：

- 把书签 HTML 导入 `<resources-root>`
- 把 B站收藏同步到 `<resources-root>`
- 把小红书收藏导入 `<resources-root>`
- 把 X likes JSON 导入 `<resources-root>`
- 在 `<resources-root>` 中搜索 `AI design tools`
- 清理 `<resources-root>/废弃`

## 刷新本地 Codex cache

如果 Codex UI 仍然显示旧 skill 列表，可以显式刷新本地 cache clone。

先 dry-run：

```bash
python3 scripts/refresh_openvault_cache.py --dry-run
```

再正式刷新：

```bash
python3 scripts/refresh_openvault_cache.py
```

脚本会输出：

- 插件是否在 `~/.codex/config.toml` 中启用
- source repo commit
- cache clone 刷新前 commit
- 目标 commit
- 是否需要刷新
- 刷新后的可见 skill 数量

这就是当 UI 与 repo 状态不同步时的标准处理方式。

## 开发说明

插件当前刻意保留四个 canonical source workflow，而不是把所有来源逻辑继续硬塞进一个巨大的统一引擎。

这样做的原因是：

- 可见 UX 可以保持非常简单
- 来源特有同步逻辑仍能独立演进
- 共享运行时规则可以集中维护

## 当前限制

- 各来源仍然依赖对应的导出文件或本地浏览器环境
- 插件不会把所有来源完全规范成一套一模一样的 schema
- 默认不提供语义 RAG 搜索
- 全局 `废弃/` 的删除语义依赖后续同步流程来真正从生成视图中剔除内容

## 历史说明

旧来源仓库和旧工作流形态目前仍作为迁移背景暂时保留，但 `openvault` 已经是当前的 canonical plugin home。
