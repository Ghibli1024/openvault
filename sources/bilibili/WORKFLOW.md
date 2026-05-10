# B站收藏到 Obsidian

## Overview

把当前 Chrome 登录态下的 B站“我创建的视频收藏夹”导出为本地 Markdown 归档，默认发布到 Obsidian 的 `04-Resources/B站/`。

v1 固定保留三种浏览方式：
- 原始收藏夹视图：`03 收藏夹/`
- 语义分类视图：`04 领域/`
- 粗领域视图：`05 粗分类/`

抓取层默认通过 opencli Browser Bridge 读取 Chrome 的 B站 cookies，再直连 B站接口拉取全部收藏夹和视频条目。

## Required Inputs

收集并确认这些字段：
1. `target-root`
2. `mode`: `merge` 或 `create`
3. `classification`: `auto` 或 `manual`
4. `manual-source`: 仅 `classification=manual` 时需要，默认优先使用现有 `ROOT分类目录.md`
5. `title-language`: `zh` 或 `en`
6. `confirm`

默认建议值：
- `target-root`: `/Users/Totoro/Library/Mobile Documents/iCloud~md~obsidian/Documents/Totoro/04-Resources`
- `mode`: `merge`
- `classification`: `auto`
- `title-language`: `zh`

这里的 `merge` 对 B站 workflow 的语义是：
- 保留本地规则文档、`06 搜索/`、`07 废弃/` 等受管目录
- 但视频主数据以上游 B站收藏状态为准
- 上游有的留下，上游新增的加入，上游没有的从本地同步移除

## Interaction Style

默认使用简短的一问一答 intake：
- 一次只问一个未确认字段
- 对 `mode`、`classification`、`title-language`、`confirm` 优先给紧凑选项
- 对路径字段先提出明显候选，再让用户确认

如果用户指向一个现有 `B站/` 归档并选择 `merge`：
- 先检查已有目录结构
- 将已有 archive 视为事实来源
- 如果 `04 领域/ROOT分类目录.md` 已存在，优先沿用它而不是强行切回默认 taxonomy

## Output Contract

固定输出到 `XX/B站/`：
- `01 日期/`
- `02 UP主/`
- `03 收藏夹/`
- `04 领域/`
- `05 粗分类/`
- `06 搜索/`
- `07 废弃/`
- `04 领域/ROOT分类目录.md`
- `Dashboard.md`

每条视频只生成一份主笔记，位于 `01 日期/`。其他目录只生成索引笔记，不复制正文。

## 粗分类规则

`05 粗分类/` 不再复用 `04 Domain/` 的一级类目，而是使用独立的粗分类桶：

- `AI与前沿科技`
  - 命中示例：`工具 / 人工智能`、`工具 / 编程开发`
  - 或标题/简介包含 `AI`、`Agent`、`DeepSeek`、`OpenAI`、`Claude`、`编程`、`代码`、`模型`、`论文`
- `学习成长`
  - 命中示例：`信息 / 学习充电`
  - 或标题/简介包含 `学习`、`课程`、`教程`、`英语`、`心理`、`成长`
- `工具效率`
  - 命中示例：`工具 / 办公效率`、`工具 / 在线工具`、`工具 / 电脑装机`、`工具 / 软件APP`
  - 或标题/简介包含 `工具`、`插件`、`软件`、`效率`、`办公`
- `商业职场`
  - 命中示例：`工具 / 各行各业`
  - 或标题/简介包含 `电商`、`运营`、`求职`、`简历`、`面试`、`营销`、`职场`、`创业`
- `生活见闻`
  - 命中示例：`信息 / 生活百科`、`信息 / 热点资讯`
  - 或标题/简介包含 `生活`、`健康`、`出行`、`安全`、`社会`、`避坑`
- `资源内容`
  - 命中示例：`资源 / *`、`会员专享`
  - 或标题/简介包含 `资源`、`网盘`、`影视`、`游戏`、`动漫`、`音乐`
