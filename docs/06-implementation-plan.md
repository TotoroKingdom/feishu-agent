# 飞书项目周报 Agent：分阶段实施与测试计划

> 文档编号：PLAN-006
> 对应需求：01-feishu-project-weekly-agent-prd.md v1.0
> 依赖设计：02-architecture-design.md、03-database-design.md、04-api-design.md、05-langgraph-design.md
> 状态：待评审；评审通过后仍必须一次只执行一个 Task

## 1. 执行策略

本计划采用“先纵向闭环，再逐步强化”，而不是先横向完成所有基础设施。

执行纪律：

1. Codex 一次只接收并执行一个 Txx.x Task。
2. 每个 Task 只交付一个主要能力，通常涉及约 5～12 个主要代码文件。
3. 每个 Task 同时包含实现和测试，不把测试留到 Milestone 末尾。
4. 每个 Task 完成后必须运行验证命令、汇报结果并停止，等待人工验收。
5. 未经明确指令不得自动继续下一个 Task、提交 Git、推送或创建 PR。
6. 数据库表随首个业务调用方加入；一个数据库 Task 最多一个主要 migration。
7. 真实平台测试与 Fake Adapter 测试分离。
8. Fake 只替代外部平台，不绕过 Graph、Checkpoint、HITL、plan_hash 或 SideEffectExecutor。
9. Graph 只依赖 RunCreationService，不依赖 Scheduler。
10. 正常报告路径不依赖完整诊断循环。
11. 所有秘密、完整原始数据和 SDK Client 均不得进入 LangGraph State。
12. 实施中发现设计冲突时，先停止并直接修正现有 02～06 文档，不创建新文档。

## 2. Milestone 总览

| Milestone | 目标 | 可演示出口 |
|---|---|---|
| Milestone 0 | 能力验证与本地开发底座 | local-demo 可手动创建 run，Fake Port 和基础 CI 可用 |
| Milestone 1 | 最小 Agent 纵向闭环 | 单项目、单表、单仓、3～5 指标、两次 HITL、三项 Fake 发布、最小运行详情 |
| Milestone 2 | 可靠性与真实适配器 | 多仓、真实 callback/adapter、幂等 ledger、unknown 核验、部分失败和重启恢复 |
| Milestone 3 | Agent Loop 与质量强化 | Observe-Diagnose-Plan-Act-Verify、人工补充、再生成、Grounding 和注入防护 |
| Milestone 4 | 产品化与部署 | 完整配置、认证强化、Scheduler、完整后台、首次配置向导、真实 E2E 和部署 |

依赖主线：

    T0.1～T0.4 能力验证
      → T0.5～T0.13 local-demo 底座
      → T1.1～T1.18 最小纵向闭环
      → T2.1～T2.19 可靠性与真实平台
      → T3.1～T3.7 Agent Loop
      → T4.1～T4.20 产品化

同一 Milestone 中只有明确标注无依赖的 Task 才可并行，但 Codex 当前执行仍遵循“一次一个 Task”。

## 3. Milestone 0：能力验证与本地开发底座

local-demo 的目标配置：

```env
APP_PROFILE=local-demo
FEISHU_PROVIDER=fake
GITHUB_PROVIDER=fake
LLM_PROVIDER=fake
```

固定场景至少包括：

- `happy_path`
- `github_repository_failure`
- `feishu_critical_field_missing`
- `side_effect_partial_failure`

模拟 HITL 必须经过同一 Approval Service；模拟文档、群消息和归档必须经过同一 SideEffectExecutor。

### T0.1 建立外部能力验证矩阵

**目标**

把飞书、GitHub 和 LLM 的验证项、状态与阻断级别写回现有架构文档。

**业务价值**

避免先冻结错误假设，也避免暂时缺少真实环境时阻塞 Fake 主链。

**实现范围**

更新 02-architecture-design.md 第 4、5、15 节；每项标记 verified、unverified、degraded 或 not_required。

**明确不包含**

不写业务代码，不新建能力报告或决策文档。

**涉及文件**

docs/02-architecture-design.md。

**实现步骤**

整理能力项；记录验证条件、Fake 行为、业务影响和上线前 Contract Test；标记阻断项。

**测试要求**

逐项对照 PRD 和附件要求；检查无新增文件。

**验收标准**

所有外部能力都有状态、负责人/条件和下一步；未验证项不会阻塞 local-demo。

**验证命令**

git diff --check；git status --short。

**前置依赖**

当前 02～06 文档评审通过。

**后续任务**

T0.2、T0.3、T0.4。

**建议 Commit**

docs(T0.1): establish capability validation matrix

### T0.2 执行飞书能力 Spike

**目标**

验证 callback、卡片、身份、多维表格、文档、群消息和归档所需飞书能力。

**业务价值**

冻结真实 Feishu Port 的协议、权限和错误语义。

**实现范围**

最小 Spike；脱敏记录结果到 02-architecture-design.md；必要时更新 04-api-design.md。

**明确不包含**

不实现生产适配器，不创建新文档，不把真实 payload 提交仓库。

**涉及文件**

scripts/spikes/feishu_spike.py；docs/02-architecture-design.md；docs/04-api-design.md；临时本地环境文件不提交。

**实现步骤**

验证 challenge/签名/重复投递；卡片动作和 actor；表 schema/分页；文档与消息外部 ID；归档 upsert/查询。

**测试要求**

真实 sandbox 可用则执行；不可用则记录 unverified 原因、Fake 合约和上线前测试。

**验收标准**

每项有 verified/degraded/unverified 结论；无秘密进入 git diff。

**验证命令**

python scripts/spikes/feishu_spike.py --check-config；git diff --check。

**前置依赖**

T0.1；飞书 sandbox 可选。

**后续任务**

T0.4、T2.3～T2.7。

**建议 Commit**

chore(T0.2): validate feishu capabilities

### T0.3 执行 GitHub 能力 Spike

**目标**

验证 Fine-grained PAT、分页、时间过滤、限流和必需只读 endpoint。

**业务价值**

冻结 GitHub 权限清单和数据采集边界。

**实现范围**

两个测试仓库；记录 metadata、issues、PR、commits、reviews、milestones、contributors 的结果。

**明确不包含**

不实现生产 GitHub adapter，不验证 Actions 可选能力。

**涉及文件**

scripts/spikes/github_spike.py；docs/02-architecture-design.md；必要的脱敏临时输出不提交。

**实现步骤**

验证 PAT 权限/过期；Issue 排除 PR；分页与 since/until；限流 headers；私有/无权仓错误。

**测试要求**

有真实 PAT 时运行；否则写明 Fake 语义和上线前 Contract Test。

**验收标准**

最小权限和错误分类有结论；无 token 出现在输出或 diff。

**验证命令**

python scripts/spikes/github_spike.py --check-config；git diff --check。

**前置依赖**

T0.1；测试 PAT 可选。

**后续任务**

T0.4、T2.7～T2.10。

**建议 Commit**

chore(T0.3): validate github capabilities

### T0.4 执行 LLM Spike并冻结受影响决策

**目标**

验证 OpenAI 兼容结构化输出、usage、超时和错误行为，并修正现有文档。

**业务价值**

让报告链可针对真实能力选择原生 schema 或受控 JSON fallback。

**实现范围**

默认 DeepSeek；将 T0.2/T0.3/T0.4 结果写回 02、04、05、06 的相关段落。

**明确不包含**

不实现正式 Provider，不要求 Streaming。

**涉及文件**

scripts/spikes/llm_spike.py；docs/02-architecture-design.md；docs/04-api-design.md；docs/05-langgraph-design.md；docs/06-implementation-plan.md。

**实现步骤**

验证 schema、usage、429/timeout；记录模型差异；关闭阻断问题；冻结已验证协议和数据口径。

**测试要求**

结构合法/非法样例；secret scan；文档交叉检查。

**验收标准**

顺序完成“Spike → 决策 → 修正文档 → 冻结”；未验证项有 Fake 和上线门槛。

**验证命令**

python scripts/spikes/llm_spike.py --check-config；git diff --check。

**前置依赖**

T0.2、T0.3。

**后续任务**

T0.5。

**建议 Commit**

docs(T0.4): freeze validated external contracts

### T0.5 初始化工程骨架

**目标**

建立 FastAPI、Next.js、测试目录和 Docker Compose 骨架。

**业务价值**

提供所有后续 Task 的最小可运行工程。

**实现范围**

后端/前端空应用、版本固定、基础测试命令和 Compose config。

**明确不包含**

不接数据库表，不实现认证、Graph 或外部 adapter。

**涉及文件**

backend/pyproject.toml；backend/app/main.py；backend/tests/test_smoke.py；frontend/package.json；frontend/src/app/page.tsx；docker-compose.yml；.env.example；README.md。

**实现步骤**

初始化工程；固定核心依赖；建立 lint/type/test/build 命令；添加 smoke test。

**测试要求**

后端 smoke、前端 lint/type/build、Compose 配置解析。

**验收标准**

全新环境可安装和运行 smoke；无业务逻辑和 secret。

**验证命令**

cd backend && pytest tests/test_smoke.py -q；cd frontend && npm run lint && npm run typecheck && npm run build；docker compose config。

**前置依赖**

T0.4。

**后续任务**

T0.6、T0.7。

**建议 Commit**

chore(T0.5): scaffold application workspace

### T0.6 建立基础 CI

**目标**

从工程骨架阶段执行质量门禁。

**业务价值**

每个后续 Task 都能获得即时回归反馈。

**实现范围**

后端 lint/format/type/unit，前端 lint/type/build，Compose config，Alembic 空迁移链 smoke 和 secret scan。

**明确不包含**

不做真实平台 smoke、镜像发布、SBOM 或高级压测。

**涉及文件**

.github/workflows/ci.yml；backend/alembic.ini 和空 migration env；backend/pyproject.toml；frontend/package.json；secret scan 配置；README.md。

**实现步骤**

配置缓存和独立 jobs；初始化 Alembic env；即使尚无 revision 也执行 upgrade head；记录本地等价命令。

**测试要求**

本地执行等价命令；Alembic 空链 smoke；用无害测试串验证 secret scanner 后移除。

**验收标准**

基础 CI 可在 clean checkout 通过；包含 Alembic smoke；不依赖真实凭证。

**验证命令**

项目定义的 ci-local 命令；docker compose config。

**前置依赖**

T0.5。

**后续任务**

所有编码 Task。

**建议 Commit**

ci(T0.6): add baseline quality gates

### T0.7 配置、日志、脱敏和健康检查

**目标**

建立 local-demo/production 配置剖面、结构化日志、统一错误和 health/ready。

**业务价值**

让 Fake/真实 provider 切换显式且安全。

**实现范围**

APP_PROFILE、三类 provider 选择、request_id、敏感字段过滤、health/ready。

**明确不包含**

不实现业务凭证入库和完整 tracing。

**涉及文件**

backend/app/core/config.py；backend/app/core/errors.py；backend/app/observability/logging.py；backend/app/security/redaction.py；backend/app/api/health/routes.py；backend/app/api/errors.py；对应测试。

**实现步骤**

定义 Pydantic settings；生产拒绝 fake；建立 JSON 日志上下文；实现脱敏和健康端点。

**测试要求**

配置矩阵、递归脱敏、错误不含堆栈、依赖异常 ready 测试。

**验收标准**

local-demo 可显式启动；production 配置不能启用模拟入口；日志无 secret。

**验证命令**

