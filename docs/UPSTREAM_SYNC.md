# 上游同步追踪

## 当前状态

- 个人仓库：`https://github.com/someone97421/open-webui-CK.git`，唯一远端 `origin`；当前分支 `main`。
- 上游临时地址：`https://github.com/open-webui/open-webui.git`，目标分支 `main`；不配置常驻上游远端。
- 初始分叉基线：`c38885a1a737da4968f157092f304f3b5481d0bf`（0.13.0）；最后正式合入：`0666e59d26a4d056e0bacee41742486badd71cf8`（0.13.4）。
- 最后核对目标：`0666e59d26a4d056e0bacee41742486badd71cf8`（0.13.4）。
- 本轮合并前 HEAD：`6936da1e7536e3d9e4a07e1bcb7bacec3a6ab39f`；合并基点：`b0e6098e940942281d9c83f3529ea117287a3a22`（上次正式合入）；上游独有 330 个提交。
- 本轮真实合并节点：以随后文档提交补录。

## 2026-11-23 吸收与适配（0.13.4）

| 范围 | 吸收与本地适配 |
| --- | --- |
| 标签页与侧边对话 | 页面（笔记、频道、工作区、自动化、日历、游乐场、主页）以标签页打开；侧边对话改为复用主 Chat。本地会话模型／参数／附件覆盖／输入开关的保存恢复移入 `Chat.svelte` 与 `Tabs/ChatTab.svelte`，删除 `ChatTabs/SideChat.svelte`；工作区页面逻辑移入 `workspace/*/Create*`、`Edit*` 组件，路由改为薄封装 |
| 文件夹 | 聊天看板、自定义状态、标签颜色、文件夹自动化与知识区、普通文件夹分享；项目文件夹保留归档只读、归属、AGENTS.md、默认 Skill／工具／模型与工作区删除流程，后端状态接口拒绝已归档项目 |
| Terminal | 吸收 Terminals 0.4.0 模板编排（`template:` 终端、实例管理）、Files 路径跳转与 Markdown 大纲、终端标签命名；所有 Open Terminal 请求仍经 `terminal_identity_headers` 签名和项目绑定校验；旧 Terminal contexts 随上游删除 |
| 生成与工具 | 多图像连接、视频生成、可视化内置工具（默认关闭）、`+` 菜单按来源分组、失败工具调用标签、超时工具错误说明 |
| 性能与修复 | 长代码块流式卡顿、PDF 大文件预览、Redis 模型列表、头像与知识库导出、压缩摘要保持、vLLM/Ollama 工具调用、OAuth 会话保持、MCP 大响应等 |
| 管理与构建 | 管理员设置保存前改动确认（含站点名与 LOGO）；Docker 依赖改用带哈希的 `backend/requirements*.lock`，改 `requirements.txt` 后须运行 `backend/update-locks.sh`；版本 0.13.4；CI 保持本地手动静态检查，CHANGELOG 保持个人版格式 |
| 本地修复 | 补上 `middleware.py` 中 `current_usage` 的外层绑定（上次提交 `6936da1e7` 因 `nonlocal` 无绑定导致后端无法加载） |

## 2026-11-14 吸收与适配

来源均为目标 `b0e6098e940942281d9c83f3529ea117287a3a22` 相对上述基点的增量，合并前已逐项评估。

