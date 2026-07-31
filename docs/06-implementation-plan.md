# 飞书项目周报 Agent：分阶段实施与测试计划

> 文档编号：PLAN-006
> 状态：T4 条件冻结评审中（真实外部 Contract Test 待补）
> 面向：个人开发者使用 Codex 按单 Task 逐步实现 MVP
> 新任务基线：44 个（T1–T44）
> 约束：本计划只拆解既有需求，不扩大 MVP；一次只执行一个 Task。

## 1. 执行原则

1. **先验证再冻结再编码**：初步评审 → 验证矩阵 → Spike → 修正设计 → 冻结协议 → 编码。
2. **纵向切片**：一个 Task 交付可观察业务能力，避免将模型、仓储、服务、API、UI 拆成无法独立验收的碎片。
3. **单一迁移所有权**：每张表只有一个首次创建 Task；后续只做显式兼容扩展。
4. **事实与副作用分离**：LangGraph 不直接执行外部写操作；副作用统一经过 SideEffectExecutor 与 Operation 账本。
5. **两阶段 HITL 不合并**：HITL 1 确认数据范围，HITL 2 审批不可变发布计划。
6. **可恢复和可审计**：跨进程步骤必须明确 checkpoint、幂等键、重试边界与人工处置状态。
7. **范围固定**：最多五仓、飞书表格只读；不实现 LLM Streaming、企业 SSO、复杂多租户和任意工具自治。
8. **单 Task 提交**：完成测试和验收后停止，不自动开始后续 Task。

## 2. Milestone 总览

| Milestone | Task 范围 | 阶段结果 |
|---|---:|---|
| M0 能力验证与本地开发底座 | T1–T8 | 已验证并冻结能力，本地可创建持久化 run |
| M1 最小 Agent 纵向闭环 | T9–T18 | Fake 平台完成双 HITL、报告与三步发布 |
| M2 真实平台与可靠性 | T19–T29 | 真实飞书/GitHub及副作用可靠性 |
| M3 Agent Loop 与质量强化 | T30–T34 | 有界诊断、人工补充和质量门 |
| M4 产品化与部署 | T35–T44 | 配置、认证、调度、观测、部署与验收 |

主依赖链：

```text
T1 → (T2, T3) → T4 → (T5, T6) → T7 → T8
T8 → T9 → T10 → T11 → T12 → T13 → T14 → T15 → T16 → T17 → T18
T18 → T19 → T20 → (T21, T22 → T23) → T24 → T25 → T26 → T27 → T28 → T29
T29 → T30 → T31 → T32 → T33 → T34
T34 → T35 → T36 → T37 → (T38, T39 → T40, T41) → T42 → T43 → T44
```

括号表示可并行准备，不代表绕过各 Task 自身依赖。计划没有反向依赖；`report_runs` 在 T8 内先迁移再实现 RunCreationService。

## 3. 数据库迁移首次所有权

| 表或表组 | 首次迁移 Task | 约束 |
|---|---:|---|
| projects、project_repositories、feishu_resources、report_runs | T8 | 先迁移，后实现 RunCreationService |
| checkpoints、run_history / approvals | T9 / T10 | 运行恢复与审批分别首次创建 |
| source_batches、normalized_records、validation_results、tool_executions | T11 | tool_executions 唯一首次创建者 |
| metric_snapshots | T12 | 唯一首次创建者 |
| reports、report_sections、evidence_refs | T13 | 报告与证据链 |
| publish_plans | T15 | 不可变计划与 plan_hash |
| operations、operation_attempts、publish_artifacts | T16 | 副作用事实账本 |
| callback_inbox、outbox_messages | T19 | 可靠消息边界 |
| encrypted_credentials | T22 | 业务凭证密文 |
| diagnosis_records | T30 | 诊断轮次 |
| project_configs、field_mappings、prompt_versions、async_jobs | T35 | 配置与连通性任务 |
| admin_users、admin_sessions、login_audits | T37 | 管理员安全 |
| schedules | T38 | 周期调度 |
| node_executions、llm_calls、audit_logs | T39 | 首次创建；tool_executions 只能扩展 |
| onboarding_sessions | T41 | 向导进度 |

若后续 Task 需要字段，只能提交显式、兼容的扩展迁移，不得重复建表。

## M0：能力验证与本地开发底座（T1–T8）

### T1 建立外部能力验证矩阵

**目标**

建立外部能力验证矩阵。

**业务价值**

避免先冻结错误假设，也避免暂时缺少真实环境时阻塞 Fake 主链。

**实现范围**

更新 02-architecture-design.md 第 4、5、15 节；每项标记 verified、unverified、degraded 或 not_required。

**明确不包含**

不写业务代码，不新建能力报告或决策文档。

**主要改动范围**

docs/验证矩阵与设计决策。

**实现步骤**

整理能力项；记录验证条件、Fake 行为、业务影响和上线前 Contract Test；标记阻断项。

**测试要求**

逐项对照 PRD 和附件要求；检查无新增文件。

**验收标准**

所有外部能力都有状态、负责人/条件和下一步；未验证项不会阻塞 local-demo。

**验证命令**

git diff --check；git status --short。

**前置依赖**

无。

**后续任务**

T2、T3。

**建议 Commit**

`task(T1): 建立外部能力验证矩阵`

### T2 完成飞书能力 Spike

**目标**

完成飞书能力 Spike。

**业务价值**

冻结真实 Feishu Port 的协议、权限和错误语义。

**实现范围**

最小 Spike；脱敏记录结果到 02-architecture-design.md；必要时更新 04-api-design.md。

**明确不包含**

不实现生产适配器，不创建新文档，不把真实 payload 提交仓库。

**主要改动范围**

spikes/feishu 与验证记录。

**实现步骤**

验证 challenge/签名/重复投递；卡片动作和 actor；表 schema/分页；文档与消息外部 ID；归档 upsert/查询。

**测试要求**

真实 sandbox 可用则执行；不可用则记录 unverified 原因、Fake 合约和上线前测试。

**验收标准**

每项有 verified/degraded/unverified 结论；无秘密进入 git diff。

**验证命令**

python scripts/spikes/feishu_spike.py --check-config；git diff --check。

**前置依赖**

T1。

**后续任务**

T4。

**建议 Commit**

`task(T2): 完成飞书能力 Spike`

### T3 完成 GitHub 与 LLM 能力 Spike

**目标**

完成 GitHub 与 LLM 能力 Spike。

**业务价值**

冻结 GitHub 权限清单和数据采集边界；让报告链可针对真实能力选择原生 schema 或受控 JSON fallback。

**实现范围**

使用两个测试仓库验证 metadata、issues、PR、commits、reviews、milestones、contributors；验证默认 LLM 的结构化输出、usage、限流和超时；将 GitHub/LLM Spike 结论写回现有设计文档。

**明确不包含**

不实现生产 GitHub adapter，不验证 Actions 可选能力；不实现正式 Provider，不要求 Streaming。

**主要改动范围**

spikes/github、spikes/llm 与验证记录。

**实现步骤**

验证 PAT 权限/过期；Issue 排除 PR；分页与 since/until；限流 headers；私有/无权仓错误；验证 schema、usage、429/timeout；记录模型差异；关闭阻断问题；冻结已验证协议和数据口径。

**测试要求**

有真实 PAT 时运行；否则写明 Fake 语义和上线前 Contract Test；结构合法/非法样例；secret scan；文档交叉检查。

**验收标准**

最小权限和错误分类有结论；无 token 出现在输出或 diff；顺序完成“Spike → 决策 → 修正文档 → 冻结”；未验证项有 Fake 和上线门槛。

**验证命令**

python scripts/spikes/github_spike.py --check-config；git diff --check；python scripts/spikes/llm_spike.py --check-config；git diff --check。

**前置依赖**

T1。

**后续任务**

T4。

**建议 Commit**

`task(T3): 完成 GitHub 与 LLM 能力 Spike`

### T4 修正设计并冻结 MVP 协议

**目标**

基于 Spike 证据修正设计并冻结 MVP 协议。

**业务价值**

确保编码只依赖已验证的飞书、GitHub、LLM 与恢复机制结论。

**实现范围**

回写验证矩阵；修正受影响的接口、状态、权限、错误语义与降级说明；形成冻结基线。

**明确不包含**

不扩大 MVP，不把后续能力提前纳入冻结范围，不写业务代码。

**主要改动范围**

现有 02–06 设计文档与决策记录。

**实现步骤**

汇总 T2/T3 结论；定位跨文档冲突；记录取舍；完成一致性评审；标记可编码基线。

**测试要求**

检查术语、状态、依赖、权限和协议的一致性；确认每个阻塞项均有证据。

**验收标准**

阻塞性未知项清零；所有编码 Task 均能引用冻结结论。

**验证命令**

文档链接与差异检查；人工设计评审。

**前置依赖**

T2、T3。

**后续任务**

T5、T6。

**建议 Commit**

`task(T4): 修正设计并冻结 MVP 协议`

### T5 建立工程骨架与基础 CI

**目标**

建立工程骨架与基础 CI。

**业务价值**

提供所有后续 Task 的最小可运行工程；每个后续 Task 都能获得即时回归反馈。

**实现范围**

后端/前端空应用、版本固定、基础测试命令和 Compose config；后端 lint/format/type/unit，前端 lint/type/build，Compose config，Alembic 空迁移链 smoke 和 secret scan。

**明确不包含**

不接数据库表，不实现认证、Graph 或外部 adapter；不做真实平台 smoke、镜像发布、SBOM 或高级压测。

