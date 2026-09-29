# Outline 环境备份脚本说明

本目录包含 Outline 服务的两个核心备份脚本，通过 crontab 定时任务实现自动化备份。

---

## 目录结构

```
shell-script/
├── outline-minio-bak.sh    # MinIO 对象存储备份（rclone 同步）
├── outline-pgsql-bak.sh    # PostgreSQL 数据库备份（pg_dumpall 全量）
└── README.md               # 本文档
```

---

## 一、outline-minio-bak.sh — MinIO 备份

### 1.1 功能

将 Outline 使用的 MinIO 存储桶内容，通过 `rclone sync` 同步到备份 MinIO 实例。

| 项目 | 值 |
|------|-----|
| 源 | `minio:outline` |
| 目标 | `minio-backup:outline-bak` |
| 策略 | 增量同步（按 checksum 比对，只传输变化文件） |
| 日志 | `/var/log/rclone-minio-backup.log` |

### 1.2 前置依赖

```bash
# 安装 rclone
curl https://rclone.org/install.sh | sudo bash

# 配置两个 MinIO remote（交互式，填写 endpoint / accessKey / secretKey）
rclone config create minio s3 \
    provider=Minio \
    endpoint=http://<minio-ip>:9000 \
    access_key_id=<your-key> \
    secret_access_key=<your-secret>

rclone config create minio-backup s3 \
    provider=Minio \
    endpoint=http://<backup-minio-ip>:9000 \
    access_key_id=<your-key> \
    secret_access_key=<your-secret>

# 验证配置
rclone lsd minio:
rclone lsd minio-backup:
```

### 1.3 配置项

在脚本中修改以下变量：

```bash
SOURCE_REMOTE="minio"              # rclone 源 remote 名称
SOURCE_BUCKET="outline"            # 源 Bucket
DEST_REMOTE="minio-backup"         # rclone 目标 remote 名称
DEST_BUCKET="outline-bak"          # 目标 Bucket
WECHAT_WEBHOOK="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=实际KEY"
```

---

## 二、outline-pgsql-bak.sh — PostgreSQL 备份

### 2.1 功能

对运行在 Docker 容器中的 PostgreSQL 执行全量逻辑备份，并同步到远程备份服务器。

| 项目 | 值 |
|------|-----|
| 数据库容器 | `postgres`（Docker） |
| 数据库用户 | `iotcloud` |
| 备份方式 | `pg_dumpall` → gzip 压缩 |
| 本地保留 | `/data/pgbackup/full/` |
| 远程同步 | `192.168.13.254:/opt/remote-outline-postgresql-bak/full/` |
| 保留天数 | 30 天（自动清理） |

> 注：增量备份（WAL 日志）功能已禁用，当前仅执行每日全量备份。

### 2.2 前置依赖

```bash
# sshpass（用于免交互 SSH 传输）
yum install -y sshpass   # CentOS/RHEL
apt install -y sshpass   # Debian/Ubuntu

# 确保 Docker 正常运行，且容器名为 postgres
docker ps | grep postgres
```

### 2.3 配置项

在脚本中修改以下变量：

```bash
CONTAINER_NAME="postgres"                               # Docker 容器名
DB_USER="iotcloud"                                      # 数据库用户
BACKUP_DIR="/data/pgbackup"                             # 本地备份根目录
REMOTE_HOST="192.168.13.254"                            # 远程备份服务器 IP
REMOTE_USER="root"                                      # 远程用户
REMOTE_PASSWORD="<实际密码>"                              # 远程密码
REMOTE_DIR="/opt/remote-outline-postgresql-bak"          # 远程备份路径
RETENTION_DAYS=30                                       # 保留天数
WECHAT_WEBHOOK="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=实际KEY"
```

---

## 三、定时任务配置

### 3.1 编辑 crontab

```bash
crontab -e
```

### 3.2 推荐调度

```cron
# MinIO 备份 — 每日凌晨 2:00
0 2 * * * /bin/bash /opt/scripts/outline-minio-bak.sh >> /var/log/outline-minio-bak-cron.log 2>&1

# PostgreSQL 备份 — 每日凌晨 3:00（MinIO 之后，避开高峰）
0 3 * * * /bin/bash /opt/scripts/outline-pgsql-bak.sh >> /var/log/outline-pgsql-bak-cron.log 2>&1
```

### 3.3 验证

```bash
# 查看定时任务列表
crontab -l

# 查看 cron 日志
tail -f /var/log/cron
```

---

## 四、企业微信通知

两个脚本都支持备份完成后发送企业微信机器人通知。

1. 在企业微信群中添加群机器人，获取 Webhook 地址
2. 替换脚本中 `WECHAT_WEBHOOK` 变量的值为实际地址
3. 不配置或填错则通知静默失败，不影响备份流程

通知示例（成功）：
> **PostgreSQL 备份通知**
> 状态：成功
> 服务器：outline-server
> 时间：2026-05-21 03:00:01
> 备份文件：/data/pgbackup/full/full_backup_20260521.sql.gz

---

## 五、日志

| 脚本 | 日志路径 | 说明 |
|------|---------|------|
| MinIO 备份 | `/var/log/rclone-minio-backup.log` | rclone 详细日志（每次覆盖） |
| MinIO cron | `/var/log/outline-minio-bak-cron.log` | cron 触发日志（追加） |
| PgSQL 备份 | 脚本输出由 cron 管理 | 见 cron 配置 |
| PgSQL cron | `/var/log/outline-pgsql-bak-cron.log` | cron 触发日志（追加） |

---

## 六、故障排查

### 6.1 MinIO 备份

| 问题 | 检查步骤 |
|------|---------|
| rclone 找不到 | `which rclone`，确认已安装并在 PATH 中 |
| remote 不通 | `rclone lsd minio:` 看能否列出 Bucket |
| 权限不足 | 检查 MinIO 的 access key 是否有读写权限 |
| 同步失败 | 查看 `/var/log/rclone-minio-backup.log` |

### 6.2 PostgreSQL 备份

| 问题 | 检查步骤 |
|------|---------|
| 容器未运行 | `docker ps \| grep postgres` |
| pg_dumpall 失败 | `docker exec postgres pg_dumpall -U iotcloud --help` 验证连接 |
| 远程传输失败 | 手动执行 `sshpass -p '密码' ssh root@192.168.13.254` 测试连通性 |
| 磁盘空间不足 | `df -h /data` 检查备份目录空间 |
| sshpass 未安装 | `which sshpass`，按 2.2 节安装 |

### 6.3 手动测试

```bash
# 手动执行备份（不依赖定时任务）
bash /opt/scripts/outline-minio-bak.sh
bash /opt/scripts/outline-pgsql-bak.sh
```

---

## 七、备份恢复

### 7.1 MinIO 恢复

```bash
# 将备份 Bucket 反向同步回源 Bucket
rclone sync minio-backup:outline-bak minio:outline --dry-run   # 先预览
rclone sync minio-backup:outline-bak minio:outline              # 执行恢复
```

### 7.2 PostgreSQL 恢复

```bash
# 方法 1：从远程备份机恢复（不经过本地）
sshpass -p '密码' ssh root@192.168.13.254 \
    "gunzip -c /opt/remote-outline-postgresql-bak/full/full_backup_20260521.sql.gz" | \
    docker exec -i postgres psql -U iotcloud -d postgres

# 方法 2：先拉取到本地再恢复
gunzip -c /data/pgbackup/full/full_backup_20260521.sql.gz | \
    docker exec -i postgres psql -U iotcloud -d postgres
```

> ⚠️ 恢复前请确认目标数据库可接受全量覆盖数据。
