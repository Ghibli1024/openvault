<!--
[INPUT]: 依赖 SKILL.md、sources/、scripts/、references/、tests/ 组织 openvault 的 skill-first 架构
[OUTPUT]: 对外提供项目结构地图、职责边界、验证入口
[POS]: openvault 根架构地图，约束唯一 skill 入口与来源实现分层
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
-->

# openvault - 本地收藏归档 skill
本项目是一个 skill-first 的本地归档工作流，用 Markdown/Obsidian 承载书签、小红书、B站、X 收藏。

<目录>
agents/ - skill UI 元数据，描述 openvault 在 agent 列表中的显示方式
references/ - 共享策略层，保存 taxonomy 与受管归档规则
scripts/ - 共享运行时脚本，负责来源识别、全局搜索、resources-root 迁移
sources/ - 来源实现层，保存书签、小红书、B站、X 的 WORKFLOW、脚本与测试
tests/ - 根层回归测试，验证 skill 发现面、路由和共享运行时
</目录>

<配置>
SKILL.md - 唯一 agent 入口，负责路由、共享规则和报告契约
README.md - 英文用户入口，主推 npx skills add 安装
README.zh-CN.md - 中文用户入口，解释 skill-first 使用方式
</配置>

法则: 单入口·来源隔离·本地优先·taxonomy 不静默覆盖