**主要改动范围**

应用入口、共享基础包、测试与 CI 配置。

**实现步骤**

初始化工程；固定核心依赖；建立 lint/type/test/build 命令；添加 smoke test；配置缓存和独立 jobs；初始化 Alembic env；即使尚无 revision 也执行 upgrade head；记录本地等价命令。

**测试要求**

后端 smoke、前端 lint/type/build、Compose 配置解析；本地执行等价命令；Alembic 空链 smoke；用无害测试串验证 secret scanner 后移除。

**验收标准**

全新环境可安装和运行 smoke；无业务逻辑和 secret；基础 CI 可在 clean checkout 通过；包含 Alembic smoke；不依赖真实凭证。

**验证命令**

cd backend && pytest tests/test_smoke.py -q；cd frontend && npm run lint && npm run typecheck && npm run build；docker compose config；项目定义的 ci-local 命令；docker compose config。

**前置依赖**

T4。

**后续任务**

T6、T7。

**建议 Commit**

`task(T5): 建立工程骨架与基础 CI`

### T6 建立配置、安全与健康检查基础

**目标**

建立配置、安全与健康检查基础。

**业务价值**

让 Fake/真实 provider 切换显式且安全；后续 GitHub PAT、飞书 Secret 和 LLM Key 不以明文持久化。

**实现范围**

APP_PROFILE、三类 provider 选择、request_id、敏感字段过滤、health/ready；加解密、tamper 检测、指纹和安全异常。

**明确不包含**

不实现业务凭证入库和完整 tracing；不创建 credential 表，不实现凭证页面。

**主要改动范围**

shared/config、shared/security、observability 与服务入口。

**实现步骤**

定义 Pydantic settings；生产拒绝 fake；建立 JSON 日志上下文；实现脱敏和健康端点；实现 AEAD；限定调用接口；禁止 secret repr；加入测试向量。

**测试要求**

配置矩阵、递归脱敏、错误不含堆栈、依赖异常 ready 测试；round-trip、错误 key、篡改、空值、异常脱敏。

**验收标准**

local-demo 可显式启动；production 配置不能启用模拟入口；日志无 secret；密文含 key version/nonce；任何响应 model 不定义明文输出字段。

**验证命令**

cd backend && pytest tests/unit/core tests/unit/security tests/integration/health -q；cd backend && pytest tests/unit/security/test_encryption.py -q。

**前置依赖**

T4、T5。

**后续任务**

T7、T8。

**建议 Commit**

`task(T6): 建立配置、安全与健康检查基础`

### T7 固定 Local-demo 数据集与 Fake Providers

**目标**

固定 Local-demo 数据集与 Fake Providers。

**业务价值**

让 Fake 与真实 adapter 可替换，Graph 不依赖 SDK；真实平台不可用时仍可开发 Graph 采集与校验路径；形成最小 Agent 闭环所需的全部出站外部替身。

**实现范围**

Protocol、DTO、ToolSpec、ToolContext、ToolResult、registry allowlist；一个飞书逻辑表、一个 GitHub 仓库的 Fake read；可切换三个场景；Fake structured report；文档/群/归档结果模拟；happy/partial-failure 场景。

**明确不包含**

不实现重试引擎、真实 API 或副作用 handler；不模拟 LLM 和发布副作用，不实现多仓并发；不实现 Graph、审批、SideEffectExecutor、RunCreationService 或 HTTP 入口。

**主要改动范围**

fixtures、providers/fake 与契约测试。

**实现步骤**

定义稳定 schema；建立错误 taxonomy；禁止动态 Tool 注册；定义无敏感数据 fixture；实现确定性分页/错误；让 Fake 通过 Port 契约；实现稳定结果 ID；按 scenario 返回 success/failed/unknown；通过现有 Port 契约。

**测试要求**

DTO schema、未知 Tool 拒绝、SDK 类型隔离检查；golden fixture、场景切换、重复读取稳定性、secret scan；固定 LLM 输出、三类结果稳定性、partial failure fixture、无网络访问。

**验收标准**

领域/Graph 只依赖 Port；三类 provider 可由配置选择；三个场景可复现；Fake 返回稳定 external ID；不访问网络；Fake 输出可确定性复现；尚未执行 Graph 或写数据库。

**验证命令**

cd backend && pytest tests/unit/tools tests/contract/test_port_contracts.py -q；cd backend && pytest tests/contract/test_fake_read_adapters.py tests/unit/local_demo -q；cd backend && pytest tests/contract/test_fake_llm.py tests/contract/test_fake_effects.py -q。

**前置依赖**

T5、T6。

**后续任务**

T8、T9。

**建议 Commit**

`task(T7): 固定 Local-demo 数据集与 Fake Providers`

### T8 实现持久化手动运行创建

**目标**

实现持久化手动运行创建。

**业务价值**

避免业务代码前一次性创建完整最终 schema；让 Graph 尽早可启动且完全不依赖 Scheduler。

**实现范围**

首次迁移创建 projects、project_repositories、feishu_resources、report_runs；随后实现 RunCreationService、运行幂等键、初始状态和内部手动入口。

**明确不包含**

不启动 LangGraph，不采集数据，不创建审批、报告或副作用记录。

**主要改动范围**

db/migrations、domain/runs、RunCreationService 与内部入口。

**实现步骤**

定义最小项目、仓库、资源和运行字段；先执行迁移；实现事务化 RunCreationService 与幂等键；开放仅 local-demo 可用的内部入口。

**测试要求**

迁移 up/down/up、外键与唯一约束、repository round-trip、重复和并发创建、非法项目与 production 路由禁用。

**验收标准**

RunCreationService 所需表已存在；同一幂等键只创建一个 run；尚未执行 Graph。

**验证命令**

cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head；运行 run creation integration tests；git diff --check。

**前置依赖**

T6、T7。

**后续任务**

T9。

**建议 Commit**

`task(T8): 实现持久化手动运行创建`

### M0 退出标准

- **可以做到**：外部能力结论已冻结，本地工程可启动，固定 Fake 数据可用，可持久化创建手动 run。
- **还不能做到**：尚不能运行 Agent 图、审批、生成或发布周报。
- **必须通过的测试**：Spike 证据评审、基础 CI、配置安全、迁移与运行创建集成测试。
- **可演示结果**：从内部入口创建一个 run，展示唯一记录与脱敏日志。
- **进入下一阶段条件**：T1–T8 全部通过且阻塞性未知项清零。

## M1：最小 Agent 纵向闭环（T9–T18）

### T9 建立可恢复的 LangGraph 运行时

**目标**

建立可恢复的 LangGraph 运行时。

**业务价值**

支持 interrupt/resume 和重启后的等待态恢复；尽早验证 State、thread 和 PostgreSQL Checkpoint 集成。

**实现范围**

定义最小 LangGraph State、节点协议与条件边；首次迁移 checkpoints、run_history；实现 Worker 启动、interrupt/resume 和 Checkpoint 恢复入口。

**明确不包含**

不创建 approvals，不实现采集、报告、诊断或发布业务节点。

**主要改动范围**

agent/state、agent/graph、agent/runtime、worker 与 checkpoint 持久化。

**实现步骤**

定义版本化 State 且只保存引用；迁移 checkpoints/run_history；装配最小图和条件边；由 Worker 用稳定 thread_id 启动；实现 checkpoint resume 与重启扫描。

**测试要求**

State 序列化与敏感字段扫描、Graph start/interrupt/resume、checkpoint round-trip、重复 start、Worker 重启恢复。

**验收标准**

手动 run 能以同一 thread 启动并持久化状态；重启后从最后 checkpoint 恢复；本 Task 不依赖 approvals 表。

**验证命令**

运行 migration、agent state/graph、checkpoint integration 与 worker restart tests；git diff --check。

**前置依赖**

T8。

**后续任务**

T10、T11。

**建议 Commit**

`task(T9): 建立可恢复的 LangGraph 运行时`

### T10 实现 HITL 1 数据范围确认

**目标**

实现 HITL 1 数据范围确认。

**业务价值**

最早打通第一阶段人工控制。

**实现范围**

首次迁移 approvals；实现 HITL 1 确认快照、waiting_confirmation、批准/拒绝/修改范围、interrupt/resume 与重复响应防护。

**明确不包含**

不接真实飞书 callback，不支持多接收人。

**主要改动范围**

agent/HITL、approvals、resume 服务与运行历史。

**实现步骤**

生成 scope hash；持久化 approval；interrupt；验证 actor/revision/hash；Command resume。

**测试要求**

批准、修改、取消、重复、旧 revision、重启等待态。

**验收标准**

批准前无采集；重复 action 只 resume 一次；修改产生新 revision。

**验证命令**

cd backend && pytest tests/integration/agent/test_hitl_generation.py -q。

**前置依赖**

T9。

**后续任务**

T11。

**建议 Commit**

`task(T10): 实现 HITL 1 数据范围确认`

### T11 实现单表单仓采集与校验快照

**目标**

实现单表单仓采集与校验快照。

**业务价值**

确保大原始数据不进入 State；打通真实业务数据形状的最小采集路径；报告不直接基于未校验原始上下文。

**实现范围**

首次迁移 source_batches、normalized_records、validation_results 与最小 tool_executions；接入单表单仓 Fake 采集、标准化和校验。

**明确不包含**

不创建 metrics/report/evidence 表；不做多仓并发、自动重试或完整分页优化；不实现完整问题分类、降级或诊断循环。

**主要改动范围**

agent/collection、domain/source、tools 与相关迁移。

