"""param_build — 对应 vars/paramBuild.groovy + Jenkinsfile.param 参数处理逻辑。

将 Jenkins UI / Webhook 传入的参数统一写入上下文，并进行分支白名单、标签必填等校验。
"""

from __future__ import annotations

from ..context import PipelineContext
from ..result import StepResult
from ..utils import normalize_branch
from . import register


@register("param_build")
def run(ctx: PipelineContext) -> StepResult:
    """
    处理参数化构建参数。

    支持 BUILD_TYPE=auto（分支构建）或 tag（标签构建）。
    自动根据分支/标签设置环境变量，供后续 git_checkout / pipeline_init 使用。
    """
    build_type = (ctx.get("BUILD_TYPE") or ctx.get("build_type") or "auto").lower()
    target_branch = normalize_branch(ctx.get("BRANCH_NAME") or ctx.get("branch") or "")
    target_tag = (ctx.get("TAG_NAME") or ctx.get("tag") or "").strip()
    target_env = (ctx.get("TARGET_ENV") or ctx.get("env") or "").strip()
    should_deploy = str(ctx.get("deploy", True)).lower() not in ("false", "0", "no", "")
    git_repo_url = (ctx.get("GIT_REPO_URL") or ctx.get("git_repo_url") or "").strip()
    git_credentials_id = (ctx.get("GIT_CREDENTIALS_ID") or ctx.get("git_credentials_id") or "").strip()
    k8s_namespace = (ctx.get("K8S_NAMESPACE") or ctx.get("k8s_namespace") or "").strip()
    dockerfile_content = ctx.get("DOCKERFILE_CONTENT") or ctx.get("dockerfile_content") or ""
    build_message = ctx.get("BUILD_MESSAGE") or ctx.get("build_message") or ""

    messages = ["[参数化构建] 开始处理构建参数..."]

    # 1. 校验 Git 仓库地址
    if not git_repo_url:
        return StepResult.fail("param_build", "请填写 GIT_REPO_URL", ctx)

    # 2. 根据构建类型处理分支/标签
    if build_type == "tag":
        if not target_tag:
            return StepResult.fail("param_build", "tag 模式必须指定 TAG_NAME", ctx)
        ctx.set_env("TAG_NAME", target_tag)
        ctx.set_env("BRANCH_NAME", "")
        messages.append(f"[参数化构建] 标签构建模式：{target_tag}")

    elif build_type == "auto":
        # Webhook 触发时，GIT_BRANCH 通常由 Jenkins 注入
        branch = target_branch or normalize_branch(ctx.get("GIT_BRANCH") or "")
        if not branch:
            return StepResult.fail("param_build", "auto 模式未获取到分支信息", ctx)

        # 白名单校验：仅允许 dev / test 分支自动构建
        if not (branch == "dev" or branch == "test" or branch.endswith("/dev") or branch.endswith("/test")):
            return StepResult.fail(
                "param_build",
                f"auto 模式仅允许 dev/test 分支自动构建，当前分支：{branch}",
                ctx,
            )
        ctx.set_env("BRANCH_NAME", branch)
        ctx.set_env("TAG_NAME", "")
        messages.append(f"[参数化构建] 自动分支构建模式：{branch}")

    else:
        return StepResult.fail("param_build", f"不支持的 BUILD_TYPE：{build_type}", ctx)

    # 3. 处理目标环境
    if target_env and target_env != "auto":
        ctx.set_env("FORCED_DEPLOY_ENV", target_env)
        messages.append(f"[参数化构建] 强制指定环境：{target_env}")
    else:
        ctx.set_env("FORCED_DEPLOY_ENV", "")
        messages.append("[参数化构建] 环境由分支/标签自动识别")

    # 4. 设置部署开关
    ctx.set_env("SHOULD_DEPLOY", str(should_deploy).lower())
    messages.append(f"[参数化构建] 部署开关：{'ENABLED' if should_deploy else 'DISABLED'}")

    # 5. 写入其他参数到环境变量
    ctx.set_env("GIT_REPO_URL", git_repo_url)
    if git_credentials_id:
        ctx.set_env("GIT_CREDENTIALS_ID", git_credentials_id)
    if build_message:
        ctx.set_env("BUILD_MESSAGE", build_message)
    if dockerfile_content:
        ctx.set_env("DOCKERFILE_CONTENT", dockerfile_content)

    # 6. 校验 K8s 命名空间
    if not k8s_namespace:
        return StepResult.fail("param_build", "未指定 K8s 命名空间 K8S_NAMESPACE", ctx)
    ctx.set_env("K8S_NAMESPACE", k8s_namespace)
    messages.append(f"[参数化构建] K8s 命名空间：{k8s_namespace}")
    messages.append("[参数化构建] 参数处理完成")

    return StepResult(
        success=True,
        step="param_build",
        env=dict(ctx.env),
        messages=messages,
    )
