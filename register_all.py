"""
ChatGPT 批量自动注册工具 (并发版) - 邮件 API 版
依赖: pip install curl_cffi
功能: 使用邮件 API 创建邮箱，并发自动注册 ChatGPT 账号，自动获取 OTP 验证码
"""

import os
import re
import uuid
import json
import random
import string
import time
import sys
import threading
import traceback
import base64
from datetime import datetime, timezone
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import parse_qs, urlparse

from curl_cffi import requests as curl_requests
from mail_service import DuckMailClient, MailApiConfig, mail_message_id_set
from oauth_service import CodexOAuthClient, CodexOAuthConfig, OAuthPhoneRequiredError
from sub2api_uploader import Sub2ApiConfig, Sub2ApiUploader

# ================= 加载配置 =================
def _load_json_file(path: str):
    """读取 JSON 文件，不存在时返回空字典。AI by zb"""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"⚠️ 加载 {os.path.basename(path)} 失败: {e}")
        return {}


def _load_config():
    """从示例配置、本地配置和环境变量加载配置。AI by zb"""
    config = {
        "total_accounts": 3,
        "duckmail_api_base": "https://api.duckmail.sbs",
        "duckmail_bearer": "",
        "duckmail_use_proxy": True,
        "proxy_enabled": True,
        "proxy": "",
        "proxy_list_enabled": True,
        "proxy_list_url": "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/US/data.txt",
        "proxy_list_default_scheme": "auto",
        "proxy_list_fetch_proxy": "",
        "proxy_list_refresh_interval_seconds": 1200,
        "proxy_validate_enabled": True,
        "proxy_validate_timeout_seconds": 6,
        "proxy_validate_workers": 40,
        "proxy_validate_test_url": "https://auth.openai.com/",
        "proxy_max_retries_per_request": 30,
        "proxy_bad_ttl_seconds": 180,
        "proxy_retry_attempts_per_account": 20,
        "otp_wait_timeout_seconds": 150,
        "otp_poll_interval_seconds": 3,
        "otp_resend_interval_seconds": 30,
        "stable_proxy_file": "stable_proxy.txt",
        "stable_proxy": "",
        "prefer_stable_proxy": True,
        "output_file": "registered_accounts.txt",
        "enable_oauth": True,
        "oauth_required": True,
        "oauth_issuer": "https://auth.openai.com",
        "oauth_client_id": "app_EMoamEEZ73f0CkXaXp7hrann",
        "oauth_redirect_uri": "http://localhost:1455/auth/callback",
        "ak_file": "ak.txt",
        "rk_file": "rk.txt",
        "token_json_dir": "codex_tokens",
        "sub2api_base_url": "",
        "sub2api_bearer": "",
        "sub2api_email": "",
        "sub2api_password": "",
        "auto_upload_sub2api": False,
        "sub2api_group_ids": [2],
    }

    base_dir = os.path.dirname(os.path.abspath(__file__))
    example_config_path = os.path.join(base_dir, "config.example.json")
    local_config_path = os.path.join(base_dir, "config.json")
    config.update(_load_json_file(example_config_path))
    config.update(_load_json_file(local_config_path))

    # 环境变量优先级更高
    config["duckmail_api_base"] = os.environ.get("DUCKMAIL_API_BASE", config["duckmail_api_base"])
    config["duckmail_bearer"] = os.environ.get("DUCKMAIL_BEARER", config["duckmail_bearer"])
    config["duckmail_use_proxy"] = os.environ.get("DUCKMAIL_USE_PROXY", config["duckmail_use_proxy"])
    config["proxy_enabled"] = os.environ.get("PROXY_ENABLED", config["proxy_enabled"])
    config["proxy"] = os.environ.get("PROXY", config["proxy"])
    config["proxy_list_enabled"] = os.environ.get("PROXY_LIST_ENABLED", config["proxy_list_enabled"])
    config["proxy_list_url"] = os.environ.get("PROXY_LIST_URL", config["proxy_list_url"])
    config["proxy_list_default_scheme"] = os.environ.get("PROXY_LIST_DEFAULT_SCHEME", config["proxy_list_default_scheme"])
    config["proxy_list_fetch_proxy"] = os.environ.get("PROXY_LIST_FETCH_PROXY", config["proxy_list_fetch_proxy"])
    config["proxy_list_refresh_interval_seconds"] = int(os.environ.get(
        "PROXY_LIST_REFRESH_INTERVAL_SECONDS", config["proxy_list_refresh_interval_seconds"]
    ))
    config["proxy_validate_enabled"] = os.environ.get("PROXY_VALIDATE_ENABLED", config["proxy_validate_enabled"])
    config["proxy_validate_timeout_seconds"] = float(os.environ.get(
        "PROXY_VALIDATE_TIMEOUT_SECONDS", config["proxy_validate_timeout_seconds"]
    ))
    config["proxy_validate_workers"] = int(os.environ.get("PROXY_VALIDATE_WORKERS", config["proxy_validate_workers"]))
    config["proxy_validate_test_url"] = os.environ.get("PROXY_VALIDATE_TEST_URL", config["proxy_validate_test_url"])
    config["total_accounts"] = int(os.environ.get("TOTAL_ACCOUNTS", config["total_accounts"]))
    config["proxy_max_retries_per_request"] = int(os.environ.get(
        "PROXY_MAX_RETRIES_PER_REQUEST", config["proxy_max_retries_per_request"]
    ))
    config["proxy_bad_ttl_seconds"] = int(os.environ.get("PROXY_BAD_TTL_SECONDS", config["proxy_bad_ttl_seconds"]))
    config["proxy_retry_attempts_per_account"] = int(os.environ.get(
        "PROXY_RETRY_ATTEMPTS_PER_ACCOUNT", config["proxy_retry_attempts_per_account"]
    ))
    config["otp_wait_timeout_seconds"] = int(os.environ.get(
        "OTP_WAIT_TIMEOUT_SECONDS", config["otp_wait_timeout_seconds"]
    ))
    config["otp_poll_interval_seconds"] = float(os.environ.get(
        "OTP_POLL_INTERVAL_SECONDS", config["otp_poll_interval_seconds"]
    ))
    config["otp_resend_interval_seconds"] = float(os.environ.get(
        "OTP_RESEND_INTERVAL_SECONDS", config["otp_resend_interval_seconds"]
    ))
    config["stable_proxy_file"] = os.environ.get("STABLE_PROXY_FILE", config["stable_proxy_file"])
    config["stable_proxy"] = os.environ.get("STABLE_PROXY", config["stable_proxy"])
    config["prefer_stable_proxy"] = os.environ.get("PREFER_STABLE_PROXY", config["prefer_stable_proxy"])
    config["enable_oauth"] = os.environ.get("ENABLE_OAUTH", config["enable_oauth"])
    config["oauth_required"] = os.environ.get("OAUTH_REQUIRED", config["oauth_required"])
    config["oauth_issuer"] = os.environ.get("OAUTH_ISSUER", config["oauth_issuer"])
    config["oauth_client_id"] = os.environ.get("OAUTH_CLIENT_ID", config["oauth_client_id"])
    config["oauth_redirect_uri"] = os.environ.get("OAUTH_REDIRECT_URI", config["oauth_redirect_uri"])
    config["ak_file"] = os.environ.get("AK_FILE", config["ak_file"])
    config["rk_file"] = os.environ.get("RK_FILE", config["rk_file"])
    config["token_json_dir"] = os.environ.get("TOKEN_JSON_DIR", config["token_json_dir"])
    config["sub2api_base_url"] = os.environ.get("SUB2API_BASE_URL", config["sub2api_base_url"])
    config["sub2api_bearer"] = os.environ.get("SUB2API_BEARER", config["sub2api_bearer"])
    config["sub2api_email"] = os.environ.get("SUB2API_EMAIL", config["sub2api_email"])
    config["sub2api_password"] = os.environ.get("SUB2API_PASSWORD", config["sub2api_password"])
    config["auto_upload_sub2api"] = os.environ.get("AUTO_UPLOAD_SUB2API", config["auto_upload_sub2api"])
    _raw_group_ids = os.environ.get("SUB2API_GROUP_IDS")
    if _raw_group_ids:
        try:
            config["sub2api_group_ids"] = [int(x.strip()) for x in _raw_group_ids.split(",") if x.strip().isdigit()]
        except Exception:
            pass

    return config


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