**实现步骤**

实现 batch hash、来源、周期和 snapshot grouping；设置数据上限；按 scope 调用 Fake；保存 batch；State 写 ref；单次失败直接安全失败；定义统一实体；标准化；落 snapshot/entity；执行最小 required rules。

**测试要求**

up/down/up、JSONB round-trip、hash 唯一、State 仅保存 refs；happy、仓库失败、重复节点复用 batch；时间边界、重复、Issue 排除 PR、关键字段缺失。

**验收标准**

采集结果可按 run 查询；一个主要 migration；批准后才采集；Checkpoint 不含 payload；失败有错误摘要；happy 直达 metrics；blocked 安全停止并记录问题，不进入诊断。

**验证命令**

cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/integration/persistence/test_source_batches.py -q；cd backend && pytest tests/integration/agent/test_minimal_collection.py -q；cd backend && pytest tests/unit/reports/normalization tests/unit/reports/validation tests/integration/agent/test_minimal_validation.py -q。

**前置依赖**

T7、T10。

**后续任务**

T12。

**建议 Commit**

`task(T11): 实现单表单仓采集与校验快照`

### T12 计算首批核心指标

**目标**

计算首批核心指标。

**业务价值**

在纵向闭环中证明 LLM 不负责数值计算。

**实现范围**

首次迁移 metric_snapshots；确定性计算首批 3–5 个核心指标并记录口径、输入范围和版本。

**明确不包含**

不实现全部 11 项指标和人员负载。

**主要改动范围**

domain/metrics、指标节点与 metric_snapshots 迁移。

**实现步骤**

实现空分母/周期边界；保存 definition_version 和 content hash。

**测试要求**

表驱动 golden、跨周期、空数据、重复数据。

**验收标准**

指标可重复且来源 snapshot 可追溯；一个小 migration 或与当前调用方同 Task 扩展。

**验证命令**

cd backend && pytest tests/unit/reports/metrics tests/integration/agent/test_metrics_node.py -q。

**前置依赖**

T11。

**后续任务**

T13。

**建议 Commit**

`task(T12): 计算首批核心指标`

### T13 生成结构化周报与证据链

**目标**

生成结构化周报与证据链。

**业务价值**

让结构化报告与来源可追溯；打通 Agent 报告生成核心，而不等待完整诊断循环。

**实现范围**

首次迁移 reports、report_sections、evidence_refs；生成结构化报告版本并为事实性结论绑定证据。

**明确不包含**

不创建 publish plan 或 operation 表；不实现 schema 修复循环、Streaming 或 Prompt 管理 UI。

**主要改动范围**

domain/reports、生成节点、LLM schema 与相关迁移。

**实现步骤**

建立不可变版本和 hash；实现 evidence allowlist 查询；构造限长输入；调用 Provider；Pydantic 校验；保存版本和 token 摘要。

**测试要求**

up/down/up、FK、重复 claim/evidence 约束；合法/非法 schema、指标值不被 LLM 改写、State 只存 report ref。

**验收标准**

报告版本能引用 metric/evidence snapshot；一个主要 migration；合法结构化结果落库；非法结果不能进入 Grounding。

**验证命令**

cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/integration/persistence/test_report_models.py -q；cd backend && pytest tests/unit/reports/generation tests/integration/agent/test_structured_report.py -q。

**前置依赖**

T12。

**后续任务**

T14。

**建议 Commit**

`task(T13): 生成结构化周报与证据链`

### T14 实现 Grounding 校验与发布渲染

**目标**

实现 Grounding 校验与发布渲染。

**业务价值**

阻止无来源关键事实进入发布。

**实现范围**

确定性引用检查、fact/inference 标记、从 verified structure 渲染。

**明确不包含**

不做语义相似度、高级修复或 Prompt Injection 强化。

**主要改动范围**

domain/grounding、renderers 与报告审查节点。

**实现步骤**

核对 allowlist；拒绝未知 evidence；生成 rendered content hash。

**测试要求**

有效引用、未知 ID、周期错配、renderer 新增事实检查。

**验收标准**

无证据关键 claim 被拒绝；正文不新增结构外事实。

**验证命令**

cd backend && pytest tests/unit/reports/verification tests/unit/reports/rendering tests/integration/agent/test_grounding.py -q。

**前置依赖**

T13。

**后续任务**

T15。

**建议 Commit**

`task(T14): 实现 Grounding 校验与发布渲染`

### T15 实现 HITL 2 与不可变发布计划

**目标**

实现 HITL 2 与不可变发布计划。

**业务价值**

在任何业务写入前获得对目标、顺序和内容的可审计授权，并防止审批后内容漂移。

**实现范围**

首次迁移 publish_plans；生成不可变三步发布计划、plan_hash 与 HITL 2 审批快照，内容变化后强制重新审批。

**明确不包含**

不创建 operations 或执行 Handler，不实现 timeout-unknown 核验。

**主要改动范围**

domain/publishing、publish_plans、plan_hash 与审批节点。

**实现步骤**

从已验证报告生成三步不可变计划；规范化目标与内容；计算 plan_hash；保存审批 revision 并 interrupt；resume 时重算 hash、校验操作者和版本。

**测试要求**

稳定规范化、字段顺序与 Unicode、旧 revision、拒绝/过期、目标或内容变化、重复批准、重启恢复。

**验收标准**

hash 不匹配时零副作用；只有原计划可获批准；内容变化必须创建新计划并重新审批。

**验证命令**

运行 publish plan migration、canonicalize、HITL 2 interrupt/resume 与 tamper tests；git diff --check。

**前置依赖**

T14。

**后续任务**

T16。

**建议 Commit**

`task(T15): 实现 HITL 2 与不可变发布计划`

### T16 实现 Operation 账本与 Fake 三步发布

**目标**

实现 Operation 账本与 Fake 三步发布。

**业务价值**

建立所有写操作必须经过的单一入口；验证第二项发布 operation 的依赖顺序和 ledger 复用；完成最小三项发布产物的 happy path。

**实现范围**

首次迁移 operations、operation_attempts、publish_artifacts；实现 SideEffectExecutor、Operation Key 和三个 Fake 发布 Handler。

**明确不包含**

不实现并发 claim、unknown 核验或部分失败恢复；不实现归档、最终 complete_run、partial failure 补偿或真实飞书；不实现 partial failure 补偿、unknown verifier 或真实飞书。

**主要改动范围**

side_effects、operations、Fake handlers 与发布路由。

**实现步骤**

执行前验证审批/hash/sequence；写 attempt；保存 artifact；重复执行读取 ledger；文档 verified 后发消息；保存 message artifact；重复执行读取 ledger；校验前两项 verified；按 Run ID upsert；保存 artifact；全部 verified 后成功。

**测试要求**

未批准、hash mismatch、成功、失败、重复调用；顺序错误、发送失败、重复节点、成功 external ID；顺序错误、归档失败、重复 upsert、三项成功。

**验收标准**

同 operation 最多一次 Fake 外部创建；成功有 external ID；文档未成功时不能发消息；成功 operation 不重复发送；happy path 产生三个稳定 artifact；全部 verified 才 succeeded。

**验证命令**

cd backend && pytest tests/unit/side_effects/test_executor.py tests/integration/agent/test_document_operation.py -q；cd backend && pytest tests/integration/agent/test_group_message_operation.py -q；cd backend && pytest tests/integration/agent/test_archive_operation.py tests/integration/agent/test_minimal_publish.py -q。

**前置依赖**

T15。

**后续任务**

T17、T18。

**建议 Commit**

`task(T16): 实现 Operation 账本与 Fake 三步发布`

### T17 提供最小运行详情 API 与页面

**目标**

提供最小运行详情 API 与页面。

**业务价值**

让 Graph/HITL 完成后立即可观察，不等待完整后台；在完整仪表盘前即可观察当前闭环。

**实现范围**

run_id、状态、当前节点、审批、Tool 摘要、错误和关键 refs；run_id、状态、当前节点、审批、Tool 摘要、错误和 refs 的单页展示。

**明确不包含**

不实现完整仪表盘、配置中心、复杂筛选或状态修改能力。

**主要改动范围**

run query API、admin/run-detail 与查询服务。

**实现步骤**

建立脱敏 projection；按 run_id 查询；限制大型字段和秘密；加载 run；活动态轮询；终态停止；展示空/错误状态。

**测试要求**

各状态 API、404、脱敏和 secret scan；各状态 fixture、轮询停止、脱敏展示、type check。

**验收标准**

API 返回七类最小信息；不解析任意 Checkpoint 或原始日志；页面展示七类最小信息；不提供状态修改或秘密查看。

**验证命令**

cd backend && pytest tests/integration/admin/test_minimal_run_detail.py -q；cd frontend && npm run test -- run-detail && npm run typecheck。

**前置依赖**

T10、T13、T16。

**后续任务**

T18。

**建议 Commit**

`task(T17): 提供最小运行详情 API 与页面`

### T18 自动化 Local-demo Happy Path E2E

**目标**

自动化 Local-demo Happy Path E2E。

**业务价值**

Milestone 1 形成可独立演示和持续回归的版本。

**实现范围**

一条 local-demo E2E、固定场景和页面/API 关键断言。

**明确不包含**

不连接真实平台，不覆盖异常诊断或部分失败恢复。

**主要改动范围**

e2e/local-demo、fixtures 与演示说明。

**实现步骤**

创建 run；批准 HITL 1；等待报告；批准 HITL 2；断言三个 artifact 和详情。

**测试要求**

