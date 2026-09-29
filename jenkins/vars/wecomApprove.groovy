import groovy.json.JsonOutput
import groovy.json.JsonSlurperClassic

// 企业微信通知 + 人工审批
// simple: 企业微信通知 + Jenkins input 审批
// app: 预留企业微信原生审批，当前仍回退为通知

def call(Map params = [:]) {
    echo 'DEBUG [wecomApprove] 加载版本标记：v20260701-002'

    def config = new com.devops.Config()
    def targetEnv = (params.env ?: env.ENV ?: 'unknown').toString().trim().toLowerCase()
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID ?: ''
    def mode = (params.mode ?: config.WECOM_APPROVE_MODE ?: 'simple').toString().trim().toLowerCase()

    echo "INFO [审批] 开始审批流程，模式=${mode}，环境=${targetEnv}，发布单=${ticketId}"

    sendApprovalNotification(params + [env: targetEnv, mode: mode])

    def approver = ''
    def approveMethod = ''
    def approveComment = ''

    echo "DEBUG [审批] 即将进入审批分支，mode=${mode}"

    try {
        if (mode == 'app') {
            echo 'DEBUG [审批] 进入 app 分支'
            def result = waitForWecomAppApproval(params + [env: targetEnv])
            approver = result.approver
            approveComment = result.comment ?: ''
            approveMethod = 'wecom_app'
        } else {
            if (mode != 'simple') {
                echo "WARN [审批] 未识别的审批模式 ${mode}，回退到 simple"
            }
            echo 'DEBUG [审批] 进入 simple 分支，即将调用 waitForJenkinsInput'
            def result = waitForJenkinsInput(params + [env: targetEnv])
            echo "DEBUG [审批] waitForJenkinsInput 已返回，result=${result}"
            approver = result.approver
            approveComment = result.comment ?: ''
            approveMethod = 'jenkins_input'
        }
    } catch (org.jenkinsci.plugins.workflow.steps.FlowInterruptedException e) {
        releaseTicket.updateStatus(
            ticketId: ticketId,
            env: targetEnv,
            status: 'failed',
            action: 'approval_rejected',
            user: 'system',
            detail: "审批被拒绝或超时：${e.getMessage()}"
        )
        sendRejectNotification(params + [env: targetEnv])
        error '审批未通过，终止后续部署'
    }

    approver = approver?.toString()?.trim()
    if (!approver) {
        error "审批完成但审批人为空，终止后续部署。请检查是否出现 [Pipeline] input、Input Step 插件版本以及 submitterParameter 是否返回 ${approveMethod}"
    }

    env.PROD_APPROVER = approver
    env.PROD_APPROVE_METHOD = approveMethod

    echo "INFO [审批] 审批通过，审批人：${approver}，方式：${approveMethod}"
    return [approver: approver, method: approveMethod, comment: approveComment]
}

def sendApprovalNotification(Map params = [:]) {
    def config = new com.devops.Config()
    def targetEnv = (params.env ?: env.ENV ?: 'unknown').toString().trim().toLowerCase()
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID ?: ''
    def serviceName = params.serviceName ?: env.JOB_NAME ?: 'unknown'
    def imageTag = params.imageTag ?: env.IMAGE_TAG ?: ''
    def triggerUser = params.triggerUser ?: env.BUILD_USER_ID ?: 'system'
    def buildUrl = params.buildUrl ?: env.BUILD_URL ?: ''
    def buildMessage = params.buildMessage ?: ''
    def mode = (params.mode ?: config.WECOM_APPROVE_MODE ?: 'simple').toString().trim().toLowerCase()

    def envEmoji = getEnvEmoji(targetEnv)
    def now = new Date().format('yyyy-MM-dd HH:mm:ss', TimeZone.getTimeZone(config.IMAGE_TAG_TIMEZONE))
    def triggerType = (params.triggerType ?: env.TRIGGER_TYPE ?: 'branch') == 'tag' ? '标签构建' : '分支构建'
    def approvalHint = mode == 'simple'
        ? "请点击 [Jenkins 构建页面](${buildUrl}) 完成人工审批"
        : '请在企业微信审批应用中处理审批'

    def content = """${envEmoji} **发布审批申请**
> **发布单号**：${ticketId}
> **服务名称**：${serviceName}
> **目标环境**：${targetEnv.toUpperCase()}
> **镜像版本**：${imageTag}
> **触发方式**：${triggerType}
> **触发人**：${triggerUser}
> **构建说明**：${buildMessage ?: '无'}
> **申请时间**：${now}

${approvalHint}"""

    if (mode == 'simple') {
        sendWecomMarkdown(content, config)
    } else {
        sendWecomAppApproval(params + [env: targetEnv], config)
    }

    echo 'INFO [审批] 已发送审批通知'
}

