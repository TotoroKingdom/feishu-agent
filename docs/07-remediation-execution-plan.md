# 飞书项目周报 Agent：修复执行计划

> 文档状态：待执行
>
> 编制日期：2026-08-03
>
> 基线：`dev` / `431259f`，依据 2026-08-01 最终测试与验收结果
>
> 目标：关闭发布阻塞项，并为 T1～T44 和 PRD 第 21 节提供可重复的最终验收证据

## 1. 文档用途

本文档供后续 Codex 按修复包逐项执行。它不是新功能计划，也不改变 MVP 范围。所有实现必须继续遵循：

- [PRD](./01-feishu-project-weekly-agent-prd.md)
- [架构设计](./02-architecture-design.md)
- [数据库设计](./03-database-design.md)
- [API 设计](./04-api-design.md)
- [LangGraph 设计](./05-langgraph-design.md)
- [T1～T44 实施计划](./06-implementation-plan.md)

执行目标不是“让现有测试变绿”，而是使生产组装、持久化恢复、外部副作用、部署和真实平台行为符合上述契约，并用实际命令证明结果。

## 2. 当前验收基线

### 2.1 已执行结果

| 项目 | 当前结果 |
|---|---:|
| 唯一测试用例 | 173 通过 / 0 失败 / 0 跳过 |
| 验收门类 | 3 通过 / 5 失败 / 0 跳过 |
| T1～T44 | 20 完成 / 19 部分完成 / 5 未完成 |
| 最终结论 | **FAIL** |

失败门类为：静态检查、迁移一致性、Local-demo 部署 E2E、故障恢复、安全扫描。

### 2.2 发布阻塞项

1. 生产入口使用 `MemorySaver`，服务进程重启后不能依靠 PostgreSQL Checkpoint 恢复。
2. production runtime 会静默回退到 Fake Providers；真实飞书读写适配器与三步发布没有完整接入。
3. 全新 Docker Compose 启动不执行数据库迁移；零业务表时 `/ready` 仍返回成功。
4. Scheduler、数据生命周期和可靠消息 worker 只有类或测试，没有生产进程组装。
5. 管理后台没有可用登录入口，部署页面请求管理 API 后得到 401。
6. Ruff、format 和 mypy 未通过，完整 CI 脚本未覆盖这些失败门禁。
7. Alembic `check` 报告模型与迁移存在大量漂移。
8. Python、Node 和容器扫描存在 HIGH 漏洞；Nginx 镜像未配置非 root 用户。
9. 恢复演练没有证明 waiting run 从持久化 Checkpoint 恢复，也没有证明副作用不重放。
10. 真实飞书、GitHub 和 LLM 只有配置预检，`network_calls_made=false`，不存在真实平台 E2E 证据。

## 3. 执行总则

### 3.1 每次只执行一个修复包

后续应把 R1～R14 分别交给 Codex。每个任务必须：

1. 先读取本文件以及该修复包引用的设计章节。
2. 检查工作区状态，保留无关的用户改动。
3. 先增加或收紧失败测试，再修改实现；只改当前修复包允许的范围。
4. 执行本修复包列出的命令，记录命令、退出码和摘要。
5. 更新本文件中的执行记录和证据位置。
6. 遇到范围外缺陷时只记录，不顺手修复。
7. 不提交、不推送、不创建 PR，除非用户在该次任务中明确授权。

### 3.2 禁止事项

- 不新增 PRD 之外的业务功能。
- 不以 Fake 测试代替真实平台验收。
- production 配置不得自动选择 Fake Provider。
- 不删除、放宽或跳过失败测试来换取通过。
- 不降低 Ruff、mypy、漏洞扫描或迁移检查标准来隐藏问题。
- 不把密钥写入测试夹具、命令行参数、日志、State、API 响应或前端 bundle。
- 不在共享/非临时数据库执行 `downgrade base`、清库或删除卷。
- 没有真实凭证时，R14 必须保持“未验证”，不得伪造成功证据。

### 3.3 证据格式

每条验证记录至少包含：

