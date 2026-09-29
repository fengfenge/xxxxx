"""release_ticket — 对应 vars/releaseTicket.groovy 发布单 CRUD。"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

from ..context import PipelineContext
from ..result import StepResult
from ..utils import date_str, load_json_file, now_str, save_json_file
from . import register


def _record_dir(config, target_env: str) -> str:
    return os.path.join(config.release_record_dir, target_env)


def _next_seq(record_dir: str, date_s: str, prefix: str) -> int:
    os.makedirs(record_dir, exist_ok=True)
    pattern = re.compile(rf"^{re.escape(prefix)}-{date_s}-(\d{{3}})\.json$")
    max_seq = 0
    for name in os.listdir(record_dir):
        m = pattern.match(name)
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return max_seq + 1


def _ticket_path(config, ticket_id: str, target_env: str = "") -> Optional[str]:
    if target_env:
        p = os.path.join(_record_dir(config, target_env), f"{ticket_id}.json")
        return p if os.path.isfile(p) else None
    base = config.release_record_dir
    if not os.path.isdir(base):
        return None
    for env_dir in os.listdir(base):
        full = os.path.join(base, env_dir, f"{ticket_id}.json")
        if os.path.isfile(full):
            return full
    return None


def load_ticket(config, ticket_id: str) -> Optional[Dict[str, Any]]:
    path = _ticket_path(config, ticket_id)
    if not path:
        return None
    return load_json_file(path)


def save_ticket(config, ticket: Dict[str, Any]) -> str:
    record_dir = _record_dir(config, ticket["environment"])
    os.makedirs(record_dir, exist_ok=True)
    path = os.path.join(record_dir, f"{ticket['ticketId']}.json")
    save_json_file(path, ticket)
    return path


def create_ticket(
    ctx: PipelineContext,
    *,
    service_name: str,
    target_env: str,
    image_tag: str,
    image: str,
    trigger_type: str,
) -> str:
    config = ctx.config
    assert config is not None
    tz = config.image_tag_timezone
    ds = date_str(tz)
    seq = _next_seq(_record_dir(config, target_env), ds, config.release_ticket_prefix)
    ticket_id = f"{config.release_ticket_prefix}-{ds}-{seq:03d}"
    now = now_str(tz)
    trigger_user = ctx.build_user_id

    ticket = {
        "ticketId": ticket_id,
        "serviceName": service_name,
        "environment": target_env,
        "imageTag": image_tag,
        "image": image,
        "triggerType": trigger_type,
        "triggerUser": trigger_user,
        "buildUrl": ctx.build_url,
        "buildMessage": ctx.get("BUILD_MESSAGE", ""),
        "status": "pending",
        "createdAt": now,
        "approvedBy": "",
        "approvedAt": "",
        "deployedAt": "",
        "deployResult": "",
        "rollbackFrom": "",
        "rollbackReason": "",
        "rollbackAt": "",
        "history": [{"time": now, "action": "created", "user": trigger_user, "detail": "发布单创建"}],
    }
    save_ticket(config, ticket)
    ctx.set_env("RELEASE_TICKET_ID", ticket_id)
    return ticket_id


def update_status(
    ctx: PipelineContext,
    *,
    ticket_id: str,
    status: str,
    action: str = "",
    user: str = "",
    detail: str = "",
    extra_fields: Optional[Dict[str, Any]] = None,
) -> None:
    config = ctx.config
    assert config is not None
    ticket = load_ticket(config, ticket_id)
    if not ticket:
        return
    now = now_str(config.image_tag_timezone)
    ticket["status"] = status
    if status == "approved":
        ticket["approvedBy"] = user
        ticket["approvedAt"] = now
    elif status in ("success", "failed"):
        ticket["deployedAt"] = now
        ticket["deployResult"] = status
    elif status == "rollback":
        ticket["rollbackAt"] = now
    if extra_fields:
        ticket.update(extra_fields)
    ticket.setdefault("history", []).append(
        {"time": now, "action": action or status, "user": user or ctx.build_user_id, "detail": detail}
    )
    save_ticket(config, ticket)


@register("release_ticket")
def run(ctx: PipelineContext) -> StepResult:
    """CLI 步骤：create / update / get"""
    action = ctx.get("action") or "create"
    config = ctx.config
    assert config is not None

    if action == "create":
        tid = create_ticket(
            ctx,
            service_name=ctx.get("service_name") or ctx.job_name,
            target_env=ctx.get("env") or ctx.get("ENV", "unknown"),
            image_tag=ctx.get("image_tag") or ctx.get("IMAGE_TAG", ""),
            image=ctx.get("image") or ctx.get("IMAGE", ""),
            trigger_type=ctx.get("trigger_type") or ctx.get("TRIGGER_TYPE", "unknown"),
        )
        return StepResult.ok("release_ticket", ctx, ticket_id=tid)

    ticket_id = ctx.get("ticket_id") or ctx.get("RELEASE_TICKET_ID", "")
    if action == "get":
        ticket = load_ticket(config, ticket_id) if ticket_id else None
        return StepResult.ok("release_ticket", ctx, ticket=ticket)

    if action == "update":
        update_status(
            ctx,
            ticket_id=ticket_id,
            status=ctx.get("status", ""),
            action=ctx.get("update_action") or ctx.get("status", ""),
            user=ctx.get("user") or ctx.build_user_id,
            detail=ctx.get("detail", ""),
        )
        return StepResult.ok("release_ticket", ctx, ticket_id=ticket_id)

    if action == "record_approval":
        approver = ctx.get("approver", "auto")
        update_status(
            ctx,
            ticket_id=ticket_id,
            status="approved",
            action="approved",
            user=approver,
            detail=f"审批通过（方式：{ctx.get('method', 'jenkins_input')}）",
            extra_fields={
                "approveMethod": ctx.get("method", "jenkins_input"),
                "approveComment": ctx.get("comment", ""),
            },
        )
        ctx.set_env("PROD_APPROVER", approver)
        return StepResult.ok("release_ticket", ctx, approver=approver)

    if action == "record_deploy":
        result = ctx.get("result", "success")
        update_status(
            ctx,
            ticket_id=ticket_id,
            status=result,
            action=f"deploy_{result}",
            user=ctx.build_user_id,
            detail=ctx.get("detail") or f"部署{'成功' if result == 'success' else '失败'}",
        )
        return StepResult.ok("release_ticket", ctx, result=result)

    return StepResult.fail("release_ticket", f"未知 action: {action}", ctx)
