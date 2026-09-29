#!/bin/bash

# SSH 免密登录配置脚本
# 用于配置备份服务器与远程备份机之间的免密登录

REMOTE_HOST="192.168.13.254"
REMOTE_USER="root"

echo "开始配置 SSH 免密登录..."

# 检查是否已有 SSH 密钥
if [ ! -f ~/.ssh/id_rsa ]; then
    echo "1. 生成 SSH 密钥对..."
    ssh-keygen -t rsa -b 4096 -N "" -f ~/.ssh/id_rsa
    echo "   密钥已生成: ~/.ssh/id_rsa"
else
    echo "1. SSH 密钥已存在，跳过生成"
fi

# 将公钥复制到远程服务器
echo "2. 将公钥复制到远程服务器 ${REMOTE_USER}@${REMOTE_HOST}..."
ssh-copy-id ${REMOTE_USER}@${REMOTE_HOST}

# 验证免密登录是否成功
echo "3. 验证免密登录..."
ssh ${REMOTE_USER}@${REMOTE_HOST} "echo '免密登录测试成功！'"

if [ $? -eq 0 ]; then
    echo ""
    echo "SSH 免密登录配置完成！"
    echo "现在可以运行 outline-pgsql-bak.sh 进行自动备份了。"
else
    echo ""
    echo "SSH 免密登录配置失败，请检查网络连接和远程服务器设置。"
    exit 1
fi