```text
时间：
环境/容器镜像：
命令：
退出码：
通过/失败/跳过数量：
脱敏结果摘要：
证据文件：
```

真实平台证据可以记录 tenant/repository/resource 的脱敏标识、`run_id`、外部产物 ID 的后四位、时间戳和结果；不得保存 token、secret、PAT、完整 webhook payload 或包含敏感数据的数据库转储。

## 4. 修复依赖与执行顺序

```text
R1 → R2 → R3 → R4 → R5 → R6 → R7
                              ├─→ R8 ─┐
                              └─→ R9 ─┼→ R10 → R11 → R12 → R13 → R14 → 最终复验
                                     ┘
```

R8 与 R9 在 R7 完成后可由不同工作区并行开发，但合并后必须重新执行 R7～R9 的全部测试。未明确要求使用子代理时，Codex 应串行执行。

## 5. 修复包

### R1 工作区与验收基线治理

**目标**：分离用户改动、历史测试产物和本轮修复，建立可重复的命令基线。

**关联任务**：T5、T43、T44。

**执行内容**：

- 运行 `git status --short` 和 `git diff --stat`，列出所有已有改动。
- 识别 `artifacts/recovery-drill`、`artifacts/sbom` 和 `backend/*.egg-info` 中由验收命令生成的变化。
- 只有在用户明确确认这些文件可恢复或重新生成后，才清理它们；不得用 `git reset --hard`。
- 为测试产物确定策略：可重复产物加入忽略，必须版本化的证据写入独立带时间戳目录。
- 记录 Python、Node、npm、Docker、Compose、PostgreSQL 和 Redis 版本。

**验证命令**：

```powershell
git status --short
git diff --check
python --version
node --version
npm --version
docker version
docker compose version
```

**退出条件**：工作区中每个修改文件都有明确归属；后续测试不会无提示覆盖基线证据。

---

### R2 后端静态检查清零

**目标**：消除当前 274 个 Ruff、54 个 format 和 187 个 mypy 问题，不改变业务行为。

**关联任务**：T5、T43。

**允许改动**：后端类型标注、导入、格式、明确的类型收窄和必要测试；不得借机重构业务流程。

**执行内容**：

- 先保存三项检查的完整失败清单并按模块分类。
- 分小批处理 Ruff/format，再处理 mypy；每批运行相关测试。
- 对第三方无类型信息优先使用窄范围 adapter/protocol/stub，不使用全局 `ignore_errors`。
- 禁止用大面积 `# noqa`、`type: ignore` 或降低 strict 配置掩盖问题。

**验证命令**：

```powershell
Set-Location backend
python -m ruff check app tests
python -m ruff format --check app tests
python -m mypy app
python -m pytest tests/unit tests/contract -q
```

**退出条件**：所有命令退出码为 0；静态规则和 mypy strict 配置未放宽。

---

### R3 完整 CI 门禁修正

**目标**：使本地完整 CI 和 GitHub Actions 真正覆盖仓库验收要求，并在任一子命令失败时返回非零。

**关联任务**：T5、T43。

**执行内容**：

- 修正 `scripts/full_ci_local.py`：覆盖后端 app/tests Ruff、format、mypy、全部 pytest（含 security）、前端全部测试/lint/typecheck/build。
- 把真实迁移 up/down/up 与 `alembic check` 纳入使用临时 PostgreSQL 的 CI job。
- 把 secret、Python dependency、Node dependency、filesystem/container scan 设为明确门禁。
- Fake/local-demo 与 real-platform 使用独立 marker/job；真实平台只能显式 opt-in。
- 确保 CI 失败产物脱敏，并记录每个子命令退出码。

**验证命令**：

```powershell
python scripts/full_ci_local.py
python scripts/secret_scan.py
git diff --check
```

**退出条件**：故意制造的临时失败能使聚合脚本返回非零；恢复后完整命令退出码为 0。临时失败验证不得遗留代码变更。

---

### R4 Alembic 模型与迁移一致性

**目标**：全新数据库和升级数据库都得到与 ORM 一致的 schema，`alembic check` 无漂移。

**关联任务**：T8、T9、T11～T16、T19、T22、T30、T35、T37～T43。

