# 飞书项目周报 Agent：API 设计

> 文档编号：DESIGN-004  
> 对应需求：`01-feishu-project-weekly-agent-prd.md` v1.0  
> 状态：待评审  
> 约束：API 层只做协议适配、鉴权、校验和用例调用，不承载 Agent 业务逻辑

## 1. API 分区

| 分区 | 前缀 | 调用方 | 鉴权 |
|---|---|---|---|
| 飞书开放平台入口 | `/api/v1/feishu` | 飞书平台 | 回调来源验证、解密、防重放 |
| 管理后台 | `/api/v1/admin` | Next.js 管理后台 | 管理员 Session/JWT |
| 本地演示 | `/api/v1/local-demo` | 开发者/自动化测试 | 仅 `APP_PROFILE=local-demo`，生产必须 404/拒绝启动 |
| 内部 Worker | `/internal/v1` | 受信 API/Worker/Scheduler | 内网 + service token/mTLS；单进程部署可直接调用应用服务 |
| 运维 | `/health`, `/ready`, `/metrics` | 编排/监控 | health 可公开最小信息；metrics 限内网 |

除飞书协议要求外，所有业务 JSON 使用 `snake_case`，时间为 ISO 8601 UTC，ID 为 UUID 字符串。

## 2. 通用协议

### 2.1 请求上下文

- 客户端可传 `X-Request-ID`；缺失时服务端生成。
- 响应返回 `X-Request-ID`。
- 修改类后台请求支持 `Idempotency-Key`。
- 乐观并发更新使用 `If-Match: "<revision>"` 或请求体 `revision`。
- API 内部关联 `run_id`，但不得信任客户端直接改变 run 状态。

### 2.2 成功响应

单资源：

```json
{
  "data": {},
  "meta": {
    "request_id": "req_..."
  }
}
```

列表：

```json
{
  "data": [],
  "page": {
    "next_cursor": null,
    "has_more": false
  },
  "meta": {
    "request_id": "req_..."
  }
}
```

后台列表优先 cursor 分页；仪表盘小型聚合可不分页。

### 2.3 统一错误

```json
{
  "error": {
    "code": "RUN_STATE_CONFLICT",
    "message": "当前运行状态不允许该操作",
    "details": {
      "run_id": "019..."
    },
    "retryable": false
  },
  "meta": {
    "request_id": "req_..."
  }
}
```

禁止返回：

- 堆栈；
- SQL/表结构细节；
- GitHub PAT、飞书 Secret、LLM API Key；
- 未脱敏的外部请求体；
- 内部异常对象 `repr`。

主要错误码：

| HTTP | Code | 含义 |
|---|---|---|
| 400 | `VALIDATION_ERROR` | DTO/业务参数非法 |
| 401 | `UNAUTHENTICATED` | 管理员未登录 |
| 403 | `FORBIDDEN` | 权限不足或飞书 actor 不在白名单 |
| 404 | `RESOURCE_NOT_FOUND` | 资源不存在 |
| 409 | `REVISION_CONFLICT` | 配置并发版本冲突 |
| 409 | `RUN_ALREADY_ACTIVE` | 同周期已有活动运行 |
| 409 | `RUN_STATE_CONFLICT` | 状态不允许操作 |
| 409 | `APPROVAL_ALREADY_DECIDED` | 审批已处理 |
| 409 | `PLAN_HASH_MISMATCH` | 发布计划失效 |
| 422 | `EXTERNAL_CAPABILITY_MISSING` | 外部能力/字段不满足 |
| 429 | `RATE_LIMITED` | 后台自身限流 |
| 502 | `EXTERNAL_PROVIDER_ERROR` | 外部平台错误 |
| 503 | `DEPENDENCY_UNAVAILABLE` | DB/Redis/Worker 不可用 |

### 2.4 异步任务

连通性测试、运行启动、resume 和安全重试返回 `202 Accepted`：

```json
{
  "data": {
    "job_id": "019...",
    "status": "accepted",
    "status_url": "/api/v1/admin/jobs/019..."
  }
}
```

任务状态：`queued/running/succeeded/failed/cancelled`。Job 只表示命令处理，不替代 `report_runs.status`。

## 3. 飞书回调

### 3.1 `POST /api/v1/feishu/events`

用途：

- URL 验证 challenge；
- 接收机器人私聊消息；
- 接收必要的用户/群事件。

处理顺序：