cd backend && pytest tests/unit/core tests/unit/security tests/integration/health -q。

**前置依赖**

T0.5、T0.6。

**后续任务**

T0.8、T0.10。

**建议 Commit**

feat(T0.7): add safe runtime profiles and health

### T0.8 实现业务凭证加密原语

**目标**

提供带 key version 的 AEAD 服务和 write-only DTO 基础。

**业务价值**

后续 GitHub PAT、飞书 Secret 和 LLM Key 不以明文持久化。

**实现范围**

加解密、tamper 检测、指纹和安全异常。

**明确不包含**

不创建 credential 表，不实现凭证页面。

**涉及文件**

backend/app/security/encryption.py；backend/app/security/fingerprints.py；backend/app/schemas/secrets.py；对应单元测试。

**实现步骤**

实现 AEAD；限定调用接口；禁止 secret repr；加入测试向量。

**测试要求**

round-trip、错误 key、篡改、空值、异常脱敏。

**验收标准**

密文含 key version/nonce；任何响应 model 不定义明文输出字段。

**验证命令**

cd backend && pytest tests/unit/security/test_encryption.py -q。

**前置依赖**

T0.7。

**后续任务**

T0.9、T2.7、T4.4。

**建议 Commit**

feat(T0.8): add versioned credential encryption

### T0.9 添加最小项目配置数据库迁移

**目标**

只创建 local-demo 当前需要的项目、仓库和飞书资源最小表。

**业务价值**

避免业务代码前一次性创建完整最终 schema。

**实现范围**

DB-0 迁移、SQLAlchemy 模型、最小 repository。

**明确不包含**

不创建凭证、run、report、operation、scheduler、auth 或 audit 表。

**涉及文件**

backend/app/persistence/db.py；backend/app/persistence/models/config.py；backend/app/persistence/repositories/projects.py；一个 Alembic migration；集成测试。

**实现步骤**

实现最小字段和约束；seed 单项目 local-demo；迁移 up/down/up。

**测试要求**

PostgreSQL 迁移、唯一约束、repository round-trip。

**验收标准**

只有当前调用方需要的表；一个主要 migration；down 后可再次 up。

**验证命令**

cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/integration/persistence/test_project_config.py -q。

**前置依赖**

T0.7、T0.8。

**后续任务**

T0.13。

**建议 Commit**

feat(T0.9): add minimal project persistence

### T0.10 定义外部 Port 和 Tool 基础协议

**目标**

定义 Feishu、GitHub、LLM Port 及只读 Tool 的输入输出和错误分类。

**业务价值**

让 Fake 与真实 adapter 可替换，Graph 不依赖 SDK。

**实现范围**

Protocol、DTO、ToolSpec、ToolContext、ToolResult、registry allowlist。

**明确不包含**

不实现重试引擎、真实 API 或副作用 handler。

**涉及文件**

backend/app/tools/base.py；backend/app/tools/registry.py；backend/app/integrations/feishu/models.py；backend/app/integrations/github/models.py；backend/app/integrations/llm/provider.py；契约测试基类。

**实现步骤**

定义稳定 schema；建立错误 taxonomy；禁止动态 Tool 注册。

**测试要求**

DTO schema、未知 Tool 拒绝、SDK 类型隔离检查。

**验收标准**

领域/Graph 只依赖 Port；三类 provider 可由配置选择。

**验证命令**

cd backend && pytest tests/unit/tools tests/contract/test_port_contracts.py -q。

**前置依赖**

T0.7。

**后续任务**

T0.11、T0.12。

**建议 Commit**

feat(T0.10): define provider ports and tool contracts

### T0.11 固定演示数据集和 Fake 读取适配器

**目标**

提供正常、仓库失败和关键字段缺失的固定输入。

**业务价值**

真实平台不可用时仍可开发 Graph 采集与校验路径。

**实现范围**

一个飞书逻辑表、一个 GitHub 仓库的 Fake read；可切换三个场景。

**明确不包含**

不模拟 LLM 和发布副作用，不实现多仓并发。

**涉及文件**

backend/tests/fixtures/datasets/；backend/app/integrations/feishu/fake.py；backend/app/integrations/github/fake.py；backend/app/local_demo/scenarios.py；契约测试。

**实现步骤**

定义无敏感数据 fixture；实现确定性分页/错误；让 Fake 通过 Port 契约。

**测试要求**

golden fixture、场景切换、重复读取稳定性、secret scan。

**验收标准**

三个场景可复现；Fake 返回稳定 external ID；不访问网络。

**验证命令**

cd backend && pytest tests/contract/test_fake_read_adapters.py tests/unit/local_demo -q。

**前置依赖**

T0.10。

**后续任务**

T1.4、T1.5。

**建议 Commit**

test(T0.11): add deterministic local demo sources

### T0.12 实现 Fake LLM 和 Fake 发布结果

**目标**

补齐 local-demo 的 Fake LLM 和三类副作用结果。

**业务价值**

形成最小 Agent 闭环所需的全部出站外部替身。

**实现范围**

Fake structured report；文档/群/归档结果模拟；happy/partial-failure 场景。

**明确不包含**

不实现 Graph、审批、SideEffectExecutor、RunCreationService 或 HTTP 入口。

**涉及文件**

backend/app/integrations/llm/fake.py；backend/app/integrations/feishu/fake_effects.py；Fake 契约测试。

**实现步骤**

实现稳定结果 ID；按 scenario 返回 success/failed/unknown；通过现有 Port 契约。

**测试要求**

固定 LLM 输出、三类结果稳定性、partial failure fixture、无网络访问。

**验收标准**

Fake 输出可确定性复现；尚未执行 Graph 或写数据库。

**验证命令**

cd backend && pytest tests/contract/test_fake_llm.py tests/contract/test_fake_effects.py -q。

**前置依赖**

T0.10、T0.11。

**后续任务**

T0.13。

**建议 Commit**

test(T0.12): add deterministic fake llm and effects

### T0.13 实现 RunCreationService 和手动入口

**目标**

通过统一服务手动创建最小 run，并提供 local-demo HTTP 入口。

**业务价值**

让 Graph 尽早可启动且完全不依赖 Scheduler。

**实现范围**

RunCreationService；周期/单项目校验；POST local-demo/runs；最小 run persistence 扩展。

**明确不包含**

不实现 Scheduler、Graph、HITL 或真实管理员认证。

**涉及文件**

backend/app/application/services/run_creation.py；backend/app/api/local_demo/runs.py；最小 run model/repository 扩展；对应测试。

**实现步骤**

校验 scenario 和周期；生产不注册路由；创建唯一 run_id/thread_id；返回 run 摘要。

**测试要求**

同请求幂等、同周期冲突、非法 scenario、production 路由禁用。

**验收标准**

local-demo 可手动创建 run；Scheduler 尚不存在；尚未执行 Graph。

**验证命令**

cd backend && pytest tests/integration/local_demo/test_run_creation.py -q。

**前置依赖**

T0.9、T0.12。

**后续任务**

T1.1。

**建议 Commit**

feat(T0.13): add manual run creation service

## 4. Milestone 1：最小 Agent 纵向闭环

Milestone 1 固定范围：单项目、一个飞书逻辑表、一个 GitHub 仓库、3～5 个核心指标、手动触发、Fake provider、基础 SideEffectExecutor 和最小运行详情。完成后必须能独立演示。

### T1.1 添加运行、审批和 Checkpoint 最小迁移

**目标**

创建最小 Graph 运行和 HITL 持久化事实。

**业务价值**

支持 interrupt/resume 和重启后的等待态恢复。

**实现范围**

report_runs、run_status_history、human_approvals、官方 PostgreSQL Checkpointer 表。

**明确不包含**

不创建采集、报告、operation 或完整观测表。

**涉及文件**

运行/审批 ORM；repository；一个 Alembic migration；checkpoint 配置；迁移测试。

**实现步骤**

实现状态约束和 thread_id；接入固定版本 checkpointer；扩展 RunCreationService。

**测试要求**

up/down/up、同周期活动唯一、审批 pending 唯一、checkpoint round-trip。

**验收标准**

手动 run 有稳定 thread；等待态可持久化；一个主要 migration。

**验证命令**

cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/integration/persistence/test_run_approval.py -q。

**前置依赖**

T0.13。

**后续任务**

T1.2。

**建议 Commit**

feat(T1.1): persist runs approvals and checkpoints

### T1.2 建立 LangGraph State 和最小骨架

**目标**

实现可启动、记录当前节点并进入终态的最小 Graph。

**业务价值**

尽早验证 State、thread 和 PostgreSQL Checkpoint 集成。

**实现范围**

State schema/reducer、graph builder、load config、terminal nodes。

**明确不包含**

不实现采集、报告、诊断或发布。

**涉及文件**

backend/app/agent/state/；backend/app/agent/graph/builder.py；backend/app/agent/nodes/scope.py；terminal.py；Graph 测试。

**实现步骤**

定义版本化 State；State 只放引用；接入 Worker start；记录状态。

**测试要求**

State 序列化、敏感字段扫描、Graph start/end、重复 start。

**验收标准**

手动 run 可由 Worker 以同一 thread 启动；Checkpoint 可读取。

**验证命令**

cd backend && pytest tests/unit/agent/state tests/integration/agent/test_graph_skeleton.py -q。

**前置依赖**

T1.1。

**后续任务**

T1.3。

**建议 Commit**

feat(T1.2): add checkpointed graph skeleton

### T1.3 实现 HITL 1 最小确认

**目标**

构造范围、interrupt，并通过 local-demo action resume。

**业务价值**

最早打通第一阶段人工控制。

**实现范围**

单仓/单表 scope；approve、modify period、cancel；approval revision/hash。

**明确不包含**

不接真实飞书 callback，不支持多接收人。

**涉及文件**

scope/approval nodes；ApprovalService；local-demo actions API；审批测试。

**实现步骤**

生成 scope hash；持久化 approval；interrupt；验证 actor/revision/hash；Command resume。

**测试要求**

批准、修改、取消、重复、旧 revision、重启等待态。

**验收标准**

批准前无采集；重复 action 只 resume 一次；修改产生新 revision。

**验证命令**

cd backend && pytest tests/integration/agent/test_hitl_generation.py -q。

**前置依赖**

T1.2。

**后续任务**

T1.4。

**建议 Commit**

feat(T1.3): add first-stage approval interrupt

### T1.4 添加原始批次和标准化快照迁移

**目标**

为单表单仓采集提供引用存储。

**业务价值**

确保大原始数据不进入 State。

**实现范围**

source_data_batches、normalized_snapshots、normalized_entities、validation_results 和最小 tool_executions。

**明确不包含**

不创建 metrics/report/evidence 表。

**涉及文件**

采集/Tool execution ORM 与 repository；一个 Alembic migration；迁移和 repository 测试。

**实现步骤**

实现 batch hash、来源、周期和 snapshot grouping；设置数据上限。

**测试要求**

up/down/up、JSONB round-trip、hash 唯一、State 仅保存 refs。

**验收标准**

采集结果可按 run 查询；一个主要 migration。

**验证命令**

cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/integration/persistence/test_source_batches.py -q。

**前置依赖**

T1.3。

**后续任务**

T1.5。

**建议 Commit**

feat(T1.4): persist source and normalized snapshots

### T1.5 接入单表和单仓 Fake 采集节点

**目标**

在 HITL 1 后读取一个飞书逻辑表和一个 GitHub 仓库。

**业务价值**