**执行内容**：

- 逐项审查 checkpoint 表、索引、外键、nullable、server default 和类型漂移。
- 明确哪些表由 LangGraph 官方 checkpointer 管理，避免 Alembic 误判为应删除对象。
- 新增向前迁移修复已发布 schema；不要篡改已有迁移历史，除非证明确实尚未发布且用户批准。
- 在一次性 PostgreSQL 中验证 `base → head → base → head`。
- 验证已有 head 数据库升级路径并保留关键表数据。

**验证命令**：

```powershell
Set-Location backend
python -m alembic upgrade head
python -m alembic check
python -m alembic downgrade base
python -m alembic upgrade head
python -m pytest tests/integration/persistence -q
```

**安全前提**：`downgrade base` 只允许对本修复包创建的一次性数据库执行，命令前必须输出并核对数据库地址。

**退出条件**：迁移命令和 `alembic check` 均退出 0；升级前后的保留数据断言通过。

---

### R5 PostgreSQL Checkpoint 与真实进程重启恢复

**目标**：production runtime 使用 PostgreSQL saver；进程销毁并重建后能恢复 waiting run，且不会重放已成功副作用。

**关联任务**：T9、T28、T42、PRD 9/19。

**执行内容**：

- 通过应用生命周期创建/关闭 PostgreSQL checkpointer，移除 production 的 `MemorySaver`。
- local-demo/test 可以显式使用内存实现，但不得成为 production fallback。
- 测试必须销毁旧 runtime、数据库连接和进程，再创建新实例；不得复用同一个 saver 对象模拟重启。
- 覆盖 HITL 1、HITL 2、人工补充 interrupt，以及发布中断后的恢复。
- 断言 checkpoint 中不含 secret 或大规模原始数据。

**验证命令**：

```powershell
Set-Location backend
python -m pytest tests/integration/agent/test_postgres_runtime.py -q
python -m pytest tests/integration/recovery/test_restart_recovery.py -q
python -m pytest tests/scenarios/test_human_input_resume.py tests/scenarios/test_partial_publish_failures.py -q
```

**退出条件**：真实新进程恢复测试通过；已成功 Operation 的外部调用次数保持为 1。

---

### R6 全新环境 Docker 部署闭环

**目标**：单命令启动自动完成迁移；只有依赖与 schema 真正可用时 `/ready` 才成功。

**关联任务**：T6、T43、PRD 20。

**执行内容**：

- 增加受控迁移阶段或等价 entrypoint，并处理多副本迁移互斥。
- `/health` 只表示进程存活；`/ready` 必须检查数据库、Redis、所需 schema 和运行时依赖。
- 删除 compose 中默认弱密码，改为显式环境配置并在缺失时 fail closed。
- 修正 HTTP/HTTPS 端口与跳转；开发自签名证书必须有明确使用说明，生产不得默认信任自签名证书。
- 生产镜像切换非 root 用户，只暴露允许路由；production 拒绝 `/internal/*` 和 local-demo。
- 使用独立 Compose project 和独立卷执行 clean-room 测试。

**验证命令**：

```powershell
$env:COMPOSE_PROJECT_NAME = "feishu-agent-acceptance"
docker compose config
docker compose up -d --build --force-recreate
docker compose ps
docker compose exec -T backend python -m alembic current
curl.exe -f http://localhost:8000/health
curl.exe -f http://localhost:8000/ready
docker compose logs --no-color
```

如端口由 Nginx 暴露，应改用 compose 实际映射端口，不得通过 `-k` 掩盖未说明的 TLS 问题。

**退出条件**：全新空卷启动后 schema 已到 head，ready 语义正确，浏览器能访问预期入口，日志无 secret 和迁移竞态。

---

### R7 Profile 驱动的 Provider Factory

**目标**：所有读取、LLM 和副作用 Provider 由统一组装层显式选择；production 缺配置时启动失败。

**关联任务**：T4、T6、T20～T25、T35。

**执行内容**：

