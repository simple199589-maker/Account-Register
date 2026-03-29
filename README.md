# GPT-Account-Register

ChatGPT 批量注册工具，包含：

- `register_all.py`：注册主脚本
- `server.py`：Web 管理端
- `config.example.json`：可提交的示例配置模板
- `config.json`：本地实际配置，不提交到 Git

## Docker 部署

项目已经整理为单容器运行模式，默认启动 Web 管理端，端口为 `18421`。

首次启动会自动完成这些事情：

- 创建宿主机目录 `docker-data/`
- 自动复制 `config.example.json` 为 `docker-data/config.json`
- 将账号结果、代理文件、Token 文件统一持久化到 `docker-data/`

启动方式：

```powershell
docker compose up --build -d
```

查看日志：

```powershell
docker compose logs -f
```

停止服务：

```powershell
docker compose down
```

启动后访问：

```text
http://localhost:18421
```

如果你想改宿主机端口，可以临时指定环境变量：

```powershell
$env:APP_PORT=28080
docker compose up --build -d
```

这时访问地址为 `http://localhost:28080`。

容器内默认仍使用项目原有路径结构，但运行时文件都会通过入口脚本映射到 `docker-data/`，因此适合直接推送源码到 GitHub，而不会把本地敏感配置和运行产物一起提交。

## 配置方式

先复制一份本地配置：

```powershell
Copy-Item config.example.json config.json
```

然后至少补齐这些字段：

- `duckmail_bearer`
- `sub2api_email`、`sub2api_password`（如果要启用 Sub2Api）

配置加载顺序如下：

1. `config.example.json`
2. `config.json`
3. 环境变量

## Python 环境

当前项目按 `pyenv` 使用方式收敛到 Python `3.13.11`：

```powershell
pyenv install 3.13.11
pyenv local 3.13.11
python -m ensurepip --upgrade
python -m pip install -e .
```

代码扫描得到的实际运行时第三方依赖为：

- `curl-cffi`
- `fastapi`
- `pydantic`
- `uvicorn`

## 启动

```powershell
python register_all.py
```

启动 Web 管理端：

```powershell
python server.py
```

如果容器已经启动，也可以进入容器手动执行注册脚本：

```powershell
docker compose exec app python register_all.py
```