| 范围 | 吸收与本地适配 |
| --- | --- |
| 聊天面板与文件 | 多分组标签、文件树与 Git 展示、Excel/Markdown 编辑预览、语音笔记、快捷打开；保留工具文件正文交付、图片预览、HTML 与 Range 代理身份；保存/上传前固定真实聊天 ID，并校验账号、聊天和连接未变化 |
| 聊天工作视图 | 按用户＋聊天私有保存面板状态，保留项目归属和共享会话访问边界；删除聊天时同步清理视图 |
| 工具与历史 | 合并工具调用批次、隐藏工具结果缓存、Skill 预加载、压缩与工具检索修复；原生 Messages 按本次隐藏预加载调用 ID 转为内部用户上下文，避免无签名工具回放关闭首轮思考；保留 Anthropic 思考签名、Responses 加密推理回传及 raw 历史工具配对 |
| 附件与检索 | 吸收全文阈值、解析器和检索兼容修复；旧模型未显式设置 file_context 时继续预加载附件；保留 RAG_TOP_K/RERANKER=3、CHUNK_SIZE=1000，示例配置同步；已保存设置优先 |
| 工具权限 | 吸收 Auto 审批与引擎配置，默认关闭；原手动/完整权限模式继续可用，未启用评分接口，不新增默认外发 |
| Terminal | 系统信息、前台进程、WebGL 终端与输出流控、Git issue/PR 搜索、流式上传与连接中断处理；保留 v2 按次签名、管理员声明、真实 chat_id 首包、只读依赖与项目工作区调度 |
| 通知与常规修复 | 通知音效、通知跳转、频道索引/消息优化、模型缓存、后台任务和检索修复；桌面已有查询、截图附件、通话事件继续保留 |
| 构建与仓库身份 | 版本升至 0.13.3；吸收前端安装跳过 CUDA 二进制等修复，保留个人 README、关闭版本检查/遥测策略、本地镜像和个人手动 Docker Hub 发布；不引入上游通用发布流程 |

## 暂缓及兼容策略

**以下来源已进入祖先链。Git 不会自动重新引入主动排除的代码，后续同步必须按来源和路径人工复查。**

| 来源完整哈希 | 功能与路径 | 原因、复查条件 |
| --- | --- | --- |
| 初始入口 `6ef26be296c80afe695fe3871b025384dd507102`，最终状态 `0666e59d26a4d056e0bacee41742486badd71cf8` | `backend/open_webui/utils/agents/`（含新增 `session.py`）；`main.py` 模型发现和聊天分发；`routers/audio/realtime.py`、`routers/automations.py` `/models`、`utils/automations.py` 终端校验与初始目录；`routers/chats.py` `ensure_chat_selections`；前端自动化编辑页编码代理模型与 Terminal 选择 | 编码代理未完成本地 workspace_worker、owner＋project 与签名身份适配，不提供入口；`folderStates.ts` 的代理模型发现函数保留但后端 `/api/models` 不处理 terminal 参数，返回为空。待凭据、续聊、附件、取消和项目删除清理纳入统一工作区网关后复查 |
| 初始入口 `404d27a36eed45359a56082500b8970ba6ad58aa`，最终状态 `0666e59d26a4d056e0bacee41742486badd71cf8` | `utils/tether.py`、`routers/tether.py`、`routers/sessions.py`、新增 `utils/mcp/tether.py`；`src/lib/utils/tether.ts`、设备授权页面 | 不注册路由。上游调用点（`openai.py` Tether 模型、`tools.py` Tether 工具服务器、`tasks.py`/`actions.py` `add_tether_model`、`mcp/client.py`）保留，由 `utils/terminal_client.py` 空实现兜底（无连接、`RelayClient` 不可达）。上游 0.13.4 同时移除了用户直连（Direct Connections），本地跟随移除，用户自建模型／工具服务器／终端需改由管理员配置。待明确设备接入需求后复查 |
| `0666e59d26a4d056e0bacee41742486badd71cf8`（“Queued messages steer replies”） | `main.py` `queue_user_message` 分支；`middleware.py` 工具循环和 `background_tasks_handler` 的 `has_queued_message` 分支；前端 `res.queued` 与服务端 pending 列表 | 与本地 `task_inputs` 逐条排队、补充输入及交付确认冲突，保留本地实现；`subagents.py` 中上游排队函数保留未调用。复查条件：评估是否以上游服务端排队替换本地实现 |
| `0666e59d26a4d056e0bacee41742486badd71cf8` | `utils/terminals.py` `get_folder_terminal_defaults`、`initialize_terminal_directory`；`main.py` 新会话文件夹默认终端与初始目录 | 与项目工作区 cwd 管理冲突，继续不接入；普通文件夹的默认终端设置仅前端保存。待项目与普通文件夹终端策略统一后复查 |
| `6f4c7f893580f29dd56d05201e9a73bbd7535cc8`，最终状态 `b0e6098e940942281d9c83f3529ea117287a3a22` | `backend/open_webui/utils/tool_permissions.py`、`config.py`、管理员聊天设置 | 代码已吸收，Auto 审批保持关闭；评分模式会发送工具参数与近期用户消息，需用户主动配置和开启后才使用。下次复查默认值及历史兼容 |
| `b0e6098e940942281d9c83f3529ea117287a3a22` | `utils/tools.py`、`config.py`、`.env.example`、`Models/Capabilities.svelte` | 不采用上游旧模型默认关闭附件预加载及 RAG 10/1024 的默认行为；保留本地兼容默认，待明确调整需求或所有模型已显式配置后复查 |
| `b0e6098e940942281d9c83f3529ea117287a3a22` | `.github/workflows/docker.yaml`、`issue-label.yaml`、`release*.yml` | 不采用上游发布与社区流程；保留个人现有 docker-publish.yml 与手动基础验证，不触发 CI |

