#!/bin/bash

# PostgreSQL 备份恢复脚本
# 支持从本地或远程服务器恢复备份

# 配置参数
CONTAINER_NAME="postgres"
DB_USER="iotcloud"
BACKUP_DIR="/data/pgbackup"
REMOTE_HOST="192.168.13.254"
REMOTE_USER="root"
REMOTE_PASSWORD="1"  # 如果使用 sshpass，填写密码；否则留空使用密钥认证
REMOTE_DIR="/opt/remote-outline-postgresql-bak"

# SSH 命令封装
if [ -n "${REMOTE_PASSWORD}" ]; then
    SSH_CMD="sshpass -p ${REMOTE_PASSWORD} ssh -o StrictHostKeyChecking=no"
    SCP_CMD="sshpass -p ${REMOTE_PASSWORD} scp -o StrictHostKeyChecking=no"
else
    SSH_CMD="ssh -o StrictHostKeyChecking=no"
    SCP_CMD="scp -o StrictHostKeyChecking=no"
fi

# 显示帮助信息
show_help() {
    echo "PostgreSQL 备份恢复脚本"
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -d, --date DATE      指定恢复的备份日期 (格式: YYYYMMDD)"
    echo "  -l, --local          从本地恢复（默认）"
    echo "  -r, --remote         从远程服务器恢复"
    echo "  -f, --file FILE      指定备份文件路径"
    echo "  -h, --help           显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 -d 20260430                    # 从本地恢复指定日期的备份"
    echo "  $0 -d 20260430 -r                 # 从远程恢复指定日期的备份"
    echo "  $0 -f /data/pgbackup/full/full_backup_20260430.sql.gz  # 恢复指定文件"
}

# 解析参数
RESTORE_DATE=""
SOURCE="local"
BACKUP_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--date)
            RESTORE_DATE="$2"
            shift 2
            ;;
        -l|--local)
            SOURCE="local"
            shift
            ;;
        -r|--remote)
            SOURCE="remote"
            shift
            ;;
        -f|--file)
            BACKUP_FILE="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
done

# 验证参数
if [ -z "${BACKUP_FILE}" ] && [ -z "${RESTORE_DATE}" ]; then
    echo "错误: 必须指定备份日期 (-d) 或备份文件 (-f)"
    show_help
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始执行 PostgreSQL 恢复..."

# 如果指定了日期，构建备份文件路径
if [ -n "${RESTORE_DATE}" ] && [ -z "${BACKUP_FILE}" ]; then
    BACKUP_FILE="${BACKUP_DIR}/full/full_backup_${RESTORE_DATE}.sql.gz"
fi

# 如果从远程恢复，先下载备份文件
if [ "${SOURCE}" = "remote" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 从远程服务器下载备份文件..."
    
    # 如果指定了日期，从远程下载
    if [ -n "${RESTORE_DATE}" ]; then
        REMOTE_FILE="${REMOTE_DIR}/full/full_backup_${RESTORE_DATE}.sql.gz"
        ${SCP_CMD} ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_FILE} ${BACKUP_DIR}/full/
        BACKUP_FILE="${BACKUP_DIR}/full/full_backup_${RESTORE_DATE}.sql.gz"
    else
        # 如果指定了文件，下载到临时位置
        ${SCP_CMD} ${REMOTE_USER}@${REMOTE_HOST}:${BACKUP_FILE} /tmp/
        BACKUP_FILE="/tmp/$(basename ${BACKUP_FILE})"
    fi
    
    if [ $? -ne 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 下载备份文件失败！"
        exit 1
    fi
fi

# 检查备份文件是否存在
if [ ! -f "${BACKUP_FILE}" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 错误: 备份文件不存在 - ${BACKUP_FILE}"
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 备份文件: ${BACKUP_FILE}"

# 解压备份文件
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 解压备份文件..."
TEMP_SQL_FILE="/tmp/restore_$(date +%Y%m%d%H%M%S).sql"
gunzip -c "${BACKUP_FILE}" > "${TEMP_SQL_FILE}"

if [ $? -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 解压备份文件失败！"
    exit 1
fi

# 将 SQL 文件复制到容器内
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 复制备份文件到容器..."
docker cp "${TEMP_SQL_FILE}" ${CONTAINER_NAME}:/tmp/restore.sql

# 执行恢复
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始恢复数据库..."
docker exec ${CONTAINER_NAME} psql -U ${DB_USER} -f /tmp/restore.sql

if [ $? -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 数据库恢复失败！"
    # 清理临时文件
    docker exec ${CONTAINER_NAME} rm -f /tmp/restore.sql
    rm -f "${TEMP_SQL_FILE}"
    exit 1
fi

# 清理临时文件
docker exec ${CONTAINER_NAME} rm -f /tmp/restore.sql
rm -f "${TEMP_SQL_FILE}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 数据库恢复完成！"
echo "恢复来源: ${SOURCE}"
echo "备份文件: ${BACKUP_FILE}"

exit 0