def waitForJenkinsInput(Map params = [:]) {
    echo 'DEBUG [审批] waitForJenkinsInput 函数入口'

    try {
        def config = new com.devops.Config()
        def targetEnv = (params.env ?: env.ENV ?: 'unknown').toString().trim().toLowerCase()
        def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID ?: ''
        def timeoutMinutes = (params.timeout ?: config.APPROVAL_TIMEOUT_MINUTES ?: 30) as int
        def approverUsers = params.approverUsers ?: config.APPROVER_USERS ?: 'admin'
        def envLabel = targetEnv.toUpperCase()
        def submitterParamName = 'APPROVER_NAME'
        def inputId = "deploy-approval-${env.BUILD_NUMBER}-${ticketId ?: System.currentTimeMillis()}"

        echo "INFO [审批] 等待 Jenkins Input 审批，超时 ${timeoutMinutes} 分钟，审批人=${approverUsers}"

        def inputResult = timeout(time: timeoutMinutes, unit: 'MINUTES') {
            input(
                id: inputId,
                message: """
${envLabel} 发布审批

发布单号：${ticketId}
服务名称：${env.JOB_NAME}
镜像版本：${env.IMAGE_TAG}
触发人：${env.BUILD_USER_ID ?: 'system'}

确认项：
1. 代码审核已完成
2. 测试验证已通过
3. 变更窗口已确认
4. 相关方已通知
""",
                ok: '确认发布',
                submitter: approverUsers,
                submitterParameter: submitterParamName
            )
        }

        echo "DEBUG [审批] input 结果类型：${inputResult?.getClass()}，值：${inputResult}"

        def approver = ''

        if (inputResult instanceof Map) {
            approver = (inputResult[submitterParamName] ?: '').toString().trim()
        } else if (inputResult != null) {
            approver = inputResult.toString().trim()
        }

        if (!approver) {
            echo "WARN [审批] submitterParameter 未返回审批人，尝试从 InputAction 回读"
            approver = getApproverFromInputAction(inputId)
        }

        if (!approver) {
            error "Jenkins Input 已确认，但无法获取审批人。inputId=${inputId}，submitterParameter=${submitterParamName}"
        }

        echo "DEBUG [审批] waitForJenkinsInput 返回 approver=${approver}"
        return [approver: approver, comment: '']
    } catch (Exception e) {
        echo "ERROR [审批] waitForJenkinsInput 内部异常：${e.getClass().getName()}：${e.getMessage()}"
        throw e
    }
}

def getApproverFromInputAction(String inputId) {
    try {
        def rawBuild = currentBuild.rawBuild
        def inputAction = rawBuild.getAction(org.jenkinsci.plugins.workflow.support.steps.input.InputAction)
        if (!inputAction) {
            echo "WARN [审批] 未找到 InputAction"
            return ''
        }
        def execution = inputAction.getExecution(inputId)
        if (!execution) {
            echo "WARN [审批] 未找到 id=${inputId} 的 InputStepExecution"
            return ''
        }
        def submitter = execution.getSubmitter()
        echo "DEBUG [审批] InputAction 回读审批人：${submitter}"
        return submitter?.toString()?.trim() ?: ''
    } catch (Exception e) {
        echo "WARN [审批] 从 InputAction 回读审批人失败：${e.getMessage()}"
        return ''
    }
}

