#!/usr/bin/env python3
"""
夜莺 v7.7+ 语音通知 HTTP 服务（K8s / 容器部署版）

独立部署的 HTTP 服务，通过夜莺「回调地址」接收告警事件，调用阿里云语音电话通知。

适用场景：
  - 夜莺 v7.7+ 容器化部署在 K8s 中，无法直接执行脚本
  - 本服务独立部署为一个 K8s Pod，暴露 HTTP 接口供夜莺回调

夜莺配置：
  告警通知 → 通知设置 → 回调地址 → 添加
  URL: http://<此服务地址>:8085/voice/notify

环境变量（全部通过 K8s ConfigMap/Secret 注入）：
  必填:
    ALIYUN_ACCESS_KEY_ID      阿里云 AccessKey ID
    ALIYUN_ACCESS_KEY_SECRET  阿里云 AccessKey Secret
    ALIYUN_TTS_CODE           阿里云 TTS 语音模板 ID (如 TTS_28726****)
  可选:
    ALIYUN_CALLED_SHOW_NUMBER 被叫显号（专属模式），不填为公共模式
    ALIYUN_PLAY_TIMES         播放次数 1~3，默认 2
    SKIP_RECOVERY_CALL        是否跳过恢复通知，默认 true
    SERVER_HOST               监听地址，默认 0.0.0.0
    SERVER_PORT               监听端口，默认 8085

阿里云 TTS 模板变量：
  ${status_text}   - 告警状态: "告警中" / "已恢复"
  ${severity_text} - 告警级别: "P1-致命" / "P2-警告" / "P3-信息"
  ${rule_name}     - 规则名称（截断20字）
  ${target_ident}  - 监控对象（截断20字）
  ${trigger_value} - 触发值（截断15字）
  ${rule_note}     - 规则备注（截断30字，可选）
  ${group_name}    - 业务组名称（截断20字，可选）

示例 TTS 模板:
  尊敬的用户，您有${status_text}告警，级别${severity_text}，规则${rule_name}，
  监控对象${target_ident}，当前值${trigger_value}。

K8s 部署清单:
  见同目录下的 n9e-voice-server.yaml
"""

import json
import logging
import os
import sys
import time
from typing import Optional, Tuple

from alibabacloud_dyvmsapi20170525.client import Client
from alibabacloud_dyvmsapi20170525 import models as dyvmsapi_models
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models

# ============================================================
# 日志配置 - 容器环境输出到 stdout
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("n9e-voice-server")

# ============================================================
# 常量
# ============================================================
NIGHTINGALE_VERSION = "v7.7.0"
SEVERITY_MAP = {1: "P1-致命", 2: "P2-警告", 3: "P3-信息"}
SEVERITY_MAP_SHORT = {1: "P1", 2: "P2", 3: "P3"}


