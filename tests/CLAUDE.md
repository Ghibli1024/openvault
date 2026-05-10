<!--
[INPUT]: 依赖 tests/test_*.py 与 sources/*/tests 验证 skill-first 结构
[OUTPUT]: 对外提供测试模块成员清单与验收命令
[POS]: tests 的 L2 模块地图，覆盖根层结构、路由、共享运行时
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
-->

# tests/
> L2 | 父级: ../CLAUDE.md

成员清单
test_detect_source.py: 验证 detect_source.py 的来源识别结果。
test_global_search_runtime.py: 验证全局搜索与 resources-root 行为。
test_skill_structure.py: 验证仓库只有根 SKILL.md 作为 skill 发现面，来源实现位于 sources/。
test_vault_runtime.py: 验证 vault_runtime.py 的迁移和全局目录语义。
test_wrapper_handoffs.py: 验证根 SKILL.md 正确路由到来源 WORKFLOW。

验收命令: `GIT_TEST_DEFAULT_INITIAL_BRANCH_NAME=main python3 -m unittest discover -s tests`，并分别运行 `sources/*/tests`。

法则: 根层测发现面·来源层测具体同步脚本

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
