// 企业微信审批集成
// 支持两种模式：
//   simple - 群机器人通知 + Jenkins input 审批（默认，无需企业微信应用）
//   app    - 企业微信应用审批（需要配置 CorpId/AgentId/Secret）

// 发送审批通知并等待审批
def call(Map params = [:]) {
    def config = new com.devops.Config()
    def targetEnv = params.env ?: env.ENV ?: 'unknown'
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID ?: ''
    def mode = params.mode ?: config.WECOM_APPROVE_MODE ?: 'simple'

    echo "🔐 [审批] 开始审批流程（模式：${mode}）| 环境：${targetEnv} | 发布单：${ticketId}"

    // 发送企业微信审批通知
    sendApprovalNotification(params + [mode: mode])

    def approver = ''
    def approveMethod = ''

    try {
        switch (mode) {
            case 'app':
                // 企业微信应用审批：在应用中审批后回调
                def result = waitForWecomAppApproval(params)
                approver = result.approver
                approveMethod = 'wecom_app'
                break

            case 'simple':
            default:
                // 简单模式：群机器人通知 + Jenkins input 审批
                def result = waitForJenkinsInput(params)
                approver = result.approver
                approveMethod = 'jenkins_input'
                break
        }
    } catch (org.jenkinsci.plugins.workflow.steps.FlowInterruptedException e) {
        // 审批被拒绝或超时
        releaseTicket.updateStatus(
            ticketId: ticketId,
            status: 'failed',
            action: 'approval_rejected',
            user: 'system',
            detail: "审批被拒绝或超时：${e.getMessage()}"
        )
        sendRejectNotification(params)
        error "❌ 审批未通过，发布流程终止。"
    }

    // 记录审批信息
    releaseTicket.recordApproval(
        ticketId: ticketId,
        approver: approver,
        method: approveMethod
    )

    echo "✅ [审批] 审批通过！审批人：${approver} | 方式：${approveMethod}"
    return [approver: approver, method: approveMethod]
}

// 发送审批通知到企业微信
def sendApprovalNotification(Map params = [:]) {
    def config = new com.devops.Config()
    def targetEnv = params.env ?: env.ENV ?: 'unknown'
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID ?: ''
    def serviceName = params.serviceName ?: env.JOB_NAME ?: 'unknown'
    def imageTag = params.imageTag ?: env.IMAGE_TAG ?: ''
    def image = params.image ?: env.IMAGE ?: ''
    def triggerUser = params.triggerUser ?: env.BUILD_USER_ID ?: 'system'
    def buildUrl = params.buildUrl ?: env.BUILD_URL ?: ''
    def buildMessage = params.buildMessage ?: ''
    def mode = params.mode ?: config.WECOM_APPROVE_MODE ?: 'simple'

    def envEmoji = getEnvEmoji(targetEnv)
    def now = new Date().format("yyyy-MM-dd HH:mm:ss", TimeZone.getTimeZone(config.IMAGE_TAG_TIMEZONE))

    def content = """${envEmoji} **发布审批申请**
> **发布单号**：${ticketId}
> **服务名称**：${serviceName}
> **目标环境**：${targetEnv.toUpperCase()}
> **镜像版本**：${imageTag}
> **触发方式**：${env.TRIGGER_TYPE == 'tag' ? '标签构建' : '分支构建'}
> **触发人**：${triggerUser}
> **构建说明**：${buildMessage ?: '无'}
> **申请时间**：${now}

${mode == 'simple' ? "请点击 [Jenkins 构建页面](${buildUrl}) 进行审批操作" : "请在企业微信审批应用中处理"}"""

    if (mode == 'simple') {
        // 使用群机器人发送 Markdown 通知
        sendWecomMarkdown(content, config)
    } else {
        // 使用企业微信应用发送审批
        sendWecomAppApproval(params, config)
    }

    echo "📢 [审批] 已发送审批通知到企业微信"
}