1. 读取原始 body 和 headers，限制请求体大小。
2. 验证来源/签名或 verification token；如启用加密先按协议解密。
3. 校验时间窗，提取 `external_event_id`。
4. 在 `callback_events` 登记 inbox；重复事件直接返回平台要求的成功响应。
5. challenge 同步返回。
6. 其他事件写 outbox/任务队列。
7. 3 秒内响应，不同步执行配置向导或 Graph。

响应体严格遵循飞书平台协议，具体字段以 Phase 0 能力验证结果为准。

支持的事件白名单：

- 机器人私聊消息：配置向导输入或已知命令；
- 不处理群聊中的任意自由指令；
- 未知事件记脱敏审计后返回成功，避免平台反复投递。

### 3.2 `POST /api/v1/feishu/card-actions`

用途：接收配置、HITL、人工补充、取消和补偿卡片动作。

内部规范化 DTO：

```json
{
  "external_event_id": "evt_xxx",
  "actor": {
    "open_id": "ou_xxx",
    "tenant_key": "xxx"
  },
  "action": {
    "action_type": "approve_publish",
    "challenge_id": "019...",
    "run_id": "019...",
    "approval_revision": 2,
    "payload": {},
    "presented_hash": "sha256..."
  },
  "occurred_at": "2026-07-24T10:00:00Z"
}
```

合法 `action_type`：

- 配置：`config_next`, `config_back`, `config_confirm`, `config_cancel`
- HITL 1：`approve_generation`, `modify_generation_scope`, `cancel_run`
- 人工补充：`submit_human_input`, `cancel_run`
- HITL 2：`approve_publish`, `regenerate_report`, `update_supplement`, `cancel_publish`
- 部分失败：`verify_again`, `retry_failed_operations`（仍受原计划约束）

关键校验：

1. callback 合法且未重放；
2. `challenge_id` 存在且 pending；
3. actor 属于 `requested_from` 白名单；
4. `run_id/revision/presented_hash` 匹配；
5. action 是当前审批类型允许的动作；
6. 表单字段通过 action 对应 schema；
7. 原子消费 challenge，派发 resume 命令。

重复点击必须返回“已处理”的友好卡片响应，但不再派发命令。

### 3.3 快速响应与卡片更新

卡片回调同步响应只表达“已接收/已处理/校验错误”。后续：

- Worker 恢复成功后异步更新卡片状态；
- 原卡片按钮尽可能禁用；
- 卡片更新失败不撤销已经合法完成的审批，记录协调消息失败并重试。

## 4. 管理后台认证 API

### 4.1 `POST /api/v1/admin/auth/login`

请求：

```json
{
  "username": "admin",
  "password": "********"
}
```

响应设置 HttpOnly、Secure、SameSite Cookie；正文仅返回管理员摘要和过期时间。登录失败使用统一信息，有限速和锁定策略。

### 4.2 `POST /api/v1/admin/auth/refresh`

使用可撤销 refresh session 换取短期 access token；旋转 refresh token。

### 4.3 `POST /api/v1/admin/auth/logout`

撤销当前 session，幂等返回 204。

### 4.4 `GET /api/v1/admin/auth/me`

返回 `id`, `username`, `status`, `session_expires_at`。

## 5. 项目配置 API

MVP 只有单项目，路径仍使用资源 ID 以保持接口清晰，不代表实现多项目产品能力。

### 5.1 项目

- `GET /api/v1/admin/project`
- `PUT /api/v1/admin/project`

更新请求示例：

```json
{
  "name": "Project Alpha",
  "description": "项目描述",
  "timezone": "Asia/Shanghai",
  "default_period_rule": {
    "type": "previous_calendar_week"
  },
  "default_prompt_version_id": "019...",
  "revision": 3
}
```

更新先校验、生成配置变更摘要，再由单管理员确认提交；写审计。对已创建 run 不追溯生效。

### 5.2 仓库绑定

- `GET /api/v1/admin/project/repositories`
- `POST /api/v1/admin/project/repositories`
- `PATCH /api/v1/admin/project/repositories/{repository_id}`
- `DELETE /api/v1/admin/project/repositories/{repository_id}`
- `POST /api/v1/admin/project/repositories/{repository_id}/connectivity-test`

创建/更新要求 `owner`, `repo`, `repository_type`, `weight`, `enabled`。删除实际为禁用；若被非终态 run 的快照引用不得物理删除。

连通性结果：

