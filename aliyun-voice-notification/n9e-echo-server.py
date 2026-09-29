#!/usr/bin/env python3
"""
夜莺 v7.7+ 回调回显服务（无依赖版）

功能：接收夜莺回调地址 POST 的 JSON，解析并回显到日志，验证联通后再接阿里云。

夜莺配置：
  告警通知 → 通知设置 → 回调地址 → 添加
  URL: http://<此服务地址>:8080/voice/notify

端点：
  GET  /                服务信息
  GET  /health          健康检查
  POST /voice/notify    接收告警回调
  POST /debug/echo      调试：回显原始 JSON + 解析结果

环境变量：
  SERVER_HOST  监听地址，默认 0.0.0.0
  SERVER_PORT  监听端口，默认 8080

K8s 快速启动（临时 Pod，验证完后删掉）：
  kubectl run n9e-echo --rm -it --image=你的镜像 --env SERVER_PORT=8080

Docker 构建和运行：
  docker build -t n9e-echo -f Dockerfile.echo .
  docker run -d -p 8080:8080 --name n9e-echo n9e-echo
"""

import json
import logging
import os
import sys
import time
from copy import deepcopy
from datetime import datetime

# ============================================================
# 日志
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("n9e-echo")

VERSION = "v7.7.0"

SEVERITY_MAP = {1: "P1-致命(Critical)", 2: "P2-警告(Warning)", 3: "P3-信息(Info)"}


# ============================================================
# 回调数据解析
# ============================================================
def parse_payload(data: dict) -> dict:
    """
    解析夜莺回调 JSON，兼容三种格式：
      - 回调地址模式：顶层就是 event 对象
      - 自定义媒介模式：{"events": [...], "sendto": "..."}
      - 通知脚本模式：{"event": {...}, "tpls": {...}}
    """
    # 提取事件
    event = None
    if "events" in data:
        event = data["events"][0] if data["events"] else {}
    elif "event" in data:
        event = data["event"]
    else:
        event = data  # 回调地址模式

    return {
        # ---- 核心字段 ----
        "severity":       event.get("severity", 3),
        "severity_text":  SEVERITY_MAP.get(event.get("severity", 3), "未知"),
        "is_recovered":   event.get("is_recovered", False),
        "status_text":    "已恢复" if event.get("is_recovered") else "告警中",
        "rule_name":      event.get("rule_name", ""),
        "rule_note":      event.get("rule_note", ""),
        "target_ident":   event.get("target_ident", ""),
        "trigger_value":  event.get("trigger_value", ""),
        "group_name":     event.get("group_name", ""),

        # ---- 时间 ----
        "trigger_time":   event.get("trigger_time", 0),
        "first_trigger_time": event.get("first_trigger_time", 0),
        "last_eval_time": event.get("last_eval_time", 0),
        "recover_time":   event.get("recover_time", 0),

        # ---- 手机号（三种来源） ----
        "phones":         _extract_phones(data, event),

        # ---- 通知用户 ----
        "notify_users_obj": event.get("notify_users_obj", []),
        "notify_channels":  event.get("notify_channels", []),
        "notify_groups_obj": event.get("notify_groups_obj", []),

        # ---- 标签 ----
        "tags":           event.get("tags", []),
        "tags_map":       event.get("tags_map", {}),

        # ---- 规则信息 ----
        "rule_id":        event.get("rule_id", 0),
        "rule_prod":      event.get("rule_prod", ""),
    }


def _extract_phones(data: dict, event: dict) -> list:
    """从三种来源提取手机号"""
    # 自定义媒介 sendto
    if data.get("sendto"):
        return [data["sendto"]]
    # 自定义媒介 sendtos
    if data.get("sendtos"):
        return [s for s in data["sendtos"] if s]
    # 回调地址 / 通知脚本 notify_users_obj
    users = event.get("notify_users_obj", [])
    return [u.get("phone", "") for u in users if u.get("phone")]


# ============================================================
# 工具
# ============================================================
def mask_phones(data: dict) -> dict:
    """手机号脱敏"""
    d = deepcopy(data)
    for key in ("sendto",):
        if isinstance(d.get(key), str) and len(d[key]) >= 7:
            d[key] = d[key][:3] + "****" + d[key][-4:]
    if isinstance(d.get("sendtos"), list):
        d["sendtos"] = [
            (p[:3] + "****" + p[-4:] if len(p) >= 7 else p) for p in d["sendtos"] if p
        ]
    return d


def format_time(ts: int) -> str:
    """时间戳转可读"""
    if ts == 0:
        return "-"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# HTTP 服务
