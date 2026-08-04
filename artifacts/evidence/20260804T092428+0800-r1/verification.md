# R1 工作区与验收基线治理证据

- 时间：2026-08-04T09:24:28+08:00
- 工作区：`C:\AI\feishu-agent`
- 分支 / HEAD：`dev` / `431259f54f8e`
- 真实凭证：未访问
- 真实 Sandbox：未请求、未执行；本证据不包含真实平台结果
- Fake：回归测试只隔离本地命令调用，不计作真实平台验收

## 初始工作区归属

R1 开始前已存在以下变更，本轮未清理、未还原：

- 历史验收命令生成：
  `artifacts/recovery-drill/postgres-backup.sql`、
  `artifacts/recovery-drill/seed-state.json`、
  `artifacts/sbom/backend.sbom.json`、
  `artifacts/sbom/frontend.sbom.json`、
  `artifacts/sbom/nginx.sbom.json`、
  `backend/feishu_project_weekly_agent_backend.egg-info/PKG-INFO`、
  `backend/feishu_project_weekly_agent_backend.egg-info/SOURCES.txt`、
  `backend/feishu_project_weekly_agent_backend.egg-info/requires.txt`。
- 用户提供的修复计划：`docs/07-remediation-execution-plan.md`（初始为未跟踪文件）。

本轮 R1 变更归属：

- 产物策略：`.gitignore`、`README.md`；
- CI 消费端与前端增量缓存：`.github/workflows/ci.yml`、
  `frontend/tsconfig.json`；
- 产物路径实现：`scripts/_ops.py`、`scripts/sbom.py`、
  `scripts/recovery_drill.py`、`scripts/full_ci_local.py`、
  `scripts/dependency_scan.py`、`scripts/secret_scan.py`；
- 包装 metadata 隔离：`backend/setup.cfg`、
  `backend/.build-metadata/.gitkeep`；
- 回归测试：`tests/test_artifact_isolation.py`；
- 执行证据与记录：本文件、`docs/07-remediation-execution-plan.md`。

初始 `git diff --numstat` 对上述八个生成文件的统计为：

```text
228  2    artifacts/recovery-drill/postgres-backup.sql
2    2    artifacts/recovery-drill/seed-state.json
201  201  artifacts/sbom/backend.sbom.json
276  276  artifacts/sbom/frontend.sbom.json
17   17   artifacts/sbom/nginx.sbom.json
2    0    backend/feishu_project_weekly_agent_backend.egg-info/PKG-INFO
68   0    backend/feishu_project_weekly_agent_backend.egg-info/SOURCES.txt
2    0    backend/feishu_project_weekly_agent_backend.egg-info/requires.txt
```

## 根因与策略

验收脚本把可重复生成物写入固定且已跟踪的 `artifacts/*` 路径，Setuptools
把 metadata 写入已跟踪的 `backend/*.egg-info`，导致后续命令静默覆盖历史基线。

R1 采用非破坏性策略：

- 可重复生成物写入并忽略
  `artifacts/generated/<run-id>/<command>/`；
- 需要版本化的脱敏证据写入
  `artifacts/evidence/<timestamp>-<scope>/`；
- Setuptools metadata 写入并忽略 `backend/.build-metadata/`；
- TypeScript incremental metadata 写入已忽略的
  `frontend/.next/cache/`；
- SBOM CI 生产端和上传端使用相同确定性 run-id，缺少新产物时上传步骤失败；
- 历史已跟踪产物保持原状，未获得用户确认前不删除、不还原、不取消跟踪。

## TDD 证据

### RED

- 命令：`python -m unittest discover -s tests -p "test_artifact_isolation.py" -v`
- 退出码：`1`
- 通过 / 失败 / 跳过：`0 / 4 / 0`（4 个测试，产生 6 个断言失败）
- 摘要：固定输出仍指向 `artifacts/sbom`、`artifacts/recovery-drill`、
  `artifacts/alembic.sql`、`artifacts/dependency-scan`、
  `artifacts/compose.config.yml`，Setuptools 在 `pyproject.toml` 旁生成
  `*.egg-info`。

### GREEN

- 命令：`python -m unittest discover -s tests -p "test_artifact_isolation.py" -v`
- 退出码：`0`
- 通过 / 失败 / 跳过：`4 / 0 / 0`
- 摘要：SBOM、恢复演练、CI/扫描快照和 Setuptools metadata 均写入隔离目录。

### 只读审查后的 RED

- 命令：`python -m unittest discover -s tests -p "test_artifact_isolation.py" -v`
- 退出码：`1`
- 通过 / 失败 / 跳过：`4 / 3 / 0`（7 个测试，产生 6 个断言失败）
- 摘要：SBOM workflow 仍上传旧 `artifacts/sbom`；TypeScript 未设置隔离的
  `tsBuildInfoFile`；run-id 仍接受 Windows 保留名和尾随点。

### 只读审查后的 GREEN

