"""DuckMail 邮箱服务模块。

@author AI by zb
"""

from __future__ import annotations

import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from curl_cffi import requests as curl_requests


@dataclass(slots=True, frozen=True)
class MailApiConfig:
    """邮件 API 配置。

    @author AI by zb
    @param base_url 邮件 API 基础地址。
    @param bearer 邮件 API 认证 Bearer。
    @param use_proxy 是否启用代理。
    """

    base_url: str
    bearer: str
    use_proxy: bool = True


def _mail_api_url(base_url: str, path: str) -> str:
    """构造邮件 API 完整地址。AI by zb"""

    api_base = base_url.rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    if api_base.endswith("/api"):
        return f"{api_base}{suffix}"
    return f"{api_base}/api{suffix}"


def _mail_api_headers(bearer: str) -> dict[str, str]:
    """构造邮件 API 认证头。AI by zb"""

    return {
        "Authorization": f"Bearer {bearer}",
        "X-Admin-Token": bearer,
    }


def _mail_message_sort_key(message: dict[str, Any]) -> tuple[float, int]:
    """按接收时间和 ID 生成排序键，优先最新邮件。AI by zb"""

    raw = str(
        message.get("received_at")
        or message.get("created_at")
        or message.get("date")
        or ""
    ).strip()
    ts = 0.0
    if raw:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
            try:
                dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
                ts = dt.timestamp()
                break
            except Exception:
                continue
        if not ts:
            for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
                try:
                    ts = datetime.strptime(raw, fmt).timestamp()
                    break
                except Exception:
                    continue
        if not ts:
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                ts = dt.timestamp()
            except Exception:
                ts = 0.0

    raw_id = message.get("id") or message.get("@id") or 0
    try:
        msg_id = int(str(raw_id).rsplit("/", 1)[-1])
    except Exception:
        msg_id = 0
    return (ts, msg_id)


def _mail_message_identity(message: dict[str, Any]) -> str:
    """提取邮件唯一标识，优先使用邮件 ID。AI by zb"""

    raw_id = message.get("id") or message.get("@id")
    return str(raw_id).strip() if raw_id is not None else ""


def mail_message_id_set(messages: list[dict[str, Any]] | None) -> set[str]:
    """提取邮件列表中的 ID 集合。AI by zb"""

    result: set[str] = set()
    if not isinstance(messages, list):
        return result
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        identity = _mail_message_identity(msg)
        if identity:
            result.add(identity)
    return result


