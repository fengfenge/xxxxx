"""配置加载 — 镜像 src/com/devops/Config.groovy 中的静态配置。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

_DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "default.yaml"


class CicdConfig:
    """运行时配置对象，提供与 Groovy Config 类等价的辅助方法。"""

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    # --- 基础属性 ---
    @property
    def registry(self) -> str:
        return self._data["registry"]

    @property
    def project(self) -> str:
        return self._data["project"]

    @property
    def env_map(self) -> Dict[str, str]:
        return self._data["env_map"]

    @property
    def env_prefix_map(self) -> Dict[str, str]:
        return self._data["env_prefix_map"]

    @property
    def tag_env_map(self) -> Dict[str, str]:
        return self._data["tag_env_map"]

    @property
    def build_strategy(self) -> Dict[str, Dict[str, Any]]:
        return self._data["build_strategy"]

    @property
    def k8s_credentials(self) -> Dict[str, str]:
        return self._data["k8s_credentials"]

    @property
    def image_tag_timezone(self) -> str:
        return self._data.get("image_tag_timezone", "Asia/Shanghai")

    @property
    def dingtalk_webhook(self) -> str:
        return self._data.get("dingtalk_webhook", "")

    @property
    def wecom_webhook(self) -> str:
        return self._data.get("wecom_webhook", "")

    @property
    def wecom_approve_mode(self) -> str:
        return self._data.get("wecom_approve_mode", "simple")

    @property
    def approval_timeout_minutes(self) -> int:
        return int(self._data.get("approval_timeout_minutes", 30))

    @property
    def approver_users(self) -> str:
        return self._data.get("approver_users", "admin")

    @property
    def release_record_dir(self) -> str:
        return self._data["release_record_dir"]

    @property
    def release_ticket_prefix(self) -> str:
        return self._data.get("release_ticket_prefix", "REL")

    @property
    def approval_env_list(self) -> List[str]:
        return list(self._data.get("approval_env_list", []))

    @property
    def harbor_credentials_id(self) -> str:
        return self._data.get("harbor_credentials_id", "harbor-credentials")

    def get_service_config(self, service_name: str) -> Dict[str, Any]:
        services = self._data.get("services") or {}
        return dict(services.get(service_name, {}))

    def is_approval_required(self, target_env: str) -> bool:
        return target_env in self.approval_env_list

    def is_tag_based_build(self, target_env: str) -> bool:
        strategy = self.build_strategy.get(target_env) or {}
        return strategy.get("trigger") == "tag"


def load_config(config_path: Optional[str] = None) -> CicdConfig:
    """
    加载 YAML 配置。
    优先级：显式路径 > 环境变量 CICD_CONFIG > 默认 default.yaml
    """
    path = config_path or os.environ.get("CICD_CONFIG") or str(_DEFAULT_CONFIG)
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return CicdConfig(data)