可重复运行、无网络、无时间竞态、secret scan。

**验收标准**

单命令完成 happy path；Graph 未依赖 Scheduler；产物 ID 稳定。

**验证命令**

cd backend && pytest tests/e2e/test_local_demo_happy_path.py -q。

**前置依赖**

T17。

**后续任务**

T19。

**建议 Commit**

`task(T18): 自动化 Local-demo Happy Path E2E`

### M1 退出标准

- **可以做到**：在 Fake 平台下完成单表、单仓、双 HITL、报告、证据链和三步发布。
- **还不能做到**：尚不承诺真实平台、多仓、诊断循环和生产部署。
- **必须通过的测试**：Graph/Checkpoint、审批、指标、Grounding、执行器、页面和 Local-demo E2E。
- **可演示结果**：一条命令演示 Happy Path、拒绝、单步失败、重启和幂等重放。
- **进入下一阶段条件**：T9–T18 全部通过且关键 E2E 稳定。

## M2：真实平台与可靠性（T19–T29）

### T19 建立 Callback Inbox 与 Transactional Outbox

**目标**

建立 Callback Inbox 与 Transactional Outbox。

**业务价值**

重复事件或重复按钮不会产生第二次业务命令；API ack、Graph resume 和 Worker 崩溃之间不丢命令。

**实现范围**

首次迁移 callback_inbox、outbox_messages；实现验签后入箱、事件去重、事务出箱、消费者 claim/ack/retry 与死信。

**明确不包含**

不解析具体飞书卡片业务，不直接推进 Graph，不执行发布副作用。

**主要改动范围**

callbacks、outbox、workers 与相关迁移。

**实现步骤**

定义外部 event key；事务插入；唯一冲突返回 duplicate；记录脱敏摘要；事务写 Outbox；claim/publish/ack；失败退避；重复消息由 dedupe_key 短路。

**测试要求**

up/down/up、顺序/并发重复、同 key 不同 payload 冲突；up/down/up、提交前/后崩溃、重复 dispatch、失败重发。

**验收标准**

同 provider/event_id 只有一条有效 Inbox 记录；一个主要 migration；未 ack 消息可恢复；已发布消息不重复产生消费者效果。

**验证命令**

cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/integration/inbox -q；cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/integration/outbox -q。

**前置依赖**

T18。

**后续任务**

T20。

**建议 Commit**

`task(T19): 建立 Callback Inbox 与 Transactional Outbox`

### T20 接入真实飞书身份、卡片与 Resume

**目标**

接入真实飞书身份、卡片与 Resume。

**业务价值**

为真实卡片、callback 和消息适配器提供认证基础；用户能通过真实飞书看到流程状态，重复发送可控；把 local-demo HITL 换成真实飞书入口。

**实现范围**

token cache、并发刷新、身份 DTO 和错误映射；feishu_message_deliveries 最小迁移；私聊卡片发送/更新；purpose/revision 幂等；challenge、签名/时间窗、actor/action 标准化、inbox/outbox、resume。

**明确不包含**

不读取多维表格，不执行最终发布，不绕过 Inbox/Outbox。

**主要改动范围**

providers/feishu/auth、cards、callbacks 与 resume 服务。

**实现步骤**

按 Spike 协议实现；秘密只在调用边界解密；映射权限/过期；生成 idempotency key；保存 message_id；更新失败可重试；原始 body 验证；登记 inbox；3 秒内 ack；Worker 异步 resume。

**测试要求**

并发刷新、失效、403/429、secret scan、sandbox smoke 分离；重复发送、更新、超时、unknown、真实 sandbox smoke 分离；脱敏 fixture、篡改、过期、重复、并发双击、P95。

**验收标准**

真实 adapter 通过身份契约；日志无 secret；同 purpose/revision/recipient 不重复创建卡片；重复 callback 一次 decision/resume；非法 actor 无状态变化。

**验证命令**

cd backend && pytest tests/contract/feishu/test_auth_identity.py -q；cd backend && pytest tests/contract/feishu/test_cards.py tests/integration/persistence/test_message_delivery.py -q；cd backend && pytest tests/integration/feishu_callbacks -q。

**前置依赖**

T19、T10、T15。

**后续任务**

T21、T25。

**建议 Commit**

`task(T20): 接入真实飞书身份、卡片与 Resume`

### T21 接入真实飞书多维表格只读采集

**目标**

接入真实飞书多维表格只读采集。

**业务价值**

替换 Milestone 1 的 Fake 飞书数据源。

**实现范围**

schema、分页读取、人员/日期/枚举转换和错误映射。

**明确不包含**

不写归档、不实现完整配置 UI。

**主要改动范围**

providers/feishu/bitable、只读 tools 与字段映射校验。

**实现步骤**

读取 schema hash；分页；限制记录量；落现有 batch。

**测试要求**

分页、空表、字段缺失、类型变化、真实 smoke 分离。

**验收标准**

真实/Fake adapter 共享契约；关键 schema 变化进入 blocked。

**验证命令**

cd backend && pytest tests/contract/feishu/test_bitable_read.py -q。

**前置依赖**

T20、T11。

**后续任务**

T24。

**建议 Commit**

`task(T21): 接入真实飞书多维表格只读采集`

### T22 建立 GitHub 凭证与客户端基础

**目标**

建立 GitHub 凭证与客户端基础。

**业务价值**

后续 GitHub PAT、飞书 Secret 和 LLM Key 不以明文持久化；替换单仓 Fake GitHub 的核心研发数据。

**实现范围**

首次迁移 encrypted_credentials；实现凭证加密引用、GitHub 只读客户端、分页、限流和错误映射。

**明确不包含**

不采集 GitHub 业务实体，不提供任意 URL 请求能力，不暴露明文凭证。

**主要改动范围**

security/credentials、providers/github/client 与凭证迁移。

**实现步骤**

实现 AEAD；限定调用接口；禁止 secret repr；加入测试向量；解密调用；能力探测；排除 Issue 中 PR；处理 403/404/429。

**测试要求**

round-trip、错误 key、篡改、空值、异常脱敏；迁移 up/down/up、分页、时间边界、权限、token 泄漏扫描、真实 smoke 分离。

**验收标准**

密文含 key version/nonce；任何响应 model 不定义明文输出字段；一个真实仓可采集；PAT 不进 API/日志/State。

**验证命令**

cd backend && pytest tests/unit/security/test_encryption.py -q；cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/contract/github/test_repository_issues_prs.py tests/unit/security/test_secret_boundaries.py -q。

**前置依赖**

T6、T4。

**后续任务**

T23。

**建议 Commit**

`task(T22): 建立 GitHub 凭证与客户端基础`

### T23 接入 GitHub 核心项目数据

**目标**

接入 GitHub 核心项目数据。

**业务价值**

替换单仓 Fake GitHub 的核心研发数据；支持代码活动和长期未审查 PR 指标；支持里程碑完成率和活跃贡献者指标。

**实现范围**

encrypted_credentials 迁移、PAT credential service、metadata/issues/PR 分页与时间过滤；commit 时间过滤、review 聚合、分页和来源 ID；milestone/contributor endpoint、202/空仓行为和统一模型。

**明确不包含**

不支持超过五仓，不采集代码正文或任意仓库内容。

**主要改动范围**

providers/github/resources、只读 tools 与 normalizers。

**实现步骤**

解密调用；能力探测；排除 Issue 中 PR；处理 403/404/429；实现 endpoint；聚合最新审查状态；保留 branch/author 摘要；实现分页；处理 contributor 202；保留 open/closed 计数和外部 ID。

**测试要求**

迁移 up/down/up、分页、时间边界、权限、token 泄漏扫描、真实 smoke 分离；分页、默认分支口径、空 review、重复 review、时间边界；空/归档仓、202 retry hint、milestone open/closed、分页。

**验收标准**

一个真实仓可采集；PAT 不进 API/日志/State；Commit/Review 通过 Fake/真实共享契约；指标输入稳定；PRD 必需 GitHub 实体齐备；Actions 保持可选后置。

**验证命令**

cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/contract/github/test_repository_issues_prs.py tests/unit/security/test_secret_boundaries.py -q；cd backend && pytest tests/contract/github/test_commits_reviews.py tests/unit/reports/normalization -q；cd backend && pytest tests/contract/github/test_milestones_contributors.py -q。

**前置依赖**

T22、T11。

**后续任务**

T24。

**建议 Commit**

`task(T23): 接入 GitHub 核心项目数据`

### T24 支持最多五仓有界并发与数据质量门

**目标**

支持最多五仓有界并发与数据质量门。

**业务价值**

满足单项目多仓 MVP。

**实现范围**

有界并发、每仓状态、采集上限和结果聚合。

**明确不包含**

不实现 ETag、增量游标优化或自动诊断。

**主要改动范围**

agent/collection、worker/concurrency 与 data-quality。

**实现步骤**

限制并发；每仓独立 batch；其他仓继续；汇总 partial/blocked。

**测试要求**

1/5 仓、单仓 403、timeout、顺序非确定但结果 hash 稳定。

**验收标准**

单仓失败不丢其他仓；最多 5 仓限制由代码和 API 校验。

**验证命令**

cd backend && pytest tests/integration/agent/test_multi_repository_collection.py -q。

**前置依赖**

T21、T23。

**后续任务**

T25、T30。

**建议 Commit**

`task(T24): 支持最多五仓有界并发与数据质量门`

### T25 接入真实飞书三步发布

**目标**

接入真实飞书三步发布。

**业务价值**

