"""Sub2Api 账号上传模块。

@author AI by zb
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Any

from curl_cffi import requests as curl_requests

DEFAULT_MODEL_MAPPING = {
    "gpt-3.5-turbo": "gpt-3.5-turbo",
    "gpt-3.5-turbo-0125": "gpt-3.5-turbo-0125",
    "gpt-3.5-turbo-1106": "gpt-3.5-turbo-1106",
    "gpt-3.5-turbo-16k": "gpt-3.5-turbo-16k",
    "gpt-4": "gpt-4",
    "gpt-4-turbo": "gpt-4-turbo",
    "gpt-4-turbo-preview": "gpt-4-turbo-preview",
    "gpt-4o": "gpt-4o",
    "gpt-4o-2024-08-06": "gpt-4o-2024-08-06",
    "gpt-4o-2024-11-20": "gpt-4o-2024-11-20",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-4o-mini-2024-07-18": "gpt-4o-mini-2024-07-18",
    "gpt-4.5-preview": "gpt-4.5-preview",
    "gpt-4.1": "gpt-4.1",
    "gpt-4.1-mini": "gpt-4.1-mini",
    "gpt-4.1-nano": "gpt-4.1-nano",
    "o1": "o1",
    "o1-preview": "o1-preview",
    "o1-mini": "o1-mini",
    "o1-pro": "o1-pro",
    "o3": "o3",
    "o3-mini": "o3-mini",
    "o3-pro": "o3-pro",
    "o4-mini": "o4-mini",
    "gpt-5": "gpt-5",
    "gpt-5-2025-08-07": "gpt-5-2025-08-07",
    "gpt-5-chat": "gpt-5-chat",
    "gpt-5-chat-latest": "gpt-5-chat-latest",
    "gpt-5-codex": "gpt-5-codex",
    "gpt-5.3-codex-spark": "gpt-5.3-codex-spark",
    "gpt-5-pro": "gpt-5-pro",
    "gpt-5-pro-2025-10-06": "gpt-5-pro-2025-10-06",
    "gpt-5-mini": "gpt-5-mini",
    "gpt-5-mini-2025-08-07": "gpt-5-mini-2025-08-07",
    "gpt-5-nano": "gpt-5-nano",
    "gpt-5-nano-2025-08-07": "gpt-5-nano-2025-08-07",
    "gpt-5.1": "gpt-5.1",
    "gpt-5.1-2025-11-13": "gpt-5.1-2025-11-13",
    "gpt-5.1-chat-latest": "gpt-5.1-chat-latest",
    "gpt-5.1-codex": "gpt-5.1-codex",
    "gpt-5.1-codex-max": "gpt-5.1-codex-max",
    "gpt-5.1-codex-mini": "gpt-5.1-codex-mini",
    "gpt-5.2": "gpt-5.2",
    "gpt-5.2-2025-12-11": "gpt-5.2-2025-12-11",
    "gpt-5.2-chat-latest": "gpt-5.2-chat-latest",
    "gpt-5.2-codex": "gpt-5.2-codex",
    "gpt-5.2-pro": "gpt-5.2-pro",
    "gpt-5.2-pro-2025-12-11": "gpt-5.2-pro-2025-12-11",
    "gpt-5.4": "gpt-5.4",
    "gpt-5.4-2026-03-05": "gpt-5.4-2026-03-05",
    "gpt-5.3-codex": "gpt-5.3-codex",
    "chatgpt-4o-latest": "chatgpt-4o-latest",
    "gpt-4o-audio-preview": "gpt-4o-audio-preview",
    "gpt-4o-realtime-preview": "gpt-4o-realtime-preview",
}


@dataclass(slots=True, frozen=True)
class Sub2ApiConfig:
    """Sub2Api 上传配置。

    @author AI by zb
    @param base_url Sub2Api 服务地址。
    @param bearer 初始 Bearer Token。
    @param email Sub2Api 登录邮箱。
    @param password Sub2Api 登录密码。
    @param group_ids 账号归属分组列表。
    @param oauth_client_id OpenAI OAuth Client ID。
    """

    base_url: str
    bearer: str = ""
    email: str = ""
    password: str = ""
    group_ids: tuple[int, ...] = (2,)
    oauth_client_id: str = ""


class Sub2ApiUploader:
    """Sub2Api 账号上传器。

    @author AI by zb
    @param config 上传配置。
    @param jwt_payload_decoder JWT 载荷解析函数。
    @param logger 日志输出函数。
    """

    def __init__(
        self,
        config: Sub2ApiConfig,
        jwt_payload_decoder: Callable[[str], dict[str, Any]],
        logger: Callable[[str], None] | None = None,
    ):
        """初始化 Sub2Api 上传器运行时状态。AI by zb"""

        self.config = config
        self._jwt_payload_decoder = jwt_payload_decoder
        self._logger = logger or (lambda _message: None)
        self._bearer_holder = [config.bearer]
        self._auth_lock = Lock()

    def is_enabled(self) -> bool:
        """判断是否启用 Sub2Api 上传。AI by zb"""

        return bool(self.config.base_url)

    def _log(self, message: str) -> None:
        """输出 Sub2Api 相关日志。AI by zb"""

        self._logger(message)

    def _login(self) -> str:
        """登录 Sub2Api 并返回新的 bearer token。AI by zb"""

        if not self.config.base_url or not self.config.email or not self.config.password:
            return ""
        try:
            resp = curl_requests.post(
                f"{self.config.base_url}/api/v1/auth/login",
                json={"email": self.config.email, "password": self.config.password},
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                impersonate="chrome131",
                timeout=15,
            )
            data = resp.json()
            token = (
                data.get("token")
                or data.get("access_token")
                or (data.get("data") or {}).get("token")
                or (data.get("data") or {}).get("access_token")
                or ""
            )
            return str(token).strip()
        except Exception as exc:
            self._log(f"[Sub2Api] 登录失败: {exc}")
            return ""

    def _build_account_payload(self, email: str, tokens: dict[str, Any]) -> dict[str, Any]:
        """构建 Sub2Api 账号上传 payload。AI by zb"""

        access_token = tokens.get("access_token", "")
        refresh_token = tokens.get("refresh_token", "")
        id_token = tokens.get("id_token", "")

        access_payload = self._jwt_payload_decoder(access_token) if access_token else {}
        access_auth = access_payload.get("https://api.openai.com/auth") or {}
        chatgpt_account_id = access_auth.get("chatgpt_account_id", "") or tokens.get("account_id", "")
        chatgpt_user_id = access_auth.get("chatgpt_user_id", "")
        exp_timestamp = access_payload.get("exp", 0)
        expires_at = (
            exp_timestamp
            if isinstance(exp_timestamp, int) and exp_timestamp > 0
            else int(time.time()) + 863999
        )

        id_payload = self._jwt_payload_decoder(id_token) if id_token else {}
        id_auth = id_payload.get("https://api.openai.com/auth") or {}
        organization_id = id_auth.get("organization_id", "")
        if not organization_id:
            organizations = id_auth.get("organizations") or []
            if organizations:
                organization_id = (organizations[0] or {}).get("id", "")

        return {
            "auto_pause_on_expired": True,
            "concurrency": 10,
            "credentials": {
                "access_token": access_token,
                "chatgpt_account_id": chatgpt_account_id,
                "chatgpt_user_id": chatgpt_user_id,
                "client_id": self.config.oauth_client_id,
                "expires_in": 863999,
                "expires_at": expires_at,
                "model_mapping": DEFAULT_MODEL_MAPPING,
                "organization_id": organization_id,
                "refresh_token": refresh_token,
            },
            "extra": {
                "email": email,
                "openai_oauth_responses_websockets_v2_enabled": True,
                "openai_oauth_responses_websockets_v2_mode": "off",
            },
            "group_ids": list(self.config.group_ids),
            "name": email,
            "notes": "",
            "platform": "openai",
            "priority": 1,
            "type": "oauth",
            "rate_multiplier": 1,
        }

    def _post_account(self, bearer: str, payload: dict[str, Any]) -> tuple[int, str]:
        """向 Sub2Api 发起账号上传请求。AI by zb"""

        try:
            resp = curl_requests.post(
                f"{self.config.base_url}/api/v1/admin/accounts",
                json=payload,
                headers={
                    "Authorization": f"Bearer {bearer}",
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/plain, */*",
                    "Referer": f"{self.config.base_url}/admin/accounts",
                },
                impersonate="chrome131",
                timeout=20,
            )
            return resp.status_code, resp.text
        except Exception as exc:
            return 0, str(exc)

    def upload_account(self, email: str, tokens: dict[str, Any]) -> bool:
        """上传账号到 Sub2Api，必要时自动重登后重试一次。AI by zb"""

        if not self.config.base_url or not tokens.get("refresh_token"):
            return False

        payload = self._build_account_payload(email, tokens)
        bearer = self._bearer_holder[0]
        status, body = self._post_account(bearer, payload)

        if status == 401 and self.config.email and self.config.password:
            with self._auth_lock:
                if self._bearer_holder[0] == bearer:
                    new_token = self._login()
                    if new_token:
                        self._bearer_holder[0] = new_token
            bearer = self._bearer_holder[0]
            status, body = self._post_account(bearer, payload)

        ok = status in (200, 201)
        if ok:
            self._log(f"[Sub2Api] 上传成功 (HTTP {status})")
        else:
            self._log(f"[Sub2Api] 上传失败 (HTTP {status}): {body[:500]}")
        return ok
