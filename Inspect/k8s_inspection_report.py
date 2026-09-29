#!/usr/bin/env python3
# k8s_inspection_report.py
# K8S 集群巡检报告生成器（K8S + Node 双巡检）

import platform
import requests
from datetime import datetime
from jinja2 import Template
import pdfkit
import os

# ==================== 配置 ====================
PROMETHEUS_URL = "http://47.115.141.138:31243/"   # 请修改为你的 Prometheus 地址
OUTPUT_DIR = "e:/pythonProject/inspection_report"

# ==================== K8S 巡检规则 ====================
K8S_INSPECTION_RULES = {
    # 节点内存
    "k8s_node_memory_total": {
        "name": "节点内存总量",
        "query": '''
            sum(kube_node_status_allocatable{resource="memory", unit="byte"}) by (node)
        ''',
        "unit": "bytes"
    },
    "k8s_node_memory_used": {
        "name": "节点内存使用量",
        "query": '''
            sum(container_memory_working_set_bytes{container!=""}) by (node)
        ''',
        "unit": "bytes"
    },
    "k8s_node_memory_ratio": {
        "name": "节点内存使用率",
        "query": '''
            sum(container_memory_working_set_bytes{container!=""}) by (node)
            /
            sum(kube_node_status_allocatable{resource="memory", unit="byte"}) by (node)
            * 100
        ''',
        "threshold_warning": 80,
        "threshold_critical": 90,
        "unit": "%"
    },
    # 节点 CPU
    "k8s_node_cpu_total": {
        "name": "节点CPU总核数",
        "query": '''
            sum(kube_node_status_allocatable{resource="cpu", unit="core"}) by (node)
        ''',
        "unit": "核"
    },
    "k8s_node_cpu_used": {
        "name": "节点CPU使用量",
        "query": '''
            sum(irate(container_cpu_usage_seconds_total{container!=""}[2m])) by (node)
        ''',
        "unit": "核"
    },
    "k8s_node_cpu_ratio": {
        "name": "节点CPU使用率",
        "query": '''
            sum(irate(container_cpu_usage_seconds_total{container!=""}[2m])) by (node)
            /
            sum(kube_node_status_allocatable{resource="cpu", unit="core"}) by (node)
            * 100
        ''',
        "threshold_warning": 70,
        "threshold_critical": 90,
        "unit": "%"
    },
    # 节点磁盘
    "k8s_node_disk_total": {
        "name": "节点磁盘总量",
        "query": '''
            sum(container_fs_limit_bytes{device=~"^/dev/.*$", id="/"}) by (node)
        ''',
        "unit": "bytes"
    },
    "k8s_node_disk_used": {
        "name": "节点磁盘使用量",
        "query": '''
            sum(container_fs_usage_bytes{device=~"^/dev/.*$", id="/"}) by (node)
        ''',
        "unit": "bytes"
    },
    "k8s_node_disk_ratio": {
        "name": "节点磁盘使用率",
        "query": '''
            sum(container_fs_usage_bytes{device=~"^/dev/.*$", id="/"}) by (node)
            /
            sum(container_fs_limit_bytes{device=~"^/dev/.*$", id="/"}) by (node)
            * 100
        ''',
        "threshold_warning": 75,
        "threshold_critical": 90,
        "unit": "%"
    },
    # 节点 Pod
    "k8s_node_pod_count": {
        "name": "节点Pod数量",
        "query": '''
            count(kube_pod_info{created_by_kind!~"<none>|Job"}) by (node)
        ''',
        "unit": "个"
    },
    "k8s_node_pod_limit": {
        "name": "节点Pod上限",
        "query": '''
            sum(kube_node_status_allocatable{resource="pods", unit="integer"}) by (node)
        ''',
        "unit": "个"
    },
    # 节点网络带宽
    "k8s_node_network_rx": {
        "name": "节点网络接收带宽",
        "query": '''
            sum(irate(container_network_receive_bytes_total[2m])) by (node) * 8 / 1024 / 1024
        ''',
        "unit": "Mbps"
    },
    "k8s_node_network_tx": {
        "name": "节点网络发送带宽",
        "query": '''
            sum(irate(container_network_transmit_bytes_total[2m])) by (node) * 8 / 1024 / 1024
        ''',
        "unit": "Mbps"
    },
    # 容器资源统计
    "k8s_container_stats": {
        "name": "容器资源统计",
        "query": '''
            sum(irate(container_cpu_usage_seconds_total{container!="",container!="POD"}[2m])) by (container, namespace)
            /
            sum(container_spec_cpu_quota{container!="",container!="POD"}/100000) by (container, namespace)
            * 100
        ''',
        "additional_queries": {
            "cpu_used": "sum(irate(container_cpu_usage_seconds_total{container!='',container!='POD'}[2m])) by (container, namespace)",
            "cpu_request": "sum(kube_pod_container_resource_requests{resource='cpu', unit='core'}) by (container, namespace)",
            "cpu_limit": "sum(kube_pod_container_resource_limits{resource='cpu', unit='core'}) by (container, namespace)",
            "memory_used_wss": "sum(container_memory_working_set_bytes{container!='',container!='POD'}) by (container, namespace)",
            "memory_request": "sum(kube_pod_container_resource_requests{resource='memory', unit='byte'}) by (container, namespace)",
            "memory_limit": "sum(kube_pod_container_resource_limits{resource='memory', unit='byte'}) by (container, namespace)"
        },
        "unit": "%",
        "cpu_threshold_warning": 70,
        "cpu_threshold_critical": 90,
        "memory_threshold_warning": 75,
        "memory_threshold_critical": 90
    },
    # 容器网络带宽
    "k8s_container_network_stats": {
        "name": "容器网络带宽",
        "query": '''
            sum(irate(container_network_receive_bytes_total[2m])) by (pod, namespace) * 8 / 1024 / 1024
        ''',
        "additional_queries": {
            "tx": "sum(irate(container_network_transmit_bytes_total[2m])) by (pod, namespace) * 8 / 1024 / 1024",
            "container_name": "kube_pod_container_info{container!='',container!='POD'}"
        },
        "unit": "Mbps"
    }
}