# ============================================================
# 阿里云语音通知客户端
# ============================================================
class AliyunVoiceNotifier:
    """阿里云语音通知发送器"""

    def __init__(self):
        self.access_key_id = os.environ.get("ALIYUN_ACCESS_KEY_ID", "")
        self.access_key_secret = os.environ.get("ALIYUN_ACCESS_KEY_SECRET", "")
        self.tts_code = os.environ.get("ALIYUN_TTS_CODE", "")
        self.called_show_number = os.environ.get("ALIYUN_CALLED_SHOW_NUMBER", "")
        self.play_times = int(os.environ.get("ALIYUN_PLAY_TIMES", "2"))

        self._validate_config()
        self.client = self._create_client()

    def _validate_config(self) -> None:
        missing = []
        if not self.access_key_id:
            missing.append("ALIYUN_ACCESS_KEY_ID")
        if not self.access_key_secret:
            missing.append("ALIYUN_ACCESS_KEY_SECRET")
        if not self.tts_code:
            missing.append("ALIYUN_TTS_CODE")
        if missing:
            raise ValueError(f"缺少必填环境变量: {', '.join(missing)}")

    def _create_client(self) -> Client:
        config = open_api_models.Config(
            access_key_id=self.access_key_id,
            access_key_secret=self.access_key_secret,
        )
        config.endpoint = "dyvmsapi.aliyuncs.com"
        return Client(config)

    def send_voice(self, called_number: str, tts_param: dict,
                   out_id: str = "") -> dict:
        """发送语音通知"""
        request = dyvmsapi_models.SingleCallByTtsRequest(
            called_number=called_number,
            tts_code=self.tts_code,
            tts_param=json.dumps(tts_param, ensure_ascii=False),
            play_times=self.play_times,
        )
        if self.called_show_number:
            request.called_show_number = self.called_show_number
        if out_id:
            request.out_id = out_id

        runtime = util_models.RuntimeOptions(read_timeout=10000, connect_timeout=10000)

        try:
            response = self.client.single_call_by_tts_with_options(request, runtime)
            result = {
                "code": response.body.code,
                "message": response.body.message,
                "request_id": response.body.request_id,
                "call_id": response.body.call_id,
            }
            if response.body.code == "OK":
                logger.info(f"✅ 语音通知成功 -> {called_number}, CallId={response.body.call_id}")
            else:
                logger.error(f"❌ 语音通知失败 -> {called_number}, Code={response.body.code}")
            return result
        except Exception as e:
            logger.error(f"❌ 语音通知异常 -> {called_number}, Error={e}")
            return {"code": "EXCEPTION", "message": str(e)}


# ============================================================
# 夜莺回调数据解析
# ============================================================
class NightingaleEvent:
    """夜莺告警事件"""

    __slots__ = (
        "severity", "severity_text", "severity_short", "status_text",
        "is_recovered", "rule_name", "rule_note", "target_ident",
        "trigger_value", "group_name", "phones",
    )

    def __init__(self, severity: int, is_recovered: bool, rule_name: str,
                 rule_note: str, target_ident: str, trigger_value: str,
                 group_name: str, phones: list):
        self.severity = severity
        self.severity_text = SEVERITY_MAP.get(severity, f"P{severity}")
        self.severity_short = SEVERITY_MAP_SHORT.get(severity, f"P{severity}")
        self.is_recovered = is_recovered
        self.status_text = "已恢复" if is_recovered else "告警中"
        self.rule_name = rule_name or "未知规则"
        self.rule_note = rule_note or ""
        self.target_ident = target_ident or "未知对象"
        self.trigger_value = trigger_value or ""
        self.group_name = group_name or ""
        self.phones = phones or []

    @classmethod
    def from_callback(cls, data: dict) -> "NightingaleEvent":
        """
        从夜莺 v7 回调 JSON 解析告警事件

        支持两种回调格式：
        格式1 - 自定义通知媒介（含 sendto/sendtos）:
        {"events": [...], "sendto": "138...", "tpl": {...}}

        格式2 - 回调地址（仅含 event 对象）:
        {"id": ..., "severity": 1, ...}  或  {"events": [...]}
        """
        # === 提取 events 列表 ===
        if "events" in data:
            events = data["events"]
            if not events:
                raise ValueError("回调数据中 events 为空")
            event = events[0]
        else:
            # 回调地址模式：顶层就是 event 对象
            event = data

        # === 提取手机号 ===
        phones = cls._extract_phones(data, event)

        # === 构建事件对象 ===
        return cls(
            severity=event.get("severity", 3),
            is_recovered=event.get("is_recovered", False),
            rule_name=event.get("rule_name", ""),
            rule_note=event.get("rule_note", ""),
            target_ident=event.get("target_ident", ""),
            trigger_value=event.get("trigger_value", ""),
            group_name=event.get("group_name", ""),
            phones=phones,
        )

    @staticmethod
    def _extract_phones(data: dict, event: dict) -> list:
        """
        从多种来源提取手机号（按优先级）：
          1. data["sendto"]   - 自定义通知媒介，单个号码
          2. data["sendtos"]  - 自定义通知媒介，号码列表
          3. event["notify_users_obj"][]["phone"] - 通知脚本模式
        """
        # 方式1: sendto 单个号码
        sendto = data.get("sendto", "")
        if sendto:
            return [sendto]

        # 方式2: sendtos 号码列表
        sendtos = data.get("sendtos", [])
        if sendtos:
            return [s for s in sendtos if s]

        # 方式3: notify_users_obj 中的 phone
        users = event.get("notify_users_obj", [])
        if users:
            phones = [u.get("phone", "") for u in users if u.get("phone")]
            if phones:
                return phones

        return []

    def build_tts_param(self) -> dict:
        """构建阿里云 TTS 模板变量"""
        params = {
            "status_text": self.status_text,
            "severity_text": self.severity_text,
            "rule_name": self.rule_name[:20],
            "target_ident": self.target_ident[:20],
            "trigger_value": self.trigger_value[:15],
        }
        if self.rule_note:
            params["rule_note"] = self.rule_note[:30]
        if self.group_name:
            params["group_name"] = self.group_name[:20]
        return params

    def to_log_str(self) -> str:
        return (
            f"S{self.severity} | {self.status_text} | "
            f"规则={self.rule_name} | 对象={self.target_ident}"
        )


