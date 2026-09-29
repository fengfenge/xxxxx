// 消息通知 - 同时支持钉钉和企业微信
// 自动根据构建状态发送通知，包含发布单、审批人等完整信息

import groovy.json.JsonOutput

def call(String status, String customMessage = '') {
    def config = new com.devops.Config()

    def color = "warning"
    def title = "构建通知"
    def statusEmoji = "⚠️"

    if (status == "SUCCESS") {
        color = "green"
        title = "✅ 部署成功"
        statusEmoji = "✅"
    } else if (status == "FAILED") {
        color = "red"
        title = "❌ 部署失败"
        statusEmoji = "❌"
    } else if (status == "ABORTED") {
        color = "gray"
        title = "⚠️ 流程中止"
        statusEmoji = "⚠️"
    }

    def ticketId = env.RELEASE_TICKET_ID ?: '无'
    def approverInfo = env.PROD_APPROVER ? "审批人：${env.PROD_APPROVER}" : ''

    def content = """${statusEmoji} **${title}**
> **项目**：${env.JOB_NAME}
> **环境**：${env.ENV ?: '未知'}
> **分支/标签**：${env.BRANCH_NAME ?: env.TAG_NAME ?: '未知'}
> **镜像版本**：${env.IMAGE_TAG ?: '未知'}
> **发布单号**：${ticketId}
> **状态**：${status}
> **耗时**：${currentBuild.durationString}
${approverInfo ? "> **" + approverInfo + "**" : ""}
${customMessage ? "> **备注**：${customMessage}" : ""}
> **详情**：[查看构建日志](${env.BUILD_URL})"""

    // 发送钉钉通知
    sendDingTalk(title, content, config)

    // 发送企业微信通知
    sendWecom(content, config)

    echo "📢 [通知] 已发送 ${status} 通知（钉钉 + 企业微信）"
}

// ========== 钉钉通知 ==========

def sendDingTalk(String title, String content, def config) {
    def webhook = config.DINGTALK_WEBHOOK
    if (!webhook || webhook.contains('YOUR_TOKEN')) {
        echo "📢 [钉钉] Webhook 未配置，跳过发送"
        return
    }

    def payload = JsonOutput.toJson([
        msgtype: 'markdown',
        markdown: [
            title: title,
            text: content
        ]
    ])

    try {
        sh """
            curl -s -X POST \
                -H 'Content-Type: application/json' \
                -d '${payload.replace("'", "'\\''")}' \
                '${webhook}'
        """
    } catch (Exception e) {
        echo "⚠️ [钉钉] 发送失败：${e.getMessage()}"
    }
}

// ========== 企业微信通知 ==========

def sendWecom(String content, def config) {
    def webhook = config.WECOM_WEBHOOK
    if (!webhook || webhook.contains('YOUR_KEY')) {
        echo "📢 [企微] Webhook 未配置，跳过发送"
        return
    }

    def payload = JsonOutput.toJson([
        msgtype: 'markdown',
        markdown: [
            content: content
        ]
    ])

    try {
        sh """
            curl -s -X POST \
                -H 'Content-Type: application/json' \
                -d '${payload.replace("'", "'\\''")}' \
                '${webhook}'
        """
    } catch (Exception e) {
        echo "⚠️ [企微] 发送失败：${e.getMessage()}"
    }
}
