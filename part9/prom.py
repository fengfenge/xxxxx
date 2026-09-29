#!/usr/bin/env python3
# k8s_inspection_report.py
# 基于 Grafana Dashboard JSON 提取的巡检报告生成器
import platform

import requests
import json
from datetime import datetime, timedelta
from jinja2 import Template
import pdfkit
import os

# ==================== 配置 ====================
PROMETHEUS_URL = "http://192.168.13.93:31999"  # 你的 Prometheus 地址
OUTPUT_DIR = "/opt/reports"
DASHBOARD_TITLE = "K8S Dashboard"

# 从 Dashboard JSON 提取的巡检规则
INSPECTION_RULES = {
    # 节点资源类
    "node_memory_ratio": {
        "name": "节点内存使用率",
        "query": '''
            sum(container_memory_working_set_bytes{container!=""}) by (node) 
            / 
            sum(kube_node_status_allocatable{resource="memory", unit="byte"}) by (node) * 100
        ''',
        "threshold_warning": 80,
        "threshold_critical": 90,
        "unit": "%",
        "panel_id": 44
    },
    "node_cpu_ratio": {
        "name": "节点CPU使用率",
        "query": '''
            sum(irate(container_cpu_usage_seconds_total{container!=""}[2m])) by (node) 
            / 
            sum(kube_node_status_allocatable{resource="cpu", unit="core"}) by (node) * 100
        ''',
        "threshold_warning": 70,
        "threshold_critical": 90,
        "unit": "%",
        "panel_id": 45
    },
    "node_pod_count": {
        "name": "节点Pod数量",
        "query": '''
            count(kube_pod_info{created_by_kind!~"<none>|Job"}) by (node)
        ''',
        "threshold_warning": 1000,
        "threshold_critical": 2000,
        "unit": "个",
        "panel_id": 74
    },
    "node_memory_usage": {
        "name": "节点内存用量",
        "query": '''
            sum(container_memory_working_set_bytes{container!=""}) by (node) / 1024 / 1024 / 1024
        ''',
        "unit": "GB",
        "panel_id": 71
    },
    "node_cpu_cores": {
        "name": "节点CPU核数",
        "query": '''
            sum(kube_node_status_allocatable{resource="cpu", unit="core"}) by (node)
        ''',
        "unit": "核",
        "panel_id": 72
    },

    # 命名空间资源类
    "namespace_cpu_usage": {
        "name": "命名空间CPU使用",
        "query": '''
            sum(irate(container_cpu_usage_seconds_total{container!="",container!="POD"}[2m])) by (namespace)
        ''',
        "threshold_warning": 0.5,
        "threshold_critical": 2.0,
        "unit": "核",
        "panel_id": 86,
        "filter": "> 0.5"
    },
    "namespace_memory_usage": {
        "name": "命名空间内存使用",
        "query": '''
            sum(container_memory_working_set_bytes{container!="",container!="POD"}) by (namespace) / 1024 / 1024 / 1024
        ''',
        "threshold_warning": 1024,  # 1GB
        "threshold_critical": 4096,  # 4GB
        "unit": "GB",
        "panel_id": 85,
        "filter": "> 1G"
    },

    # PVC存储类
    "pvc_usage": {
        "name": "PVC存储使用率",
        "query": '''
            max(kubelet_volume_stats_used_bytes) by (namespace, persistentvolumeclaim) 
            / 
            (max(kubelet_volume_stats_available_bytes) by (namespace, persistentvolumeclaim) 
            + max(kubelet_volume_stats_used_bytes) by (namespace, persistentvolumeclaim)) * 100
        ''',
        "threshold_warning": 75,
        "threshold_critical": 90,
        "unit": "%",
        "panel_id": 92
    },

    # Pod健康类
    "pod_restart_count": {
        "name": "Pod重启次数",
        "query": '''
            kube_pod_container_status_restarts_total
        ''',
        "threshold_warning": 1,
        "threshold_critical": 3,
        "unit": "次",
        "panel_id": 47
    },

    # 网络类
    "network_receive": {
        "name": "网络接收带宽",
        "query": '''
            sum(irate(container_network_receive_bytes_total[2m])) by (node) * 8 / 1024 / 1024
        ''',
        "unit": "Mbps",
        "panel_id": 32
    },
    "network_transmit": {
        "name": "网络发送带宽",
        "query": '''
            sum(irate(container_network_transmit_bytes_total[2m])) by (node) * 8 / 1024 / 1024
        ''',
        "unit": "Mbps",
        "panel_id": 32
    }
}