打通真实业务数据形状的最小采集路径。

**实现范围**

两个只读节点、Tool execution 最小摘要、batch 落库。

**明确不包含**

不做多仓并发、自动重试或完整分页优化。

**涉及文件**

collection nodes；ToolExecutor 最小实现；source service；对应 Graph 测试。

**实现步骤**

按 scope 调用 Fake；保存 batch；State 写 ref；单次失败直接安全失败。

**测试要求**

happy、仓库失败、重复节点复用 batch。

**验收标准**

批准后才采集；Checkpoint 不含 payload；失败有错误摘要。

**验证命令**

cd backend && pytest tests/integration/agent/test_minimal_collection.py -q。

**前置依赖**

T1.4、T0.11。

**后续任务**

T1.6。

**建议 Commit**

feat(T1.5): collect minimal fake project data

### T1.6 实现最小标准化和校验

**目标**

将单表/单仓数据映射到统一模型并判断最小必需字段。

**业务价值**

报告不直接基于未校验原始上下文。

**实现范围**

字段映射、去重、UTC 半开区间、happy/blocked 两种校验结果。

**明确不包含**

不实现完整问题分类、降级或诊断循环。

**涉及文件**

reports/normalization/；reports/validation/；validation node；固定数据测试。

**实现步骤**

定义统一实体；标准化；落 snapshot/entity；执行最小 required rules。

**测试要求**

时间边界、重复、Issue 排除 PR、关键字段缺失。

**验收标准**

happy 直达 metrics；blocked 安全停止并记录问题，不进入诊断。

**验证命令**

cd backend && pytest tests/unit/reports/normalization tests/unit/reports/validation tests/integration/agent/test_minimal_validation.py -q。

**前置依赖**

T1.5。

**后续任务**

T1.7。

**建议 Commit**

feat(T1.6): normalize and validate minimal dataset

### T1.7 计算首批核心指标

**目标**

确定性计算新增/关闭 Issue、合并 PR、Commit 数和计划完成率中的 3～5 项。

**业务价值**

在纵向闭环中证明 LLM 不负责数值计算。

**实现范围**

口径版本、metric schema、纯函数和 metric snapshot 最小持久化。

**明确不包含**

不实现全部 11 项指标和人员负载。

**涉及文件**

reports/metrics/；metric snapshot 模型/迁移扩展；metrics node；golden tests。

**实现步骤**

实现空分母/周期边界；保存 definition_version 和 content hash。

**测试要求**

表驱动 golden、跨周期、空数据、重复数据。

**验收标准**

指标可重复且来源 snapshot 可追溯；一个小 migration 或与当前调用方同 Task 扩展。

**验证命令**

cd backend && pytest tests/unit/reports/metrics tests/integration/agent/test_metrics_node.py -q。

**前置依赖**

T1.6。

**后续任务**

T1.8。

**建议 Commit**

feat(T1.7): calculate first deterministic metrics

### T1.8 添加最小报告和证据迁移

**目标**

持久化 evidence set、report version 和 claim 引用。

**业务价值**

让结构化报告与来源可追溯。

**实现范围**

metric_snapshots 补全、evidence_sets/items、report_versions、report_claims/evidence 的最小字段。

**明确不包含**

不创建 publish plan 或 operation 表。

**涉及文件**

报告 ORM/repository；一个 Alembic migration；迁移测试。

**实现步骤**

建立不可变版本和 hash；实现 evidence allowlist 查询。

**测试要求**

up/down/up、FK、重复 claim/evidence 约束。

**验收标准**

报告版本能引用 metric/evidence snapshot；一个主要 migration。

**验证命令**

cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/integration/persistence/test_report_models.py -q。

**前置依赖**

T1.7。

**后续任务**

T1.9。

**建议 Commit**

feat(T1.8): persist minimal report evidence model

### T1.9 生成结构化周报

**目标**

使用 Fake LLM 从已校验指标和 evidence 生成 PRD 结构化结果。

**业务价值**

打通 Agent 报告生成核心，而不等待完整诊断循环。

**实现范围**

安全输入、schema 校验、report version；一次失败即安全失败。

**明确不包含**

不实现 schema 修复循环、Streaming 或 Prompt 管理 UI。

**涉及文件**

reports/generation/；LLM node；schema；Fake LLM contract；测试。

**实现步骤**

构造限长输入；调用 Provider；Pydantic 校验；保存版本和 token 摘要。

**测试要求**

合法/非法 schema、指标值不被 LLM 改写、State 只存 report ref。

**验收标准**

合法结构化结果落库；非法结果不能进入 Grounding。

**验证命令**

cd backend && pytest tests/unit/reports/generation tests/integration/agent/test_structured_report.py -q。

**前置依赖**

T1.8、T0.12。

**后续任务**

T1.10。

**建议 Commit**

feat(T1.9): generate structured weekly report

### T1.10 实现基础 Grounding 和渲染

**目标**

验证关键 claim 的 evidence ID/周期并渲染最小正文。

**业务价值**

阻止无来源关键事实进入发布。

**实现范围**

确定性引用检查、fact/inference 标记、从 verified structure 渲染。

**明确不包含**

不做语义相似度、高级修复或 Prompt Injection 强化。

**涉及文件**

reports/verification/；reports/rendering/；grounding/render nodes；测试。

**实现步骤**

核对 allowlist；拒绝未知 evidence；生成 rendered content hash。

**测试要求**

有效引用、未知 ID、周期错配、renderer 新增事实检查。

**验收标准**

无证据关键 claim 被拒绝；正文不新增结构外事实。

**验证命令**

cd backend && pytest tests/unit/reports/verification tests/unit/reports/rendering tests/integration/agent/test_grounding.py -q。

**前置依赖**

T1.9。

**后续任务**

T1.11。

**建议 Commit**

feat(T1.10): verify grounding and render report

### T1.11 添加发布计划和 Operation 迁移

**目标**

持久化 canonical publish plan、三项 operation 和 artifact。

**业务价值**

为 HITL 2 和安全副作用提供 ledger。

**实现范围**

publish_plans、side_effect_operations、side_effect_attempts、report_artifacts。

**明确不包含**

不执行任何 handler，不实现 unknown verifier。

**涉及文件**

发布 ORM/repository；一个 Alembic migration；迁移测试。

**实现步骤**

实现状态 CHECK、sequence/idempotency 唯一、payload/target hash。

**测试要求**

up/down/up、约束、operation 顺序和状态转换基础。

**验收标准**

三项 operation 可冻结；一个主要 migration。

**验证命令**

cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/integration/persistence/test_publish_models.py -q。

**前置依赖**

T1.10。

**后续任务**

T1.12。

**建议 Commit**

feat(T1.11): persist publish plan and operations

### T1.12 实现 plan_hash 和 HITL 2

**目标**

冻结报告、目标和操作，interrupt 并验证批准 hash。

**业务价值**

任何业务写入前获得可审计人工授权。

**实现范围**

canonical JSON、SHA-256、approve/regenerate/cancel 的最小路由。

**明确不包含**

regenerate 暂返回原报告链入口，不实现高级缓存策略。

**涉及文件**

side_effects/planner.py；canonicalize.py；publish approval nodes；local-demo actions；测试。

**实现步骤**

生成 plan；保存 approval revision；interrupt；resume 重算 hash。

**测试要求**

字段顺序/Unicode/时间稳定性、旧 revision、目标/内容变化、重复批准。

**验收标准**

hash 不匹配零副作用；批准后只允许原计划。

**验证命令**

cd backend && pytest tests/unit/side_effects/test_canonicalize.py tests/integration/agent/test_hitl_publish.py -q。

**前置依赖**

T1.11。

**后续任务**

T1.13。

**建议 Commit**

feat(T1.12): freeze and approve publish plan

### T1.13 实现基础 SideEffectExecutor 和文档 handler

**目标**

验证 plan_hash 后按 ledger 执行 Fake create-document operation。

**业务价值**

建立所有写操作必须经过的单一入口。

**实现范围**

executor、operation 状态机、Fake 文档 handler、succeeded 去重基础。

**明确不包含**

不实现并发 claim、unknown 核验或部分失败恢复。

**涉及文件**

side_effects/executor.py；handlers/document.py；publishing node；repository；测试。

**实现步骤**

执行前验证审批/hash/sequence；写 attempt；保存 artifact；重复执行读取 ledger。

**测试要求**

未批准、hash mismatch、成功、失败、重复调用。

**验收标准**

同 operation 最多一次 Fake 外部创建；成功有 external ID。

**验证命令**

cd backend && pytest tests/unit/side_effects/test_executor.py tests/integration/agent/test_document_operation.py -q。

**前置依赖**

T1.12。

**后续任务**

T1.14。

**建议 Commit**

feat(T1.13): execute approved document operation

### T1.14 添加 Fake 群摘要 Handler

**目标**

在文档成功后按计划发送 Fake 群摘要。

**业务价值**

验证第二项发布 operation 的依赖顺序和 ledger 复用。

**实现范围**

群消息 handler、文档依赖和 message artifact。

**明确不包含**

不实现归档、最终 complete_run、partial failure 补偿或真实飞书。

**涉及文件**

handlers/group_message.py；对应 publishing node；Fake effects；测试。

**实现步骤**

文档 verified 后发消息；保存 message artifact；重复执行读取 ledger。

**测试要求**

顺序错误、发送失败、重复节点、成功 external ID。

**验收标准**

文档未成功时不能发消息；成功 operation 不重复发送。

**验证命令**

cd backend && pytest tests/integration/agent/test_group_message_operation.py -q。

**前置依赖**

T1.13。

**后续任务**

T1.15。

**建议 Commit**

feat(T1.14): add fake group message operation

### T1.15 添加 Fake 归档 Handler 和完成路由

**目标**

在文档和群消息成功后按 Run ID upsert Fake 归档，并完成 run。

**业务价值**

完成最小三项发布产物的 happy path。

**实现范围**

archive handler、依赖顺序、verify_side_effects 最小汇总和 complete_run。

**明确不包含**

不实现 partial failure 补偿、unknown verifier 或真实飞书。

**涉及文件**

handlers/archive.py；archive publishing node；终态 route；Fake effects；测试。

**实现步骤**

校验前两项 verified；按 Run ID upsert；保存 artifact；全部 verified 后成功。

**测试要求**

顺序错误、归档失败、重复 upsert、三项成功。

**验收标准**

happy path 产生三个稳定 artifact；全部 verified 才 succeeded。

**验证命令**

cd backend && pytest tests/integration/agent/test_archive_operation.py tests/integration/agent/test_minimal_publish.py -q。

**前置依赖**

T1.14。

**后续任务**

T1.16。

**建议 Commit**

feat(T1.15): complete fake publish sequence

### T1.16 提供最小运行详情 API

**目标**

提供最小运行详情的脱敏查询接口。

**业务价值**

让 Graph/HITL 完成后立即可观察，不等待完整后台。

**实现范围**

run_id、状态、当前节点、审批、Tool 摘要、错误和关键 refs。

**明确不包含**

不做页面、完整时间线、聚合指标、复杂筛选或 BI。

**涉及文件**

admin/local-demo run query API；query projection；响应 schema；API 测试。

**实现步骤**

建立脱敏 projection；按 run_id 查询；限制大型字段和秘密。

**测试要求**

各状态 API、404、脱敏和 secret scan。

**验收标准**

API 返回七类最小信息；不解析任意 Checkpoint 或原始日志。

**验证命令**

