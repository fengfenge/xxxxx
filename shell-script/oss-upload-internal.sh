#!/bin/bash
#===============================================================================
# 阿里云纯内网 ECS → OSS 文件上传脚本（curl + 手动签名）
#
# 原理：
#   ECS 只有内网时，无法访问公网 oss-cn-shenzhen.aliyuncs.com
#   必须使用 OSS 内网 endpoint: oss-cn-shenzhen-internal.aliyuncs.com
#   前提：ECS 和 OSS Bucket 在同一个地域（深圳）
#
#   ★ 内网访问 OSS 不收流量费
#
# 用法：
#   chmod +x oss-upload-internal.sh
#   ./oss-upload-internal.sh                                    # 使用默认配置
#   ./oss-upload-internal.sh /data/ra44w.jsonl my-bucket       # 指定文件和 Bucket
#   ./oss-upload-internal.sh /data/ra44w.jsonl my-bucket path/to/remote.jsonl
#===============================================================================

set -e

# ============================================================
# 阿里云 OSS 配置
# ============================================================
ACCESS_KEY_ID="${ALIYUN_ACCESS_KEY_ID:-}"
ACCESS_KEY_SECRET="${ALIYUN_ACCESS_KEY_SECRET:-}"

# ★ 内网 ECS 请使用内网 endpoint（同地域免流量）
OSS_INTERNAL_ENDPOINT="oss-cn-shenzhen-internal.aliyuncs.com"
# 如果 ECS 后续开通了公网，可改为: oss-cn-shenzhen.aliyuncs.com