def waitForWecomAppApproval(Map params = [:]) {
    def config = new com.devops.Config()
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID ?: ''
    def timeoutMinutes = (params.timeout ?: config.APPROVAL_TIMEOUT_MINUTES ?: 30) as int
    def checkIntervalSeconds = 15

    echo "INFO [审批] 等待企业微信原生审批，超时 ${timeoutMinutes} 分钟"

    def startTime = System.currentTimeMillis()
    def timeoutMs = timeoutMinutes * 60 * 1000

    while (System.currentTimeMillis() - startTime < timeoutMs) {
        def status = queryWecomApprovalStatus(ticketId, config)

        if (status.approved) {
            return [approver: status.approver ?: '', comment: status.comment ?: '']
        }
        if (status.rejected) {
            error "企业微信审批被拒绝，审批人：${status.approver}，原因：${status.reason}"
        }

        sleep time: checkIntervalSeconds, unit: 'SECONDS'
    }

    error "审批超时：${timeoutMinutes} 分钟"
}

def queryWecomApprovalStatus(String ticketId, def config) {
    // 预留企业微信原生审批查询。
    return [approved: false, rejected: false, approver: '', comment: '', reason: '']
}

def sendWecomAppApproval(Map params, def config) {
    if (!config.WECOM_CORP_ID || !config.WECOM_APP_AGENT_ID) {
        echo 'WARN [审批] 企业微信原生审批配置缺失，回退到 Markdown 通知'
        sendWecomMarkdown(buildApprovalMessage(params), config)
        return
    }

    echo 'WARN [审批] 企业微信原生审批 API 尚未实现，回退到 Markdown 通知'
    sendWecomMarkdown(buildApprovalMessage(params), config)
}

def sendRejectNotification(Map params = [:]) {
    def config = new com.devops.Config()
    def targetEnv = (params.env ?: env.ENV ?: 'unknown').toString().trim().toLowerCase()
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID ?: ''
    def serviceName = params.serviceName ?: env.JOB_NAME ?: 'unknown'

    def content = """[REJECTED] **发布审批未通过**
> **发布单号**：${ticketId}
> **服务名称**：${serviceName}
> **目标环境**：${targetEnv.toUpperCase()}
> **结果**：审批被拒绝或超时，发布流程已终止"""

    sendWecomMarkdown(content, config)
}

def sendDeployResultNotification(Map params = [:]) {
    def config = new com.devops.Config()
    def status = params.status ?: 'unknown'
    def targetEnv = (params.env ?: env.ENV ?: 'unknown').toString().trim().toLowerCase()
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID ?: ''
    def serviceName = params.serviceName ?: env.JOB_NAME ?: 'unknown'
    def imageTag = params.imageTag ?: env.IMAGE_TAG ?: ''
    def deployDuration = params.deployDuration ?: ''
    def now = new Date().format('yyyy-MM-dd HH:mm:ss', TimeZone.getTimeZone(config.IMAGE_TAG_TIMEZONE))

    def approver = (params.approver ?: env.PROD_APPROVER ?: '').toString().trim()
    if (!approver && ticketId) {
        def ticket = releaseTicket.getTicket(ticketId: ticketId, env: targetEnv)
        approver = (ticket?.approver ?: ticket?.approvedBy ?: '').toString().trim()
    }
    def approverDisplay = approver ?: (config.isApprovalRequired(targetEnv) ? '审批人未回写' : '无需审批')

    def statusEmoji = status == 'SUCCESS' ? '[SUCCESS]' : '[FAILED]'
    def statusText = status == 'SUCCESS' ? '部署成功' : '部署失败'

    def content = """${statusEmoji} **${statusText}**
> **发布单号**：${ticketId}
> **服务名称**：${serviceName}
> **目标环境**：${targetEnv.toUpperCase()}
> **镜像版本**：${imageTag}
> **审批人**：${approverDisplay}
> **部署时间**：${now}
${deployDuration ? "> **部署耗时**：${deployDuration}" : ''}
> **详情**：[查看构建日志](${env.BUILD_URL})"""

    sendWecomMarkdown(content, config)
}

