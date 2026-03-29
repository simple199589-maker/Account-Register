# GPT-Account-Register

ChatGPT 批量注册工具，包含：

- `register_all.py`：注册主脚本
- `server.py`：Web 管理端
- `config.example.json`：可提交的示例配置模板
- `config.json`：本地实际配置，不提交到 Git

## Docker 使用

项目已经整理为单容器运行模式，默认启动 Web 管理端，端口为 `18421`。

首次启动会自动完成这些事情：

- 创建宿主机目录 `docker-data/`
- 自动复制 `config.example.json` 为 `docker-data/config.json`
- 将账号结果、代理文件、Token 文件统一持久化到 `docker-data/`

方式一：本地构建运行

```powershell
docker compose up --build -d
```

方式二：直接使用镜像运行

```bash
docker run -d \
  --name account-register \
  --restart unless-stopped \
  -p 18421:18421 \
  -v /path/to/docker-data:/app/data \
  ghcr.io/simple199589-maker/account-register:latest
```

查看日志：

```powershell
docker compose logs -f
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

## 挂载说明

运行容器时，只需要把宿主机目录挂载到容器内的 `/app/data`：

```bash
-v /path/to/docker-data:/app/data
```

例如：

```bash
docker run -d \
  --name account-register \
  --restart unless-stopped \
  -p 18421:18421 \
  -v /path/to/docker-data:/app/data \
  ghcr.io/simple199589-maker/account-register:latest
```

首次启动后，容器会在挂载目录中自动生成并维护这些文件：

- `config.json`
- `registered_accounts.txt`
- `stable_proxy.txt`
- `ak.txt`
- `rk.txt`
- `codex_tokens/`

你后续主要维护挂载目录里的 `config.json` 即可。

建议：

- 不要把真实配置提交到 Git
- 只修改挂载目录中的 `config.json`
- 容器重建时继续使用同一个挂载目录

## 配置注意事项

配置加载顺序如下：

1. `config.example.json`
2. `config.json`
3. 环境变量

至少需要关注这些字段：

- `duckmail_bearer`
- `sub2api_email`
- `sub2api_password`

修改 `config.json` 后，建议重启容器使配置生效：

```bash
docker restart account-register
```

如果你使用 `docker compose` 运行，则执行：

```bash
docker compose restart app
```

更新镜像或重建容器时，不需要重建挂载目录；只要继续挂载同一个 `/app/data`，原来的 `config.json` 和运行数据都会保留。

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