- 建立统一 profile：`test`、`local-demo`、`sandbox`、`production`。
- `test/local-demo` 可显式使用 Fake；`sandbox/production` 必须使用真实 adapter。
- 删除业务 service 构造器内的隐式 Fake 默认值。
- 启动时输出 provider 类型和 capability 状态，但不输出凭证或资源完整标识。
- 为错误组合增加 fail-closed 测试，包括 production + Fake、缺凭证、缺 capability。

**验证命令**：

```powershell
Set-Location backend
python -m pytest tests/contract -q
python -m pytest tests/unit/core tests/unit/security/test_secret_boundaries.py -q
python -m pytest tests/integration/health -q
```

**退出条件**：production 任何 Fake fallback 都会在启动期被拒绝；local-demo 行为保持可用。

---

### R8 真实飞书身份、卡片、Bitable 读取与首次配置

**目标**：完成真实飞书读链路和两阶段 HITL 的 sandbox 能力，不在此包执行真实发布写操作。

**关联任务**：T1、T2、T20、T21、T24、T41，PRD 1/3/4/5/9。

**执行内容**：

- 实现真实 tenant token、回调签名/解密、用户身份绑定、卡片发送/更新 adapter。
- 实现真实 Bitable schema/record 分页读取、限流、错误分类和字段映射。
- callback inbox 以平台 event/action ID 去重；重复点击返回稳定结果。
- 两阶段 HITL 的 resume 必须关联持久化 checkpoint、approval revision 和 actor。
- 完成首次配置向导所需后端 capability/connectivity API。
- 先跑无凭证 contract 测试；真实 sandbox 测试必须单独显式 opt-in。

**离线验证命令**：

```powershell
Set-Location backend
python -m pytest tests/contract/feishu tests/integration/feishu_callbacks -q
python -m pytest tests/integration/agent/test_hitl_generation.py tests/integration/agent/test_publish_confirmation.py -q
python -m pytest tests/scenarios/test_feishu_onboarding.py -q
```

**真实验证要求**：新增稳定的 `real-platform` 命令，执行 token、Bitable read、卡片 HITL 1/HITL 2、重复 callback/点击和 checkpoint resume；输出脱敏 run_id 与证据清单。

**退出条件**：离线测试全通过；sandbox 证据证明实际发生网络调用，且重复事件没有重复 resume 或副作用。

---

### R9 真实 GitHub 与 LLM 运行时接入

**目标**：在 sandbox/production runtime 中实际使用真实 GitHub 和 LLM adapter，完成双源、最多五仓采集和结构化生成。

**关联任务**：T1、T3、T22～T24、T33～T35，PRD 2/5/6/10～12/18。

**执行内容**：

- 将已有 GitHub client/reader 接入 Provider Factory，覆盖 issues、PR、commits、reviews、milestones、contributors。
- 验证 PAT 最小权限、分页、限流、404/403 分类、最多五仓有界并发。
- 接入真实 LLM provider 的 structured output、超时、重试、schema recovery 和 token/cost 观测。
- 保持确定性指标由代码计算；LLM 不参与权限、幂等和数值事实判定。
- 对日志、API、State、Trace、前端响应和异常文本执行 secret 边界测试。

**离线验证命令**：

```powershell
Set-Location backend
python -m pytest tests/contract/github -q
python -m pytest tests/integration/admin/test_github_connectivity.py tests/integration/admin/test_llm_connectivity.py -q
python -m pytest tests/integration/agent/test_minimal_collection.py tests/integration/agent/test_structured_report.py -q
python -m pytest tests/scenarios/test_llm_schema_recovery.py tests/scenarios/test_grounding_quality.py -q
python -m pytest tests/unit/security/test_secret_boundaries.py -q
```

**退出条件**：真实 sandbox 证据包含至少两个仓库和一次真实 structured LLM 调用；任何输出均不包含凭证明文。

---

### R10 真实飞书三步发布与副作用可靠性

**目标**：通过统一执行器真实创建飞书文档、发送群消息、写入归档表，并证明 plan_hash、幂等与故障恢复。

**关联任务**：T15、T16、T25～T29，PRD 13～16。

**执行内容**：

