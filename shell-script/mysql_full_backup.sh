#!/bin/bash
set -euo pipefail

# ==================== 配置区域 ====================
MYSQL_USER="backup_admin"
MYSQL_PASSWORD="SecureBackupPass2026!"
MYSQL_HOST="localhost"
MYSQL_SOCKET="/data/mysql/mysql.sock"
BACKUP_ROOT="/data/backup/mysql"
RETENTION_DAYS=30
GZIP_LEVEL=6
#ENCRYPT_KEY_FILE="/etc/backup/aes_keyfile"
REMOTE_BACKUP_HOST="192.168.13.254"
REMOTE_BACKUP_USER=""
REMOTE_BACKUP_PATH="/opt/remote-mysql-idc-bak"
ENABLE_REMOTE_SYNC=false
ENABLE_ENCRYPT=false

# 企业微信群聊机器人 Webhook 地址
WECHAT_WEBHOOK="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_WEBHOOK_KEY"
# ==================== 配置结束 ====================

# 发送企业微信群聊通知
send_wechat_notification() {
    local status=$1
    local detail=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local hostname=$(hostname)

    local content
    if [ "$status" = "success" ]; then
        content="**MySQL 备份通知**\n> 状态：<font color=\"info\">成功</font>\n> 服务器：${hostname}\n> 时间：${timestamp}\n> 详情：${detail}"
    else
        content="**MySQL 备份通知**\n> 状态：<font color=\"warning\">失败</font>\n> 服务器：${hostname}\n> 时间：${timestamp}\n> 错误：${detail}\n> 请及时检查！"
    fi

    curl -s -X POST "${WECHAT_WEBHOOK}" \
        -H 'Content-Type: application/json' \
        -d "{\"msgtype\":\"markdown\",\"markdown\":{\"content\":\"${content}\"}}" > /dev/null 2>&1
}

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 错误处理函数
error_exit() {
    log "ERROR: $1"
    send_wechat_notification "failed" "$1"
    exit 1
}

# 检查 MySQL 连接
check_mysql() {
    log "检查 MySQL 连接..."
    if ! mysql -u "${MYSQL_USER}" -p"${MYSQL_PASSWORD}" -h "${MYSQL_HOST}" -e "SELECT 1" >/dev/null 2>&1; then
        error_exit "MySQL 连接失败"
    fi
    log "MySQL 连接正常"
}

# 获取备份数据库列表
get_databases() {
    mysql -u "${MYSQL_USER}" -p"${MYSQL_PASSWORD}" -h "${MYSQL_HOST}" -N -e "SHOW DATABASES" 2>/dev/null | 
        grep -vE '(information_schema|performance_schema|mysql|sys|test)'
}

# 备份单个数据库
backup_database() {
    local db_name=$1
    local backup_file="${BACKUP_ROOT}/${BACKUP_DATE}/${db_name}.sql"

    log "备份数据库: ${db_name}"

    # 使用 --single-transaction 保证 InnoDB 一致性
    # 使用 --master-data=2 记录 binlog 位置
    mysqldump \
        --user="${MYSQL_USER}" \
        --password="${MYSQL_PASSWORD}" \
        --host="${MYSQL_HOST}" \
        --socket="${MYSQL_SOCKET}" \
        --single-transaction \
        --routines \
        --triggers \
        --events \
        --master-data=2 \
        --flush-logs \
        --lock-tables=false \
        --databases "${db_name}" 2>/dev/null | \
        gzip -${GZIP_LEVEL} > "${backup_file}.gz"

    if [ $? -eq 0 ] && [ -s "${backup_file}.gz" ]; then
        log "数据库 ${db_name} 备份成功: $(du -h ${backup_file}.gz | cut -f1)"
    else
        error_exit "数据库 ${db_name} 备份失败"
    fi
}

# 备份所有表结构（不含数据）
backup_schema() {
    local db_name=$1
    local schema_file="${BACKUP_ROOT}/${BACKUP_DATE}/${db_name}_schema.sql"

    mysqldump \
        --user="${MYSQL_USER}" \
        --password="${MYSQL_PASSWORD}" \
        --host="${MYSQL_HOST}" \
        --socket="${MYSQL_SOCKET}" \
        --no-data \
        --routines \
        --triggers \
        --events \
        --databases "${db_name}" 2>/dev/null | \
        gzip -${GZIP_LEVEL} > "${schema_file}.gz"

    log "数据库 ${db_name} 表结构备份完成"
}

