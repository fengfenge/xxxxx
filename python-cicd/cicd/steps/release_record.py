"""release_record — 对应 vars/releaseRecord.groovy 发布记录索引。"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ..context import PipelineContext
from ..result import StepResult
from ..utils import load_json_file, now_str, save_json_file
from . import register


def _index_path(config) -> str:
    return os.path.join(config.release_record_dir, "deploy-index.json")


def load_index(config) -> List[Dict[str, Any]]:
    return load_json_file(_index_path(config), default=[])


def append_to_index(config, record: Dict[str, Any]) -> None:
    records = load_index(config)
    records.append(record)
    os.makedirs(config.release_record_dir, exist_ok=True)
    save_json_file(_index_path(config), records)


def create_deploy_record(ctx: PipelineContext, **kwargs) -> Dict[str, Any]:
    config = ctx.config
    assert config is not None
    now = now_str(config.image_tag_timezone)
    record = {
        "recordId": f"REC-{int(__import__('time').time() * 1000)}",
        "ticketId": kwargs.get("ticket_id") or ctx.get("RELEASE_TICKET_ID", ""),
        "serviceName": kwargs.get("service_name") or ctx.job_name,
        "environment": kwargs.get("env") or ctx.get("ENV", "unknown"),
        "imageTag": kwargs.get("image_tag") or ctx.get("IMAGE_TAG", ""),
        "image": kwargs.get("image") or ctx.get("IMAGE", ""),
        "previousImage": kwargs.get("previous_image", ""),
        "triggerType": kwargs.get("trigger_type") or ctx.get("TRIGGER_TYPE", "unknown"),
        "triggerUser": kwargs.get("trigger_user") or ctx.build_user_id,
        "approver": kwargs.get("approver") or ctx.get("PROD_APPROVER", ""),
        "result": kwargs.get("result", "success"),
        "deployDuration": kwargs.get("deploy_duration", ""),
        "deployTime": now,
        "buildUrl": kwargs.get("build_url") or ctx.build_url,
        "isRolledBack": False,
        "rollbackTicketId": "",
    }
    append_to_index(config, record)
    return record


@register("release_record")
def run(ctx: PipelineContext) -> StepResult:
    action = ctx.get("action") or "create"
    config = ctx.config
    assert config is not None

    if action == "create":
        record = create_deploy_record(
            ctx,
            ticket_id=ctx.get("ticket_id"),
            service_name=ctx.get("service_name"),
            env=ctx.get("env"),
            image_tag=ctx.get("image_tag"),
            image=ctx.get("image"),
            result=ctx.get("result", "success"),
            approver=ctx.get("approver"),
            previous_image=ctx.get("previous_image", ""),
        )
        return StepResult.ok("release_record", ctx, record=record)

    if action == "get_history":
        service = ctx.get("service_name") or ctx.job_name
        target_env = ctx.get("env") or ctx.get("ENV", "")
        limit = int(ctx.get("limit", 20))
        records = load_index(config)
        if service:
            records = [r for r in records if r.get("serviceName") == service]
        if target_env:
            records = [r for r in records if r.get("environment") == target_env]
        records = sorted(records, key=lambda r: r.get("deployTime", ""), reverse=True)[:limit]
        return StepResult.ok("release_record", ctx, records=records)

    return StepResult.fail("release_record", f"未知 action: {action}", ctx)
