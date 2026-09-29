#!/bin/bash

# PostgreSQL 增量备份脚本
# 基于 WAL 日志实现增量备份，已禁用
# 策略：每周日执行全量备份，其他时间执行增量备份（WAL日志备份），已禁用

# 配置参数
CONTAINER_NAME="postgres"
DB_USER="iotcloud"
BACKUP_DIR="/data/pgbackup"
FULL_BACKUP_DIR="${BACKUP_DIR}/full"
INCR_BACKUP_DIR="${BACKUP_DIR}/incremental"
WAL_ARCHIVE_DIR="/var/lib/postgresql/data/pg_wal/archive"
REMOTE_HOST="192.168.13.254"
REMOTE_USER="root"
REMOTE_PASSWORD="1"  # 远程服务器密码
REMOTE_DIR="/opt/remote-outline-postgresql-bak"
RETENTION_DAYS=30

# 企业微信群聊机器人 Webhook 地址
WECHAT_WEBHOOK="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_WEBHOOK_KEY"

# SSH 命令封装（使用 sshpass）
SSH_CMD="sshpass -p ${REMOTE_PASSWORD} ssh -o StrictHostKeyChecking=no"
SCP_CMD="sshpass -p ${REMOTE_PASSWORD} scp -o StrictHostKeyChecking=no"

# 创建备份目录
mkdir -p ${FULL_BACKUP_DIR}
mkdir -p ${INCR_BACKUP_DIR}