cd backend && pytest tests/integration/admin/test_minimal_run_detail.py -q。

**前置依赖**

T1.15。

**后续任务**

T1.17。

**建议 Commit**

feat(T1.16): expose minimal run detail api

### T1.17 提供最小运行详情页面

**目标**

用简单 Next.js 页面展示最小运行详情并轮询活动 run。

**业务价值**

在完整仪表盘前即可观察当前闭环。

**实现范围**

run_id、状态、当前节点、审批、Tool 摘要、错误和 refs 的单页展示。

**明确不包含**

不做仪表盘聚合、复杂筛选、图编辑或 BI。

**涉及文件**

frontend 最小 run page；API client/schema；状态组件；UI 测试。

**实现步骤**

加载 run；活动态轮询；终态停止；展示空/错误状态。

**测试要求**

各状态 fixture、轮询停止、脱敏展示、type check。

**验收标准**

页面展示七类最小信息；不提供状态修改或秘密查看。

**验证命令**

cd frontend && npm run test -- run-detail && npm run typecheck。

**前置依赖**

T1.16。

**后续任务**

T1.18。

**建议 Commit**

feat(T1.17): add minimal run detail page

### T1.18 自动化 Local-demo Happy Path E2E

**目标**

自动执行手动创建、两次模拟 HITL、采集、报告和三项 Fake 发布。

**业务价值**

Milestone 1 形成可独立演示和持续回归的版本。

**实现范围**

一条 local-demo E2E、固定场景和页面/API 关键断言。

**明确不包含**

不连接真实平台，不覆盖异常诊断或部分失败恢复。

**涉及文件**

tests/e2e/test_local_demo_happy_path.py；E2E fixture/helper；必要的测试配置。

**实现步骤**

创建 run；批准 HITL 1；等待报告；批准 HITL 2；断言三个 artifact 和详情。

**测试要求**

可重复运行、无网络、无时间竞态、secret scan。

**验收标准**

单命令完成 happy path；Graph 未依赖 Scheduler；产物 ID 稳定。

**验证命令**

cd backend && pytest tests/e2e/test_local_demo_happy_path.py -q。

**前置依赖**

T1.17。

**后续任务**

Milestone 1 人工验收；T2.1。

**建议 Commit**

test(T1.18): cover local demo happy path

## 5. Milestone 2：可靠性强化与真实适配器

### T2.1 添加 Callback Inbox

**目标**

持久化 callback 事件并提供原子去重。

**业务价值**

重复事件或重复按钮不会产生第二次业务命令。

**实现范围**

callback_events、Inbox repository、事件 hash/状态；一个 migration。

**明确不包含**

不实现 Outbox、真实验签、Graph resume 或通用消息总线。

**涉及文件**

callback ORM/repository；一个 Alembic migration；Inbox service；并发测试。

**实现步骤**

定义外部 event key；事务插入；唯一冲突返回 duplicate；记录脱敏摘要。

**测试要求**

up/down/up、顺序/并发重复、同 key 不同 payload 冲突。

**验收标准**

同 provider/event_id 只有一条有效 Inbox 记录；一个主要 migration。

**验证命令**

cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/integration/inbox -q。

**前置依赖**

T1.18。

**后续任务**

T2.2、T2.5。

**建议 Commit**

feat(T2.1): add callback inbox deduplication

### T2.2 添加 Transactional Outbox

**目标**

在业务事务内可靠记录待派发命令，并支持失败重发。

**业务价值**

API ack、Graph resume 和 Worker 崩溃之间不丢命令。

**实现范围**

outbox_messages、dispatcher、dedupe/available_at；一个 migration。

**明确不包含**

不引入 Kafka，不实现具体飞书 callback。

**涉及文件**

outbox ORM/repository；一个 Alembic migration；dispatcher；Worker job；测试。

**实现步骤**

事务写 Outbox；claim/publish/ack；失败退避；重复消息由 dedupe_key 短路。

**测试要求**

up/down/up、提交前/后崩溃、重复 dispatch、失败重发。

**验收标准**

未 ack 消息可恢复；已发布消息不重复产生消费者效果。

**验证命令**

cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/integration/outbox -q。

**前置依赖**

T2.1。

**后续任务**

T2.5、T2.17。

**建议 Commit**

feat(T2.2): add transactional command outbox

### T2.3 实现飞书 Token 与身份能力

**目标**

实现 tenant token 刷新和用户/群身份查询。

**业务价值**

为真实卡片、callback 和消息适配器提供认证基础。

**实现范围**

token cache、并发刷新、身份 DTO 和错误映射。

**明确不包含**

不发送卡片、不读多维表格。

**涉及文件**

integrations/feishu/auth.py；client.py；identity.py；契约测试。

**实现步骤**

按 Spike 协议实现；秘密只在调用边界解密；映射权限/过期。

**测试要求**

并发刷新、失效、403/429、secret scan、sandbox smoke 分离。

**验收标准**

真实 adapter 通过身份契约；日志无 secret。

**验证命令**

cd backend && pytest tests/contract/feishu/test_auth_identity.py -q。

**前置依赖**

T0.2、T0.8、T2.2。

**后续任务**

T2.4～T2.6、T2.12～T2.15。

**建议 Commit**

feat(T2.3): add feishu auth and identity adapter

### T2.4 实现卡片发送、更新和协调消息幂等

**目标**

真实发送/更新审批和状态卡片，并保存投递 ID。

**业务价值**

用户能通过真实飞书看到流程状态，重复发送可控。

**实现范围**

feishu_message_deliveries 最小迁移；私聊卡片发送/更新；purpose/revision 幂等。

**明确不包含**

不处理 callback，不发送群摘要。

**涉及文件**

messaging/cards adapter；delivery ORM/repository；一个 migration；契约测试。

**实现步骤**

生成 idempotency key；保存 message_id；更新失败可重试。

**测试要求**

重复发送、更新、超时、unknown、真实 sandbox smoke 分离。

**验收标准**

同 purpose/revision/recipient 不重复创建卡片。

**验证命令**

cd backend && pytest tests/contract/feishu/test_cards.py tests/integration/persistence/test_message_delivery.py -q。

**前置依赖**

T2.3。

**后续任务**

T2.5、T2.16。

**建议 Commit**

feat(T2.4): deliver idempotent feishu cards

### T2.5 接入真实飞书 Callback 和 Resume

**目标**

验证、解密、快速响应真实事件/卡片并消费 approval。

**业务价值**

把 local-demo HITL 换成真实飞书入口。

**实现范围**

challenge、签名/时间窗、actor/action 标准化、inbox/outbox、resume。

**明确不包含**

不处理任意群聊指令，不实现首次配置向导。

**涉及文件**

api/feishu/events.py；cards.py；verification.py；ApprovalService adapter；集成测试。

**实现步骤**

原始 body 验证；登记 inbox；3 秒内 ack；Worker 异步 resume。

**测试要求**

脱敏 fixture、篡改、过期、重复、并发双击、P95。

**验收标准**

重复 callback 一次 decision/resume；非法 actor 无状态变化。

**验证命令**

cd backend && pytest tests/integration/feishu_callbacks -q。

**前置依赖**

T2.1、T2.2、T2.4。

**后续任务**

T2.16、T3.3。

**建议 Commit**

feat(T2.5): resume graph from secure feishu callbacks

### T2.6 实现多维表格 Schema 与只读适配器

**目标**

用真实飞书读取最小逻辑表并校验 schema。

**业务价值**

替换 Milestone 1 的 Fake 飞书数据源。

**实现范围**

schema、分页读取、人员/日期/枚举转换和错误映射。

**明确不包含**

不写归档、不实现完整配置 UI。

**涉及文件**

integrations/feishu/bitable.py；read Tool；mapping DTO；契约测试。

**实现步骤**

读取 schema hash；分页；限制记录量；落现有 batch。

**测试要求**

分页、空表、字段缺失、类型变化、真实 smoke 分离。

**验收标准**

真实/Fake adapter 共享契约；关键 schema 变化进入 blocked。

**验证命令**

cd backend && pytest tests/contract/feishu/test_bitable_read.py -q。

**前置依赖**

T2.3、T1.6。

**后续任务**

T2.14、T3.1。

**建议 Commit**

feat(T2.6): read feishu bitable through contract

### T2.7 实现 GitHub 凭证、仓库和 Issue/PR

**目标**

安全使用 PAT 读取仓库 metadata、Issue 和 PR。

**业务价值**

替换单仓 Fake GitHub 的核心研发数据。

**实现范围**

encrypted_credentials 迁移、PAT credential service、metadata/issues/PR 分页与时间过滤。

**明确不包含**

不实现 commits、reviews、milestones、contributors 或多仓并发。

**涉及文件**

credential ORM/repository 和一个 migration；integrations/github/client.py；credentials service；read Tool；write-only API；契约测试。

**实现步骤**

解密调用；能力探测；排除 Issue 中 PR；处理 403/404/429。

**测试要求**

迁移 up/down/up、分页、时间边界、权限、token 泄漏扫描、真实 smoke 分离。

**验收标准**

一个真实仓可采集；PAT 不进 API/日志/State。

**验证命令**

cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/contract/github/test_repository_issues_prs.py tests/unit/security/test_secret_boundaries.py -q。

**前置依赖**

T0.3、T0.8、T0.10。

**后续任务**

T2.8。

**建议 Commit**

feat(T2.7): collect github repository issues and prs

### T2.8 实现 GitHub Commit 与 Review

**目标**

采集 Commit 和 Review/审查状态并映射统一模型。

**业务价值**

支持代码活动和长期未审查 PR 指标。

**实现范围**

commit 时间过滤、review 聚合、分页和来源 ID。

**明确不包含**

不实现 milestone、contributor、Actions 或多仓并发。

**涉及文件**

GitHub commit/review adapter；DTO；normalizer 扩展；契约和指标测试。

**实现步骤**

实现 endpoint；聚合最新审查状态；保留 branch/author 摘要。

**测试要求**

分页、默认分支口径、空 review、重复 review、时间边界。

**验收标准**

Commit/Review 通过 Fake/真实共享契约；指标输入稳定。

**验证命令**

cd backend && pytest tests/contract/github/test_commits_reviews.py tests/unit/reports/normalization -q。

**前置依赖**

T2.7。

**后续任务**

T2.9。

**建议 Commit**

feat(T2.8): collect github commits and reviews

### T2.9 实现 GitHub Milestone 与 Contributor

**目标**

采集里程碑和贡献者数据。

**业务价值**

支持里程碑完成率和活跃贡献者指标。

**实现范围**

milestone/contributor endpoint、202/空仓行为和统一模型。

**明确不包含**

不实现 Actions、ETag 优化或多仓并发。

**涉及文件**

GitHub milestone/contributor adapter；DTO；normalizer 扩展；契约测试。

**实现步骤**

实现分页；处理 contributor 202；保留 open/closed 计数和外部 ID。

**测试要求**

空/归档仓、202 retry hint、milestone open/closed、分页。

**验收标准**

PRD 必需 GitHub 实体齐备；Actions 保持可选后置。

**验证命令**

cd backend && pytest tests/contract/github/test_milestones_contributors.py -q。

**前置依赖**

T2.8。

**后续任务**

T2.10、T3.5。

**建议 Commit**

feat(T2.9): collect github milestones and contributors

### T2.10 支持最多五仓有界并发

**目标**

按批准 scope 并发采集 1～5 个仓库，隔离单仓失败。

**业务价值**