# ============================================================
# 语音通知处理
# ============================================================
def handle_alert(data: dict) -> dict:
    """
    处理夜莺告警回调，执行语音通知

    Args:
        data: 夜莺 POST 的 JSON 数据

    Returns:
        处理结果字典
    """
    # 1. 解析事件
    try:
        event = NightingaleEvent.from_callback(data)
    except ValueError as e:
        logger.error(f"解析回调数据失败: {e}")
        return {"success": False, "message": str(e)}

    logger.info(f"📞 收到告警事件: {event.to_log_str()} | 号码={event.phones}")

    # 2. 跳过已恢复事件
    skip_recovery = os.environ.get("SKIP_RECOVERY_CALL", "true").lower() == "true"
    if event.is_recovered and skip_recovery:
        logger.info(f"⏭️ 事件已恢复，跳过语音通知 [{event.rule_name}]")
        return {
            "success": True,
            "message": "已恢复事件，跳过语音通知",
            "skipped": True,
        }

    # 3. 检查号码
    if not event.phones:
        logger.warning(f"⚠️ 未找到通知用户的手机号 [{event.rule_name}]")
        return {"success": False, "message": "无有效手机号"}

    # 4. 初始化阿里云客户端
    try:
        notifier = AliyunVoiceNotifier()
    except ValueError as e:
        logger.error(f"阿里云配置错误: {e}")
        return {"success": False, "message": str(e)}

    # 5. 构建 TTS 参数
    tts_param = event.build_tts_param()

    # 6. 逐个拨打语音通知
    success_count = 0
    results = []
    for phone in event.phones:
        out_id = f"n9e-{event.severity}-{int(time.time())}"
        result = notifier.send_voice(
            called_number=phone,
            tts_param=tts_param,
            out_id=out_id,
        )
        results.append({"phone": phone, "code": result.get("code")})
        if result.get("code") == "OK":
            success_count += 1
        time.sleep(1)  # 避免触发流控

    summary = f"成功 {success_count}/{len(event.phones)}"
    logger.info(f"📊 语音通知完成: {summary}")
    return {
        "success": success_count > 0,
        "message": f"语音通知完成: {summary}",
        "results": results,
    }