- 实现 document、group message、archive 三个真实 effect adapter 和 verifier。
- 所有写操作只能通过 Operation ledger/executor；provider 不得绕过账本。
- 审批时冻结 canonical plan 与 `plan_hash`；执行前重算并常量时间比较。
- 重复 callback、重复点击、并发 claim 和 safe retry 不得重复发布。
- timeout-unknown 必须先查询外部平台，再决定标记成功或重试。
- 三步中任一步失败后只恢复未完成步骤，已成功步骤不得重放。
- 真实 sandbox 测试使用专用文档目录、群和归档表，并提供可清理的产物清单；清理属于单独授权动作。

**离线验证命令**：

```powershell
Set-Location backend
python -m pytest tests/unit/publishing tests/unit/side_effects -q
python -m pytest tests/integration/side_effects -q
python -m pytest tests/integration/agent/test_publish_confirmation.py -q
python -m pytest tests/scenarios/test_partial_publish_failures.py -q
python -m pytest tests/integration/runs/test_safe_retry.py tests/integration/runs/test_cancel.py -q
```

**退出条件**：篡改、重复、并发、unknown 和部分失败场景均有自动测试；真实 sandbox 中三项产物与内部账本一一对应。

---

### R11 Worker、调度、生命周期与恢复演练

**目标**：把 Scheduler、Outbox、租约、恢复和数据生命周期接入真实运行进程，并升级恢复演练。

**关联任务**：T28、T38、T39、T42、T43。

**执行内容**：

- 明确 web 与 worker 的进程边界，在 compose 中启动实际 worker。
- 组装 scheduler、outbox delivery、lease heartbeat、stale run recovery 和 lifecycle cleanup。
- 多 worker 下使用数据库 claim/lease 防止重复调度和重复发送。
- 恢复演练必须备份数据库、恢复到新数据库/新容器、启动新 runtime、resume waiting run、核验 unknown Operation，并断言已成功副作用没有重放。
- 生命周期测试使用专用过期数据，不删除审计和法律/业务要求保留的记录。

**验证命令**：

```powershell
Set-Location backend
python -m pytest tests/unit/scheduling tests/integration/scheduling -q
python -m pytest tests/integration/outbox tests/integration/recovery tests/integration/persistence/test_data_lifecycle.py -q
Set-Location ..
python scripts/recovery_drill.py
```

**退出条件**：实际 worker 容器可观测且健康；恢复演练对 checkpoint、operation 和外部调用计数都有断言。

---

### R12 管理后台登录、配置与可观测 UI

**目标**：用户能从部署入口登录，并完成配置、首次向导、dashboard、运行列表和运行详情全链路。

**关联任务**：T36、T37、T39～T41，PRD 1/17。

**执行内容**：

- 增加可导航的登录页和未认证重定向，正确处理 session、CSRF、旋转、超时和登出。
- 接通 dashboard、run list、run detail、configuration 和 onboarding 的真实后端 API。
- 运行详情展示节点轨迹、tool 调用、审批、重试、operation 和证据链。
- 前端不得接收或渲染 credential value；只展示 fingerprint suffix/status。
- 增加通过 Nginx 的浏览器 E2E，不使用组件 fixture 代替部署验证。

**验证命令**：

```powershell
Set-Location backend
python -m pytest tests/integration/admin tests/security/test_admin_sessions.py -q
Set-Location ../frontend
npm test
npm run lint
npm run typecheck
npm run build
```

**浏览器 E2E 最低路径**：登录 → dashboard → 运行列表 → waiting run → 审批详情 → evidence/operation → 登出；未登录访问管理页必须跳转登录而不是显示 401 错误页。

**退出条件**：API、前端单测和真实部署浏览器 E2E 全通过；浏览器网络响应中没有 secret。

---

### R13 依赖、容器与 Secret 安全整改

**目标**：清除已知 HIGH 漏洞和高风险容器配置，建立发布门禁。

**关联任务**：T6、T34、T37、T39、T43，PRD 18。

**执行内容**：

