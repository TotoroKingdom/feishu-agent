# R2 后端静态检查清零验证记录

- 执行日期：2026-08-04
- 工作区：`C:\AI\feishu-agent`
- 分支：`dev`
- 用户声明基线：`431259f54f8e`
- 实际开始 HEAD：`042bf19dd2b3`
- 验证时 HEAD：`fb081312b153`
- 范围：仅 R2（T5、T43 的后端 Ruff、format、mypy 与 unit/contract 门禁）

## 1. 基线与既有改动边界

开始执行时，`dev` 的实际 HEAD 为 `042bf19dd2b3`，不是用户上下文中的
`431259f54f8e`。只读核对确认 `042bf19dd2b3` 是 `431259f54f8e` 的直接后继，
其中已经固化了 R1 记录以及 recovery-drill、SBOM、egg-info 等历史生成物。
R2 开始前工作树的 `git status --short --untracked-files=all`、`git diff --stat`
和 `git diff --check` 均为空；创建初始扫描日志后再次取样时，仅出现三个 R2
证据文件。完整快照见 [initial-git-baseline.txt](initial-git-baseline.txt)。

执行期间发生了非本代理发起的提交，HEAD 从 `042bf19dd2b3` 前进到
`fb081312b153`（提交标题 `feat: 修复R1`）。只读核对确认它是前一 HEAD 的后继，
且提交内容包含已产生的初始 R2 证据和首批静态修复；未执行 reset、restore、
checkout、clean、删除、取消跟踪或历史改写。后续验证基于该提交加剩余 R2 工作树。

边界分类：

- R1 未提交改动：实际开始时已不存在；相关内容已经位于 `042bf19dd2b3`。
- R1 前历史生成物：已位于 `042bf19dd2b3`，本轮未修改或清理 recovery-drill、
  SBOM、egg-info 生成物。
- R2 改动：`backend/app`、`backend/tests` 中的导入、格式、类型标注、显式类型
  收窄，以及一项最小行为测试与对应的缺失存储方法；另含本证据和执行记录更新。

## 2. 初始失败清单

先运行静态检查并保存完整输出：

| 门禁 | 初始结果 | 完整清单 |
|---|---:|---|
| Ruff | 274 errors | [initial-ruff.txt](initial-ruff.txt) |
| Ruff format | 54 files would be reformatted | [initial-format.txt](initial-format.txt) |
| mypy strict | 187 errors / 29 files | [initial-mypy.txt](initial-mypy.txt) |
| unit + contract 基线 | 75 passed | [initial-tests.txt](initial-tests.txt) |

Ruff 分类：E501 168、UP017 32、UP038 25、I001 25、F401 22、F841 1、F811 1。
mypy 按模块分为：LangGraph 状态/节点签名、审批存储契约、采集与 provider
payload 类型、报告与指标结构、运行时租约泛型、管理端与可观测性 ORM 类型、
FastAPI 动态 application state。

## 3. 分批修复与 TDD

按根因分批执行：

1. Ruff 安全修复、导入整理和格式化；随后处理现代化语法与长行。
2. provider、report、metrics、collection payload 的局部 `Mapping`/`Sequence`/
   `Literal` 收窄。
3. ORM 查询结果、运行时泛型、管理端响应和应用状态的精确标注。
4. LangGraph 节点使用结构化 `Protocol`，补齐 `WorkflowState` 已真实使用的字段与
   可空性，不改变图路由或公开行为。
5. mypy 暴露 `PublishApprovalStore.load_approval_by_challenge` 缺失后，先新增真实
   SQLite 存储测试并确认 `AttributeError`（RED），再添加最小查询实现并确认 GREEN。
   记录见 [tdd-approval-store.txt](tdd-approval-store.txt)。

未放宽 Ruff、format 或 mypy 配置；未增加全局 `ignore_errors`；未用大面积
`noqa`/`type: ignore`；未删除、跳过或弱化测试；未重构业务流程。

## 4. R2 最终门禁

| 命令 | 结果 | 证据 |
|---|---|---|
| `python -m ruff check app tests` | exit 0，0 errors | [final-ruff.txt](final-ruff.txt) |
| `python -m ruff format --check app tests` | exit 0，157 files formatted | [final-ruff.txt](final-ruff.txt) |
| `python -m mypy app` | exit 0，78 source files / 0 issues | [final-mypy.txt](final-mypy.txt) |
| `python -m pytest tests/unit tests/contract -q` | exit 0，76 passed / 0 failed / 0 skipped | [final-tests.txt](final-tests.txt) |

## 5. 范围外记录

- 未执行 R3 完整 CI、R4 迁移或其他修复包。
- `HumanInputApprovalStore` 中仍存在命名为 publish load/decision 的相邻方法，且当前
  `backend/app` 未发现调用点；移动或重构这些方法超出 R2 的类型/格式范围，本轮未处理。
- 用户声明基线与实际 HEAD 不一致，以及执行期间的外部提交推进，均按事实记录；
  未尝试修正、回退或重写这些范围外状态。
- 行尾转换警告来自 Git 在 Windows 上的现有配置；`git diff --check` 为 0。

结论：R2 四条必需门禁全部退出 0，后端 `app` 与 `tests` 的 Ruff、format、mypy
问题已清零，unit/contract 回归通过。R2 可标记完成。
