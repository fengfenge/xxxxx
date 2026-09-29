#!/bin/bash

# PostgreSQL WAL 归档配置脚本
# 用于配置 PostgreSQL 以支持增量备份

CONTAINER_NAME="postgres"
DB_USER="iotcloud"

echo "开始配置 PostgreSQL WAL 归档..."

# 1. 进入容器查看当前配置
echo "1. 查看当前 WAL 配置..."
docker exec ${CONTAINER_NAME} psql -U ${DB_USER} -c "SHOW wal_level;"
docker exec ${CONTAINER_NAME} psql -U ${DB_USER} -c "SHOW archive_mode;"
docker exec ${CONTAINER_NAME} psql -U ${DB_USER} -c "SHOW archive_command;"

# 2. 停止容器
echo "2. 停止 PostgreSQL 容器..."
docker stop ${CONTAINER_NAME}

# 3. 修改 postgresql.conf 配置
echo "3. 修改 postgresql.conf 配置..."
docker exec ${CONTAINER_NAME} bash -c "cat > /var/lib/postgresql/data/postgresql.conf << 'EOF'
# WAL 配置
wal_level = replica
archive_mode = on
archive_command = 'cp %p /var/lib/postgresql/data/pg_wal/archive/%f'
EOF"

# 4. 创建归档目录
echo "4. 创建 WAL 归档目录..."
docker exec ${CONTAINER_NAME} mkdir -p /var/lib/postgresql/data/pg_wal/archive

# 5. 启动容器
echo "5. 启动 PostgreSQL 容器..."
docker start ${CONTAINER_NAME}

# 等待容器启动
sleep 10

# 6. 验证配置
echo "6. 验证 WAL 配置..."
docker exec ${CONTAINER_NAME} psql -U ${DB_USER} -c "SHOW wal_level;"
docker exec ${CONTAINER_NAME} psql -U ${DB_USER} -c "SHOW archive_mode;"
docker exec ${CONTAINER_NAME} psql -U ${DB_USER} -c "SHOW archive_command;"

echo ""
echo "WAL 归档配置完成！"
echo "现在可以运行 outline-pgsql-bak.sh 进行增量备份了。"