# ==================== Node 巡检规则 ====================
# 基于提供的 Node Exporter Dashboard JSON 提取
NODE_INSPECTION_RULES = {
    # 主机信息
    "node_hostname": {
        "name": "主机名",
        "query": "node_uname_info - 0",
        "unit": ""
    },
    "node_instance": {
        "name": "IP",
        "query": "node_uname_info - 0",
        "unit": ""
    },
    "node_uptime": {
        "name": "启动天数",
        "query": "sum(time() - node_boot_time_seconds) by (instance) / 86400",
        "unit": "天"
    },
    # CPU
    "node_cpu_total": {
        "name": "CPU总核数",
        "query": "count(node_cpu_seconds_total{mode='system'}) by (instance)",
        "unit": "核"
    },
    "node_cpu_usage": {
        "name": "CPU使用率",
        "query": "(1 - avg(irate(node_cpu_seconds_total{mode='idle'}[2m])) by (instance)) * 100",
        "threshold_warning": 70,
        "threshold_critical": 90,
        "unit": "%"
    },
    # 内存
    "node_memory_total": {
        "name": "内存总量",
        "query": "node_memory_MemTotal_bytes",
        "unit": "bytes"
    },
    "node_memory_available": {
        "name": "内存可用量",
        "query": "node_memory_MemAvailable_bytes",
        "unit": "bytes"
    },
    "node_memory_usage": {
        "name": "内存使用率",
        "query": "(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100",
        "threshold_warning": 80,
        "threshold_critical": 90,
        "unit": "%"
    },
    # 磁盘
    "node_disk_usage": {
        "name": "磁盘使用率（最高分区）",
        "query": '''
            max((node_filesystem_size_bytes{fstype=~"ext.?|xfs"} - node_filesystem_free_bytes{fstype=~"ext.?|xfs"})
            *100/(node_filesystem_avail_bytes{fstype=~"ext.?|xfs"} + (node_filesystem_size_bytes{fstype=~"ext.?|xfs"} - node_filesystem_free_bytes{fstype=~"ext.?|xfs"}))) by (instance)
        ''',
        "threshold_warning": 75,
        "threshold_critical": 90,
        "unit": "%"
    },
    # 网络带宽
    "node_network_rx": {
        "name": "接收带宽",
        "query": "max(irate(node_network_receive_bytes_total[2m]) * 8 / 1024 / 1024) by (instance)",
        "unit": "Mbps"
    },
    "node_network_tx": {
        "name": "发送带宽",
        "query": "max(irate(node_network_transmit_bytes_total[2m]) * 8 / 1024 / 1024) by (instance)",
        "unit": "Mbps"
    },
    # 负载
    "node_load5": {
        "name": "5分钟负载",
        "query": "node_load5",
        "unit": ""
    },
    # 进程
    "node_procs_running": {
        "name": "运行进程数",
        "query": "node_procs_running",
        "unit": ""
    },
    "node_procs_blocked": {
        "name": "阻塞进程数",
        "query": "node_procs_blocked",
        "unit": ""
    },
    # 文件描述符
    "node_fd_allocated": {
        "name": "已分配文件描述符",
        "query": "node_filefd_allocated",
        "unit": ""
    },
    "node_fd_maximum": {
        "name": "最大文件描述符",
        "query": "node_filefd_maximum",
        "unit": ""
    },
    # Socket
    "node_tcp_currestab": {
        "name": "TCP连接数",
        "query": "node_netstat_Tcp_CurrEstab",
        "unit": ""
    },
    "node_tcp_tw": {
        "name": "TCP TIME_WAIT",
        "query": "node_sockstat_TCP_tw",
        "unit": ""
    }
}

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

