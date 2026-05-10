<!--
[INPUT]: 依赖 sources/*/WORKFLOW.md、scripts/、tests/ 描述来源实现边界
[OUTPUT]: 对外提供 sources 模块成员清单与跨来源依赖关系
[POS]: sources 的 L2 模块地图，被根 SKILL.md 按需路由读取
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
-->

# sources/
> L2 | 父级: ../CLAUDE.md

成员清单
bilibili/: B站收藏来源实现，依赖本地浏览器登录态和 B站接口，输出 `B站/` 受管归档。
bookmarks/: 浏览器书签来源实现，依赖 Netscape bookmark HTML，输出 categories-only Markdown 分类树。
x-likes/: X/Twitter likes 来源实现，依赖 likes JSON，输出 `X/` 受管归档，并兼容旧 `X Likes/`。
xhs/: 小红书来源实现，依赖收藏/喜欢 HTML，输出 `小红书/` 受管归档，并复用 X likes 同步内核。

法则: 一来源一目录·WORKFLOW 只给 agent 读·脚本保持来源内聚

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