# 获取当前日期信息
DATE=$(date +%Y%m%d)
DAY_OF_WEEK=$(date +%u)  # 1=周一, 7=周日
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# 检查 WAL 归档是否已配置
check_wal_config() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 检查 PostgreSQL WAL 配置..."
    
    # 检查 wal_level
    WAL_LEVEL=$(docker exec ${CONTAINER_NAME} psql -U ${DB_USER} -c "SHOW wal_level;" -t -A 2>/dev/null)
    if [ "$WAL_LEVEL" != "replica" ] && [ "$WAL_LEVEL" != "logical" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 警告: wal_level 当前为 '$WAL_LEVEL'，建议设置为 'replica' 或 'logical'"
        return 1
    fi
    
    # 检查 archive_mode
    ARCHIVE_MODE=$(docker exec ${CONTAINER_NAME} psql -U ${DB_USER} -c "SHOW archive_mode;" -t -A 2>/dev/null)
    if [ "$ARCHIVE_MODE" != "on" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 警告: archive_mode 当前为 '$ARCHIVE_MODE'，需要设置为 'on'"
        return 1
    fi
    
    # 检查归档目录
    docker exec ${CONTAINER_NAME} mkdir -p ${WAL_ARCHIVE_DIR} 2>/dev/null
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WAL 配置检查通过"
    return 0
}

# 执行全量备份
perform_full_backup() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 执行全量备份..."
    BACKUP_NAME="full_backup_${DATE}"
    FULL_BACKUP_PATH="${FULL_BACKUP_DIR}/${BACKUP_NAME}"
    
    # 使用 pg_dumpall 创建逻辑备份
    docker exec ${CONTAINER_NAME} pg_dumpall -U ${DB_USER} -f /tmp/${BACKUP_NAME}.sql
    
    if [ $? -ne 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 全量备份失败！"
        return 1
    fi
    
    # 压缩备份文件
    docker exec ${CONTAINER_NAME} gzip /tmp/${BACKUP_NAME}.sql
    
    # 复制到宿主机
    docker cp ${CONTAINER_NAME}:/tmp/${BACKUP_NAME}.sql.gz ${FULL_BACKUP_PATH}.sql.gz
    
    if [ $? -ne 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 复制全量备份失败！"
        return 1
    fi
    
    # 清理容器内临时文件
    docker exec ${CONTAINER_NAME} rm -f /tmp/${BACKUP_NAME}.sql.gz
    
    # 发送到远程备份机
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 发送全量备份到远程..."
    ${SSH_CMD} ${REMOTE_USER}@${REMOTE_HOST} "mkdir -p ${REMOTE_DIR}/full" 2>/dev/null
    ${SCP_CMD} ${FULL_BACKUP_PATH}.sql.gz ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/full/
    
    if [ $? -ne 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 发送全量备份失败！"
        return 1
    fi
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 全量备份完成！"
    echo "备份文件：${FULL_BACKUP_PATH}.sql.gz"
    return 0
}

# 执行增量备份（已禁用，暂不使用）
# perform_incremental_backup() {
#     echo "[$(date '+%Y-%m-%d %H:%M:%S')] 执行增量备份（WAL日志）..."
#     
#     # 获取最新的全量备份
#     LATEST_FULL=$(ls -1 ${FULL_BACKUP_DIR}/full_backup_*.tar.gz 2>/dev/null | sort -r | head -1)
#     
#     if [ -z "${LATEST_FULL}" ]; then
#         echo "[$(date '+%Y-%m-%d %H:%M:%S')] 未找到全量备份，先执行全量备份..."
#         perform_full_backup
#         return $?
#     fi
#     
#     # 获取上次备份的 WAL 位置
#     LAST_WAL_POS=$(cat ${BACKUP_DIR}/last_wal_position 2>/dev/null || echo "")
#     
#     # 创建增量备份目录
#     INCR_NAME="incr_backup_${DATE}"
#     INCR_PATH="${INCR_BACKUP_DIR}/${INCR_NAME}"
#     
#     # 备份 WAL 日志归档
#     docker exec ${CONTAINER_NAME} bash -c "mkdir -p /tmp/${INCR_NAME} && cp -f ${WAL_ARCHIVE_DIR}/* /tmp/${INCR_NAME}/ 2>/dev/null || true"
#     
#     # 打包 WAL 日志
#     docker exec ${CONTAINER_NAME} tar -czf /tmp/${INCR_NAME}.tar.gz -C /tmp ${INCR_NAME}
#     
#     # 复制到宿主机
#     docker cp ${CONTAINER_NAME}:/tmp/${INCR_NAME}.tar.gz ${INCR_PATH}.tar.gz
#     
#     if [ $? -ne 0 ]; then
#         echo "[$(date '+%Y-%m-%d %H:%M:%S')] 复制增量备份失败！"
#         return 1
#     fi
#     
#     # 清理容器内临时文件
#     docker exec ${CONTAINER_NAME} rm -rf /tmp/${INCR_NAME} /tmp/${INCR_NAME}.tar.gz
#     
#     # 更新 WAL 位置记录
#     docker exec ${CONTAINER_NAME} psql -U ${DB_USER} -c "SELECT pg_current_wal_lsn();" -t -A > ${BACKUP_DIR}/last_wal_position
#     
#     # 发送到远程备份机
#     echo "[$(date '+%Y-%m-%d %H:%M:%S')] 发送增量备份到远程..."
#     ssh ${REMOTE_USER}@${REMOTE_HOST} "mkdir -p ${REMOTE_DIR}/incremental" 2>/dev/null
#     scp ${INCR_PATH}.tar.gz ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/incremental/
#     
#     if [ $? -ne 0 ]; then
#         echo "[$(date '+%Y-%m-%d %H:%M:%S')] 发送增量备份失败！"
#         return 1
#     fi
#     
#     echo "[$(date '+%Y-%m-%d %H:%M:%S')] 增量备份完成！"
#     echo "备份文件：${INCR_PATH}.tar.gz"
#     return 0
# }

# 发送企业微信群聊通知
send_wechat_notification() {
    local status=$1
    local backup_file=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local hostname=$(hostname)

    local content
    if [ "$status" = "success" ]; then
        content="**PostgreSQL 备份通知**\n 服务器：${hostname}\n 时间：${timestamp}\n 状态：成功\n 备份文件：${backup_file}"
    else
        content="**PostgreSQL 备份通知**\n 服务器：${hostname}\n 时间：${timestamp}\n 状态：失败，请及时检查！"
    fi

    curl -s -X POST "${WECHAT_WEBHOOK}" \
        -H 'Content-Type: application/json' \
        -d "{\"msgtype\":\"markdown\",\"markdown\":{\"content\":\"${content}\"}}" > /dev/null 2>&1
}

# 主程序
echo "[$TIMESTAMP] 开始执行 PostgreSQL 备份..."

# 检查 WAL 配置
# check_wal_config
# if [ $? -ne 0 ]; then
#     echo "[$(date '+%Y-%m-%d %H:%M:%S')] 建议先运行配置脚本启用 WAL 归档"
# fi

# 执行全量备份（暂不使用增量备份）
perform_full_backup

# 原增量备份逻辑（已禁用）：
# if [ ${DAY_OF_WEEK} -eq 7 ]; then
#     perform_full_backup
# else
#     perform_incremental_backup
# fi

BACKUP_RESULT=$?

# 清理过期备份
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 清理 ${RETENTION_DAYS} 天前的旧备份..."
find ${FULL_BACKUP_DIR} -name "*.tar.gz" -mtime +${RETENTION_DAYS} -delete
# 增量备份目录清理（暂不使用）
# find ${INCR_BACKUP_DIR} -name "*.tar.gz" -mtime +${RETENTION_DAYS} -delete

if [ ${BACKUP_RESULT} -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 备份任务全部完成！"
    send_wechat_notification "success" "${FULL_BACKUP_PATH}.sql.gz"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 备份任务失败！"
    send_wechat_notification "failed" ""
    exit 1
fi

exit 0