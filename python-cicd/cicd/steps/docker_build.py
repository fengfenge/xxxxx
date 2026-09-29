"""docker_build — 对应 vars/dockerBuildPush.groovy 镜像构建与推送。"""

from __future__ import annotations

import os

from ..context import PipelineContext
from ..result import StepResult
from ..utils import run_shell
from . import register


@register("docker_build")
def run(ctx: PipelineContext) -> StepResult:
    """
    镜像构建步骤。

    凭据注入由 Groovy withCredentials 完成，Python 读取环境变量：
      DOCKER_USER / DOCKER_PASS — Harbor 登录
    """
    config = ctx.config
    assert config is not None
    workspace = ctx.workspace
    messages = ["[镜像] 开始构建与推送..."]

    dockerfile_content = ctx.get("DOCKERFILE_CONTENT") or ctx.get("dockerfile_content") or ""
    dockerfile_name = ctx.get("dockerfile") or "Dockerfile"
    dockerfile_path = os.path.join(workspace, dockerfile_name)

    app_name = ctx.get("app_name") or ctx.get("APP_NAME") or ctx.job_name
    harbor_project = ctx.get("harbor_project") or ctx.get("HARBOR_PROJECT") or config.project
    registry = config.registry

    # 共享库模式：根据 app_name 生成镜像名
    image = ctx.get("IMAGE") or ctx.get("FULL_IMAGE") or ""
    if not image:
        build_number = ctx.get("BUILD_NUMBER") or ctx.get("build_number") or "latest"
        image_tag = ctx.get("IMAGE_TAG") or f"build-{build_number}"
        image_repo = f"{registry}/{harbor_project}/{app_name}"
        image = f"{image_repo}:{image_tag}"
        ctx.set_env("IMAGE", image)
        ctx.set_env("FULL_IMAGE", image)
        ctx.set_env("IMAGE_TAG", image_tag)
        ctx.set_env("IMAGE_REPO", image_repo)

    if dockerfile_content.strip():
        messages.append("使用 Jenkins 参数中定义的 Dockerfile")
        with open(dockerfile_path, "w", encoding="utf-8") as f:
            f.write(dockerfile_content)
    elif not os.path.isfile(dockerfile_path):
        return StepResult.fail(
            "docker_build",
            f"未找到 {dockerfile_name}：请在仓库中添加 Dockerfile",
            ctx,
        )
    else:
        messages.append("使用项目仓库中的 Dockerfile")

    image = ctx.get("IMAGE") or ctx.get("FULL_IMAGE") or ""
    registry = config.registry
    docker_user = ctx.get("DOCKER_USER") or os.environ.get("DOCKER_USER", "")
    docker_pass = ctx.get("DOCKER_PASS") or os.environ.get("DOCKER_PASS", "")

    if not docker_user or not docker_pass:
        return StepResult.fail(
            "docker_build",
            "缺少 DOCKER_USER/DOCKER_PASS，请在 Groovy 层用 withCredentials 注入",
            ctx,
        )

    build_time = run_shell('date -u +"%Y-%m-%dT%H:%M:%SZ"', cwd=workspace)
    git_commit = run_shell("git rev-parse HEAD", cwd=workspace)
    target_env = ctx.get("ENV", "dev")
    build_url = ctx.get("BUILD_URL", "")

    build_args = (
        f'--build-arg BUILD_TIME="{build_time}" '
        f'--build-arg GIT_COMMIT="{git_commit}" '
        f'--build-arg ENV="{target_env}" '
        f'--label "org.opencontainers.image.created={build_time}" '
        f'--label "org.opencontainers.image.revision={git_commit}" '
        f'--label "org.opencontainers.image.source={build_url}" '
        f"--pull -t {image}"
    )

    try:
        run_shell(
            f'echo "{docker_pass}" | docker login {registry} -u "{docker_user}" --password-stdin',
            cwd=workspace,
        )
        messages.append(f"正在构建镜像：{image}")
        run_shell(f"docker build {build_args} .", cwd=workspace)
        messages.append("正在推送镜像...")
        run_shell(f"docker push {image}", cwd=workspace)

        if target_env == "prod":
            messages.append("生产镜像签名步骤已跳过（需配置 DCT 密钥）")

        messages.append(f"[镜像] 推送成功：{image}")
        return StepResult(
            success=True,
            step="docker_build",
            env=dict(ctx.env),
            data={"full_image": image, "image_tag": ctx.get("IMAGE_TAG", "")},
            messages=messages,
        )

    except Exception as exc:
        return StepResult.fail("docker_build", f"镜像构建或推送失败: {exc}", ctx)

    finally:
        try:
            run_shell(f"docker rmi {image} || true", cwd=workspace, check=False)
            run_shell('docker image prune -f --filter "until=24h" || true', cwd=workspace, check=False)
        except Exception:
            pass
