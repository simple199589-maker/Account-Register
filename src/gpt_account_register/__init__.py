"""账号注册示例 CLI。

@author AI by zb
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from uuid import uuid4


@dataclass(slots=True)
class AccountProfile:
    """账号信息模型。

    @author AI by zb
    @param account_id 账号 ID。
    @param username 用户名。
    @param email 邮箱地址。
    @param plan 套餐类型。
    @param welcome_message 欢迎语。
    """

    account_id: str
    username: str
    email: str
    plan: str
    welcome_message: str


def validate_username(username: str) -> str:
    """校验并标准化用户名。

    @author AI by zb
    @param username 原始用户名。
    @returns 标准化后的用户名。
    @raises ValueError 用户名不符合要求时抛出。
    """

    normalized = username.strip()
    if len(normalized) < 3:
        raise ValueError("用户名长度至少为 3 个字符。")
    if not normalized.replace("_", "").isalnum():
        raise ValueError("用户名只能包含字母、数字和下划线。")
    return normalized


def validate_email(email: str) -> str:
    """校验邮箱格式。

    @author AI by zb
    @param email 原始邮箱。
    @returns 标准化后的邮箱。
    @raises ValueError 邮箱格式不合法时抛出。
    """

    normalized = email.strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise ValueError("邮箱格式不合法。")
    local_part, _, domain = normalized.partition("@")
    if "." not in domain or not local_part:
        raise ValueError("邮箱格式不合法。")
    return normalized


def build_account_profile(username: str, email: str, plan: str) -> AccountProfile:
    """构建示例账号资料。

    @author AI by zb
    @param username 用户名。
    @param email 邮箱地址。
    @param plan 套餐类型。
    @returns 生成后的账号资料对象。
    """

    normalized_username = validate_username(username)
    normalized_email = validate_email(email)
    normalized_plan = plan.upper()
    return AccountProfile(
        account_id=f"acct-{uuid4().hex[:8]}",
        username=normalized_username,
        email=normalized_email,
        plan=normalized_plan,
        welcome_message=f"欢迎 {normalized_username}，账号已创建并开通 {normalized_plan} 套餐。",
    )


def parse_args() -> argparse.Namespace:
    """解析命令行参数。

    @author AI by zb
    @returns 解析后的命名空间对象。
    """

    parser = argparse.ArgumentParser(description="账号注册示例 CLI")
    parser.add_argument("--username", default="demo_user", help="注册用户名")
    parser.add_argument("--email", default="demo@example.com", help="注册邮箱")
    parser.add_argument(
        "--plan",
        choices=("free", "pro", "team"),
        default="free",
        help="账号套餐",
    )
    return parser.parse_args()


def main() -> None:
    """执行示例账号注册流程。

    @author AI by zb
    """

    args = parse_args()
    profile = build_account_profile(args.username, args.email, args.plan)
    print(json.dumps(asdict(profile), ensure_ascii=False, indent=2))