满足单项目多仓 MVP。

**实现范围**

有界并发、每仓状态、采集上限和结果聚合。

**明确不包含**

不实现 ETag、增量游标优化或自动诊断。

**涉及文件**

data_collection service；GitHub collection node；policy/config；场景测试。

**实现步骤**

限制并发；每仓独立 batch；其他仓继续；汇总 partial/blocked。

**测试要求**

1/5 仓、单仓 403、timeout、顺序非确定但结果 hash 稳定。

**验收标准**

单仓失败不丢其他仓；最多 5 仓限制由代码和 API 校验。

**验证命令**

cd backend && pytest tests/integration/agent/test_multi_repository_collection.py -q。

**前置依赖**

T2.9。

**后续任务**

T3.1。

**建议 Commit**

feat(T2.10): collect five repositories with bounded concurrency

### T2.11 强化 Operation Claim 和 Succeeded 去重

**目标**

让多个 Worker 不会同时执行同一 operation，成功项永不重放。

**业务价值**

建立发布 exactly-once effect 的数据库防线。

**实现范围**

FOR UPDATE SKIP LOCKED/乐观版本、claim lease、attempt 记录、ledger 查询。

**明确不包含**

不实现 timeout unknown verifier。

**涉及文件**

operation repository；executor；状态机；并发集成测试。

**实现步骤**

原子 claim；校验 plan hash；成功短路；过期 claim 标记待核验。

**测试要求**

双 Worker、Checkpoint 落后、重复 resume、成功重放。

**验收标准**

同 operation 并发只一次外部调用；succeeded 永不再次调用。

**验证命令**

cd backend && pytest tests/integration/side_effects/test_operation_claim.py -q。

**前置依赖**

T1.15。

**后续任务**

T2.12～T2.15。

**建议 Commit**

feat(T2.11): claim and deduplicate publish operations

### T2.12 实现真实 Create Document Handler

**目标**

通过真实 Feishu Port 创建/分块写入文档并保存外部 ID。

**业务价值**

产出用户可访问的周报文档。

**实现范围**

documents adapter、create-document handler、document URL 和错误映射。

**明确不包含**

不发送群消息、不写归档、不实现 unknown verifier。

**涉及文件**

integrations/feishu/documents.py；handlers/document.py；契约测试。

**实现步骤**

复用 approved payload ref；创建后分块写入；保存 document_id/url。

**测试要求**

分块失败、权限、重复 ledger 短路、真实 sandbox smoke 分离。

**验收标准**

handler 不含审批逻辑；结果可供 verifier 查询。

**验证命令**

cd backend && pytest tests/contract/feishu/test_document.py tests/integration/side_effects/test_document_handler.py -q。

**前置依赖**

T2.3、T2.11。

**后续任务**

T2.13、T2.15。

**建议 Commit**

feat(T2.12): create approved feishu document

### T2.13 实现真实 Send Group Summary Handler

**目标**

在文档 confirmed 后向批准群发送摘要和链接。

**业务价值**

向项目群交付周报通知。

**实现范围**

group message adapter、handler、message_id 和依赖校验。

**明确不包含**

不写归档、不更换目标群、不实现 unknown verifier。

**涉及文件**

integrations/feishu/group_messages.py；handlers/group_message.py；契约测试。

**实现步骤**

校验 document artifact；使用冻结 target/payload；保存 message_id。

**测试要求**

群不可发、timeout、重复 ledger 短路、真实 smoke 分离。

**验收标准**

未 confirmed 文档不能发消息；目标来自批准计划。

**验证命令**

cd backend && pytest tests/contract/feishu/test_group_message.py tests/integration/side_effects/test_group_handler.py -q。

**前置依赖**

T2.12。

**后续任务**

T2.14、T2.15。

**建议 Commit**

feat(T2.13): send approved group summary

### T2.14 实现真实 Archive Record Handler

**目标**

按 Run ID 幂等 upsert 周报归档记录。

**业务价值**

在飞书多维表格留下可查询执行档案。

**实现范围**

archive adapter、handler、record ID 和内容 hash。

**明确不包含**

不实现其他表写入或外部结果总 verifier。

**涉及文件**

integrations/feishu/archive.py；handlers/archive.py；契约测试。

**实现步骤**

按 Run ID 查询；不存在新增、存在更新；保存 record_id。

**测试要求**

首次写入、重复 upsert、schema 缺失、真实 smoke 分离。

**验收标准**

同 Run ID 不产生重复归档；字段来自配置 mapping。

**验证命令**

cd backend && pytest tests/contract/feishu/test_archive.py tests/integration/side_effects/test_archive_handler.py -q。

**前置依赖**

T2.6、T2.13。

**后续任务**

T2.15。

**建议 Commit**

feat(T2.14): upsert approved report archive

### T2.15 实现 Timeout Unknown Verifier

**目标**

对三类副作用的 timeout/running 结果查询实际状态。

**业务价值**

避免盲目重建文档或重复发消息。

**实现范围**

SideEffectVerifier；confirmed/not_found/inconclusive；operation verification 状态。

**明确不包含**

不实现 Graph 补偿路由。

**涉及文件**

integrations/feishu/verification.py；side_effects/verifier.py；operation repository；测试。

**实现步骤**

按 external ID/Run ID/平台能力查询；保存证据；inconclusive 保持 unknown。

**测试要求**

timeout 后 found/not_found/inconclusive；重复核验；无 query 能力。

**验收标准**

unknown 不自动 POST；核验结果持久化且可审计。

**验证命令**

cd backend && pytest tests/integration/side_effects/test_verifier.py -q。

**前置依赖**

T2.12、T2.13、T2.14。

**后续任务**

T2.16。

**建议 Commit**

feat(T2.15): verify unknown external effects

### T2.16 实现部分失败 Graph 路由

**目标**

文档、消息、归档部分失败时只向前恢复未完成项。

**业务价值**

不伪造跨平台回滚，也不重复已成功产物。

**实现范围**

verify_side_effects、compensate_partial_failure、partial_failed 状态和卡片摘要。

**明确不包含**

不实现通用 Saga 或删除已发布内容。

**涉及文件**

publishing nodes/routes；compensation service；部分失败卡片 projection；场景测试。

**实现步骤**

汇总 ledger；retryable 续跑；unknown 先核验；永久失败形成真实终态。

**测试要求**

文档成功消息失败；文档消息成功归档失败；inconclusive；重复恢复。

**验收标准**

只重试原批准计划的失败项；已成功 artifact 保留。

**验证命令**

cd backend && pytest tests/scenarios/test_partial_publish_failures.py -q。

**前置依赖**

T2.4、T2.5、T2.15。

**后续任务**

T2.17。

**建议 Commit**

feat(T2.16): recover partial publish failures

### T2.17 实现 Worker 崩溃与服务重启恢复

**目标**

从 Checkpoint、outbox 和 operation ledger 恢复等待态与执行态。

**业务价值**

满足服务重启后不丢任务、不重复副作用。

**实现范围**

recovery scanner、run lease 最小实现、stale running/unknown 分类。

**明确不包含**

不实现完整 Redis lease 续租体系和备份恢复演练。

**涉及文件**

application/services/recovery.py；workers/runner.py；lease/recovery repository；故障注入测试。

**实现步骤**

扫描 waiting/active；waiting 不占 Worker；running effect 先 verifier；重新派发 outbox。

**测试要求**

每个副作用四个崩溃点、Redis flush、Worker restart、Checkpoint 滞后。

**验收标准**

已成功节点/operation 不重复；等待审批仍可 resume。

**验证命令**

cd backend && pytest tests/integration/recovery tests/scenarios/test_restart_recovery.py -q。

**前置依赖**

T2.2、T2.16。

**后续任务**

T2.18。

**建议 Commit**

feat(T2.17): recover workflows after worker crashes

### T2.18 实现运行取消

**目标**

按阶段持久化取消请求并阻止未开始工作。

**业务价值**

用户可在发布前停止 run，发布中也不会伪造回滚。

**实现范围**

durable cancel flag、节点边界检查、admin/Feishu cancel action。

**明确不包含**

不实现 Safe Retry，不删除已完成 artifact。

**涉及文件**

run control service；cancel endpoint/action；graph routes；测试。

**实现步骤**

定义允许状态；等待态 resume cancel；publishing 中取消 pending operation。

**测试要求**

等待/采集/生成/发布各阶段、重复取消、已完成 operation。

**验收标准**

已完成操作保留真实记录；取消不启动新工作。

**验证命令**

cd backend && pytest tests/integration/runs/test_cancel.py -q。

**前置依赖**

T2.17。

**后续任务**

T2.19。

**建议 Commit**

feat(T2.18): cancel runs without false rollback

### T2.19 实现 Safe Retry

**目标**

只恢复允许的失败节点或原批准计划中的 failed/unknown operation。

**业务价值**

管理员可安全恢复失败，而不绕过审批或重复发布。

**实现范围**

safe-retry service/API、状态/plan/approval/ledger 校验。

**明确不包含**

不重开 succeeded/cancelled run，不创建新发布计划。

**涉及文件**

recovery service 扩展；admin endpoint；authorization policy；测试。

**实现步骤**

校验失败分类；重算 hash；核验 unknown；派发唯一恢复命令。

**测试要求**

partial_failed、永久失败、terminal 拒绝、重复请求、hash 变化。

**验收标准**

Safe Retry 不重复 artifact；不允许扩大原计划。

**验证命令**

cd backend && pytest tests/integration/runs/test_safe_retry.py -q。

**前置依赖**

T2.18。

**后续任务**

Milestone 2 人工验收；T3.1。

**建议 Commit**

feat(T2.19): retry failed runs safely

## 6. Milestone 3：Agent Loop 与质量强化

### T3.1 添加诊断记录和问题分类

**目标**

建立固定 problem taxonomy、严重度、可恢复性和 action allowlist。

**业务价值**

让异常处理可观察、可测试，而不是自由 LLM 决策。

**实现范围**

diagnosis_records 迁移、ProblemPolicyRegistry、Observe 记录。

**明确不包含**

不执行自动 repair，不做人工作业。

**涉及文件**

诊断 ORM/repository；一个 migration；agent policies；observe node；测试。

**实现步骤**

映射 timeout/rate-limit/permission/schema/missing/conflict/LLM/grounding 类别。

**测试要求**

分类表驱动、未知错误 fallback、迁移 up/down/up。

**验收标准**

每个问题有稳定 key 和允许动作；LLM 不能创建类别。

**验证命令**

cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/unit/agent/policies/test_problem_registry.py -q。

**前置依赖**

T2.19。

**后续任务**

T3.2。

**建议 Commit**

feat(T3.1): classify diagnosable workflow problems

### T3.2 实现 Observe-Diagnose-Plan-Act-Verify

**目标**

对可自动恢复问题执行白名单诊断循环。

**业务价值**

Agent 能自动处理瞬态故障和允许降级的数据问题。

**实现范围**

五个节点、指数退避、单问题计数、Continue/Escalate 路由。

**明确不包含**

不实现人工补充卡片和 LLM schema 修复。

**涉及文件**

agent/nodes/diagnosis.py；policies/retry.py；data_quality.py；graph routes；场景测试。

**实现步骤**

记录 observation；规则诊断；选择 action；重试/降级；重新校验。

**测试要求**

限流后成功、单仓失败、非关键降级、达到上限。

**验收标准**

正常路径仍直达 metrics；只有异常进入循环；最多 3 次。