产出用户可访问的周报文档；向项目群交付周报通知；在飞书多维表格留下可查询执行档案。

**实现范围**

documents adapter、create-document handler、document URL 和错误映射；group message adapter、handler、message_id 和依赖校验；archive adapter、handler、record ID 和内容 hash。

**明确不包含**

不绕过 SideEffectExecutor，不自动删除或覆盖用户已有产物。

**主要改动范围**

providers/feishu/publish、SideEffect handlers 与产物持久化。

**实现步骤**

复用 approved payload ref；创建后分块写入；保存 document_id/url；校验 document artifact；使用冻结 target/payload；保存 message_id；按 Run ID 查询；不存在新增、存在更新；保存 record_id。

**测试要求**

分块失败、权限、重复 ledger 短路、真实 sandbox smoke 分离；群不可发、timeout、重复 ledger 短路、真实 smoke 分离；首次写入、重复 upsert、schema 缺失、真实 smoke 分离。

**验收标准**

handler 不含审批逻辑；结果可供 verifier 查询；未 confirmed 文档不能发消息；目标来自批准计划；同 Run ID 不产生重复归档；字段来自配置 mapping。

**验证命令**

cd backend && pytest tests/contract/feishu/test_document.py tests/integration/side_effects/test_document_handler.py -q；cd backend && pytest tests/contract/feishu/test_group_message.py tests/integration/side_effects/test_group_handler.py -q；cd backend && pytest tests/contract/feishu/test_archive.py tests/integration/side_effects/test_archive_handler.py -q。

**前置依赖**

T20、T24、T16。

**后续任务**

T26、T27。

**建议 Commit**

`task(T25): 接入真实飞书三步发布`

### T26 强化 Operation 并发 Claim 与成功去重

**目标**

强化 Operation 并发 Claim 与成功去重。

**业务价值**

建立发布 exactly-once effect 的数据库防线。

**实现范围**

FOR UPDATE SKIP LOCKED/乐观版本、claim lease、attempt 记录、ledger 查询。

**明确不包含**

不实现 timeout unknown verifier。

**主要改动范围**

domain/operations、repositories 与 SideEffectExecutor。

**实现步骤**

原子 claim；校验 plan hash；成功短路；过期 claim 标记待核验。

**测试要求**

双 Worker、Checkpoint 落后、重复 resume、成功重放。

**验收标准**

同 operation 并发只一次外部调用；succeeded 永不再次调用。

**验证命令**

cd backend && pytest tests/integration/side_effects/test_operation_claim.py -q。

**前置依赖**

T25。

**后续任务**

T27、T28。

**建议 Commit**

`task(T26): 强化 Operation 并发 Claim 与成功去重`

### T27 实现 Timeout-Unknown 核验

**目标**

实现 Timeout-Unknown 核验。

**业务价值**

避免盲目重建文档或重复发消息。

**实现范围**

SideEffectVerifier；confirmed/not_found/inconclusive；operation verification 状态。

**明确不包含**

不实现 Graph 补偿路由。

**主要改动范围**

side_effects/verifiers、operations 状态机与飞书查询适配器。

**实现步骤**

按 external ID/Run ID/平台能力查询；保存证据；inconclusive 保持 unknown。

**测试要求**

timeout 后 found/not_found/inconclusive；重复核验；无 query 能力。

**验收标准**

unknown 不自动 POST；核验结果持久化且可审计。

**验证命令**

cd backend && pytest tests/integration/side_effects/test_verifier.py -q。

**前置依赖**

T25、T26。

**后续任务**

T28。

**建议 Commit**

`task(T27): 实现 Timeout-Unknown 核验`

### T28 实现部分失败补偿与重启恢复

**目标**

实现部分失败补偿与重启恢复。

**业务价值**

不伪造跨平台回滚，也不重复已成功产物；满足服务重启后不丢任务、不重复副作用。

**实现范围**

verify_side_effects、compensate_partial_failure、partial_failed 状态和卡片摘要；recovery scanner、run lease 最小实现、stale running/unknown 分类。

**明确不包含**

不做破坏性自动回滚，不删除已发布文档或消息。

**主要改动范围**

发布路由、operation recovery 与 worker reconciler。

**实现步骤**

汇总 ledger；retryable 续跑；unknown 先核验；永久失败形成真实终态；扫描 waiting/active；waiting 不占 Worker；running effect 先 verifier；重新派发 outbox。

**测试要求**

文档成功消息失败；文档消息成功归档失败；inconclusive；重复恢复；每个副作用四个崩溃点、Redis flush、Worker restart、Checkpoint 滞后。

**验收标准**

只重试原批准计划的失败项；已成功 artifact 保留；已成功节点/operation 不重复；等待审批仍可 resume。

**验证命令**

cd backend && pytest tests/scenarios/test_partial_publish_failures.py -q；cd backend && pytest tests/integration/recovery tests/scenarios/test_restart_recovery.py -q。

**前置依赖**

T26、T27。

**后续任务**

T29。

**建议 Commit**

`task(T28): 实现部分失败补偿与重启恢复`

### T29 实现运行取消与 Safe Retry

**目标**

实现运行取消与 Safe Retry。

**业务价值**

用户可在发布前停止 run，发布中也不会伪造回滚；管理员可安全恢复失败，而不绕过审批或重复发布。

**实现范围**

durable cancel flag、节点边界检查、admin/Feishu cancel action；safe-retry service/API、状态/plan/approval/ledger 校验。

**明确不包含**

不强杀正在进行的不可逆外部请求，不允许从任意节点回跳。

**主要改动范围**

run-control、agent/routing、operations 与运行 API。

**实现步骤**

定义允许状态；等待态 resume cancel；publishing 中取消 pending operation；校验失败分类；重算 hash；核验 unknown；派发唯一恢复命令。

**测试要求**

等待/采集/生成/发布各阶段、重复取消、已完成 operation；partial_failed、永久失败、terminal 拒绝、重复请求、hash 变化。

**验收标准**

已完成操作保留真实记录；取消不启动新工作；Safe Retry 不重复 artifact；不允许扩大原计划。

**验证命令**

cd backend && pytest tests/integration/runs/test_cancel.py -q；cd backend && pytest tests/integration/runs/test_safe_retry.py -q。

**前置依赖**

T28。

**后续任务**

T30。

**建议 Commit**

`task(T29): 实现运行取消与 Safe Retry`

### M2 退出标准

- **可以做到**：接入真实飞书/GitHub、多仓采集和真实发布，并处理重复、超时未知、部分失败、取消与安全重试。
- **还不能做到**：尚不具备完整诊断 Agent Loop、产品化配置和生产交付。
- **必须通过的测试**：Provider 契约、沙箱集成、并发、故障注入和真实发布 E2E。
- **可演示结果**：真实数据生成并发布周报，演示重复回调与部分失败恢复。
- **进入下一阶段条件**：T19–T29 全部通过且内部账本与外部产物一致。

## M3：Agent Loop 与质量强化（T30–T34）

### T30 实现受控诊断 Agent Loop

**目标**

实现受控诊断 Agent Loop。

**业务价值**

让异常处理可观察、可测试，而不是自由 LLM 决策；Agent 能自动处理瞬态故障和允许降级的数据问题。

**实现范围**

首次迁移 diagnosis_records；实现问题分类、Observe-Diagnose-Plan-Act-Verify、动作白名单、循环预算和退出路由。

**明确不包含**

不允许模型直接调用副作用 Tool，不允许无限循环或扩大数据范围。

**主要改动范围**

agent/diagnosis、诊断策略与 diagnosis_records 迁移。

**实现步骤**

映射 timeout/rate-limit/permission/schema/missing/conflict/LLM/grounding 类别；记录 observation；规则诊断；选择 action；重试/降级；重新校验。

**测试要求**

分类表驱动、未知错误 fallback、迁移 up/down/up；限流后成功、单仓失败、非关键降级、达到上限。

**验收标准**

每个问题有稳定 key 和允许动作；LLM 不能创建类别；正常路径仍直达 metrics；只有异常进入循环；最多 3 次。

**验证命令**

cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/unit/agent/policies/test_problem_registry.py -q；cd backend && pytest tests/scenarios/test_diagnosis_loop.py -q。

**前置依赖**

T24、T29。

**后续任务**

T31、T32。

**建议 Commit**

`task(T30): 实现受控诊断 Agent Loop`

### T31 实现人工补充 Interrupt

**目标**

实现人工补充 Interrupt。

**业务价值**

关键数据不足时不伪造也不从头重跑。

**实现范围**

human_input approval、补充 schema、飞书/Fake 卡片、验证后回 validation。

**明确不包含**

不允许任意 Tool 指令或直接编辑 State。

**主要改动范围**

agent/human-input、approvals 与 resume 服务。

**实现步骤**

输出缺失/尝试/原因/所需/恢复点；校验 supplement ref；resume。

**测试要求**

非法/合法、重复、旧卡片、重启等待态、成功节点不重跑。

**验收标准**

补充后从指定节点继续；关键缺失前不会发布。

**验证命令**

cd backend && pytest tests/scenarios/test_human_input_resume.py -q。

**前置依赖**

T30。

**后续任务**

T32。

**建议 Commit**

`task(T31): 实现人工补充 Interrupt`

### T32 实现报告重新生成与缓存复用

**目标**

实现报告重新生成与缓存复用。

**业务价值**

避免重复采集和指标计算，同时保证新内容重新审批。

**实现范围**

report/plan revision、input hash 复用、scope 变化回 HITL 1。

**明确不包含**

