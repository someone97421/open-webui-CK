# Chat 与项目工作区

侧栏的“新建 Chat”创建独立聊天，“新建项目”创建绑定一个 Open Terminal 的项目。普通账号的项目与工作区按账号隔离，所属账号可以自行访问、编辑、归档和删除，删除无需管理员同意；管理员保留跨账号管理权限。同一账号在同一项目内的聊天共享文件和项目指令；不同项目保持隔离。原有普通分组的共享功能保留，不自动升级为项目。

侧栏的“会话、分组、项目”三个板块整体按最近活动时间降序排列；分组和项目计入内部未归档对话的更新时间及自身创建时间，展开、折叠和自动整理不影响排序。普通置顶会话计入“会话”，置顶的分组/项目会话按原归属计算；时间相同保持“会话、分组、项目”的顺序。已归档项目仍收纳在“项目”板块内。会话内容最多占半屏并独立滚动，避免无限加载挡住后续板块。

## 普通 Chat

普通 Chat 默认启用 Pyodide 代码解释器，仍遵守管理员开关、用户权限和模型能力。聊天模式使用 Pyodide，不使用全局 Jupyter 配置。普通聊天不再绑定 Terminal；旧消息和文件引用保留，旧 Terminal 工作区的磁盘内容不自动搬入浏览器。

浏览器运行环境按 `(user_id, chat_id)` 分配 scope；不同聊天不共用 Python 内存或 `/mnt`。启用文件持久化后，IDBFS 挂载在 `/.chat-workspaces/<编码后的用户>/<编码后的聊天>`，通过 `/mnt` 访问。切换聊天会重建运行环境；包下载仍使用浏览器缓存，Python 变量不跨聊天保留。运行中的请求捕获原 scope，后台返回不修改当前聊天的文件面板。

上传或首次执行前应使用最终聊天 ID。新聊天经现有 `/api/v1/chats/new` 预建，后续首条消息沿用该 ID。临时聊天不使用持久化文件；未落库草稿只使用内存 scope。旧版全站共享的 `/mnt` 数据不自动归入任何聊天，避免猜测文件归属。

这属于浏览器应用内的运行环境与文件命名空间隔离。启用 IDBFS 的 Worker 与页面使用同源存储，具备任意 JavaScript 能力的代码仍可访问同源浏览器资源；它不提供 Terminal 的 Linux 沙箱边界，也不把模块导入限制视为安全沙箱。

## 项目

项目复用文件夹记录，配置为：

```json
{"data":{"project":{"version":1,"terminal_id":"连接 ID","archived":false}}}
```

项目必须位于顶层，不能包含子文件夹。已有非空文件夹不能直接升级。项目聊天不能临时运行，依赖临时会话的 Side chat 入口在项目中关闭；需要并行讨论时在同项目内新建 Chat。聊天不能从普通区移动到项目，不能跨项目移动；Fork/Clone 留在原项目中，因此沿用原项目的磁盘文件。普通聊天 Fork/Clone 仍使用新的独立 scope。

WebUI 服务端从已保存聊天的数据库 `folder_id` 解析项目归属，校验所属账号或管理员身份、归档状态和 Terminal 访问权限，再固定使用项目连接并关闭代码解释器。客户端传入的 `terminal_id` 不能覆盖项目绑定。有聊天的项目不能更换 Terminal 或撤销项目配置。项目与项目会话不支持向其他普通账号共享；共享授权不能绕过归属检查，已有分享链接不能向其他普通账号提供项目会话。

项目支持归档、恢复和删除。归档保留会话与文件；所属账号可自行删除，无需审批，不依赖通用 `chat.delete` 或普通分组功能权限，管理员也可管理和删除。删除会永久清理该项目的全部会话、派生内部聊天及专属 Terminal 工作区，强制 `delete_contents=true`，不会把项目会话搬到普通聊天区；单独删除聊天仍不清理项目磁盘。项目导入与共享快照跨工作区克隆首版返回 409，不自动迁移文件。

删除前会确认 Terminal 的 `workspace_context.operations` 包含 `delete`，随后持久设置可选的 `data.project.deleting=true`，阻止新执行与新聊天进入。旧项目缺少该字段时行为不变，无需数据库迁移。清理任务和磁盘成功后才在单次事务内删除 WebUI 记录；失败时保留待删除项目，可从同一删除入口重试，已经清理的文件无法恢复。仅失去 Terminal 使用授权不妨碍项目所属账号清理原工作区，但原连接配置必须保留且 Terminal 可达。两端均须升级；旧 Terminal 不支持时返回明确错误，不删除项目记录。

### 项目 AGENTS.md

项目主页只展示会话，`AGENTS.md` 的入口位于项目编辑的高级设置。展开后通过以下接口直接读写工作区根目录的文件：

