# 开发环境完整启动
ansible-playbook -i hosts kafka.yaml -l dev_kafka

# 测试环境完整启动
ansible-playbook -i hosts kafka.yaml -l test_kafka

# 只启动 Zookeeper
ansible-playbook -i hosts kafka.yaml -l dev_kafka --tags zookeeper

# 只启动 Kafka（假设 ZK 已运行）
ansible-playbook -i hosts kafka.yaml -l dev_kafka --tags kafka

# 检查模式（不实际执行）
ansible-playbook -i hosts kafka.yaml -l dev_kafka --check

#   ansible-playbook -i hosts mongodb.yaml -l dev_mongo
#   ansible-playbook -i hosts mongodb.yaml -l test_mongo