// 发布单管理 - 简化版
// 一个 Jenkins build 对应一份 JSON。发布单只做留痕、通知、事后追溯，不维护阶段 history。

import groovy.json.JsonOutput
import groovy.json.JsonSlurper

def call(Map params = [:]) {
    def config = params.config ?: new com.devops.Config()
    def targetEnv = (params.env ?: env.ENV ?: 'unknown').toString().trim().toLowerCase()
    def ticketId = buildTicketId(config)
    def createdAt = currentTime(config)

    def ticket = [
        ticketId      : ticketId,
        jobName       : env.JOB_NAME ?: 'unknown',
        buildNumber   : env.BUILD_NUMBER ?: '',
        serviceName   : params.serviceName ?: env.JOB_NAME ?: 'unknown',
        environment   : targetEnv,
        branchOrTag   : params.branchOrTag ?: resolveBranchOrTag(),
        imageTag      : params.imageTag ?: env.IMAGE_TAG ?: '',
        image         : params.image ?: env.IMAGE ?: '',
        triggerType   : params.triggerType ?: env.TRIGGER_TYPE ?: 'unknown',
        triggerUser   : params.triggerUser ?: env.TRIGGER_USER ?: env.BUILD_USER_ID ?: 'system',
        approver      : '',
        approveMethod : '',
        approveComment: '',
        status        : 'pending',
        deployResult  : '',
        failReason    : '',
        previousImage : '',
        buildUrl      : params.buildUrl ?: env.BUILD_URL ?: '',
        buildMessage  : params.buildMessage ?: params.commitMessage ?: '',
        createdAt     : createdAt,
        finishedAt    : ''
    ]

    saveTicket(ticket, config)
    env.RELEASE_TICKET_ID = ticketId

    echo "📋 [发布单] 已创建：${ticketId} | 环境=${targetEnv} | 镜像=${ticket.image}"
    return ticketId
}

def updateStatus(Map params = [:]) {
    def config = params.config ?: new com.devops.Config()
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID
    def targetEnv = (params.env ?: env.ENV ?: '').toString().trim().toLowerCase()

    if (!ticketId) {
        echo "⚠️ [发布单] 未找到发布单 ID，跳过更新"
        return
    }

    def ticket = loadTicket(ticketId, config, targetEnv)
    if (!ticket) {
        echo "⚠️ [发布单] 未找到发布单：${ticketId}${targetEnv ? ' | 环境=' + targetEnv : ''}"
        return
    }

    def status = params.status ?: ticket.status ?: 'unknown'
    def detail = params.detail ?: ''

    ticket.status = status
    ticket.deployResult = params.result ?: normalizeDeployResult(status)
    ticket.finishedAt = currentTime(config)
    ticket.approver = params.approver ?: ticket.approver ?: env.PROD_APPROVER ?: ''
    ticket.approveMethod = params.approveMethod ?: ticket.approveMethod ?: env.PROD_APPROVE_METHOD ?: ''
    ticket.approveComment = params.approveComment ?: ticket.approveComment ?: ''
    ticket.previousImage = params.previousImage ?: ticket.previousImage ?: ''
    ticket.failReason = detail ?: params.failReason ?: ticket.failReason ?: ''

    if (params.extraFields instanceof Map) {
        params.extraFields.each { k, v -> ticket[k] = v }
    }

    saveTicket(ticket, config)
    echo "📋 [发布单] ${ticketId} 最终状态：${ticket.status}${ticket.failReason ? ' | ' + ticket.failReason : ''}"
}

def recordApproval(Map params = [:]) {
    env.PROD_APPROVER = params.approver ?: env.PROD_APPROVER ?: ''
    env.PROD_APPROVE_METHOD = params.method ?: env.PROD_APPROVE_METHOD ?: 'jenkins_input'
}

def recordDeployResult(Map params = [:]) {
    def result = (params.result ?: 'unknown').toString()
    updateStatus(
        ticketId: params.ticketId ?: env.RELEASE_TICKET_ID,
        env: params.env ?: env.ENV,
        status: result,
        result: result,
        approver: params.approver ?: env.PROD_APPROVER ?: '',
        approveMethod: params.approveMethod ?: env.PROD_APPROVE_METHOD ?: '',
        previousImage: params.previousImage ?: '',
        detail: params.detail ?: ''
    )
}

def recordRollback(Map params = [:]) {
    updateStatus(
        ticketId: params.ticketId ?: env.RELEASE_TICKET_ID,
        env: params.env ?: env.ENV,
        status: 'rollback',
        result: 'rollback',
        approver: params.operator ?: env.PROD_APPROVER ?: env.BUILD_USER_ID ?: 'system',
        detail: params.reason ?: '执行回滚',
        extraFields: [
            rollbackReason  : params.reason ?: '',
            rollbackOperator: params.operator ?: env.PROD_APPROVER ?: env.BUILD_USER_ID ?: 'system'
        ]
    )
}

