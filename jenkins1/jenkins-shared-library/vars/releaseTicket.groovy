// 发布单管理 - 创建/查询/更新发布单状态
// 发布单是每次发布的正式记录，包含审批、部署、回滚全流程信息
// 存储格式：JSON 文件，路径 = Config.RELEASE_RECORD_DIR / {env} / {ticketId}.json

import groovy.json.JsonOutput
import groovy.json.JsonSlurper

// 创建发布单
def call(Map params = [:]) {
    def config = new com.devops.Config()
    def serviceName = params.serviceName ?: env.JOB_NAME ?: 'unknown'
    def targetEnv = params.env ?: env.ENV ?: 'unknown'
    def imageTag = params.imageTag ?: env.IMAGE_TAG ?: ''
    def image = params.image ?: env.IMAGE ?: ''
    def triggerType = params.triggerType ?: env.TRIGGER_TYPE ?: 'unknown'
    def triggerUser = params.triggerUser ?: env.BUILD_USER_ID ?: 'system'
    def buildUrl = params.buildUrl ?: env.BUILD_URL ?: ''
    def buildMessage = params.buildMessage ?: params.commitMessage ?: ''

    // 生成发布单 ID：REL-yyyyMMdd-NNN
    def tz = java.util.TimeZone.getTimeZone(config.IMAGE_TAG_TIMEZONE ?: 'Asia/Shanghai')
    def dateFmt = new java.text.SimpleDateFormat('yyyyMMdd')
    dateFmt.setTimeZone(tz)
    def dateStr = dateFmt.format(new Date())

    def recordDir = "${config.RELEASE_RECORD_DIR}/${targetEnv}"
    def seqNum = getNextSeqNum(recordDir, dateStr, config)
    def ticketId = "${config.RELEASE_TICKET_PREFIX}-${dateStr}-${String.format('%03d', seqNum)}"

    def now = new Date().format("yyyy-MM-dd HH:mm:ss", TimeZone.getTimeZone(config.IMAGE_TAG_TIMEZONE))

    def ticket = [
        ticketId: ticketId,
        serviceName: serviceName,
        environment: targetEnv,
        imageTag: imageTag,
        image: image,
        triggerType: triggerType,
        triggerUser: triggerUser,
        buildUrl: buildUrl,
        buildMessage: buildMessage,
        status: 'pending',        // pending / approved / deploying / success / failed / rollback
        createdAt: now,
        approvedBy: '',
        approvedAt: '',
        deployedAt: '',
        deployResult: '',
        rollbackFrom: '',
        rollbackReason: '',
        rollbackAt: '',
        history: [
            [time: now, action: 'created', user: triggerUser, detail: '发布单创建']
        ]
    ]

    // 写入文件
    saveTicket(ticket, config)

    // 注入环境变量供后续阶段使用
    env.RELEASE_TICKET_ID = ticketId

    echo "📋 [发布单] 已创建发布单：${ticketId}"
    echo "   服务：${serviceName} | 环境：${targetEnv} | 镜像：${image}"
    echo "   状态：pending | 创建人：${triggerUser}"

    return ticketId
}

// 更新发布单状态
def updateStatus(Map params = [:]) {
    def config = new com.devops.Config()
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID
    def newStatus = params.status
    def action = params.action ?: newStatus
    def user = params.user ?: env.BUILD_USER_ID ?: 'system'
    def detail = params.detail ?: ''
    def extraFields = params.extraFields ?: [:]

    if (!ticketId) {
        echo "⚠️ [发布单] 未找到发布单 ID，跳过更新"
        return
    }

    def ticket = loadTicket(ticketId, config)
    if (!ticket) {
        echo "⚠️ [发布单] 未找到发布单：${ticketId}"
        return
    }

    def now = new Date().format("yyyy-MM-dd HH:mm:ss", TimeZone.getTimeZone(config.IMAGE_TAG_TIMEZONE))

    // 更新状态
    ticket.status = newStatus

    // 更新时间字段
    switch (newStatus) {
        case 'approved':
            ticket.approvedBy = user
            ticket.approvedAt = now
            break
        case 'deploying':
            break
        case 'success':
        case 'failed':
            ticket.deployedAt = now
            ticket.deployResult = newStatus
            break
        case 'rollback':
            ticket.rollbackAt = now
            break
    }

    // 合并额外字段
    extraFields.each { k, v -> ticket[k] = v }

    // 追加历史记录
    ticket.history << [time: now, action: action, user: user, detail: detail]

    saveTicket(ticket, config)
    echo "📋 [发布单] ${ticketId} 状态更新：${newStatus}${detail ? ' | ' + detail : ''}"
}