// 等待 Jenkins Input 审批
def waitForJenkinsInput(Map params = [:]) {
    def config = new com.devops.Config()
    def targetEnv = params.env ?: env.ENV ?: 'unknown'
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID ?: ''
    def timeoutMinutes = params.timeout ?: config.APPROVAL_TIMEOUT_MINUTES ?: 30
    def approverUsers = params.approverUsers ?: config.APPROVER_USERS ?: 'admin'

    def envLabel = targetEnv.toUpperCase()

    def userInput = input(
        message: """
        ⚠️ **${envLabel} 环境发布审批** ⚠️
        
        发布单号：${ticketId}
        服务：${env.JOB_NAME}
        版本：${env.IMAGE_TAG}
        触发人：${env.BUILD_USER_ID ?: 'system'}
        
        请确认：
        1. 代码审查已完成
        2. 测试环境验证通过
        3. 数据库脚本已就绪（如涉及）
        4. 已通知相关业务方
        """,
        ok: '✅ 确认发布',
        submitter: approverUsers,
        submitterParameter: 'APPROVER_NAME'
    )

    return [approver: userInput]
}

// 等待企业微信应用审批
def waitForWecomAppApproval(Map params = [:]) {
    def config = new com.devops.Config()
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID ?: ''
    def timeoutMinutes = params.timeout ?: config.APPROVAL_TIMEOUT_MINUTES ?: 30
    def checkInterval = 15  // 每 15 秒查询一次审批状态

    echo "⏳ [审批] 等待企业微信审批（超时 ${timeoutMinutes} 分钟）..."

    def startTime = System.currentTimeMillis()
    def timeoutMs = timeoutMinutes * 60 * 1000

    while (System.currentTimeMillis() - startTime < timeoutMs) {
        def status = queryWecomApprovalStatus(ticketId, config)

        if (status.approved) {
            return [approver: status.approver]
        } else if (status.rejected) {
            error "❌ 企业微信审批被拒绝，审批人：${status.approver}，原因：${status.reason}"
        }

        sleep(checkInterval * 1000)
    }

    error "❌ 审批超时（${timeoutMinutes} 分钟），发布流程终止。"
}

// 查询企业微信审批状态
def queryWecomApprovalStatus(String ticketId, def config) {
    // TODO: 实现企业微信审批 API 查询
    // 需要：1. 获取 access_token  2. 调用审批状态查询接口
    // 当前返回 pending 状态，实际使用时需对接企业微信审批回调
    return [approved: false, rejected: false, approver: '', reason: '']
}

// 通过企业微信应用发送审批
def sendWecomAppApproval(Map params, def config) {
    if (!config.WECOM_CORP_ID || !config.WECOM_APP_AGENT_ID) {
        echo "⚠️ [审批] 企业微信应用未配置，回退到群机器人通知"
        def content = buildApprovalMessage(params)
        sendWecomMarkdown(content, config)
        return
    }

    // TODO: 实现企业微信审批应用 API 调用
    // 1. 获取 access_token（通过 WECOM_APP_SECRET_CREDENTIALS_ID）
    // 2. 创建审批实例
    // 3. 记录审批编号
    echo "⚠️ [审批] 企业微信应用审批 API 待实现，当前使用群机器人通知"
    def content = buildApprovalMessage(params)
    sendWecomMarkdown(content, config)
}

// 发送审批拒绝/超时通知
def sendRejectNotification(Map params = [:]) {
    def config = new com.devops.Config()
    def targetEnv = params.env ?: env.ENV ?: 'unknown'
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID ?: ''
    def serviceName = params.serviceName ?: env.JOB_NAME ?: 'unknown'

    def content = """❌ **发布审批未通过**
> **发布单号**：${ticketId}
> **服务名称**：${serviceName}
> **目标环境**：${targetEnv.toUpperCase()}
> **结果**：审批被拒绝或超时，发布流程已终止"""

    sendWecomMarkdown(content, config)
}