_CONFIG = _load_config()
DUCKMAIL_API_BASE = _CONFIG["duckmail_api_base"]
DUCKMAIL_BEARER = _CONFIG["duckmail_bearer"]
DUCKMAIL_USE_PROXY = _as_bool(_CONFIG.get("duckmail_use_proxy", True))
DEFAULT_TOTAL_ACCOUNTS = _CONFIG["total_accounts"]
PROXY_ENABLED = _as_bool(_CONFIG.get("proxy_enabled", True))
DEFAULT_PROXY = _CONFIG["proxy"]
PROXY_LIST_ENABLED = _as_bool(_CONFIG.get("proxy_list_enabled", True))
PROXY_LIST_URL = _CONFIG["proxy_list_url"]
PROXY_LIST_DEFAULT_SCHEME = str(_CONFIG.get("proxy_list_default_scheme", "auto") or "auto").strip().lower() or "auto"
PROXY_LIST_FETCH_PROXY = str(_CONFIG.get("proxy_list_fetch_proxy", "") or "").strip()
PROXY_LIST_REFRESH_INTERVAL_SECONDS = max(0, int(_CONFIG.get("proxy_list_refresh_interval_seconds", 1200)))
PROXY_VALIDATE_ENABLED = _as_bool(_CONFIG.get("proxy_validate_enabled", True))
PROXY_VALIDATE_TIMEOUT_SECONDS = max(1.0, float(_CONFIG.get("proxy_validate_timeout_seconds", 6)))
PROXY_VALIDATE_WORKERS = max(1, int(_CONFIG.get("proxy_validate_workers", 40)))
PROXY_VALIDATE_TEST_URL = str(_CONFIG.get("proxy_validate_test_url", "https://auth.openai.com/")).strip() or "https://auth.openai.com/"
PROXY_MAX_RETRIES_PER_REQUEST = max(1, int(_CONFIG.get("proxy_max_retries_per_request", 30)))
PROXY_BAD_TTL_SECONDS = max(10, int(_CONFIG.get("proxy_bad_ttl_seconds", 180)))
PROXY_RETRY_ATTEMPTS_PER_ACCOUNT = max(1, int(_CONFIG.get("proxy_retry_attempts_per_account", 20)))
OTP_WAIT_TIMEOUT_SECONDS = max(60, int(_CONFIG.get("otp_wait_timeout_seconds", 150)))
OTP_POLL_INTERVAL_SECONDS = max(1.0, float(_CONFIG.get("otp_poll_interval_seconds", 3)))
OTP_RESEND_INTERVAL_SECONDS = max(5.0, float(_CONFIG.get("otp_resend_interval_seconds", 30)))
STABLE_PROXY_FILE = _CONFIG.get("stable_proxy_file", "stable_proxy.txt")
STABLE_PROXY_RAW = _CONFIG.get("stable_proxy", "")
PREFER_STABLE_PROXY = _as_bool(_CONFIG.get("prefer_stable_proxy", True))
DEFAULT_OUTPUT_FILE = _CONFIG["output_file"]
ENABLE_OAUTH = _as_bool(_CONFIG.get("enable_oauth", True))
OAUTH_REQUIRED = _as_bool(_CONFIG.get("oauth_required", True))
OAUTH_ISSUER = _CONFIG["oauth_issuer"].rstrip("/")
OAUTH_CLIENT_ID = str(_CONFIG.get("oauth_client_id", "") or "").strip() or "app_EMoamEEZ73f0CkXaXp7hrann"
OAUTH_REDIRECT_URI = _CONFIG["oauth_redirect_uri"]
AK_FILE = _CONFIG["ak_file"]
RK_FILE = _CONFIG["rk_file"]
TOKEN_JSON_DIR = _CONFIG["token_json_dir"]
SUB2API_BASE_URL = str(_CONFIG.get("sub2api_base_url", "") or "").strip().rstrip("/")
SUB2API_BEARER = str(_CONFIG.get("sub2api_bearer", "") or "").strip()
SUB2API_EMAIL = str(_CONFIG.get("sub2api_email", "") or "").strip()
SUB2API_PASSWORD = str(_CONFIG.get("sub2api_password", "") or "").strip()
AUTO_UPLOAD_SUB2API = _as_bool(_CONFIG.get("auto_upload_sub2api", False))
_raw = _CONFIG.get("sub2api_group_ids", [2])
SUB2API_GROUP_IDS = [int(x) for x in (_raw if isinstance(_raw, list) else [_raw]) if str(x).strip().lstrip("-").isdigit()]

if not DUCKMAIL_BEARER:
    print("⚠️ 警告: 未设置 duckmail_bearer(JWT_TOKEN)，请在 config.json 中设置或设置环境变量")
    print("   可先复制 config.example.json 为 config.json 再填写")
    print("   文件: config.json -> duckmail_bearer")
    print("   环境变量: export DUCKMAIL_BEARER='your_jwt_token'")

# 全局线程锁
_print_lock = threading.Lock()
_file_lock = threading.Lock()
# 停止信号：外部调用 _stop_event.set() 可中断注册循环
_stop_event = threading.Event()


def _normalize_proxy_scheme(scheme: str, allow_auto: bool = False):
    """标准化代理协议配置，兼容常见别名。AI by zb"""
    value = str(scheme or "").strip().lower()
    aliases = {
        "https": "http",
        "http/https": "http",
        "httphttps": "http",
        "socks": "socks5",
    }
    value = aliases.get(value, value)
    if allow_auto and value in {"", "auto"}:
        return "auto"
    return value if value in {"http", "socks4", "socks5"} else "http"


def _normalize_proxy(proxy: str, default_scheme: str = "http"):
    if not proxy:
        return None
    value = str(proxy).strip()
    if not value:
        return None
    if "://" in value:
        return value
    scheme = _normalize_proxy_scheme(default_scheme)
    return f"{scheme}://{value}"


STABLE_PROXY = _normalize_proxy(STABLE_PROXY_RAW)


def _normalize_proxy_list_url(url: str):
    value = (url or "").strip()
    if not value:
        return "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/US/data.txt"

    m = re.match(r"^https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$", value)
    if m:
        owner, repo, branch, path = m.groups()
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    return value


def _extract_proxy_scheme(proxy: str):
    """提取代理地址中的协议头。AI by zb"""
    value = str(proxy or "").strip()
    if "://" not in value:
        return ""
    return _normalize_proxy_scheme(urlparse(value).scheme)


def _infer_proxy_list_scheme(list_url: str, configured_scheme: str = "auto",
                             fetch_proxy: str = None, fallback_proxy: str = None):
    """推断裸 ip:port 应补全成哪种代理协议。AI by zb"""
    configured = _normalize_proxy_scheme(configured_scheme, allow_auto=True)
    if configured != "auto":
        return configured

    try:
        params = parse_qs(urlparse(str(list_url or "")).query)
        pt = str((params.get("pt") or [""])[0]).strip().lower()
        if pt in {"2", "socks5"}:
            return "socks5"
        if pt in {"3", "socks4"}:
            return "socks4"
        if pt in {"1", "http", "https"}:
            return "http"
    except Exception:
        pass

    lower_url = str(list_url or "").lower()
    if "socks5" in lower_url:
        return "socks5"
    if "socks4" in lower_url:
        return "socks4"

    for proxy in (fetch_proxy, fallback_proxy):
        scheme = _extract_proxy_scheme(proxy)
        if scheme:
            return scheme
    return "http"


def _is_proxy_candidate(value: str):
    """判断字符串是否像一个可用代理地址。AI by zb"""
    text = str(value or "").strip()
    if not text:
        return False
    try:
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", text):
            parsed = urlparse(text)
        else:
            parsed = urlparse(f"//{text}")
        return bool(parsed.hostname and parsed.port)
    except Exception:
        return False


def _collect_proxies_from_payload(payload):
    """递归提取 JSON 载荷中的代理候选项。AI by zb"""
    candidates = []
    if payload is None:
        return candidates
    if isinstance(payload, str):
        for raw_part in re.split(r"[\r\n,]+", payload):
            value = raw_part.strip().strip("'\"")
            if value:
                candidates.append(value)
        return candidates
    if isinstance(payload, (list, tuple, set)):
        for item in payload:
            candidates.extend(_collect_proxies_from_payload(item))
        return candidates
    if isinstance(payload, dict):
        ip = payload.get("ip") or payload.get("host")
        port = payload.get("port")
        if ip and port:
            candidates.append(f"{ip}:{port}")
        for key in ("proxy", "http", "https", "socks4", "socks5", "server", "addr"):
            if key in payload:
                candidates.extend(_collect_proxies_from_payload(payload.get(key)))
        for value in payload.values():
            candidates.extend(_collect_proxies_from_payload(value))
    return candidates


def _dedupe_normalized_proxies(candidates, default_scheme: str = "http"):
    """标准化并去重代理候选项。AI by zb"""
    proxies = []
    seen = set()
    for candidate in candidates:
        if not _is_proxy_candidate(candidate):
            continue
        normalized = _normalize_proxy(candidate, default_scheme=default_scheme)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        proxies.append(normalized)
    return proxies


