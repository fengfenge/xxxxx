#!/usr/bin/env python3
# clickhouse_inspection_report.py
# ClickHouse 集群巡检报告生成器（基于 Prometheus clickhouse_exporter）

import platform
import requests
from datetime import datetime
from jinja2 import Template
import pdfkit
import os

# 阿里云OSS SDK
try:
    import oss2
    OSS_AVAILABLE = True
except ImportError:
    print("⚠️ 未安装阿里云OSS SDK，请执行: pip install oss2")
    OSS_AVAILABLE = False

# ==================== 配置 ====================
PROMETHEUS_URL = "http://192.168.13.93:31909"   # 请修改为你的 Prometheus 地址
OUTPUT_DIR = "e:/pythonProject/inspection_report"
# 可选：指定要巡检的 ClickHouse 实例（留空表示所有实例）
# 例如: ["192.168.1.1:9363", "192.168.1.2:9363"]
FILTER_INSTANCES = []   # 留空则自动发现所有实例

# ==================== 告警阈值配置 ====================
ALERT_THRESHOLDS = {
    'memory_bytes': {
        'name': '内存使用',
        'warning': 16 * 1024**3,      # 16GB
        'critical': 24 * 1024**3,     # 24GB
        'unit': 'bytes'
    },
    'tcp_conn': {
        'name': 'TCP连接数',
        'warning': 500,
        'critical': 1000,
        'unit': '个'
    },
    'http_conn': {
        'name': 'HTTP连接数',
        'warning': 100,
        'critical': 500,
        'unit': '个'
    },
    'failed_query_rate': {
        'name': '失败查询速率',
        'warning': 3,
        'critical': 10,
        'unit': '/s'
    },
    'failed_select_rate': {
        'name': '失败SELECT速率',
        'warning': 3,
        'critical': 5,
        'unit': '/s'
    },
    'failed_insert_rate': {
        'name': '失败INSERT速率',
        'warning': 3,
        'critical': 5,
        'unit': '/s'
    },
    'rejected_inserts_rate': {
        'name': '拒绝插入速率',
        'warning': 1,
        'critical': 10,
        'unit': '/s'
    },
    'part_failed_fetches_rate': {
        'name': '副本获取失败速率',
        'warning': 0.1,
        'critical': 1,
        'unit': '/s'
    },
    'data_loss_rate': {
        'name': '数据丢失速率',
        'warning': 0,
        'critical': 0,
        'unit': '/s'
    },
    'readonly_replica': {
        'name': '只读副本',
        'warning': 1,
        'critical': 1,
        'unit': ''
    },
    'zk_user_exceptions_rate': {
        'name': 'ZK用户异常速率',
        'warning': 1,
        'critical': 10,
        'unit': '/s'
    },
    'zk_hw_exceptions_rate': {
        'name': 'ZK硬件异常速率',
        'warning': 1,
        'critical': 5,
        'unit': '/s'
    }
}

# 企业微信配置
WECHAT_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=87708747-919b-460c-b357-003edb891ea7"  # 请替换为你的企业微信机器人Webhook URL

# 阿里云OSS配置
OSS_ACCESS_KEY_ID = os.environ.get("ALIYUN_ACCESS_KEY_ID", "")           # 阿里云AccessKey ID
OSS_ACCESS_KEY_SECRET = os.environ.get("ALIYUN_ACCESS_KEY_SECRET", "")   # 阿里云AccessKey Secret
OSS_ENDPOINT = "oss-cn-shenzhen.aliyuncs.com"       # OSS地域Endpoint
OSS_BUCKET_NAME = "ops-inspection-report"               # OSS Bucket名称
OSS_FILE_PREFIX = "clickhouse-inspection"                 # 文件存储前缀（可选）

