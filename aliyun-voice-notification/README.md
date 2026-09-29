# 夜莺(Nightingale)告警语音通知

通过阿里云语音服务，将夜莺告警事件转为语音电话通知。

**兼容版本**：夜莺 v5 / v6 / v7（前端 v7.7.0，后端 v7.7.2）

## 架构流程

### 模式1: 通知脚本 (stdin) - 兼容 v5/v6/v7

```
夜莺告警触发 → stdin 传入 JSON → 脚本解析事件 → 调用阿里云 SingleCallByTts API → 拨打语音电话
```

### 模式2: 自定义通知媒介 (HTTP) - v7+ 推荐

```
夜莺告警触发 → 通知规则匹配 → HTTP POST 回调 → 脚本解析请求 → 调用阿里云 SingleCallByTts API → 拨打语音电话
```

## 前置准备

### 1. 阿里云侧

- 开通 [阿里云语音服务](https://www.aliyun.com/product/vms)
- 创建 RAM 用户并授权 `AliyunDyvmsFullAccess`
- 获取 AccessKey ID 和 AccessKey Secret
- 在语音控制台创建 **TTS 语音通知模板**，示例模板内容：

```
尊敬的用户，您有${status_text}告警，级别${severity_text}，规则${rule_name}，监控对象${target_ident}，当前值${trigger_value}。
```

> **提示**：阿里云 TTS 使用 `${变量名}` 占位符，与夜莺的 `{{$event.字段名}}` 模板语法不同。夜莺模板用于渲染通知文本，阿里云 TTS 模板用于语音播报。

- 记录生成的 **TTS 模板 ID**（格式如 `TTS_28726****`）

### 2. 夜莺侧

- 确保夜莺用户资料中填写了**手机号**
- 通知规则中配置语音通知渠道

## 安装部署

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

在夜莺所在服务器上配置以下环境变量（或写入 `/etc/profile.d/nightingale-voice.sh`）：

```bash
# 必填
export ALIYUN_ACCESS_KEY_ID="你的AccessKey ID"
export ALIYUN_ACCESS_KEY_SECRET="你的AccessKey Secret"
export ALIYUN_TTS_CODE="TTS_28726****"           # 你的 TTS 模板 ID

# 运行模式
export VOICE_MODE="script"                        # script(通知脚本) / http(自定义通知媒介)

# 通知脚本模式专用配置
export VOICE_STRATEGY="severity"                  # 触发策略: severity(按级别) / rule_name(按规则名) / channel(按渠道)
export VOICE_SEVERITY_LEVELS="1"                  # 策略=severity时，触发语音的级别(1=P1,2=P2,3=P3)，逗号分隔，默认 "1"
export VOICE_RULE_KEYWORDS=""                      # 策略=rule_name时，规则名关键字，逗号分隔，如 "CPU,内存,磁盘"
export NIGHTINGALE_VOICE_CHANNEL="voice"          # 策略=channel时，通知渠道名，默认 voice

# HTTP 模式专用配置
export VOICE_HTTP_HOST="0.0.0.0"                  # 监听地址
export VOICE_HTTP_PORT="8085"                      # 监听端口

# 可选 - 其他
export ALIYUN_CALLED_SHOW_NUMBER="0571****5678"   # 被叫显号（专属模式），不填为公共模式
export ALIYUN_PLAY_TIMES="2"                      # 播放次数 1~3，默认 2
export SKIP_RECOVERY_CALL="true"                  # 是否跳过恢复通知，默认 true
```

---

## 模式1: 通知脚本部署 (兼容 v5/v6/v7)

### 配置夜莺通知脚本

进入夜莺管理后台：**告警通知 → 通知设置 → 通知脚本**

- **启用**：打开开关
- **超时**：设置为 30（秒），切勿设为 0
- **脚本内容方式**：选择「指定脚本路径」，填写脚本绝对路径，如：

```
/opt/nightingale/script/aliyun-voice-notification.py
```

确保脚本有可执行权限：

```bash
chmod +x /opt/nightingale/script/aliyun-voice-notification.py
```

### 测试脚本模式

```bash
echo '{
  "event": {
    "severity": 1,
    "is_recovered": false,
    "rule_name": "CPU使用率超过90%",
    "rule_note": "检查服务器负载",
    "target_ident": "web-server-01",
    "trigger_value": "95.3%",
    "group_name": "生产环境",
    "notify_channels": ["voice", "email"],
    "notify_users_obj": [
      {"username": "admin", "phone": "13800138000", "email": "admin@example.com"}
    ]
  },
  "tpls": {}
}' | python3 aliyun-voice-notification.py --mode script
```

---

## 模式2: 自定义通知媒介部署 (v7+ 推荐)

### 第一步：创建联系方式

进入夜莺：**告警通知 → 联系方式管理**

创建 `phone` 联系方式（如已存在可跳过），各用户自行填写手机号。

### 第二步：启动 HTTP 服务

```bash
# 前台启动
python3 aliyun-voice-notification.py --mode http --port 8085

# 后台启动（推荐使用 systemd）
nohup python3 aliyun-voice-notification.py --mode http --port 8085 > /dev/null 2>&1 &
```

#### systemd 服务配置（推荐）

创建 `/etc/systemd/system/nightingale-voice.service`：

```ini
[Unit]
Description=Nightingale Voice Notification Service
After=network.target

[Service]
Type=simple
User=nightingale
WorkingDirectory=/opt/nightingale/script
ExecStart=/usr/bin/python3 /opt/nightingale/script/aliyun-voice-notification.py --mode http --port 8085
Restart=always
RestartSec=5

# 环境变量
EnvironmentFile=/etc/profile.d/nightingale-voice.sh

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable nightingale-voice
systemctl start nightingale-voice
```

### 第三步：创建消息模板

进入夜莺：**告警通知 → 通知模板**

创建语音通知消息模板：
- **媒介类型**：`voicecall`（自定义名称，需与通知媒介一致）
- **内容**（示例）：

```
级别状态: S{{$event.Severity}} {{if $event.IsRecovered}}Recovered{{else}}Triggered{{end}}
规则标题: {{$event.RuleName}}{{if $event.RuleNote}}
规则备注: {{$event.RuleNote}}{{end}}{{if $event.TargetIdent}}
监控对象: {{$event.TargetIdent}}{{end}}
监控指标: {{$event.TagsJSON}}{{if not $event.IsRecovered}}
触发时值: {{$event.TriggerValue}}{{end}}
{{if $event.IsRecovered}}恢复时间: {{timeformat $event.LastEvalTime}}{{else}}首次触发时间: {{timeformat $event.FirstTriggerTime}}{{end}}
发送时间: {{timestamp}}
```

> **参考**：模板语法与 wecom 等内置模板一致，使用 Go template 语法。自定义通知媒介中事件对象为 `$event`（内置模板为 `.`）。语音模板不需要 Markdown/HTML 格式，纯文本即可。

### 第四步：创建自定义通知媒介

进入夜莺：**告警通知 → 通知设置 → 通知媒介**

创建自定义通知媒介：
- **媒介类型**：`voicecall`（与消息模板一致）
- **联系方式**：选择 `Phone`
- **请求方法**：POST
- **URL**：`http://<脚本所在机器IP>:8085/voice/notify`
- **请求头**：`Content-Type: application/json`
- **请求体**：

```json
{
    "events": {{ jsonMarshal $events }},
    "sendto": "{{ $sendto }}",
    "tpl": {{ jsonMarshal $tpl }}
}
```

> **说明**：`{{ $sendto }}` 是夜莺内置变量，会自动替换为接收人的手机号（来自用户 Profile 中的 Phone 字段）。夜莺会**逐个接收人**发送请求，每次 `sendto` 只有一个手机号。

### 第五步：创建通知规则

进入夜莺：**告警通知 → 通知规则**

创建通知规则：
- 选择通知媒介：`voicecall`
- 配置接收人/团队
- 设置触发条件（如仅 P1 级别触发语音通知）

### 验证 HTTP 模式

```bash
# 健康检查
curl http://localhost:8085/health

# 模拟回调
curl -X POST http://localhost:8085/voice/notify \
  -H "Content-Type: application/json" \
  -d '{
    "events": [{
      "severity": 1,
      "is_recovered": false,
      "rule_name": "CPU使用率超过90%",
      "target_ident": "web-server-01",
      "trigger_value": "95.3%",
      "group_name": "生产环境"
    }],
    "sendto": "13800138000",
    "tpl": {"content": "P1告警: CPU使用率超过90%"}
  }'
```

---

## TTS 模板变量说明

脚本会向阿里云 TTS 模板传入以下变量，请确保你的模板包含对应占位符：

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `status_text` | 告警状态 | `告警中` / `已恢复` |
| `severity_text` | 告警级别 | `P1-致命` / `P2-警告` / `P3-信息` |
| `rule_name` | 规则名称（截断20字） | `CPU使用率超限` |
| `target_ident` | 监控对象（截断20字） | `web-server-01` |
| `trigger_value` | 触发值（截断15字） | `95.3%` |
| `rule_note` | 规则备注（截断30字，可选） | `检查服务器负载` |
| `group_name` | 业务组名称（截断20字，可选） | `生产环境` |

阿里云 TTS 模板示例（含可选变量）：

```
尊敬的用户，您有${status_text}告警，级别${severity_text}，规则${rule_name}，监控对象${target_ident}，当前值${trigger_value}。${group_name}
```

> **注意**：阿里云 TTS 模板中未使用的变量会自动忽略，无需修改模板。如果你的模板变量不同，请修改脚本中 `build_tts_param()` 函数。

## 两种模式对比

| 对比项 | 通知脚本 (stdin) | 自定义通知媒介 (HTTP) |
|--------|-------------------|-----------------------|
| 适用版本 | v5 / v6 / v7 | v7+ |
| 数据传输 | stdin | HTTP POST |
| 部署位置 | 夜莺同机器 | 可独立部署 |
| 手机号来源 | 从 `notify_users_obj` 提取 | `sendto` 直接传入 |
| 策略过滤 | 脚本内配置策略 | 通知规则中配置 |
| 高可用 | 依赖夜莺进程 | 独立服务，可做负载 |
| 推荐程度 | 兼容方案 | **v7 推荐** |

## 查看日志

```bash
tail -f voice-notification.log
```

## 费用参考

阿里云语音通知按次计费，参考价格：

| 项目 | 价格 |
|------|------|
| 语音通知（国内） | 约 ¥0.05~0.10/次 |

具体价格以 [阿里云语音服务定价](https://www.aliyun.com/price/product?spm=5176.7933683.J_5253135400.3.71372a66T2LYbF#/vms/detail) 为准。

## 注意事项

1. **流控限制**：同一号码 1次/分钟、5次/小时、20次/24小时（专属模式可申请调整）
2. **外呼时间**：阿里云限制 12:00~14:00 和 21:00~次日 8:00 不可外呼（申请专属模式可放宽）
3. **恢复通知**：默认不拨打恢复通知，可通过 `SKIP_RECOVERY_CALL=false` 开启
4. **日志轮转**：建议配置 logrotate 对 `voice-notification.log` 进行轮转
5. **HTTP 模式安全**：生产环境建议配合 nginx 反向代理，添加鉴权或限制内网访问
