#!/bin/bash
set -euo pipefail

# ==================== 配置区域 ====================
GITLAB_BACKUP_DIR="/home/gitlab-back/backups"
REMOTE_HOST="192.168.13.254"
REMOTE_USER="root"
REMOTE_PATH="/opt/remote-gitlab-bak"
# 企业微信群聊机器人 Webhook 地址
WECHAT_WEBHOOK="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_WEBHOOK_KEY"
# ==================== 配置结束 ====================

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# 发送企业微信群聊通知
send_wechat_notification() {
    local status=$1
    local detail=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local hostname=$(hostname)

    local content
    if [ "$status" = "success" ]; then
        content="**GitLab 备份通知**\n 服务器：${hostname}\n 时间：${timestamp}\n 状态：成功\n 详情：${detail}"
    else
        content="**GitLab 备份通知**\n 服务器：${hostname}\n 时间：${timestamp}\n 状态：失败\n 错误：${detail}"
    fi

    curl -s -X POST "${WECHAT_WEBHOOK}" \
        -H 'Content-Type: application/json' \
        -d "{\"msgtype\":\"markdown\",\"markdown\":{\"content\":\"${content}\"}}" > /dev/null 2>&1
}

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# ==================== 主流程 ====================
log "========== GitLab 备份开始 =========="

# 1. 执行 GitLab 备份
log "执行 GitLab 备份..."
/opt/gitlab/bin/gitlab-backup create CRON=1

if [ $? -ne 0 ]; then
    log "ERROR: GitLab 备份失败"
    send_wechat_notification "failed" "gitlab-backup create 执行失败"
    exit 1
fi

# 2. 获取最新备份文件
LATEST_BACKUP=$(sudo ls -t ${GITLAB_BACKUP_DIR}/*.tar 2>/dev/null | head -n1)

if [ -z "$LATEST_BACKUP" ]; then
    log "ERROR: 未找到备份文件"
    send_wechat_notification "failed" "备份目录中未找到 .tar 文件"
    exit 1
fi

BACKUP_SIZE=$(du -h "$LATEST_BACKUP" | cut -f1)
log "最新备份: ${LATEST_BACKUP} (${BACKUP_SIZE})"

# 3. 同步到远程服务器
log "同步备份到远程服务器 ${REMOTE_HOST}..."
rsync -av "$LATEST_BACKUP" ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/

if [ $? -ne 0 ]; then
    log "ERROR: 远程同步失败"
    send_wechat_notification "failed" "rsync 同步到 ${REMOTE_HOST} 失败"
    exit 1
fi

log "========== GitLab 备份完成 =========="
log "备份文件: ${LATEST_BACKUP} (${BACKUP_SIZE})"

# 4. 发送成功通知
send_wechat_notification "success" "备份文件: $(basename ${LATEST_BACKUP}), 大小: ${BACKUP_SIZE}, 已同步至: ${REMOTE_HOST}:${REMOTE_PATH}"

exit 0