不刷新真实数据快照，除非范围变化。

**主要改动范围**

agent/cache、reports 与 regenerate 服务。

**实现步骤**

使旧 plan/approval invalid；复用 snapshot/metrics/evidence；生成新版本/hash。

**测试要求**

supplement、regenerate、scope change、旧批准失效。

**验收标准**

新报告必有新 plan approval；不无条件重拉数据。

**验证命令**

cd backend && pytest tests/scenarios/test_report_regeneration.py -q。

**前置依赖**

T30、T31、T15。

**后续任务**

T33。

**建议 Commit**

`task(T32): 实现报告重新生成与缓存复用`

### T33 完善指标体系与 Grounding 质量门

**目标**

完善指标体系与 Grounding 质量门。

**业务价值**

最终报告达到完整可追溯验收口径。

**实现范围**

全部 11 项指标、人员活动分项、claim 类型/置信度/周期、可修复 grounding 路由。

**明确不包含**

不生成人员绩效综合分。

**主要改动范围**

domain/metrics、domain/grounding 与质量测试。

**实现步骤**

补指标口径；建立 evidence candidates；修复或降级非关键 claim；关键无证据阻止。

**测试要求**

golden、冲突、partial 数据、无证据关键 claim。

**验收标准**

PRD 指标全覆盖；关键 claim 全部可追溯或被阻止。

**验证命令**

cd backend && pytest tests/unit/reports tests/scenarios/test_grounding_quality.py -q。

**前置依赖**

T32、T24。

**后续任务**

T34。

**建议 Commit**

`task(T33): 完善指标体系与 Grounding 质量门`

### T34 加固 Prompt Injection 与 Schema 恢复

**目标**

加固 Prompt Injection 与 Schema 恢复。

**业务价值**

防止外部内容改变工具、目标或审批边界。

**实现范围**

输入边界/清洗/长度/URL allowlist；schema repair 最多有限次数；安全失败。

**明确不包含**

不实现通用内容安全平台或 LLM Streaming。

**主要改动范围**

llm/policies、schema-repair 与安全测试。

**实现步骤**

标记来源；限制 evidence IDs；拒绝控制字段；修复 JSON；记录尝试。

**测试要求**

PRD 注入场景、超长文本、恶意 URL、非法 schema、达上限。

**验收标准**

外部文本不能新增 Tool/operation/target；无效结构不发布。

**验证命令**

cd backend && pytest tests/security/test_prompt_injection.py tests/scenarios/test_llm_schema_recovery.py -q。

**前置依赖**

T33、T30。

**后续任务**

T35。

**建议 Commit**

`task(T34): 加固 Prompt Injection 与 Schema 恢复`

### M3 退出标准

- **可以做到**：对允许的问题做有界诊断、人工补充和安全再生成，并提供完整质量门。
- **还不能做到**：尚不具备完整管理体验、调度与生产发布门。
- **必须通过的测试**：循环策略/预算、Interrupt、缓存失效、指标黄金集和注入对抗集。
- **可演示结果**：制造缺数或 schema 问题，演示诊断、人工补充、再生成与重新审批。
- **进入下一阶段条件**：T30–T34 全部通过且自治边界可审计。

## M4：产品化与部署（T35–T44）

### T35 建立配置模型、后端 API 与连通性测试

**目标**

建立配置模型、后端 API 与连通性测试。

**业务价值**

让产品不依赖 seed/local-demo 配置；管理员能在运行前发现 PAT/权限问题；配置阶段提前发现资源或权限错误；管理员能在运行前发现模型不兼容。

**实现范围**

首次迁移 project_configs、field_mappings、prompt_versions、async_jobs；实现版本化配置 API 与飞书/GitHub/LLM 只读连通性测试。

**明确不包含**

不实现管理 UI，不保存明文凭证，连通性测试不产生业务副作用。

**主要改动范围**

configuration、config API、connectivity jobs 与相关迁移。

**实现步骤**

补最终 schema；实现乐观并发；运行继续使用 config snapshot；调用已实现 adapter；返回 ok/degraded/failed；脱敏错误；检查 token/identity、表/群/文档 target；返回 schema hash 和 capability；保存加密 key；发最小 schema 请求；返回 capability 和耗时。

**测试要求**

up/down/up、revision 冲突、最多 5 仓、已创建 run 不受变化影响；迁移 up/down/up、有效/过期/权限不足/仓库不存在、异步 job 状态；字段缺失、群不可发、文档不可建、sandbox smoke 分离；无效 key、模型不存在、schema fallback、secret scan。

**验收标准**

基础 CRUD 完整；没有硬编码中文字段/仓库/群 ID；不是单一布尔值；不回显 PAT；结果可定位到具体资源/能力；不产生未审计正式内容；API 不返回 key；业务代码仍厂商无关。

**验证命令**

cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/integration/admin/test_config_crud.py -q；cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/integration/admin/test_github_connectivity.py -q；cd backend && pytest tests/integration/admin/test_feishu_connectivity.py -q；cd backend && pytest tests/integration/admin/test_llm_connectivity.py -q。

**前置依赖**

T34、T22。

**后续任务**

T36、T38。

**建议 Commit**

`task(T35): 建立配置模型、后端 API 与连通性测试`

### T36 实现配置管理 UI、确认与审计

**目标**

实现配置管理 UI、确认与审计。

**业务价值**

管理员可独立管理最多五个仓库；管理员无需硬编码飞书资源或中文字段；管理员能安全轮换凭证而不会在前端回显秘密；满足配置写操作的明确确认和可追溯要求。

**实现范围**

仓库页面、API client/schema 和 revision 冲突处理；资源列表/表单、schema 预览、logical mapping 和 Feishu capability 展示；凭证 metadata、更新表单、验证状态和 secret 清空策略；配置变更摘要、确认 API/UI、before/after 脱敏审计。

**明确不包含**

不展示明文密钥，不实现企业 SSO、复杂多租户或需求外配置项。

**主要改动范围**

admin/configuration、API client 与审计视图。

**实现步骤**

实现列表/表单；显示 capability；校验 1～5 仓；处理并发 revision；加载 schema hash；映射 logical field；显示 required level；处理旧 schema 冲突；只显示 fingerprint suffix/status；提交后清空输入；显示三类 connectivity；生成白名单 diff/hash；确认时重算 revision；事务应用并写 audit。

**测试要求**

表单、最多五仓、revision 冲突、空/错误状态、可访问性基础；字段类型、旧 schema、缺少 critical field、群/文档 capability、可访问性；DOM/API mock 无 secret 回显、错误后清理、状态展示、可访问性；hash/revision 变化、取消、重复确认、secret 脱敏、审计前后摘要。

**验收标准**

仓库配置可用且不影响已创建 run snapshot；页面不写死中文字段；旧 schema 不能覆盖新 mapping；前端缓存、日志和响应对象均不包含原秘密；所有后台配置修改均有明确确认和审计；不影响既有 run snapshot。

**验证命令**

cd frontend && npm run test -- repository-config && npm run typecheck；cd frontend && npm run test -- feishu-resource-mapping && npm run typecheck；cd frontend && npm run test -- credentials && npm run typecheck；cd backend && pytest tests/integration/admin/test_config_audit.py -q；cd frontend && npm run test -- config-confirmation。

**前置依赖**

T35。

**后续任务**

T37、T41。

**建议 Commit**

`task(T36): 实现配置管理 UI、确认与审计`

### T37 强化管理员认证与会话安全

**目标**

强化管理员认证与会话安全。

**业务价值**

防止未授权用户查看运行和修改配置；达到生产后台登录安全要求。

**实现范围**

首次迁移 admin_users、admin_sessions、login_audits；实现管理员登录、会话旋转、CSRF、超时、登出和登录审计。

**明确不包含**

不实现企业 SSO、复杂 RBAC 或面向公网的多租户身份系统。

**主要改动范围**

auth、admin middleware、会话迁移与安全测试。

**实现步骤**

生产强密码初始化；安全 Cookie；路由 guard；旋转 refresh；撤销；失败计数；记录安全事件。

**测试要求**

正确/错误登录、过期、未认证、无默认弱密码；重放旧 refresh、并发刷新、锁定、撤销、CSRF/Origin。

**验收标准**

后台默认受保护；单管理员满足 MVP；撤销 session 不可刷新；审计无密码/token。

**验证命令**

cd backend && pytest tests/integration/admin/test_auth_basic.py -q；cd frontend && npm run test -- auth；cd backend && pytest tests/security/test_admin_sessions.py -q。

**前置依赖**

T36。

**后续任务**

T38、T40。

**建议 Commit**

`task(T37): 强化管理员认证与会话安全`

### T38 实现每周 Scheduler

**目标**

实现每周 Scheduler。

**业务价值**

在纵向闭环稳定后加入自动周报触发。

**实现范围**

首次迁移 schedules；实现时区、周期、启停、misfire、唯一周期键，并复用 RunCreationService 创建运行。

**明确不包含**

不修改 Graph，不引入独立消息平台。

**主要改动范围**

schedules、scheduler worker 与调度 API。

**实现步骤**

按项目时区计算半开周期；调用同一服务；DB unique 兜底。

**测试要求**

时区/DST/年边界、双 scheduler、misfire、Redis 丢失。

**验收标准**

Graph 对触发来源无感；同周期最多一个活动 run。

**验证命令**

cd backend && pytest tests/unit/scheduling tests/integration/scheduling -q。

**前置依赖**

T35、T37、T8。

**后续任务**

T42。

**建议 Commit**

