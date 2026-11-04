# Open Terminal 会话工作区接入

本功能需要同时部署本仓库和 `open-terminal-ck` 的对应改动。WebUI 负责确认用户及会话归属，Terminal 负责将文件操作、命令、notebook、HTTP/端口代理和终端 WebSocket 路由到独立工作进程。

## 会话与文件

普通聊天在第一次访问终端工作区时，先调用现有 `/api/v1/chats/new` 创建空会话。上传、文件面板、终端和首条消息沿用该 ID，不在发送首条消息后改名或迁移目录。多文件并发上传共用同一个会话创建过程。

临时聊天保留 `temporary:<socket_id>:<uuid>` 身份。访问工作区前调用 `/api/v1/terminals/chats/prepare`，由后端验证已登录用户及实时连接并登记临时归属；不会因此成为普通持久化聊天。临时归属过期后拒绝访问，不回退默认空间。

WebUI 后端对每个带会话身份的终端请求重新查验写权限。原生 Bearer 终端连接通过现有 API Key 签发有效期最多 300 秒的 HMAC 工作区上下文，覆盖上传下载、模型工具、HTTP 和 WebSocket 代理。模型工具每次执行重新签名，审批等待或长对话不会复用已过期的签名。API Key 与签名不交给浏览器或模型。

Terminal 按 `/workspaces/<SHA256(user_id)>/<SHA256(chat_id)>/` 保留文件。不同用户、不同会话使用不同目录和进程；回到原会话使用原目录。共享聊天中各用户也拥有各自的工作区。Fork/Clone 使用新会话 ID，因此不会自动复制原会话的磁盘文件；历史中的终端文件引用需要在新会话重新上传。

## 部署

在 Terminal 服务端设置：

```dotenv
OPEN_TERMINAL_WORKSPACE_ISOLATION=true
OPEN_TERMINAL_WORKSPACE_ROOT=/workspaces
```

为 `/workspaces` 挂载持久卷；WebUI 管理员终端连接使用该服务地址、Bearer 认证和与 `OPEN_TERMINAL_API_KEY` 相同的 Key。使用 WebUI 后端代理连接；个人浏览器直连无法签发可信会话身份。无需在 WebUI 增加密钥或额外签名开关。

所有人共享镜像内只读的系统工具和依赖。额外共享虚拟环境通过 Terminal 的 `OPEN_TERMINAL_WORKSPACE_RUNTIME_PATHS` 配置，其 `bin` 会加入工作区 PATH；共享依赖由管理员统一安装，工作区自行安装的依赖只属于当前工作区。Python 解释器及项目包必须安装在沙箱可见的共享运行时中。

Terminal 需要 Linux 和可用的 bubblewrap/user namespace。隔离模式默认不提供外网；`OPEN_TERMINAL_WORKSPACE_NETWORK=shared` 可复用外网，但会放开工作区之间的网络可达性，应根据实际部署选择。隔离模式当前关闭 browser/desktop；不修改旧单用户或用户级模式的开关。

已有共享目录不会自动迁移。先备份旧卷，再按真实用户和会话分配到对应目录，不能从旧文件路径猜测归属。Terminal 仓库的 `docs/WORKSPACE_IMAGE_CONTEXT.md` 记录了目录、运行时、迁移和协议细节。

## 验收范围

此次只做源码静态审查、语法与差异检查，未启动服务、运行测试、CI 或构建镜像。部署后仍需验证：首条消息前多文件上传、临时聊天上传、两用户各两会话互相不可见、回到原会话及服务重启后文件恢复、终端 WebSocket 和 notebook 使用同一目录、长时间等待后的工具调用，以及共享依赖可用且不能被工作区改写。
