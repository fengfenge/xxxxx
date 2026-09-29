#!/usr/bin/env python3
# mq_inspection.py
# 消息队列巡检：Kafka（kafka_exporter）+ RabbitMQ（与 Grafana RabbitMQ-Overview 一致的 Prometheus 查询）

import os
from datetime import datetime

import pdfkit
import requests
from jinja2 import Template

# 阿里云OSS SDK
try:
    import oss2
    OSS_AVAILABLE = True
except ImportError:
    print("⚠️ 未安装阿里云OSS SDK，请执行: pip install oss2")
    OSS_AVAILABLE = False

# ==================== 配置 ====================
PROMETHEUS_URL = "http://192.168.13.93:31909/"

OUTPUT_DIR = "e:/pythonProject/inspection_report"

# 企业微信配置
WECHAT_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=87708747-919b-460c-b357-003edb891ea7"  # 请替换为你的企业微信机器人Webhook URL

# 阿里云OSS配置
OSS_ACCESS_KEY_ID = os.environ.get("ALIYUN_ACCESS_KEY_ID", "")           # 阿里云AccessKey ID
OSS_ACCESS_KEY_SECRET = os.environ.get("ALIYUN_ACCESS_KEY_SECRET", "")   # 阿里云AccessKey Secret
OSS_ENDPOINT = "oss-cn-shenzhen.aliyuncs.com"       # OSS地域Endpoint
OSS_BUCKET_NAME = "ops-inspection-report"               # OSS Bucket名称
OSS_FILE_PREFIX = "mq-inspection"                 # 文件存储前缀（可选）

# Kafka（对应 Grafana 变量 $job / $name）
KAFKA_JOB = "iot-kafka"
KAFKA_NAME = "kafka-dev"

# RabbitMQ（与 RabbitMQ-Overview-base.json 中 templating 变量一致）
RABBITMQ_NAMESPACE = ""
RABBITMQ_CLUSTER = "rabbit@rabbitmq-test"
RABBITMQ_ENDPOINT = ""

# PromQL 中与 Grafana 对齐：irate/rate 窗口
RABBITMQ_RATE_INTERVAL = "5m"
RABBITMQ_SHORT_RATE = "60s"
# 用于消息体大小等 $__range 类查询
RABBITMQ_RANGE = "1h"

ENABLE_KAFKA = True
ENABLE_RABBITMQ = True

# ==================== 巡检告警规则 ====================
KAFKA_INSPECTION_RULES = {
    # ISR不足分区
    "kafka_isr_insufficient": {
        "name": "ISR不足分区",
        "query": '''
            kafka_topic_partition_replicas - kafka_topic_partition_in_sync_replica
        ''',
        "threshold_warning": 1,
        "threshold_critical": 1,
        "unit": "个",
        "labels": ["topic", "partition"]
    },
    # 消费组延迟
    "kafka_consumer_group_lag": {
        "name": "消费组延迟",
        "query": '''
            sum by (group) (kafka_consumergroup_lag)
        ''',
        "threshold_warning": 1000,
        "threshold_critical": 10000,
        "unit": "条",
        "labels": ["group"]
    },
    # 生产速率异常（过低）
    "kafka_produce_rate": {
        "name": "生产速率",
        "query": '''
            sum(irate(kafka_topic_partition_messages_in_total[5m])) by (topic)
        ''',
        "threshold_warning": 0,
        "threshold_critical": 0,
        "unit": "/s",
        "labels": ["topic"],
        "check_type": "min",
        "min_threshold": 10
    }
}

RABBITMQ_INSPECTION_RULES = {
    # 内存使用
    "rabbitmq_resident_memory_ratio": {
        "name": "内存使用率(Resident)",
        "query": '''
            rabbitmq_process_resident_memory_bytes / rabbitmq_resident_memory_limit_bytes * 100
        ''',
        "threshold_warning": 70,
        "threshold_critical": 85,
        "unit": "%",
        "labels": ["rabbitmq_node"]
    },
    # Erlang进程数
    "rabbitmq_erlang_process_ratio": {
        "name": "Erlang进程使用率",
        "query": '''
            rabbitmq_erlang_processes_used / rabbitmq_erlang_processes_limit * 100
        ''',
        "threshold_warning": 70,
        "threshold_critical": 85,
        "unit": "%",
        "labels": ["rabbitmq_node"]
    },
    # 调度器运行队列
    "rabbitmq_scheduler_run_queue": {
        "name": "调度器运行队列",
        "query": '''
            rabbitmq_erlang_scheduler_run_queue
        ''',
        "threshold_warning": 5,
        "threshold_critical": 20,
        "unit": "",
        "labels": ["rabbitmq_node"]
    },
    # 队列消息积压
    "rabbitmq_queue_backlog": {
        "name": "队列消息积压",
        "query": '''
            rabbitmq_queue_messages_ready + rabbitmq_queue_messages_unacked
        ''',
        "threshold_warning": 1000,
        "threshold_critical": 2000,
        "unit": "条",
        "labels": ["vhost", "queue"]
    },
    # 认证失败（24小时增量）
    "rabbitmq_auth_failed": {
        "name": "认证失败数(24h)",
        "query": '''
            increase(rabbitmq_auth_attempts_failed_total[24h])
        ''',
        "threshold_warning": 10,
        "threshold_critical": 100,
        "unit": "次",
        "labels": ["protocol", "instance"]
    },
    # Unroutable Messages (24h increase)
    "rabbitmq_unroutable_messages": {
        "name": "Unroutable Messages (24h)",
        "query": '''
            increase(rabbitmq_global_messages_unroutable_dropped_total[24h]) + increase(rabbitmq_global_messages_unroutable_returned_total[24h])
        ''',
        "threshold_warning": 1,
        "threshold_critical": 10,
        "unit": "messages",
        "labels": ["protocol"]
    }
}