- 升级存在漏洞的 `cryptography`、`starlette/FastAPI`、Next.js、PostCSS 及其锁文件，逐项运行回归。
- Nginx/应用镜像使用非 root 用户，最小化包和写权限。
- 使用可执行的 Trivy 或等价 scanner；Docker Scout 登录限制不能成为唯一扫描路径。
- 扫描 tracked files、镜像层、容器环境、OpenAPI、前端 bundle、应用日志和脱敏数据库 dump。
- 加入 prompt injection、回调签名、session/CSRF、路由暴露和默认凭证测试。
- 漏洞豁免必须记录 CVE、影响判断、负责人和到期时间，不能无限期忽略。

**验证命令**：

```powershell
python scripts/secret_scan.py
python -m pip_audit -r backend/requirements.txt
npm audit --omit=dev --prefix frontend
trivy fs --severity HIGH,CRITICAL --exit-code 1 .
python scripts/sbom.py
```

构建后还必须对 backend、frontend、nginx 三个最终镜像执行 HIGH/CRITICAL 扫描。

**退出条件**：无未批准的 HIGH/CRITICAL；secret 全边界零命中；SBOM 可重复生成且不含 secret。

---

### R14 显式 opt-in 的真实平台 E2E

**目标**：完成 T44；将无凭证 CI 与真实 Sandbox 验收严格分开。

**关联任务**：T1～T4、T20～T25、T44，PRD 1～20。

**执行内容**：

- 建立 `e2e/real-platform` 或等价测试入口，默认不运行，缺少显式 opt-in 时必须报告 skipped/not requested，而不是 Fake pass。
- 运行真实两阶段 HITL、至少两仓、Bitable + GitHub、structured LLM、Grounding、三步发布和后台查看。
- 注入重复 callback/点击、plan tamper、进程重启、并发 claim、timeout-unknown 和三种部分失败。
- 记录真实 `run_id`、时间、脱敏资源标识、内部 operation ID、外部产物后四位和截图/JSON 摘要。
- 证明日志、API、State、Trace 和前端不含 secret。
- 更新 T1～T44 与 PRD 验收矩阵；未验证能力保持失败或条件项。

**无凭证命令**：

```powershell
python scripts/full_ci_local.py
Set-Location backend
python -m pytest tests/e2e/test_local_demo_happy_path.py -q
```

**真实 Sandbox 命令要求**：项目必须提供单一、文档化、显式 opt-in 命令，例如：

```powershell
$env:RUN_REAL_PLATFORM_E2E = "1"
python -m pytest tests/e2e/real_platform -m real_platform -q
```

真实凭证只能由安全环境注入。测试结束后只输出脱敏证据，不回显环境变量。

**退出条件**：真实网络调用、真实两阶段审批、三项真实外部产物和全部故障场景均通过；没有用 Fake 替代的步骤。

## 6. T1～T44 关闭矩阵

“回归”表示当前验收为完成，但最终仍须重新运行；“关闭”表示需要对应修复包提供新证据。

| Task | 当前状态 | 关闭责任 |
|---|---|---|
| T1 | 部分 | R8、R9、R14 |
| T2 | 未完成 | R8、R14 |
| T3 | 部分 | R9、R14 |
| T4 | 未完成 | R7～R10、R14 |
| T5 | 部分 | R2、R3 |
| T6 | 部分 | R6、R7、R13 |
| T7 | 完成 | 最终回归 |
| T8 | 完成 | 最终回归 |
| T9 | 部分 | R5 |
| T10 | 完成 | 最终回归 |
| T11 | 完成 | 最终回归 |
| T12 | 完成 | 最终回归 |
| T13 | 完成 | 最终回归 |
| T14 | 完成 | 最终回归 |
| T15 | 完成 | R10、最终回归 |
| T16 | 完成 | R10、最终回归 |
| T17 | 完成 | R12、最终回归 |
| T18 | 完成 | 最终回归 |
| T19 | 完成 | 最终回归 |
| T20 | 部分 | R8 |
| T21 | 未完成 | R8 |
| T22 | 部分 | R9 |
| T23 | 部分 | R9 |
| T24 | 部分 | R8、R9 |
| T25 | 未完成 | R10 |
| T26 | 完成 | R10 回归 |
| T27 | 完成 | R10 回归 |
| T28 | 部分 | R5、R10、R11 |
| T29 | 完成 | R10、最终回归 |
| T30 | 完成 | 最终回归 |
| T31 | 完成 | R5、最终回归 |
| T32 | 完成 | 最终回归 |
| T33 | 完成 | R9、最终回归 |
| T34 | 完成 | R9、R13、最终回归 |
| T35 | 部分 | R7～R9 |
| T36 | 部分 | R12 |
| T37 | 部分 | R12、R13 |
| T38 | 部分 | R11 |
| T39 | 部分 | R11、R12 |
| T40 | 部分 | R12 |
| T41 | 部分 | R8、R12 |
| T42 | 部分 | R11 |
| T43 | 部分 | R3、R4、R6、R11、R13 |
| T44 | 未完成 | R14、最终复验 |