def getTicket(Map params = [:]) {
    def config = params.config ?: new com.devops.Config()
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID
    def targetEnv = (params.env ?: env.ENV ?: '').toString().trim().toLowerCase()
    if (!ticketId) return null
    return loadTicket(ticketId, config, targetEnv)
}

def listRecentTickets(Map params = [:]) {
    def config = params.config ?: new com.devops.Config()
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
                tickets << new JsonSlurper().parse(f)
            } catch (Exception ignored) {
                echo "⚠️ [发布单] 解析失败：${f.name}"
            }
        }
    } catch (Exception e) {
        echo "⚠️ [发布单] 查询失败：${e.getMessage()}"
    }

    return tickets
}

def buildTicketId(def config) {
    def tz = java.util.TimeZone.getTimeZone(config.IMAGE_TAG_TIMEZONE ?: 'Asia/Shanghai')
    def fmt = new java.text.SimpleDateFormat('yyyyMMdd')
    fmt.setTimeZone(tz)

    def dateStr = fmt.format(new Date())
    def jobSlug = sanitizeForId(env.JOB_NAME ?: 'job')
    def buildNumber = env.BUILD_NUMBER ?: System.currentTimeMillis().toString()
    return "${config.RELEASE_TICKET_PREFIX}-${dateStr}-${jobSlug}-${buildNumber}"
}

def saveTicket(Map ticket, def config) {
    def recordDir = "${config.RELEASE_RECORD_DIR}/${ticket.environment}"
    def filePath = "${recordDir}/${ticket.ticketId}.json"

    try {
        def dir = new File(recordDir)
        if (!dir.exists()) {
            dir.mkdirs()
        }

        def json = decodeJsonEscapedText(JsonOutput.prettyPrint(JsonOutput.toJson(ticket)))
        new File(filePath).write(json, 'UTF-8')
        echo "💾 [发布单] 已保存：${filePath}"
    } catch (Exception e) {
        echo "⚠️ [发布单] 保存失败：${e.getMessage()}"
    }
}

def loadTicket(String ticketId, def config, String targetEnv = '') {
    try {
        if (targetEnv?.trim()) {
            def file = new File("${config.RELEASE_RECORD_DIR}/${targetEnv}/${ticketId}.json")
            return file.exists() ? new JsonSlurper().parse(file) : null
        }

        def baseDir = new File(config.RELEASE_RECORD_DIR)
        if (!baseDir.exists()) return null

        def envDirs = baseDir.listFiles()?.findAll { it.isDirectory() } ?: []
        for (def envDir : envDirs) {
            def file = new File("${envDir.absolutePath}/${ticketId}.json")
            if (file.exists()) {
                return new JsonSlurper().parse(file)
            }
        }
    } catch (Exception e) {
        echo "⚠️ [发布单] 加载失败：${e.getMessage()}"
    }
    return null
}

def resolveBranchOrTag() {
    if (env.TRIGGER_TYPE == 'tag') {
        return env.TAG_NAME ?: env.GIT_TAG_NAME ?: env.GIT_BRANCH ?: env.ref ?: ''
    }
    return env.GIT_BRANCH ?: env.ref ?: env.BRANCH_NAME ?: env.TAG_NAME ?: ''
}

def normalizeDeployResult(String status) {
    if (status == 'success') return 'success'
    if (status == 'failed') return 'failed'
    if (status == 'rollback') return 'rollback'
    return ''
}

def sanitizeForId(String raw) {
    def value = raw.toString().trim()
    def safe = value.replaceAll('[^a-zA-Z0-9._-]', '-').replaceAll('-+', '-').replaceAll(/^[.-]+|[.-]+$/, '')
    return safe ?: 'job'
}

def currentTime(def config) {
    return new Date().format('yyyy-MM-dd HH:mm:ss', TimeZone.getTimeZone(config.IMAGE_TAG_TIMEZONE ?: 'Asia/Shanghai'))
}

def decodeJsonEscapedText(String json) {
    def slash = Character.toString((char) 92)
    def pattern = slash + slash + 'u' + '([0-9a-fA-F]{4})'
    def matcher = java.util.regex.Pattern.compile(pattern).matcher(json)
    def result = new StringBuffer()

    while (matcher.find()) {
        def decoded = String.valueOf((char) Integer.parseInt(matcher.group(1), 16))
        matcher.appendReplacement(result, java.util.regex.Matcher.quoteReplacement(decoded))
    }
    matcher.appendTail(result)
    return result.toString()
}
