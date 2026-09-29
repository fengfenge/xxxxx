"""步骤执行结果 — 统一 JSON 输出格式供 Groovy 解析。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StepResult:
    success: bool = True
    step: str = ""
    env: Dict[str, str] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)
    messages: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "step": self.step,
            "env": self.env,
            "data": self.data,
            "messages": self.messages,
            "error": self.error,
        }

    @classmethod
    def ok(cls, step: str, ctx, **data) -> "StepResult":
        return cls(success=True, step=step, env=dict(ctx.env), data=data)

    @classmethod
    def fail(cls, step: str, message: str, ctx=None) -> "StepResult":
        env = dict(ctx.env) if ctx else {}
        return cls(success=False, step=step, env=env, error=message, messages=[message])
