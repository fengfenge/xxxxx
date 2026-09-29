"""k8s_deploy — 对应 vars/k8sDeploy.groovy K8s 部署逻辑。"""

from __future__ import annotations

import os

from ..context import PipelineContext
from ..result import StepResult
from ..utils import run_shell
from . import register
from .release_record import create_deploy_record
from .release_ticket import update_status


@register("k8s_deploy")
def run(ctx: PipelineContext) -> StepResult:
    config = ctx.config
    assert config is not None
    messages = ["[部署] 开始部署到 Kubernetes..."]

    deploy_env = ctx.get("environment") or ctx.get("ENV") or "dev"
    namespace = (ctx.get("namespace") or ctx.get("k8s_namespace") or ctx.get("K8S_NAMESPACE") or "").strip()
    if not namespace:
        return StepResult.fail("k8s_deploy", "未指定 K8s 命名空间", ctx)

    image_ref = ctx.get("image") or ctx.get("IMAGE") or ctx.get("FULL_IMAGE") or ""
    deploy_name = ctx.get("app_name") or ctx.get("APP_NAME") or ctx.job_name
    container_name = ctx.get("container_name") or deploy_name
    ticket_id = ctx.get("RELEASE_TICKET_ID", "")

    kubeconfig = (
        ctx.get("kubeconfig")
        or ctx.get("KUBECONFIG_FILE")
        or os.environ.get("KUBECONFIG_FILE", "")
        or os.environ.get("KUBECONFIG", "")
    )
    if not kubeconfig:
        return StepResult.fail(
            "k8s_deploy",
            "缺少 KUBECONFIG_FILE，请在 Groovy 层 withCredentials 注入 kubeconfig",
            ctx,
        )

    env_vars = {**os.environ, "KUBECONFIG": kubeconfig}

    if ticket_id:
        update_status(
            ctx,
            ticket_id=ticket_id,
            status="deploying",
            action="deploy_start",
            user=ctx.build_user_id,
            detail=f"开始部署到 {deploy_env} 环境",
        )

    previous_image = ""
    try:
        previous_image = run_shell(
            f"kubectl get deployment/{deploy_name} -n {namespace} "
            f"-o jsonpath='{{.spec.template.spec.containers[0].image}}' 2>/dev/null || echo ''",
            env=env_vars,
            check=False,
        )
        if previous_image:
            messages.append(f"当前运行镜像：{previous_image}")

        run_shell("kubectl config current-context", env=env_vars, check=False)
        messages.append(f"本次部署命名空间：{namespace}")
        run_shell(
            f"kubectl set image deployment/{deploy_name} {container_name}={image_ref} -n {namespace}",
            env=env_vars,
        )
        run_shell(
            f"kubectl rollout status deployment/{deploy_name} -n {namespace} --timeout=5m",
            env=env_vars,
        )
        run_shell(
            f"kubectl get pods -n {namespace} -l app={deploy_name}",
            env=env_vars,
            check=False,
        )

        if ticket_id:
            update_status(
                ctx,
                ticket_id=ticket_id,
                status="success",
                action="deploy_success",
                user=ctx.build_user_id,
                detail="部署成功",
            )

        create_deploy_record(
            ctx,
            env=deploy_env,
            image=image_ref,
            image_tag=ctx.get("IMAGE_TAG", ""),
            ticket_id=ticket_id,
            previous_image=previous_image,
            approver=ctx.get("PROD_APPROVER", ""),
        )

        messages.append(f"[部署] 部署成功！发布单：{ticket_id}")
        return StepResult(
            success=True,
            step="k8s_deploy",
            env=dict(ctx.env),
            data={"previous_image": previous_image},
            messages=messages,
        )

    except Exception as exc:
        if ticket_id:
            update_status(
                ctx,
                ticket_id=ticket_id,
                status="failed",
                action="deploy_failed",
                user=ctx.build_user_id,
                detail=str(exc),
            )
        return StepResult.fail("k8s_deploy", f"部署失败: {exc}", ctx)