**验证命令**

cd backend && pytest tests/scenarios/test_diagnosis_loop.py -q。

**前置依赖**

T3.1。

**后续任务**

T3.3。

**建议 Commit**

feat(T3.2): add bounded diagnosis loop

### T3.3 实现人工补充 Interrupt

**目标**

自动修复失败后请求精确输入，并从已有 Checkpoint 恢复。

**业务价值**

关键数据不足时不伪造也不从头重跑。

**实现范围**

human_input approval、补充 schema、飞书/Fake 卡片、验证后回 validation。

**明确不包含**

不允许任意 Tool 指令或直接编辑 State。

**涉及文件**

human input nodes；ApprovalService 扩展；卡片模板；Graph 场景测试。

**实现步骤**

输出缺失/尝试/原因/所需/恢复点；校验 supplement ref；resume。

**测试要求**

非法/合法、重复、旧卡片、重启等待态、成功节点不重跑。

**验收标准**

补充后从指定节点继续；关键缺失前不会发布。

**验证命令**

cd backend && pytest tests/scenarios/test_human_input_resume.py -q。

**前置依赖**

T2.4、T3.2。

**后续任务**

T3.4。

**建议 Commit**

feat(T3.3): resume from validated human input

### T3.4 实现报告重新生成和缓存复用

**目标**

HITL 2 的补充/重新生成只重跑受影响报告节点。

**业务价值**

避免重复采集和指标计算，同时保证新内容重新审批。

**实现范围**

report/plan revision、input hash 复用、scope 变化回 HITL 1。

**明确不包含**

不刷新真实数据快照，除非范围变化。

**涉及文件**

report generation service；publish approval routes；cache policy；测试。

**实现步骤**

使旧 plan/approval invalid；复用 snapshot/metrics/evidence；生成新版本/hash。

**测试要求**

supplement、regenerate、scope change、旧批准失效。

**验收标准**

新报告必有新 plan approval；不无条件重拉数据。

**验证命令**

cd backend && pytest tests/scenarios/test_report_regeneration.py -q。

**前置依赖**

T3.3。

**后续任务**

T3.5。

**建议 Commit**

feat(T3.4): regenerate reports from cached evidence

### T3.5 强化 Grounding 和完整指标

**目标**

补齐 PRD 指标并增强 claim/evidence 一致性。

**业务价值**

最终报告达到完整可追溯验收口径。

**实现范围**

全部 11 项指标、人员活动分项、claim 类型/置信度/周期、可修复 grounding 路由。

**明确不包含**

不生成人员绩效综合分。

**涉及文件**

reports/metrics/；reports/evidence/；reports/verification/；固定数据集；测试。

**实现步骤**

补指标口径；建立 evidence candidates；修复或降级非关键 claim；关键无证据阻止。

**测试要求**

golden、冲突、partial 数据、无证据关键 claim。

**验收标准**

PRD 指标全覆盖；关键 claim 全部可追溯或被阻止。

**验证命令**

cd backend && pytest tests/unit/reports tests/scenarios/test_grounding_quality.py -q。

**前置依赖**

T2.9、T3.4。

**后续任务**

T3.6。

**建议 Commit**

feat(T3.5): complete metrics and grounding rules

### T3.6 加固 Prompt Injection 和 LLM Schema 恢复

**目标**

把外部文本视为数据，并对结构失败做有限修复。

**业务价值**

防止外部内容改变工具、目标或审批边界。

**实现范围**

输入边界/清洗/长度/URL allowlist；schema repair 最多有限次数；安全失败。

**明确不包含**

不实现通用内容安全平台或 LLM Streaming。

**涉及文件**

security/prompt_guard.py；generation schemas；LLM retry policy；攻击 fixture；测试。

**实现步骤**

标记来源；限制 evidence IDs；拒绝控制字段；修复 JSON；记录尝试。

**测试要求**

PRD 注入场景、超长文本、恶意 URL、非法 schema、达上限。

**验收标准**

外部文本不能新增 Tool/operation/target；无效结构不发布。

**验证命令**

cd backend && pytest tests/security/test_prompt_injection.py tests/scenarios/test_llm_schema_recovery.py -q。

**前置依赖**

T3.5。

**后续任务**

T3.7。

**建议 Commit**

feat(T3.6): harden prompts and structured output recovery

### T3.7 完成 Node、Tool、LLM 和审计记录

**目标**

持久化完整节点、Tool、LLM execution 和审计事件，扩展早期最小 Tool 记录。

**业务价值**

为完整运行后台和安全审计提供稳定事实，而不是解析日志或任意 Checkpoint。

**实现范围**

node_executions、llm_executions、audit_logs；tool_executions 增强字段；一个 migration 和 recorder。

**明确不包含**

不实现完整查询 API、前端仪表盘或外部日志平台。

**涉及文件**

观测 ORM/repository；一个 Alembic migration；execution/audit recorder；集成测试。

**实现步骤**

记录 node start/end；Tool 脱敏摘要；LLM model/token/latency；审批/配置/副作用 audit。

**测试要求**

迁移 up/down/up、run_id 关联、recorder 失败隔离、secret/stack 扫描。

**验收标准**

一次场景的 node/tool/LLM/audit 可按 run_id 串联；一个主要 migration。

**验证命令**

cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/integration/observability -q。

**前置依赖**

T3.6。

**后续任务**

Milestone 3 人工验收；T4.1、T4.12。

**建议 Commit**

feat(T3.7): persist workflow execution and audit records

## 7. Milestone 4：产品化与部署

### T4.1 完成配置数据模型和后端 CRUD

**目标**

补齐字段映射、Prompt 版本、资源和 schedule 配置的后端能力。

**业务价值**

让产品不依赖 seed/local-demo 配置。

**实现范围**

DB-6 配置部分 migration、revision CRUD；仍是单项目。

**明确不包含**

不实现 UI、连通性测试或 Scheduler 执行。

**涉及文件**

配置 ORM/repository；一个 migration；admin API；测试。

**实现步骤**

补最终 schema；实现乐观并发；运行继续使用 config snapshot。

**测试要求**

up/down/up、revision 冲突、最多 5 仓、已创建 run 不受变化影响。

**验收标准**

基础 CRUD 完整；没有硬编码中文字段/仓库/群 ID。

**验证命令**

cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/integration/admin/test_config_crud.py -q。

**前置依赖**

T3.7。

**后续任务**

T4.2～T4.5。

**建议 Commit**

feat(T4.1): complete project configuration api

### T4.2 实现 GitHub 连通性测试

**目标**

按仓库返回细粒度 GitHub capability。

**业务价值**

管理员能在运行前发现 PAT/权限问题。

**实现范围**

async_jobs 迁移、独立 endpoint/job、metadata 与必需 endpoint 探测。

**明确不包含**

不探测 Actions，不修改凭证。

**涉及文件**

async job ORM/repository 和一个 migration；admin/connectivity.py；GitHub capability service；job projection；测试。

**实现步骤**

调用已实现 adapter；返回 ok/degraded/failed；脱敏错误。

**测试要求**

迁移 up/down/up、有效/过期/权限不足/仓库不存在、异步 job 状态。

**验收标准**

不是单一布尔值；不回显 PAT。

**验证命令**

cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest tests/integration/admin/test_github_connectivity.py -q。

**前置依赖**

T4.1、T2.7。

**后续任务**

T4.5。

**建议 Commit**

feat(T4.2): expose github capability checks

### T4.3 实现飞书连通性测试

**目标**

验证表 schema、群发送和文档目标能力。

**业务价值**

配置阶段提前发现资源或权限错误。

**实现范围**

独立 endpoint/job；默认只做无业务副作用探测，必要测试写入明确标记并清理。

**明确不包含**

不修改运行或发布目标。

**涉及文件**

Feishu capability service；admin endpoint；测试。

**实现步骤**

检查 token/identity、表/群/文档 target；返回 schema hash 和 capability。

**测试要求**

字段缺失、群不可发、文档不可建、sandbox smoke 分离。

**验收标准**

结果可定位到具体资源/能力；不产生未审计正式内容。

**验证命令**

cd backend && pytest tests/integration/admin/test_feishu_connectivity.py -q。

**前置依赖**

T4.1、T2.6、T2.12、T2.13。

**后续任务**

T4.5。

**建议 Commit**

feat(T4.3): expose feishu capability checks

### T4.4 实现 LLM 连通性和模型配置测试

**目标**

验证 base URL、模型、结构化输出和 usage 能力。

**业务价值**

管理员能在运行前发现模型不兼容。

**实现范围**

非敏感配置、write-only API key、独立 connectivity endpoint。

**明确不包含**

不实现 Streaming。

**涉及文件**

LLM config service；admin model endpoint；credential update；测试。

**实现步骤**

保存加密 key；发最小 schema 请求；返回 capability 和耗时。

**测试要求**

无效 key、模型不存在、schema fallback、secret scan。

**验收标准**

API 不返回 key；业务代码仍厂商无关。

**验证命令**

cd backend && pytest tests/integration/admin/test_llm_connectivity.py -q。

**前置依赖**

T0.8、T4.1。

**后续任务**

T4.5。

**建议 Commit**

feat(T4.4): manage and test llm configuration

### T4.5 实现仓库配置页面

**目标**

实现仓库列表、新增、启停、类型/权重和 GitHub capability 展示。

**业务价值**

管理员可独立管理最多五个仓库。

**实现范围**

仓库页面、API client/schema 和 revision 冲突处理。

**明确不包含**

不实现飞书资源、凭证、配置最终确认或复杂 RBAC。

**涉及文件**

frontend repository-config feature；API client/schema；UI 测试。

**实现步骤**

实现列表/表单；显示 capability；校验 1～5 仓；处理并发 revision。

**测试要求**

表单、最多五仓、revision 冲突、空/错误状态、可访问性基础。

**验收标准**

仓库配置可用且不影响已创建 run snapshot。

**验证命令**

cd frontend && npm run test -- repository-config && npm run typecheck。

**前置依赖**

T4.1、T4.2。

**后续任务**

T4.6。

**建议 Commit**

feat(T4.5): add repository configuration page

### T4.6 实现飞书资源和字段映射页面

**目标**

配置多维表格、字段 mapping、发布群和文档目标。

**业务价值**

管理员无需硬编码飞书资源或中文字段。

**实现范围**

资源列表/表单、schema 预览、logical mapping 和 Feishu capability 展示。

**明确不包含**

不实现凭证页面或最终配置确认。

**涉及文件**

frontend feishu-resource feature；mapping components；API client/schema；UI 测试。

**实现步骤**

加载 schema hash；映射 logical field；显示 required level；处理旧 schema 冲突。

**测试要求**

字段类型、旧 schema、缺少 critical field、群/文档 capability、可访问性。

**验收标准**

页面不写死中文字段；旧 schema 不能覆盖新 mapping。

**验证命令**

cd frontend && npm run test -- feishu-resource-mapping && npm run typecheck。

**前置依赖**

T4.3、T4.5。

**后续任务**

T4.7。

**建议 Commit**

feat(T4.6): add feishu resource mapping page

### T4.7 实现凭证页面

**目标**

提供 GitHub PAT、飞书和 LLM 凭证的 write-only 更新与状态展示。

**业务价值**

管理员能安全轮换凭证而不会在前端回显秘密。

**实现范围**

凭证 metadata、更新表单、验证状态和 secret 清空策略。

**明确不包含**

不实现配置确认审计或管理员登录。

