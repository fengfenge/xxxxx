#!/bin/bash

# MinIO 备份脚本
# 使用 rclone 将 minio:outline 同步到 minio-backup:outline-bak

# 配置参数
SOURCE_REMOTE="minio"
SOURCE_BUCKET="outline"
DEST_REMOTE="minio-backup"
DEST_BUCKET="outline-bak"
LOG_FILE="/var/log/rclone-minio-backup.log"

# 企业微信群聊机器人 Webhook 地址
WECHAT_WEBHOOK="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=aabe9965-dc02-48de-8c91-a4903096f5e5"

# 获取当前时间
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# 发送企业微信群聊通知
send_wechat_notification() {
    local status=$1
    local detail=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local hostname=$(hostname)

    local content
    if [ "$status" = "success" ]; then
        content="**MinIO Outline备份通知**\n 服务器：${hostname}\n 时间：${timestamp}\n 状态：成功\n 源：${SOURCE_REMOTE}:${SOURCE_BUCKET}\n 目标：${DEST_REMOTE}:${DEST_BUCKET}\n 详情：${detail}"
    else
        content="**MinIO Outline备份通知**\n 服务器：${hostname}\n 时间：${timestamp}\n 状态：失败\n 源：${SOURCE_REMOTE}:${SOURCE_BUCKET}\n 目标：${DEST_REMOTE}:${DEST_BUCKET}\n 错误：${detail}"
    fi

    curl -s -X POST "${WECHAT_WEBHOOK}" \
        -H 'Content-Type: application/json' \
        -d "{\"msgtype\":\"markdown\",\"markdown\":{\"content\":\"${content}\"}}" > /dev/null 2>&1
}

# 主程序
echo "[$TIMESTAMP] 开始执行 MinIO Outline备份..."

rclone sync ${SOURCE_REMOTE}:${SOURCE_BUCKET} ${DEST_REMOTE}:${DEST_BUCKET} \
    --verbose \
    --progress \
    --checksum \
    --log-file=${LOG_FILE}

BACKUP_RESULT=$?

if [ ${BACKUP_RESULT} -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] MinIO Outline备份任务全部完成！"
    send_wechat_notification "success" "同步完成，日志：${LOG_FILE}"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] MinIO Outline备份任务失败！"
    send_wechat_notification "failed" "rclone 退出码：${BACKUP_RESULT}，日志：${LOG_FILE}"
    exit 1
fi

exit 0