def _sort_mail_messages(messages: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """按最新优先排序邮件列表。AI by zb"""

    if not isinstance(messages, list):
        return []
    return sorted(
        [msg for msg in messages if isinstance(msg, dict)],
        key=_mail_message_sort_key,
        reverse=True,
    )


def recent_mail_messages(
    messages: list[dict[str, Any]] | None,
    not_before_ts: float | None = None,
    slack_seconds: int = 8,
    exclude_message_ids: set[str] | list[str] | None = None,
) -> list[dict[str, Any]]:
    """筛选指定时间后的邮件，优先避免误用旧验证码。AI by zb"""

    ordered = _sort_mail_messages(messages)
    excluded = set(exclude_message_ids or [])
    if not not_before_ts and not excluded:
        return ordered

    threshold = float(not_before_ts) - max(0, int(slack_seconds))
    recent: list[dict[str, Any]] = []
    for msg in ordered:
        identity = _mail_message_identity(msg)
        if identity and identity in excluded:
            continue
        if not not_before_ts:
            recent.append(msg)
            continue
        msg_ts, _ = _mail_message_sort_key(msg)
        if msg_ts <= 0:
            continue
        if msg_ts >= threshold:
            recent.append(msg)
    return recent


class DuckMailClient:
    """DuckMail 邮箱服务客户端。

    @author AI by zb
    @param config 邮箱配置。
    @param user_agent 请求使用的 User-Agent。
    @param impersonate curl_cffi 模拟浏览器标识。
    @param session_preparer 会话预处理函数。
    @param logger 日志输出函数。
    """

    def __init__(
        self,
        config: MailApiConfig,
        user_agent: str,
        impersonate: str = "chrome131",
        session_preparer: Callable[[Any], Any] | None = None,
        logger: Callable[[str], None] | None = None,
    ):
        """初始化 DuckMail 客户端。AI by zb"""

        self.config = config
        self.user_agent = user_agent
        self.impersonate = impersonate
        self._session_preparer = session_preparer
        self._logger = logger or (lambda _message: None)

    def _log(self, message: str) -> None:
        """输出邮件服务相关日志。AI by zb"""

        self._logger(message)

    def _create_session(self):
        """创建邮件 API 请求会话。AI by zb"""

        session = curl_requests.Session()
        session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        if self.config.use_proxy and self._session_preparer:
            prepared = self._session_preparer(session)
            return prepared if prepared is not None else session
        session.trust_env = False
        return session

    def create_temp_email(self) -> tuple[str, str, str]:
        """创建邮件地址，返回 (email, password, mailbox_ref)。AI by zb"""

        if not self.config.bearer:
            raise Exception("duckmail_bearer(JWT_TOKEN) 未设置，无法创建临时邮箱")

        session = self._create_session()
        try:
            # domainIndex
            res = session.get(
                _mail_api_url(self.config.base_url, "/generate"),
                params={"length": random.randint(8, 13), "mode": "human", "domainIndex": random.choice([1, 2, 3,4])},
                headers=_mail_api_headers(self.config.bearer),
                timeout=15,
                impersonate=self.impersonate,
            )

            if res.status_code != 200:
                raise Exception(f"创建邮箱失败: {res.status_code} - {res.text[:200]}")

            data = res.json()
            email = data.get("email") or (data.get("data") or {}).get("email") or ""
            if email:
                return email, "N/A", email
            raise Exception(f"创建邮箱响应缺少 email: {str(data)[:200]}")
        except Exception as exc:
            raise Exception(f"邮件 API 创建邮箱失败: {exc}")

    def fetch_emails(self, mailbox_ref: str) -> list[dict[str, Any]]:
        """按邮箱地址获取邮件列表。AI by zb"""

        try:
            session = self._create_session()
            res = session.get(
                _mail_api_url(self.config.base_url, "/emails"),
                params={"mailbox": mailbox_ref, "limit": 20},
                headers=_mail_api_headers(self.config.bearer),
                timeout=15,
                impersonate=self.impersonate,
            )
            if res.status_code != 200:
                return []
            data = res.json()
            if isinstance(data, list):
                return [msg for msg in data if isinstance(msg, dict)]
            messages = data.get("data") or data.get("items") or []
            return [msg for msg in messages if isinstance(msg, dict)] if isinstance(messages, list) else []
        except Exception:
            return []

    def fetch_email_detail(self, mailbox_ref: str, msg_id: str) -> dict[str, Any] | None:
        """获取单封邮件详情。AI by zb"""

        _ = mailbox_ref
        try:
            session = self._create_session()
            normalized_msg_id = msg_id.rsplit("/", 1)[-1] if isinstance(msg_id, str) else str(msg_id)
            res = session.get(
                _mail_api_url(self.config.base_url, f"/email/{normalized_msg_id}"),
                headers=_mail_api_headers(self.config.bearer),
                timeout=15,
                impersonate=self.impersonate,
            )
            if res.status_code == 200:
                data = res.json()
                return data if isinstance(data, dict) else None
        except Exception:
            pass
        return None

    def extract_verification_code(self, email_content: str) -> str | None:
        """从邮件内容提取 6 位验证码。AI by zb"""

        if not email_content:
            return None

        patterns = [
            r"Verification code:?\s*(\d{6})",
            r"code is\s*(\d{6})",
            r"代码为[:：]?\s*(\d{6})",
            r"验证码[:：]?\s*(\d{6})",
            r">\s*(\d{6})\s*<",
            r"(?<![#&])\b(\d{6})\b",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, email_content, re.IGNORECASE)
            for code in matches:
                if code == "177010":
                    continue
                return code
        return None

    def wait_for_verification_email(
        self,
        mailbox_ref: str,
        timeout: int = 120,
        not_before_ts: float | None = None,
        exclude_message_ids: set[str] | list[str] | None = None,
        poll_interval_seconds: float = 3.0,
    ) -> str | None:
        """等待并提取 OpenAI 验证码。AI by zb"""

        self._log(f"[OTP] 等待验证码邮件 (最多 {timeout}s)...")
        start_time = time.time()
        normalized_poll_interval = max(1.0, float(poll_interval_seconds))

        while time.time() - start_time < timeout:
            messages = recent_mail_messages(
                self.fetch_emails(mailbox_ref),
                not_before_ts=not_before_ts,
                exclude_message_ids=exclude_message_ids,
            )
            if messages:
                for msg in messages[:12]:
                    code = str(msg.get("verification_code") or "").strip()
                    if re.fullmatch(r"\d{6}", code) and code != "177010":
                        self._log(f"[OTP] 验证码: {code}")
                        return code

                    msg_id = msg.get("id") or msg.get("@id")
                    if not msg_id:
                        continue

                    detail = self.fetch_email_detail(mailbox_ref, msg_id)
                    if not detail:
                        continue

                    code = str(detail.get("verification_code") or "").strip()
                    if re.fullmatch(r"\d{6}", code) and code != "177010":
                        self._log(f"[OTP] 验证码: {code}")
                        return code

                    content = (
                        detail.get("content")
                        or detail.get("html_content")
                        or detail.get("text")
                        or detail.get("html")
                        or detail.get("preview")
                        or msg.get("preview")
                        or ""
                    )
                    code = self.extract_verification_code(content)
                    if code:
                        self._log(f"[OTP] 验证码: {code}")
                        return code

            time.sleep(normalized_poll_interval)

        return None