任何 Task 只有在其原始“测试要求”和“验收标准”均有实际命令证据后才能标记完成。

## 7. PRD 验收关闭矩阵

| # | PRD 验收项摘要 | 当前 | 关闭责任 |
|---:|---|---|---|
| 1 | 飞书首次项目配置 | 未通过 | R8、R12、R14 |
| 2 | 至少两个 GitHub 仓库 | 未真实验证 | R9、R14 |
| 3 | 周任务与第一阶段卡片 | 部分 | R8、R11、R14 |
| 4 | 修改范围/提示/确认/取消 | 本地通过 | R14 回归 |
| 5 | 读取 Bitable 与 GitHub | 未真实验证 | R8、R9、R14 |
| 6 | 确定性指标 | 本地通过 | 最终回归 |
| 7 | 数据缺失诊断循环 | 本地通过 | 最终回归 |
| 8 | 自动恢复失败后人工补充 | 本地通过 | R5、R14 回归 |
| 9 | 补充后 Checkpoint 恢复 | 部分 | R5、R14 |
| 10 | 结构化中间结果 | 本地通过 | R9、R14 回归 |
| 11 | 关键结论证据追溯 | 本地通过 | R9、R14 回归 |
| 12 | 无证据内容标记/阻止 | 本地通过 | R9、R14 回归 |
| 13 | 发布计划展示并等待确认 | 本地通过 | R10、R14 回归 |
| 14 | 审批后变更重新审批 | 本地通过 | R10、R14 回归 |
| 15 | 文档/群消息/归档三步发布 | 未真实验证 | R10、R14 |
| 16 | 重复回调不重复发布 | 部分 | R8、R10、R14 |
| 17 | 后台完整轨迹 | 未通过 | R11、R12、R14 |
| 18 | Secret 不进入各边界 | 部分 | R7～R10、R12、R13、R14 |
| 19 | 重启后 waiting run 可恢复 | 未通过 | R5、R11、R14 |
| 20 | 核心测试与 Compose 一键启动 | 未通过 | R2～R6、R13、最终复验 |

## 8. 最终复验门禁

R1～R14 完成后，进入一次只验收、不修复的独立任务。至少依次执行以下门类，并记录每条命令退出码。

### 8.1 静态检查

```powershell
Set-Location backend
python -m ruff check app tests
python -m ruff format --check app tests
python -m mypy app
Set-Location ../frontend
npm run lint
npm run typecheck
npm run build
```

### 8.2 单元、Contract、集成、场景与前端测试

```powershell
Set-Location backend
python -m pytest tests/unit -q
python -m pytest tests/contract -q
python -m pytest tests/integration -q
python -m pytest tests/scenarios -q
python -m pytest tests/security -q
Set-Location ../frontend
npm test
```

### 8.3 迁移、Local-demo E2E 与恢复

```powershell
Set-Location backend
python -m alembic upgrade head
python -m alembic check
python -m pytest tests/e2e/test_local_demo_happy_path.py -q
Set-Location ..
python scripts/recovery_drill.py
```

完整迁移往返必须在独立空数据库执行，不能对共享数据执行 downgrade。

### 8.4 安全与供应链

