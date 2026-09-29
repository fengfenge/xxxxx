"""步骤注册表 — 通过 step 名称路由到 Python 处理器。"""

from __future__ import annotations

from typing import Callable, Dict

from ..context import PipelineContext
from ..result import StepResult

StepHandler = Callable[[PipelineContext], StepResult]

_REGISTRY: Dict[str, StepHandler] = {}


def register(name: str):
    """装饰器：注册步骤处理器。"""

    def decorator(fn: StepHandler) -> StepHandler:
        _REGISTRY[name] = fn
        return fn

    return decorator


def get_step(name: str) -> StepHandler:
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY))
        raise KeyError(f"未知步骤 '{name}'，可用: {available}")
    return _REGISTRY[name]


def list_steps() -> list:
    return sorted(_REGISTRY.keys())


# 导入各步骤模块以触发 @register 装饰器
from . import (  # noqa: E402, F401
    approve,
    build,
    docker_build,
    k8s_deploy,
    maven_build,
    notify,
    param_build,
    pipeline_init,
    release_record,
    release_ticket,
    rollback,
    security_check,
)
