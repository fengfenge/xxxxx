"""流水线上下文 — 聚合 Jenkins 传入的 params 与环境变量。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .config import CicdConfig, load_config


@dataclass
class PipelineContext:
    """
    统一上下文对象，供各 step 读取参数并写回 env 更新。

    params:  Jenkinsfile / Groovy 传入的业务参数（BUILD_TYPE、TAG_NAME 等）
    env:     当前环境变量快照；step 可通过 ctx.set_env() 追加更新
    config:  静态配置（镜像 Config.groovy）
    workspace: Jenkins WORKSPACE 路径
    """

    params: Dict[str, Any] = field(default_factory=dict)
    env: Dict[str, str] = field(default_factory=dict)
    config: Optional[CicdConfig] = None
    workspace: str = "."

    def __post_init__(self) -> None:
        if self.config is None:
            cfg_path = self.params.get("config_path") or self.env.get("CICD_CONFIG")
            self.config = load_config(cfg_path)
        if not self.workspace or self.workspace == ".":
            ws = self.params.get("workspace") or self.env.get("WORKSPACE", os.getcwd())
            self.workspace = str(ws)

    @classmethod
    def from_sources(
        cls,
        params: Optional[Dict[str, Any]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> "PipelineContext":
        """从 params dict 和 os.environ 构建上下文。"""
        merged_env = {k: v for k, v in os.environ.items() if v is not None}
        if env:
            merged_env.update({k: str(v) for k, v in env.items() if v is not None})
        return cls(params=params or {}, env=merged_env)

    def get(self, key: str, default: Any = None) -> Any:
        """优先读 params，再读 env。"""
        if key in self.params and self.params[key] not in (None, ""):
            return self.params[key]
        return self.env.get(key, default)

    def set_env(self, key: str, value: Any) -> None:
        """记录待写回 Jenkins 的环境变量。"""
        self.env[key] = str(value) if value is not None else ""

    @property
    def job_name(self) -> str:
        return self.get("app_name") or self.get("APP_NAME") or self.get("JOB_NAME", self.get("service_name", "unknown"))

    @property
    def build_url(self) -> str:
        return self.get("BUILD_URL", "")

    @property
    def build_user_id(self) -> str:
        return self.get("BUILD_USER_ID", "system")

    @property
    def should_deploy(self) -> bool:
        val = self.get("SHOULD_DEPLOY", "true")
        return str(val).lower() in ("true", "1", "yes")