def _parse_proxy_response_body(body: str, default_scheme: str = "http"):
    """解析代理列表响应，兼容纯文本与常见 JSON 结构。AI by zb"""
    text = str(body or "").strip()
    if not text:
        return []

    if text[:1] in ("{", "["):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if payload is not None:
            proxies = _dedupe_normalized_proxies(
                _collect_proxies_from_payload(payload),
                default_scheme=default_scheme,
            )
            if proxies:
                return proxies
            if isinstance(payload, dict):
                code = payload.get("code")
                msg = str(
                    payload.get("msg")
                    or payload.get("message")
                    or payload.get("error")
                    or payload.get("detail")
                    or ""
                ).strip()
                status = str(payload.get("status") or "").strip()
                if code is not None or msg or status:
                    details = []
                    if code is not None:
                        details.append(f"code={code}")
                    if status:
                        details.append(f"status={status}")
                    if msg:
                        details.append(f"msg={msg}")
                    raise Exception("代理列表接口返回错误: " + ", ".join(details))
            raise Exception("代理列表接口返回 JSON，但未解析到任何代理地址")

    return _dedupe_normalized_proxies(re.split(r"[\r\n,]+", text), default_scheme=default_scheme)


class ProxyPool:
    """线程安全代理池：使用 HTTP/SOCKS 代理并轮询"""

    def __init__(self, list_url: str, fallback_proxy: str = None,
                 max_retries_per_request: int = 30, bad_ttl_seconds: int = 180,
                 validate_enabled: bool = True, validate_timeout_seconds: float = 6,
                 validate_workers: int = 40, validate_test_url: str = "https://auth.openai.com/",
                 prefer_stable_proxy: bool = True, list_enabled: bool = True,
                 list_default_scheme: str = "auto", list_fetch_proxy: str = None,
                 list_refresh_interval_seconds: int = 1200):
        self.list_url = _normalize_proxy_list_url(list_url)
        self.fallback_proxy = _normalize_proxy(fallback_proxy)
        self.list_enabled = bool(list_enabled)
        self.list_default_scheme = _normalize_proxy_scheme(list_default_scheme, allow_auto=True)
        self.list_fetch_proxy = _normalize_proxy(list_fetch_proxy) if list_fetch_proxy else None
        self.list_refresh_interval_seconds = max(0, int(list_refresh_interval_seconds))
        self.max_retries_per_request = max(1, int(max_retries_per_request))
        self.bad_ttl_seconds = max(10, int(bad_ttl_seconds))
        self.validate_enabled = bool(validate_enabled)
        self.validate_timeout_seconds = max(1.0, float(validate_timeout_seconds))
        self.validate_workers = max(1, int(validate_workers))
        self.validate_test_url = str(validate_test_url).strip() or "https://auth.openai.com/"
        self.prefer_stable_proxy = bool(prefer_stable_proxy)
        self._lock = threading.Lock()
        self._loaded = False
        self._proxies = []
        self._index = 0
        self._bad_until = {}
        self._last_fetched_count = 0
        self._last_valid_count = 0
        self._last_refresh_at = 0.0
        self._stable_proxy = None
        self._last_error = ""

    def set_fallback(self, proxy: str):
        normalized = _normalize_proxy(proxy)
        if normalized:
            with self._lock:
                self.fallback_proxy = normalized

    def set_stable_proxy(self, proxy: str):
        normalized = _normalize_proxy(proxy)
        if not normalized:
            return
        with self._lock:
            self._stable_proxy = normalized
            self._bad_until.pop(normalized, None)

    def set_prefer_stable_proxy(self, enabled: bool):
        with self._lock:
            self.prefer_stable_proxy = bool(enabled)

    def set_list_fetch_proxy(self, proxy: str):
        """更新代理列表接口拉取时使用的兜底代理。AI by zb"""
        normalized = _normalize_proxy(proxy) if proxy else None
        with self._lock:
            if self.list_fetch_proxy == normalized:
                return
            self.list_fetch_proxy = normalized
            self._loaded = False

    def set_list_default_scheme(self, scheme: str):
        """更新裸 ip:port 的默认补全协议。AI by zb"""
        normalized = _normalize_proxy_scheme(scheme, allow_auto=True)
        with self._lock:
            if self.list_default_scheme == normalized:
                return
            self.list_default_scheme = normalized
            self._loaded = False

    def set_list_refresh_interval(self, seconds: int):
        """更新代理列表自动刷新间隔。AI by zb"""
        normalized = max(0, int(seconds))
        with self._lock:
            if self.list_refresh_interval_seconds == normalized:
                return
            self.list_refresh_interval_seconds = normalized
            self._loaded = False

    def set_list_enabled(self, enabled: bool):
        """切换是否使用代理列表。AI by zb"""
        with self._lock:
            enabled = bool(enabled)
            if self.list_enabled == enabled:
                return
            self.list_enabled = enabled
            self._loaded = False

    def get_stable_proxy(self):
        with self._lock:
            return self._stable_proxy

    def _current_list_scheme(self):
        """计算当前代理列表的有效默认协议。AI by zb"""
        return _infer_proxy_list_scheme(
            self.list_url,
            configured_scheme=self.list_default_scheme,
            fetch_proxy=self.list_fetch_proxy,
            fallback_proxy=self.fallback_proxy,
        )

    def _fetch_proxies(self):
        request_kwargs = {"timeout": 20}
        if self.list_fetch_proxy:
            request_kwargs["proxies"] = {
                "http": self.list_fetch_proxy,
                "https": self.list_fetch_proxy,
            }
        res = curl_requests.get(self.list_url, **request_kwargs)
        body = res.text or ""
        if res.status_code != 200:
            snippet = " ".join(body.strip().split())[:200]
            raise Exception(f"HTTP {res.status_code}: {snippet or 'empty response'}")

        return _parse_proxy_response_body(body, default_scheme=self._current_list_scheme())

    def _validate_single_proxy(self, proxy: str):
        try:
            res = curl_requests.get(
                self.validate_test_url,
                timeout=self.validate_timeout_seconds,
                allow_redirects=False,
                proxies={"http": proxy, "https": proxy},
                impersonate="chrome131",
            )
            return 200 <= res.status_code < 500
        except Exception:
            return False

    def _filter_valid_proxies(self, proxies):
        if not self.validate_enabled or not proxies:
            return list(proxies)

        workers = min(self.validate_workers, len(proxies))
        valid = []
        total = len(proxies)
        done = 0
        started_at = time.time()
        last_log_at = started_at

        with _print_lock:
            print(
                f"[ProxyCheck] 开始校验代理: 总数 {total}, 并发 {workers}, "
                f"超时 {self.validate_timeout_seconds}s, 测试URL {self.validate_test_url}"
            )

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(self._validate_single_proxy, proxy): proxy for proxy in proxies}
            for future in as_completed(futures):
                proxy = futures[future]
                done += 1
                try:
                    if future.result():
                        valid.append(proxy)
                except Exception:
                    pass

                now = time.time()
                if done == total or (now - last_log_at) >= 1.5:
                    with _print_lock:
                        print(f"[ProxyCheck] 进度 {done}/{total}, 可用 {len(valid)}")
                    last_log_at = now

        elapsed = time.time() - started_at
        with _print_lock:
            print(f"[ProxyCheck] 校验完成: 可用 {len(valid)}/{total}, 耗时 {elapsed:.1f}s")
        return valid

    def refresh(self, force=False):
        with self._lock:
            refresh_due = (
                self._loaded
                and self.list_enabled
                and self.list_refresh_interval_seconds > 0
                and (time.time() - self._last_refresh_at) >= self.list_refresh_interval_seconds
            )
            if self._loaded and not force and not refresh_due:
                return
            list_enabled = self.list_enabled
            stable_proxy = self._stable_proxy
            fallback_proxy = self.fallback_proxy
            refresh_started_at = time.time()

        proxies = []
        fetched_proxies = []
        last_error = ""
        if list_enabled:
            try:
                fetched_proxies = self._fetch_proxies()
                proxies = self._filter_valid_proxies(fetched_proxies)
                if self.validate_enabled and fetched_proxies and not proxies:
                    last_error = "代理校验后无可用代理"
            except Exception as e:
                last_error = str(e)
        else:
            seen = set()
            for proxy in (stable_proxy, fallback_proxy):
                normalized = _normalize_proxy(proxy)
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    proxies.append(normalized)

        with self._lock:
            self._last_fetched_count = len(fetched_proxies)
            self._last_valid_count = len(proxies) if self.validate_enabled else len(fetched_proxies)
            self._last_refresh_at = refresh_started_at
            if proxies:
                random.shuffle(proxies)
                self._proxies = proxies
                self._index = 0
                self._bad_until = {}
                if self._stable_proxy and self._stable_proxy not in self._proxies:
                    self._stable_proxy = None
                self._last_error = ""
            elif not self._proxies:
                self._proxies = [self.fallback_proxy] if self.fallback_proxy else []
                self._index = 0
                self._last_error = last_error
            else:
                self._last_error = last_error
            self._loaded = True

    def next_proxy(self):
        self.refresh()
        with self._lock:
            if not self._proxies:
                return None
            now = time.time()
            stable = self._stable_proxy if self.prefer_stable_proxy else None
            if stable:
                stable_bad_until = self._bad_until.get(stable, 0)
                if stable_bad_until and stable_bad_until <= now:
                    self._bad_until.pop(stable, None)
                    stable_bad_until = 0
                if stable_bad_until > now:
                    self._stable_proxy = None
                else:
                    return stable

            total = len(self._proxies)
            for _ in range(total):
                proxy = self._proxies[self._index]
                self._index = (self._index + 1) % total

                bad_until = self._bad_until.get(proxy, 0)
                if bad_until and bad_until <= now:
                    self._bad_until.pop(proxy, None)
                    bad_until = 0

                if bad_until > now:
                    continue
                return proxy

            fallback = self.fallback_proxy
            if fallback:
                bad_until = self._bad_until.get(fallback, 0)
                if bad_until and bad_until <= now:
                    self._bad_until.pop(fallback, None)
                    bad_until = 0
                if bad_until <= now:
                    return fallback
            # 所有代理都在冷却时，仍尝试一个代理，避免长时间完全不可用
            proxy = self._proxies[self._index]
            self._index = (self._index + 1) % total
            return proxy

    def report_bad(self, proxy: str, error=None):
        normalized = _normalize_proxy(proxy)
        if not normalized:
            return

        until = time.time() + self.bad_ttl_seconds
        with self._lock:
            self._bad_until[normalized] = until
            if self._stable_proxy == normalized:
                self._stable_proxy = None
            if error:
                self._last_error = f"{normalized} -> {str(error)[:160]}"

    def report_success(self, proxy: str):
        normalized = _normalize_proxy(proxy)
        if not normalized:
            return
        with self._lock:
            self._stable_proxy = normalized
            self._bad_until.pop(normalized, None)

    def request_retry_limit(self):
        self.refresh()
        with self._lock:
            pool_size = len(self._proxies)
            if self.fallback_proxy and self.fallback_proxy not in self._proxies:
                pool_size += 1
            max_retries = self.max_retries_per_request
        return max(1, min(max_retries, max(1, pool_size)))

    def info(self):
        with self._lock:
            now = time.time()
            bad_count = 0
            for until in self._bad_until.values():
                if until > now:
                    bad_count += 1
            return {
                "list_url": self.list_url,
                "list_enabled": self.list_enabled,
                "list_default_scheme": self._current_list_scheme(),
                "list_fetch_proxy": self.list_fetch_proxy,
                "list_refresh_interval_seconds": self.list_refresh_interval_seconds,
                "last_refresh_at": self._last_refresh_at,
                "count": len(self._proxies),
                "fetched_count": self._last_fetched_count,
                "validated_count": self._last_valid_count,
                "validate_enabled": self.validate_enabled,
                "validate_test_url": self.validate_test_url,
                "validate_timeout_seconds": self.validate_timeout_seconds,
                "validate_workers": self.validate_workers,
                "bad_count": bad_count,
                "fallback_proxy": self.fallback_proxy,
                "stable_proxy": self._stable_proxy,
                "prefer_stable_proxy": self.prefer_stable_proxy,
                "max_retries_per_request": self.max_retries_per_request,
                "bad_ttl_seconds": self.bad_ttl_seconds,
                "last_error": self._last_error,
            }


