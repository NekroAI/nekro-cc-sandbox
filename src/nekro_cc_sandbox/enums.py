"""项目级枚举定义（用于稳定协议与配置）。

约束：
- 所有枚举值必须显式定义，避免散落字符串
- 用于 OpenAPI schema/前后端契约时，必须保持稳定
"""

from __future__ import annotations

from enum import StrEnum


class RuntimePolicyMode(StrEnum):
    """运行时能力策略模式。"""

    RELAXED = "relaxed"
    STRICT = "strict"
    AGENT = "agent"