- `创作设计`
  - 命中示例：`素材 / *`
  - 或标题/简介包含 `剪辑`、`设计`、`海报`、`素材`、`摄影`、`封面`

粗分类优先服务“人类快速浏览”，不是替代 `04 领域/` 的精细 taxonomy。

补充规则：
- 如果某个 `05 粗分类/*.md` 文件生成后预计超过 `50` 行，脚本会在该文件内部按现有 `domain_parts` 自动做细分。
- 第一层细分使用二级标题 `##`，通常对应 `domain_parts[1]`
- 如果某个二级分组仍然过长，会继续用三级标题 `###`，通常对应 `domain_parts[2]`

## Workflow

1. 确认 `target-root`
2. 确认 `mode`
3. 确认 `classification`
4. 若 `manual`，确认 taxonomy Markdown 路径
5. 确认 `title-language`
6. 让用户明确回复 `run`
7. 运行抓取 helper：

```bash
node sources/bilibili/scripts/fetch_bilibili_favorites.mjs
```

8. 运行同步脚本：

```bash
python3 sources/bilibili/scripts/sync_bilibili_favorites.py \
  --target-root "/Users/Totoro/Library/Mobile Documents/iCloud~md~obsidian/Documents/Totoro/04-Resources" \
  --mode merge \
  --classification auto \
  --title-language zh
```

9. 验证输出根目录、主笔记数量、收藏夹视图、粗分类视图、领域视图和 Dashboard
10. 任务开始前先检查一次根目录里是否出现重复文件/文件夹，例如 `01 日期 2`、`02 UP主 2`、`Dashboard 2.md`，发现就立即修复
11. 任务完成后等待 `90` 秒，再复查一次重复文件/文件夹；如果 iCloud/同步过程中晚到地生成了重复项，也要自动修复

## Manual Classification

`manual` 模式默认接受 Markdown taxonomy：
- 优先显式传入路径
- 其次使用 `B站/04 领域/ROOT分类目录.md`
- 再其次使用 `/Users/Totoro/Library/Mobile Documents/iCloud~md~obsidian/Documents/Totoro/04-Resources/书签/ROOT分类目录.md`

## Rubbish

`07 废弃/` 是稳定保留目录：
- 每次重建归档时都应存在
- 如果 archive 里已经有 `07 废弃/` 内容，重建时需要一并保留
- 如果是从旧结构升级，原有 `07 Rubbish/` 或 `06 Rubbish/` 内容也要自动迁移过去
- 不要往里面生成可见的 helper Markdown
- 如果目录为空，用隐藏占位文件维持目录可见性

## Search

生成完成后，可以用搜索脚本把查询结果写入 `06 搜索/`：

```bash
python3 sources/bilibili/scripts/search_bilibili_favorites.py \
  --archive-root "/Users/Totoro/Library/Mobile Documents/iCloud~md~obsidian/Documents/Totoro/04-Resources/B站" \
  --query "AI 教程"
```

## Validation Checklist

运行后至少确认：
1. 根目录包含 `01 日期`、`02 UP主`、`03 收藏夹`、`04 领域`、`05 粗分类`、`06 搜索`、`07 废弃`、`Dashboard.md`
2. `01 日期` 下主笔记数等于最终视频数
3. `03 收藏夹`、`05 粗分类` 与 `04 领域` 同时存在
4. `04 领域/ROOT分类目录.md` 已复制到本地 archive
5. `07 废弃/` 存在，且不会因为重建而丢失原有内容
6. 如果 archive 来自旧结构，原有 `01 Date`、`04 Domain`、`06 Search`、`07 Rubbish` 等英文根目录会迁移到中文位置
7. Dashboard 里至少有总视频数、收藏夹数、新增数、按月统计、按 UP 主统计、按 Domain 统计
8. 任务开始前和完成后 `90` 秒的重复项审计都已执行；像 `01 日期 2`、`02 UP主 2`、`Dashboard 2.md` 这类重复根项会被自动合并回 canonical 位置