_proxy_pool = ProxyPool(
    PROXY_LIST_URL,
    fallback_proxy=DEFAULT_PROXY,
    max_retries_per_request=PROXY_MAX_RETRIES_PER_REQUEST,
    bad_ttl_seconds=PROXY_BAD_TTL_SECONDS,
    validate_enabled=PROXY_VALIDATE_ENABLED,
    validate_timeout_seconds=PROXY_VALIDATE_TIMEOUT_SECONDS,
    validate_workers=PROXY_VALIDATE_WORKERS,
    validate_test_url=PROXY_VALIDATE_TEST_URL,
    prefer_stable_proxy=PREFER_STABLE_PROXY,
    list_enabled=PROXY_LIST_ENABLED,
    list_default_scheme=PROXY_LIST_DEFAULT_SCHEME,
    list_fetch_proxy=PROXY_LIST_FETCH_PROXY,
    list_refresh_interval_seconds=PROXY_LIST_REFRESH_INTERVAL_SECONDS,
)
_stable_proxy_loaded = False


def inspect_proxy_source(config: dict):
    """按指定配置即时检查代理源状态。AI by zb"""
    proxy_enabled = _as_bool(config.get("proxy_enabled", True))
    list_enabled = _as_bool(config.get("proxy_list_enabled", True))
    fallback_proxy = str(config.get("proxy", "") or "").strip()
    stable_proxy = str(config.get("stable_proxy", "") or "").strip()
    pool = ProxyPool(
        str(config.get("proxy_list_url", "") or ""),
        fallback_proxy=fallback_proxy,
        max_retries_per_request=int(config.get("proxy_max_retries_per_request", 30) or 30),
        bad_ttl_seconds=int(config.get("proxy_bad_ttl_seconds", 180) or 180),
        validate_enabled=_as_bool(config.get("proxy_validate_enabled", True)),
        validate_timeout_seconds=float(config.get("proxy_validate_timeout_seconds", 6) or 6),
        validate_workers=int(config.get("proxy_validate_workers", 40) or 40),
        validate_test_url=str(config.get("proxy_validate_test_url", "https://auth.openai.com/") or "https://auth.openai.com/"),
        prefer_stable_proxy=_as_bool(config.get("prefer_stable_proxy", True)),
        list_enabled=list_enabled,
        list_default_scheme=str(config.get("proxy_list_default_scheme", "auto") or "auto"),
        list_fetch_proxy=str(config.get("proxy_list_fetch_proxy", "") or ""),
        list_refresh_interval_seconds=int(config.get("proxy_list_refresh_interval_seconds", 1200) or 1200),
    )
    if stable_proxy:
        pool.set_stable_proxy(stable_proxy)
    if proxy_enabled:
        pool.refresh(force=True)
    info = pool.info()
    info["proxy_enabled"] = proxy_enabled
    info["has_any_proxy"] = bool(
        info["count"] > 0
        or info["fallback_proxy"]
        or info["stable_proxy"]
    )
    return info


def _get_proxy_pool(fallback_proxy=None):
    global _stable_proxy_loaded
    _proxy_pool.set_prefer_stable_proxy(PREFER_STABLE_PROXY)
    _proxy_pool.set_list_enabled(PROXY_LIST_ENABLED)
    _proxy_pool.set_list_default_scheme(PROXY_LIST_DEFAULT_SCHEME)
    _proxy_pool.set_list_fetch_proxy(PROXY_LIST_FETCH_PROXY)
    _proxy_pool.set_list_refresh_interval(PROXY_LIST_REFRESH_INTERVAL_SECONDS)
    if not _stable_proxy_loaded:
        stable = STABLE_PROXY or _load_stable_proxy_from_file()
        if stable:
            _proxy_pool.set_stable_proxy(stable)
        _stable_proxy_loaded = True
    if fallback_proxy:
        _proxy_pool.set_fallback(fallback_proxy)
    return _proxy_pool


def _is_proxy_related_error(exc: Exception):
    class_name = exc.__class__.__name__.lower()
    if "proxy" in class_name:
        return True

    curl_code = getattr(exc, "code", None)
    if curl_code in {5, 6, 7, 28, 35, 47, 52, 55, 56, 97}:
        return True

    msg = str(exc).lower()
    keywords = [
        "proxy",
        "connect tunnel failed",
        "could not connect",
        "connection refused",
        "timed out",
    ]
    for word in keywords:
        if word in msg:
            return True
    return False


def _enable_proxy_rotation(session, fallback_proxy=None, fixed_proxy=None):
    if not PROXY_ENABLED:
        session.trust_env = False
        return session
    pool = _get_proxy_pool(fallback_proxy)
    fixed_proxy = _normalize_proxy(fixed_proxy)
    original_request = session.request
    if getattr(original_request, "_proxy_rotation_wrapped", False):
        return session

    def _request_with_rotating_proxy(method, url, **kwargs):
        if kwargs.get("proxies"):
            return original_request(method, url, **kwargs)

        if fixed_proxy:
            req_kwargs = dict(kwargs)
            req_kwargs["proxies"] = {"http": fixed_proxy, "https": fixed_proxy}
            try:
                return original_request(method, url, **req_kwargs)
            except Exception as e:
                if _is_proxy_related_error(e):
                    pool.report_bad(fixed_proxy, error=e)
                raise

        retry_limit = pool.request_retry_limit()
        last_error = None

        for _ in range(retry_limit):
            proxy = pool.next_proxy()
            req_kwargs = kwargs
            if proxy:
                req_kwargs = dict(kwargs)
                req_kwargs["proxies"] = {"http": proxy, "https": proxy}

            try:
                return original_request(method, url, **req_kwargs)
            except Exception as e:
                last_error = e
                if not proxy:
                    raise
                if not _is_proxy_related_error(e):
                    raise
                pool.report_bad(proxy, error=e)

        if last_error:
            raise last_error
        return original_request(method, url, **kwargs)

    _request_with_rotating_proxy._proxy_rotation_wrapped = True
    session.request = _request_with_rotating_proxy
    return session