# ==================== 通用巡检器 ====================
class GenericInspector:
    def __init__(self, prometheus_url, rules):
        self.prom = PrometheusClient(prometheus_url)
        self.rules = rules
        self.results = {}
        self.alerts = []
        self.summary = {
            'total_checks': 0,
            'normal': 0,
            'warning': 0,
            'critical': 0
        }

    def check_metric(self, rule_id, rule):
        print(f"🔍 检查: {rule['name']}...")

        data = self.prom.query(rule['query'])
        additional_data = {}
        if 'additional_queries' in rule:
            for name, q in rule['additional_queries'].items():
                additional_data[name] = self.prom.query(q)

        items = []
        for item in data:
            labels = item['metric']
            value = float(item['value'][1])

            # 基础项
            item_dict = {
                'labels': labels,
                'value': value,
                'node': labels.get('node', labels.get('container', labels.get('namespace', labels.get('instance', 'N/A')))),
                'instance': labels.get('persistentvolumeclaim', labels.get('pod', ''))
            }

            # 合并附加查询数据
            for key, adata in additional_data.items():
                for aitem in adata:
                    alabels = aitem['metric']
                    if rule_id.startswith('k8s_container') and key != 'container_name':
                        # 容器统计匹配 container 和 namespace
                        if (alabels.get('container') == labels.get('container') and
                            alabels.get('namespace') == labels.get('namespace')):
                            item_dict[key] = float(aitem['value'][1])
                            break
                    elif key == 'container_name':
                        # 容器网络关联
                        if (alabels.get('pod') == labels.get('pod') and
                            alabels.get('namespace') == labels.get('namespace')):
                            item_dict['container'] = alabels.get('container', 'unknown')
                            break
                    else:
                        # 普通匹配 instance
                        if alabels.get('instance') == labels.get('instance'):
                            item_dict[key] = float(aitem['value'][1])
                            break

            # 状态判断
            status = 'normal'
            if 'threshold_critical' in rule and value > rule['threshold_critical']:
                status = 'critical'
            elif 'threshold_warning' in rule and value > rule['threshold_warning']:
                status = 'warning'
            item_dict['status'] = status
            items.append(item_dict)

        # 统计
        check_result = {
            'name': rule['name'],
            'unit': rule.get('unit', ''),
            'threshold_warning': rule.get('threshold_warning'),
            'threshold_critical': rule.get('threshold_critical'),
            'items': items,
            'total': len(items),
            'normal_count': sum(1 for i in items if i['status'] == 'normal'),
            'warning_count': sum(1 for i in items if i['status'] == 'warning'),
            'critical_count': sum(1 for i in items if i['status'] == 'critical'),
            'has_alert': any(i['status'] != 'normal' for i in items)
        }

        self.results[rule_id] = check_result

        self.summary['total_checks'] += 1
        if check_result['critical_count'] > 0:
            self.summary['critical'] += 1
        elif check_result['warning_count'] > 0:
            self.summary['warning'] += 1
        else:
            self.summary['normal'] += 1

        for item in items:
            if item['status'] != 'normal':
                self.alerts.append({
                    'check_name': rule['name'],
                    'node': item['node'],
                    'instance': item['instance'],
                    'value': f"{item['value']:.2f}{rule.get('unit', '')}",
                    'status': item['status'],
                    'threshold': rule.get(f"threshold_{item['status']}", 'N/A')
                })

        return check_result

    def run_all_checks(self, prefix=""):
        print("=" * 60)
        print(f"🚀 开始 {prefix}巡检 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)

        for rule_id, rule in self.rules.items():
            self.check_metric(rule_id, rule)

        print("=" * 60)
        print(f"✅ {prefix}巡检完成: 总计{self.summary['total_checks']}项 | "
              f"正常{self.summary['normal']} | "
              f"警告{self.summary['warning']} | "
              f"严重{self.summary['critical']}")
        print("=" * 60)

        return self.results, self.alerts, self.summary

# ==================== 报告生成器 ====================
class ReportGenerator:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_html(self, k8s_results, k8s_alerts, k8s_summary,
                      node_results, node_alerts, node_summary):
        """生成综合 HTML 报告"""
        # 处理 K8S 节点数据
        k8s_node_data = {}
        for rule_id, check in k8s_results.items():
            if rule_id.startswith('k8s_node_') and rule_id not in ['k8s_node_network_rx', 'k8s_node_network_tx']:
                for item in check['items']:
                    node = item['node']
                    if node not in k8s_node_data:
                        k8s_node_data[node] = {}
                    # 填充字段
                    if 'memory_total' in rule_id:
                        k8s_node_data[node]['memory_total'] = item['value']
                    elif 'memory_used' in rule_id:
                        k8s_node_data[node]['memory_used'] = item['value']
                    elif 'memory_ratio' in rule_id:
                        k8s_node_data[node]['memory_ratio'] = item['value']
                        k8s_node_data[node]['memory_status'] = item['status']
                    elif 'cpu_total' in rule_id:
                        k8s_node_data[node]['cpu_total'] = item['value']
                    elif 'cpu_used' in rule_id:
                        k8s_node_data[node]['cpu_used'] = item['value']
                    elif 'cpu_ratio' in rule_id:
                        k8s_node_data[node]['cpu_ratio'] = item['value']
                        k8s_node_data[node]['cpu_status'] = item['status']
                    elif 'disk_total' in rule_id:
                        k8s_node_data[node]['disk_total'] = item['value']
                    elif 'disk_used' in rule_id:
                        k8s_node_data[node]['disk_used'] = item['value']
                    elif 'disk_ratio' in rule_id:
                        k8s_node_data[node]['disk_ratio'] = item['value']
                        k8s_node_data[node]['disk_status'] = item['status']
                    elif 'pod_count' in rule_id and 'limit' not in rule_id:
                        k8s_node_data[node]['pod_count'] = item['value']
                    elif 'pod_limit' in rule_id:
                        k8s_node_data[node]['pod_limit'] = item['value']

        # 节点网络
        k8s_node_network = {}
        if 'k8s_node_network_rx' in k8s_results:
            for item in k8s_results['k8s_node_network_rx']['items']:
                node = item['node']
                k8s_node_network.setdefault(node, {})['rx'] = item['value']
        if 'k8s_node_network_tx' in k8s_results:
            for item in k8s_results['k8s_node_network_tx']['items']:
                node = item['node']
                k8s_node_network.setdefault(node, {})['tx'] = item['value']

        k8s_nodes = []
        for node, data in k8s_node_data.items():
            k8s_nodes.append({
                'name': node,
                'memory_total': data.get('memory_total', 0),
                'memory_used': data.get('memory_used', 0),
                'memory_ratio': data.get('memory_ratio', 0),
                'memory_status': data.get('memory_status', 'normal'),
                'cpu_total': data.get('cpu_total', 0),
                'cpu_used': data.get('cpu_used', 0),
                'cpu_ratio': data.get('cpu_ratio', 0),
                'cpu_status': data.get('cpu_status', 'normal'),
                'disk_total': data.get('disk_total', 0),
                'disk_used': data.get('disk_used', 0),
                'disk_ratio': data.get('disk_ratio', 0),
                'disk_status': data.get('disk_status', 'normal'),
                'pod_count': data.get('pod_count', 0),
                'pod_limit': data.get('pod_limit', 1),
                'network_rx': k8s_node_network.get(node, {}).get('rx', 0),
                'network_tx': k8s_node_network.get(node, {}).get('tx', 0)
            })

        # 容器数据
        containers_by_namespace = {}
        if 'k8s_container_stats' in k8s_results:
            for item in k8s_results['k8s_container_stats']['items']:
                ns = item['labels'].get('namespace', 'unknown')
                if ns not in containers_by_namespace:
                    containers_by_namespace[ns] = []
                cpu_ratio = item['value']
                memory_used_wss = item.get('memory_used_wss', 0)
                memory_limit = item.get('memory_limit', 1)
                memory_ratio = (memory_used_wss / memory_limit * 100) if memory_limit > 0 else 0

                status = 'normal'
                cpu_warning = K8S_INSPECTION_RULES['k8s_container_stats'].get('cpu_threshold_warning', 70)
                cpu_critical = K8S_INSPECTION_RULES['k8s_container_stats'].get('cpu_threshold_critical', 90)
                mem_warning = K8S_INSPECTION_RULES['k8s_container_stats'].get('memory_threshold_warning', 75)
                mem_critical = K8S_INSPECTION_RULES['k8s_container_stats'].get('memory_threshold_critical', 90)
                if cpu_ratio > cpu_critical or memory_ratio > mem_critical:
                    status = 'critical'
                elif cpu_ratio > cpu_warning or memory_ratio > mem_warning:
                    status = 'warning'

                container_info = {
                    'name': item['labels'].get('container', 'unknown'),
                    'cpu_ratio': cpu_ratio,
                    'cpu_used': item.get('cpu_used', 0),
                    'cpu_request': item.get('cpu_request', 0),
                    'cpu_limit': item.get('cpu_limit', 0),
                    'memory_ratio': memory_ratio,
                    'memory_used_wss': memory_used_wss,
                    'memory_request': item.get('memory_request', 0),
                    'memory_limit': memory_limit,
                    'status': status
                }
                containers_by_namespace[ns].append(container_info)

        # 容器网络关联
        container_network = {}
        if 'k8s_container_network_stats' in k8s_results:
            for item in k8s_results['k8s_container_network_stats']['items']:
                container_name = item.get('container', 'unknown')
                ns = item['labels'].get('namespace', 'unknown')
                key = f"{ns}|{container_name}"
                container_network[key] = {
                    'rx': item['value'],
                    'tx': item.get('tx', 0),
                    'namespace': ns,
                    'container': container_name
                }
        for ns, containers in containers_by_namespace.items():
            for c in containers:
                key = f"{ns}|{c['name']}"
                net = container_network.get(key, {})
                c['network_rx'] = net.get('rx', 0)
                c['network_tx'] = net.get('tx', 0)

        # 处理 Node 数据
        node_instances = {}
        for rule_id, check in node_results.items():
            for item in check['items']:
                instance = item['node']  # instance 作为节点标识
                if instance not in node_instances:
                    node_instances[instance] = {}
                # 根据规则名填充
                if 'hostname' in rule_id:
                    node_instances[instance]['hostname'] = item['labels'].get('nodename', instance)
                elif 'instance' in rule_id:
                    node_instances[instance]['ip'] = instance
                elif 'uptime' in rule_id:
                    node_instances[instance]['uptime'] = item['value']
                elif 'cpu_total' in rule_id:
                    node_instances[instance]['cpu_total'] = item['value']
                elif 'cpu_usage' in rule_id:
                    node_instances[instance]['cpu_usage'] = item['value']
                    node_instances[instance]['cpu_status'] = item['status']
                elif 'memory_total' in rule_id:
                    node_instances[instance]['memory_total'] = item['value']
                elif 'memory_available' in rule_id:
                    node_instances[instance]['memory_available'] = item['value']
                elif 'memory_usage' in rule_id:
                    node_instances[instance]['memory_usage'] = item['value']
                    node_instances[instance]['memory_status'] = item['status']
                elif 'disk_usage' in rule_id:
                    node_instances[instance]['disk_usage'] = item['value']
                    node_instances[instance]['disk_status'] = item['status']
                elif 'network_rx' in rule_id:
                    node_instances[instance]['network_rx'] = item['value']
                elif 'network_tx' in rule_id:
                    node_instances[instance]['network_tx'] = item['value']
                elif 'load5' in rule_id:
                    node_instances[instance]['load5'] = item['value']
                elif 'procs_running' in rule_id:
                    node_instances[instance]['procs_running'] = item['value']
                elif 'procs_blocked' in rule_id:
                    node_instances[instance]['procs_blocked'] = item['value']
                elif 'fd_allocated' in rule_id:
                    node_instances[instance]['fd_allocated'] = item['value']
                elif 'fd_maximum' in rule_id:
                    node_instances[instance]['fd_maximum'] = item['value']
                elif 'tcp_currestab' in rule_id:
                    node_instances[instance]['tcp_currestab'] = item['value']
                elif 'tcp_tw' in rule_id:
                    node_instances[instance]['tcp_tw'] = item['value']

        # 填充默认值
        node_list = []
        for instance, data in node_instances.items():
            node_list.append({
                'hostname': data.get('hostname', instance),
                'ip': data.get('ip', instance),
                'uptime': data.get('uptime', 0),
                'cpu_total': data.get('cpu_total', 0),
                'cpu_usage': data.get('cpu_usage', 0),
                'cpu_status': data.get('cpu_status', 'normal'),
                'memory_total': data.get('memory_total', 0),
                'memory_available': data.get('memory_available', 0),
                'memory_usage': data.get('memory_usage', 0),
                'memory_status': data.get('memory_status', 'normal'),
                'disk_usage': data.get('disk_usage', 0),
                'disk_status': data.get('disk_status', 'normal'),
                'network_rx': data.get('network_rx', 0),
                'network_tx': data.get('network_tx', 0),
                'load5': data.get('load5', 0),
                'procs_running': data.get('procs_running', 0),
                'procs_blocked': data.get('procs_blocked', 0),
                'fd_allocated': data.get('fd_allocated', 0),
                'fd_maximum': data.get('fd_maximum', 1),
                'tcp_currestab': data.get('tcp_currestab', 0),
                'tcp_tw': data.get('tcp_tw', 0)
            })

        # 合并告警
        all_alerts = k8s_alerts + node_alerts

        # 生成 HTML
        template = Template('''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>K8S+Node 综合巡检报告 - {{ date }}</title>
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
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
        }
        .summary-card {
            background: white;
            border-radius: 12px;
            padding: 25px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            transition: transform 0.3s;
        }
        .summary-card:hover { transform: translateY(-5px); }
        .summary-card .number { font-size: 42px; font-weight: bold; margin-bottom: 8px; }
        .summary-card .label { color: #6c757d; font-size: 14px; }
        .summary-card.total .number { color: #667eea; }
        .summary-card.normal .number { color: #28a745; }
        .summary-card.warning .number { color: #ffc107; }
        .summary-card.critical .number { color: #dc3545; }

        .alerts-section {
            padding: 30px;
            background: #fff5f5;
            border-left: 5px solid #dc3545;
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
        .badge { padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; text-transform: uppercase; }
        .badge-warning { background: #ffc107; color: #212529; }
        .badge-critical { background: #dc3545; color: white; }

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
        .status-dot {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 5px;
        }
        .status-normal { background: #28a745; }
        .status-warning { background: #ffc107; }
        .status-critical { background: #dc3545; }
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
        <h1>🔍 K8S + Node 综合巡检报告</h1>
        <div class="subtitle">生成时间: {{ date }} | 巡检周期: {{ time_range }} | 数据源: Prometheus</div>
    </div>

    <!-- 汇总卡片 -->
    <div class="summary-section">
        <div class="summary-card total"><div class="number">{{ k8s_summary.total_checks + node_summary.total_checks }}</div><div class="label">巡检项目</div></div>
        <div class="summary-card normal"><div class="number">{{ k8s_summary.normal + node_summary.normal }}</div><div class="label">正常</div></div>
        <div class="summary-card warning"><div class="number">{{ k8s_summary.warning + node_summary.warning }}</div><div class="label">警告</div></div>
        <div class="summary-card critical"><div class="number">{{ k8s_summary.critical + node_summary.critical }}</div><div class="label">严重</div></div>
    </div>

    <!-- 告警区域 -->
    {% if alerts %}
    <div class="alerts-section">
        <h2>⚠️ 告警详情 (共 {{ alerts|length }} 条)</h2>
        <table class="alert-table">
            <thead><tr><th>检查项</th><th>节点/实例</th><th>当前值</th><th>状态</th>?</thead>
            <tbody>
                {% for alert in alerts %}
                <tr>
                    <td>{{ alert.check_name }}</td>
                    <td>{{ alert.node }}{% if alert.instance %} / {{ alert.instance }}{% endif %}</td>
                    <td><strong>{{ alert.value }}</strong></td>
                    <td><span class="badge badge-{{ alert.status }}">{{ '警告' if alert.status == 'warning' else '严重' }}</span></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    <!-- K8S 节点资源表格 -->
    <div class="details-section">
        <h2>📊 K8S 节点资源详情</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>节点名称</th>
                        <th>内存总量(GB)</th><th>内存使用量(GB)</th><th>内存使用率(%)</th>
                        <th>CPU总量(核)</th><th>CPU使用量(核)</th><th>CPU使用率(%)</th>
                        <th>磁盘总量(GB)</th><th>磁盘使用量(GB)</th><th>磁盘使用率(%)</th>
                        <th>Pod数量</th><th>Pod上限</th>
                    </tr>
                </thead>
                <tbody>
                    {% for node in k8s_nodes %}
                    <tr>
                        <td>{{ node.name }}</td>
                        <td>{{ "%.2f"|format(node.memory_total / 1024 / 1024 / 1024) }}</td>
                        <td>{{ "%.2f"|format(node.memory_used / 1024 / 1024 / 1024) }}</td>
                        <td>{{ "%.2f"|format(node.memory_ratio) }} <span class="status-dot status-{{ node.memory_status }}"></span></td>
                        <td>{{ "%.2f"|format(node.cpu_total) }}</td>
                        <td>{{ "%.2f"|format(node.cpu_used) }}</td>
                        <td>{{ "%.2f"|format(node.cpu_ratio) }} <span class="status-dot status-{{ node.cpu_status }}"></span></td>
                        <td>{{ "%.2f"|format(node.disk_total / 1024 / 1024 / 1024) }}</td>
                        <td>{{ "%.2f"|format(node.disk_used / 1024 / 1024 / 1024) }}</td>
                        <td>{{ "%.2f"|format(node.disk_ratio) }} <span class="status-dot status-{{ node.disk_status }}"></span></td>
                        <td>{{ node.pod_count|int }}</td>
                        <td>{{ node.pod_limit|int }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- K8S 节点网络带宽 -->
    <div class="details-section">
        <h2>🌐 K8S 节点网络带宽</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr><th>节点名称</th><th>接收带宽 (Mbps)</th><th>发送带宽 (Mbps)</th></tr></thead>
                <tbody>
                    {% for node in k8s_nodes %}
                    <tr>
                        <td>{{ node.name }}</td>
                        <td>{{ "%.2f"|format(node.network_rx) }}</td>
                        <td>{{ "%.2f"|format(node.network_tx) }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- K8S 容器资源统计（按名称空间分组） -->
    <div class="details-section">
        <h2>📊 K8S 容器资源统计</h2>
        {% if containers_by_namespace %}
            {% for namespace, containers in containers_by_namespace.items() %}
            <h3 style="margin-top: 20px;">名称空间: {{ namespace }}</h3>
            <div class="table-wrapper">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>容器名称</th>
                            <th>CPU使用率(%)</th><th>CPU使用量(核)</th><th>CPU请求(核)</th><th>CPU限制(核)</th>
                            <th>内存使用率(%)</th><th>内存使用量(GB)</th><th>内存请求(GB)</th><th>内存限制(GB)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for c in containers %}
                        <tr>
                            <td>{{ c.name }}</td>
                            <td>{{ "%.2f"|format(c.cpu_ratio) }} <span class="status-dot status-{{ c.status }}"></span></td>
                            <td>{{ "%.3f"|format(c.cpu_used) }}</td>
                            <td>{{ "%.3f"|format(c.cpu_request) }}</td>
                            <td>{{ "%.3f"|format(c.cpu_limit) }}</td>
                            <td>{{ "%.2f"|format(c.memory_ratio) }} <span class="status-dot status-{{ c.status }}"></span></td>
                            <td>{{ "%.2f"|format(c.memory_used_wss / 1024 / 1024 / 1024) }}</td>
                            <td>{{ "%.2f"|format(c.memory_request / 1024 / 1024 / 1024) }}</td>
                            <td>{{ "%.2f"|format(c.memory_limit / 1024 / 1024 / 1024) }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% endfor %}
        {% else %}
        <p>无容器统计数据</p>
        {% endif %}
    </div>

    <!-- K8S 容器网络带宽 -->
    <div class="details-section">
        <h2>🌐 K8S 容器网络带宽</h2>
        {% if containers_by_namespace %}
            {% for namespace, containers in containers_by_namespace.items() %}
            <h3 style="margin-top: 20px;">名称空间: {{ namespace }}</h3>
            <div class="table-wrapper">
                <table class="data-table">
                    <thead><tr><th>容器名称</th><th>接收带宽 (Mbps)</th><th>发送带宽 (Mbps)</th></tr></thead>
                    <tbody>
                        {% for c in containers %}
                        <tr>
                            <td>{{ c.name }}</td>
                            <td>{{ "%.2f"|format(c.network_rx) }}</td>
                            <td>{{ "%.2f"|format(c.network_tx) }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% endfor %}
        {% else %}
        <p>无容器网络数据</p>
        {% endif %}
    </div>

    <!-- Node 主机基础资源 -->
    <div class="details-section">
        <h2>🖥️ Node 主机基础资源</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>主机名</th><th>IP</th><th>启动天数</th>
                        <th>CPU总核数</th><th>CPU使用率(%)</th>
                        <th>内存总量(GB)</th><th>内存可用(GB)</th><th>内存使用率(%)</th>
                        <th>磁盘使用率(%)</th>
                     </tr>
                </thead>
                <tbody>
                    {% for node in node_list %}
                    <tr>
                        <td>{{ node.hostname }}</td>
                        <td>{{ node.ip }}</td>
                        <td>{{ "%.1f"|format(node.uptime) }}</td>
                        <td>{{ node.cpu_total|int }}</td>
                        <td>{{ "%.2f"|format(node.cpu_usage) }} <span class="status-dot status-{{ node.cpu_status }}"></span></td>
                        <td>{{ "%.2f"|format(node.memory_total / 1024 / 1024 / 1024) }}</td>
                        <td>{{ "%.2f"|format(node.memory_available / 1024 / 1024 / 1024) }}</td>
                        <td>{{ "%.2f"|format(node.memory_usage) }} <span class="status-dot status-{{ node.memory_status }}"></span></td>
                        <td>{{ "%.2f"|format(node.disk_usage) }} <span class="status-dot status-{{ node.disk_status }}"></span></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- Node 主机扩展指标 -->
    <div class="details-section">
        <h2>🌐 Node 主机扩展指标（网络/负载/进程/文件描述符/TCP）</h2>
        <div class="table-wrapper">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>主机名</th><th>IP</th>
                        <th>接收带宽(Mbps)</th><th>发送带宽(Mbps)</th>
                        <th>5分钟负载</th><th>运行进程</th><th>阻塞进程</th>
                        <th>FD已分配</th><th>FD最大</th>
                        <th>TCP连接数</th><th>TCP TIME_WAIT</th>
                     </tr>
                </thead>
                <tbody>
                    {% for node in node_list %}
                    <tr>
                        <td>{{ node.hostname }}</td>
                        <td>{{ node.ip }}</td>
                        <td>{{ "%.2f"|format(node.network_rx) }}</td>
                        <td>{{ "%.2f"|format(node.network_tx) }}</td>
                        <td>{{ "%.2f"|format(node.load5) }}</td>
                        <td>{{ node.procs_running|int }}</td>
                        <td>{{ node.procs_blocked|int }}</td>
                        <td>{{ node.fd_allocated|int }}</td>
                        <td>{{ node.fd_maximum|int }}</td>
                        <td>{{ node.tcp_currestab|int }}</td>
                        <td>{{ node.tcp_tw|int }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div class="footer">
        <p>本报告由 K8S+Node 巡检系统自动生成 | 基于 Prometheus 数据 | {{ date }}</p>
    </div>
</div>
</body>
</html>
        ''')

        html = template.render(
            date=datetime.now().strftime('%Y-%m-%d %H:%M'),
            time_range="最近24小时",
            platform=f"{platform.system()} {platform.release()}",
            alerts=all_alerts,
            k8s_summary=k8s_summary,
            node_summary=node_summary,
            k8s_nodes=k8s_nodes,
            containers_by_namespace=containers_by_namespace,
            node_list=node_list
        )

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        html_file = f"{self.output_dir}/k8s_node_inspection_{timestamp}.html"
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

# ==================== 主程序 ====================
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. K8S 巡检
    k8s_inspector = GenericInspector(PROMETHEUS_URL, K8S_INSPECTION_RULES)
    k8s_results, k8s_alerts, k8s_summary = k8s_inspector.run_all_checks(prefix="K8S")

    # 2. Node 巡检
    node_inspector = GenericInspector(PROMETHEUS_URL, NODE_INSPECTION_RULES)
    node_results, node_alerts, node_summary = node_inspector.run_all_checks(prefix="Node")

    # 3. 生成报告
    generator = ReportGenerator(OUTPUT_DIR)
    html_file, html_content = generator.generate_html(
        k8s_results, k8s_alerts, k8s_summary,
        node_results, node_alerts, node_summary
    )
    pdf_file = generator.convert_to_pdf(html_content, html_file)

    print("\n" + "=" * 60)
    print("📋 综合巡检报告汇总")
    print("=" * 60)
    print(f"HTML 报告: {html_file}")
    if pdf_file:
        print(f"PDF 报告:  {pdf_file}")
    print(f"K8S 告警:  {len(k8s_alerts)} 条")
    print(f"Node 告警: {len(node_alerts)} 条")
    print("=" * 60)

if __name__ == '__main__':
    main()