# ============================================================
def create_app():
    from flask import Flask, request, jsonify

    app = Flask(__name__)

    @app.route("/", methods=["GET"])
    def index():
        return jsonify({
            "service": "夜莺回调回显服务",
            "version": VERSION,
            "endpoints": {
                "health": "/health",
                "notify": "/voice/notify [POST]",
                "debug":  "/debug/echo [POST]",
            },
        })

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "version": VERSION, "time": int(time.time())})

    @app.route("/voice/notify", methods=["POST"])
    def voice_notify():
        """正式回调入口 - 解析并回显"""
        try:
            data = request.get_json(force=True)
        except Exception as e:
            logger.error(f"请求体解析失败: {e}")
            return jsonify({"ok": False, "err": str(e)}), 400

        # 脱敏日志
        safe = mask_phones(data)
        logger.info("=" * 70)
        logger.info(f"📨 收到夜莺回调 (长度={len(json.dumps(data))} 字符)")
        logger.info(f"   原始 JSON: {json.dumps(safe, ensure_ascii=False)[:300]}")

        # 解析
        p = parse_payload(data)
        logger.info("─" * 50)
        logger.info(f"   📋 级别:     {p['severity_text']}")
        logger.info(f"   📋 状态:     {p['status_text']} (is_recovered={p['is_recovered']})")
        logger.info(f"   📋 规则:     {p['rule_name']}")
        logger.info(f"   📋 备注:     {p['rule_note'] or '(无)'}")
        logger.info(f"   📋 对象:     {p['target_ident'] or '(无)'}")
        logger.info(f"   📋 触发值:   {p['trigger_value'] or '(无)'}")
        logger.info(f"   📋 业务组:   {p['group_name'] or '(无)'}")
        logger.info(f"   📋 触发时间: {format_time(p['trigger_time'])}")
        logger.info(f"   📋 首次时间: {format_time(p['first_trigger_time'])}")
        logger.info(f"   📋 手机号:   {p['phones']}")
        logger.info(f"   📋 通知渠道: {p['notify_channels']}")
        logger.info(f"   📋 标签:     {p['tags'][:5]}{'...' if len(p['tags'])>5 else ''}")
        logger.info(f"   📋 通知用户: {len(p['notify_users_obj'])} 人")
        logger.info(f"   📋 通知组:   {len(p['notify_groups_obj'])} 个")

        # 排查手机号：打印用户对象的关键字段
        for u in p["notify_users_obj"]:
            logger.info(f"   🔍 用户详情: username={u.get('username')} | "
                        f"phone={u.get('phone','(空)') or '(空)'} | "
                        f"email={u.get('email','(空)') or '(空)'} | "
                        f"contacts={u.get('contacts',{})} | "
                        f"keys={list(u.keys())}")

        # 检查手机号
        if not p["phones"]:
            logger.warning("   ⚠️ 未提取到手机号！请检查夜莺用户 Profile 中的 Phone 字段")
        else:
            logger.info(f"   ✅ 可拨打号码 {len(p['phones'])} 个")

        logger.info("=" * 70)

        return jsonify({
            "ok": True,
            "parsed": {
                "severity": p["severity"],
                "severity_text": p["severity_text"],
                "is_recovered": p["is_recovered"],
                "status_text": p["status_text"],
                "rule_name": p["rule_name"],
                "target_ident": p["target_ident"],
                "trigger_value": p["trigger_value"],
                "phones": p["phones"],
                "phones_count": len(p["phones"]),
            },
        })

    @app.route("/debug/echo", methods=["POST"])
    def debug_echo():
        """调试端点 - 回显完整原始 JSON + 解析结果"""
        try:
            data = request.get_json(force=True)
        except Exception as e:
            return jsonify({"ok": False, "err": str(e)}), 400

        p = parse_payload(data)
        logger.info("=" * 70)
        logger.info(f"[DEBUG] 夜莺原始 JSON:\n{json.dumps(data, ensure_ascii=False, indent=2)}")
        logger.info("=" * 70)

        return jsonify({
            "ok": True,
            "raw": data,
            "parsed": {
                "severity":        p["severity"],
                "severity_text":   p["severity_text"],
                "is_recovered":    p["is_recovered"],
                "status_text":     p["status_text"],
                "rule_name":       p["rule_name"],
                "rule_note":       p["rule_note"],
                "target_ident":    p["target_ident"],
                "trigger_value":   p["trigger_value"],
                "group_name":      p["group_name"],
                "trigger_time":    format_time(p["trigger_time"]),
                "first_trigger_time": format_time(p["first_trigger_time"]),
                "last_eval_time":  format_time(p["last_eval_time"]),
                "phones":          p["phones"],
                "notify_channels": p["notify_channels"],
                "notify_users_count": len(p["notify_users_obj"]),
                "notify_groups_count": len(p["notify_groups_obj"]),
                "tags":            p["tags"],
                "tags_map":        p["tags_map"],
                "rule_id":         p["rule_id"],
                "rule_prod":       p["rule_prod"],
            },
            "hint": "检查 parsed.phones 是否有值，无值则手机号提取失败",
        })

    return app


# ============================================================
# 主入口
# ============================================================
def main():
    host = os.environ.get("SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("SERVER_PORT", "8080"))

    logger.info("=" * 60)
    logger.info(f"  夜莺回调回显服务 v{VERSION}")
    logger.info(f"  监听: http://{host}:{port}")
    logger.info(f"  通知: POST http://<IP>:{port}/voice/notify")
    logger.info(f"  调试: POST http://<IP>:{port}/debug/echo")
    logger.info(f"  健康: GET  http://<IP>:{port}/health")
    logger.info("=" * 60)

    app = create_app()
    app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    main()