# Chrome 指纹配置: impersonate 与 sec-ch-ua 必须匹配真实浏览器
_CHROME_PROFILES = [
    {
        "major": 131, "impersonate": "chrome131",
        "build": 6778, "patch_range": (69, 205),
        "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    },
    {
        "major": 133, "impersonate": "chrome133a",
        "build": 6943, "patch_range": (33, 153),
        "sec_ch_ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
    },
    {
        "major": 136, "impersonate": "chrome136",
        "build": 7103, "patch_range": (48, 175),
        "sec_ch_ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    },
    {
        "major": 142, "impersonate": "chrome142",
        "build": 7540, "patch_range": (30, 150),
        "sec_ch_ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
    },
]


def _random_chrome_version():
    profile = random.choice(_CHROME_PROFILES)
    major = profile["major"]
    build = profile["build"]
    patch = random.randint(*profile["patch_range"])
    full_ver = f"{major}.0.{build}.{patch}"
    ua = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{full_ver} Safari/537.36"
    return profile["impersonate"], major, full_ver, ua, profile["sec_ch_ua"]


def _random_delay(low=0.3, high=1.0):
    time.sleep(random.uniform(low, high))


def _make_trace_headers():
    trace_id = random.randint(10**17, 10**18 - 1)
    parent_id = random.randint(10**17, 10**18 - 1)
    tp = f"00-{uuid.uuid4().hex}-{format(parent_id, '016x')}-01"
    return {
        "traceparent": tp, "tracestate": "dd=s:1;o:rum",
        "x-datadog-origin": "rum", "x-datadog-sampling-priority": "1",
        "x-datadog-trace-id": str(trace_id), "x-datadog-parent-id": str(parent_id),
    }


def _decode_jwt_payload(token: str):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception:
        return {}


def _log_sub2api(message: str):
    """输出 Sub2Api 相关日志。AI by zb"""
    with _print_lock:
        print(message)


def _create_sub2api_uploader() -> Sub2ApiUploader:
    """根据当前配置创建 Sub2Api 上传器。AI by zb"""
    return Sub2ApiUploader(
        config=Sub2ApiConfig(
            base_url=SUB2API_BASE_URL,
            bearer=SUB2API_BEARER,
            email=SUB2API_EMAIL,
            password=SUB2API_PASSWORD,
            group_ids=tuple(SUB2API_GROUP_IDS),
            oauth_client_id=OAUTH_CLIENT_ID,
        ),
        jwt_payload_decoder=_decode_jwt_payload,
        logger=_log_sub2api,
    )


_sub2api_uploader = _create_sub2api_uploader()


def _save_codex_tokens(email: str, tokens: dict):
    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    id_token = tokens.get("id_token", "")

    if access_token:
        with _file_lock:
            with open(AK_FILE, "a", encoding="utf-8") as f:
                f.write(f"{access_token}\n")

    if refresh_token:
        with _file_lock:
            with open(RK_FILE, "a", encoding="utf-8") as f:
                f.write(f"{refresh_token}\n")

    if not access_token:
        return

    payload = _decode_jwt_payload(access_token)
    auth_info = payload.get("https://api.openai.com/auth", {})
    account_id = auth_info.get("chatgpt_account_id", "")

    exp_timestamp = payload.get("exp")
    expired_str = ""
    if isinstance(exp_timestamp, int) and exp_timestamp > 0:
        from datetime import datetime, timezone, timedelta

        exp_dt = datetime.fromtimestamp(exp_timestamp, tz=timezone(timedelta(hours=8)))
        expired_str = exp_dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")

    from datetime import datetime, timezone, timedelta

    now = datetime.now(tz=timezone(timedelta(hours=8)))
    token_data = {
        "type": "codex",
        "email": email,
        "expired": expired_str,
        "id_token": id_token,
        "account_id": account_id,
        "access_token": access_token,
        "last_refresh": now.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "refresh_token": refresh_token,
    }

    base_dir = os.path.dirname(os.path.abspath(__file__))
    token_dir = TOKEN_JSON_DIR if os.path.isabs(TOKEN_JSON_DIR) else os.path.join(base_dir, TOKEN_JSON_DIR)
    os.makedirs(token_dir, exist_ok=True)

    token_path = os.path.join(token_dir, f"{email}.json")
    with _file_lock:
        with open(token_path, "w", encoding="utf-8") as f:
            json.dump(token_data, f, ensure_ascii=False)


def _stable_proxy_path():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return STABLE_PROXY_FILE if os.path.isabs(STABLE_PROXY_FILE) else os.path.join(base_dir, STABLE_PROXY_FILE)


def _load_stable_proxy_from_file():
    path = _stable_proxy_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            line = f.readline().strip()
        return _normalize_proxy(line)
    except Exception:
        return None


def _save_stable_proxy_to_config(proxy: str):
    normalized = _normalize_proxy(proxy)
    if not normalized:
        return

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if not os.path.exists(config_path):
        return

    try:
        with _file_lock:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            config["stable_proxy"] = normalized
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
                f.write("\n")
    except Exception:
        return


def _save_stable_proxy_to_file(proxy: str):
    normalized = _normalize_proxy(proxy)
    if not normalized:
        return
    path = _stable_proxy_path()
    with _file_lock:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"{normalized}\n")


def _generate_password(length=14):
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%&*"
    pwd = [random.choice(lower), random.choice(upper),
           random.choice(digits), random.choice(special)]
    all_chars = lower + upper + digits + special
    pwd += [random.choice(all_chars) for _ in range(length - 4)]
    random.shuffle(pwd)
    return "".join(pwd)


def _random_name():
    first = random.choice([
        "James", "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia",
        "Lucas", "Mia", "Mason", "Isabella", "Logan", "Charlotte", "Alexander",
        "Amelia", "Benjamin", "Harper", "William", "Evelyn", "Henry", "Abigail",
        "Sebastian", "Emily", "Jack", "Elizabeth",
    ])
    last = random.choice([
        "Smith", "Johnson", "Brown", "Davis", "Wilson", "Moore", "Taylor",
        "Clark", "Hall", "Young", "Anderson", "Thomas", "Jackson", "White",
        "Harris", "Martin", "Thompson", "Garcia", "Robinson", "Lewis",
        "Walker", "Allen", "King", "Wright", "Scott", "Green",
    ])
    return f"{first} {last}"


def _random_birthdate():
    y = random.randint(1985, 2002)
    m = random.randint(1, 12)
    d = random.randint(1, 28)
    return f"{y}-{m:02d}-{d:02d}"


class ChatGPTRegister:
    BASE = "https://chatgpt.com"
    AUTH = "https://auth.openai.com"

    def __init__(self, proxy: str = None, tag: str = "", fixed_proxy: str = None):
        self.tag = tag  # 线程标识，用于日志
        self.device_id = str(uuid.uuid4())
        self.auth_session_logging_id = str(uuid.uuid4())
        self.impersonate, self.chrome_major, self.chrome_full, self.ua, self.sec_ch_ua = _random_chrome_version()

        self.session = curl_requests.Session(impersonate=self.impersonate)

        self.proxy = _normalize_proxy(proxy)
        self.fixed_proxy = _normalize_proxy(fixed_proxy)
        _enable_proxy_rotation(self.session, fallback_proxy=self.proxy, fixed_proxy=self.fixed_proxy)

        self.session.headers.update({
            "User-Agent": self.ua,
            "Accept-Language": random.choice([
                "en-US,en;q=0.9", "en-US,en;q=0.9,zh-CN;q=0.8",
                "en,en-US;q=0.9", "en-US,en;q=0.8",
            ]),
            "sec-ch-ua": self.sec_ch_ua, "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"', "sec-ch-ua-arch": '"x86"',
            "sec-ch-ua-bitness": '"64"',
            "sec-ch-ua-full-version": f'"{self.chrome_full}"',
            "sec-ch-ua-platform-version": f'"{random.randint(10, 15)}.0.0"',
        })

        self.session.cookies.set("oai-did", self.device_id, domain="chatgpt.com")
        self._callback_url = None
        self.mail_client = DuckMailClient(
            config=MailApiConfig(
                base_url=DUCKMAIL_API_BASE,
                bearer=DUCKMAIL_BEARER,
                use_proxy=DUCKMAIL_USE_PROXY,
            ),
            user_agent=self.ua,
            impersonate=self.impersonate,
            session_preparer=self._prepare_mail_api_session,
            logger=self._print,
        )
        self.oauth_client = CodexOAuthClient(
            config=CodexOAuthConfig(
                issuer=OAUTH_ISSUER,
                client_id=OAUTH_CLIENT_ID,
                redirect_uri=OAUTH_REDIRECT_URI,
                base_url=self.BASE,
            ),
            session=self.session,
            mail_client=self.mail_client,
            logger=self._print,
            trace_headers_factory=_make_trace_headers,
            user_agent=self.ua,
            device_id=self.device_id,
            sec_ch_ua=self.sec_ch_ua,
            impersonate=self.impersonate,
            otp_wait_timeout_seconds=OTP_WAIT_TIMEOUT_SECONDS,
            otp_poll_interval_seconds=OTP_POLL_INTERVAL_SECONDS,
            otp_resend_interval_seconds=OTP_RESEND_INTERVAL_SECONDS,
        )

    def _log(self, step, method, url, status, body=None):
        prefix = f"[{self.tag}] " if self.tag else ""
        lines = [
            f"\n{'='*60}",
            f"{prefix}[Step] {step}",
            f"{prefix}[{method}] {url}",
            f"{prefix}[Status] {status}",
        ]
        if body:
            try:
                lines.append(f"{prefix}[Response] {json.dumps(body, indent=2, ensure_ascii=False)[:1000]}")
            except Exception:
                lines.append(f"{prefix}[Response] {str(body)[:1000]}")
        lines.append(f"{'='*60}")
        with _print_lock:
            print("\n".join(lines))

    def _print(self, msg):
        prefix = f"[{self.tag}] " if self.tag else ""
        with _print_lock:
            print(f"{prefix}{msg}")

    def _parse_json_or_raise(self, response, step_name: str):
        if response.status_code >= 400:
            raise Exception(f"{step_name} 被拦截 ({response.status_code})")

        try:
            data = response.json()
        except Exception:
            body = (response.text or "")[:200].replace("\n", " ")
            raise Exception(
                f"{step_name} 返回非 JSON (status={response.status_code}, body={body})"
            )
        return data

    # ==================== 邮件 API ====================

    def _prepare_mail_api_session(self, session):
        """为邮件 API 会话附加代理轮换能力。AI by zb"""

        return _enable_proxy_rotation(session, fallback_proxy=self.proxy, fixed_proxy=self.fixed_proxy)

    def create_temp_email(self):
        """通过 DuckMailClient 创建临时邮箱。AI by zb"""

        return self.mail_client.create_temp_email()

    def _fetch_emails_mail_api(self, mailbox_ref: str):
        """通过 DuckMailClient 拉取邮件列表。AI by zb"""

        return self.mail_client.fetch_emails(mailbox_ref)

    def _fetch_email_detail_mail_api(self, mailbox_ref: str, msg_id: str):
        """通过 DuckMailClient 拉取邮件详情。AI by zb"""

        return self.mail_client.fetch_email_detail(mailbox_ref, msg_id)

    def _extract_verification_code(self, email_content: str):
        """通过 DuckMailClient 提取验证码。AI by zb"""

        return self.mail_client.extract_verification_code(email_content)

    def wait_for_verification_email(self, mailbox_ref: str, timeout: int = OTP_WAIT_TIMEOUT_SECONDS,
                                    not_before_ts: float = None, exclude_message_ids=None):
        """通过 DuckMailClient 等待验证码邮件。AI by zb"""

        return self.mail_client.wait_for_verification_email(
            mailbox_ref,
            timeout=timeout,
            not_before_ts=not_before_ts,
            exclude_message_ids=exclude_message_ids,
            poll_interval_seconds=OTP_POLL_INTERVAL_SECONDS,
            on_retry=self.resend_otp,
            retry_interval_seconds=OTP_RESEND_INTERVAL_SECONDS,
        )

    # ==================== 注册流程 ====================

    def visit_homepage(self):
        url = f"{self.BASE}/"
        r = self.session.get(url, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
        }, allow_redirects=True)
        self._log("0. Visit homepage", "GET", url, r.status_code,
                   {"cookies_count": len(self.session.cookies)})
        if r.status_code != 200:
            raise Exception(f"Visit homepage 被拦截 ({r.status_code})")

    def get_csrf(self) -> str:
        url = f"{self.BASE}/api/auth/csrf"
        r = self.session.get(url, headers={"Accept": "application/json", "Referer": f"{self.BASE}/"})
        data = self._parse_json_or_raise(r, "Get CSRF")
        token = data.get("csrfToken", "")
        self._log("1. Get CSRF", "GET", url, r.status_code, data)
        if not token:
            raise Exception("Failed to get CSRF token")
        return token

    def signin(self, email: str, csrf: str) -> str:
        url = f"{self.BASE}/api/auth/signin/openai"
        params = {
            "prompt": "login", "ext-oai-did": self.device_id,
            "auth_session_logging_id": self.auth_session_logging_id,
            "ext-passkey-client-capabilities": "1111",
            "screen_hint": "login_or_signup", "login_hint": email,
        }
        form_data = {"callbackUrl": f"{self.BASE}/", "csrfToken": csrf, "json": "true"}
        r = self.session.post(url, params=params, data=form_data, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json", "Referer": f"{self.BASE}/", "Origin": self.BASE,
        })
        data = self._parse_json_or_raise(r, "Signin")
        authorize_url = data.get("url", "")
        self._log("2. Signin", "POST", url, r.status_code, data)
        if not authorize_url:
            raise Exception("Failed to get authorize URL")
        return authorize_url

    def authorize(self, url: str) -> str:
        r = self.session.get(url, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{self.BASE}/", "Upgrade-Insecure-Requests": "1",
        }, allow_redirects=True)
        final_url = str(r.url)
        self._log("3. Authorize", "GET", url, r.status_code, {"final_url": final_url})
        if r.status_code >= 400:
            raise Exception(f"Authorize 被拦截 ({r.status_code})")
        return final_url

    def register(self, email: str, password: str):
        url = f"{self.AUTH}/api/accounts/user/register"
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                    "Referer": f"{self.AUTH}/create-account/password", "Origin": self.AUTH}
        headers.update(_make_trace_headers())
        r = self.session.post(url, json={"username": email, "password": password}, headers=headers)
        try: data = r.json()
        except Exception: data = {"text": r.text[:500]}
        self._log("4. Register", "POST", url, r.status_code, data)
        return r.status_code, data

    def send_otp(self):
        url = f"{self.AUTH}/api/accounts/email-otp/send"
        r = self.session.get(url, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{self.AUTH}/create-account/password", "Upgrade-Insecure-Requests": "1",
        }, allow_redirects=True)
        try: data = r.json()
        except Exception: data = {"final_url": str(r.url), "status": r.status_code}
        self._log("5. Send OTP", "GET", url, r.status_code, data)
        return r.status_code, data

    def resend_otp(self, attempt: int = 1):
        """在等待超时阶段补发验证码邮件。AI by zb"""

        url = f"{self.AUTH}/api/accounts/email-otp/resend"
        headers = {
            "Accept": "*/*",
            "Origin": self.AUTH,
            "Referer": f"{self.AUTH}/email-verification",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }
        headers.update(_make_trace_headers())
        r = self.session.post(
            url,
            headers=headers,
            data=b"",
            allow_redirects=False,
        )
        try:
            data = r.json()
        except Exception:
            data = {"text": (r.text or "")[:500], "status": r.status_code}
        self._log(f"5.{attempt} Resend OTP", "POST", url, r.status_code, data)
        return r.status_code, data

    def validate_otp(self, code: str):
        url = f"{self.AUTH}/api/accounts/email-otp/validate"
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                    "Referer": f"{self.AUTH}/email-verification", "Origin": self.AUTH}
        headers.update(_make_trace_headers())
        r = self.session.post(url, json={"code": code}, headers=headers)
        try: data = r.json()
        except Exception: data = {"text": r.text[:500]}
        self._log("6. Validate OTP", "POST", url, r.status_code, data)
        return r.status_code, data

    def create_account(self, name: str, birthdate: str):
        url = f"{self.AUTH}/api/accounts/create_account"
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                    "Referer": f"{self.AUTH}/about-you", "Origin": self.AUTH}
        headers.update(_make_trace_headers())
        r = self.session.post(url, json={"name": name, "birthdate": birthdate}, headers=headers)
        try: data = r.json()
        except Exception: data = {"text": r.text[:500]}
        self._log("7. Create Account", "POST", url, r.status_code, data)
        if isinstance(data, dict):
            cb = data.get("continue_url") or data.get("url") or data.get("redirect_url")
            if cb:
                self._callback_url = cb
        return r.status_code, data

    def callback(self, url: str = None):
        if not url:
            url = self._callback_url
        if not url:
            self._print("[!] No callback URL, skipping.")
            return None, None
        r = self.session.get(url, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
        }, allow_redirects=True)
        self._log("8. Callback", "GET", url, r.status_code, {"final_url": str(r.url)})
        return r.status_code, {"final_url": str(r.url)}

    # ==================== 自动注册主流程 ====================

    def run_register(self, email, password, name, birthdate, mailbox_ref):
        """使用邮件 API 的注册流程"""
        self.visit_homepage()
        _random_delay(0.3, 0.8)
        csrf = self.get_csrf()
        _random_delay(0.2, 0.5)
        auth_url = self.signin(email, csrf)
        _random_delay(0.3, 0.8)
        pre_authorize_message_ids = mail_message_id_set(self._fetch_emails_mail_api(mailbox_ref))

        final_url = self.authorize(auth_url)
        final_path = urlparse(final_url).path
        _random_delay(0.3, 0.8)

        self._print(f"Authorize → {final_path}")

        need_otp = False
        otp_started_at = None
        otp_seen_message_ids = set()

        if "create-account/password" in final_path:
            self._print("全新注册流程")
            _random_delay(0.5, 1.0)
            status, data = self.register(email, password)
            if status != 200:
                raise Exception(f"Register 失败 ({status}): {data}")
            # register 之后可能还需要 send_otp（全新注册流程中 OTP 不一定在 authorize 时发送）
            _random_delay(0.3, 0.8)
            otp_seen_message_ids = mail_message_id_set(self._fetch_emails_mail_api(mailbox_ref))
            self.send_otp()
            need_otp = True
            otp_started_at = time.time()
        elif "email-verification" in final_path or "email-otp" in final_path:
            self._print("跳到 OTP 验证阶段 (authorize 已触发 OTP，不再重复发送)")
            # 不调用 send_otp()，因为 authorize 重定向到 email-verification 时服务器已发送 OTP
            need_otp = True
            otp_started_at = time.time()
            otp_seen_message_ids = pre_authorize_message_ids
        elif "about-you" in final_path:
            self._print("跳到填写信息阶段")
            _random_delay(0.5, 1.0)
            self.create_account(name, birthdate)
            _random_delay(0.3, 0.5)
            self.callback()
            return True
        elif "callback" in final_path or "chatgpt.com" in final_url:
            self._print("账号已完成注册")
            return True
        else:
            self._print(f"未知跳转: {final_url}")
            self.register(email, password)
            otp_seen_message_ids = mail_message_id_set(self._fetch_emails_mail_api(mailbox_ref))
            self.send_otp()
            need_otp = True
            otp_started_at = time.time()

        if need_otp:
            # 使用邮件 API 等待验证码
            otp_code = self.wait_for_verification_email(
                mailbox_ref,
                not_before_ts=otp_started_at,
                exclude_message_ids=otp_seen_message_ids,
            )
            if not otp_code:
                raise Exception("未能获取验证码")

            _random_delay(0.3, 0.8)
            status, data = self.validate_otp(otp_code)
            if status != 200:
                self._print("验证码失败，重试...")
                otp_seen_message_ids = mail_message_id_set(self._fetch_emails_mail_api(mailbox_ref))
                self.send_otp()
                otp_started_at = time.time()
                _random_delay(1.0, 2.0)
                otp_code = self.wait_for_verification_email(
                    mailbox_ref,
                    timeout=OTP_WAIT_TIMEOUT_SECONDS,
                    not_before_ts=otp_started_at,
                    exclude_message_ids=otp_seen_message_ids,
                )
                if not otp_code:
                    raise Exception("重试后仍未获取验证码")
                _random_delay(0.3, 0.8)
                status, data = self.validate_otp(otp_code)
                if status != 200:
                    raise Exception(f"验证码失败 ({status}): {data}")

        _random_delay(0.5, 1.5)
        status, data = self.create_account(name, birthdate)
        if status != 200:
            raise Exception(f"Create account 失败 ({status}): {data}")
        _random_delay(0.2, 0.5)
        self.callback()
        return True

    def perform_codex_oauth_login_http(self, email: str, password: str, mailbox_ref: str = None):
        """通过 CodexOAuthClient 执行 OAuth 登录。AI by zb"""

        return self.oauth_client.perform_login(email, password, mailbox_ref=mailbox_ref)