# 生成备份元信息
generate_metadata() {
    local metadata_file="${BACKUP_ROOT}/${BACKUP_DATE}/metadata.txt"

    {
        echo"Backup Date: ${BACKUP_DATE}"
        echo"Backup Time: $(date '+%Y-%m-%d %H:%M:%S')"
        echo"MySQL Version: $(mysql -u "${MYSQL_USER}" -p"${MYSQL_PASSWORD}" -h "${MYSQL_HOST}" -N -e "SELECT VERSION();" 2>/dev/null)"
        echo "Binlog Position: $(mysql -u "${MYSQL_USER}" -p"${MYSQL_PASSWORD}" -h "${MYSQL_HOST}" -N -e "SHOW MASTER STATUS;" 2>/dev/null | head -1)"
        echo "Databases: $(get_databases | tr '\n'', ')"
    } > "${metadata_file}"

    log "元信息文件已生成"
}


# 清理过期备份
cleanup_old_backups() {
    log "清理 ${RETENTION_DAYS} 天前的备份..."
    find "${BACKUP_ROOT}" -type d -name "????-??-??" -mtime +${RETENTION_DAYS} -exec rm -rf {} \; 2>/dev/null
    log "过期备份清理完成"
}

# 同步到远程服务器
sync_to_remote() {
    if [ "$ENABLE_REMOTE_SYNC" = true ]; then
        log "同步备份到远程服务器..."
        rsync -avz --progress \
            -e "ssh -o StrictHostKeyChecking=no" \
            "${BACKUP_ROOT}/${BACKUP_DATE}" \
            "${REMOTE_BACKUP_HOST}:${REMOTE_BACKUP_PATH}/"
        log "远程同步完成"
    fi
}

# 验证备份完整性
verify_backup() {
    log "验证备份完整性..."
    local failed=0
    for f in "${BACKUP_ROOT}/${BACKUP_DATE}"/*.gz; do
        if ! gzip -t "$f" 2>/dev/null; then
            log "备份文件损坏: $(basename $f)"
            ((failed++))
        fi
    done

    if [ $failed -eq 0 ]; then
        log "备份完整性验证通过"
    else
        error_exit "${failed} 个备份文件验证失败"
    fi
}

# ==================== 主流程 ====================
main() {
    BACKUP_DATE=$(date '+%Y-%m-%d')

    log "========== MySQL 全量备份开始 =========="

    # 预检查
    check_mysql || error_exit "预检查失败"

    # 创建备份目录
    mkdir -p "${BACKUP_ROOT}/${BACKUP_DATE}"

    # 备份每个数据库
    for db in $(get_databases); do
        backup_database "$db"
        backup_schema "$db"
    done

    # 备份 MySQL 系统表
    log "备份 MySQL 系统表..."
    mysqldump \
        --user="${MYSQL_USER}" \
        --password="${MYSQL_PASSWORD}" \
        --host="${MYSQL_HOST}" \
        --socket="${MYSQL_SOCKET}" \
        --single-transaction \
        mysql > "${BACKUP_ROOT}/${BACKUP_DATE}/mysql_system.sql" 2>/dev/null
    gzip "${BACKUP_ROOT}/${BACKUP_DATE}/mysql_system.sql"

    # 生成元信息
    generate_metadata


    # 验证
    verify_backup

    # 清理过期备份
    cleanup_old_backups

    # 远程同步
    sync_to_remote

    log "========== MySQL 全量备份完成 =========="
    log "备份位置: ${BACKUP_ROOT}/${BACKUP_DATE}"
    log "备份大小: $(du -sh ${BACKUP_ROOT}/${BACKUP_DATE} | cut -f1)"

    # 发送成功通知
    send_wechat_notification "success" "备份位置: ${BACKUP_ROOT}/${BACKUP_DATE}, 大小: $(du -sh ${BACKUP_ROOT}/${BACKUP_DATE} | cut -f1)"
}

main "$@"
