"""pipeline_init — 对应 vars/pipelineInit.groovy 核心决策逻辑。"""

from __future__ import annotations

import re

from ..context import PipelineContext
from ..result import StepResult
from ..utils import normalize_branch, parse_tag, sanitize_branch_for_image_tag, timestamp_tag
from . import register
from .release_ticket import create_ticket


def _init_from_standard_pipeline(ctx: PipelineContext, config) -> StepResult:
    """共享库 standardPipeline 初始化：根据 appName/envs 生成镜像信息。"""
    app_name = ctx.get("app_name") or ctx.get("APP_NAME") or ctx.job_name
    envs = ctx.get("envs") or []
    if isinstance(envs, str):
        envs = [e.strip() for e in envs.split(",") if e.strip()]

    harbor_project = ctx.get("harbor_project") or ctx.get("HARBOR_PROJECT") or config.project
    k8s_ns = (ctx.get("k8s_namespace") or ctx.get("K8S_NAMESPACE") or "default").strip()
    build_number = ctx.get("BUILD_NUMBER") or ctx.get("build_number") or "local"
    branch = normalize_branch(ctx.get("BRANCH_NAME") or ctx.get("GIT_BRANCH") or "main")
    branch_slug = sanitize_branch_for_image_tag(branch)
    image_tag = f"{branch_slug}-{timestamp_tag(config.image_tag_timezone)}"

    image_repo = f"{config.registry}/{harbor_project}/{app_name}"
    image = f"{image_repo}:{image_tag}"
    primary_env = envs[0] if envs else "dev"

    ctx.set_env("APP_NAME", app_name)
    ctx.set_env("SERVICE_NAME", app_name)
    ctx.set_env("ENV", primary_env)
    ctx.set_env("TARGET_ENVS", ",".join(envs))
    ctx.set_env("SHOULD_DEPLOY", "true")
    ctx.set_env("SHOULD_BUILD_IMAGE", "true")
    ctx.set_env("TRIGGER_TYPE", "branch")
    ctx.set_env("BUILD_LANGUAGE", ctx.get("language") or "")
    ctx.set_env("BUILD_TOOL", ctx.get("build_tool") or "")
    ctx.set_env("IMAGE_TAG", image_tag)
    ctx.set_env("IMAGE_REPO", image_repo)
    ctx.set_env("IMAGE", image)
    ctx.set_env("FULL_IMAGE", image)
    ctx.set_env("K8S_NAMESPACE", k8s_ns)
    ctx.set_env("HARBOR_PROJECT", harbor_project)

    if primary_env in config.k8s_credentials:
        ctx.set_env("K8S_CREDENTIAL_ID", config.k8s_credentials[primary_env])

    messages = [
        "[初始化] 共享库 standardPipeline 模式",
        f"应用: {app_name} | 语言: {ctx.get('language', 'java')}",
        f"目标环境: {', '.join(envs) if envs else primary_env}",
        f"镜像: {image}",
        f"命名空间: {k8s_ns}",
    ]

    return StepResult(
        success=True,
        step="pipeline_init",
        env=dict(ctx.env),
        data={"image_tag": image_tag, "full_image": image, "envs": envs},
        messages=messages,
    )


def _is_manual_trigger(ctx: PipelineContext) -> bool:
    if ctx.get("BUILD_USER_ID"):
        return True
    build_cause = (ctx.get("BUILD_CAUSE") or "").lower()
    if "userid" in build_cause or "manual" in build_cause:
        return True
    # Jenkins 参数化构建通常意味着手动触发
    if ctx.params:
        return True
    return False


def _match_tag_to_env(tag: str, config) -> str | None:
    for pattern, env_name in config.tag_env_map.items():
        if re.match(pattern, tag):
            return env_name
    return None


def _match_branch_to_env(branch: str, config) -> str | None:
    if branch in config.env_map:
        return config.env_map[branch]
    for prefix, env_name in config.env_prefix_map.items():
        if branch.startswith(prefix):
            return env_name
    if branch.startswith("feature/") or branch.startswith("feat/"):
        return "dev"
    return None