**涉及文件**

frontend credential feature；write-only API client；安全组件测试。

**实现步骤**

只显示 fingerprint suffix/status；提交后清空输入；显示三类 connectivity。

**测试要求**

DOM/API mock 无 secret 回显、错误后清理、状态展示、可访问性。

**验收标准**

前端缓存、日志和响应对象均不包含原秘密。

**验证命令**

cd frontend && npm run test -- credentials && npm run typecheck。

**前置依赖**

T4.2、T4.3、T4.4、T4.6。

**后续任务**

T4.8。

**建议 Commit**

feat(T4.7): add write-only credential page

### T4.8 实现配置确认和审计

**目标**

对配置变更显示 diff/hash，经管理员确认后按 revision 应用并审计。

**业务价值**

满足配置写操作的明确确认和可追溯要求。

**实现范围**

配置变更摘要、确认 API/UI、before/after 脱敏审计。

**明确不包含**

不复用周报 HITL 2，不实现多人审批。

**涉及文件**

configuration change service；audit repository；confirm endpoint；frontend confirm modal；测试。

**实现步骤**

生成白名单 diff/hash；确认时重算 revision；事务应用并写 audit。

**测试要求**

hash/revision 变化、取消、重复确认、secret 脱敏、审计前后摘要。

**验收标准**

所有后台配置修改均有明确确认和审计；不影响既有 run snapshot。

**验证命令**

cd backend && pytest tests/integration/admin/test_config_audit.py -q；cd frontend && npm run test -- config-confirmation。

**前置依赖**

T4.7。

**后续任务**

T4.9、T4.11、T4.14。

**建议 Commit**

feat(T4.8): confirm and audit configuration changes

### T4.9 实现基础管理员登录

**目标**

以单管理员保护后台。

**业务价值**

防止未授权用户查看运行和修改配置。

**实现范围**

密码哈希、短期 session/access token、login/logout/me、受保护 layout。

**明确不包含**

不实现 refresh token 旋转、完整登录审计或复杂 RBAC。

**涉及文件**

admin auth model/migration；auth service/API；frontend login；测试。

**实现步骤**

生产强密码初始化；安全 Cookie；路由 guard。

**测试要求**

正确/错误登录、过期、未认证、无默认弱密码。

**验收标准**

后台默认受保护；单管理员满足 MVP。

**验证命令**

cd backend && pytest tests/integration/admin/test_auth_basic.py -q；cd frontend && npm run test -- auth。

**前置依赖**

T4.8。

**后续任务**

T4.10。

**建议 Commit**

feat(T4.9): protect admin with single-user login

### T4.10 强化 Session 旋转和登录审计

**目标**

补充 refresh session 撤销/旋转、失败锁定和安全审计。

**业务价值**

达到生产后台登录安全要求。

**实现范围**

admin_sessions、refresh、lockout、login audit。

**明确不包含**

不实现 SSO、多人角色或租户 RBAC。

**涉及文件**

auth model migration；JWT/session service；auth endpoints；测试。

**实现步骤**

旋转 refresh；撤销；失败计数；记录安全事件。

**测试要求**

重放旧 refresh、并发刷新、锁定、撤销、CSRF/Origin。

**验收标准**

撤销 session 不可刷新；审计无密码/token。

**验证命令**

cd backend && pytest tests/security/test_admin_sessions.py -q。

**前置依赖**

T4.9。

**后续任务**

T4.11。

**建议 Commit**

feat(T4.10): harden admin sessions and audits

### T4.11 实现每周 Scheduler

**目标**

让 Scheduler 复用 RunCreationService 创建唯一周期运行。

**业务价值**

在纵向闭环稳定后加入自动周报触发。

**实现范围**

schedule_configs、周期计算、misfire、唯一触发。

**明确不包含**

不修改 Graph，不引入独立消息平台。

**涉及文件**

scheduling/scheduler.py；periods.py；schedule migration/repository；测试。

**实现步骤**

按项目时区计算半开周期；调用同一服务；DB unique 兜底。

**测试要求**

时区/DST/年边界、双 scheduler、misfire、Redis 丢失。

**验收标准**

Graph 对触发来源无感；同周期最多一个活动 run。

**验证命令**

cd backend && pytest tests/unit/scheduling tests/integration/scheduling -q。

**前置依赖**

T4.8、T4.10、T0.13。

**后续任务**

T4.12。

**建议 Commit**

feat(T4.11): schedule unique weekly runs

### T4.12 完整运行查询 API

**目标**

在最小详情之上补齐筛选、时间线、诊断、审批、证据、计划、operation 和聚合查询。

**业务价值**

为完整后台提供稳定、脱敏且高性能的数据接口。

**实现范围**

后端 projections、cursor/filter、仪表盘聚合和必要索引；P95 基准。

**明确不包含**

不实现前端页面、复杂 BI 或任意日志下载。

**涉及文件**

admin run query API；query services；数据库索引 migration（如需要）；性能测试。

**实现步骤**

实现 cursor/filter；分端点返回 node/tool/approval/evidence/plan/effect；聚合 dashboard。

**测试要求**

各状态 fixture、脱敏、cursor 稳定性、索引查询、P95 < 800ms。

**验收标准**

PRD 后台查询字段全覆盖；API 不提供任意 State/日志下载。

**验证命令**

cd backend && pytest tests/integration/admin/test_run_queries.py tests/performance/test_admin_queries.py -q。

**前置依赖**

T4.11、T3.6。

**后续任务**

T4.13。

**建议 Commit**

feat(T4.12): complete run observability queries

### T4.13 完整运行详情和仪表盘 UI

**目标**

实现运行筛选、流程时间线、各类详情面板和聚合仪表盘。

**业务价值**

形成 PRD 定义的 Agent 可观测平台。

**实现范围**

dashboard、run list/detail、node/tool/approval/diagnosis/evidence/effect panels 和轮询。

**明确不包含**

不建设复杂 BI，不提供绕过 Graph 的状态修改。

**涉及文件**

frontend dashboard/runs features；API client/schema；图形/时间线组件；UI 测试。

**实现步骤**

实现筛选和 cursor；补详情 panels；活动 run 轮询，终态停止。

**测试要求**

各状态 fixture、空/错误状态、脱敏展示、可访问性和 type check。

**验收标准**

PRD 后台字段可查看；无秘密、堆栈或原始 Checkpoint 下载。

**验证命令**

cd frontend && npm run test -- dashboard runs && npm run typecheck。

**前置依赖**

T4.12。

**后续任务**

T4.14。

**建议 Commit**

feat(T4.13): complete observability dashboard ui

### T4.14 实现飞书首次配置向导

**目标**

复用配置服务，通过飞书对话/卡片完成首次配置。

**业务价值**

满足产品化配置体验，但不阻塞核心 Agent E2E。

**实现范围**

有限状态向导、逐步校验、最终确认、重启恢复。

**明确不包含**

不复制配置逻辑，不实现多人管理员。

**涉及文件**

onboarding model/migration；service；卡片模板；callback routing；场景测试。

**实现步骤**

收集 PRD 字段；即时调用 connectivity；PAT 立即加密；确认后激活。

**测试要求**

正常、回退、过期、重复、非管理员、服务重启。

**验收标准**

未最终确认不激活配置；local-demo/手动配置仍可独立运行。

**验证命令**

cd backend && pytest tests/scenarios/test_feishu_onboarding.py -q。

**前置依赖**

T4.8、T4.10、T2.5。

**后续任务**

T4.15。

**建议 Commit**

feat(T4.14): add recoverable feishu onboarding

### T4.15 完成生产 Docker 与 Nginx 配置

**目标**

提供生产 Compose/Nginx、非 root 镜像和健康检查。

**业务价值**

让项目可在全新环境安全、可重复启动。

**实现范围**

多阶段镜像、healthcheck、Nginx HTTPS/路由限制、环境变量示例。

**明确不包含**

不扩展 CI、不做备份恢复、SBOM、Kubernetes 或高级压测。

**涉及文件**

docker-compose.yml；deploy/docker/；deploy/nginx/；.env.example；README.md。

**实现步骤**

构建非 root 镜像；配置 healthcheck；只暴露允许路由；生产拒绝 local-demo。

**测试要求**

clean compose up、health/ready、容器重启、路由/默认凭证检查。

**验收标准**

一键启动通过 ready；无默认弱密码/镜像 secret；internal/local-demo 不暴露。

**验证命令**

docker compose config && docker compose up --build。

**前置依赖**

T4.14。

**后续任务**

T4.16。

**建议 Commit**

chore(T4.15): add production container deployment

### T4.16 扩展 CI 到集成、契约和 E2E

**目标**

在基础 CI 上加入 PostgreSQL、Redis、迁移、Adapter contract、Graph resume 和 local-demo E2E。

**业务价值**

发布候选能自动验证核心可靠性，而不是依赖手工回归。

**实现范围**

CI service containers、测试分层、镜像构建、dependency/secret scan。

**明确不包含**

不运行需要真实凭证的平台 E2E，不生成 SBOM。

**涉及文件**

.github/workflows/ci.yml；测试配置；Compose CI override；README.md。

**实现步骤**

增加并行 jobs；Fake/真实测试标签隔离；缓存；失败产物脱敏。

**测试要求**

clean CI 等价命令、migration up/down/up、local-demo E2E、镜像扫描。

**验收标准**

无真实凭证即可完成完整 Fake CI；真实 smoke 只能显式 opt-in。

**验证命令**

执行项目 full-ci-local 命令和 docker compose config。

**前置依赖**

T4.15。

**后续任务**

T4.17。

**建议 Commit**

ci(T4.16): run integration contract and demo tests

### T4.17 补充备份恢复演练和 SBOM

**目标**

验证 PostgreSQL 恢复、等待 run 恢复和 unknown operation 核验，并生成 SBOM。

**业务价值**

给出可操作的灾难恢复和供应链证据。

**实现范围**

备份/恢复脚本或命令、现有 README/02/06 运维章节、SBOM CI job。

**明确不包含**

不引入专用备份平台、Kubernetes 或高级压测。

**涉及文件**

scripts/operations/；.github/workflows/；README.md；docs/02-architecture-design.md；docs/06-implementation-plan.md。

**实现步骤**

备份测试库；恢复新环境；resume waiting run；核验 unknown；生成镜像 SBOM。

**测试要求**

实际演练并记录脱敏结果；确保文档命令可复现。

**验收标准**

恢复后不重复副作用；SBOM 可由 CI 生成；不新建额外设计文档。

**验证命令**

执行项目 recovery-drill 和 sbom 命令。

**前置依赖**

T4.16。

**后续任务**

T4.18。

**建议 Commit**

chore(T4.17): verify recovery and generate sbom

### T4.18 强化 Redis Lease 与 Worker Heartbeat

**目标**

补齐长任务 lease 续租、heartbeat、过期接管和运行控制指标。

**业务价值**

减少慢外部调用或 Worker 抖动造成的错误并发接管。

**实现范围**

run/operation lease renewal、heartbeat、fencing token 和监控指标。

**明确不包含**

不把 Redis 变成业务事实源，不引入专用队列平台。

**涉及文件**

scheduling/locks.py；workers/heartbeat.py；operation/run claim service；Redis 集成测试。

**实现步骤**

加入 fencing/version；周期续租；数据库状态兜底；过期后先核验再接管。

**测试要求**

Redis 重启、heartbeat 丢失、双 Worker、长调用、旧 fencing token。

**验收标准**

