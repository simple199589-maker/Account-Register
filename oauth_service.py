"""Codex OAuth 服务模块。

@author AI by zb
"""

from __future__ import annotations

import base64
import hashlib
import json
import random
import re
import secrets
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from mail_service import recent_mail_messages


def _extract_code_from_url(url: str) -> str | None:
    """从 URL 中提取 OAuth code。AI by zb"""

    if not url or "code=" not in url:
        return None
    try:
        return parse_qs(urlparse(url).query).get("code", [None])[0]
    except Exception:
        return None


def _generate_pkce() -> tuple[str, str]:
    """生成 OAuth PKCE 参数。AI by zb"""

    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


class SentinelTokenGenerator:
    """纯 Python 版本 sentinel token 生成器（PoW）。

    @author AI by zb
    """

    MAX_ATTEMPTS = 500000
    ERROR_PREFIX = "wQ8Lk5FbGpA2NcR9dShT6gYjU7VxZ4D"

    def __init__(self, device_id: str | None = None, user_agent: str | None = None):
        """初始化 Sentinel token 生成器。AI by zb"""

        self.device_id = device_id or str(uuid.uuid4())
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36"
        )
        self.requirements_seed = str(random.random())
        self.sid = str(uuid.uuid4())

    @staticmethod
    def _fnv1a_32(text: str) -> str:
        """计算 FNV1a 32 位哈希。AI by zb"""

        h = 2166136261
        for ch in text:
            h ^= ord(ch)
            h = (h * 16777619) & 0xFFFFFFFF
        h ^= (h >> 16)
        h = (h * 2246822507) & 0xFFFFFFFF
        h ^= (h >> 13)
        h = (h * 3266489909) & 0xFFFFFFFF
        h ^= (h >> 16)
        h &= 0xFFFFFFFF
        return format(h, "08x")

    def _get_config(self) -> list[Any]:
        """构造 Sentinel PoW 配置。AI by zb"""

        now_str = time.strftime(
            "%a %b %d %Y %H:%M:%S GMT+0000 (Coordinated Universal Time)",
            time.gmtime(),
        )
        perf_now = random.uniform(1000, 50000)
        time_origin = time.time() * 1000 - perf_now
        nav_prop = random.choice([
            "vendorSub", "productSub", "vendor", "maxTouchPoints",
            "scheduling", "userActivation", "doNotTrack", "geolocation",
            "connection", "plugins", "mimeTypes", "pdfViewerEnabled",
            "webkitTemporaryStorage", "webkitPersistentStorage",
            "hardwareConcurrency", "cookieEnabled", "credentials",
            "mediaDevices", "permissions", "locks", "ink",
        ])
        nav_val = f"{nav_prop}-undefined"

        return [
            "1920x1080",
            now_str,
            4294705152,
            random.random(),
            self.user_agent,
            "https://sentinel.openai.com/sentinel/20260124ceb8/sdk.js",
            None,
            None,
            "en-US",
            "en-US,en",
            random.random(),
            nav_val,
            random.choice(["location", "implementation", "URL", "documentURI", "compatMode"]),
            random.choice(["Object", "Function", "Array", "Number", "parseFloat", "undefined"]),
            perf_now,
            self.sid,
            "",
            random.choice([4, 8, 12, 16]),
            time_origin,
        ]

    @staticmethod
    def _base64_encode(data: Any) -> str:
        """编码 Sentinel 载荷。AI by zb"""

        raw = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return base64.b64encode(raw).decode("ascii")

    def _run_check(self, start_time: float, seed: str, difficulty: str, config: list[Any], nonce: int) -> str | None:
        """运行单次 Sentinel PoW 检查。AI by zb"""

        config[3] = nonce
        config[9] = round((time.time() - start_time) * 1000)
        data = self._base64_encode(config)
        hash_hex = self._fnv1a_32(seed + data)
        diff_len = len(difficulty)
        if hash_hex[:diff_len] <= difficulty:
            return data + "~S"
        return None

    def generate_token(self, seed: str | None = None, difficulty: str | None = None) -> str:
        """生成真正提交用的 Sentinel token。AI by zb"""

        normalized_seed = seed if seed is not None else self.requirements_seed
        normalized_difficulty = str(difficulty or "0")
        start_time = time.time()
        config = self._get_config()

        for i in range(self.MAX_ATTEMPTS):
            result = self._run_check(start_time, normalized_seed, normalized_difficulty, config, i)
            if result:
                return "gAAAAAB" + result
        return "gAAAAAB" + self.ERROR_PREFIX + self._base64_encode(str(None))

    def generate_requirements_token(self) -> str:
        """生成 requirements Sentinel token。AI by zb"""

        config = self._get_config()
        config[3] = 1
        config[9] = round(random.uniform(5, 50))
        data = self._base64_encode(config)
        return "gAAAAAC" + data