## 数据迁移与部署影响

0.13.3 新增 Alembic 链为 `8bc7e5a902d1`（auth_session）→ `6a23bd107e54`（chat_view_state）→ `9f6c2a8d1b43`（频道查找索引），前序为 `e42c8f710a36`；auth_session 表保留但暂不由设备授权入口写入。Terminal 普通 pip 安装的 Notebook 依赖改为 notebooks extra，详见 Terminal 仓库同步记录。

0.13.4 上游没有新增 Alembic 迁移；文件夹聊天状态等新数据写入现有 JSON 字段。首次启动 0.13.4 会把旧图像生成环境变量配置转换为图像连接，此后 `IMAGE_GENERATION_ENGINE` 等环境变量不再读取（`ENABLE_PERSISTENT_CONFIG` 关闭时除外）。

本轮没有启动后端或执行迁移。升级前停止写入并备份数据库及持久化数据卷；回退时恢复升级前备份后启动旧镜像，不把仅回退镜像当作数据库回退。新迁移及运行行为尚未实机验证。

## 实际验证

- 冲突索引为空；暂存区 `git diff --check` 通过。
- 后端：全部 Python 文件 `compile()`（本机 3.9 不支持 `match` 语法的两个上游文件除外）；`ruff` F821/F823/F811 检查；自写脚本核对 `open_webui.*` 内部导入名均存在。
- 前端：冲突标记、UTF-8/LF、`$lib` 与相对导入路径及命名导出核对；子代理做了 Svelte 结构与脚本语法检查。
- 独立静态审查覆盖中间件重试、终端身份、侧边对话与排队定制。
- 未执行测试、构建、svelte-check、服务、依赖安装、数据库迁移、CI 或镜像构建。

## 同步历史

| 日期 | 上游目标完整哈希 | 方式 | 本地节点与核验 |
| --- | --- | --- | --- |
| 2026-11-03 | `c38885a1a737da4968f157092f304f3b5481d0bf` | 初始分叉导入 | 基线，无个人同步合并节点 |
| 2026-11-14 | `b0e6098e940942281d9c83f3529ea117287a3a22` | 非快进真实合并 | `9d8b8ef11c8b4edbac8d99463c0fc69367db5022`；双父节点与目标祖先关系核验通过 |
| 2026-11-23 | `0666e59d26a4d056e0bacee41742486badd71cf8` | 非快进真实合并 | 合并节点以随后文档提交补录 |

遵循根目录 `AGENTS.md` 的固定同步流程。只有真实合并完成才更新最后正式合入；合并节点以随后文档提交补录，避免自引用。
