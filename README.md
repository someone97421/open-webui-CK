# Open WebUI CK

本项目是基于 Open WebUI 的非官方 Fork，由个人独立维护，不代表 Open WebUI 官方，也不构成官方背书。个人仓库、反馈和源码下载入口：[someone97421/open-webui-CK](https://github.com/someone97421/open-webui-CK)。不向上游贡献，不使用上游公开包或容器替代本地定制构建。

开发规则与完整环境速查见 [AGENTS.md](AGENTS.md)，上游同步基线与追踪表见 [docs/UPSTREAM_SYNC.md](docs/UPSTREAM_SYNC.md)，初始化盘点与清理记录见 [docs/INITIALIZATION.md](docs/INITIALIZATION.md)。上游旧文档已归档到 [docs/archive/upstream/](docs/archive/upstream/说明.md)，仅作历史参考字典，无需遵守其中的社区流程。

## 本地开发

使用 Node.js 22 / npm 和 Python 3.12（支持 3.11–3.12）。以下是 Windows PowerShell 命令，安装后在两个独立可见终端运行前后端。

```powershell
npm ci --force
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
Copy-Item .env.example .env
```

编辑 `.env` 中的本地连接信息；已有 `.env` 时保留原文件，不重复复制。

前端终端，在仓库根目录执行：

```powershell
npm run dev
```

后端终端，从仓库根目录进入后端：

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn open_webui.main:app --host 127.0.0.1 --port 8080 --reload
```

前端默认端口 5173，代理后端 8080；自定义后端地址用 `WEBUI_BACKEND_URL`。Shell 脚本在 WSL 中运行。

## 本地构建

- 前端：`npm run build`，先校验加密 WASM 并准备 Pyodide，产物在 `build/`。
- 容器：`docker build -t open-webui-ck:local .` 或 `docker compose build open-webui`。Compose 使用本地镜像，启动前须完成构建。
- 数据：`backend/data/` 或 Docker 的 `open-webui` 卷；更换环境前备份，勿提交私人数据与 `.env`。
- 验证：默认按需手动执行；GitHub Actions 仅保留手动触发的基础验证，不发布包或镜像。

自动版本检查及对外遥测已禁用，插件市场、模型资源下载与本地业务统计保留。可选企业许可证校验仍按原有显式配置运行，详见初始化记录。

## 许可

保留 Open WebUI 的原始版权声明、[LICENSE](LICENSE)、[LICENSE_HISTORY](LICENSE_HISTORY)、[LICENSE_NOTICE](LICENSE_NOTICE) 和资源内第三方许可；使用、修改及分发须遵守对应许可证。根许可证提及的上游贡献者协议原文见 [历史归档](docs/archive/upstream/CONTRIBUTOR_LICENSE_AGREEMENT)；当前开发遵循本仓库规则。