def fetch_sentinel_challenge(
    session,
    device_id: str,
    flow: str = "authorize_continue",
    user_agent: str | None = None,
    sec_ch_ua: str | None = None,
    impersonate: str | None = None,
) -> dict[str, Any] | None:
    """拉取 Sentinel challenge。AI by zb"""

    generator = SentinelTokenGenerator(device_id=device_id, user_agent=user_agent)
    req_body = {
        "p": generator.generate_requirements_token(),
        "id": device_id,
        "flow": flow,
    }
    headers = {
        "Content-Type": "text/plain;charset=UTF-8",
        "Referer": "https://sentinel.openai.com/backend-api/sentinel/frame.html",
        "Origin": "https://sentinel.openai.com",
        "User-Agent": user_agent or "Mozilla/5.0",
        "sec-ch-ua": sec_ch_ua or '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }
    kwargs = {
        "data": json.dumps(req_body),
        "headers": headers,
        "timeout": 20,
    }
    if impersonate:
        kwargs["impersonate"] = impersonate

    try:
        resp = session.post("https://sentinel.openai.com/backend-api/sentinel/req", **kwargs)
    except Exception:
        return None

    if resp.status_code != 200:
        return None

    try:
        data = resp.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def build_sentinel_token(
    session,
    device_id: str,
    flow: str = "authorize_continue",
    user_agent: str | None = None,
    sec_ch_ua: str | None = None,
    impersonate: str | None = None,
) -> str | None:
    """构造最终使用的 Sentinel token。AI by zb"""

    challenge = fetch_sentinel_challenge(
        session,
        device_id,
        flow=flow,
        user_agent=user_agent,
        sec_ch_ua=sec_ch_ua,
        impersonate=impersonate,
    )
    if not challenge:
        return None

    c_value = challenge.get("token", "")
    if not c_value:
        return None

    pow_data = challenge.get("proofofwork") or {}
    generator = SentinelTokenGenerator(device_id=device_id, user_agent=user_agent)
    if pow_data.get("required") and pow_data.get("seed"):
        p_value = generator.generate_token(
            seed=pow_data.get("seed"),
            difficulty=pow_data.get("difficulty", "0"),
        )
    else:
        p_value = generator.generate_requirements_token()

    return json.dumps({
        "p": p_value,
        "t": "",
        "c": c_value,
        "id": device_id,
        "flow": flow,
    }, separators=(",", ":"))


@dataclass(slots=True, frozen=True)
class CodexOAuthConfig:
    """Codex OAuth 配置。

    @author AI by zb
    @param issuer OAuth issuer 地址。
    @param client_id OAuth client id。
    @param redirect_uri OAuth redirect uri。
    @param base_url ChatGPT 基础地址。
    """

    issuer: str
    client_id: str
    redirect_uri: str
    base_url: str


class CodexOAuthClient:
    """Codex OAuth 协议客户端。

    @author AI by zb
    """

    def __init__(
        self,
        config: CodexOAuthConfig,
        session,
        mail_client,
        logger: Callable[[str], None],
        trace_headers_factory: Callable[[], dict[str, str]],
        user_agent: str,
        device_id: str,
        sec_ch_ua: str,
        impersonate: str,
        otp_wait_timeout_seconds: int = 120,
        otp_poll_interval_seconds: float = 3.0,
    ):
        """初始化 Codex OAuth 客户端。AI by zb"""

        self.config = config
        self.session = session
        self.mail_client = mail_client
        self._logger = logger
        self._trace_headers_factory = trace_headers_factory
        self.user_agent = user_agent
        self.device_id = device_id
        self.sec_ch_ua = sec_ch_ua
        self.impersonate = impersonate
        self.otp_wait_timeout_seconds = max(60, int(otp_wait_timeout_seconds))
        self.otp_poll_interval_seconds = max(1.0, float(otp_poll_interval_seconds))

    def _log(self, message: str) -> None:
        """输出 OAuth 日志。AI by zb"""

        self._logger(message)

    def _oauth_json_headers(self, referer: str) -> dict[str, str]:
        """构造 OAuth JSON 请求头。AI by zb"""

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": self.config.issuer,
            "Referer": referer,
            "User-Agent": self.user_agent,
            "oai-device-id": self.device_id,
        }
        headers.update(self._trace_headers_factory())
        return headers

    def _decode_oauth_session_cookie(self) -> dict[str, Any] | None:
        """解析 OAuth session cookie。AI by zb"""

        jar = getattr(self.session.cookies, "jar", None)
        cookie_items = list(jar) if jar is not None else []

        for cookie in cookie_items:
            name = getattr(cookie, "name", "") or ""
            if "oai-client-auth-session" not in name:
                continue

            raw_val = (getattr(cookie, "value", "") or "").strip()
            if not raw_val:
                continue

            candidates = [raw_val]
            try:
                from urllib.parse import unquote

                decoded = unquote(raw_val)
                if decoded != raw_val:
                    candidates.append(decoded)
            except Exception:
                pass

            for val in candidates:
                try:
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]

                    part = val.split(".")[0] if "." in val else val
                    pad = 4 - len(part) % 4
                    if pad != 4:
                        part += "=" * pad
                    raw = base64.urlsafe_b64decode(part)
                    data = json.loads(raw.decode("utf-8"))
                    if isinstance(data, dict):
                        return data
                except Exception:
                    continue
        return None

    def _allow_redirect_extract_code(self, url: str, referer: str | None = None) -> str | None:
        """允许自动跳转并尝试提取 OAuth code。AI by zb"""

        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": self.user_agent,
        }
        if referer:
            headers["Referer"] = referer

        try:
            resp = self.session.get(
                url,
                headers=headers,
                allow_redirects=True,
                timeout=30,
                impersonate=self.impersonate,
            )
            final_url = str(resp.url)
            code = _extract_code_from_url(final_url)
            if code:
                self._log("[OAuth] allow_redirect 命中最终 URL code")
                return code

            for item in getattr(resp, "history", []) or []:
                loc = item.headers.get("Location", "")
                code = _extract_code_from_url(loc)
                if code:
                    self._log("[OAuth] allow_redirect 命中 history Location code")
                    return code
                code = _extract_code_from_url(str(item.url))
                if code:
                    self._log("[OAuth] allow_redirect 命中 history URL code")
                    return code
        except Exception as exc:
            maybe_localhost = re.search(r'(https?://localhost[^\s\'\"]+)', str(exc))
            if maybe_localhost:
                code = _extract_code_from_url(maybe_localhost.group(1))
                if code:
                    self._log("[OAuth] allow_redirect 从 localhost 异常提取 code")
                    return code
            self._log(f"[OAuth] allow_redirect 异常: {exc}")

        return None

    def _follow_for_code(self, start_url: str, referer: str | None = None, max_hops: int = 16) -> tuple[str | None, str]:
        """手动跟随跳转并提取 OAuth code。AI by zb"""

        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": self.user_agent,
        }
        if referer:
            headers["Referer"] = referer

        current_url = start_url
        last_url = start_url
        for hop in range(max_hops):
            try:
                resp = self.session.get(
                    current_url,
                    headers=headers,
                    allow_redirects=False,
                    timeout=30,
                    impersonate=self.impersonate,
                )
            except Exception as exc:
                maybe_localhost = re.search(r'(https?://localhost[^\s\'\"]+)', str(exc))
                if maybe_localhost:
                    code = _extract_code_from_url(maybe_localhost.group(1))
                    if code:
                        self._log(f"[OAuth] follow[{hop + 1}] 命中 localhost 回调")
                        return code, maybe_localhost.group(1)
                self._log(f"[OAuth] follow[{hop + 1}] 请求异常: {exc}")
                return None, last_url

            last_url = str(resp.url)
            self._log(f"[OAuth] follow[{hop + 1}] {resp.status_code} {last_url[:140]}")
            code = _extract_code_from_url(last_url)
            if code:
                return code, last_url

            if resp.status_code in (301, 302, 303, 307, 308):
                loc = resp.headers.get("Location", "")
                if not loc:
                    return None, last_url
                if loc.startswith("/"):
                    loc = f"{self.config.issuer}{loc}"
                code = _extract_code_from_url(loc)
                if code:
                    return code, loc
                current_url = loc
                headers["Referer"] = last_url
                continue

            return None, last_url

        return None, last_url

    def _submit_workspace_and_org(self, consent_url: str) -> str | None:
        """处理 OAuth consent 阶段的 workspace 和组织选择。AI by zb"""

        session_data = self._decode_oauth_session_cookie()
        if not session_data:
            jar = getattr(self.session.cookies, "jar", None)
            if jar is not None:
                cookie_names = [getattr(cookie, "name", "") for cookie in list(jar)]
            else:
                cookie_names = list(self.session.cookies.keys())
            self._log(f"[OAuth] 无法解码 oai-client-auth-session, cookies={cookie_names[:12]}")
            return None

        workspaces = session_data.get("workspaces", [])
        if not workspaces:
            self._log("[OAuth] session 中没有 workspace 信息")
            return None

        workspace_id = (workspaces[0] or {}).get("id")
        if not workspace_id:
            self._log("[OAuth] workspace_id 为空")
            return None

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": self.config.issuer,
            "Referer": consent_url,
            "User-Agent": self.user_agent,
            "oai-device-id": self.device_id,
        }
        headers.update(self._trace_headers_factory())

        resp = self.session.post(
            f"{self.config.issuer}/api/accounts/workspace/select",
            json={"workspace_id": workspace_id},
            headers=headers,
            allow_redirects=False,
            timeout=30,
            impersonate=self.impersonate,
        )
        self._log(f"[OAuth] workspace/select -> {resp.status_code}")

        if resp.status_code in (301, 302, 303, 307, 308):
            loc = resp.headers.get("Location", "")
            if loc.startswith("/"):
                loc = f"{self.config.issuer}{loc}"
            code = _extract_code_from_url(loc)
            if code:
                return code
            code, _ = self._follow_for_code(loc, referer=consent_url)
            if not code:
                code = self._allow_redirect_extract_code(loc, referer=consent_url)
            return code

        if resp.status_code != 200:
            self._log(f"[OAuth] workspace/select 失败: {resp.status_code}")
            return None

        try:
            ws_data = resp.json()
        except Exception:
            self._log("[OAuth] workspace/select 响应不是 JSON")
            return None

        ws_next = ws_data.get("continue_url", "")
        orgs = ws_data.get("data", {}).get("orgs", [])
        ws_page = (ws_data.get("page") or {}).get("type", "")
        self._log(f"[OAuth] workspace/select page={ws_page or '-'} next={(ws_next or '-')[:140]}")

        org_id = None
        project_id = None
        if orgs:
            org_id = (orgs[0] or {}).get("id")
            projects = (orgs[0] or {}).get("projects", [])
            if projects:
                project_id = (projects[0] or {}).get("id")

        if org_id:
            org_body = {"org_id": org_id}
            if project_id:
                org_body["project_id"] = project_id

            h_org = dict(headers)
            if ws_next:
                h_org["Referer"] = ws_next if ws_next.startswith("http") else f"{self.config.issuer}{ws_next}"

            resp_org = self.session.post(
                f"{self.config.issuer}/api/accounts/organization/select",
                json=org_body,
                headers=h_org,
                allow_redirects=False,
                timeout=30,
                impersonate=self.impersonate,
            )
            self._log(f"[OAuth] organization/select -> {resp_org.status_code}")

            if resp_org.status_code in (301, 302, 303, 307, 308):
                loc = resp_org.headers.get("Location", "")
                if loc.startswith("/"):
                    loc = f"{self.config.issuer}{loc}"
                code = _extract_code_from_url(loc)
                if code:
                    return code
                code, _ = self._follow_for_code(loc, referer=h_org.get("Referer"))
                if not code:
                    code = self._allow_redirect_extract_code(loc, referer=h_org.get("Referer"))
                return code

            if resp_org.status_code == 200:
                try:
                    org_data = resp_org.json()
                except Exception:
                    self._log("[OAuth] organization/select 响应不是 JSON")
                    return None

                org_next = org_data.get("continue_url", "")
                org_page = (org_data.get("page") or {}).get("type", "")
                self._log(f"[OAuth] organization/select page={org_page or '-'} next={(org_next or '-')[:140]}")
                if org_next:
                    if org_next.startswith("/"):
                        org_next = f"{self.config.issuer}{org_next}"
                    code, _ = self._follow_for_code(org_next, referer=h_org.get("Referer"))
                    if not code:
                        code = self._allow_redirect_extract_code(org_next, referer=h_org.get("Referer"))
                    return code

        if ws_next:
            if ws_next.startswith("/"):
                ws_next = f"{self.config.issuer}{ws_next}"
            code, _ = self._follow_for_code(ws_next, referer=consent_url)
            if not code:
                code = self._allow_redirect_extract_code(ws_next, referer=consent_url)
            return code

        return None

    def _bootstrap_session(self, authorize_url: str, authorize_params: dict[str, str]) -> tuple[bool, str]:
        """初始化 OAuth 会话，获取 login_session。AI by zb"""

        self._log("[OAuth] 1/7 GET /oauth/authorize")
        try:
            resp = self.session.get(
                authorize_url,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Referer": f"{self.config.base_url}/",
                    "Upgrade-Insecure-Requests": "1",
                    "User-Agent": self.user_agent,
                },
                allow_redirects=True,
                timeout=30,
                impersonate=self.impersonate,
            )
        except Exception as exc:
            self._log(f"[OAuth] /oauth/authorize 异常: {exc}")
            return False, ""

        final_url = str(resp.url)
        redirects = len(getattr(resp, "history", []) or [])
        self._log(f"[OAuth] /oauth/authorize -> {resp.status_code}, final={(final_url or '-')[:140]}, redirects={redirects}")

        has_login = any(getattr(cookie, "name", "") == "login_session" for cookie in self.session.cookies)
        self._log(f"[OAuth] login_session: {'已获取' if has_login else '未获取'}")

        if not has_login:
            self._log("[OAuth] 未拿到 login_session，尝试访问 oauth2 auth 入口")
            oauth2_url = f"{self.config.issuer}/api/oauth/oauth2/auth"
            try:
                resp2 = self.session.get(
                    oauth2_url,
                    headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Referer": authorize_url,
                        "Upgrade-Insecure-Requests": "1",
                        "User-Agent": self.user_agent,
                    },
                    params=authorize_params,
                    allow_redirects=True,
                    timeout=30,
                    impersonate=self.impersonate,
                )
                final_url = str(resp2.url)
                redirects2 = len(getattr(resp2, "history", []) or [])
                self._log(f"[OAuth] /api/oauth/oauth2/auth -> {resp2.status_code}, final={(final_url or '-')[:140]}, redirects={redirects2}")
            except Exception as exc:
                self._log(f"[OAuth] /api/oauth/oauth2/auth 异常: {exc}")

            has_login = any(getattr(cookie, "name", "") == "login_session" for cookie in self.session.cookies)
            self._log(f"[OAuth] login_session(重试): {'已获取' if has_login else '未获取'}")

        return has_login, final_url

    def _post_authorize_continue(self, referer_url: str, email: str):
        """提交 authorize continue。AI by zb"""

        sentinel_authorize = build_sentinel_token(
            self.session,
            self.device_id,
            flow="authorize_continue",
            user_agent=self.user_agent,
            sec_ch_ua=self.sec_ch_ua,
            impersonate=self.impersonate,
        )
        if not sentinel_authorize:
            self._log("[OAuth] authorize_continue 的 sentinel token 获取失败")
            return None

        headers = self._oauth_json_headers(referer_url)
        headers["openai-sentinel-token"] = sentinel_authorize
        try:
            return self.session.post(
                f"{self.config.issuer}/api/accounts/authorize/continue",
                json={"username": {"kind": "email", "value": email}},
                headers=headers,
                timeout=30,
                allow_redirects=False,
                impersonate=self.impersonate,
            )
        except Exception as exc:
            self._log(f"[OAuth] authorize/continue 异常: {exc}")
            return None

    def perform_login(self, email: str, password: str, mailbox_ref: str | None = None) -> dict[str, Any] | None:
        """执行 Codex OAuth 纯协议登录。AI by zb"""

        self._log("[OAuth] 开始执行 Codex OAuth 纯协议流程...")
        self.session.cookies.set("oai-did", self.device_id, domain=".auth.openai.com")
        self.session.cookies.set("oai-did", self.device_id, domain="auth.openai.com")

        code_verifier, code_challenge = _generate_pkce()
        state = secrets.token_urlsafe(24)
        authorize_params = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": "openid profile email offline_access",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        authorize_url = f"{self.config.issuer}/oauth/authorize?{urlencode(authorize_params)}"

        _has_login_session, authorize_final_url = self._bootstrap_session(authorize_url, authorize_params)
        if not authorize_final_url:
            return None

        continue_referer = (
            authorize_final_url if authorize_final_url.startswith(self.config.issuer)
            else f"{self.config.issuer}/log-in"
        )

        self._log("[OAuth] 2/7 POST /api/accounts/authorize/continue")
        resp_continue = self._post_authorize_continue(continue_referer, email)
        if resp_continue is None:
            return None

        self._log(f"[OAuth] /authorize/continue -> {resp_continue.status_code}")
        if resp_continue.status_code == 400 and "invalid_auth_step" in (resp_continue.text or ""):
            self._log("[OAuth] invalid_auth_step，重新 bootstrap 后重试一次")
            _has_login_session, authorize_final_url = self._bootstrap_session(authorize_url, authorize_params)
            if not authorize_final_url:
                return None
            continue_referer = (
                authorize_final_url if authorize_final_url.startswith(self.config.issuer)
                else f"{self.config.issuer}/log-in"
            )
            resp_continue = self._post_authorize_continue(continue_referer, email)
            if resp_continue is None:
                return None
            self._log(f"[OAuth] /authorize/continue(重试) -> {resp_continue.status_code}")

        if resp_continue.status_code != 200:
            self._log(f"[OAuth] 邮箱提交失败: {resp_continue.text[:180]}")
            return None

        try:
            continue_data = resp_continue.json()
        except Exception:
            self._log("[OAuth] authorize/continue 响应解析失败")
            return None

        continue_url = continue_data.get("continue_url", "")
        page_type = (continue_data.get("page") or {}).get("type", "")
        self._log(f"[OAuth] continue page={page_type or '-'} next={(continue_url or '-')[:140]}")

        self._log("[OAuth] 3/7 POST /api/accounts/password/verify")
        sentinel_pwd = build_sentinel_token(
            self.session,
            self.device_id,
            flow="password_verify",
            user_agent=self.user_agent,
            sec_ch_ua=self.sec_ch_ua,
            impersonate=self.impersonate,
        )
        if not sentinel_pwd:
            self._log("[OAuth] password_verify 的 sentinel token 获取失败")
            return None

        headers_verify = self._oauth_json_headers(f"{self.config.issuer}/log-in/password")
        headers_verify["openai-sentinel-token"] = sentinel_pwd
        try:
            resp_verify = self.session.post(
                f"{self.config.issuer}/api/accounts/password/verify",
                json={"password": password},
                headers=headers_verify,
                timeout=30,
                allow_redirects=False,
                impersonate=self.impersonate,
            )
        except Exception as exc:
            self._log(f"[OAuth] password/verify 异常: {exc}")
            return None

        self._log(f"[OAuth] /password/verify -> {resp_verify.status_code}")
        if resp_verify.status_code != 200:
            self._log(f"[OAuth] 密码校验失败: {resp_verify.text[:180]}")
            return None

        try:
            verify_data = resp_verify.json()
        except Exception:
            self._log("[OAuth] password/verify 响应解析失败")
            return None

        continue_url = verify_data.get("continue_url", "") or continue_url
        page_type = (verify_data.get("page") or {}).get("type", "") or page_type
        self._log(f"[OAuth] verify page={page_type or '-'} next={(continue_url or '-')[:140]}")

        need_oauth_otp = (
            page_type == "email_otp_verification"
            or "email-verification" in (continue_url or "")
            or "email-otp" in (continue_url or "")
        )

        if need_oauth_otp:
            self._log("[OAuth] 4/7 检测到邮箱 OTP 验证")
            if not mailbox_ref:
                self._log("[OAuth] OAuth 阶段需要邮箱 OTP，但未提供 mailbox_ref")
                return None

            headers_otp = self._oauth_json_headers(f"{self.config.issuer}/email-verification")
            tried_codes: set[str] = set()
            otp_success = False
            otp_deadline = time.time() + self.otp_wait_timeout_seconds
            otp_not_before_ts = time.time()

            while time.time() < otp_deadline and not otp_success:
                messages = recent_mail_messages(
                    self.mail_client.fetch_emails(mailbox_ref) or [],
                    not_before_ts=otp_not_before_ts,
                )
                candidate_codes: list[str] = []
                round_seen: set[str] = set()

                for msg in messages[:12]:
                    code = str(msg.get("verification_code") or "").strip()
                    if (
                        re.fullmatch(r"\d{6}", code)
                        and code != "177010"
                        and code not in tried_codes
                        and code not in round_seen
                    ):
                        candidate_codes.append(code)
                        round_seen.add(code)

                    msg_id = msg.get("id") or msg.get("@id")
                    if not msg_id:
                        continue
                    detail = self.mail_client.fetch_email_detail(mailbox_ref, msg_id)
                    if not detail:
                        continue

                    code = str(detail.get("verification_code") or "").strip()
                    if (
                        re.fullmatch(r"\d{6}", code)
                        and code != "177010"
                        and code not in tried_codes
                        and code not in round_seen
                    ):
                        candidate_codes.append(code)
                        round_seen.add(code)
                        continue

                    content = (
                        detail.get("content")
                        or detail.get("html_content")
                        or detail.get("text")
                        or detail.get("html")
                        or detail.get("preview")
                        or msg.get("preview")
                        or ""
                    )
                    code = self.mail_client.extract_verification_code(content)
                    if code and code not in tried_codes and code not in round_seen:
                        candidate_codes.append(code)
                        round_seen.add(code)

                if not candidate_codes:
                    elapsed = int(self.otp_wait_timeout_seconds - max(0, otp_deadline - time.time()))
                    self._log(f"[OAuth] OTP 等待中... ({elapsed}s/{self.otp_wait_timeout_seconds}s)")
                    time.sleep(self.otp_poll_interval_seconds)
                    continue

                for otp_code in candidate_codes:
                    tried_codes.add(otp_code)
                    self._log(f"[OAuth] 尝试 OTP: {otp_code}")
                    try:
                        resp_otp = self.session.post(
                            f"{self.config.issuer}/api/accounts/email-otp/validate",
                            json={"code": otp_code},
                            headers=headers_otp,
                            timeout=30,
                            allow_redirects=False,
                            impersonate=self.impersonate,
                        )
                    except Exception as exc:
                        self._log(f"[OAuth] email-otp/validate 异常: {exc}")
                        continue

                    self._log(f"[OAuth] /email-otp/validate -> {resp_otp.status_code}")
                    if resp_otp.status_code != 200:
                        self._log(f"[OAuth] OTP 无效，继续尝试下一条: {resp_otp.text[:160]}")
                        continue

                    try:
                        otp_data = resp_otp.json()
                    except Exception:
                        self._log("[OAuth] email-otp/validate 响应解析失败")
                        continue

                    continue_url = otp_data.get("continue_url", "") or continue_url
                    page_type = (otp_data.get("page") or {}).get("type", "") or page_type
                    self._log(f"[OAuth] OTP 验证通过 page={page_type or '-'} next={(continue_url or '-')[:140]}")
                    otp_success = True
                    break

                if not otp_success:
                    time.sleep(self.otp_poll_interval_seconds)

            if not otp_success:
                self._log(f"[OAuth] OAuth 阶段 OTP 验证失败，已尝试 {len(tried_codes)} 个验证码")
                return None

        code = None
        consent_url = continue_url
        if consent_url and consent_url.startswith("/"):
            consent_url = f"{self.config.issuer}{consent_url}"

        if not consent_url and "consent" in page_type:
            consent_url = f"{self.config.issuer}/sign-in-with-chatgpt/codex/consent"

        if consent_url:
            code = _extract_code_from_url(consent_url)

        if not code and consent_url:
            self._log("[OAuth] 5/7 跟随 continue_url 提取 code")
            code, _ = self._follow_for_code(consent_url, referer=f"{self.config.issuer}/log-in/password")

        consent_hint = (
            ("consent" in (consent_url or ""))
            or ("sign-in-with-chatgpt" in (consent_url or ""))
            or ("workspace" in (consent_url or ""))
            or ("organization" in (consent_url or ""))
            or ("consent" in page_type)
            or ("organization" in page_type)
        )

        if not code and consent_hint:
            if not consent_url:
                consent_url = f"{self.config.issuer}/sign-in-with-chatgpt/codex/consent"
            self._log("[OAuth] 6/7 执行 workspace/org 选择")
            code = self._submit_workspace_and_org(consent_url)

        if not code:
            fallback_consent = f"{self.config.issuer}/sign-in-with-chatgpt/codex/consent"
            self._log("[OAuth] 6/7 回退 consent 路径重试")
            code = self._submit_workspace_and_org(fallback_consent)
            if not code:
                code, _ = self._follow_for_code(fallback_consent, referer=f"{self.config.issuer}/log-in/password")

        if not code:
            self._log("[OAuth] 未获取到 authorization code")
            return None

        self._log("[OAuth] 7/7 POST /oauth/token")
        token_resp = self.session.post(
            f"{self.config.issuer}/oauth/token",
            headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": self.user_agent},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.config.redirect_uri,
                "client_id": self.config.client_id,
                "code_verifier": code_verifier,
            },
            timeout=60,
            impersonate=self.impersonate,
        )
        self._log(f"[OAuth] /oauth/token -> {token_resp.status_code}")

        if token_resp.status_code != 200:
            self._log(f"[OAuth] token 交换失败: {token_resp.status_code} {token_resp.text[:200]}")
            return None

        try:
            data = token_resp.json()
        except Exception:
            self._log("[OAuth] token 响应解析失败")
            return None

        if not data.get("access_token"):
            self._log("[OAuth] token 响应缺少 access_token")
            return None

        self._log("[OAuth] Codex Token 获取成功")
        return data