# ==================== 并发批量注册 ====================

def _register_one(idx, total, proxy, output_file):
    """单个注册任务 (在线程中运行) - 使用邮件 API 创建邮箱"""
    pool = _get_proxy_pool(fallback_proxy=proxy) if PROXY_ENABLED else None
    last_error = "unknown error"

    for attempt in range(1, PROXY_RETRY_ATTEMPTS_PER_ACCOUNT + 1):
        if _stop_event.is_set():
            return False, None, "已手动停止"
        reg = None
        current_proxy = pool.next_proxy() if pool else None
        proxy_label = current_proxy or "direct"

        if PROXY_ENABLED and not current_proxy:
            last_error = "代理已启用，但当前没有可用代理 IP"
            with _print_lock:
                print(
                    f"\n[FAIL] [{idx}] 尝试 {attempt}/{PROXY_RETRY_ATTEMPTS_PER_ACCOUNT} "
                    f"失败: {last_error}"
                )
            if attempt >= PROXY_RETRY_ATTEMPTS_PER_ACCOUNT:
                break
            time.sleep(1)
            continue

        try:
            reg = ChatGPTRegister(
                proxy=current_proxy,
                fixed_proxy=current_proxy,
                tag=f"{idx}-try{attempt}",
            )
            reg._print(
                f"[Proxy] 尝试 {attempt}/{PROXY_RETRY_ATTEMPTS_PER_ACCOUNT}: {proxy_label}"
            )

            # 1. 创建邮件地址
            reg._print("[MailAPI] 创建临时邮箱...")
            email, email_pwd, mailbox_ref = reg.create_temp_email()
            tag = email.split("@")[0]
            reg.tag = tag  # 更新 tag

            chatgpt_password = _generate_password()
            name = _random_name()
            birthdate = _random_birthdate()

            with _print_lock:
                print(f"\n{'='*60}")
                print(f"  [{idx}/{total}] 注册: {email}")
                print(f"  ChatGPT密码: {chatgpt_password}")
                print(f"  邮箱凭据: {email_pwd}")
                print(f"  姓名: {name} | 生日: {birthdate}")
                print(f"  代理: {proxy_label}")
                print(f"{'='*60}")

            # 2. 执行注册流程
            reg.run_register(email, chatgpt_password, name, birthdate, mailbox_ref)

            # 3. OAuth（可选）
            oauth_ok = True
            if ENABLE_OAUTH:
                reg._print("[OAuth] 开始获取 Codex Token...")
                tokens = reg.perform_codex_oauth_login_http(email, chatgpt_password, mailbox_ref=mailbox_ref)
                oauth_ok = bool(tokens and tokens.get("access_token"))
                if oauth_ok:
                    _save_codex_tokens(email, tokens)
                    reg._print("[OAuth] Token 已保存")
                    if AUTO_UPLOAD_SUB2API and _sub2api_uploader.is_enabled() and tokens.get("refresh_token"):
                        reg._print("[Sub2Api] 正在上传账号...")
                        _sub2api_uploader.upload_account(email, tokens)
                else:
                    msg = "OAuth 获取失败"
                    if OAUTH_REQUIRED:
                        raise Exception(f"{msg}（oauth_required=true）")
                    reg._print(f"[OAuth] {msg}（按配置继续）")

            # 4. 成功后固定此代理（后续优先使用）
            if current_proxy and pool:
                pool.report_success(current_proxy)
                _save_stable_proxy_to_file(current_proxy)
                _save_stable_proxy_to_config(current_proxy)

            # 5. 线程安全写入结果
            with _file_lock:
                with open(output_file, "a", encoding="utf-8") as out:
                    out.write(
                        f"{email}----{chatgpt_password}----{email_pwd}"
                        f"----oauth={'ok' if oauth_ok else 'fail'}----proxy={proxy_label}\n"
                    )

            with _print_lock:
                print(f"\n[OK] [{tag}] {email} 注册成功! 代理: {proxy_label}")
            return True, email, None

        except OAuthPhoneRequiredError as e:
            last_error = str(e)
            with _print_lock:
                print(
                    f"\n[FAIL] [{idx}] 尝试 {attempt}/{PROXY_RETRY_ATTEMPTS_PER_ACCOUNT} "
                    f"终止: {last_error} | 代理: {proxy_label}"
                )
            return False, None, last_error
        except Exception as e:
            last_error = str(e)
            if current_proxy and pool:
                pool.report_bad(current_proxy, error=e)

            with _print_lock:
                print(
                    f"\n[FAIL] [{idx}] 尝试 {attempt}/{PROXY_RETRY_ATTEMPTS_PER_ACCOUNT} "
                    f"失败: {last_error} | 代理: {proxy_label}"
                )

            if attempt >= PROXY_RETRY_ATTEMPTS_PER_ACCOUNT:
                with _print_lock:
                    traceback.print_exc()
                break

    return False, None, f"代理重试耗尽: {last_error}"


