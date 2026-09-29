"""approve — 对应 vars/approveProd.groovy 审批判断逻辑（Jenkins input 仍由 Groovy 执行）。"""

from __future__ import annotations

from ..context import PipelineContext
from ..result import StepResult
from . import register
from .notify import build_approval_message, send_wecom
from .release_ticket import update_status


@register("approve")
def run(ctx: PipelineContext) -> StepResult:
    """
    审批前置步骤：判断是否需要审批、发送通知、更新发布单状态。

    实际 Jenkins input 必须在 Groovy 层执行（approve_input.groovy），
    审批通过后 Groovy 再调用 release_ticket action=record_approval。
    """
    config = ctx.config
    assert config is not None
    target_env = ctx.get("env") or ctx.get("ENV", "unknown")
    ticket_id = ctx.get("ticket_id") or ctx.get("RELEASE_TICKET_ID", "")
    messages = []

    if not config.is_approval_required(target_env):
        messages.append(f"[审批] {target_env} 环境无需审批，自动通过")
        if ticket_id:
            update_status(
                ctx,
                ticket_id=ticket_id,
                status="approved",
                action="approved",
                user="auto",
                detail=f"{target_env} 环境自动审批",
                extra_fields={"approveMethod": "auto", "approveComment": ""},
            )
            ctx.set_env("PROD_APPROVER", "auto")
        return StepResult(
            success=True,
            step="approve",
            env=dict(ctx.env),
            data={"required": False, "auto_approved": True},
            messages=messages,
        )

    messages.append(f"[审批] {target_env.upper()} 环境需要审批")
    if ticket_id:
        update_status(
            ctx,
            ticket_id=ticket_id,
            status="pending",
            action="approval_requested",
            user=ctx.build_user_id,
            detail=f"请求{target_env.upper()}环境审批",
        )

    content = build_approval_message(ctx)
    if send_wecom(content, config.wecom_webhook):
        messages.append("[审批] 已发送审批通知到企业微信")
    else:
        messages.append("[企微] Webhook 未配置，消息内容已生成供 Groovy 展示")

    return StepResult(
        success=True,
        step="approve",
        env=dict(ctx.env),
        data={
            "required": True,
            "approver_users": config.approver_users,
            "timeout_minutes": config.approval_timeout_minutes,
            "approval_message": content,
        },
        messages=messages,
    )