- `GET /api/v1/terminals/projects/{project_id}/agents`
- `PUT /api/v1/terminals/projects/{project_id}/agents`，请求为 `{"content":"..."}`。

两个接口响应均含 `content` 和 `exists`。缺失文件返回 `{"content":"","exists":false}`，编辑器置灰，由用户手动创建；已有空文件的 `exists` 为 `true`。创建空文件也会实际保存，不自动为新项目创建文件。工作区不可用属于加载错误，不当作文件缺失；普通项目设置仍可独立保存。

文本上限为 32 KiB，仅允许项目所属账号或管理员访问；归档项目可查看，恢复后才能创建或保存。每轮模型请求重新读取同一个文件；不复制到文件夹 `system_prompt`。同一项目内的聊天共享此文件，保存后下轮对话生效。

## Terminal 部署与协议

需要同时升级 WebUI 和 `open-terminal-ck`。项目仅支持管理员配置的 Bearer 直连 Open Terminal，不支持个人浏览器直连或 orchestrator。项目创建、绑定和实际请求都会验证 `/api/config` 中的 `workspace_isolation`、`project_workspaces`、v2 协议和 project scope，旧服务返回明确的 409。

Terminal 配置：

```dotenv
OPEN_TERMINAL_WORKSPACE_ISOLATION=true
OPEN_TERMINAL_WORKSPACE_ROOT=/workspaces
```

为 `/workspaces` 挂载持久卷。WebUI 连接 Key 与现有 `OPEN_TERMINAL_API_KEY` 一致，无需增加密钥。依赖使用镜像内只读的系统目录；额外共享虚拟环境通过 `OPEN_TERMINAL_WORKSPACE_RUNTIME_PATHS` 配置，项目自行安装的依赖只保留在自己的目录。

项目目录为 `/workspaces/<SHA256(project_owner)>/project-<SHA256(project_id)>/`。同一账号的同项目聊天复用一个工作进程、同一目录；终端 shell、notebook 和请求的 `X-Session-Id` 仍使用真实聊天 ID，防止不同聊天混用实时会话。

WebUI 对每次上传下载、工具调用、HTTP/WS 代理重新校验归属或管理员身份，并签发最长 300 秒的 HMAC。v2 签名包含真实操作者 `user`、真实 `chat`、`scope_type: project`、`scope_id` 和项目实际所有者 `owner`，签名前缀为 `open-terminal/workspace/v2`；管理员请求额外签入 `admin:true`。Terminal 要求普通账号 `user == owner`，仅接受验签后的管理员声明跨账号管理；目录始终按实际 `owner` 定位。服务端项目设置使用受限的 `project:<id>` 上下文，仅用于读写指令。浏览器和模型不能自行选择此上下文或声明管理员身份。

v1 的用户＋聊天签名与 `/workspaces/<SHA256(user)>/<SHA256(chat)>/` 路径继续兼容。旧工作区数据保留，不自动搬迁。其他非聊天入口沿用各自的原有连接配置。

Terminal 需要 Linux、bubblewrap 和允许 user namespace 的容器策略。隔离模式默认不提供外网；`OPEN_TERMINAL_WORKSPACE_NETWORK=shared` 可联网，但同时放开网络互达。隔离模式关闭 browser/desktop。详细部署、共享依赖与图片行为见 Terminal 仓库的 `docs/WORKSPACE_IMAGE_CONTEXT.md`。

### NAS 上的 namespace 权限失败

若 Terminal 日志出现 `bwrap: No permissions to create a new namespace`，同时 `/api/config` 返回 200、`/files/cwd`、文件列表及执行接口返回 503，说明请求已到达 Terminal，但宿主拒绝启动工作区。能力声明不等于工作进程已成功启动，修改连接 Key 或重复创建项目不能解决此故障。

先在 NAS 上检查：

```bash
uname -r
sysctl user.max_user_namespaces
sysctl kernel.unprivileged_userns_clone
docker inspect open-terminal --format '{{json .HostConfig.SecurityOpt}}'
docker exec open-terminal bwrap --unshare-user --ro-bind / / /bin/true
```

部分内核没有 `kernel.unprivileged_userns_clone` 这一开关，单独缺少该项不能证明不支持 user namespace。还需结合宿主内核配置、AppArmor 拒绝记录和 bubblewrap 输出判断。

在 NAS 的 Linux 6.12.30+、Docker 26.1.0、Compose v2.26.1 上，独立探测已确认仅解除 seccomp/AppArmor 仍会因 `/proc` 挂载被拒而失败。以下组合已在同镜像、UID/GID 1000:1000、无宿主挂载和生产凭据的一次性容器中验证，可启动实际工作进程并完成临时文件写入、列目录及 Python 命令执行：

```yaml
security_opt:
  - seccomp=unconfined
  - apparmor=unconfined
  - systempaths=unconfined
```