# ============================================================
# 参数处理
# ============================================================
# ── 参数: ./script.sh <本地文件> <Bucket名> [OSS路径] ──
if [ $# -lt 2 ]; then
    echo "用法: $0 <本地文件路径> <OSS Bucket名称> [OSS对象路径]"
    echo "示例: $0 /tmp/ra44w.jsonl ops-inspection-report"
    echo "      $0 /tmp/ra44w.jsonl ops-inspection-report data/ra44w.jsonl"
    exit 1
fi

LOCAL_FILE="$1"
BUCKET="$2"
OSS_OBJECT="${3:-ra44w.jsonl}"

# ============================================================
# 前置检查
# ============================================================
if [ ! -f "$LOCAL_FILE" ]; then
    echo "[ERROR] 文件不存在: $LOCAL_FILE"
    exit 1
fi

for cmd in curl openssl date; do
    if ! command -v $cmd &>/dev/null; then
        echo "[ERROR] 缺少命令: $cmd，请先安装"
        exit 1
    fi
done

FILE_SIZE=$(stat -c%s "$LOCAL_FILE" 2>/dev/null || stat -f%z "$LOCAL_FILE" 2>/dev/null)
echo "[INFO] 文件: $LOCAL_FILE ($FILE_SIZE bytes)"
echo "[INFO] 目标: oss://${BUCKET}/${OSS_OBJECT}"
echo "[INFO] Endpoint: ${OSS_INTERNAL_ENDPOINT}"

# ============================================================
# 步骤 1: 测试内网连通性
# ============================================================
echo "[INFO] 测试 OSS 内网连通性..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "https://${BUCKET}.${OSS_INTERNAL_ENDPOINT}" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "000" ]; then
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  ❌ 无法连接 OSS 内网 endpoint！                          ║"
    echo "║                                                          ║"
    echo "║  可能原因：                                               ║"
    echo "║  1. ECS 和 OSS 不在同一地域                                ║"
    echo "║  2. 安全组/防火墙阻止了 443 端口出方向                      ║"
    echo "║  3. VPC 路由未配置正确                                     ║"
    echo "║                                                          ║"
    echo "║  解决方案：                                               ║"
    echo "║  a) 检查 ECS 地域是否为深圳                                ║"
    echo "║  b) 确认安全组出方向放行 443                               ║"
    echo "║  c) 如跨地域，需使用 NAT 网关或中转机                       ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    exit 1
fi
echo "[INFO] OSS 内网连通性 OK (HTTP $HTTP_CODE)"

# ============================================================
# 步骤 2: 计算 OSS 签名（Authorization V1）
#
#  签名字符串格式:
#    VERB + \n
#    + Content-MD5 + \n
#    + Content-Type + \n
#    + Date + \n
#    + CanonicalizedResource
#
#  对于简单 PUT 上传:
#    PUT\n\napplication/json\n{Date}\n/{bucket}/{object}
# ============================================================

# 生成 GMT 格式日期（OSS 要求）
DATE_VALUE=$(env LANG=C TZ=GMT date "+%a, %d %b %Y %H:%M:%S GMT")
CONTENT_TYPE="application/json"
CANONICAL_RESOURCE="/${BUCKET}/${OSS_OBJECT}"

# 构造待签名字符串（注意 Content-MD5 为空）
STRING_TO_SIGN="PUT"$'\n'""$'\n'"${CONTENT_TYPE}"$'\n'"${DATE_VALUE}"$'\n'"${CANONICAL_RESOURCE}"

# 计算签名: Base64(HMAC-SHA1(SecretKey, StringToSign))
SIGNATURE=$(echo -n "$STRING_TO_SIGN" | openssl dgst -sha1 -hmac "$ACCESS_KEY_SECRET" -binary | openssl base64 -A)

echo "[INFO] Date: $DATE_VALUE"
echo "[INFO] 签名计算完成"

# ============================================================
# 步骤 3: 上传文件
# ============================================================
echo "[INFO] 开始上传..."

UPLOAD_URL="https://${BUCKET}.${OSS_INTERNAL_ENDPOINT}/${OSS_OBJECT}"

# 使用 curl 执行 PUT 请求
HTTP_RESPONSE=$(curl -w "\n%{http_code}" -s \
    -X PUT \
    -H "Authorization: OSS ${ACCESS_KEY_ID}:${SIGNATURE}" \
    -H "Date: ${DATE_VALUE}" \
    -H "Content-Type: ${CONTENT_TYPE}" \
    -H "Content-Length: ${FILE_SIZE}" \
    --data-binary "@${LOCAL_FILE}" \
    --connect-timeout 30 \
    --max-time 300 \
    "${UPLOAD_URL}" 2>&1)

# 分离响应体和状态码
HTTP_BODY=$(echo "$HTTP_RESPONSE" | head -n -1)
HTTP_STATUS=$(echo "$HTTP_RESPONSE" | tail -n 1)

# ============================================================
# 步骤 4: 结果检查
# ============================================================
if [ "$HTTP_STATUS" = "200" ]; then
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  ✅ 上传成功！                                            ║"
    echo "║                                                          ║"
    echo "║  文件: oss://${BUCKET}/${OSS_OBJECT}                     ║"
    echo "║  大小: ${FILE_SIZE} bytes                                ║"
    echo "║  URL:  https://${BUCKET}.oss-cn-shenzhen.aliyuncs.com/${OSS_OBJECT}"
    echo "╚══════════════════════════════════════════════════════════╝"
else
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  ❌ 上传失败！HTTP 状态码: ${HTTP_STATUS}                 ║"
    echo "║  响应: ${HTTP_BODY}                                      ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    echo "[DEBUG] 签名调试信息:"
    echo "  URL:          ${UPLOAD_URL}"
    echo "  Date:         ${DATE_VALUE}"
    echo "  Content-Type: ${CONTENT_TYPE}"
    echo "  签名字符串:"
    echo "  -------------"
    # 显示签名字符串中用 * 标记换行符
    echo "$STRING_TO_SIGN" | while IFS= read -r line; do echo "  $line"; done
    echo "  -------------"
    echo "  Signature:    ${SIGNATURE}"
    exit 1
fi
