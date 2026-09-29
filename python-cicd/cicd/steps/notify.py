"""notify — 对应 vars/messageNotify.groovy + wecomApprove 通知部分。"""

from __future__ import annotations

import json
from typing import Dict

import requests

from ..context import PipelineContext
from ..result import StepResult
from . import register


def _build_content(ctx: PipelineContext, status: str, custom_message: str = "") -> str:
    emoji_map = {"SUCCESS": "✅", "FAILED": "❌", "ABORTED": "⚠️"}
    title_map = {"SUCCESS": "✅ 部署成功", "FAILED": "❌ 部署失败", "ABORTED": "⚠️ 流程中止"}
    emoji = emoji_map.get(status, "⚠️")
    title = title_map.get(status, "构建通知")
    ticket_id = ctx.get("RELEASE_TICKET_ID", "无")
    approver = ctx.get("PROD_APPROVER", "")
    approver_line = f"> **审批人：{approver}**" if approver else ""
    custom_line = f"> **备注**：{custom_message}" if custom_message else ""
    duration = ctx.get("BUILD_DURATION", "")

    return f"""{emoji} **{title}**
> **项目**：{ctx.job_name}
> **环境**：{ctx.get('ENV', '未知')}
> **分支/标签**：{ctx.get('BRANCH_NAME') or ctx.get('TAG_NAME') or '未知'}
> **镜像版本**：{ctx.get('IMAGE_TAG', '未知')}
> **发布单号**：{ticket_id}
> **状态**：{status}
> **耗时**：{duration}
{approver_line}
{custom_line}
> **详情**：[查看构建日志]({ctx.build_url})"""


def _send_webhook(url: str, payload: Dict) -> bool:
    if not url or "YOUR_TOKEN" in url or "YOUR_KEY" in url:
        return False
    try:
        resp = requests.post(url, json=payload, timeout=15)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def send_dingtalk(title: str, content: str, webhook: str) -> bool:
    return _send_webhook(webhook, {"msgtype": "markdown", "markdown": {"title": title, "text": content}})


def send_wecom(content: str, webhook: str) -> bool:
    return _send_webhook(webhook, {"msgtype": "markdown", "markdown": {"content": content}})


def build_approval_message(ctx: PipelineContext) -> str:
    target_env = ctx.get("ENV", "unknown")
    emoji = {"prod": "🔴", "uat": "🟠", "test": "🟡", "dev": "🟢"}.get(target_env, "⚪")
    trigger = "标签构建" if ctx.get("TRIGGER_TYPE") == "tag" else "分支构建"
    return f"""{emoji} **发布审批申请**
> **发布单号**：{ctx.get('RELEASE_TICKET_ID', '')}
> **服务名称**：{ctx.job_name}
> **目标环境**：{target_env.upper()}
> **镜像版本**：{ctx.get('IMAGE_TAG', '')}
> **触发方式**：{trigger}
> **触发人**：{ctx.build_user_id}
> **构建说明**：{ctx.get('BUILD_MESSAGE') or '无'}

请点击 [Jenkins 构建页面]({ctx.build_url}) 进行审批操作"""


@register("notify")
def run(ctx: PipelineContext) -> StepResult:
    config = ctx.config
    assert config is not None
    notify_type = ctx.get("notify_type") or "build_result"
    messages = []

    if notify_type == "approval":
        content = build_approval_message(ctx)
        if send_wecom(content, config.wecom_webhook):
            messages.append("[审批] 已发送审批通知到企业微信")
        else:
            messages.append("[企微] Webhook 未配置，跳过发送")
        return StepResult(success=True, step="notify", env=dict(ctx.env), messages=messages, data={"content": content})

    status = (ctx.get("status") or "SUCCESS").upper()
    custom = ctx.get("custom_message") or ""
    content = _build_content(ctx, status, custom)
    title = {"SUCCESS": "部署成功", "FAILED": "部署失败"}.get(status, "构建通知")

    if send_dingtalk(title, content, config.dingtalk_webhook):
        messages.append("[钉钉] 已发送")
    else:
        messages.append("[钉钉] Webhook 未配置，跳过")

    if send_wecom(content, config.wecom_webhook):
        messages.append("[企微] 已发送")
    else:
        messages.append("[企微] Webhook 未配置，跳过")

    messages.append(f"[通知] 已发送 {status} 通知")
    return StepResult(success=True, step="notify", env=dict(ctx.env), messages=messages)