`task(T38): 实现每周 Scheduler`

### T39 完善可观测性持久化与查询 API

**目标**

完善可观测性持久化与查询 API。

**业务价值**

为完整运行后台和安全审计提供稳定事实，而不是解析日志或任意 Checkpoint；为完整后台提供稳定、脱敏且高性能的数据接口。

**实现范围**

首次迁移 node_executions、llm_calls、audit_logs；只扩展 T11 已创建的 tool_executions；实现脱敏事件、成本/时延与查询 API。

**明确不包含**

不重复创建 tool_executions，不保存明文提示、密钥或大体积原始 payload。

**主要改动范围**

observability、query API 与相关扩展迁移。

**实现步骤**

迁移节点、LLM 与审计表；以兼容迁移扩展 tool_executions；统一 request/run/node correlation；写入脱敏时延和成本摘要；实现分页筛选查询。

**测试要求**

迁移 up/down/up、旧 tool 记录兼容、节点/模型/工具异常路径、脱敏、分页、时区与查询权限。

**验收标准**

一次 run 的节点、Tool、LLM 与审计事件可关联查询；tool_executions 不被重建；敏感值不落库。

**验证命令**

运行 observability migrations、integration、query API 与 secret scan；git diff --check。

**前置依赖**

T34、T37。

**后续任务**

T40、T42。

**建议 Commit**

`task(T39): 完善可观测性持久化与查询 API`

### T40 完善运行详情与仪表盘 UI

**目标**

完善运行详情与仪表盘 UI。

**业务价值**

形成 PRD 定义的 Agent 可观测平台。

**实现范围**

dashboard、run list/detail、node/tool/approval/diagnosis/evidence/effect panels 和轮询。

**明确不包含**

不建设复杂 BI，不提供绕过 Graph 的状态修改。

**主要改动范围**

admin/dashboard、run-detail 与 query clients。

**实现步骤**

实现筛选和 cursor；补详情 panels；活动 run 轮询，终态停止。

**测试要求**

各状态 fixture、空/错误状态、脱敏展示、可访问性和 type check。

**验收标准**

PRD 后台字段可查看；无秘密、堆栈或原始 Checkpoint 下载。

**验证命令**

cd frontend && npm run test -- dashboard runs && npm run typecheck。

**前置依赖**

T37、T39、T29。

**后续任务**

T41、T44。

**建议 Commit**

`task(T40): 完善运行详情与仪表盘 UI`

### T41 实现飞书首次配置向导

**目标**

实现飞书首次配置向导。

**业务价值**

满足产品化配置体验，但不阻塞核心 Agent E2E。

**实现范围**

首次迁移 onboarding_sessions；实现可恢复的飞书权限、资源绑定、字段映射、测试预览和完成门。

**明确不包含**

不复制配置逻辑，不实现多人管理员。

**主要改动范围**

admin/onboarding、onboarding 服务与进度迁移。

**实现步骤**

收集 PRD 字段；即时调用 connectivity；PAT 立即加密；确认后激活。

**测试要求**

正常、回退、过期、重复、非管理员、服务重启。

**验收标准**

未最终确认不激活配置；local-demo/手动配置仍可独立运行。

**验证命令**

cd backend && pytest tests/scenarios/test_feishu_onboarding.py -q。

**前置依赖**

T36、T20、T21。

**后续任务**

T44。

**建议 Commit**

`task(T41): 实现飞书首次配置向导`

### T42 强化运行租约并实施数据生命周期

**目标**

强化运行租约并实施数据生命周期。

**业务价值**

减少慢外部调用或 Worker 抖动造成的错误并发接管；控制 PostgreSQL 容量，同时保留审批、报告、证据和审计事实。

**实现范围**

run/operation lease renewal、heartbeat、fencing token 和监控指标；分批 cleanup job、终态/unknown/waiting 排除、payload 先清理策略和审计。

**明确不包含**

不以 Redis 作为事实来源，不删除保留期内、被引用或处于活动运行的数据。

**主要改动范围**

runtime/leases、worker heartbeat 与 retention jobs。

**实现步骤**

加入 fencing/version；周期续租；数据库状态兜底；过期后先核验再接管；实现 dry-run；按表批处理；保护引用；记录清理数量和失败。

**测试要求**

Redis 重启、heartbeat 丢失、双 Worker、长调用、旧 fencing token；等待态、unknown、终态、边界日期、重复清理、事务失败。

**验收标准**

旧 Worker 无法覆盖新接管结果；Redis 丢失不破坏数据库事实；活动和未解决数据不会删除；清理可重入且有审计。

**验证命令**

cd backend && pytest tests/integration/recovery/test_lease_heartbeat.py -q；cd backend && pytest tests/integration/persistence/test_data_lifecycle.py -q。

**前置依赖**

T38、T39、T28。

**后续任务**

T43、T44。

**建议 Commit**

`task(T42): 强化运行租约并实施数据生命周期`

### T43 完成生产部署、CI、恢复演练与 SBOM

**目标**

完成生产部署、CI、恢复演练与 SBOM。

**业务价值**

让项目可在全新环境安全、可重复启动；发布候选能自动验证核心可靠性，而不是依赖手工回归；给出可操作的灾难恢复和供应链证据。

**实现范围**

多阶段镜像、healthcheck、Nginx HTTPS/路由限制、环境变量示例；CI service containers、测试分层、镜像构建、dependency/secret scan；备份/恢复脚本或命令、现有 README/02/06 运维章节、SBOM CI job。

**明确不包含**

不引入需求外云平台、Kubernetes 或复杂集群。

**主要改动范围**

deploy、CI、运维说明与备份恢复工具。

**实现步骤**

构建非 root 镜像；配置 healthcheck；只暴露允许路由；生产拒绝 local-demo；增加并行 jobs；Fake/真实测试标签隔离；缓存；失败产物脱敏；备份测试库；恢复新环境；resume waiting run；核验 unknown；生成镜像 SBOM。

**测试要求**

clean compose up、health/ready、容器重启、路由/默认凭证检查；clean CI 等价命令、migration up/down/up、local-demo E2E、镜像扫描；实际演练并记录脱敏结果；确保文档命令可复现。

**验收标准**

一键启动通过 ready；无默认弱密码/镜像 secret；internal/local-demo 不暴露；无真实凭证即可完成完整 Fake CI；真实 smoke 只能显式 opt-in；恢复后不重复副作用；SBOM 可由 CI 生成；不新建额外设计文档。

**验证命令**

docker compose config && docker compose up --build；执行项目 full-ci-local 命令和 docker compose config；执行项目 recovery-drill 和 sbom 命令。

**前置依赖**

T42、T37。

**后续任务**

T44。

**建议 Commit**

`task(T43): 完成生产部署、CI、恢复演练与 SBOM`

### T44 完成真实平台 E2E 与最终验收

**目标**

完成真实平台 E2E 与最终验收。

**业务价值**

形成 MVP 可用性的最终证据。

**实现范围**

真实两阶段 HITL、双源、多仓、报告、三项发布、后台、重复点击、重启恢复。

**明确不包含**

不新增功能；验收发现问题时只回到对应 Task 修复。

**主要改动范围**

e2e/real-platform、验收证据与 release checklist。

**实现步骤**

运行真实 smoke/E2E；更新未验证能力状态；记录 run_id 和脱敏证据；逐项对照 PRD 验收。

**测试要求**

PRD 14 场景、性能、安全、重复 callback、故障注入和 Compose。

**验收标准**

所有核心验收通过或有明确、经批准的限制；没有未验证的上线阻断能力。

**验证命令**

执行项目 full-ci、local-demo E2E 和显式 opt-in 的 real-platform E2E 命令。

**前置依赖**

T40、T41、T42、T43。

**后续任务**

无。

**建议 Commit**

`task(T44): 完成真实平台 E2E 与最终验收`

### M4 退出标准

- **可以做到**：完成配置、认证、调度、观测、向导、生命周期、部署与最终验收。
- **还不能做到**：不包含企业 SSO、复杂多租户、无限仓库、任意工具自治或 LLM Streaming。
- **必须通过的测试**：完整 CI、安全、浏览器 E2E、恢复演练和真实平台 E2E。
- **可演示结果**：从首次配置到定时生成、审批、发布、恢复和审计的完整演示。
- **进入下一阶段条件**：全部验收通过后才可发布 MVP；新增能力另立需求。

## 9. 旧任务到新任务映射

原计划共 77 个分层编号 Task，现合并为 44 个连续编号 Task。旧编号只允许出现在本节，用于审计历史引用。

