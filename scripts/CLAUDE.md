<!--
[INPUT]: 依赖 detect_source.py、search_resources.py、vault_runtime.py 描述共享脚本层
[OUTPUT]: 对外提供 scripts 模块成员清单与运行边界
[POS]: scripts 的 L2 模块地图，被 SKILL.md 和来源脚本调用
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
-->

# scripts/
> L2 | 父级: ../CLAUDE.md

成员清单
detect_source.py: 来源识别 helper，根据请求文本和文件路径返回 bookmarks/xhs/bilibili/x-likes。
search_resources.py: 全局搜索 helper，跨 resources-root 搜索 Markdown 内容并写入搜索结果。
vault_runtime.py: 共享运行时，负责 resources-root 迁移、全局搜索/废弃目录和路径规则。

法则: 只放跨来源能力·来源专属逻辑回到 sources/

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