def run_batch(total_accounts: int = 3, output_file="registered_accounts.txt",
              max_workers=3, proxy=None):
    """并发批量注册 - 邮件 API 版"""

    _stop_event.clear()

    if not DUCKMAIL_BEARER:
        print("❌ 错误: 未设置 duckmail_bearer(JWT_TOKEN) 环境变量")
        print("   请设置: export DUCKMAIL_BEARER='your_jwt_token'")
        print("   或: set DUCKMAIL_BEARER=your_jwt_token (Windows)")
        return

    actual_workers = min(max_workers, total_accounts)
    print(f"\n{'#'*60}")
    print(f"  ChatGPT 批量自动注册 (邮件 API 版)")
    print(f"  注册数量: {total_accounts} | 并发数: {actual_workers}")
    print(f"  邮件 API: {DUCKMAIL_API_BASE}")
    if PROXY_ENABLED:
        pool = _get_proxy_pool(fallback_proxy=proxy)
        pool.refresh(force=True)
        proxy_info = pool.info()
        print(f"  代理源: {proxy_info['list_url']}")
        print(f"  优先稳定代理: {'是' if proxy_info['prefer_stable_proxy'] else '否'}")
        print(f"  账号级代理重试: {PROXY_RETRY_ATTEMPTS_PER_ACCOUNT} 次/账号")
        print(
            f"  OTP 等待: 最多 {OTP_WAIT_TIMEOUT_SECONDS} 秒 | "
            f"轮询间隔: {OTP_POLL_INTERVAL_SECONDS} 秒 | 补发间隔: {OTP_RESEND_INTERVAL_SECONDS} 秒"
        )
        print(f"  代理校验: {'开启' if proxy_info['validate_enabled'] else '关闭'}")
        if proxy_info["validate_enabled"]:
            print(f"  校验目标: {proxy_info['validate_test_url']}")
            print(f"  校验超时: {proxy_info['validate_timeout_seconds']} 秒 | 校验并发: {proxy_info['validate_workers']}")
            print(f"  校验通过: {proxy_info['validated_count']}/{proxy_info['fetched_count']}")
        print(f"  代理池(HTTP/SOCKS): {proxy_info['count']} 个")
        print(f"  代理重试: 单请求最多 {proxy_info['max_retries_per_request']} 次")
        print(f"  失效冷却: {proxy_info['bad_ttl_seconds']} 秒")
        if proxy_info["bad_count"] > 0:
            print(f"  当前冷却代理: {proxy_info['bad_count']} 个")
        if proxy_info["fallback_proxy"]:
            print(f"  兜底代理: {proxy_info['fallback_proxy']}")
        if proxy_info["stable_proxy"]:
            print(f"  稳定代理: {proxy_info['stable_proxy']}")
        print(f"  稳定代理文件: {_stable_proxy_path()}")
        if proxy_info["last_error"]:
            print(f"  代理拉取告警: {proxy_info['last_error'][:200]}")
        has_any_proxy = bool(
            proxy_info["count"] > 0
            or proxy_info["fallback_proxy"]
            or proxy_info["stable_proxy"]
        )
        if not has_any_proxy:
            print("  ❌ 当前未拿到任何可用代理，已阻止直连运行")
            print(f"{'#'*60}\n")
            return
    else:
        print("  代理: 已关闭，当前以直连模式运行")
    print(f"  OAuth: {'开启' if ENABLE_OAUTH else '关闭'} | required: {'是' if OAUTH_REQUIRED else '否'}")
    print(
        f"  OTP 等待: 最多 {OTP_WAIT_TIMEOUT_SECONDS} 秒 | "
        f"轮询间隔: {OTP_POLL_INTERVAL_SECONDS} 秒 | 补发间隔: {OTP_RESEND_INTERVAL_SECONDS} 秒"
    )
    if ENABLE_OAUTH:
        print(f"  OAuth Issuer: {OAUTH_ISSUER}")
        print(f"  OAuth Client: {OAUTH_CLIENT_ID}")
        print(f"  Token输出: {TOKEN_JSON_DIR}/, {AK_FILE}, {RK_FILE}")
    print(f"  输出文件: {output_file}")
    print(f"{'#'*60}\n")

    success_count = 0
    fail_count = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=actual_workers) as executor:
        futures = {}
        for idx in range(1, total_accounts + 1):
            future = executor.submit(
                _register_one, idx, total_accounts, proxy, output_file
            )
            futures[future] = idx

        for future in as_completed(futures):
            idx = futures[future]
            try:
                ok, email, err = future.result()
                if ok:
                    success_count += 1
                else:
                    fail_count += 1
                    print(f"  [账号 {idx}] 失败: {err}")
            except Exception as e:
                fail_count += 1
                with _print_lock:
                    print(f"[FAIL] 账号 {idx} 线程异常: {e}")

    elapsed = time.time() - start_time
    avg = elapsed / total_accounts if total_accounts else 0
    print(f"\n{'#'*60}")
    print(f"  注册完成! 耗时 {elapsed:.1f} 秒")
    print(f"  总数: {total_accounts} | 成功: {success_count} | 失败: {fail_count}")
    print(f"  平均速度: {avg:.1f} 秒/个")
    if success_count > 0:
        print(f"  结果文件: {output_file}")
    print(f"{'#'*60}")