// 记录审批信息
def recordApproval(Map params = [:]) {
    def config = new com.devops.Config()
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID
    def approver = params.approver ?: ''
    def approveMethod = params.method ?: 'jenkins_input'  // jenkins_input / wecom / wecom_app
    def comment = params.comment ?: ''

    if (!ticketId) return

    updateStatus(
        ticketId: ticketId,
        status: 'approved',
        action: 'approved',
        user: approver,
        detail: "审批通过（方式：${approveMethod}）${comment ? '，备注：' + comment : ''}",
        extraFields: [
            approveMethod: approveMethod,
            approveComment: comment
        ]
    )

    env.PROD_APPROVER = approver
}

// 记录部署结果
def recordDeployResult(Map params = [:]) {
    def config = new com.devops.Config()
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID
    def result = params.result ?: 'unknown'  // success / failed
    def detail = params.detail ?: ''

    if (!ticketId) return

    updateStatus(
        ticketId: ticketId,
        status: result,
        action: 'deploy_' + result,
        user: env.BUILD_USER_ID ?: 'system',
        detail: detail ?: "部署${result == 'success' ? '成功' : '失败'}"
    )
}

// 记录回滚
def recordRollback(Map params = [:]) {
    def config = new com.devops.Config()
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID
    def reason = params.reason ?: ''
    def operator = params.operator ?: env.BUILD_USER_ID ?: 'system'

    if (!ticketId) return

    updateStatus(
        ticketId: ticketId,
        status: 'rollback',
        action: 'rollback',
        user: operator,
        detail: reason ? "回滚原因：${reason}" : '执行回滚',
        extraFields: [
            rollbackReason: reason,
            rollbackOperator: operator
        ]
    )
}

// 获取发布单详情
def getTicket(String ticketId = null) {
    def config = new com.devops.Config()
    ticketId = ticketId ?: env.RELEASE_TICKET_ID
    if (!ticketId) return null
    return loadTicket(ticketId, config)
}

// 查询环境最近发布记录
def listRecentTickets(Map params = [:]) {
    def config = new com.devops.Config()
    def targetEnv = params.env ?: env.ENV ?: 'dev'
    def limit = params.limit ?: 10
    def recordDir = "${config.RELEASE_RECORD_DIR}/${targetEnv}"

    def tickets = []
    try {
        def dir = new File(recordDir)
        if (!dir.exists()) return tickets

        def files = dir.listFiles()?.findAll { it.name.endsWith('.json') }
            ?.sort { -it.lastModified() }
            ?.take(limit)

        files?.each { f ->
            try {
                def ticket = new JsonSlurper().parse(f)
                tickets << ticket
            } catch (e) {
                echo "⚠️ 解析发布单文件失败：${f.name}"
            }
        }
    } catch (Exception e) {
        echo "⚠️ 查询发布记录失败：${e.getMessage()}"
    }

    return tickets
}

// ========== 内部辅助方法 ==========

// 获取下一个序列号
def getNextSeqNum(String recordDir, String dateStr, def config) {
    try {
        def dir = new File(recordDir)
        if (!dir.exists()) {
            dir.mkdirs()
        }

        def existingFiles = dir.listFiles()?.findAll {
            it.name.startsWith("${config.RELEASE_TICKET_PREFIX}-${dateStr}") && it.name.endsWith('.json')
        }

        if (!existingFiles || existingFiles.isEmpty()) return 1

        def maxSeq = existingFiles.collect { f ->
            def matcher = f.name =~ /${config.RELEASE_TICKET_PREFIX}-${dateStr}-(\d{3})\.json/
            matcher ? matcher[0][1].toInteger() : 0
        }.max()

        return maxSeq + 1
    } catch (Exception e) {
        echo "⚠️ 获取序列号失败：${e.getMessage()}"
        return 1
    }
}

// 保存发布单到文件
def saveTicket(Map ticket, def config) {
    def recordDir = "${config.RELEASE_RECORD_DIR}/${ticket.environment}"
    def filePath = "${recordDir}/${ticket.ticketId}.json"

    try {
        def dir = new File(recordDir)
        if (!dir.exists()) {
            dir.mkdirs()
        }

        def json = JsonOutput.prettyPrint(JsonOutput.toJson(ticket))
        def file = new File(filePath)
        file.write(json, 'UTF-8')

        echo "💾 [发布单] 已保存：${filePath}"
    } catch (Exception e) {
        echo "⚠️ [发布单] 保存失败：${e.getMessage()}"
    }
}

// 从文件加载发布单
def loadTicket(String ticketId, def config) {
    // 遍历环境目录查找
    try {
        def baseDir = new File(config.RELEASE_RECORD_DIR)
        if (!baseDir.exists()) return null

        def envDirs = baseDir.listFiles()?.findAll { it.isDirectory() }
        for (def envDir : envDirs) {
            def filePath = "${envDir.absolutePath}/${ticketId}.json"
            def file = new File(filePath)
            if (file.exists()) {
                return new JsonSlurper().parse(file)
            }
        }
    } catch (Exception e) {
        echo "⚠️ [发布单] 加载失败：${e.getMessage()}"
    }
    return null
}
