"""build — 统一构建入口（共享库 buildStage 调用）。"""

from __future__ import annotations

from ..context import PipelineContext
from ..result import StepResult
from . import register
from . import maven_build  # noqa: F401 — 保留模块引用


@register("build")
def run(ctx: PipelineContext) -> StepResult:
    language = (ctx.get("language") or ctx.get("BUILD_LANGUAGE") or "java").lower()
    build_tool = (ctx.get("build_tool") or ctx.get("buildTool") or ctx.get("BUILD_TOOL") or "maven").lower()

    if language == "java" and build_tool in ("maven", "mvn"):
        from .maven_build import run as maven_run
        return maven_run(ctx)

    if language == "java" and build_tool == "gradle":
        return _gradle_build(ctx)

    if language == "python":
        return _python_build(ctx)

    if language in ("nodejs", "node"):
        return _npm_build(ctx)

    if language == "go":
        return _go_build(ctx)

    return StepResult.fail("build", f"不支持的构建组合: language={language}, build_tool={build_tool}", ctx)


def _gradle_build(ctx: PipelineContext) -> StepResult:
    from ..utils import run_shell

    workspace = ctx.workspace
    skip = str(ctx.get("skip_tests", "false")).lower() in ("true", "1", "yes")
    args = "build" if skip else "build test"
    try:
        run_shell(f"./gradlew {args}" if __import__("os").path.isfile(f"{workspace}/gradlew") else f"gradle {args}", cwd=workspace)
        return StepResult(success=True, step="build", env=dict(ctx.env), messages=["Gradle 构建成功"])
    except Exception as exc:
        return StepResult.fail("build", f"Gradle 构建失败: {exc}", ctx)


def _python_build(ctx: PipelineContext) -> StepResult:
    from ..utils import run_shell

    workspace = ctx.workspace
    try:
        run_shell("pip install -r requirements.txt", cwd=workspace, check=False)
        run_shell("python -m pytest -q", cwd=workspace, check=False)
        return StepResult(success=True, step="build", env=dict(ctx.env), messages=["Python 构建/测试完成"])
    except Exception as exc:
        return StepResult.fail("build", f"Python 构建失败: {exc}", ctx)


def _npm_build(ctx: PipelineContext) -> StepResult:
    from ..utils import run_shell

    workspace = ctx.workspace
    try:
        run_shell("npm ci && npm run build", cwd=workspace)
        return StepResult(success=True, step="build", env=dict(ctx.env), messages=["Node.js 构建成功"])
    except Exception as exc:
        return StepResult.fail("build", f"Node.js 构建失败: {exc}", ctx)


def _go_build(ctx: PipelineContext) -> StepResult:
    from ..utils import run_shell

    workspace = ctx.workspace
    try:
        run_shell("go test ./... && go build -v ./...", cwd=workspace)
        return StepResult(success=True, step="build", env=dict(ctx.env), messages=["Go 构建成功"])
    except Exception as exc:
        return StepResult.fail("build", f"Go 构建失败: {exc}", ctx)
