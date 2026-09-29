"""maven_build — 对应 vars/javamavenBuild.groovy Java/Maven 编译逻辑。"""

from __future__ import annotations

import os

from ..context import PipelineContext
from ..result import StepResult
from ..utils import run_shell
from . import register


@register("maven_build")
def run(ctx: PipelineContext) -> StepResult:
    messages = ["[构建] 开始 Maven 编译..."]
    workspace = ctx.workspace
    maven_args = "-T 1C -DskipTests -Dmaven.repo.local=./.m2/repository"

    target_env = ctx.get("ENV", "dev")
    if target_env == "prod":
        messages.append("[构建] 生产环境构建，建议开启单元测试验证...")

    mvn_cmd = "./mvnw" if os.path.isfile(os.path.join(workspace, "mvnw")) else "mvn"
    if mvn_cmd == "mvn":
        messages.append("[构建] 未检测到 Maven Wrapper，使用系统 Maven。")

    try:
        run_shell("java -version", cwd=workspace, check=False)
        run_shell(f"{mvn_cmd} clean package {maven_args}", cwd=workspace)

        if target_env == "prod":
            messages.append("[检查] 验证生产版本规范性...")
            version = run_shell(
                f"{mvn_cmd} help:evaluate -Dexpression=project.version -q -DforceStdout",
                cwd=workspace,
            )
            if version.endswith("-SNAPSHOT"):
                return StepResult.fail(
                    "maven_build",
                    f"生产环境禁止发布 SNAPSHOT 版本！当前版本：{version}",
                    ctx,
                )
            messages.append(f"版本检查通过：{version}")

        messages.append("[构建] Maven 编译成功。")
        return StepResult(success=True, step="maven_build", env=dict(ctx.env), messages=messages)

    except Exception as exc:
        return StepResult.fail("maven_build", f"Maven 编译失败: {exc}", ctx)
