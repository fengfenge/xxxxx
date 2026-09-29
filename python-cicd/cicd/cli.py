"""CLI 入口 — Jenkins Groovy 通过此模块调用 Python 步骤。"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict

from .context import PipelineContext
from .steps import get_step, list_steps


def _load_params(path: str | None, inline: str | None) -> Dict[str, Any]:
    if inline:
        return json.loads(inline)
    if path:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description="python-cicd 步骤执行器")
    parser.add_argument("--step", required=True, help=f"步骤名称，可用: {', '.join(list_steps())}")
    parser.add_argument("--params", help="params JSON 文件路径")
    parser.add_argument("--params-json", help="params JSON 字符串（适合 Groovy 内联传参）")
    parser.add_argument("--list-steps", action="store_true", help="列出所有可用步骤")
    args = parser.parse_args(argv)

    if args.list_steps:
        print(json.dumps({"steps": list_steps()}, ensure_ascii=False))
        return 0

    params = _load_params(args.params, args.params_json)
    ctx = PipelineContext.from_sources(params=params)

    try:
        handler = get_step(args.step)
        result = handler(ctx)
        print(json.dumps(result.to_dict(), ensure_ascii=False))
        return 0 if result.success else 1
    except Exception as exc:
        payload = {"success": False, "step": args.step, "error": str(exc), "env": dict(ctx.env)}
        print(json.dumps(payload, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