```json
{
  "data": {
    "status": "degraded",
    "repository_id": 123456,
    "default_branch": "main",
    "capabilities": {
      "metadata": "ok",
      "issues": "ok",
      "pull_requests": "ok",
      "reviews": "permission_missing",
      "commits": "ok",
      "milestones": "ok",
      "contributors": "ok"
    },
    "checked_at": "2026-07-24T10:00:00Z"
  }
}
```

### 5.3 飞书资源与字段映射

- `GET /api/v1/admin/project/feishu-resources`
- `POST /api/v1/admin/project/feishu-resources`
- `PATCH /api/v1/admin/project/feishu-resources/{resource_id}`
- `POST /api/v1/admin/project/feishu-resources/{resource_id}/schema`
- `PUT /api/v1/admin/project/feishu-resources/{resource_id}/field-mappings`
- `POST /api/v1/admin/project/feishu-resources/{resource_id}/connectivity-test`

字段映射请求：

```json
{
  "schema_hash": "sha256...",
  "mappings": [
    {
      "logical_field": "task_id",
      "external_field_id": "fld_xxx",
      "external_field_type": "text",
      "converter": "text",
      "required_level": "critical",
      "mapping_options": {}
    }
  ],
  "revision": 2
}
```

若实时 schema hash 已变化，返回 `409 REVISION_CONFLICT`，防止把旧 mapping 写给新表结构。

### 5.4 凭证

- `GET /api/v1/admin/project/credentials`
- `PUT /api/v1/admin/project/credentials/github-pat`
- `POST /api/v1/admin/project/credentials/github-pat/validate`
- `PUT /api/v1/admin/llm/credential`

GET 只返回：

```json
{
  "credential_type": "github_pat",
  "status": "active",
  "fingerprint_suffix": "a91c",
  "expires_at": null,
  "last_validated_at": "2026-07-24T10:00:00Z"
}
```

PUT 的秘密字段为 write-only，不回显；禁止通用 `PATCH` 读取或修改密文字段。

### 5.5 定时规则

- `GET /api/v1/admin/project/schedule`
- `PUT /api/v1/admin/project/schedule`
- `POST /api/v1/admin/project/schedule/validate`

请求包含 `cron_expression`, `timezone`, `enabled`, `misfire_policy`, `revision`。响应给出未来 3 次触发时间，帮助校验时区。

### 5.6 Prompt 与模型

- `GET /api/v1/admin/model-config`
- `PATCH /api/v1/admin/model-config`
- `GET /api/v1/admin/prompts?type=report`
- `POST /api/v1/admin/prompts`
- `POST /api/v1/admin/prompts/{prompt_version_id}/activate`

模型配置只允许非敏感字段：`base_url` 是否可修改需部署策略决定；`model`, `temperature`, `timeout`, `max_retries`, `stream` 可配。API 永不返回 API Key。

### 5.7 聚合连通性

- `POST /api/v1/admin/project/connectivity-test`
- `GET /api/v1/admin/connectivity-jobs/{job_id}`

按能力而非单一布尔值返回 GitHub、飞书表、群、文档和 LLM 检测结果。

## 6. 运行与可观测 API

### 6.1 仪表盘

`GET /api/v1/admin/dashboard?from=...&to=...`

返回：

- 最近运行；
- 成功率、平均主动耗时；
- 等待审批数；
- Tool 失败率和重试次数；
- 数据质量分布；
- Token 使用量。

默认时间窗口必须明确，例如最近 30 天。

### 6.2 运行列表

`GET /api/v1/admin/runs`

查询参数：

- `status`
- `created_from`, `created_to`
- `requester_id`
- `period_start`, `period_end`
- `has_human_input`
- `has_retry`
- `has_partial_failure`
- `cursor`, `limit`（上限 100）

### 6.3 运行详情

`GET /api/v1/admin/runs/{run_id}`

返回当前状态、周期、范围摘要、数据质量、当前节点、等待原因、审批摘要、计划哈希、最终产物和耗时。大型列表使用独立端点：

- `GET /api/v1/admin/runs/{run_id}/timeline`
- `GET /api/v1/admin/runs/{run_id}/nodes`
- `GET /api/v1/admin/runs/{run_id}/tools`
- `GET /api/v1/admin/runs/{run_id}/llm-executions`
- `GET /api/v1/admin/runs/{run_id}/diagnoses`
- `GET /api/v1/admin/runs/{run_id}/approvals`
- `GET /api/v1/admin/runs/{run_id}/evidence`
- `GET /api/v1/admin/runs/{run_id}/artifacts`
- `GET /api/v1/admin/runs/{run_id}/publish-plan`
- `GET /api/v1/admin/runs/{run_id}/side-effects`