@register("pipeline_init")
def run(ctx: PipelineContext) -> StepResult:
    config = ctx.config
    assert config is not None

    # 共享库 standardPipeline 模式：传入 app_name + envs
    if ctx.get("app_name") or ctx.get("APP_NAME"):
        return _init_from_standard_pipeline(ctx, config)

    branch_raw = ctx.get("BRANCH_NAME") or ctx.get("GIT_BRANCH") or ""
    branch = normalize_branch(branch_raw)
    mr_target = normalize_branch(
        ctx.get("gitlabTargetBranch")
        or ctx.get("GITLAB_TARGET_BRANCH")
        or ctx.get("CHANGE_TARGET")
        or ""
    )
    branch_for_env = mr_target or branch
    tag = ctx.get("TAG_NAME") or ctx.get("GIT_TAG_NAME") or ""

    target_env = ""
    should_deploy = ctx.should_deploy
    trigger_type = ""
    messages = ["[初始化] 正在解析构建策略..."]

    if tag:
        trigger_type = "tag"
        messages.append(f"[策略] 检测到标签构建：{tag}")
        target_env = _match_tag_to_env(tag, config)
        if not target_env:
            return StepResult.fail(
                "pipeline_init",
                f"不支持的标签格式：{tag}，请使用 分支-年月日时分-v版本 格式",
                ctx,
            )

        strategy = config.build_strategy.get(target_env) or {}
        if strategy.get("requireTag"):
            pattern = strategy.get("versionPattern", "")
            if pattern and not re.match(pattern, tag):
                return StepResult.fail(
                    "pipeline_init",
                    f"标签 {tag} 不符合环境 {target_env} 的要求",
                    ctx,
                )

        if strategy.get("manualOnly") and not _is_manual_trigger(ctx):
            return StepResult.fail(
                "pipeline_init",
                f"环境 {target_env} 仅支持手动构建部署",
                ctx,
            )
        messages.append(f"[策略] 检测到手动触发，允许部署到 {target_env} 环境。")

    else:
        trigger_type = "branch"
        messages.append(
            f"[策略] 检测到分支构建：检出分支={branch}"
            + (f"，MR目标分支={mr_target}" if mr_target else "")
        )
        target_env = _match_branch_to_env(branch_for_env, config)
        if not target_env:
            return StepResult.fail(
                "pipeline_init",
                f"不支持的分支：{branch_for_env}，仅允许 dev/test/dev-*/test-*/feature/*",
                ctx,
            )

        strategy = config.build_strategy.get(target_env) or {}
        if strategy.get("trigger") == "tag":
            return StepResult.fail(
                "pipeline_init",
                f"环境 {target_env} 必须使用标签构建",
                ctx,
            )

        if strategy.get("autoDeploy") is not None:
            should_deploy = bool(strategy["autoDeploy"])

        is_feat = branch.startswith("feature/") or branch.startswith("feat/")
        merges_dev_test = mr_target and (
            mr_target in ("dev", "test")
            or mr_target.startswith("dev-")
            or mr_target.startswith("test-")
        )
        if is_feat and not merges_dev_test:
            should_deploy = False
            messages.append(f"[策略] 功能分支 {branch} 未合并目标为 dev/test，仅构建，不部署。")

    forced = (ctx.get("FORCED_DEPLOY_ENV") or "").strip()
    if forced:
        if forced not in config.k8s_credentials:
            return StepResult.fail("pipeline_init", f"强制环境 {forced} 未在 K8S_CREDENTIALS 中配置", ctx)
        messages.append(f"[策略] 使用参数指定的环境覆盖：{target_env} -> {forced}")
        target_env = forced

    ctx.set_env("ENV", target_env)
    ctx.set_env("SHOULD_DEPLOY", str(should_deploy).lower())
    ctx.set_env("TRIGGER_TYPE", trigger_type)
    ctx.set_env("SERVICE_NAME", ctx.job_name)

    service_cfg = config.get_service_config(ctx.job_name)
    if service_cfg.get("name"):
        ctx.set_env("SERVICE_DISPLAY_NAME", service_cfg["name"])
        messages.append(f"[服务] 识别到服务：{service_cfg['name']}")

    if trigger_type == "tag":
        image_tag = tag
    else:
        branch_slug = sanitize_branch_for_image_tag(branch) if branch else "unknown"
        image_tag = f"{branch_slug}-{timestamp_tag(config.image_tag_timezone)}"
        messages.append(f"[DEBUG] 分支构建镜像 tag: {image_tag}")

    image_repo = f"{config.registry}/{config.project}/{ctx.job_name}"
    image = f"{image_repo}:{image_tag}"

    ctx.set_env("IMAGE_TAG", image_tag)
    ctx.set_env("IMAGE_REPO", image_repo)
    ctx.set_env("IMAGE", image)

    if target_env not in config.k8s_credentials:
        return StepResult.fail("pipeline_init", f"未找到环境 {target_env} 的 K8s 配置", ctx)

    ctx.set_env("K8S_CREDENTIAL_ID", config.k8s_credentials[target_env])

    k8s_ns = (ctx.get("K8S_NAMESPACE") or "").strip()
    if not k8s_ns:
        return StepResult.fail("pipeline_init", "未指定 K8s 命名空间 K8S_NAMESPACE", ctx)
    ctx.set_env("K8S_NAMESPACE", k8s_ns)

    if trigger_type == "tag":
        tag_info = parse_tag(tag)
        ctx.set_env("TAG_BRANCH", tag_info["branch"])
        ctx.set_env("TAG_TIMESTAMP", tag_info["timestamp"])
        ctx.set_env("TAG_VERSION", tag_info["version"])
        messages.append(
            f"[标签信息] 分支: {tag_info['branch']}, 时间: {tag_info['timestamp']}, 版本: {tag_info['version']}"
        )

    ticket_id = None
    if should_deploy:
        ticket_id = create_ticket(
            ctx,
            service_name=ctx.job_name,
            target_env=target_env,
            image_tag=image_tag,
            image=image,
            trigger_type=trigger_type,
        )
        messages.append(f"[发布单] 已创建：{ticket_id}")

    approval_required = config.is_approval_required(target_env)
    messages.extend(
        [
            "==========================================",
            f"服务: {ctx.env.get('SERVICE_DISPLAY_NAME', ctx.job_name)}",
            f"环境: {target_env.upper()}",
            f"触发类型: {trigger_type.upper()}",
            f"镜像: {image}",
            f"发布单: {ticket_id or '无'}",
            f"K8s 命名空间: {k8s_ns}",
            f"部署: {'ENABLED' if should_deploy else 'DISABLED'}",
            f"审批: {'REQUIRED' if approval_required else 'NOT REQUIRED'}",
            "==========================================",
        ]
    )

    return StepResult(
        success=True,
        step="pipeline_init",
        env=dict(ctx.env),
        data={"ticket_id": ticket_id, "approval_required": approval_required},
        messages=messages,
    )