def main():
    print("=" * 60)
    print("  ChatGPT 批量自动注册工具 (邮件 API 版)")
    print("=" * 60)

    # 检查邮件 API 配置
    if not DUCKMAIL_BEARER:
        print("\n⚠️  警告: 未设置 duckmail_bearer(JWT_TOKEN)")
        print("   请编辑 config.json 设置 duckmail_bearer，或设置环境变量:")
        print("   可先执行: Copy-Item config.example.json config.json")
        print("   Windows: set DUCKMAIL_BEARER=your_jwt_token")
        print("   Linux/Mac: export DUCKMAIL_BEARER='your_jwt_token'")
        print("\n   按 Enter 继续尝试运行 (可能会失败)...")
        input()

    if PROXY_ENABLED:
        env_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") \
                 or os.environ.get("ALL_PROXY") or os.environ.get("all_proxy")
        default_fallback_proxy = _normalize_proxy(DEFAULT_PROXY)
        env_fallback_proxy = _normalize_proxy(env_proxy)
        proxy = default_fallback_proxy or env_fallback_proxy
        proxy_source = "config.json(proxy)" if default_fallback_proxy else (
            "环境变量(HTTPS_PROXY/ALL_PROXY)" if env_fallback_proxy else "未配置"
        )

        print(f"[Info] 代理池地址: {_normalize_proxy_list_url(PROXY_LIST_URL)}")
        print("[Info] 代理模式: 自动拉取 US 列表，使用 http/socks 代理并轮询")
        print(f"[Info] 列表默认协议: {_infer_proxy_list_scheme(PROXY_LIST_URL, PROXY_LIST_DEFAULT_SCHEME, PROXY_LIST_FETCH_PROXY, DEFAULT_PROXY)}")
        print(f"[Info] 代理校验: {'开启' if PROXY_VALIDATE_ENABLED else '关闭'} | 目标: {PROXY_VALIDATE_TEST_URL}")
        print(f"[Info] 列表自动刷新间隔: {PROXY_LIST_REFRESH_INTERVAL_SECONDS} 秒")
        print(f"[Info] 优先稳定代理开关: {'开启' if PREFER_STABLE_PROXY else '关闭'}")
        print(f"[Info] 账号失败自动换代理重试: {PROXY_RETRY_ATTEMPTS_PER_ACCOUNT} 次")
        if PROXY_LIST_FETCH_PROXY:
            print(f"[Info] 拉取代理列表时使用兜底代理: {_normalize_proxy(PROXY_LIST_FETCH_PROXY)}")
        if proxy:
            print(f"[Info] 兜底代理来源: {proxy_source} -> {proxy}")
        else:
            print("[Info] 未配置兜底代理，远端列表为空时将直连")
    else:
        proxy = None
        print("[Info] 代理模式: 已关闭，忽略 config 与环境变量代理")

    # 输入注册数量
    count_input = input(f"\n注册账号数量 (默认 {DEFAULT_TOTAL_ACCOUNTS}): ").strip()
    total_accounts = int(count_input) if count_input.isdigit() and int(count_input) > 0 else DEFAULT_TOTAL_ACCOUNTS

    workers_input = input("并发数 (默认 3): ").strip()
    max_workers = int(workers_input) if workers_input.isdigit() and int(workers_input) > 0 else 3

    run_batch(total_accounts=total_accounts, output_file=DEFAULT_OUTPUT_FILE,
              max_workers=max_workers, proxy=proxy)


if __name__ == "__main__":
    main()