# ==================== Prometheus 客户端 ====================
class PrometheusClient:
    def __init__(self, url):
        self.url = url

    def query(self, query, time=None):
        params = {'query': query}
        if time:
            params['time'] = time
        try:
            resp = requests.get(f"{self.url}/api/v1/query", params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()['data']['result']
        except Exception as e:
            print(f"查询失败: {e}")
            return []

    def query_range(self, query, start, end, step='300s'):
        params = {'query': query, 'start': start, 'end': end, 'step': step}
        try:
            resp = requests.get(f"{self.url}/api/v1/query_range", params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()['data']['result']
        except Exception as e:
            print(f"范围查询失败: {e}")
            return []

# ==================== ClickHouse 巡检器 ====================
class ClickHouseInspector:
    def __init__(self, prometheus_url, filter_instances=None):
        self.prom = PrometheusClient(prometheus_url)
        self.filter_instances = filter_instances or []
        self.results = {}
        self.alerts = []
        self.summary = {
            'total_checks': 0,
            'normal': 0,
            'warning': 0,
            'critical': 0
        }

    def _query_single_value(self, query, instance=None):
        """执行查询，返回 (instance, value) 列表"""
        full_query = query
        if instance:
            full_query = f'{query}{{instance="{instance}"}}'
        data = self.prom.query(full_query)
        items = []
        for item in data:
            inst = item['metric'].get('instance', 'unknown')
            value = float(item['value'][1])
            items.append({'instance': inst, 'value': value})
        return items

    def _query_rate(self, metric, interval='5m', instance=None):
        """查询 Counter 指标的最近平均速率"""
        if instance:
            query = f'rate({metric}{{instance="{instance}"}}[{interval}])'
        else:
            query = f'rate({metric}[{interval}])'
        data = self.prom.query(query)
        items = []
        for item in data:
            inst = item['metric'].get('instance', 'unknown')
            value = float(item['value'][1])
            items.append({'instance': inst, 'value': value})
        return items

    def _get_instances(self):
        """获取所有 ClickHouse 实例列表"""
        data = self.prom.query('ClickHouseAsyncMetrics_Uptime')
        instances = []
        for item in data:
            inst = item['metric'].get('instance', 'unknown')
            if not self.filter_instances or inst in self.filter_instances:
                instances.append(inst)
        return sorted(instances)

    def run_all_checks(self):
        print("=" * 60)
        print(f"🚀 开始 ClickHouse 巡检 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)

        instances = self._get_instances()
        if not instances:
            print("未发现任何 ClickHouse 实例，请检查 Prometheus 配置。")
            return {}, [], self.summary

        print(f"发现 {len(instances)} 个实例: {', '.join(instances)}")

        # 存储每个实例的指标
        node_data = {}
        for inst in instances:
            node_data[inst] = {}

        # 1. 基础信息 (版本、修订、表数、库数、运行时间)
        print("🔍 检查: 基础信息...")
        for metric, label in [
            ('ClickHouseMetrics_VersionInteger', 'version'),
            ('ClickHouseMetrics_Revision', 'revision'),
            ('ClickHouseAsyncMetrics_NumberOfTables', 'tables'),
            ('ClickHouseAsyncMetrics_NumberOfDatabases', 'databases'),
            ('ClickHouseAsyncMetrics_Uptime', 'uptime')
        ]:
            items = self._query_single_value(metric)
            for item in items:
                inst = item['instance']
                node_data[inst][label] = item['value']
        # 版本整数转为点分字符串 (简单处理)
        for inst in instances:
            if 'version' in node_data[inst]:
                v = int(node_data[inst]['version'])
                major = v // 1000000
                minor = (v % 1000000) // 1000
                patch = v % 1000
                node_data[inst]['version_str'] = f"{major}.{minor}.{patch}"
            else:
                node_data[inst]['version_str'] = 'unknown'

        # 2. 内存使用 (ClickHouseMetrics_MemoryTracking)
        print("🔍 检查: 内存...")
        items = self._query_single_value('ClickHouseMetrics_MemoryTracking')
        for item in items:
            node_data[item['instance']]['memory_bytes'] = item['value']

        # 3. 连接数 (TCP, HTTP)
        print("🔍 检查: 连接...")
        for metric, label in [('ClickHouseMetrics_TCPConnection', 'tcp_conn'),
                              ('ClickHouseMetrics_HTTPConnection', 'http_conn')]:
            items = self._query_single_value(metric)
            for item in items:
                node_data[item['instance']][label] = item['value']

        # 4. 查询速率 (Query, SelectQuery, InsertQuery, FailedQuery 等)
        print("🔍 检查: 查询速率...")
        rate_interval = '5m'
        rate_metrics = [
            ('ClickHouseProfileEvents_Query', 'query_rate'),
            ('ClickHouseProfileEvents_SelectQuery', 'select_rate'),
            ('ClickHouseProfileEvents_InsertQuery', 'insert_rate'),
            ('ClickHouseProfileEvents_FailedQuery', 'failed_query_rate'),
            ('ClickHouseProfileEvents_FailedSelectQuery', 'failed_select_rate'),
            ('ClickHouseProfileEvents_FailedInsertQuery', 'failed_insert_rate'),
        ]
        for metric, label in rate_metrics:
            items = self._query_rate(metric, interval=rate_interval)
            for item in items:
                node_data[item['instance']][label] = item['value']

        # 5. 插入数据量 (InsertedRows, InsertedBytes)
        print("🔍 检查: 插入数据量...")
        for metric, label in [('ClickHouseProfileEvents_InsertedRows', 'inserted_rows_rate'),
                              ('ClickHouseProfileEvents_InsertedBytes', 'inserted_bytes_rate')]:
            items = self._query_rate(metric, interval=rate_interval)
            for item in items:
                node_data[item['instance']][label] = item['value']

        # 6. 插入延迟/拒绝
        print("🔍 检查: 插入延迟/拒绝...")
        for metric, label in [('ClickHouseProfileEvents_DelayedInserts', 'delayed_inserts_rate'),
                              ('ClickHouseProfileEvents_RejectedInserts', 'rejected_inserts_rate')]:
            items = self._query_rate(metric, interval=rate_interval)
            for item in items:
                node_data[item['instance']][label] = item['value']

        # 7. 读取数据量 (SelectedRows, SelectedBytes)
        print("🔍 检查: 读取数据量...")
        for metric, label in [('ClickHouseProfileEvents_SelectedRows', 'selected_rows_rate'),
                              ('ClickHouseProfileEvents_SelectedBytes', 'selected_bytes_rate')]:
            items = self._query_rate(metric, interval=rate_interval)
            for item in items:
                node_data[item['instance']][label] = item['value']

        # 8. 文件 IO (Read, Write)
        print("🔍 检查: 文件 IO...")
        io_metrics = [
            ('ClickHouseProfileEvents_ReadBufferFromFileDescriptorReadBytes', 'fd_read_bytes_rate'),
            ('ClickHouseProfileEvents_WriteBufferFromFileDescriptorWriteBytes', 'fd_write_bytes_rate'),
            ('ClickHouseProfileEvents_ReadCompressedBytes', 'read_compressed_bytes_rate'),
            ('ClickHouseProfileEvents_CompressedReadBufferBytes', 'read_uncompressed_bytes_rate'),
        ]
        for metric, label in io_metrics:
            items = self._query_rate(metric, interval=rate_interval)
            for item in items:
                node_data[item['instance']][label] = item['value']

        # 9. 复制相关 (ReadonlyReplica, ReplicatedPartFetches, FailedFetches, Merges, DataLoss)
        print("🔍 检查: 复制状态...")
        replica_metrics = [
            ('ClickHouseMetrics_ReadonlyReplica', 'readonly_replica'),
            ('ClickHouseProfileEvents_ReplicatedPartFetches', 'part_fetches_rate'),
            ('ClickHouseProfileEvents_ReplicatedPartFailedFetches', 'part_failed_fetches_rate'),
            ('ClickHouseProfileEvents_ReplicatedPartMerges', 'part_merges_rate'),
            ('ClickHouseProfileEvents_ReplicatedDataLoss', 'data_loss_rate'),
        ]
        for metric, label in replica_metrics:
            if 'rate' in label:
                items = self._query_rate(metric, interval=rate_interval)
            else:
                items = self._query_single_value(metric)
            for item in items:
                node_data[item['instance']][label] = item['value']

        # 10. 后台任务 (BackgroundPoolTask, etc.)
        print("🔍 检查: 后台任务...")
        bg_metrics = [
            ('ClickHouseMetrics_BackgroundPoolTask', 'bg_pool_tasks'),
            ('ClickHouseMetrics_BackgroundFetchesPoolTask', 'bg_fetches_tasks'),
            ('ClickHouseMetrics_BackgroundMovePoolTask', 'bg_move_tasks'),
            ('ClickHouseMetrics_BackgroundSchedulePoolTask', 'bg_schedule_tasks'),
        ]
        for metric, label in bg_metrics:
            items = self._query_single_value(metric)
            for item in items:
                node_data[item['instance']][label] = item['value']

        # 11. ZooKeeper 相关 (Sessions, Watches, Requests, 各种操作速率)
        print("🔍 检查: ZooKeeper...")
        zk_metrics = [
            ('ClickHouseMetrics_ZooKeeperSession', 'zk_sessions'),
            ('ClickHouseMetrics_ZooKeeperWatch', 'zk_watches'),
            ('ClickHouseMetrics_ZooKeeperRequest', 'zk_requests'),
            ('ClickHouseMetrics_EphemeralNode', 'zk_ephemeral_nodes'),
        ]
        for metric, label in zk_metrics:
            items = self._query_single_value(metric)
            for item in items:
                node_data[item['instance']][label] = item['value']

        # ZK 操作速率
        zk_rate_metrics = [
            ('ClickHouseProfileEvents_ZooKeeperTransactions', 'zk_transactions_rate'),
            ('ClickHouseProfileEvents_ZooKeeperCreate', 'zk_create_rate'),
            ('ClickHouseProfileEvents_ZooKeeperRemove', 'zk_remove_rate'),
            ('ClickHouseProfileEvents_ZooKeeperGet', 'zk_get_rate'),
            ('ClickHouseProfileEvents_ZooKeeperSet', 'zk_set_rate'),
            ('ClickHouseProfileEvents_ZooKeeperMulti', 'zk_multi_rate'),
            ('ClickHouseProfileEvents_ZooKeeperCheck', 'zk_check_rate'),
            ('ClickHouseProfileEvents_ZooKeeperClose', 'zk_close_rate'),
            ('ClickHouseProfileEvents_ZooKeeperWatchResponse', 'zk_watch_response_rate'),
            ('ClickHouseProfileEvents_ZooKeeperUserExceptions', 'zk_user_exceptions_rate'),
            ('ClickHouseProfileEvents_ZooKeeperHardwareExceptions', 'zk_hw_exceptions_rate'),
            ('ClickHouseProfileEvents_ZooKeeperBytesReceived', 'zk_bytes_received_rate'),
            ('ClickHouseProfileEvents_ZooKeeperBytesSent', 'zk_bytes_sent_rate'),
        ]
        for metric, label in zk_rate_metrics:
            items = self._query_rate(metric, interval=rate_interval)
            for item in items:
                node_data[item['instance']][label] = item['value']

        # 告警检测与汇总统计
        self.summary['total_checks'] = 0
        self.summary['normal'] = 0
        self.summary['warning'] = 0
        self.summary['critical'] = 0
        self.alerts = []

        # 检查每个实例的告警指标
        for inst in instances:
            node_info = node_data.get(inst, {})
            for metric_key, threshold in ALERT_THRESHOLDS.items():
                self.summary['total_checks'] += 1
                value = node_info.get(metric_key, 0)
                check_name = threshold['name']
                unit = threshold['unit']
                
                # 判断状态
                status = 'normal'
                if value > threshold['critical']:
                    status = 'critical'
                elif value > threshold['warning']:
                    status = 'warning'
                
                # 更新统计
                if status == 'critical':
                    self.summary['critical'] += 1
                elif status == 'warning':
                    self.summary['warning'] += 1
                else:
                    self.summary['normal'] += 1
                
                # 记录告警
                if status != 'normal':
                    # 格式化值
                    if unit == 'bytes':
                        display_value = f"{value / 1024 / 1024 / 1024:.2f} GB"
                    elif unit == '/s':
                        display_value = f"{value:.2f}/s"
                    else:
                        display_value = f"{value:.2f}{unit}"
                    
                    self.alerts.append({
                        'check_name': check_name,
                        'node': inst,
                        'instance': '',
                        'value': display_value,
                        'status': status,
                        'threshold': f"警告: {threshold['warning']}, 严重: {threshold['critical']}"
                    })

        self.results['nodes'] = node_data
        self.results['instances'] = instances

        print("=" * 60)
        print(f"✅ ClickHouse 巡检完成，共检查 {len(instances)} 个节点")
        print("=" * 60)

        return self.results, self.alerts, self.summary


# ==================== 报告生成器 ====================
class ReportGenerator:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_html(self, results, alerts, summary):
        instances = results.get('instances', [])
        nodes = results.get('nodes', {})

        template = Template('''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>ClickHouse 巡检报告 - {{ date }}</title>
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
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>🔍 ClickHouse 集群巡检报告</h1>
        <div class="subtitle">生成时间: {{ date }} | 数据源: Prometheus</div>
    </div>

    <!-- 汇总卡片 -->
    <div class="summary-section">
        <div class="summary-card"><div class="number">{{ instances|length }}</div><div class="label">节点数</div></div>
        <div class="summary-card"><div class="number">{{ "%.0f"|format(total_memory / 1024 / 1024 / 1024) }} GB</div><div class="label">总内存</div></div>
        <div class="summary-card"><div class="number">{{ "%.0f"|format(total_tables) }}</div><div class="label">总表数</div></div>
        <div class="summary-card"><div class="number">{{ "%.0f"|format(total_databases) }}</div><div class="label">总库数</div></div>
    </div>

    <!-- 节点基础信息表 -->
    <div class="details-section">
        <h2>📋 节点基础信息</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>实例</th><th>版本</th><th>修订</th><th>表数</th><th>库数</th><th>运行时间(秒)</th>
                        <th>内存(GB)</th><th>TCP连接</th><th>HTTP连接</th>
                    </tr>
                </thead>
                <tbody>
                    {% for inst in instances %}
                    {% set n = nodes[inst] %}
                    <tr>
                        <td>{{ inst }}</td>
                        <td>{{ n.get('version_str', 'N/A') }}</td>
                        <td>{{ n.get('revision', 0)|int }}</td>
                        <td>{{ n.get('tables', 0)|int }}</td>
                        <td>{{ n.get('databases', 0)|int }}</td>
                        <td>{{ "%.0f"|format(n.get('uptime', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('memory_bytes', 0) / 1024 / 1024 / 1024) }}</td>
                        <td>{{ n.get('tcp_conn', 0)|int }}</td>
                        <td>{{ n.get('http_conn', 0)|int }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- 查询与性能指标表 -->
    <div class="details-section">
        <h2>⚡ 查询性能 (最近5分钟平均速率)</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>实例</th><th>总查询(/s)</th><th>SELECT(/s)</th><th>INSERT(/s)</th>
                        <th>失败查询(/s)</th><th>失败SELECT(/s)</th><th>失败INSERT(/s)</th>
                    </tr>
                </thead>
                <tbody>
                    {% for inst in instances %}
                    {% set n = nodes[inst] %}
                    <tr>
                        <td>{{ inst }}</td>
                        <td>{{ "%.2f"|format(n.get('query_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('select_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('insert_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('failed_query_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('failed_select_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('failed_insert_rate', 0)) }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- 数据插入与读取 -->
    <div class="details-section">
        <h2>📥 数据插入与读取 (速率)</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>实例</th><th>插入行数(/s)</th><th>插入字节(/s)</th><th>延迟插入(/s)</th><th>拒绝插入(/s)</th>
                        <th>读取行数(/s)</th><th>读取字节(/s)</th>
                    </tr>
                </thead>
                <tbody>
                    {% for inst in instances %}
                    {% set n = nodes[inst] %}
                    <tr>
                        <td>{{ inst }}</td>
                        <td>{{ "%.2f"|format(n.get('inserted_rows_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('inserted_bytes_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('delayed_inserts_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('rejected_inserts_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('selected_rows_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('selected_bytes_rate', 0)) }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- 文件IO -->
    <div class="details-section">
        <h2>💾 文件 IO (速率)</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>实例</th><th>FD读字节(/s)</th><th>FD写字节(/s)</th>
                        <th>压缩读字节(/s)</th><th>解压读字节(/s)</th>
                    </tr>
                </thead>
                <tbody>
                    {% for inst in instances %}
                    {% set n = nodes[inst] %}
                    <tr>
                        <td>{{ inst }}</td>
                        <td>{{ "%.2f"|format(n.get('fd_read_bytes_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('fd_write_bytes_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('read_compressed_bytes_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('read_uncompressed_bytes_rate', 0)) }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- 复制与副本状态 -->
    <div class="details-section">
        <h2>🔄 复制状态</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>实例</th><th>只读副本</th><th>部分获取速率(/s)</th><th>部分获取失败(/s)</th>
                        <th>部分合并速率(/s)</th><th>数据丢失(/s)</th>
                    </tr>
                </thead>
                <tbody>
                    {% for inst in instances %}
                    {% set n = nodes[inst] %}
                    <tr>
                        <td>{{ inst }}</td>
                        <td>{{ n.get('readonly_replica', 0)|int }}</td>
                        <td>{{ "%.2f"|format(n.get('part_fetches_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('part_failed_fetches_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('part_merges_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('data_loss_rate', 0)) }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- 后台任务 -->
    <div class="details-section">
        <h2>⚙️ 后台任务活跃数</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>实例</th><th>Processing Pool</th><th>Fetches Pool</th><th>Move Pool</th><th>Schedule Pool</th>
                    </tr>
                </thead>
                <tbody>
                    {% for inst in instances %}
                    {% set n = nodes[inst] %}
                    <tr>
                        <td>{{ inst }}</td>
                        <td>{{ n.get('bg_pool_tasks', 0)|int }}</td>
                        <td>{{ n.get('bg_fetches_tasks', 0)|int }}</td>
                        <td>{{ n.get('bg_move_tasks', 0)|int }}</td>
                        <td>{{ n.get('bg_schedule_tasks', 0)|int }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- ZooKeeper 统计 -->
    <div class="details-section">
        <h2>🦒 ZooKeeper 指标</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>实例</th><th>Sessions</th><th>Watches</th><th>Requests</th><th>Ephemeral Nodes</th>
                        <th>事务速率(/s)</th><th>创建速率(/s)</th><th>删除速率(/s)</th><th>获取速率(/s)</th><th>设置速率(/s)</th>
                    </tr>
                </thead>
                <tbody>
                    {% for inst in instances %}
                    {% set n = nodes[inst] %}
                    <tr>
                        <td>{{ inst }}</td>
                        <td>{{ n.get('zk_sessions', 0)|int }}</td>
                        <td>{{ n.get('zk_watches', 0)|int }}</td>
                        <td>{{ n.get('zk_requests', 0)|int }}</td>
                        <td>{{ n.get('zk_ephemeral_nodes', 0)|int }}</td>
                        <td>{{ "%.2f"|format(n.get('zk_transactions_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('zk_create_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('zk_remove_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('zk_get_rate', 0)) }}</td>
                        <td>{{ "%.2f"|format(n.get('zk_set_rate', 0)) }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div class="footer">
        <p>本报告由 ClickHouse 巡检系统自动生成 | 基于 Prometheus + clickhouse_exporter | {{ date }}</p>
    </div>
</div>
</body>
</html>
        ''')

        # 计算总内存、总表数等汇总信息
        total_memory = sum(nodes.get(inst, {}).get('memory_bytes', 0) for inst in instances)
        total_tables = sum(nodes.get(inst, {}).get('tables', 0) for inst in instances)
        total_databases = sum(nodes.get(inst, {}).get('databases', 0) for inst in instances)

        html = template.render(
            date=datetime.now().strftime('%Y-%m-%d %H:%M'),
            instances=instances,
            nodes=nodes,
            total_memory=total_memory,
            total_tables=total_tables,
            total_databases=total_databases
        )

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        month_dir = datetime.now().strftime('%Y/%m')
        full_output_dir = os.path.join(self.output_dir, month_dir)
        os.makedirs(full_output_dir, exist_ok=True)
        html_file = f"{full_output_dir}/clickhouse_inspection_{timestamp}.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"✅ HTML 报告已生成: {html_file}")
        return html_file, html

    def convert_to_pdf(self, html_content, html_file):
        pdf_file = html_file.replace('.html', '.pdf')
        options = {
            'page-size': 'A3',
            'orientation': 'Landscape',
            'margin-top': '10mm',
            'margin-right': '10mm',
            'margin-bottom': '10mm',
            'margin-left': '10mm',
            'encoding': 'UTF-8',
            'enable-local-file-access': None,
            'quiet': ''
        }
        try:
            pdfkit.from_string(html_content, pdf_file, options=options)
            print(f"✅ PDF 报告已生成: {pdf_file}")
            return pdf_file
        except Exception as e:
            print(f"⚠️ PDF 生成失败: {e}")
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
        except Exception as e:
            print(f"❌ OSS上传失败: {str(e)}")
            return None

    def send_to_wechat(self, html_file, alerts, summary):
        """发送HTML报告到企业微信（先上传到OSS，再发送链接）"""
        try:
            total_alerts = len(alerts)
            total_checks = summary['total_checks']
            total_normal = summary['normal']
            total_warning = summary['warning']
            total_critical = summary['critical']

            oss_url = self.upload_to_oss(html_file)
            
            if not oss_url:
                print("❌ OSS上传失败，跳过企业微信发送")
                return False

            summary_text = f"""
## 📊 ClickHouse集群巡检报告

### 🔍 巡检摘要
- 总检查项: **{total_checks}**
- ✅ 正常: **{total_normal}**
- ⚠️ 警告: **{total_warning}**
- 🔴 严重: **{total_critical}**
- 🚨 总告警数: **{total_alerts}**

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
                    "content": summary_text
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


# ==================== 主程序 ====================
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    inspector = ClickHouseInspector(PROMETHEUS_URL, FILTER_INSTANCES)
    results, alerts, summary = inspector.run_all_checks()

    if not results.get('instances'):
        print("未发现 ClickHouse 实例，退出。")
        return

    generator = ReportGenerator(OUTPUT_DIR)
    html_file, html_content = generator.generate_html(results, alerts, summary)
    pdf_file = generator.convert_to_pdf(html_content, html_file)

    # 上传到阿里云OSS并发送到企业微信
    generator.send_to_wechat(html_file, alerts, summary)

    print("\n" + "=" * 60)
    print("📋 ClickHouse 巡检报告汇总")
    print("=" * 60)
    print(f"HTML 报告: {html_file}")
    if pdf_file:
        print(f"PDF 报告:  {pdf_file}")
    print("=" * 60)


if __name__ == '__main__':
    main()