# ==================== Prometheus 客户端 ====================
class PrometheusClient:
    def __init__(self, url):
        self.url = url.rstrip("/")

    def query(self, query, time=None):
        params = {"query": query}
        if time:
            params["time"] = time
        try:
            resp = requests.get(f"{self.url}/api/v1/query", params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()["data"]["result"]
        except Exception as e:
            print(f"查询失败: {e}")
            return []


# ==================== 规则检查器 ====================
class RuleInspector:
    def __init__(self, prometheus_url, rules, filters=None):
        self.prom = PrometheusClient(prometheus_url)
        self.rules = rules
        self.filters = filters or {}
        self.results = {}
        self.alerts = []
        self.summary = {"total_checks": 0, "normal": 0, "warning": 0, "critical": 0}

    def _apply_filters(self, query):
        for key, value in self.filters.items():
            query = query.replace(f"{{{{{key}}}}}", value)
        return query

    def check_rule(self, rule_id, rule):
        print(f"🔍 检查规则: {rule['name']}...")
        query = self._apply_filters(rule['query'].strip())
        data = self.prom.query(query)
        
        check_result = {
            'name': rule['name'],
            'unit': rule.get('unit', ''),
            'threshold_warning': rule.get('threshold_warning'),
            'threshold_critical': rule.get('threshold_critical'),
            'items': [],
            'status': 'normal'
        }

        for item in data:
            labels = item["metric"]
            value = float(item["value"][1])
            status = 'normal'
            
            check_type = rule.get('check_type', 'max')
            min_threshold = rule.get('min_threshold')
            
            if check_type == 'min':
                if min_threshold and value < min_threshold:
                    if value < min_threshold * 0.5:
                        status = 'critical'
                    else:
                        status = 'warning'
            else:
                if 'threshold_critical' in rule and value > rule['threshold_critical']:
                    status = 'critical'
                elif 'threshold_warning' in rule and value > rule['threshold_warning']:
                    status = 'warning'

            label_values = {}
            for label in rule.get('labels', []):
                label_values[label] = labels.get(label, '')

            check_result['items'].append({
                'labels': label_values,
                'value': value,
                'status': status
            })

            self.summary['total_checks'] += 1
            if status == 'critical':
                self.summary['critical'] += 1
                check_result['status'] = 'critical'
                self.alerts.append({
                    'check_name': rule['name'],
                    'node': ', '.join([f"{k}={v}" for k, v in label_values.items()]),
                    'instance': '',
                    'value': f"{value:.2f}{rule.get('unit', '')}",
                    'status': 'critical',
                    'threshold': f">{rule['threshold_critical']}{rule.get('unit', '')}"
                })
            elif status == 'warning':
                self.summary['warning'] += 1
                if check_result['status'] == 'normal':
                    check_result['status'] = 'warning'
                self.alerts.append({
                    'check_name': rule['name'],
                    'node': ', '.join([f"{k}={v}" for k, v in label_values.items()]),
                    'instance': '',
                    'value': f"{value:.2f}{rule.get('unit', '')}",
                    'status': 'warning',
                    'threshold': f">{rule['threshold_warning']}{rule.get('unit', '')}"
                })
            else:
                self.summary['normal'] += 1

        self.results[rule_id] = check_result

    def run_all_rules(self):
        print("=" * 60)
        print(f"开始规则检查 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)
        for rule_id, rule in self.rules.items():
            self.check_rule(rule_id, rule)
        print(f"规则检查完成: 总计 {self.summary['total_checks']} 项, 正常 {self.summary['normal']}, 警告 {self.summary['warning']}, 严重 {self.summary['critical']}")


# ==================== Kafka 巡检 ====================
class KafkaInspector:
    def __init__(self, prometheus_url, job, name):
        self.prom = PrometheusClient(prometheus_url)
        self.job = job
        self.name = name
        self.results = {}
        self.alerts = []
        self.summary = {"total_checks": 0, "normal": 0, "warning": 0, "critical": 0}

    def _query_instant(self, query, label=None):
        data = self.prom.query(query)
        items = []
        for item in data:
            items.append({"labels": item["metric"], "value": float(item["value"][1])})
        return items

    def _query_single_value(self, query):
        data = self.prom.query(query)
        if data:
            return float(data[0]["value"][1])
        return 0.0

    def run_all_checks(self):
        print("=" * 60)
        print(f"开始 Kafka 巡检 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)

        overview = {}
        overview["brokers"] = self._query_single_value(
            f'kafka_brokers{{job="{self.job}",name="{self.name}"}}'
        )
        overview["topics"] = self._query_single_value(
            f'count(kafka_topic_partitions{{job="{self.job}",name="{self.name}",topic!~"__.*"}})'
        )
        overview["partitions"] = self._query_single_value(
            f'sum(kafka_topic_partitions{{job="{self.job}",name="{self.name}",topic!~"__.*"}})'
        )
        overview["consumer_groups"] = self._query_single_value(
            f'count(kafka_consumergroup_members{{job="{self.job}",name="{self.name}",consumergroup!~"__.*"}})'
        )
        overview["consumers"] = self._query_single_value(
            f'sum(kafka_consumergroup_members{{job="{self.job}",name="{self.name}",consumergroup!~"__.*"}})'
        )
        overview["replicas"] = self._query_single_value(
            f'sum(kafka_topic_partition_replicas{{job="{self.job}",name="{self.name}"}})'
        )
        overview["in_sync_replicas"] = self._query_single_value(
            f'sum(kafka_topic_partition_in_sync_replica{{job="{self.job}",name="{self.name}"}})'
        )
        overview["preferred_not_leader"] = self._query_single_value(
            f'count(kafka_topic_partition_leader_is_preferred{{job="{self.job}",name="{self.name}"}} < 1)'
        )
        overview["total_produce_rate"] = self._query_single_value(
            f'sum(irate(kafka_topic_partition_current_offset{{job="{self.job}",name="{self.name}",topic!~"__.*"}}[3m]))'
        )
        overview["total_consume_rate"] = self._query_single_value(
            f'sum(irate(kafka_consumergroup_current_offset{{job="{self.job}",name=~"{self.name}"}}[3m]))'
        )
        overview["total_lag"] = self._query_single_value(
            f'sum(kafka_consumergroup_lag_sum{{job="{self.job}",name="{self.name}"}})'
        )
        self.results["overview"] = overview

        print("检查: 消费组列表...")
        consumer_groups = {}
        members_data = self._query_instant(
            f'kafka_consumergroup_members{{job="{self.job}",name="{self.name}",consumergroup!~"__.*"}}'
        )
        for item in members_data:
            cg = item["labels"].get("consumergroup")
            if cg:
                consumer_groups[cg] = {"members": item["value"], "topics": set()}
        lag_data = self._query_instant(
            f'kafka_consumergroup_lag_sum{{job="{self.job}",name="{self.name}",consumergroup!~"__.*",topic!~"__.*"}}'
        )
        for item in lag_data:
            cg = item["labels"].get("consumergroup")
            topic = item["labels"].get("topic")
            if cg and topic and cg in consumer_groups:
                consumer_groups[cg]["topics"].add(topic)
        for cg in consumer_groups:
            consumer_groups[cg]["topic_count"] = len(consumer_groups[cg]["topics"])
        self.results["consumer_groups"] = consumer_groups

        print("检查: Topic 列表...")
        topics = {}
        topic_partitions = self._query_instant(
            f'sum by(topic) (kafka_topic_partitions{{job="{self.job}",name="{self.name}",topic!~"__.*"}})'
        )
        for item in topic_partitions:
            topic = item["labels"].get("topic")
            if topic:
                topics[topic] = {"partitions": item["value"]}
        self.results["topics"] = topics

        print("检查: 积压 TOP 20...")
        lag_items = self._query_instant(
            f'kafka_consumergroup_lag_sum{{job="{self.job}",name="{self.name}",consumergroup!~"__.*",topic!~"__.*"}}'
        )
        lag_list = []
        for item in lag_items:
            lag_list.append(
                {
                    "consumergroup": item["labels"].get("consumergroup", ""),
                    "topic": item["labels"].get("topic", ""),
                    "lag": item["value"],
                }
            )
        lag_list.sort(key=lambda x: x["lag"], reverse=True)
        self.results["top_lags"] = lag_list[:20]

        print("检查: 无消费组消费的 Topic...")
        all_topics = set(topics.keys())
        consumed_topics = set()
        for item in lag_items:
            t = item["labels"].get("topic")
            if t:
                consumed_topics.add(t)
        orphan_topics = all_topics - consumed_topics
        orphan_topic_list = []
        for t in orphan_topics:
            total_msgs = self._query_single_value(
                f'sum(kafka_topic_partition_current_offset{{job="{self.job}",name="{self.name}",topic="{t}"}} '
                f'- kafka_topic_partition_oldest_offset{{job="{self.job}",name="{self.name}",topic="{t}"}})'
            )
            produce_rate = self._query_single_value(
                f'sum(irate(kafka_topic_partition_current_offset{{job="{self.job}",name="{self.name}",topic="{t}"}}[3m]))'
            )
            orphan_topic_list.append(
                {
                    "topic": t,
                    "partitions": topics[t]["partitions"],
                    "total_messages": total_msgs,
                    "produce_rate": produce_rate,
                }
            )
        self.results["orphan_topics"] = orphan_topic_list

        print("检查: 无关联 Topic 的消费组...")
        all_cg = set(consumer_groups.keys())
        cg_with_topic = set()
        for item in lag_items:
            cg = item["labels"].get("consumergroup")
            if cg:
                cg_with_topic.add(cg)
        orphan_cg = all_cg - cg_with_topic
        orphan_cg_list = []
        for cg in orphan_cg:
            orphan_cg_list.append({"consumergroup": cg, "members": consumer_groups[cg]["members"]})
        self.results["orphan_consumer_groups"] = orphan_cg_list

        print("检查: 分区积压 TOP 20...")
        partition_lag = self._query_instant(
            f'sum(kafka_consumergroup_lag{{job="{self.job}",name="{self.name}",consumergroup!~"__.*",topic!~"__.*"}}) '
            f"by (consumergroup, topic, partition)"
        )
        partition_lag_list = []
        for item in partition_lag:
            partition_lag_list.append(
                {
                    "consumergroup": item["labels"].get("consumergroup", ""),
                    "topic": item["labels"].get("topic", ""),
                    "partition": item["labels"].get("partition", ""),
                    "lag": item["value"],
                }
            )
        partition_lag_list.sort(key=lambda x: x["lag"], reverse=True)
        self.results["top_partition_lags"] = partition_lag_list[:20]

        print("检查: Topic生产速率 TOP 20...")
        topic_produce_rate = self._query_instant(
            f'sum by(topic) (irate(kafka_topic_partition_current_offset{{job="{self.job}",name="{self.name}",topic !~ "__.*"}}[3m]))'
        )
        topic_produce_list = []
        for item in topic_produce_rate:
            topic_produce_list.append(
                {
                    "topic": item["labels"].get("topic", ""),
                    "produce_rate": item["value"],
                }
            )
        topic_produce_list.sort(key=lambda x: x["produce_rate"], reverse=True)
        self.results["top_produce_rates"] = topic_produce_list[:20]

        print("检查: 消费组消费速率 TOP 20...")
        cg_consume_rate = self._query_instant(
            f'sum by(consumergroup, topic) (irate(kafka_consumergroup_current_offset{{job="{self.job}",name=~"{self.name}",consumergroup!~"__.*",topic!~"__.*"}}[3m]))'
        )
        cg_consume_list = []
        for item in cg_consume_rate:
            cg_consume_list.append(
                {
                    "consumergroup": item["labels"].get("consumergroup", ""),
                    "topic": item["labels"].get("topic", ""),
                    "consume_rate": item["value"],
                }
            )
        cg_consume_list.sort(key=lambda x: x["consume_rate"], reverse=True)
        self.results["top_consume_rates"] = cg_consume_list[:20]

        print("检查: Topic消费能力不足检测...")
        topic_produce = self._query_instant(
            f'sum by(topic) (irate(kafka_topic_partition_current_offset{{job="{self.job}",name="{self.name}",topic !~ "__.*"}}[3m]))'
        )
        topic_consume = self._query_instant(
            f'sum by(topic) (irate(kafka_consumergroup_current_offset{{job="{self.job}",name=~"{self.name}",consumergroup!~"__.*",topic!~"__.*"}}[3m]))'
        )
        cg_count_by_topic = self._query_instant(
            f'count by(topic) (kafka_consumergroup_lag_sum{{job="{self.job}",name="{self.name}",consumergroup!~"__.*",topic!~"__.*"}})'
        )
        
        topic_produce_map = {item["labels"].get("topic"): item["value"] for item in topic_produce}
        topic_consume_map = {item["labels"].get("topic"): item["value"] for item in topic_consume}
        cg_count_map = {item["labels"].get("topic"): item["value"] for item in cg_count_by_topic}
        
        topic_gap_list = []
        for topic in topic_produce_map:
            produce = topic_produce_map[topic]
            consume = topic_consume_map.get(topic, 0)
            cg_count = cg_count_map.get(topic, 1)
            gap = consume - produce * cg_count
            topic_gap_list.append(
                {
                    "topic": topic,
                    "produce_rate": produce,
                    "consume_rate": consume,
                    "consumer_groups": cg_count,
                    "gap": gap,
                    "status": "消费不足" if gap < 0 else "正常",
                }
            )
        topic_gap_list.sort(key=lambda x: x["gap"])
        self.results["topic_consume_gap"] = topic_gap_list

        print("检查: ISR不足分区检测...")
        isr_data = self._query_instant(
            f'kafka_topic_partition_replicas{{job="{self.job}",name="{self.name}",topic!~"__.*"}} - kafka_topic_partition_in_sync_replica{{job="{self.job}",name="{self.name}",topic!~"__.*"}}'
        )
        isr_insufficient = []
        for item in isr_data:
            diff = item["value"]
            if diff > 0:
                isr_insufficient.append({
                    "topic": item["labels"].get("topic", ""),
                    "partition": item["labels"].get("partition", ""),
                    "replicas": self._query_single_value(
                        f'kafka_topic_partition_replicas{{job="{self.job}",name="{self.name}",topic="{item["labels"].get("topic", "")}",partition="{item["labels"].get("partition", "")}"}}'
                    ),
                    "in_sync_replicas": self._query_single_value(
                        f'kafka_topic_partition_in_sync_replica{{job="{self.job}",name="{self.name}",topic="{item["labels"].get("topic", "")}",partition="{item["labels"].get("partition", "")}"}}'
                    ),
                    "missing_replicas": diff,
                })
        isr_insufficient.sort(key=lambda x: x["missing_replicas"], reverse=True)
        self.results["isr_insufficient"] = isr_insufficient

        print("检查: Broker节点信息...")
        broker_info = self._query_instant(
            f'kafka_broker_info{{job="{self.job}",name="{self.name}"}}'
        )
        broker_nodes = {}
        for item in broker_info:
            broker_id = item["labels"].get("id", "")
            address = item["labels"].get("address", "")
            broker_nodes[broker_id] = {
                "broker_id": broker_id,
                "address": address,
            }

        broker_list = sorted(broker_nodes.values(), key=lambda x: x["broker_id"])
        self.results["broker_nodes"] = broker_list

        print("检查: Topic消息统计...")
        topic_msg_stats = []
        topic_partition_data = self._query_instant(
            f'sum by(topic) (kafka_topic_partition_current_offset{{job="{self.job}",name="{self.name}",topic!~"__.*"}})'
        )
        for item in topic_partition_data:
            topic = item["labels"].get("topic", "")
            total_offset = item["value"]
            oldest_offset = self._query_single_value(
                f'sum(kafka_topic_partition_oldest_offset{{job="{self.job}",name="{self.name}",topic="{topic}"}})'
            )
            topic_msg_stats.append({
                "topic": topic,
                "total_messages": int(total_offset - oldest_offset),
                "current_offset": int(total_offset),
                "oldest_offset": int(oldest_offset),
            })
        topic_msg_stats.sort(key=lambda x: x["total_messages"], reverse=True)
        self.results["topic_message_stats"] = topic_msg_stats[:20]

        self.summary["total_checks"] = len(self.results)
        self.summary["normal"] = len(self.results)
        print("Kafka 巡检完成")
        print("=" * 60)

        return self.results, self.alerts, self.summary


# ==================== RabbitMQ 巡检 ====================
class RabbitMQInspector:
    """使用与 Grafana 面板相同的 join(rabbitmq_identity_info) 过滤集群/命名空间/endpoint。"""

    def __init__(self, prometheus_url, namespace, cluster, endpoint):
        self.prom = PrometheusClient(prometheus_url)
        self.namespace = namespace
        self.cluster = cluster
        self.endpoint = endpoint
        self.results = {}

    def _identity_simple(self):
        # 与面板 stat 一致：rabbitmq_cluster, namespace, rabbitmq_endpoint
        return (
            f'rabbitmq_cluster="{self.cluster}", namespace="{self.namespace}", '
            f'rabbitmq_endpoint="{self.endpoint}"'
        )

    def _identity_ns_first(self):
        # 部分面板使用 namespace 在前
        return (
            f'namespace="{self.namespace}", rabbitmq_cluster="{self.cluster}", '
            f'rabbitmq_endpoint="{self.endpoint}"'
        )

    def _query_single_value(self, query):
        data = self.prom.query(query)
        if data:
            return float(data[0]["value"][1])
        return 0.0

    def _query_vector(self, query):
        out = []
        data = self.prom.query(query)
        for item in data:
            out.append(
                {
                    "labels": item["metric"],
                    "value": float(item["value"][1]),
                }
            )
        return out

    def run_all_checks(self):
        print("=" * 60)
        print(f"开始 RabbitMQ 巡检 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)

        ids = self._identity_simple()
        ri = RABBITMQ_RATE_INTERVAL
        sr = RABBITMQ_SHORT_RATE
        rg = RABBITMQ_RANGE

        overview = {}
        # 顶栏 stat 与面板标题一致（RabbitMQ-Overview-base.json）
        overview["messages_ready"] = self._query_single_value(
            f"sum(rabbitmq_queue_messages_ready * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        overview["outgoing_per_s"] = self._query_single_value(
            f"sum(irate(rabbitmq_global_messages_delivered_total[{ri}]) * on(instance, job) "
            f"group_left(rabbitmq_cluster) rabbitmq_identity_info{{{ids}}})"
        )
        overview["publishers"] = self._query_single_value(
            f"sum(rabbitmq_global_publishers * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        overview["connections"] = self._query_single_value(
            f"sum(rabbitmq_connections * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        overview["queues"] = self._query_single_value(
            f"sum(rabbitmq_queues * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        overview["messages_unacked"] = self._query_single_value(
            f"sum(rabbitmq_queue_messages_unacked * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        overview["incoming_per_s"] = self._query_single_value(
            f"sum(irate(rabbitmq_global_messages_received_total[{ri}]) * on(instance, job) "
            f"group_left(rabbitmq_cluster) rabbitmq_identity_info{{{ids}}})"
        )
        overview["consumers"] = self._query_single_value(
            f"sum(rabbitmq_global_consumers * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        overview["channels"] = self._query_single_value(
            f"sum(rabbitmq_channels * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        id_count_sel = (
            f'namespace="{self.namespace}",rabbitmq_cluster="{self.cluster}",'
            f'rabbitmq_endpoint="{self.endpoint}"'
        )
        overview["nodes"] = self._query_single_value(
            f"count(rabbitmq_identity_info{{{id_count_sel}}})"
        )

        self.results["overview"] = overview

        # 集群级消息健康（面板 OUTGOING / Unroutable / redeliver 等聚合）
        flows = {}
        flows["routed_per_s"] = self._query_single_value(
            f"sum(rate(rabbitmq_global_messages_routed_total[{sr}]) * on(instance, job) "
            f"group_left(rabbitmq_cluster) rabbitmq_identity_info{{{ids}}})"
        )
        flows["confirmed_per_s"] = self._query_single_value(
            f"sum(rate(rabbitmq_global_messages_confirmed_total[{sr}]) * on(instance, job) "
            f"group_left(rabbitmq_cluster) rabbitmq_identity_info{{{ids}}})"
        )
        flows["unroutable_dropped_per_s"] = self._query_single_value(
            f"sum(rate(rabbitmq_global_messages_unroutable_dropped_total[{sr}]) * on(instance, job) "
            f"group_left(rabbitmq_cluster) rabbitmq_identity_info{{{ids}}})"
        )
        flows["unroutable_returned_per_s"] = self._query_single_value(
            f"sum(rate(rabbitmq_global_messages_unroutable_returned_total[{sr}]) * on(instance, job) "
            f"group_left(rabbitmq_cluster) rabbitmq_identity_info{{{ids}}})"
        )
        flows["redelivered_per_s"] = self._query_single_value(
            f"sum(rate(rabbitmq_global_messages_redelivered_total[{sr}]) * on(instance, job) "
            f"group_left(rabbitmq_cluster) rabbitmq_identity_info{{{ids}}})"
        )
        flows["delivered_consume_per_s"] = self._query_single_value(
            f"sum((rate(rabbitmq_global_messages_delivered_consume_auto_ack_total[{sr}]) * on(instance, job) "
            f"group_left(rabbitmq_cluster) rabbitmq_identity_info{{{ids}}}) + "
            f"(rate(rabbitmq_global_messages_delivered_consume_manual_ack_total[{sr}]) * on(instance, job) "
            f"group_left(rabbitmq_cluster) rabbitmq_identity_info{{{ids}}}))"
        )
        self.results["cluster_flows"] = flows

        # 平均消息大小（面板 Avg Size，使用 $__range -> 固定窗口）
        avg_size_q = (
            f"sum (increase(rabbitmq_message_size_bytes_sum[{rg}]) * on(instance, job) "
            f"group_left(rabbitmq_cluster) rabbitmq_identity_info{{{ids}}}) / "
            f"sum (increase(rabbitmq_message_size_bytes_count[{rg}]) * on(instance, job) "
            f"group_left(rabbitmq_cluster) rabbitmq_identity_info{{{ids}}})"
        )
        self.results["avg_message_size_bytes"] = self._query_single_value(avg_size_q)

        id_nf = self._identity_ns_first()

        # 按节点：就绪/未确认、发布速率、内存余量、磁盘、运行时间
        ready_by_node = self._query_vector(
            f"sum(rabbitmq_queue_messages_ready * on(instance, job) group_left(rabbitmq_cluster, rabbitmq_node) "
            f"rabbitmq_identity_info{{{ids}}}) by(rabbitmq_node)"
        )
        unacked_by_node = self._query_vector(
            f"sum(rabbitmq_queue_messages_unacked * on(instance, job) group_left(rabbitmq_cluster, rabbitmq_node) "
            f"rabbitmq_identity_info{{{ids}}}) by(rabbitmq_node)"
        )
        published_by_node = self._query_vector(
            f"sum(rate(rabbitmq_global_messages_received_total[{sr}]) * on(instance, job) "
            f"group_left(rabbitmq_cluster, rabbitmq_node) rabbitmq_identity_info{{{ids}}}) by(rabbitmq_node)"
        )

        memory_free = self._query_vector(
            f"(rabbitmq_resident_memory_limit_bytes * on(instance, job) group_left(rabbitmq_cluster, rabbitmq_node) "
            f"rabbitmq_identity_info{{{ids}}}) - "
            f"(rabbitmq_process_resident_memory_bytes * on(instance, job) group_left(rabbitmq_cluster, rabbitmq_node) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        disk_avail = self._query_vector(
            f"rabbitmq_disk_space_available_bytes * on(instance, job) group_left(rabbitmq_cluster, rabbitmq_node) "
            f"rabbitmq_identity_info{{{ids}}}"
        )
        uptime = self._query_vector(
            f"rabbitmq_erlang_uptime_seconds *on(instance,job) group_left(rabbitmq_version, erlang_version) "
            f"rabbitmq_build_info * on(instance, job) group_left(rabbitmq_cluster, rabbitmq_node) "
            f"rabbitmq_identity_info{{{id_nf}}}"
        )

        node_map = {}

        def fill_from(series, key):
            for item in series:
                node = item["labels"].get("rabbitmq_node") or ""
                if node not in node_map:
                    node_map[node] = {"rabbitmq_node": node}
                node_map[node][key] = item["value"]
                if key == "uptime_seconds":
                    node_map[node]["rabbitmq_version"] = item["labels"].get("rabbitmq_version", "")
                    node_map[node]["erlang_version"] = item["labels"].get("erlang_version", "")

        fill_from(ready_by_node, "messages_ready")
        fill_from(unacked_by_node, "messages_unacked")
        fill_from(published_by_node, "published_per_s")
        fill_from(memory_free, "memory_free_bytes")
        fill_from(disk_avail, "disk_free_bytes")
        fill_from(uptime, "uptime_seconds")

        self.results["nodes"] = [node_map[k] for k in sorted(node_map.keys())]

        print("检查: 队列消息TOP 20...")
        queue_messages_ready = self._query_vector(
            f"rabbitmq_queue_messages_ready * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}}"
        )
        queue_messages_unacked = self._query_vector(
            f"rabbitmq_queue_messages_unacked * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}}"
        )
        
        queue_map = {}
        for item in queue_messages_ready:
            queue_name = item["labels"].get("queue", "")
            if queue_name not in queue_map:
                queue_map[queue_name] = {
                    "vhost": item["labels"].get("vhost", ""),
                    "queue": queue_name,
                    "messages_ready": 0,
                    "messages_unacked": 0,
                    "total_messages": 0,
                }
            queue_map[queue_name]["messages_ready"] = item["value"]
        
        for item in queue_messages_unacked:
            queue_name = item["labels"].get("queue", "")
            if queue_name in queue_map:
                queue_map[queue_name]["messages_unacked"] = item["value"]
        
        for q in queue_map.values():
            q["total_messages"] = q["messages_ready"] + q["messages_unacked"]
        
        queue_top_list = sorted(queue_map.values(), key=lambda x: x["total_messages"], reverse=True)
        self.results["queue_messages_top"] = queue_top_list[:20]

        print("检查: 消息积压检测...")
        backlog_summary = {}
        backlog_summary["total_ready"] = self._query_single_value(
            f"sum(rabbitmq_queue_messages_ready * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        backlog_summary["total_unacked"] = self._query_single_value(
            f"sum(rabbitmq_queue_messages_unacked * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        backlog_summary["total_messages"] = backlog_summary["total_ready"] + backlog_summary["total_unacked"]
        
        backlog_queues = [q for q in queue_map.values() if q["total_messages"] > 0]
        backlog_summary["queues_with_backlog"] = len(backlog_queues)
        backlog_summary["critical_queues"] = len([q for q in backlog_queues if q["total_messages"] > 10000])
        backlog_summary["warning_queues"] = len([q for q in backlog_queues if q["total_messages"] > 1000 and q["total_messages"] <= 10000])
        
        self.results["backlog_summary"] = backlog_summary

        print("检查: 集群综合指标...")
        cluster_stats = {}
        
        cluster_stats["resident_memory_bytes"] = self._query_single_value(
            f"sum(rabbitmq_process_resident_memory_bytes * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        cluster_stats["resident_memory_limit_bytes"] = self._query_single_value(
            f"sum(rabbitmq_resident_memory_limit_bytes * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        cluster_stats["resident_memory_usage_percent"] = (
            cluster_stats["resident_memory_bytes"] / cluster_stats["resident_memory_limit_bytes"] * 100 
            if cluster_stats["resident_memory_limit_bytes"] > 0 else 0
        )
        
        cluster_stats["disk_free_bytes"] = self._query_single_value(
            f"sum(rabbitmq_disk_free * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        
        cluster_stats["erlang_processes_used"] = self._query_single_value(
            f"sum(rabbitmq_erlang_processes_used * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        cluster_stats["erlang_processes_limit"] = self._query_single_value(
            f"sum(rabbitmq_erlang_processes_limit * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        cluster_stats["erlang_processes_usage_percent"] = (
            cluster_stats["erlang_processes_used"] / cluster_stats["erlang_processes_limit"] * 100 
            if cluster_stats["erlang_processes_limit"] > 0 else 0
        )
        
        cluster_stats["scheduler_run_queue"] = self._query_single_value(
            f"sum(rabbitmq_erlang_scheduler_run_queue * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        
        cluster_stats["total_ready_messages"] = self._query_single_value(
            f"sum(rabbitmq_queue_messages_ready * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        cluster_stats["total_unacked_messages"] = self._query_single_value(
            f"sum(rabbitmq_queue_messages_unacked * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        cluster_stats["total_messages_bytes"] = self._query_single_value(
            f"sum(rabbitmq_queue_messages_bytes * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        
        cluster_stats["consumer_capacity_total"] = self._query_single_value(
            f"sum(rabbitmq_queue_consumer_capacity * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        cluster_stats["consumer_utilisation_avg"] = self._query_single_value(
            f"avg(rabbitmq_queue_consumer_utilisation * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        
        cluster_stats["redelivered_total"] = self._query_single_value(
            f"sum(rabbitmq_global_messages_redelivered_total * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        
        cluster_stats["unroutable_dropped_total"] = self._query_single_value(
            f"sum(rabbitmq_global_messages_unroutable_dropped_total * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        cluster_stats["unroutable_returned_total"] = self._query_single_value(
            f"sum(rabbitmq_global_messages_unroutable_returned_total * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        
        cluster_stats["auth_failed_amqp"] = self._query_single_value(
            f"sum(rabbitmq_auth_attempts_failed_total{{protocol='amqp091'}} * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        cluster_stats["auth_failed_http"] = self._query_single_value(
            f"sum(rabbitmq_auth_attempts_failed_total{{protocol='http'}} * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        
        self.results["cluster_stats"] = cluster_stats

        print("检查: 告警状态检测...")
        alarms = {}
        alarms["file_descriptor_alarm"] = self._query_single_value(
            f"sum(rabbitmq_alarms_file_descriptor_limit * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        alarms["disk_space_alarm"] = self._query_single_value(
            f"sum(rabbitmq_alarms_free_disk_space_watermark * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        alarms["memory_alarm"] = self._query_single_value(
            f"sum(rabbitmq_alarms_memory_used_watermark * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        self.results["alarms"] = alarms

        print("检查: 进程资源使用...")
        process_stats = {}
        process_stats["open_fds"] = self._query_single_value(
            f"sum(rabbitmq_process_open_fds * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        process_stats["max_fds"] = self._query_single_value(
            f"sum(rabbitmq_process_max_fds * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        process_stats["open_tcp_sockets"] = self._query_single_value(
            f"sum(rabbitmq_process_open_tcp_sockets * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        process_stats["max_tcp_sockets"] = self._query_single_value(
            f"sum(rabbitmq_process_max_tcp_sockets * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        process_stats["erlang_processes_used"] = self._query_single_value(
            f"sum(rabbitmq_erlang_processes_used * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        process_stats["erlang_processes_limit"] = self._query_single_value(
            f"sum(rabbitmq_erlang_processes_limit * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        self.results["process_stats"] = process_stats

        print("检查: 连接通道统计...")
        connection_stats = {}
        connection_stats["connections_opened_total"] = self._query_single_value(
            f"sum(rabbitmq_connections_opened_total * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        connection_stats["connections_closed_total"] = self._query_single_value(
            f"sum(rabbitmq_connections_closed_total * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        connection_stats["channels_opened_total"] = self._query_single_value(
            f"sum(rabbitmq_channels_opened_total * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        connection_stats["channels_closed_total"] = self._query_single_value(
            f"sum(rabbitmq_channels_closed_total * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        connection_stats["queues_declared_total"] = self._query_single_value(
            f"sum(rabbitmq_queues_declared_total * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        connection_stats["queues_created_total"] = self._query_single_value(
            f"sum(rabbitmq_queues_created_total * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        connection_stats["queues_deleted_total"] = self._query_single_value(
            f"sum(rabbitmq_queues_deleted_total * on(instance, job) group_left(rabbitmq_cluster) "
            f"rabbitmq_identity_info{{{ids}}})"
        )
        self.results["connection_stats"] = connection_stats

        print("RabbitMQ 巡检完成")
        print("=" * 60)
        return self.results


# ==================== 报告 ====================
class ReportGenerator:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_html(self, kafka_results, rabbitmq_results, kafka_rule_results=None, rabbitmq_rule_results=None):
        overview = kafka_results.get("overview", {}) if kafka_results else {}
        consumer_groups = kafka_results.get("consumer_groups", {}) if kafka_results else {}
        topics = kafka_results.get("topics", {}) if kafka_results else {}
        top_lags = kafka_results.get("top_lags", []) if kafka_results else []
        orphan_topics = kafka_results.get("orphan_topics", []) if kafka_results else []
        orphan_cg = kafka_results.get("orphan_consumer_groups", []) if kafka_results else []
        top_partition_lags = kafka_results.get("top_partition_lags", []) if kafka_results else []
        top_produce_rates = kafka_results.get("top_produce_rates", []) if kafka_results else []
        top_consume_rates = kafka_results.get("top_consume_rates", []) if kafka_results else []
        topic_consume_gap = kafka_results.get("topic_consume_gap", []) if kafka_results else []
        isr_insufficient = kafka_results.get("isr_insufficient", []) if kafka_results else []
        broker_nodes = kafka_results.get("broker_nodes", []) if kafka_results else []
        topic_message_stats = kafka_results.get("topic_message_stats", []) if kafka_results else []

        rmq_overview = (rabbitmq_results or {}).get("overview", {})
        rmq_flows = (rabbitmq_results or {}).get("cluster_flows", {})
        rmq_nodes = (rabbitmq_results or {}).get("nodes", [])
        rmq_avg_size = (rabbitmq_results or {}).get("avg_message_size_bytes", 0)
        rmq_queue_top = (rabbitmq_results or {}).get("queue_messages_top", [])
        rmq_backlog = (rabbitmq_results or {}).get("backlog_summary", {})
        rmq_cluster_stats = (rabbitmq_results or {}).get("cluster_stats", {})
        rmq_alarms = (rabbitmq_results or {}).get("alarms", {})
        rmq_process_stats = (rabbitmq_results or {}).get("process_stats", {})
        rmq_connection_stats = (rabbitmq_results or {}).get("connection_stats", {})

        kafka_rules = (kafka_rule_results or {}).get("rules", {})
        kafka_rule_alerts = (kafka_rule_results or {}).get("alerts", [])
        kafka_rule_summary = (kafka_rule_results or {}).get("summary", {"total_checks": 0, "normal": 0, "warning": 0, "critical": 0})
        
        rmq_rules = (rabbitmq_rule_results or {}).get("rules", {})
        rmq_rule_alerts = (rabbitmq_rule_results or {}).get("alerts", [])
        rmq_rule_summary = (rabbitmq_rule_results or {}).get("summary", {"total_checks": 0, "normal": 0, "warning": 0, "critical": 0})

        alerts = []
        summary = {"total_checks": 0, "normal": 0, "warning": 0, "critical": 0}

        for alert in kafka_rule_alerts:
            alert["type"] = "Kafka"
            alerts.append(alert)
        for alert in rmq_rule_alerts:
            alert["type"] = "RabbitMQ"
            alerts.append(alert)
        
        summary["total_checks"] = kafka_rule_summary["total_checks"] + rmq_rule_summary["total_checks"]
        summary["normal"] = kafka_rule_summary["normal"] + rmq_rule_summary["normal"]
        summary["warning"] = kafka_rule_summary["warning"] + rmq_rule_summary["warning"]
        summary["critical"] = kafka_rule_summary["critical"] + rmq_rule_summary["critical"]

        if kafka_results:
            for node in broker_nodes:
                summary["normal"] += 1

            for item in isr_insufficient:
                alerts.append({
                    "check_name": "ISR不足",
                    "type": "Kafka",
                    "node": item["topic"],
                    "instance": f"Partition {item['partition']}",
                    "value": f"缺失{int(item['missing_replicas'])}个ISR",
                    "status": "critical",
                    "threshold": "0"
                })
                summary["critical"] += 1

        if rabbitmq_results:
            if rmq_alarms.get("file_descriptor_alarm", 0) > 0:
                alerts.append({
                    "check_name": "文件描述符告警",
                    "type": "RabbitMQ",
                    "node": "Cluster",
                    "instance": "",
                    "value": "触发",
                    "status": "critical",
                    "threshold": "0"
                })
                summary["critical"] += 1
            else:
                summary["normal"] += 1

            if rmq_alarms.get("disk_space_alarm", 0) > 0:
                alerts.append({
                    "check_name": "磁盘空间告警",
                    "type": "RabbitMQ",
                    "node": "Cluster",
                    "instance": "",
                    "value": "触发",
                    "status": "critical",
                    "threshold": "0"
                })
                summary["critical"] += 1
            else:
                summary["normal"] += 1

            if rmq_alarms.get("memory_alarm", 0) > 0:
                alerts.append({
                    "check_name": "内存告警",
                    "type": "RabbitMQ",
                    "node": "Cluster",
                    "instance": "",
                    "value": "触发",
                    "status": "critical",
                    "threshold": "0"
                })
                summary["critical"] += 1
            else:
                summary["normal"] += 1

        template = Template(
            """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>消息队列巡检报告 - {{ date }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }
        .header h1 { font-size: 36px; margin-bottom: 10px; }
        .header .subtitle { opacity: 0.9; font-size: 16px; }
        .section-title {
            padding: 16px 30px 0;
            font-size: 22px;
            color: #1e3c72;
            border-left: 4px solid #667eea;
            margin: 24px 30px 0;
        }
        .summary-section {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
        }
        .summary-card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        }
        .summary-card .number { font-size: 32px; font-weight: bold; color: #667eea; }
        .summary-card .label { color: #6c757d; font-size: 14px; margin-top: 5px; }
        .details-section { padding: 30px; }
        .details-section h2 { margin-bottom: 20px; color: #2c3e50; border-bottom: 3px solid #667eea; padding-bottom: 10px; margin-top: 30px; }
        .table-wrapper {
            width: 100%;
            overflow-x: auto;
            margin-top: 10px;
            margin-bottom: 20px;
        }
        .data-table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .data-table th, .data-table td {
            padding: 12px;
            border: 1px solid #e9ecef;
            text-align: left;
            font-size: 13px;
            white-space: nowrap;
        }
        .data-table th {
            background: #667eea;
            color: white;
            font-weight: 600;
        }
        .data-table tr:nth-child(even) { background: #f8f9fa; }
        .footer {
            padding: 20px;
            text-align: center;
            color: #6c757d;
            font-size: 13px;
            background: #f8f9fa;
        }
        .summary-card.normal .number { color: #28a745; }
        .summary-card.warning .number { color: #ffc107; }
        .summary-card.critical .number { color: #dc3545; }
        .alerts-section {
            padding: 20px 30px;
            background: #fff5f5;
            border-bottom: 2px solid #dc3545;
        }
        .alerts-section h2 { color: #dc3545; margin-bottom: 20px; display: flex; align-items: center; gap: 10px; }
        .alert-table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .alert-table th { background: #dc3545; color: white; padding: 15px; text-align: left; font-weight: 600; }
        .alert-table td { padding: 12px 15px; border-bottom: 1px solid #e9ecef; }
        .alert-table tr:hover { background: #f8f9fa; }
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .badge-warning { background: #ffc107; color: #212529; }
        .badge-critical { background: #dc3545; color: white; }
        .badge-type { background: #17a2b8; color: white; font-size: 11px; }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>消息队列巡检报告</h1>
        <div class="subtitle">生成时间: {{ date }} | 数据源: Prometheus（Kafka + RabbitMQ）</div>
    </div>

    <div class="summary-section">
        <div class="summary-card normal"><div class="number">{{ summary.normal }}</div><div class="label">正常</div></div>
        <div class="summary-card warning"><div class="number">{{ summary.warning }}</div><div class="label">警告</div></div>
        <div class="summary-card critical"><div class="number">{{ summary.critical }}</div><div class="label">严重</div></div>
    </div>

    {% if alerts %}
    <div class="alerts-section">
        <h2>⚠️ 告警详情 (共 {{ alerts|length }} 条)</h2>
        <table class="alert-table">
            <thead><tr><th>集群类型</th><th>检查项</th><th>节点/实例</th><th>当前值</th><th>状态</th><th>阈值</th></tr></thead>
            <tbody>
                {% for alert in alerts %}
                <tr {% if alert.status == 'critical' %}style="background-color: #fdf2f2;"{% elif alert.status == 'warning' %}style="background-color: #fffcf2;"{% endif %}>
                    <td><span class="badge badge-type">{{ alert.type or 'Unknown' }}</span></td>
                    <td>{{ alert.check_name }}</td>
                    <td>{{ alert.node }}{% if alert.instance %} / {{ alert.instance }}{% endif %}</td>
                    <td><strong>{{ alert.value }}</strong></td>
                    <td><span class="badge badge-{{ alert.status }}">{% if alert.status == 'warning' %}⚠️ 警告{% else %}🔴 严重{% endif %}</span></td>
                    <td>{{ alert.threshold }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    <div class="details-section">
        <h2>📋 巡检规则统计</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr>
                    <th>集群类型</th><th>检查总数</th><th>正常</th><th>警告</th><th>严重</th>
                </tr></thead>
                <tbody>
                    <tr>
                        <td>Kafka</td>
                        <td>{{ kafka_rule_summary.total_checks }}</td>
                        <td style="color: #28a745; font-weight: bold;">{{ kafka_rule_summary.normal }}</td>
                        <td{% if kafka_rule_summary.warning > 0 %} style="background-color: #fff3cd; color: #856404; font-weight: bold;"{% endif %}>{{ kafka_rule_summary.warning }}</td>
                        <td{% if kafka_rule_summary.critical > 0 %} style="background-color: #f8d7da; color: #721c24; font-weight: bold;"{% endif %}>{{ kafka_rule_summary.critical }}</td>
                    </tr>
                    <tr>
                        <td>RabbitMQ</td>
                        <td>{{ rmq_rule_summary.total_checks }}</td>
                        <td style="color: #28a745; font-weight: bold;">{{ rmq_rule_summary.normal }}</td>
                        <td{% if rmq_rule_summary.warning > 0 %} style="background-color: #fff3cd; color: #856404; font-weight: bold;"{% endif %}>{{ rmq_rule_summary.warning }}</td>
                        <td{% if rmq_rule_summary.critical > 0 %} style="background-color: #f8d7da; color: #721c24; font-weight: bold;"{% endif %}>{{ rmq_rule_summary.critical }}</td>
                    </tr>
                    <tr>
                        <td><strong>总计</strong></td>
                        <td><strong>{{ summary.total_checks }}</strong></td>
                        <td style="color: #28a745; font-weight: bold;"><strong>{{ summary.normal }}</strong></td>
                        <td{% if summary.warning > 0 %} style="background-color: #fff3cd; color: #856404; font-weight: bold;"{% endif %}><strong>{{ summary.warning }}</strong></td>
                        <td{% if summary.critical > 0 %} style="background-color: #f8d7da; color: #721c24; font-weight: bold;"{% endif %}><strong>{{ summary.critical }}</strong></td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>

    {% if show_kafka %}
    <div class="section-title">Kafka 集群</div>
    <div class="summary-section">
        <div class="summary-card"><div class="number">{{ overview.brokers|int }}</div><div class="label">Brokers</div></div>
        <div class="summary-card"><div class="number">{{ overview.topics|int }}</div><div class="label">Topics</div></div>
        <div class="summary-card"><div class="number">{{ overview.partitions|int }}</div><div class="label">Partitions</div></div>
        <div class="summary-card"><div class="number">{{ overview.consumer_groups|int }}</div><div class="label">Consumer Groups</div></div>
        <div class="summary-card"><div class="number">{{ overview.consumers|int }}</div><div class="label">Consumers</div></div>
        <div class="summary-card"><div class="number">{{ overview.replicas|int }}</div><div class="label">Replicas</div></div>
        <div class="summary-card"><div class="number">{{ overview.in_sync_replicas|int }}</div><div class="label">In Sync Replicas</div></div>
        <div class="summary-card"><div class="number">{{ overview.preferred_not_leader|int }}</div><div class="label">Non-preferred Leader</div></div>
        <div class="summary-card"><div class="number">{{ "%.2f"|format(overview.total_produce_rate) }}</div><div class="label">Total Produce/s</div></div>
        <div class="summary-card"><div class="number">{{ "%.2f"|format(overview.total_consume_rate) }}</div><div class="label">Total Consume/s</div></div>
        <div class="summary-card"><div class="number">{{ overview.total_lag|int }}</div><div class="label">Total Lag</div></div>
    </div>

    <div class="details-section">
        <h2>Kafka 节点</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr>
                    <th>Broker ID</th><th>Address</th>
                </tr></thead>
                <tbody>
                    {% for item in broker_nodes %}
                    <tr>
                        <td>{{ item.broker_id }}</td>
                        <td>{{ item.address }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div class="details-section">
        <h2>消费组列表</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr><th>消费组</th><th>消费者数</th><th>关联Topic数</th></tr></thead>
                <tbody>
                    {% for cg, data in consumer_groups.items() %}
                    <tr><td>{{ cg }}</td><td>{{ data.members|int }}</td><td>{{ data.topic_count|int }}</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div class="details-section">
        <h2>Topic 列表</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr><th>Topic</th><th>分区数</th></tr></thead>
                <tbody>
                    {% for topic, data in topics.items() %}
                    <tr><td>{{ topic }}</td><td>{{ data.partitions|int }}</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div class="details-section">
        <h2>积压 TOP 20（消费组+Topic）</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr><th>消费组</th><th>Topic</th><th>积压数</th></tr></thead>
                <tbody>
                    {% for item in top_lags %}
                    <tr><td>{{ item.consumergroup }}</td><td>{{ item.topic }}</td><td>{{ item.lag|int }}</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div class="details-section">
        <h2>无消费组消费的 Topic</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr><th>Topic</th><th>分区数</th><th>总消息数</th><th>每秒生产速率</th></tr></thead>
                <tbody>
                    {% for item in orphan_topics %}
                    <tr><td>{{ item.topic }}</td><td>{{ item.partitions|int }}</td><td>{{ item.total_messages|int }}</td><td>{{ "%.2f"|format(item.produce_rate) }}</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div class="details-section">
        <h2>无关联 Topic 的消费组</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr><th>消费组</th><th>消费者数</th></tr></thead>
                <tbody>
                    {% for item in orphan_cg %}
                    <tr><td>{{ item.consumergroup }}</td><td>{{ item.members|int }}</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div class="details-section">
        <h2>分区积压 TOP 20</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr><th>消费组</th><th>Topic</th><th>分区</th><th>积压数</th></tr></thead>
                <tbody>
                    {% for item in top_partition_lags %}
                    <tr><td>{{ item.consumergroup }}</td><td>{{ item.topic }}</td><td>{{ item.partition }}</td><td>{{ item.lag|int }}</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div class="details-section">
        <h2>Topic生产速率 TOP 20</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr><th>Topic</th><th>每秒生产消息数</th></tr></thead>
                <tbody>
                    {% for item in top_produce_rates %}
                    <tr><td>{{ item.topic }}</td><td>{{ "%.2f"|format(item.produce_rate) }}</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div class="details-section">
        <h2>消费组消费速率 TOP 20</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr><th>消费组</th><th>Topic</th><th>每秒消费消息数</th></tr></thead>
                <tbody>
                    {% for item in top_consume_rates %}
                    <tr><td>{{ item.consumergroup }}</td><td>{{ item.topic }}</td><td>{{ "%.2f"|format(item.consume_rate) }}</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div class="details-section">
        <h2>Topic消费能力检测（消费速率 - 生产速率×消费组数）</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr><th>Topic</th><th>生产速率/s</th><th>消费速率/s</th><th>消费组数</th><th>差值(消费-生产×组数)</th><th>状态</th></tr></thead>
                <tbody>
                    {% for item in topic_consume_gap %}
                    <tr>
                        <td>{{ item.topic }}</td>
                        <td>{{ "%.2f"|format(item.produce_rate) }}</td>
                        <td>{{ "%.2f"|format(item.consume_rate) }}</td>
                        <td>{{ item.consumer_groups|int }}</td>
                        <td{% if item.gap < 0 %} style="background-color: #f8d7da; color: #721c24;"{% endif %}>{{ "%.2f"|format(item.gap) }}</td>
                        <td{% if item.gap < 0 %} style="background-color: #f8d7da; color: #721c24; font-weight: bold;"{% endif %}>{{ item.status }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        <p style="color: #6c757d; font-size: 12px; margin-top: 10px;">注：差值为负表示消费能力不足，需要关注</p>
    </div>

    <div class="details-section">
        <h2>ISR不足分区检测</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr><th>Topic</th><th>分区</th><th>副本数</th><th>ISR数</th><th>缺失ISR数</th></tr></thead>
                <tbody>
                    {% if isr_insufficient %}
                    {% for item in isr_insufficient %}
                    <tr style="background-color: #f8d7da;">
                        <td>{{ item.topic }}</td>
                        <td>{{ item.partition }}</td>
                        <td>{{ item.replicas|int }}</td>
                        <td>{{ item.in_sync_replicas|int }}</td>
                        <td style="color: #721c24; font-weight: bold;">{{ item.missing_replicas|int }}</td>
                    </tr>
                    {% endfor %}
                    {% else %}
                    <tr><td colspan="5" style="text-align: center; color: #28a745;">所有分区ISR正常</td></tr>
                    {% endif %}
                </tbody>
            </table>
        </div>
    </div>

    <div class="details-section">
        <h2>Topic消息统计 TOP 20</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr><th>Topic</th><th>消息总数</th><th>当前偏移量</th><th>最早偏移量</th></tr></thead>
                <tbody>
                    {% for item in topic_message_stats %}
                    <tr><td>{{ item.topic }}</td><td>{{ item.total_messages }}</td><td>{{ item.current_offset }}</td><td>{{ item.oldest_offset }}</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    {% endif %}

    {% if show_rabbitmq %}
    <div class="section-title">RabbitMQ 集群 </div>
    <div class="summary-section">
        <div class="summary-card"><div class="number">{{ rmq_overview.messages_ready|int }}</div><div class="label">Ready Messages </div></div>
        <div class="summary-card"><div class="number">{{ "%.2f"|format(rmq_overview.outgoing_per_s) }}</div><div class="label">Outgoing messages/s</div></div>
        <div class="summary-card"><div class="number">{{ rmq_overview.publishers|int }}</div><div class="label">Publishers</div></div>
        <div class="summary-card"><div class="number">{{ rmq_overview.connections|int }}</div><div class="label">Connections</div></div>
        <div class="summary-card"><div class="number">{{ rmq_overview.queues|int }}</div><div class="label">Queues</div></div>
        <div class="summary-card"><div class="number">{{ rmq_overview.messages_unacked|int }}</div><div class="label">Unacknowledged messages</div></div>
        <div class="summary-card"><div class="number">{{ "%.2f"|format(rmq_overview.incoming_per_s) }}</div><div class="label">Incoming messages/s</div></div>
        <div class="summary-card"><div class="number">{{ rmq_overview.consumers|int }}</div><div class="label">Consumers</div></div>
        <div class="summary-card"><div class="number">{{ rmq_overview.channels|int }}</div><div class="label">Channels</div></div>
        <div class="summary-card"><div class="number">{{ rmq_overview.nodes|int }}</div><div class="label">Nodes</div></div>
    </div>

    <div class="details-section">
        <h2>节点资源与队列分布（NODES / QUEUED MESSAGES）</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr>
                    <th>节点</th><th>运行时间(s)</th><th>RabbitMQ</th><th>Erlang</th>
                    <th>内存剩余(B)</th><th>磁盘可用(B)</th>
                    <th>Ready</th><th>Unacked</th><th>Published/s</th>
                </tr></thead>
                <tbody>
                    {% for row in rmq_nodes %}
                    <tr>
                        <td>{{ row.rabbitmq_node }}</td>
                        <td>{{ row.uptime_seconds|default(0)|int }}</td>
                        <td>{{ row.rabbitmq_version|default("") }}</td>
                        <td>{{ row.erlang_version|default("") }}</td>
                        <td>{{ row.memory_free_bytes|default(0)|int }}</td>
                        <td>{{ row.disk_free_bytes|default(0)|int }}</td>
                        <td>{{ row.messages_ready|default(0)|int }}</td>
                        <td>{{ row.messages_unacked|default(0)|int }}</td>
                        <td>{{ "%.4f"|format(row.published_per_s|default(0.0)) }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div class="summary-section">
        <div class="summary-card"><div class="number">{{ rmq_backlog.total_messages|int }}</div><div class="label">总积压消息</div></div>
        <div class="summary-card"><div class="number">{{ rmq_backlog.total_ready|int }}</div><div class="label">待投递消息</div></div>
        <div class="summary-card"><div class="number">{{ rmq_backlog.total_unacked|int }}</div><div class="label">未确认消息</div></div>
        <div class="summary-card"><div class="number">{{ rmq_backlog.queues_with_backlog|int }}</div><div class="label">有积压队列数</div></div>
        <div class="summary-card{% if rmq_backlog.warning_queues > 0 %} warning{% endif %}"><div class="number">{{ rmq_backlog.warning_queues|int }}</div><div class="label">警告队列(>1000)</div></div>
        <div class="summary-card{% if rmq_backlog.critical_queues > 0 %} critical{% endif %}"><div class="number">{{ rmq_backlog.critical_queues|int }}</div><div class="label">严重队列(>10000)</div></div>
    </div>

    <div class="details-section">
        <h2>集群资源指标</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr>
                    <th>指标</th><th>当前值</th><th>阈值/限制</th><th>使用率</th>
                </tr></thead>
                <tbody>
                    <tr>
                        <td>内存使用 (Resident)</td>
                        <td>{{ "%.2f GB"|format(rmq_cluster_stats.resident_memory_bytes|default(0) / (1024*1024*1024)) }}</td>
                        <td>{{ "%.2f GB"|format(rmq_cluster_stats.resident_memory_limit_bytes|default(0) / (1024*1024*1024)) }}</td>
                        <td{% if rmq_cluster_stats.resident_memory_usage_percent|default(0) > 80 %} style="background-color: #f8d7da; color: #721c24; font-weight: bold;"{% endif %}>
                            {{ "%.1f%%"|format(rmq_cluster_stats.resident_memory_usage_percent|default(0)) }}
                        </td>
                    </tr>
                    <tr>
                        <td>磁盘可用空间</td>
                        <td>{{ "%.2f GB"|format(rmq_cluster_stats.disk_free_bytes|default(0) / (1024*1024*1024)) }}</td>
                        <td>-</td>
                        <td>-</td>
                    </tr>
                    <tr>
                        <td>Erlang进程数</td>
                        <td>{{ rmq_cluster_stats.erlang_processes_used|default(0)|int }}</td>
                        <td>{{ rmq_cluster_stats.erlang_processes_limit|default(0)|int }}</td>
                        <td{% if rmq_cluster_stats.erlang_processes_usage_percent|default(0) > 80 %} style="background-color: #f8d7da; color: #721c24; font-weight: bold;"{% endif %}>
                            {{ "%.1f%%"|format(rmq_cluster_stats.erlang_processes_usage_percent|default(0)) }}
                        </td>
                    </tr>
                    <tr>
                        <td>调度器运行队列</td>
                        <td{% if rmq_cluster_stats.scheduler_run_queue|default(0) > 10 %} style="background-color: #f8d7da; color: #721c24; font-weight: bold;"{% endif %}>
                            {{ rmq_cluster_stats.scheduler_run_queue|default(0)|int }}
                        </td>
                        <td>&lt; 10</td>
                        <td>-</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>

    <div class="details-section">
        <h2>消息统计与消费者指标</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr>
                    <th>指标</th><th>当前值</th><th>单位</th>
                </tr></thead>
                <tbody>
                    <tr>
                        <td>队列中Ready消息</td>
                        <td>{{ rmq_cluster_stats.total_ready_messages|default(0)|int }}</td>
                        <td>条</td>
                    </tr>
                    <tr>
                        <td>队列中Unacked消息</td>
                        <td>{{ rmq_cluster_stats.total_unacked_messages|default(0)|int }}</td>
                        <td>条</td>
                    </tr>
                    <tr>
                        <td>队列消息总字节数</td>
                        <td>{{ "%.2f MB"|format(rmq_cluster_stats.total_messages_bytes|default(0) / (1024*1024)) }}</td>
                        <td>-</td>
                    </tr>
                    <tr>
                        <td>消费者容量总计</td>
                        <td>{{ rmq_cluster_stats.consumer_capacity_total|default(0)|int }}</td>
                        <td>-</td>
                    </tr>
                    <tr>
                        <td>消费者平均利用率</td>
                        <td>{{ "%.2f"|format(rmq_cluster_stats.consumer_utilisation_avg|default(0)) }}</td>
                        <td>-</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>

    <div class="details-section">
        <h2>集群消息流</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr>
                    <th>路由到队列 / s</th><th>发布确认 / s</th><th>投递消费 / s</th>
                    <th>无法路由丢弃 / s</th><th>无法路由退回 / s</th><th>重投 / s</th>
                    <th>近{{ range_label }}平均消息大小（字节）</th>
                </tr></thead>
                <tbody><tr>
                    <td>{{ "%.4f"|format(rmq_flows.routed_per_s) }}</td>
                    <td>{{ "%.4f"|format(rmq_flows.confirmed_per_s) }}</td>
                    <td>{{ "%.4f"|format(rmq_flows.delivered_consume_per_s) }}</td>
                    <td>{{ "%.4f"|format(rmq_flows.unroutable_dropped_per_s) }}</td>
                    <td>{{ "%.4f"|format(rmq_flows.unroutable_returned_per_s) }}</td>
                    <td>{{ "%.4f"|format(rmq_flows.redelivered_per_s) }}</td>
                    <td>{{ "%.2f"|format(rmq_avg_size) }}</td>
                </tr></tbody>
            </table>
        </div>
    </div>

    <div class="details-section">
        <h2>队列消息积压TOP 20</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr><th>VHost</th><th>队列名称</th><th>待投递</th><th>未确认</th><th>总积压</th></tr></thead>
                <tbody>
                    {% for item in rmq_queue_top %}
                    <tr{% if item.total_messages > 10000 %} style="background-color: #f8d7da;"{% elif item.total_messages > 1000 %} style="background-color: #fff3cd;"{% endif %}>
                        <td>{{ item.vhost }}</td><td>{{ item.queue }}</td>
                        <td>{{ item.messages_ready|int }}</td><td>{{ item.messages_unacked|int }}</td>
                        <td{% if item.total_messages > 10000 %} style="font-weight: bold; color: #dc3545;"{% elif item.total_messages > 1000 %} style="font-weight: bold; color: #ffc107;"{% endif %}>{{ item.total_messages|int }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div class="details-section">
        <h2>告警状态检测</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr><th>告警类型</th><th>状态</th></tr></thead>
                <tbody>
                    <tr>
                        <td>文件描述符告警</td>
                        <td{% if rmq_alarms.file_descriptor_alarm > 0 %} style="background-color: #f8d7da; color: #721c24; font-weight: bold;"{% else %} style="color: #28a745;"{% endif %}>
                            {{ "触发" if rmq_alarms.file_descriptor_alarm > 0 else "正常" }}
                        </td>
                    </tr>
                    <tr>
                        <td>磁盘空间告警</td>
                        <td{% if rmq_alarms.disk_space_alarm > 0 %} style="background-color: #f8d7da; color: #721c24; font-weight: bold;"{% else %} style="color: #28a745;"{% endif %}>
                            {{ "触发" if rmq_alarms.disk_space_alarm > 0 else "正常" }}
                        </td>
                    </tr>
                    <tr>
                        <td>内存使用告警</td>
                        <td{% if rmq_alarms.memory_alarm > 0 %} style="background-color: #f8d7da; color: #721c24; font-weight: bold;"{% else %} style="color: #28a745;"{% endif %}>
                            {{ "触发" if rmq_alarms.memory_alarm > 0 else "正常" }}
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>

    <div class="details-section">
        <h2>进程资源使用</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr>
                    <th>打开文件描述符</th><th>文件描述符上限</th><th>打开TCP连接</th><th>TCP连接上限</th>
                    <th>Erlang进程数</th><th>Erlang进程上限</th>
                </tr></thead>
                <tbody><tr>
                    <td>{{ rmq_process_stats.open_fds|int }}</td>
                    <td>{{ rmq_process_stats.max_fds|int }}</td>
                    <td>{{ rmq_process_stats.open_tcp_sockets|int }}</td>
                    <td>{{ rmq_process_stats.max_tcp_sockets|int }}</td>
                    <td>{{ rmq_process_stats.erlang_processes_used|int }}</td>
                    <td>{{ rmq_process_stats.erlang_processes_limit|int }}</td>
                </tr></tbody>
            </table>
        </div>
    </div>

    <div class="details-section">
        <h2>连接通道统计（累计）</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr>
                    <th>连接打开数</th><th>连接关闭数</th><th>通道打开数</th><th>通道关闭数</th>
                    <th>队列声明数</th><th>队列创建数</th><th>队列删除数</th>
                </tr></thead>
                <tbody><tr>
                    <td>{{ rmq_connection_stats.connections_opened_total|int }}</td>
                    <td>{{ rmq_connection_stats.connections_closed_total|int }}</td>
                    <td>{{ rmq_connection_stats.channels_opened_total|int }}</td>
                    <td>{{ rmq_connection_stats.channels_closed_total|int }}</td>
                    <td>{{ rmq_connection_stats.queues_declared_total|int }}</td>
                    <td>{{ rmq_connection_stats.queues_created_total|int }}</td>
                    <td>{{ rmq_connection_stats.queues_deleted_total|int }}</td>
                </tr></tbody>
            </table>
        </div>
    </div>
    {% endif %}

    <div class="footer">
        <p>本报告由 mq_inspection 自动生成 | Prometheus |
        {% if show_kafka %}Kafka Exporter{% endif %}
        {% if show_kafka and show_rabbitmq %} + {% endif %}
        {% if show_rabbitmq %}RabbitMQ Prometheus Plugin{% endif %}
        | {{ date }}</p>
    </div>
</div>
</body>
</html>
        """
        )

        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        html = template.render(
            date=date_str,
            show_kafka=bool(kafka_results),
            show_rabbitmq=bool(rabbitmq_results),
            summary=summary,
            alerts=alerts,
            overview=overview,
            consumer_groups=consumer_groups,
            topics=topics,
            top_lags=top_lags,
            orphan_topics=orphan_topics,
            orphan_cg=orphan_cg,
            top_partition_lags=top_partition_lags,
            top_produce_rates=top_produce_rates,
            top_consume_rates=top_consume_rates,
            topic_consume_gap=topic_consume_gap,
            isr_insufficient=isr_insufficient,
            broker_nodes=broker_nodes,
            topic_message_stats=topic_message_stats,
            kafka_rules=kafka_rules,
            kafka_rule_summary=kafka_rule_summary,
            rmq_overview=rmq_overview,
            rmq_flows=rmq_flows,
            rmq_nodes=rmq_nodes,
            rmq_avg_size=rmq_avg_size,
            rmq_queue_top=rmq_queue_top,
            rmq_backlog=rmq_backlog,
            rmq_cluster_stats=rmq_cluster_stats,
            rmq_alarms=rmq_alarms,
            rmq_process_stats=rmq_process_stats,
            rmq_connection_stats=rmq_connection_stats,
            rmq_rules=rmq_rules,
            rmq_rule_summary=rmq_rule_summary,
            range_label=RABBITMQ_RANGE,
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_file = os.path.join(self.output_dir, f"mq_inspection_{timestamp}.html")
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"HTML 报告已生成: {html_file}")
        return html_file, html, alerts, summary

    def convert_to_pdf(self, html_content, html_file):
        pdf_file = html_file.replace(".html", ".pdf")
        options = {
            "page-size": "A3",
            "orientation": "Landscape",
            "margin-top": "10mm",
            "margin-right": "10mm",
            "margin-bottom": "10mm",
            "margin-left": "10mm",
            "encoding": "UTF-8",
            "enable-local-file-access": None,
            "quiet": "",
        }
        try:
            pdfkit.from_string(html_content, pdf_file, options=options)
            print(f"PDF 报告已生成: {pdf_file}")
            return pdf_file
        except Exception as e:
            print(f"PDF 生成失败: {e}")
            return None

    def upload_to_oss(self, html_file):
        """上传文件到阿里云OSS"""
        try:
            if not OSS_AVAILABLE:
                print("❌ oss2模块未安装，请执行: pip install oss2")
                return None
            
            if not OSS_ACCESS_KEY_ID or not OSS_ACCESS_KEY_SECRET or not OSS_BUCKET_NAME:
                print("❌ OSS配置不完整，请检查配置参数")
                return None

            auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
            bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_NAME)

            file_name = os.path.basename(html_file)
            month_dir = datetime.now().strftime('%Y/%m')
            if OSS_FILE_PREFIX:
                oss_key = f"{OSS_FILE_PREFIX}/{month_dir}/{file_name}"
            else:
                oss_key = f"{month_dir}/{file_name}"

            with open(html_file, 'rb') as f:
                bucket.put_object(
                    oss_key, 
                    f,
                    headers={
                        'Content-Type': 'text/html; charset=utf-8',
                        'Content-Disposition': 'inline',
                        'Cache-Control': 'no-cache'
                    }
                )

            bucket.put_object_acl(oss_key, oss2.OBJECT_ACL_PUBLIC_READ)

            oss_url = f"https://{OSS_BUCKET_NAME}.{OSS_ENDPOINT}/{oss_key}"
            print(f"✅ 文件已上传至OSS: {oss_url}")

            return oss_url

        except ImportError:
            print("❌ 未安装阿里云OSS SDK，请执行: pip install oss2")
            return None
        except Exception as e:
            print(f"❌ OSS上传失败: {str(e)}")
            return None

    def send_to_wechat(self, html_file, kafka_alerts, rabbitmq_alerts, kafka_summary, rabbitmq_summary):
        """发送HTML报告到企业微信（先上传到OSS，再发送链接）"""
        try:
            total_alerts = len(kafka_alerts) + len(rabbitmq_alerts)
            total_checks = 0
            total_normal = 0
            total_warning = 0
            total_critical = 0
            
            if kafka_summary:
                total_checks += kafka_summary.get('total_checks', 0)
                total_normal += kafka_summary.get('normal', 0)
                total_warning += kafka_summary.get('warning', 0)
                total_critical += kafka_summary.get('critical', 0)
            
            if rabbitmq_summary:
                total_checks += rabbitmq_summary.get('total_checks', 0)
                total_normal += rabbitmq_summary.get('normal', 0)
                total_warning += rabbitmq_summary.get('warning', 0)
                total_critical += rabbitmq_summary.get('critical', 0)

            oss_url = self.upload_to_oss(html_file)
            
            if not oss_url:
                print("❌ OSS上传失败，跳过企业微信发送")
                return False

            summary = f"""
## 📊 消息队列巡检报告

### 🔍 巡检摘要
- 总检查项: **{total_checks}**
- ✅ 正常: **{total_normal}**
- ⚠️ 警告: **{total_warning}**
- 🔴 严重: **{total_critical}**
- 🚨 总告警数: **{total_alerts}**

### 📈 Kafka巡检
- 告警数: {len(kafka_alerts) if kafka_alerts else 0}

### 🐰 RabbitMQ巡检
- 告警数: {len(rabbitmq_alerts) if rabbitmq_alerts else 0}

### ⏰ 巡检时间
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

### 📎 详细报告
[点击查看完整HTML报告]({oss_url})

---
💡 报告已保存至阿里云OSS
"""

            message_data = {
                "msgtype": "markdown",
                "markdown": {
                    "content": summary
                }
            }
            response = requests.post(WECHAT_WEBHOOK_URL, json=message_data, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get('errcode') == 0:
                print("✅ 企业微信消息发送成功")
                return True
            else:
                print(f"❌ 企业微信消息发送失败: {result.get('errmsg')}")
                return False

        except Exception as e:
            print(f"❌ 发送企业微信消息异常: {str(e)}")
            return False


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    kafka_results = None
    kafka_rule_results = None
    if ENABLE_KAFKA:
        k = KafkaInspector(PROMETHEUS_URL, KAFKA_JOB, KAFKA_NAME)
        kafka_results, _, _ = k.run_all_checks()
        
        kafka_filters = {"job": KAFKA_JOB, "name": KAFKA_NAME}
        kafka_rule_inspector = RuleInspector(PROMETHEUS_URL, KAFKA_INSPECTION_RULES, kafka_filters)
        kafka_rule_inspector.run_all_rules()
        kafka_rule_results = {
            'rules': kafka_rule_inspector.results,
            'alerts': kafka_rule_inspector.alerts,
            'summary': kafka_rule_inspector.summary
        }

    rabbitmq_results = None
    rabbitmq_rule_results = None
    if ENABLE_RABBITMQ:
        r = RabbitMQInspector(
            PROMETHEUS_URL,
            RABBITMQ_NAMESPACE,
            RABBITMQ_CLUSTER,
            RABBITMQ_ENDPOINT,
        )
        rabbitmq_results = r.run_all_checks()
        
        rmq_filters = {"rabbitmq_cluster": RABBITMQ_CLUSTER}
        rmq_rule_inspector = RuleInspector(PROMETHEUS_URL, RABBITMQ_INSPECTION_RULES, rmq_filters)
        rmq_rule_inspector.run_all_rules()
        rabbitmq_rule_results = {
            'rules': rmq_rule_inspector.results,
            'alerts': rmq_rule_inspector.alerts,
            'summary': rmq_rule_inspector.summary
        }

    generator = ReportGenerator(OUTPUT_DIR)
    html_file, html_content, alerts, summary = generator.generate_html(
        kafka_results, rabbitmq_results, 
        kafka_rule_results, rabbitmq_rule_results
    )
    generator.convert_to_pdf(html_content, html_file)

    kafka_alerts = kafka_rule_results['alerts'] if kafka_rule_results else []
    kafka_summary = kafka_rule_results['summary'] if kafka_rule_results else None
    rabbitmq_alerts = rabbitmq_rule_results['alerts'] if rabbitmq_rule_results else []
    rabbitmq_summary = rabbitmq_rule_results['summary'] if rabbitmq_rule_results else None

    wechat_success = generator.send_to_wechat(html_file, kafka_alerts, rabbitmq_alerts, kafka_summary, rabbitmq_summary)

    print("\n" + "=" * 60)
    print("消息队列巡检报告")
    print("=" * 60)
    print(f"HTML: {html_file}")
    print(f"企业微信: {'✅ 发送成功' if wechat_success else '❌ 发送失败'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