# ==================== 核心类 ====================

class PrometheusClient:
    """Prometheus 查询客户端"""

    def __init__(self, url):
        self.url = url

    def query(self, query, time=None):
        """瞬时查询"""
        params = {'query': query}
        if time:
            params['time'] = time
        try:
            resp = requests.get(f"{self.url}/api/v1/query", params=params, timeout=30)
            return resp.json()['data']['result']
        except Exception as e:
            print(f"查询失败: {e}")
            return []

    def query_range(self, query, start, end, step='300s'):
        """范围查询"""
        params = {
            'query': query,
            'start': start,
            'end': end,
            'step': step
        }
        try:
            resp = requests.get(f"{self.url}/api/v1/query_range", params=params, timeout=30)
            return resp.json()['data']['result']
        except Exception as e:
            print(f"范围查询失败: {e}")
            return []


class K8SInspector:
    """K8S 巡检器"""

    def __init__(self, prometheus_url):
        self.prom = PrometheusClient(prometheus_url)
        self.results = {}
        self.alerts = []
        self.summary = {
            'total_checks': 0,
            'normal': 0,
            'warning': 0,
            'critical': 0
        }

    def check_metric(self, rule_id, rule):
        """执行单项巡检"""
        print(f"🔍 检查: {rule['name']}...")

        # 执行查询
        data = self.prom.query(rule['query'])

        items = []
        for item in data:
            labels = item['metric']
            value = float(item['value'][1])

            # 判断状态
            status = 'normal'
            if 'threshold_critical' in rule and value > rule['threshold_critical']:
                status = 'critical'
            elif 'threshold_warning' in rule and value > rule['threshold_warning']:
                status = 'warning'

            items.append({
                'labels': labels,
                'value': value,
                'status': status,
                'node': labels.get('node', labels.get('namespace', 'N/A')),
                'instance': labels.get('persistentvolumeclaim', labels.get('pod', ''))
            })

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

        # 更新汇总
        self.summary['total_checks'] += 1
        if check_result['critical_count'] > 0:
            self.summary['critical'] += 1
        elif check_result['warning_count'] > 0:
            self.summary['warning'] += 1
        else:
            self.summary['normal'] += 1

        # 记录告警
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

    def run_all_checks(self):
        """执行全部巡检"""
        print("=" * 60)
        print(f"🚀 开始 K8S 集群巡检 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)

        for rule_id, rule in INSPECTION_RULES.items():
            self.check_metric(rule_id, rule)

        print("=" * 60)
        print(f"✅ 巡检完成: 总计{self.summary['total_checks']}项 | "
              f"正常{self.summary['normal']} | "
              f"警告{self.summary['warning']} | "
              f"严重{self.summary['critical']}")
        print("=" * 60)

        return self.results, self.alerts, self.summary


class ReportGenerator:
    """报告生成器"""

    def __init__(self, output_dir):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_html(self, results, alerts, summary):
        """生成 HTML 报告（带数据清洗）"""
        # ========== 1. 基础类型检查 ==========
        if not isinstance(results, dict):
            print(f"❌ 警告: results 类型为 {type(results)}，重置为空字典")
            results = {}
        if not isinstance(alerts, list):
            print(f"❌ 警告: alerts 类型为 {type(alerts)}，重置为空列表")
            alerts = []
        if not isinstance(summary, dict):
            print(f"❌ 警告: summary 类型为 {type(summary)}，重置为默认值")
            summary = {'total_checks': 0, 'normal': 0, 'warning': 0, 'critical': 0}

        # ========== 2. 清洗 results 字典中的每个检查项 ==========
        for check_id, check in list(results.items()):  # 使用 list 避免迭代时修改
            if not isinstance(check, dict):
                print(f"❌ 警告: 检查项 {check_id} 不是字典，已移除")
                del results[check_id]
                continue

            # 确保 items 是列表
            if 'items' not in check or not isinstance(check['items'], list):
                print(f"⚠️ 警告: 检查项 {check_id} 的 items 不是列表，重置为空列表")
                check['items'] = []

            # 确保必要字段存在
            check.setdefault('name', check_id)
            check.setdefault('unit', '')
            check.setdefault('threshold_warning', None)
            check.setdefault('threshold_critical', None)
            check.setdefault('normal_count', 0)
            check.setdefault('warning_count', 0)
            check.setdefault('critical_count', 0)

            # 清洗 items 列表中的每个元素
            for i, item in enumerate(check['items']):
                if not isinstance(item, dict):
                    print(f"⚠️ 警告: {check_id} 的 items[{i}] 不是字典，已跳过")
                    continue
                # 确保每个 item 有必要的字段
                item.setdefault('node', 'N/A')
                item.setdefault('instance', '')
                item.setdefault('value', 0.0)
                item.setdefault('status', 'normal')
                # 确保 value 是数值
                if not isinstance(item['value'], (int, float)):
                    try:
                        item['value'] = float(item['value'])
                    except:
                        item['value'] = 0.0

        # ========== 3. 清洗 alerts 列表 ==========
        for i, alert in enumerate(alerts):
            if not isinstance(alert, dict):
                print(f"⚠️ 警告: alerts[{i}] 不是字典，替换为空字典")
                alerts[i] = {}
                alert = alerts[i]
            alert.setdefault('check_name', '未知')
            alert.setdefault('node', 'N/A')
            alert.setdefault('instance', '')
            alert.setdefault('value', '0')
            alert.setdefault('status', 'warning')
            alert.setdefault('threshold', 'N/A')

        # ========== 4. 清洗 summary 字典 ==========
        summary.setdefault('total_checks', 0)
        summary.setdefault('normal', 0)
        summary.setdefault('warning', 0)
        summary.setdefault('critical', 0)

        # ========== 5. 可选：打印部分数据以便调试 ==========
        print(f"🔍 数据清洗完成，results 包含 {len(results)} 项，alerts 包含 {len(alerts)} 项")
        if results:
            first_key = next(iter(results))
            first_check = results[first_key]
            print(f"   示例: {first_key} -> items 数量: {len(first_check.get('items', []))}")

        template = Template('''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>K8S 集群巡检报告 - {{ date }}</title>
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

        /* 汇总卡片 */
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
        .summary-card .number {
            font-size: 42px;
            font-weight: bold;
            margin-bottom: 8px;
        }
        .summary-card .label { color: #6c757d; font-size: 14px; }
        .summary-card.total .number { color: #667eea; }
        .summary-card.normal .number { color: #28a745; }
        .summary-card.warning .number { color: #ffc107; }
        .summary-card.critical .number { color: #dc3545; }

        /* 告警区域 */
        .alerts-section {
            padding: 30px;
            background: #fff5f5;
            border-left: 5px solid #dc3545;
        }
        .alerts-section h2 {
            color: #dc3545;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .alert-table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .alert-table th {
            background: #dc3545;
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }
        .alert-table td {
            padding: 12px 15px;
            border-bottom: 1px solid #e9ecef;
        }
        .alert-table tr:hover { background: #f8f9fa; }
        .badge {
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }
        .badge-warning { background: #ffc107; color: #212529; }
        .badge-critical { background: #dc3545; color: white; }

        /* 详细检查区域 */
        .details-section {
            padding: 30px;
        }
        .details-section h2 {
            margin-bottom: 20px;
            color: #2c3e50;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }
        .check-card {
            background: white;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            overflow: hidden;
        }
        .check-header {
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-left: 5px solid #28a745;
        }
        .check-header.warning { border-left-color: #ffc107; }
        .check-header.critical { border-left-color: #dc3545; }
        .check-title { font-size: 18px; font-weight: 600; color: #2c3e50; }
        .check-stats { display: flex; gap: 15px; }
        .stat-item { text-align: center; }
        .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }
        .stat-label { font-size: 12px; color: #6c757d; }

        .check-body {
            padding: 20px;
            background: #f8f9fa;
        }
        .data-table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
        }
        .data-table th {
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-size: 13px;
        }
        .data-table td {
            padding: 10px 12px;
            border-bottom: 1px solid #e9ecef;
            font-size: 13px;
        }
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
            <h1>🔍 K8S 集群巡检报告</h1>
            <div class="subtitle">
                生成时间: {{ date }} | 巡检周期: {{ time_range }} | 数据源: Prometheus
            </div>
        </div>

        <!-- 汇总区域 -->
        <div class="summary-section">
            <div class="summary-card total">
                <div class="number">{{ summary.total_checks }}</div>
                <div class="label">巡检项目</div>
            </div>
            <div class="summary-card normal">
                <div class="number">{{ summary.normal }}</div>
                <div class="label">正常</div>
            </div>
            <div class="summary-card warning">
                <div class="number">{{ summary.warning }}</div>
                <div class="label">警告</div>
            </div>
            <div class="summary-card critical">
                <div class="number">{{ summary.critical }}</div>
                <div class="label">严重</div>
            </div>
        </div>

        <!-- 告警汇总 -->
        {% if alerts %}
        <div class="alerts-section">
            <h2>⚠️ 告警详情 (共 {{ alerts|length }} 条)</h2>
            <table class="alert-table">
                <tr>
                    <th>检查项</th>
                    <th>节点/实例</th>
                    <th>当前值</th>
                    <th>状态</th>
                </tr>
                {% for alert in alerts %}
                <tr>
                    <td>{{ alert.check_name }}</td>
                    <td>{{ alert.node }}{% if alert.instance %} / {{ alert.instance }}{% endif %}</td>
                    <td><strong>{{ alert.value }}</strong></td>
                    <td>
                        <span class="badge badge-{{ alert.status }}">
                            {{ '警告' if alert.status == 'warning' else '严重' }}
                        </span>
                    </td>
                </tr>
                {% endfor %}
            </table>
        </div>
        {% endif %}

        <!-- 详细检查 -->
        <div class="details-section">
            <h2>📊 详细检查结果</h2>
            {% for check_id, check in results.items() %}
            <div class="check-card">
                <div class="check-header {% if check.critical_count > 0 %}critical{% elif check.warning_count > 0 %}warning{% endif %}">
                    <div class="check-title">{{ check.name }}</div>
                    <div class="check-stats">
                        <div class="stat-item">
                            <div class="stat-value" style="color: #28a745;">{{ check.normal_count }}</div>
                            <div class="stat-label">正常</div>
                        </div>
                        {% if check.warning_count > 0 %}
                        <div class="stat-item">
                            <div class="stat-value" style="color: #ffc107;">{{ check.warning_count }}</div>
                            <div class="stat-label">警告</div>
                        </div>
                        {% endif %}
                        {% if check.critical_count > 0 %}
                        <div class="stat-item">
                            <div class="stat-value" style="color: #dc3545;">{{ check.critical_count }}</div>
                            <div class="stat-label">严重</div>
                        </div>
                        {% endif %}
                    </div>
                </div>
                {% if check['items'] %}
                <div class="check-body">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>节点/实例</th>
                                <th>当前值</th>
                                <th>阈值</th>
                                <th>状态</th>
                            </tr>
                        </thead>
                        <tbody>   
                            {% for item in check['items'] %}
                            <tr>
                                <td>{{ item.node }}{% if item.instance %} / {{ item.instance }}{% endif %}</td>
                                <td><strong>{{ "%.2f"|format(item.value) }}{{ check.unit }}</strong></td>
                                <td>
                                    {% if check.threshold_warning %}
                                    警告: {{ check.threshold_warning }}{{ check.unit }}<br>
                                    严重: {{ check.threshold_critical }}{{ check.unit }}
                                    {% else %}
                                    -
                                    {% endif %}
                                </td>
                                <td>
                                    <span class="status-dot status-{{ item.status }}"></span>
                                    {{ '正常' if item.status == 'normal' else '警告' if item.status == 'warning' else '严重' }}
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                {% endif %}
            </div>
            {% endfor %}
        </div>

        <div class="footer">
            <p>本报告由 K8S 巡检系统自动生成 | 基于 Grafana Dashboard 模板提取 | {{ date }}</p>
        </div>
    </div>
</body>
</html>
        ''')

        html = template.render(
            date=datetime.now().strftime('%Y-%m-%d %H:%M'),
            time_range="最近24小时",
            platform=f"{platform.system()} {platform.release()}",
            results=results,
            alerts=alerts,
            summary=summary
        )

        # 保存 HTML
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        html_file = f"{self.output_dir}/k8s_inspection_{timestamp}.html"

        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"✅ HTML 报告已生成: {html_file}")
        return html_file, html

    def convert_to_pdf(self, html_content, html_file):
        """转换为 PDF"""
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
    """主入口"""
    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 执行巡检
    inspector = K8SInspector(PROMETHEUS_URL)
    results, alerts, summary = inspector.run_all_checks()

    # 生成报告
    generator = ReportGenerator(OUTPUT_DIR)
    html_file, html_content = generator.generate_html(results, alerts, summary)
    pdf_file = generator.convert_to_pdf(html_content, html_file)

    # 输出汇总
    print("\n" + "=" * 60)
    print("📋 巡检报告汇总")
    print("=" * 60)
    print(f"HTML 报告: {html_file}")
    if pdf_file:
        print(f"PDF 报告:  {pdf_file}")
    print(f"告警数量:  {len(alerts)} 条")
    print("=" * 60)


if __name__ == '__main__':
    main()