这会放宽外层容器的 seccomp/AppArmor 策略并取消默认系统路径遮罩、只读限制，不修改 Key、项目目录或应用内工作区隔离，也未使用 `privileged` 或 `SYS_ADMIN`。这是已探测组合中的可运行配置，不等于最精细的权限规则；缺少内核 user namespace 能力时仍不能靠这些选项补足。

该 NAS 的 Compose 已验证正确应用第三项。它可能不保留在 `SecurityOpt` 数组中，应检查实际的 `MaskedPaths=[]`、`ReadonlyPaths=[]`。旧镜像读取文本时暴露了图片识别的 `KeyError: 'MPO'`，源码已修复，尚待新镜像复测；不能把工作进程启动成功等同于全部文件工具恢复。生产项目身份签发、网关转发、项目子目录和 WebSocket 仍需验收。

启动失败会保留 Terminal 的原始诊断日志，并返回可读的工作区错误；项目 AGENTS.md 接口保留上游的 503 状态。

## 验证范围

本次只进行源码静态审核、Python AST / Svelte / TypeScript 语法、UTF-8 与差异检查。未运行测试、服务、CI、构建或镜像构建。

部署后仍需实测：普通聊天首次上传与回访恢复、临时聊天不持久化、切换聊天期间后台执行、同项目多聊天共享文件、不同项目隔离、项目协作者权限、AGENTS.md 修改后下轮加载、归档恢复，以及目标宿主的 bubblewrap 能力。

## 对话中的文件链接

聊天正文中的 `/mnt/...`、常见工作区绝对路径、相对文件路径、旧 `sandbox:` / `file:` 引用，以及本站 WebUI 文件与 Terminal 文件 API 链接，会打开文件预览弹窗，可直接下载。普通网页链接仍按原方式打开。链接只引用实际存在的文件，不会把远程模型服务的沙箱文件自动搬到本机。

普通 Chat 按消息的聊天 ID 读取对应 Pyodide scope；相对文件路径以 `/mnt/uploads/` 为基准。项目按项目绑定的 Terminal 解析路径，相对路径使用该聊天的工作目录。显式 Terminal 链接保留自身的连接和聊天 ID；每次访问仍由后端检查权限和项目绑定。旧文件卡片无需当前选中相同 Terminal 即可预览下载。

Pyodide 文件初始只在当前浏览器。在预览中点击“保存到文件库并复制链接”，会通过原有文件上传接口保存原文件（不做知识提取），然后复制 WebUI 文件地址；其他设备登录有权限的账号后可打开。文件库链接和管理员 Terminal 代理链接也可从预览中复制。链接不携带 JWT 或 Terminal 密钥，沿用现有登录与文件权限；不提供匿名公开分享。

管理员 Terminal 的 HTML 预览始终使用带聊天 ID 的代理路径，避免 iframe 无法传会话请求头。文件代理转发 Range / If-Range，保留分段响应能力。缺失文件、连接不可用、读取或复制失败通过 toast 提示；不再把本地路径作为 WebUI 网页导航。

本轮仅静态核验；正文链接、跨设备保存与复制、HTML 相对资源及媒体分段读取仍需部署后实测。

## 回复中的文件附件

模型调用 `display_file` 后，文件默认直接出现在回复里。图片自动展开预览；PDF、表格、文档、压缩包等显示文件卡片，点击名称可展开受支持的预览，下载按钮始终保留。同一回复重复展示相同连接、聊天、路径和页码时只显示一张卡片。历史结构化结果中的侧栏文件引用也会显示为附件，不需要重新生成文件。

个人界面的“终端文件显示”默认是“附件”。“侧边栏”会额外打开右侧文件查看器，“内联”会直接展开完整文件预览；已保存的侧栏或内联偏好继续有效。工具显式传入 `inline=true` 时仍展开完整预览。

工具回执的 `attached=true` 与兼容字段 `displayed=true` 表示附件已交给消息展示链路，不是浏览器加载完成的确认。回执会说明无需重复调用或解释渲染状态。原生工具与审批续聊复用持久化的 `function_call_output`；旧式工具调用通过消息的 `files` 事件保存文件引用，不额外把预览原图送入模型输入。

附件保存的是原文件引用，不自动复制到 WebUI 文件库，不在聊天历史中保存文件二进制。Terminal 文件仍通过所属聊天的授权代理读取，同账号其他设备可在对应连接可用时查看；原文件被删除或项目工作区被清理后，附件也会失效。需要独立保存时，继续使用文件库功能。普通 Chat 的 Pyodide 文件仍保留原有浏览器本地边界，不因附件展示自动上传。

本轮仅静态检查；部署后需确认图片展示、附件下载、历史恢复、重复展示去重、直连 Terminal、显式侧栏偏好和跨聊天切换。