所有 Tool/LLM 参数只返回脱敏摘要；Checkpoint State 不提供任意下载接口。

### 6.4 运行控制

#### `POST /api/v1/admin/runs/{run_id}/cancel`

请求：

```json
{
  "reason": "管理员取消",
  "expected_status": "waiting_generation_approval"
}
```

规则：

- 正式发布前设置取消请求并派发 Graph resume；
- 发布中只取消尚未开始的 operation；
- 已完成 operation 保留；
- 返回 202。

#### `POST /api/v1/admin/runs/{run_id}/safe-retry`

仅允许：

- `failed` 且失败节点可安全重放；
- `partial_failed` 且仅恢复原批准计划中的 failed/unknown 操作；
- 必须提供 `reason`；
- 重新验证审批、计划哈希和实际外部结果。

它不允许绕过 HITL 或把已取消 run 改回活动状态。

#### `POST /api/v1/admin/runs/trigger`

管理员演示/补跑入口，调用 `RunCreationService`，使用项目默认周期或显式周期；创建后仍停在 HITL 1。它是最小纵向闭环入口，Scheduler 只在产品化阶段复用同一服务。

### 6.7 `local-demo` 模拟入口

仅在 `APP_PROFILE=local-demo` 注册：

- `POST /api/v1/local-demo/runs`：选择固定 scenario 并手动创建运行；
- `POST /api/v1/local-demo/runs/{run_id}/actions`：模拟经过同一 Approval Service 校验的 HITL 动作；
- `GET /api/v1/local-demo/scenarios`：列出固定演示数据集。

合法 scenario 至少包括 `happy_path`, `github_repository_failure`, `feishu_critical_field_missing`, `side_effect_partial_failure`。

模拟入口不能：

- 直接修改 Graph State；
- 绕过 approval revision/hash；
- 绕过 `SideEffectExecutor`；
- 在非 local-demo 配置下注册；
- 接受任意文件路径、URL、Tool 名或外部 payload。

### 6.5 Job 状态

`GET /api/v1/admin/jobs/{job_id}` 只返回命令状态和关联 `run_id`，不返回内部队列信息。

### 6.6 实时刷新

MVP 默认后台以 React Query 轮询运行详情和时间线（活动 run 2–5 秒，终态停止），不强制引入 WebSocket/SSE。若实际体验需要，可增加只读 SSE，但不作为验收必需项。

## 7. 内部服务 API 与命令契约

模块化单体内优先使用 Python Application Port；只有当 API/Worker 分进程时，通过数据库 outbox/队列传递下列版本化命令。`/internal/v1` HTTP 是运维补充入口，不应暴露公网。

### 7.1 命令信封

```json
{
  "message_id": "019...",
  "message_type": "RESUME_WORKFLOW",
  "schema_version": 1,
  "dedupe_key": "sha256...",
  "occurred_at": "2026-07-24T10:00:00Z",
  "request_id": "req_...",
  "run_id": "019...",
  "payload": {}
}
```

消费者必须以 `message_id/dedupe_key` 去重。

### 7.2 核心命令

| 命令 | 生产者 | 消费者 | 载荷 |
|---|---|---|---|
| `CREATE_SCHEDULED_RUN` | Scheduler | Run service | project、period、schedule revision |
| `START_REPORT_RUN` | Run service | Graph worker | run_id, thread_id, graph_version |
| `RESUME_WORKFLOW` | Approval service | Graph worker | run_id, interrupt_id, resume_payload_ref |
| `CANCEL_REPORT_RUN` | 飞书/后台 | Graph worker | run_id, actor, reason |
| `SAFE_RETRY_RUN` | 后台 | Recovery worker | run_id, allowed_scope, reason |
| `EXECUTE_SIDE_EFFECT` | Graph | Side-effect worker/同一 Worker | operation_id, approved_plan_hash |
| `VERIFY_SIDE_EFFECT` | Recovery | Side-effect verifier | operation_id |
| `UPDATE_COORDINATION_CARD` | Graph | Feishu message worker | card_ref, template, state ref |

### 7.3 Application Ports

以下是内部接口职责，不是公网 REST：

