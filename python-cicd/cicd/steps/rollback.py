"""rollback — 对应 vars/rollbackDeploy.groovy K8s 回滚逻辑。"""

from __future__ import annotations

import os

from ..context import PipelineContext
from ..result import StepResult
from ..utils import run_shell
from . import register


@register("rollback")
def run(ctx: PipelineContext) -> StepResult:
    config = ctx.config
    assert config is not None
    messages = ["[回滚] 开始执行回滚操作..."]

    target_env = ctx.get("env") or ctx.get("TARGET_ENV") or ctx.get("ENV", "")
    deployment_name = ctx.get("deployment_name") or ctx.get("DEPLOYMENT_NAME") or ctx.job_name
    revision = ctx.get("revision") or ctx.get("REVISION")
    namespace = (ctx.get("namespace") or ctx.get("K8S_NAMESPACE") or "").strip()

    if not target_env:
        return StepResult.fail("rollback", "必须指定目标环境 env", ctx)
    if not deployment_name:
        return StepResult.fail("rollback", "必须指定 deployment_name", ctx)
    if not namespace:
        return StepResult.fail("rollback", "必须指定 K8s 命名空间 namespace", ctx)
    if target_env not in config.k8s_credentials:
        return StepResult.fail("rollback", f"不支持的环境: {target_env}", ctx)

    kubeconfig = ctx.get("KUBECONFIG_FILE") or os.environ.get("KUBECONFIG_FILE", "")
    if not kubeconfig:
        return StepResult.fail("rollback", "缺少 KUBECONFIG_FILE", ctx)

    env_vars = {**os.environ, "KUBECONFIG": kubeconfig}
    rollback_cmd = f"kubectl rollout undo deployment/{deployment_name} -n {namespace}"
    if revision:
        rollback_cmd += f" --to-revision={revision}"

    messages.extend(
        [
            f"回滚环境：{target_env}",
            f"Deployment：{deployment_name}",
            f"命名空间：{namespace}",
            f"回滚版本：{'版本 ' + str(revision) if revision else '上一版本'}",
        ]
    )

    try:
        run_shell("kubectl config current-context", env=env_vars, check=False)
        run_shell(
            f"kubectl get deployments -n {namespace} {deployment_name} -o wide",
            env=env_vars,
            check=False,
        )
        run_shell(
            f"kubectl rollout history deployment/{deployment_name} -n {namespace} --max=5",
            env=env_vars,
            check=False,
        )
        run_shell(rollback_cmd, env=env_vars)
        run_shell(
            f"kubectl rollout status deployment/{deployment_name} -n {namespace} --timeout=5m",
            env=env_vars,
        )
        messages.append("[回滚] 操作完成！")
        return StepResult(success=True, step="rollback", env=dict(ctx.env), messages=messages)

    except Exception as exc:
        return StepResult.fail("rollback", f"回滚失败: {exc}", ctx)