```powershell
python scripts/secret_scan.py
python -m pip_audit -r backend/requirements.txt
npm audit --omit=dev --prefix frontend
trivy fs --severity HIGH,CRITICAL --exit-code 1 .
python scripts/sbom.py
```

### 8.5 Clean Docker 与真实平台

- 使用新 Compose project、新卷构建并启动。
- 验证自动迁移、health/ready、允许/禁止路由、管理员登录、重启恢复和 worker。
- 先执行无凭证完整 CI；再由授权人员注入 Sandbox 凭证，显式执行 real-platform E2E。
- 两组结果分别统计，禁止合并成一个“通过”数字。

## 9. 最终判定规则

### PASS

- R1～R14 全部关闭；
- T1～T44 全部有真实证据完成；
- PRD 20 项全部通过；
- 所有必需门禁退出码为 0；
- 无未批准 HIGH/CRITICAL 安全问题；
- 真实 Sandbox E2E 已完成且无 Fake 替代。

### CONDITIONAL PASS

仅适用于不影响 MVP 核心能力、已有书面责任人和截止日期的外部限制。以下情况不能给 CONDITIONAL PASS：

- 真实平台核心读写仍未验证；
- Checkpoint 重启恢复未通过；
- plan_hash、幂等、timeout-unknown 或部分失败恢复未通过；
- Secret 泄露或存在未批准 HIGH/CRITICAL；
- 全新 Docker 环境不能一键 ready。

### FAIL

任一发布阻塞项未关闭、必需命令非零、真实能力被 Fake 替代，或证据不足以证明行为时，结论必须为 FAIL。

## 10. 交给 Codex 的任务模板

每次复制下面模板，只替换修复包编号：

```text
执行 docs/07-remediation-execution-plan.md 的 R__。

要求：
1. 先读取 PRD、架构、数据库、API、LangGraph、Implement Plan 和修复执行计划中与 R__ 相关的章节。
2. 只处理 R__ 范围，不扩大 MVP；发现范围外问题只记录。
3. 先建立能复现问题的测试，再修改实现。
4. 保留工作区已有无关改动，不 reset，不清理未确认产物。
5. 执行 R__ 的全部验证命令，报告实际命令、退出码、通过/失败/跳过数量。
6. 更新修复执行计划的执行记录；没有证据不得标记完成。
7. 无真实凭证与真实 Sandbox 结果分开；Fake 不得代替真实平台。
8. 完成后停止，不提交、不推送、不创建 PR。
```

## 11. 执行记录

| 修复包 | 状态 | 日期 | 代码基线 | 结果与证据 |
|---|---|---|---|---|
| R1 | 完成 | 2026-08-04 | `dev` / `431259f54f8e`（未提交工作区） | R1 必需命令 7/7 退出 0；回归测试 7/0/0、根目录累计测试 13/0/0；历史生成物未清理，脚本/CI/TypeScript/包装 metadata 与版本化证据已分流；只读复审无 Critical/Important；真实 Sandbox 未请求/未执行。[证据](../artifacts/evidence/20260804T092428+0800-r1/verification.md) |
| R2 | 完成 | 2026-08-04 | `dev` / 实际开始 `042bf19dd2b3`（执行期间外部推进至 `fb081312b153`） | Ruff 274→0、format 54→0、mypy 187→0；unit/contract 76/0/0；未放宽配置、未清理 R1 或历史生成物、未执行 R3/R4；基线偏差与外部提交已如实记录。[证据](../artifacts/evidence/20260804T215608+0800-r2/verification.md) |
| R3 | 待执行 |  |  |  |
| R4 | 待执行 |  |  |  |
| R5 | 待执行 |  |  |  |
| R6 | 待执行 |  |  |  |
| R7 | 待执行 |  |  |  |
| R8 | 待执行 |  |  |  |
| R9 | 待执行 |  |  |  |
| R10 | 待执行 |  |  |  |
| R11 | 待执行 |  |  |  |
| R12 | 待执行 |  |  |  |
| R13 | 待执行 |  |  |  |
| R14 | 待执行 |  |  |  |
| 最终复验 | 待执行 |  |  |  |