| 旧任务 | 新任务 |
|---|---|
| T0.1 | T1 |
| T0.2 | T2 |
| T0.3 | T3 |
| T0.4 | T3 |
| T0.5 | T5 |
| T0.6 | T5 |
| T0.7 | T6 |
| T0.8 | T6、T22 |
| T0.9 | T8 |
| T0.10 | T7 |
| T0.11 | T7 |
| T0.12 | T7 |
| T0.13 | T8 |
| T1.1 | T9 |
| T1.2 | T9 |
| T1.3 | T10 |
| T1.4 | T11 |
| T1.5 | T11 |
| T1.6 | T11 |
| T1.7 | T12 |
| T1.8 | T13 |
| T1.9 | T13 |
| T1.10 | T14 |
| T1.11 | T15 |
| T1.12 | T15 |
| T1.13 | T16 |
| T1.14 | T16 |
| T1.15 | T16 |
| T1.16 | T17 |
| T1.17 | T17 |
| T1.18 | T18 |
| T2.1 | T19 |
| T2.2 | T19 |
| T2.3 | T20 |
| T2.4 | T20 |
| T2.5 | T20 |
| T2.6 | T21 |
| T2.7 | T22、T23 |
| T2.8 | T23 |
| T2.9 | T23 |
| T2.10 | T24 |
| T2.11 | T26 |
| T2.12 | T25 |
| T2.13 | T25 |
| T2.14 | T25 |
| T2.15 | T27 |
| T2.16 | T28 |
| T2.17 | T28 |
| T2.18 | T29 |
| T2.19 | T29 |
| T3.1 | T30 |
| T3.2 | T30 |
| T3.3 | T31 |
| T3.4 | T32 |
| T3.5 | T33 |
| T3.6 | T34 |
| T3.7 | T39 |
| T4.1 | T35 |
| T4.2 | T35 |
| T4.3 | T35 |
| T4.4 | T35 |
| T4.5 | T36 |
| T4.6 | T36 |
| T4.7 | T36 |
| T4.8 | T36 |
| T4.9 | T37 |
| T4.10 | T37 |
| T4.11 | T38 |
| T4.12 | T39 |
| T4.13 | T40 |
| T4.14 | T41 |
| T4.15 | T43 |
| T4.16 | T43 |
| T4.17 | T43 |
| T4.18 | T42 |
| T4.19 | T42 |
| T4.20 | T44 |

## 10. 后置或明确不进入 MVP 的能力

- **LLM Streaming**：不设实施 Task；只有用户研究证明长等待是主要问题后才另立需求。
- 企业 SSO、细粒度 RBAC、复杂多租户和跨组织管理。
- 超过五仓、无限 fan-out 和通用分布式工作流平台。
- 飞书业务表任意写入、自动删除已发布内容和破坏性补偿。
- 任意网页抓取、代码正文采集、任意 URL Tool 和模型直接执行副作用。
- 高级 BI、移动端、国际化及需求未定义指标。

## 11. 测试与 CI 增长路径

| 阶段 | 必跑门 |
|---|---|
| T1–T4 | 文档/Spike 证据评审与冻结检查 |
| T5–T8 | lint、typecheck、unit、migration、基础 integration |
| T9–T18 | graph/checkpoint、provider contract、Local-demo E2E |
| T19–T29 | sandbox integration、并发、fault injection、真实发布 E2E |
| T30–T34 | 策略预算、黄金指标、对抗安全、质量回归 |
| T35–T44 | API/UI/security E2E、完整 CI、恢复演练、真实平台验收 |

单 Task 运行与改动相关的最小测试集；Milestone 退出时运行累计回归。不得通过跳过测试把失败转移到后续 Task。

## 12. 仍需人工确认的问题

1. 首批 3–5 个核心指标的业务口径、时区与周区间。
2. 飞书租户、权限申请人、测试群、多维表格与归档资源。
3. GitHub 使用 Fine-grained PAT 还是 GitHub App，以及私有仓库权限边界。
4. LLM 提供商、允许模型、数据保留/出境要求与单次预算。
5. 两阶段审批人、代审批规则、超时策略与拒绝后的业务期望。
6. 真实发布测试范围、测试产物清理责任、生产部署与备份目标。

阻塞当前 Task 的问题未确认时必须停止，不得以扩大范围的假设继续。

## 13. Codex 单 Task 执行方式

1. 读取本计划、相关设计和目标 Task，确认前置依赖已验收。
2. 只列该 Task 的改动与测试，复核“明确不包含”。
3. 先建立能证明验收标准的测试，再做最小实现。
4. 运行验证命令和受影响回归，记录真实结果。
5. 检查迁移所有权、幂等、安全日志和文档一致性。
6. 只提交该 Task 的必要变更，然后停止等待审核。

## 14. 第一个可执行 Task

**T1 建立外部能力验证矩阵**。它不依赖代码或外部写操作。T2/T3 必须引用其验证项；T4 修正并冻结协议之前不得开始 T5 及后续编码任务。

## 15. 开始与停止条件

- **开始条件**：前置 Task 已验收，所需人工输入和测试资源齐备。
- **停止条件**：当前 Task 验收标准满足且验证命令通过，立即等待审核。
- **阻塞条件**：能力与冻结设计冲突、需新权限、需扩大 MVP、迁移所有权冲突或无法证明副作用安全。
- **禁止行为**：跳 Task、顺手实现后续能力、改写未验证协议、删除测试换取通过、未批准执行真实发布。

## 16. T4 执行记录（2026-07-27）

`.env` 完整性审计通过，三个 Provider 配置检查器均返回 `status=ready`；但三者均明确 `network_calls_made=false`。因此 T4 已完成跨文档边界和条件冻结记录，但正式验收未通过：阻塞性未知项尚未清零，不能开始 T5 及后续编码。

正式冻结前仍需取得并记录：飞书真实回调/卡片/多维表格/文档/消息 Contract Test，GitHub 两个测试仓库的最小权限与错误分类 Contract Test，以及 LLM schema、usage、429、timeout 和模型能力 Contract Test。

## 17. T44 首轮执行记录（2026-07-31）

### 17.1 本地验收结果

- 后端完整 `tests` 测试集通过；此前失败的指标版本、发布计划终态、production 配置夹具和 `onboarding_sessions` 表清单已按既有 T33/T16/T20/T41 契约同步。
- `full-ci-local` 已扩展为执行 unit、contract、integration、scenarios 和 e2e，避免局部测试通过掩盖累计回归。
- local-demo happy path、Compose health/ready、外部 `/internal/*` 隔离以及数据库备份/恢复演练已通过；恢复演练产生的容器和临时数据卷已清理。
- 全新 Compose 数据卷启动后容器可进入 healthy，但业务表尚不存在；手动执行 `docker compose exec -T backend alembic upgrade head` 后才能创建 local-demo 运行，说明 T43 的“一键启动”验收仍有迁移缺口。
- 手动迁移后，运行详情页面及 `/api/v1/admin/runs/{run_id}` 可访问；但 `/api/v1/admin/dashboard` 和 `/api/v1/admin/runs` 均返回 404，dashboard/run-list 页面最终渲染为 `Failed to load` 与 `NEXT_NOT_FOUND`，说明 T39/T40 的查询 API 与 UI 联调验收未闭环。
- 内置浏览器还会把本机和私网目标隔离到其自身的 `https://localhost`，无法访问宿主机端口；本轮未取得 DOM 级浏览器 E2E 证据，checklist 保持未通过。

### 17.2 真实平台预检结果

- 飞书鉴权成功；测试多维表格字段和记录读取均被业务码 `99991672` 拒绝，缺少应用身份的多维表格读取权限。
- GitHub 两个测试仓均对当前 PAT 返回 HTTP 404，尚不能证明仓库存在性、授权范围或核心实体读取能力。
- LLM 原配置模型名无效；`deepseek-v4-flash` 的最小 JSON Output 与 usage 探测成功，但错误矩阵和完整报告 schema 尚未验证。
- 本轮没有执行真实卡片、文档、群消息或归档写入，也没有生成可记录的真实平台 `run_id`。

### 17.3 Release checklist

- [x] 后端完整测试集通过。
- [x] local-demo E2E 通过。
- [x] Compose health/ready 与公网路由限制通过。
- [x] 备份、清库、恢复和恢复后记录校验通过。
- [x] 扩展后的 `full-ci-local` 在当前变更上完整复跑通过。
- [ ] 浏览器 E2E 通过。
- [ ] 飞书 F-01–F-10 Contract Test 取得脱敏真实证据。
- [ ] GitHub G-01–G-10 Contract Test 取得脱敏真实证据。
- [ ] LLM L-01–L-03 Contract Test 取得脱敏真实证据。
- [ ] 真实两阶段 HITL、双源、多仓和重复点击通过。
- [ ] 真实文档、群消息和多维表格归档三步发布通过。
- [ ] 真实运行完成重启恢复并记录 `run_id`、审计轨迹和脱敏证据。

### 17.4 当前阻塞

1. 飞书管理员需为应用开通多维表格读取权限，并确保测试多维表格将该应用加入可访问范围。
2. GitHub 管理员需确认两个 `owner/repo` 标识，并将两个仓库加入 Fine-grained PAT 的 Repository access；至少授予 Metadata、Contents、Issues 和 Pull requests 只读权限。
3. LLM 配置需将模型更新为当前 Provider 支持的模型，并由产品/安全负责人确认预算、数据保留和出境策略。
4. 执行真实写入前，需确认公网 HTTPS 回调地址、飞书事件/卡片回调配置、测试产物保留或清理责任，并明确批准真实发布范围。
5. T43 需补齐 clean Compose 启动时的自动迁移或等价单命令编排，再重新执行“一键启动”验收。
6. T20/T21/T25/T13/T23 的真实多维表格、卡片、文档/消息/归档、LLM 适配器及 production runtime 组装尚未完整接入；按本计划 T44 验收失败回退规则，应先回到对应 Task 修复，不能在 T44 中用 Fake 结果替代真实证据。
7. T39/T40 需补齐 dashboard 与 run-list 查询 API，并增加覆盖真实前后端路由的集成/E2E 测试；当前仅前端 fixture 测试通过，部署后页面实际加载失败。
8. 修复第 7 项后，浏览器 E2E 需在能够直接访问宿主机 `localhost` 的浏览器执行环境中复跑管理仪表盘、运行列表和运行详情页。

依据本计划第 12、15 节，以上阻塞清零前不得执行真实发布，T44 状态保持未完成。