```text
RunCommandService.create_scheduled_run(...)
RunCommandService.cancel_run(...)
WorkflowRuntime.start(run_id)
WorkflowRuntime.resume(run_id, interrupt_id, payload_ref)
ApprovalService.consume_callback(...)
ToolExecutor.execute(spec, context, input) -> ToolResult
ReportService.calculate/build/generate/verify/render(...)
PublishPlanService.freeze(...) -> plan_hash
SideEffectExecutor.execute(operation_id)
SideEffectVerifier.verify(operation_id)
RecoveryService.recover_stale_runs(...)
```

端口参数使用 DTO/ID，不传外部 SDK 对象。

### 7.4 内部 HTTP（如启用）

- `POST /internal/v1/jobs/dispatch`
- `POST /internal/v1/workflows/{run_id}/start`
- `POST /internal/v1/workflows/{run_id}/resume`
- `POST /internal/v1/side-effects/{operation_id}/execute`
- `POST /internal/v1/recovery/scan`

必须限制来源、使用短期 service credential、记录 audit，并在 Nginx 明确禁止公网路由。

## 8. HITL API 语义

### 8.1 生成范围修改

卡片 `modify_generation_scope` 不是直接 resume 主采集，而是：

1. 校验时间、仓库白名单和提示长度；
2. `scope_revision + 1`；
3. 旧 generation approval 标为 `superseded`；
4. 重建范围草案和 hash；
5. 发送/更新新确认卡片；
6. 继续等待明确批准。

### 8.2 人工补充

补充请求包含 machine-readable schema：

```json
{
  "problem_key": "missing_member_mapping:ou_xxx",
  "requested_fields": [
    {
      "name": "github_username",
      "type": "string",
      "required": true
    }
  ],
  "resume_from": "validate_data",
  "checkpoint_id": "..."
}
```

回调只提交允许字段。补充先持久化、校验，再 resume；不接受任意 Tool 指令。

### 8.3 发布批准

`approve_publish` 必须同时携带：

- `challenge_id`
- `approval_revision`
- `run_id`
- `presented_hash = plan_hash`

服务端重新从数据库 canonical plan 计算 hash，不能只比较客户端字符串。任何失配都使旧审批失效并重新发卡。

## 9. 幂等与重试

### 9.1 API 幂等

| 场景 | 幂等键 |
|---|---|
| 飞书事件 | `provider + external_event_id` |
| 卡片动作 | `external_event_id + challenge_id` |
| 定时创建 | `project_id + period_start + period_end` |
| 管理员手动触发 | `Idempotency-Key` + 请求 hash |
| 安全重试 | `run_id + failed_state_revision + Idempotency-Key` |

相同 key、相同请求返回首次结果；相同 key、不同请求 hash 返回 409。

### 9.2 外部调用重试

- 只读 GET：超时、5xx、明确限流可自动重试。
- 回调响应：不调用耗时外部服务。
- 副作用 POST：只有平台原生支持幂等，或本地能先查询确认未执行时才重试。
- 重试上限与等待由 Tool/operation policy 管理，不由 HTTP 客户端默认无限重试。

## 10. API 安全

- OpenAPI 文档生产环境仅管理员可见或关闭。
- DTO 对秘密字段使用专用 write model，响应 model 根本不定义秘密字段。
- 所有输入有长度、枚举和 allowlist 校验。
- URL 字段只允许 GitHub 和飞书合法域名/应用生成 URL。
- 后台 Cookie 防 XSS/CSRF；跨域仅允许配置的前端 origin。
- 管理操作审计 actor、资源、前后摘要和结果。
- 运行查询按脱敏 projection 返回，禁止任意 SQL/filter 表达式。

## 11. API 验收

- [ ] 飞书 challenge、事件和卡片回调均能在 3 秒内返回。
- [ ] 重复事件和重复按钮不重复派发 resume/副作用。
- [ ] 越权 actor、过期 challenge、旧 revision 和 hash 失配被拒绝。
- [ ] 后台可完成 PRD 要求的配置、连通性、运行观察、取消和安全重试。
- [ ] 凭证 GET/API 错误/OpenAPI schema 均不泄露秘密。
- [ ] 所有外部写入无法通过后台通用接口绕过发布审批。
- [ ] 管理后台的运行详情能关联节点、Tool、诊断、审批、证据和产物。
- [ ] 内部命令版本化、可去重，且不暴露公网。
- [ ] 手动运行入口与 Scheduler 使用同一 `RunCreationService`，Graph 不依赖 Scheduler。
- [ ] local-demo 可模拟完整审批与副作用结果，生产环境不存在模拟入口。
