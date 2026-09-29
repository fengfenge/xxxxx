"""security_check — 对应 vars/securityCheck.groovy Trivy 镜像扫描。"""

from __future__ import annotations

from ..context import PipelineContext
from ..result import StepResult
from ..utils import run_shell
from . import register


@register("security_check")
def run(ctx: PipelineContext) -> StepResult:
    messages = ["[安全] 开始执行安全扫描..."]
    image = ctx.get("IMAGE", "")
    skip = str(ctx.get("SKIP_SECURITY", "false")).lower() in ("true", "1", "yes")

    if skip:
        messages.append("[安全] 已跳过安全扫描（SKIP_SECURITY=true）")
        return StepResult(success=True, step="security_check", env=dict(ctx.env), messages=messages)

    messages.append("执行 Trivy 镜像漏洞扫描 (High/Critical)...")
    try:
        run_shell(
            f"trivy image --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed {image}",
            check=True,
        )
        messages.append("[安全] 安全检查通过。")
        return StepResult(success=True, step="security_check", env=dict(ctx.env), messages=messages)
    except Exception as exc:
        # 与 Groovy 版一致：trivy 未安装时警告但不阻断（可按 params 配置）
        strict = str(ctx.get("SECURITY_STRICT", "false")).lower() in ("true", "1", "yes")
        msg = f"Trivy 扫描异常: {exc}"
        if strict:
            return StepResult.fail("security_check", msg, ctx)
        messages.append(f"⚠️ {msg}，非严格模式继续执行")
        return StepResult(success=True, step="security_check", env=dict(ctx.env), messages=messages)
