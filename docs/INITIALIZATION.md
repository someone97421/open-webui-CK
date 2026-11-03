# 个人版初始化记录

初始化日期：2026-11-03。范围为工程环境、文档、协作与外联策略；本次不运行构建、测试或服务，不修改数据库、持久化格式及核心聊天/检索逻辑。

## 初始状态与盘点

- 分支 `main`，工作区干净；唯一远端 `origin` 的拉取与推送地址均为 `https://github.com/someone97421/open-webui-CK.git`，无常驻上游远端需要移除。
- `HEAD` 与 `origin/main` 均为 `c38885a1a737da4968f157092f304f3b5481d0bf`，完整历史，非浅克隆；最近提交为上游 0.13.0 合并节点及其修复历史。以初始导入节点建立同步基线，未联网确认上游最新状态。
- 已盘点受版本控制的文档、隐藏工程配置、工作流、脚本与包元数据，并搜索常见 AI 助手配置。没有既存 `AGENTS.md`、`CLAUDE.md`、`GEMINI.md`、Cursor/Windsurf/Copilot 规则；没有独立 ADR、架构提案、治理文档或变更模板，也没有 CODEOWNERS、Renovate、GitLab 或 CircleCI 配置。
- 上游社区资产为行为准则、贡献者协议、安全文档、多语言 README、旧排障和变更历史，以及 `.github` 中的交互模板、Dependabot、赞助和自动化配置。
- 工程命令来自 `package.json`、`pyproject.toml`、`backend/requirements.txt`、Dockerfile、Vite 配置与启动脚本；环境与目录速查统一放在根目录 `AGENTS.md`。现有 Makefile 为旧辅助入口，不作为安装指南。

## 已归档

原文统一移动到 `docs/archive/upstream/`：

- 根目录上游 `README.md` 和全部 `README.*.md`（英文及各语言版本）。
- 上游 `CHANGELOG.md`、`CODE_OF_CONDUCT.md`、`CONTRIBUTOR_LICENSE_AGREEMENT`、`TROUBLESHOOTING.md`。
- `docs/SECURITY.md`。

目录内 `说明.md` 标明“仅作历史参考字典，无需遵守”。根许可证及版权声明不改写；其引用的贡献者协议保留完整原文，并在当前 README 中提供归档链接。

## 已删除

- 社区交互：`.github/ISSUE_TEMPLATE/` 三个文件、`.github/pull_request_template.md`。
- 机器人和赞助：`.github/dependabot.yml`、`.github/FUNDING.yml`、`.github/workflows/issue-label.yaml`。
- 发布与部署：`.github/workflows/release.yml`、`release-pypi.yml`、`docker.yaml`，移除 GitHub Release、PyPI 上传、容器推送与签名、镜像清理、Helm 自动派发等整套发布流程。
- 上游测试编排与失效工作流：`.github/workflows/regression.yaml`、`codespell.disabled`、`lint-backend.disabled`、`lint-frontend.disabled`。
- 社区贡献统计脚本：`contribution_stats.py`。
- 遥测编排：`docker-compose.otel.yaml`。
- 后端版本查询中的上游 HTTP 请求代码；函数新建模板中的默认上游赞助字段；设置界面的上游社交推广入口。

## 已新增或改写

- `AGENTS.md`：统一中文规则、核心底线、开发自由度、定制保留项、七步同步流程和单行环境速查。
- `docs/UPSTREAM_SYNC.md`：初始化“最后正式合入”“最后核对”，建立空白“已吸收改动”“暂缓/不采用”表。
- `README.md`：个人仓库入口和 Windows 本地开发指南；`CHANGELOG.md`：精简个人版记录，保留后端、Docker 和 Python 打包所需的原路径与解析格式。
- `.github/workflows/frontend.yaml`、`backend.yaml`：仅 `workflow_dispatch` 手动触发，分别执行基础前端构建、后端格式与静态错误检查，仓库权限只读，不发布、签名或部署。
- `backend/open_webui/env.py`：固定关闭自动版本检查与 OTEL 开关，在模型/遥测依赖加载前设置第三方禁用变量；不启用全局离线模式，保留正常模型下载。
- `backend/open_webui/main.py`：版本查询保留认证与 `current`、`latest` 字段，直接返回当前版本，无外部版本请求。
- `.env.example`、Dockerfile：补充 Hugging Face 与 OTEL SDK 禁用变量；原有 Scarf、DO_NOT_TRACK 和 Chroma 禁用策略保留，不提供无效的版本检查或 OTEL 环境开关。
- `docker-compose.yaml`、`scripts/generate-sbom.sh`：默认采用 `open-webui-ck:local`，WebUI 服务禁止远端拉取；Ollama、基础镜像及依赖镜像正常保留。
- `pyproject.toml`：增加 `Private :: Do Not Upload`，阻止 PyPI 接收此项目；npm 的 `private: true` 与 Rust 的 `publish = false` 已有，无需改写依赖锁文件。
- 前端关于、管理员设置、连接帮助、更新提示、语言反馈和后端缺失页：反馈/仓库/下载入口指向个人仓库；用户菜单改为个人仓库提交历史；函数新建模板仅调整作者元数据，不改模板业务行为。

## 外联与稳定性边界

| 类别 | 处理与理由 |
| --- | --- |
| 上游 GitHub 最新版本查询 | 关闭环境开关并移除 HTTP 请求；前端按服务端标志跳过检查 |
| OpenTelemetry | 各开关固定关闭，SDK 禁用；删除显式启用的 Compose 文件，不再向用户配置的导出器上报 |
| Chroma 匿名遥测 | 原实现已固定 `anonymized_telemetry=False`，保留 |
| 第三方遥测 | 设置 `SCARF_NO_ANALYTICS=true`、`DO_NOT_TRACK=true`、`ANONYMIZED_TELEMETRY=false`、`HF_HUB_DISABLE_TELEMETRY=1`、`OTEL_SDK_DISABLED=true`；第三方实现未运行验证 |
| 插件市场与资源 | 保留 `openwebui.com` 市场、postMessage 来源校验、模型和依赖下载及 API 服务地址，不做域名全局替换 |
| 本地业务统计 | 保留 analytics、使用量和审计日志的本地数据库与接口 |
| 企业授权与品牌 | `LICENSE_KEY` 非空时的许可证校验、`CUSTOM_NAME` 非空时的品牌资源拉取仍保留；默认不触发，属于显式配置功能，不是遥测 |
| 版权、许可与帮助资源 | 保留原作者、品牌、第三方许可证、法律文档和集成参考链接；User-Agent/HTTP-Referer 中的来源标识不等于对上游上报 |

**行为变化**：版本检查和 OTEL 导出现在不能通过环境变量重新启用；WebUI 容器需先构建本地镜像；社区交互与公共发布自动化已删除。以上均为本次明确要求的工程调整。核心业务代码、数据库结构、持久化数据格式、API 路径与响应字段未变更。

## 验证范围

仅做差异与直接关联代码的静态审阅、归档一致性核对、编码/冲突残留/敏感配置检查及 Git 状态核对。不安装依赖、不运行构建或测试、不启动服务；运行期兼容性未执行验证。本次不推送远端。
