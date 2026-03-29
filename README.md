# GPT-Account-Register

ChatGPT 批量注册工具，包含：

- `register_all.py`：注册主脚本
- `server.py`：Web 管理端
- `config.example.json`：可提交的示例配置模板
- `config.json`：本地实际配置，不提交到 Git

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