- 命令：`python -m unittest discover -s tests -p "test_artifact_isolation.py" -v`
- 退出码：`0`
- 通过 / 失败 / 跳过：`7 / 0 / 0`
- 摘要：SBOM 生产/上传路径一致并 fail-closed；TypeScript cache 使用
  `.next/cache`；full CI 向扫描子进程传播同一 run-id；Windows 不可移植
  run-id 被拒绝。

### TypeScript tracked 产物保护

- 命令：`npm run typecheck --prefix frontend`，并对
  `frontend/tsconfig.tsbuildinfo` 前后执行 SHA-256
- 退出码：`0`
- 通过 / 失败 / 跳过：`1 / 0 / 0`（命令级）
- 摘要：typecheck 通过；tracked 文件前后 hash 均为
  `A4CE3C301A67BE41BBD9357076F2698F7EBA7B3F1CC372EC96DA3E542897B740`；
  `frontend/.next/cache/tsconfig.tsbuildinfo` 已生成。

### 独立只读审查

- 初审：2 个 Important（SBOM 上传旧路径、tracked TypeScript cache）和
  2 个 Minor。
- 修复复审：全部 Critical/Important 均已解决，未引入新的
  Critical/Important；配置契约测试仍不能替代 GitHub Actions 平台执行，记录为
  Minor，不扩大为 R3/T43 的真实 CI 执行。

### 受影响静态检查

- 命令：`python -m ruff check scripts tests/test_artifact_isolation.py`
- 退出码：`0`
- 通过 / 失败 / 跳过：`1 / 0 / 0`（命令级）
- 摘要：`All checks passed!`
- 命令：`python -m ruff format --check scripts tests/test_artifact_isolation.py`
- 退出码：`0`
- 通过 / 失败 / 跳过：`13 / 0 / 0`（文件级）
- 摘要：`13 files already formatted`

## 环境版本

| 命令 | 退出码 | 通过 / 失败 / 跳过 | 脱敏结果摘要 |
|---|---:|---:|---|
| `python --version` | 0 | 1 / 0 / 0 | Python 3.13.13 |
| `node --version` | 0 | 1 / 0 / 0 | v24.18.0 |
| `npm --version` | 0 | 1 / 0 / 0 | 11.17.0 |
| `docker version` | 0 | 1 / 0 / 0 | Client/Engine 29.6.1；Docker Desktop 4.80.0；containerd 2.2.5；runc 1.3.6 |
| `docker compose version` | 0 | 1 / 0 / 0 | Docker Compose v5.3.0 |
| `docker compose config --images` | 0 | 1 / 0 / 0 | PostgreSQL `16.6-alpine`；Redis `7.4-alpine`；三个本地应用镜像 |
| `docker run --rm postgres:16.6-alpine postgres --version` | 0 | 1 / 0 / 0 | PostgreSQL 16.6 |
| `docker run --rm redis:7.4-alpine redis-server --version` | 0 | 1 / 0 / 0 | Redis 7.4.10；jemalloc 5.3.0 |

## R1 验证命令

| 命令 | 退出码 | 通过 / 失败 / 跳过 | 脱敏结果摘要 |
|---|---:|---:|---|
| `git status --short` | 0 | 1 / 0 / 0（命令级） | 18 个已修改路径、5 个未跟踪路径；8 个历史生成文件仍保留，R1 文件可单独识别 |
| `git diff --check` | 0 | 1 / 0 / 0（命令级） | 无 whitespace error；输出仅含 Windows `core.autocrlf` 的 LF→CRLF 提示 |
| `python --version` | 0 | 1 / 0 / 0（命令级） | Python 3.13.13 |
| `node --version` | 0 | 1 / 0 / 0（命令级） | Node v24.18.0 |
| `npm --version` | 0 | 1 / 0 / 0（命令级） | npm 11.17.0 |
| `docker version` | 0 | 1 / 0 / 0（命令级） | Client/Engine 29.6.1；Docker Desktop 4.80.0 |
| `docker compose version` | 0 | 1 / 0 / 0（命令级） | Docker Compose v5.3.0 |

补充执行：

- 命令：`git diff --stat`
- 退出码：`0`
- 通过 / 失败 / 跳过：`1 / 0 / 0`（命令级）
- 摘要：tracked diff 为 18 个文件、907 insertions、519 deletions；其中包含开始前已有的 8 个历史生成文件，未跟踪文件不在该统计内。
- 命令：`python -m unittest discover -s tests -v`
- 退出码：`0`
- 通过 / 失败 / 跳过：`13 / 0 / 0`
- 摘要：R1 产物隔离回归与已有外部配置预检单元测试全部通过；这些本地测试不构成真实平台证据。

## 范围外记录

- `git diff --check` 的 LF→CRLF 提示来自当前 Windows Git 行尾配置，不是 whitespace error；R1 不新增 `.gitattributes` 策略。
- R2～R14 的静态检查、迁移、部署、真实 Provider 与真实 Sandbox 问题均未在 R1 中修改或验收。