# ============================================================
# HTTP 服务
# ============================================================
def create_app():
    """创建 Flask 应用"""
    try:
        from flask import Flask, request, jsonify
    except ImportError:
        logger.error("缺少 Flask 依赖，请执行: pip install flask")
        sys.exit(1)

    app = Flask(__name__)

    @app.route("/voice/notify", methods=["POST"])
    def voice_notify():
        """接收夜莺告警回调"""
        # 解析请求体
        try:
            data = request.get_json(force=True)
        except Exception as e:
            logger.error(f"无法解析请求体: {e}")
            return jsonify({"success": False, "message": f"无效的JSON: {e}"}), 400

        # 记录请求摘要（隐私保护：手机号脱敏）
        log_data = _mask_phones(data)
        logger.info(f"📨 收到回调: {json.dumps(log_data, ensure_ascii=False)[:500]}")

        # 处理告警
        result = handle_alert(data)
        status_code = 200 if result.get("success") else 500
        return jsonify(result), status_code

    @app.route("/health", methods=["GET"])
    def health():
        """健康检查 + 配置状态"""
        config_ok = all([
            os.environ.get("ALIYUN_ACCESS_KEY_ID"),
            os.environ.get("ALIYUN_ACCESS_KEY_SECRET"),
            os.environ.get("ALIYUN_TTS_CODE"),
        ])
        return jsonify({
            "status": "ok" if config_ok else "config_error",
            "nightingale_version": NIGHTINGALE_VERSION,
            "skip_recovery": os.environ.get("SKIP_RECOVERY_CALL", "true"),
            "tts_code": (os.environ.get("ALIYUN_TTS_CODE", "")[:4] + "****" if os.environ.get("ALIYUN_TTS_CODE") else "未配置"),
        })

    @app.route("/debug/echo", methods=["POST", "GET"])
    def debug_echo():
        """
        调试端点：回显夜莺 POST 的原始 JSON（生产环境请删除）
        用于验证夜莺回调数据格式是否正确
        """
        if request.method == "POST":
            try:
                data = request.get_json(force=True)
            except Exception as e:
                return jsonify({"error": str(e)}), 400

            # 完整记录原始 JSON（不脱敏）
            logger.info(f"[DEBUG] 夜莺原始回调数据:\n{json.dumps(data, ensure_ascii=False, indent=2)}")

            # 展示解析结果
            try:
                event = NightingaleEvent.from_callback(data)
                parsed_info = {
                    "severity": event.severity,
                    "severity_text": event.severity_text,
                    "is_recovered": event.is_recovered,
                    "status_text": event.status_text,
                    "rule_name": event.rule_name,
                    "rule_note": event.rule_note,
                    "target_ident": event.target_ident,
                    "trigger_value": event.trigger_value,
                    "group_name": event.group_name,
                    "phones": event.phones,
                    "tts_param": event.build_tts_param(),
                }
            except Exception as e:
                parsed_info = {"error": str(e)}

            return jsonify({
                "raw": data,
                "parsed": parsed_info,
                "hint": "检查 parsed.phones 是否有值，如果没有则说明手机号提取失败",
            })
        else:
            return jsonify({
                "usage": "POST 到此端点可查看夜莺原始回调 JSON 及解析结果",
                "endpoints": {
                    "health": "/health",
                    "notify": "/voice/notify [POST]",
                    "debug_echo": "/debug/echo [POST]",
                },
            })

    @app.route("/", methods=["GET"])
    def index():
        return jsonify({
            "service": "夜莺语音通知服务",
            "version": NIGHTINGALE_VERSION,
            "endpoints": {
                "health": "/health",
                "notify": "/voice/notify [POST]",
                "debug_echo": "/debug/echo [POST]",
            },
        })

    return app


def _mask_phones(data: dict) -> dict:
    """手机号脱敏（日志安全）"""
    import copy
    masked = copy.deepcopy(data)
    if "sendto" in masked and masked["sendto"]:
        p = masked["sendto"]
        if len(p) >= 7:
            masked["sendto"] = p[:3] + "****" + p[-4:]
    if "sendtos" in masked:
        masked["sendtos"] = [
            (p[:3] + "****" + p[-4:] if len(p) >= 7 else p)
            for p in masked["sendtos"] if p
        ]
    return masked


# ============================================================
# 主入口
# ============================================================
def main():
    host = os.environ.get("SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("SERVER_PORT", "8085"))

    logger.info("=" * 60)
    logger.info(f"  夜莺语音通知服务 v{NIGHTINGALE_VERSION}")
    logger.info(f"  监听地址: http://{host}:{port}")
    logger.info(f"  回调地址: http://<IP>:{port}/voice/notify")
    logger.info(f"  健康检查: http://<IP>:{port}/health")
    logger.info("=" * 60)

    app = create_app()
    app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    main()