旧 Worker 无法覆盖新接管结果；Redis 丢失不破坏数据库事实。

**验证命令**

cd backend && pytest tests/integration/recovery/test_lease_heartbeat.py -q。

**前置依赖**

T4.17、T2.17。

**后续任务**

T4.19。

**建议 Commit**

feat(T4.18): harden worker leases and heartbeats

### T4.19 实现数据生命周期清理

**目标**

按 03-database-design.md 的保留期安全清理大 payload 和过期运行数据。

**业务价值**

控制 PostgreSQL 容量，同时保留审批、报告、证据和审计事实。

**实现范围**

分批 cleanup job、终态/unknown/waiting 排除、payload 先清理策略和审计。

**明确不包含**

不物理删除活动 run、未解决 unknown、凭证审计或外部飞书产物。

**涉及文件**

persistence/cleanup service；cleanup job；配置；集成测试。

**实现步骤**

实现 dry-run；按表批处理；保护引用；记录清理数量和失败。

**测试要求**

等待态、unknown、终态、边界日期、重复清理、事务失败。

**验收标准**

活动和未解决数据不会删除；清理可重入且有审计。

**验证命令**

cd backend && pytest tests/integration/persistence/test_data_lifecycle.py -q。

**前置依赖**

T4.18。

**后续任务**

T4.20。

**建议 Commit**

feat(T4.19): enforce safe data retention

### T4.20 真实平台 E2E 和最终验收

**目标**

在隔离飞书/GitHub 环境验证完整真实闭环和恢复场景。

**业务价值**

形成 MVP 可用性的最终证据。

**实现范围**

真实两阶段 HITL、双源、多仓、报告、三项发布、后台、重复点击、重启恢复。

**明确不包含**

不扩展多租户、多人审批、GitHub App/OAuth 或 Actions。

**涉及文件**

现有 tests/e2e/；现有 02～06 文档的验证状态/结果章节；README.md。

**实现步骤**

运行真实 smoke/E2E；更新未验证能力状态；记录 run_id 和脱敏证据；逐项对照 PRD 验收。

**测试要求**

PRD 14 场景、性能、安全、重复 callback、故障注入和 Compose。

**验收标准**

所有核心验收通过或有明确、经批准的限制；没有未验证的上线阻断能力。

**验证命令**

执行项目 full-ci、local-demo E2E 和显式 opt-in 的 real-platform E2E 命令。

**前置依赖**

T4.19；真实 sandbox 和凭证。

**后续任务**

MVP 人工终验；不得自动扩展范围。

**建议 Commit**

test(T4.20): verify production mvp end to end

## 8. 原任务到新任务的映射

| 原任务 | 原问题 | 新任务 |
|---|---|---|
| T00 | 先冻结后验证且要新建 07/08 文档 | T0.1～T0.4，结果直接写回 02～06 |
| T01 | 骨架与工具链可保留 | T0.5 |
| T02 | 安全、日志、健康混合过多 | T0.7、T0.8 |
| T03 | 一次创建全部数据库表 | T0.9、T1.1、T1.4、T1.8、T1.11、T2.1、T3.1、T4.1 等按调用方迁移 |
| T04 | 完整认证阻塞核心 | T4.9、T4.10，后置 |
| T05 | Port/Tool/Fake 引入不足 | T0.10～T0.13 |
| T06 | Callback 过早成为主链前置 | T2.1、T2.2、T2.4、T2.5；M1 用模拟 HITL |
| T07 | 飞书全能力单一 Epic | T2.3～T2.6、T2.12～T2.15 |
| T08 | GitHub PAT 和所有 endpoint 过大 | T2.7～T2.10 |
| T09 | LLM Provider 可提前 | Spike T0.4、Fake T0.12、结构生成 T1.9、真实配置 T4.4 |
| T10 | CRUD/UI/连通性单一 Epic | T4.1～T4.8 |
| T11 | 首次配置向导阻塞 E2E | T4.14，后置 |
| T12 | Scheduler 阻塞 Graph | 手动 RunCreationService T0.13；Scheduler T4.11 |
| T13 | 确定性报告基础过大 | T1.6～T1.10、T3.5 |
| T14 | 完整观测过早 | 最小详情 T1.16、T1.17；完整观测 T4.12、T4.13 |
| T15 | Graph 被 Scheduler/观测阻塞 | T1.1～T1.3，直接接手动 run |
| T16 | 双源/多仓一次完成 | 单表单仓 T1.4～T1.6；多仓 T2.10 |
| T17 | 完整诊断阻塞报告 | 后置 T3.1～T3.3 |
| T18 | 报告等待诊断 | happy path T1.7～T1.10；强化 T3.4～T3.6 |
| T19 | 计划/HITL 2 可保留但需变小 | T1.11、T1.12 |
| T20 | 副作用执行 Epic | T1.11～T1.15、T2.11～T2.16 |
| T21 | 恢复、取消、清理混合 | T2.17～T2.19；备份/恢复在 T4.17；生命周期清理在 T4.19 |
| T22 | 完整后台过晚且最小详情缺失 | 最小 T1.16、T1.17；完整 T4.12、T4.13 |
| T23 | Fake 数据集/E2E 引入太晚 | Fake T0.11/T0.12；local-demo E2E T1.18；真实 E2E T4.20 |
| T24 | CI 太晚 | 基础 CI T0.6；扩展 CI T4.16；部署 T4.15 |

## 9. 被后置但保留的能力

以下能力不阻塞 Milestone 1：

- 飞书首次配置向导；
- 完整 refresh token 旋转和登录安全审计；
- 周期 Scheduler；
- 完整项目配置 UI 和三类连通性页面；
- 完整运行仪表盘和聚合指标；
- Redis lease 续租强化；
- GitHub ETag 优化；
- GitHub Actions 等可选 endpoint；
- LLM Streaming（周报后台任务不需要）；
- SBOM 和完整备份恢复演练；
- 高级压测。

以下仍明确不属于 MVP：多人审批、多租户、GitHub App/OAuth、复杂 BI、通用 RAG、任意 URL 和自动修改 GitHub/代码。

## 10. CI 和测试增长路径

| 起点 | CI/测试能力 |
|---|---|
| T0.6 | 后端 lint/format/type/unit，前端 lint/type/build，Compose config，secret scan |
| 首个 migration | 增加 Alembic up/down/up 和 PostgreSQL integration |
| T0.10 | 增加 Fake adapter contract |
| T1.2 | 增加 PostgreSQL Checkpoint 和 Graph State 测试 |
| T1.3 | 增加 interrupt/resume 和审批重复测试 |
| T1.13 | 增加 plan_hash/side effect tests |
| T1.18 | 增加 local-demo E2E |
| T2.1 | 增加 callback/outbox 幂等 |
| T2.17 | 增加 crash recovery 和 Redis integration |
| T2.3～T2.15 | 真实平台 smoke 作为显式 opt-in，与 Fake CI 分离 |
| T4.15～T4.17 | 增加镜像、dependency、SBOM 和完整 Compose |
| T4.20 | 发布候选执行真实平台 E2E |

测试不变量：

1. HITL 1 前无正式采集。
2. HITL 2 前无业务发布。
3. hash 不匹配时零副作用。
4. succeeded operation 永不二次调用。
5. 正常数据不经过诊断循环。
6. State 中无密钥、大 payload 或 SDK Client。
7. Fake 和真实 adapter 满足同一 Port contract。
8. production 不注册 local-demo 路由。
9. Scheduler 和手动入口创建的 run 使用同一 Graph。
10. 每个数据库 Task 通过 up/down/up。

## 11. Codex 单任务执行模板

后续若需要新增或细分 Task，必须在本文直接按以下字段记录：

    ### Txx.x 任务名称
    **目标**
    **业务价值**
    **实现范围**
    **明确不包含**
    **涉及文件**
    **实现步骤**
    **测试要求**
    **验收标准**
    **验证命令**
    **前置依赖**
    **后续任务**
    **建议 Commit**

执行一个 Task 时，Codex 必须：

1. 先复述 Task 的范围、明确不包含和前置依赖检查结果。
2. 只读取该 Task 直接需要的设计章节和代码。
3. 发现 dirty worktree 时保护用户变更。
4. 先补测试或与实现同 Task 提交测试。
5. 运行该 Task 的验证命令，并提供原始结果摘要。
6. 不扩大范围，不顺便开始后续 Task。
7. 不自动 commit；只有用户明确要求时才按“建议 Commit”提交。
8. 完成后停止，等待人工验收。

## 12. 仍需人工确认的问题

这些问题不阻塞 local-demo，但在对应真实能力 Task 前必须确认：

1. A-02/A-03：两阶段审批人白名单及多人同时操作语义；MVP 当前采用首个合法动作生效。
2. A-05：逾期、长时间未审查和活跃贡献者的最终口径。
3. A-07：成员负载只展示分项，不做绩效综合分，是否接受。
4. A-08：每个飞书逻辑表的 critical/required/optional 字段清单。
5. A-09：飞书与 GitHub 里程碑冲突时的权威口径。
6. A-13：飞书文档 owner/folder 和可见范围。
7. A-14：群消息超时后的查询能力；不可确认时是否接受 unknown + 人工处理。
8. A-16：后台配置修改采用独立确认摘要还是复用某类审批记录。
9. 真实测试租户、测试群、多维表格、文档目标和 GitHub PAT 的可用时间。
10. 数据保留期是否采用 03-database-design.md 的建议默认值。

## 13. 第一个可执行 Task

文档评审通过后的第一个 Task 是 T0.1“建立外部能力验证矩阵”。

它只修改现有 02-architecture-design.md，不写业务代码、不需要真实凭证，并为 T0.2～T0.4 明确 verified/unverified/degraded 的记录方式。T0.1 完成后 Codex 必须停止等待验收，不得自动进入飞书 Spike。

## 14. Milestone 验收门

### Milestone 0

- 外部能力经过 Spike 或明确标记 unverified，并有 Fake 与上线 Contract Test。
- local-demo 配置、固定数据、Fake adapters、手动 run 和基础 CI 可用。
- 不需要真实飞书企业环境即可进入 M1。

### Milestone 1

- 手动 run 完成两次模拟 HITL、单表单仓采集、3～5 指标、结构化报告、Grounding 和三项发布。
- 最小运行详情可观察 run、节点、审批、Tool、错误和 refs。
- 形成可独立演示版本。

### Milestone 2

- 真实 callback/adapter 可选接入，多仓、inbox/outbox、ledger、unknown、部分失败和重启恢复通过。
- 重复 callback/resume/operation 不重复发布。

### Milestone 3

- 正常路径不走诊断；异常路径完成 Observe-Diagnose-Plan-Act-Verify。
- 人工补充、再生成、完整指标、注入和 schema 恢复通过。

### Milestone 4

- 配置、认证、Scheduler、完整后台、首次向导和部署完成。
- 真实平台 E2E、性能、安全和恢复达到 PRD 验收。

## 15. 开始与停止条件

开始任一 Task 前：

- 前置 Task 已人工验收；
- 所需外部能力为 verified，或该 Task 明确只依赖 Fake；
- 工作区无无法解释的冲突；
- 用户明确指定当前 Task。

停止条件：

- 当前 Task 验证通过；或
- 需要用户选择且会改变范围；或
- 外部能力与冻结合约冲突；或
- 同一阻断连续出现且无法在当前 Task 内安全解决。

无论成功还是阻断，都不得自动开始下一个 Task。