// 发送部署结果通知
def sendDeployResultNotification(Map params = [:]) {
    def config = new com.devops.Config()
    def status = params.status ?: 'unknown'
    def targetEnv = params.env ?: env.ENV ?: 'unknown'
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID ?: ''
    def serviceName = params.serviceName ?: env.JOB_NAME ?: 'unknown'
    def imageTag = params.imageTag ?: env.IMAGE_TAG ?: ''
    def approver = params.approver ?: env.PROD_APPROVER ?: ''
    def deployDuration = params.deployDuration ?: ''
    def now = new Date().format("yyyy-MM-dd HH:mm:ss", TimeZone.getTimeZone(config.IMAGE_TAG_TIMEZONE))

    def statusEmoji = status == 'SUCCESS' ? '✅' : '❌'
    def statusText = status == 'SUCCESS' ? '部署成功' : '部署失败'

    def content = """${statusEmoji} **${statusText}**
> **发布单号**：${ticketId}
> **服务名称**：${serviceName}
> **目标环境**：${targetEnv.toUpperCase()}
> **镜像版本**：${imageTag}
> **审批人**：${approver ?: '自动审批'}
> **部署时间**：${now}
${deployDuration ? "> **部署耗时**：${deployDuration}" : ""}
> **详情**：[查看构建日志](${env.BUILD_URL})"""

    sendWecomMarkdown(content, config)
}

// 发送回滚通知
def sendRollbackNotification(Map params = [:]) {
    def config = new com.devops.Config()
    def targetEnv = params.env ?: env.ENV ?: 'unknown'
    def serviceName = params.serviceName ?: env.JOB_NAME ?: 'unknown'
    def reason = params.reason ?: ''
    def operator = params.operator ?: env.BUILD_USER_ID ?: 'system'
    def now = new Date().format("yyyy-MM-dd HH:mm:ss", TimeZone.getTimeZone(config.IMAGE_TAG_TIMEZONE))

    def content = """↩️ **回滚通知**
> **服务名称**：${serviceName}
> **目标环境**：${targetEnv.toUpperCase()}
> **操作人**：${operator}
> **回滚原因**：${reason ?: '未填写'}
> **操作时间**：${now}"""

    sendWecomMarkdown(content, config)
}

// ========== 通用发送方法 ==========

// 发送企业微信 Markdown 消息（群机器人）
def sendWecomMarkdown(String content, def config) {
    def webhook = config.WECOM_WEBHOOK
    if (!webhook || webhook.contains('YOUR_KEY')) {
        echo "📢 [企微] Webhook 未配置，跳过发送。消息内容：\n${content}"
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
        echo "📢 [企微] 已发送 Markdown 通知"
    } catch (Exception e) {
        echo "⚠️ [企微] 发送失败：${e.getMessage()}"
    }
}

// 构建审批消息文本
def buildApprovalMessage(Map params = [:]) {
    def targetEnv = params.env ?: env.ENV ?: 'unknown'
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID ?: ''
    def serviceName = params.serviceName ?: env.JOB_NAME ?: 'unknown'
    def imageTag = params.imageTag ?: env.IMAGE_TAG ?: ''
    def triggerUser = params.triggerUser ?: env.BUILD_USER_ID ?: 'system'
    def buildUrl = params.buildUrl ?: env.BUILD_URL ?: ''
    def config = new com.devops.Config()
    def now = new Date().format("yyyy-MM-dd HH:mm:ss", TimeZone.getTimeZone(config.IMAGE_TAG_TIMEZONE))

    return """${getEnvEmoji(targetEnv)} **发布审批申请**
> **发布单号**：${ticketId}
> **服务名称**：${serviceName}
> **目标环境**：${targetEnv.toUpperCase()}
> **镜像版本**：${imageTag}
> **触发人**：${triggerUser}
> **申请时间**：${now}

请点击 [Jenkins 构建页面](${buildUrl}) 进行审批操作"""
}

// 环境对应的 Emoji
def getEnvEmoji(String targetEnv) {
    switch (targetEnv) {
        case 'prod': return '🔴'
        case 'uat':  return '🟠'
        case 'test': return '🟡'
        case 'dev':  return '🟢'
        default:     return '⚪'
    }
}