def sendRollbackNotification(Map params = [:]) {
    def config = new com.devops.Config()
    def targetEnv = (params.env ?: env.ENV ?: 'unknown').toString().trim().toLowerCase()
    def serviceName = params.serviceName ?: env.JOB_NAME ?: 'unknown'
    def reason = params.reason ?: ''
    def operator = params.operator ?: env.BUILD_USER_ID ?: 'system'
    def now = new Date().format('yyyy-MM-dd HH:mm:ss', TimeZone.getTimeZone(config.IMAGE_TAG_TIMEZONE))

    def content = """[ROLLBACK] **回滚通知**
> **服务名称**：${serviceName}
> **目标环境**：${targetEnv.toUpperCase()}
> **操作人**：${operator}
> **回滚原因**：${reason ?: '无'}
> **操作时间**：${now}"""

    sendWecomMarkdown(content, config)
}

def sendWecomMarkdown(String content, def config) {
    def webhook = config.WECOM_WEBHOOK
    def webhookUpper = webhook?.toString()?.toUpperCase() ?: ''
    if (!webhook || webhookUpper.contains('YOUR_KEY') || webhookUpper.contains('YOURKEY')) {
        echo "WARN [企微] Webhook 未配置，跳过发送。消息内容：\n${content}"
        return
    }

    def payload = JsonOutput.toJson([
        msgtype : 'markdown',
        markdown: [
            content: content
        ]
    ])

    try {
        writeFile file: '.wecom_markdown_payload.json', text: payload, encoding: 'UTF-8'
        def response = sh(
            script: """
            curl -sS -X POST \\
                -H 'Content-Type: application/json' \\
                --data @.wecom_markdown_payload.json \\
                '${webhook}'
            """,
            returnStdout: true
        ).trim()
        echo "DEBUG [企微] Markdown 通知返回：${response}"

        def result = new JsonSlurperClassic().parseText(response)
        if ((result.errcode as int) != 0) {
            error "企业微信 Markdown 通知发送失败：errcode=${result.errcode}，errmsg=${result.errmsg}"
        }

        echo 'INFO [企微] Markdown 通知发送成功'
    } catch (Exception e) {
        error "企微发送失败：${e.getMessage()}"
    }
}

def buildApprovalMessage(Map params = [:]) {
    def targetEnv = (params.env ?: env.ENV ?: 'unknown').toString().trim().toLowerCase()
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID ?: ''
    def serviceName = params.serviceName ?: env.JOB_NAME ?: 'unknown'
    def imageTag = params.imageTag ?: env.IMAGE_TAG ?: ''
    def triggerUser = params.triggerUser ?: env.BUILD_USER_ID ?: 'system'
    def buildUrl = params.buildUrl ?: env.BUILD_URL ?: ''
    def config = new com.devops.Config()
    def now = new Date().format('yyyy-MM-dd HH:mm:ss', TimeZone.getTimeZone(config.IMAGE_TAG_TIMEZONE))

    return """${getEnvEmoji(targetEnv)} **发布审批申请**
> **发布单号**：${ticketId}
> **服务名称**：${serviceName}
> **目标环境**：${targetEnv.toUpperCase()}
> **镜像版本**：${imageTag}
> **触发人**：${triggerUser}
> **申请时间**：${now}

请点击 [Jenkins 构建页面](${buildUrl}) 完成人工审批"""
}

def getEnvEmoji(String targetEnv) {
    switch (targetEnv) {
        case 'prod':
            return '生产'
        case 'uat':
            return '预发布'
        case 'test':
            return '测试'
        case 'dev':
            return '开发'
        default:
            return '未知'
    }
}
