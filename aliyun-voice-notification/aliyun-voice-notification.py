#!/usr/bin/env python3
"""
夜莺(Nightingale)告警语音通知脚本
通过阿里云语音服务 SingleCallByTts 接口，将夜莺告警事件转为语音电话通知

支持两种接入模式：
  模式1 - 通知脚本 (stdin)：兼容 v5/v6/v7，夜莺通过 stdin 传入 JSON
  模式2 - 自定义通知媒介 (HTTP)：v7+ 推荐方式，夜莺通过 HTTP POST 回调

使用方式：
  通知脚本模式：
    python aliyun-voice-notification.py --mode script
    在夜莺「告警通知 -> 通知设置 -> 通知脚本」中配置此脚本路径

  自定义通知媒介模式：
    python aliyun-voice-notification.py --mode http --port 8085
    在夜莺「告警通知 -> 通知设置 -> 自定义通知媒介」中配置回调 URL

环境变量：
  ALIYUN_ACCESS_KEY_ID      - 阿里云 AccessKey ID（必填）
  ALIYUN_ACCESS_KEY_SECRET  - 阿里云 AccessKey Secret（必填）
  ALIYUN_TTS_CODE           - 阿里云 TTS 语音模板 ID（必填）
  ALIYUN_CALLED_SHOW_NUMBER - 被叫显号（可选，不填为公共模式）
  ALIYUN_PLAY_TIMES         - 播放次数，1~3（可选，默认 2）
  NIGHTINGALE_VOICE_CHANNEL - 夜莺通知渠道名称（可选，默认 voice，仅脚本模式）
  VOICE_STRATEGY            - 语音通知触发策略（可选，默认 severity，仅脚本模式）
  VOICE_MODE                - 运行模式 script/http（可选，默认 script）
  VOICE_HTTP_HOST           - HTTP 模式监听地址（可选，默认 0.0.0.0）
  VOICE_HTTP_PORT           - HTTP 模式监听端口（可选，默认 8085）
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Optional

from alibabacloud_dyvmsapi20170525.client import Client
from alibabacloud_dyvmsapi20170525 import models as dyvmsapi_models
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models

# ============================================================
# 夜莺版本号（用于标识兼容版本）
# ============================================================
NIGHTINGALE_VERSION = "v7.7.0"

# ============================================================
# 日志配置
# ============================================================
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice-notification.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger("nightingale-voice")


# ============================================================
# 阿里云语音通知核心类
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

    def _validate_config(self):
        """校验必填配置"""
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
        """创建阿里云 SDK Client"""
        config = open_api_models.Config(
            access_key_id=self.access_key_id,
            access_key_secret=self.access_key_secret,
        )
        config.endpoint = "dyvmsapi.aliyuncs.com"
        return Client(config)

    def send_voice(self, called_number: str, tts_param: dict, out_id: str = "") -> dict:
        """
        发送语音通知

        Args:
            called_number: 被叫号码
            tts_param: TTS 模板变量字典，如 {"rule_name": "CPU告警", "severity": "P1"}
            out_id: 自定义回调ID（可选）

        Returns:
            阿里云 API 返回结果字典
        """
        request = dyvmsapi_models.SingleCallByTtsRequest(
            called_number=called_number,
            tts_code=self.tts_code,
            tts_param=json.dumps(tts_param, ensure_ascii=False),
            play_times=self.play_times,
        )

        # 设置被叫显号（专属模式）
        if self.called_show_number:
            request.called_show_number = self.called_show_number

        # 设置自定义ID
        if out_id:
            request.out_id = out_id

        runtime = util_models.RuntimeOptions(
            read_timeout=10000,
            connect_timeout=10000,
        )

        try:
            response = self.client.single_call_by_tts_with_options(request, runtime)
            result = {
                "code": response.body.code,
                "message": response.body.message,
                "request_id": response.body.request_id,
                "call_id": response.body.call_id,
            }
            if response.body.code == "OK":
                logger.info(f"语音通知发送成功 -> {called_number}, CallId={response.body.call_id}")
            else:
                logger.error(f"语音通知发送失败 -> {called_number}, Code={response.body.code}, Msg={response.body.message}")
            return result
        except Exception as e:
            logger.error(f"语音通知调用异常 -> {called_number}, Error={e}")
            return {"code": "EXCEPTION", "message": str(e)}


# ============================================================
# 夜莺告警事件处理 - 通用
# ============================================================
SEVERITY_MAP = {
    1: "P1-致命",
    2: "P2-警告",
    3: "P3-信息",
}


def build_tts_param(severity: int, status_text: str, rule_name: str,
                    target_ident: str, trigger_value: str,
                    rule_note: str = "", group_name: str = "") -> dict:
    """
    构建阿里云 TTS 模板变量

    注意：模板变量需要与你在阿里云语音控制台创建的 TTS 模板中的占位符对应。
    默认模板变量格式示例：
      尊敬的用户，您有${status_text}告警，级别${severity_text}，规则${rule_name}，监控对象${target_ident}，当前值${trigger_value}。

    如果你的模板变量不同，请修改此函数。
    """
    severity_text = SEVERITY_MAP.get(severity, f"P{severity}")
    params = {
        "status_text": status_text,
        "severity_text": severity_text,
        "rule_name": rule_name[:20],       # 截断，避免过长
        "target_ident": target_ident[:20],
        "trigger_value": trigger_value[:15],
    }
    # 可选变量（阿里云 TTS 模板中如未引用这些变量，会自动忽略）
    if rule_note:
        params["rule_note"] = rule_note[:30]
    if group_name:
        params["group_name"] = group_name[:20]
    return params


def send_voice_for_event(phones: list, severity: int, status_text: str,
                         rule_name: str, target_ident: str, trigger_value: str,
                         rule_note: str = "", group_name: str = "",
                         out_id_prefix: str = "n9e") -> dict:
    """
    通用语音通知发送逻辑

    Args:
        phones: 被叫号码列表
        severity: 告警级别
        status_text: 告警状态文本
        rule_name: 规则名称
        target_ident: 监控对象标识
        trigger_value: 触发值
        rule_note: 规则备注（可选）
        group_name: 业务组名称（可选）
        out_id_prefix: out_id 前缀

    Returns:
        发送结果摘要
    """
    if not phones:
        logger.warning("无有效手机号，无法拨打语音通知")
        return {"success": False, "message": "无有效手机号"}

    try:
        notifier = AliyunVoiceNotifier()
    except ValueError as e:
        logger.error(f"阿里云配置错误: {e}")
        return {"success": False, "message": str(e)}

    tts_param = build_tts_param(
        severity=severity,
        status_text=status_text,
        rule_name=rule_name,
        target_ident=target_ident,
        trigger_value=trigger_value,
        rule_note=rule_note,
        group_name=group_name,
    )

    success_count = 0
    results = []
    for phone in phones:
        out_id = f"{out_id_prefix}-{severity}-{int(time.time())}"
        result = notifier.send_voice(
            called_number=phone,
            tts_param=tts_param,
            out_id=out_id,
        )
        results.append({"phone": phone, "code": result.get("code")})
        if result.get("code") == "OK":
            success_count += 1
        # 避免触发阿里云流控（1次/分钟）
        time.sleep(1)

    logger.info(f"语音通知完成: 成功 {success_count}/{len(phones)}")
    return {
        "success": success_count > 0,
        "message": f"语音通知完成: 成功 {success_count}/{len(phones)}",
        "results": results,
    }


# ============================================================
# 模式1: 通知脚本模式 (stdin) - 兼容 v5/v6/v7
# ============================================================
VOICE_STRATEGY = os.environ.get("VOICE_STRATEGY", "severity")
VOICE_SEVERITY_LEVELS = os.environ.get("VOICE_SEVERITY_LEVELS", "1")
VOICE_RULE_KEYWORDS = os.environ.get("VOICE_RULE_KEYWORDS", "")
VOICE_CHANNEL = os.environ.get("NIGHTINGALE_VOICE_CHANNEL", "voice")


def parse_nightingale_event(payload: dict) -> dict:
    """
    解析夜莺通知脚本传入的告警事件 (stdin JSON)

    适用于 v5/v6/v7 的通知脚本模式，JSON 格式：
    {"event": {...}, "tpls": {...}}

    Args:
        payload: 从 stdin 读取的 JSON 数据

    Returns:
        解析后的事件摘要字典
    """
    event = payload.get("event", {})
    tpls = payload.get("tpls", {})

    severity = event.get("severity", 3)
    is_recovered = event.get("is_recovered", False)
    rule_name = event.get("rule_name", "未知规则")
    rule_note = event.get("rule_note", "")
    target_ident = event.get("target_ident", "未知对象")
    trigger_value = event.get("trigger_value", "")
    group_name = event.get("group_name", "")

    # 优先使用 tpls 中渲染好的模板文本
    tpls_text = tpls.get("wecom", "") or tpls.get("feishu", "") or tpls.get("dingtalk", "")

    # 获取通知用户列表
    notify_users = event.get("notify_users_obj", [])
    phones = [u.get("phone", "") for u in notify_users if u.get("phone")]

    # 获取通知渠道
    notify_channels = event.get("notify_channels", [])

    severity_text = SEVERITY_MAP.get(severity, f"P{severity}")
    status_text = "已恢复" if is_recovered else "告警中"

    return {
        "severity": severity,
        "severity_text": severity_text,
        "status_text": status_text,
        "rule_name": rule_name,
        "rule_note": rule_note,
        "target_ident": target_ident,
        "trigger_value": trigger_value,
        "group_name": group_name,
        "is_recovered": is_recovered,
        "notify_channels": notify_channels,
        "phones": phones,
        "tpls_text": tpls_text,
    }


def should_voice_notify(parsed: dict) -> bool:
    """
    根据配置的策略判断是否需要语音通知（仅脚本模式使用）

    Returns:
        True 表示需要拨打语音，False 表示跳过
    """
    if VOICE_STRATEGY == "severity":
        # 按告警级别判断
        allowed = [int(s.strip()) for s in VOICE_SEVERITY_LEVELS.split(",") if s.strip()]
        if parsed["severity"] in allowed:
            logger.info(f"策略[severity]: 级别 {parsed['severity_text']} 在允许列表中，触发语音通知")
            return True
        else:
            logger.info(f"策略[severity]: 级别 {parsed['severity_text']} 不在允许列表({VOICE_SEVERITY_LEVELS})中，跳过")
            return False

    elif VOICE_STRATEGY == "rule_name":
        # 按规则名称关键字匹配
        if not VOICE_RULE_KEYWORDS:
            logger.warning("策略[rule_name]: 未配置 VOICE_RULE_KEYWORDS，跳过所有语音通知")
            return False
        keywords = [k.strip() for k in VOICE_RULE_KEYWORDS.split(",") if k.strip()]
        for kw in keywords:
            if kw in parsed["rule_name"]:
                logger.info(f"策略[rule_name]: 规则名 '{parsed['rule_name']}' 匹配关键字 '{kw}'，触发语音通知")
                return True
        logger.info(f"策略[rule_name]: 规则名 '{parsed['rule_name']}' 未匹配任何关键字({VOICE_RULE_KEYWORDS})，跳过")
        return False

    elif VOICE_STRATEGY == "channel":
        # 按通知渠道判断（原逻辑）
        if VOICE_CHANNEL in parsed["notify_channels"]:
            logger.info(f"策略[channel]: 通知渠道包含 {VOICE_CHANNEL}，触发语音通知")
            return True
        else:
            logger.info(f"策略[channel]: 通知渠道 {parsed['notify_channels']} 不包含 {VOICE_CHANNEL}，跳过")
            return False

    else:
        logger.warning(f"未知策略: {VOICE_STRATEGY}，跳过语音通知")
        return False


def run_script_mode():
    """通知脚本模式：从 stdin 读取夜莺告警事件 JSON"""
    # 1. 从 stdin 读取夜莺告警事件
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        logger.error(f"无法解析 stdin JSON: {e}")
        sys.exit(1)

    logger.info(f"收到夜莺告警事件: {json.dumps(payload, ensure_ascii=False)[:500]}")

    # 2. 解析事件
    parsed = parse_nightingale_event(payload)
    logger.info(
        f"解析事件: {parsed['severity_text']} | {parsed['status_text']} | "
        f"规则={parsed['rule_name']} | 对象={parsed['target_ident']}"
    )

    # 3. 根据策略判断是否需要语音通知
    if not should_voice_notify(parsed):
        sys.exit(0)

    # 4. 已恢复事件可选择不拨打语音（可配置）
    skip_recovery = os.environ.get("SKIP_RECOVERY_CALL", "true").lower() == "true"
    if parsed["is_recovered"] and skip_recovery:
        logger.info("告警已恢复，跳过语音通知（可通过 SKIP_RECOVERY_CALL=false 开启恢复通知）")
        sys.exit(0)

    # 5. 发送语音通知
    result = send_voice_for_event(
        phones=parsed["phones"],
        severity=parsed["severity"],
        status_text=parsed["status_text"],
        rule_name=parsed["rule_name"],
        target_ident=parsed["target_ident"],
        trigger_value=parsed["trigger_value"],
        rule_note=parsed["rule_note"],
        group_name=parsed["group_name"],
        out_id_prefix="n9e",
    )

    sys.exit(0 if result["success"] else 1)


# ============================================================
# 模式2: 自定义通知媒介模式 (HTTP) - v7+ 推荐
# ============================================================
def parse_v7_callback(data: dict) -> dict:
    """
    解析夜莺 v7 自定义通知媒介的回调数据

    v7 自定义通知媒介 HTTP POST 格式（通知规则模式）：
    方式1 - 通知规则（v7.7+）: 逐个接收人发送
    {
        "events": [{...}],
        "sendto": "13800138000",
        "tpl": {"content": "..."}
    }

    方式2 - 早期自定义媒介: 批量发送
    {
        "events": [{...}],
        "sendtos": ["13800138000", "13900139000"],
        "tpl": {"content": "..."}
    }

    Args:
        data: HTTP POST 请求体 JSON

    Returns:
        解析后的事件摘要字典
    """
    events = data.get("events", [])
    tpl = data.get("tpl", {})

    if not events:
        raise ValueError("回调数据中 events 为空")

    event = events[0]  # 开源版通常只有一条事件

    severity = event.get("severity", 3)
    is_recovered = event.get("is_recovered", False)
    rule_name = event.get("rule_name", "未知规则")
    rule_note = event.get("rule_note", "")
    target_ident = event.get("target_ident", "未知对象")
    trigger_value = event.get("trigger_value", "")

    # v7 新增字段
    group_name = event.get("group_name", "")
    tags = event.get("tags", [])
    trigger_time = event.get("trigger_time", 0)
    tags_map = event.get("tags_map", {})

    severity_text = SEVERITY_MAP.get(severity, f"P{severity}")
    status_text = "已恢复" if is_recovered else "告警中"

    # 兼容两种格式：v7.7+ 使用 sendto（单个），早期版本使用 sendtos（数组）
    sendto = data.get("sendto", "")
    sendtos = data.get("sendtos", [])

    if sendto:
        # v7.7+ 通知规则模式，sendto 为单个手机号
        phones = [sendto] if sendto else []
    elif sendtos:
        # 早期自定义媒介模式，sendtos 为手机号列表
        phones = [s for s in sendtos if s]
    else:
        phones = []

    return {
        "severity": severity,
        "severity_text": severity_text,
        "status_text": status_text,
        "rule_name": rule_name,
        "rule_note": rule_note,
        "target_ident": target_ident,
        "trigger_value": trigger_value,
        "group_name": group_name,
        "is_recovered": is_recovered,
        "phones": phones,
        "tags": tags,
        "tags_map": tags_map,
        "trigger_time": trigger_time,
        "tpl_content": tpl.get("content", ""),
    }


def handle_v7_callback(data: dict) -> dict:
    """
    处理 v7 自定义通知媒介回调

    Returns:
        处理结果摘要
    """
    try:
        parsed = parse_v7_callback(data)
    except ValueError as e:
        logger.error(f"解析 v7 回调数据失败: {e}")
        return {"success": False, "message": str(e)}

    logger.info(
        f"v7回调事件: {parsed['severity_text']} | {parsed['status_text']} | "
        f"规则={parsed['rule_name']} | 对象={parsed['target_ident']} | "
        f"被叫号码={parsed['phones']}"
    )
    if parsed.get("tpl_content"):
        logger.info(f"v7渲染模板: {parsed['tpl_content'][:200]}")

    # 已恢复事件可选择不拨打语音（可配置）
    skip_recovery = os.environ.get("SKIP_RECOVERY_CALL", "true").lower() == "true"
    if parsed["is_recovered"] and skip_recovery:
        logger.info("告警已恢复，跳过语音通知（可通过 SKIP_RECOVERY_CALL=false 开启恢复通知）")
        return {"success": True, "message": "已恢复事件，跳过语音通知", "skipped": True}

    # 发送语音通知
    return send_voice_for_event(
        phones=parsed["phones"],
        severity=parsed["severity"],
        status_text=parsed["status_text"],
        rule_name=parsed["rule_name"],
        target_ident=parsed["target_ident"],
        trigger_value=parsed["trigger_value"],
        rule_note=parsed.get("rule_note", ""),
        group_name=parsed.get("group_name", ""),
        out_id_prefix="n9e-v7",
    )


def run_http_mode(host: str = "0.0.0.0", port: int = 8085):
    """
    自定义通知媒介模式：启动 HTTP 服务接收夜莺 v7+ 回调

    夜莺 v7 自定义通知媒介配置：
      - URL: http://<本机IP>:<port>/voice/notify
      - 请求方法: POST
      - 请求体:
        {
            "events": {{ jsonMarshal $events }},
            "sendto": "{{ $sendto }}",
            "tpl": {{ jsonMarshal $tpl }}
        }
    """
    try:
        from flask import Flask, request, jsonify
    except ImportError:
        logger.error("HTTP 模式需要 Flask，请执行: pip install flask")
        sys.exit(1)

    app = Flask(__name__)

    @app.route("/voice/notify", methods=["POST"])
    def voice_notify():
        """接收夜莺 v7+ 自定义通知媒介回调"""
        try:
            data = request.get_json(force=True)
        except Exception as e:
            logger.error(f"解析请求体失败: {e}")
            return jsonify({"success": False, "message": f"无效的JSON: {e}"}), 400

        logger.info(f"收到 v7 回调请求: {json.dumps(data, ensure_ascii=False)[:500]}")
        result = handle_v7_callback(data)
        status_code = 200 if result.get("success") else 500
        return jsonify(result), status_code

    @app.route("/health", methods=["GET"])
    def health():
        """健康检查"""
        return jsonify({
            "status": "ok",
            "mode": "http",
            "nightingale_version": NIGHTINGALE_VERSION,
        })

    logger.info(f"启动 HTTP 服务: http://{host}:{port}")
    logger.info(f"回调地址: http://<本机IP>:{port}/voice/notify")
    logger.info(f"兼容夜莺版本: {NIGHTINGALE_VERSION}+")
    app.run(host=host, port=port, threaded=True)


# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="夜莺告警语音通知 - 阿里云语音服务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
运行模式说明：
  script  通知脚本模式（默认），兼容 v5/v6/v7，通过 stdin 接收 JSON
  http    自定义通知媒介模式，v7+ 推荐，启动 HTTP 服务接收回调

示例：
  # 通知脚本模式
  echo '{"event":{...}}' | python aliyun-voice-notification.py --mode script

  # HTTP 服务模式
  python aliyun-voice-notification.py --mode http --port 8085
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["script", "http"],
        default=os.environ.get("VOICE_MODE", "script"),
        help="运行模式: script(通知脚本,默认) / http(自定义通知媒介,v7+推荐)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("VOICE_HTTP_HOST", "0.0.0.0"),
        help="HTTP 模式监听地址 (默认: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("VOICE_HTTP_PORT", "8085")),
        help="HTTP 模式监听端口 (默认: 8085)",
    )

    args = parser.parse_args()

    if args.mode == "http":
        logger.info(f"运行模式: 自定义通知媒介 (HTTP) - 适用于夜莺 {NIGHTINGALE_VERSION}+")
        run_http_mode(host=args.host, port=args.port)
    else:
        logger.info(f"运行模式: 通知脚本 (stdin) - 兼容夜莺 v5/v6/v7 (当前版本 {NIGHTINGALE_VERSION})")
        run_script_mode()


if __name__ == "__main__":
    main()
