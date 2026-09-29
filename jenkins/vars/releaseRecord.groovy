// 发布记录管理 - 持久化部署历史，支持查询和回滚追溯
// 与 releaseTicket 配合，发布记录是面向运维的汇总视图

import groovy.json.JsonOutput
import groovy.json.JsonSlurper

// 创建发布记录（部署成功后调用）
def call(Map params = [:]) {
    def config = new com.devops.Config()
    def serviceName = params.serviceName ?: env.JOB_NAME ?: 'unknown'
    def targetEnv = params.env ?: env.ENV ?: 'unknown'
    def imageTag = params.imageTag ?: env.IMAGE_TAG ?: ''
    def image = params.image ?: env.IMAGE ?: ''
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID ?: ''
    def result = params.result ?: 'success'
    def approver = params.approver ?: env.PROD_APPROVER ?: ''
    def triggerType = params.triggerType ?: env.TRIGGER_TYPE ?: 'unknown'
    def triggerUser = params.triggerUser ?: env.BUILD_USER_ID ?: 'system'
    def deployDuration = params.deployDuration ?: ''
    def buildUrl = params.buildUrl ?: env.BUILD_URL ?: ''
    def previousImage = params.previousImage ?: ''

    def now = new Date().format("yyyy-MM-dd HH:mm:ss", TimeZone.getTimeZone(config.IMAGE_TAG_TIMEZONE))

    def record = [
        recordId: "REC-${System.currentTimeMillis()}",
        ticketId: ticketId,
        serviceName: serviceName,
        environment: targetEnv,
        imageTag: imageTag,
        image: image,
        previousImage: previousImage,
        triggerType: triggerType,
        triggerUser: triggerUser,
        approver: approver,
        result: result,
        deployDuration: deployDuration,
        deployTime: now,
        buildUrl: buildUrl,
        isRolledBack: false,
        rollbackTicketId: ''
    ]

    // 保存到发布记录索引文件
    appendToIndex(record, config)

    echo "📝 [发布记录] 已记录：${serviceName} | ${targetEnv} | ${imageTag} | ${result}"
    return record
}

// 创建回滚记录
def recordRollback(Map params = [:]) {
    def config = new com.devops.Config()
    def serviceName = params.serviceName ?: env.JOB_NAME ?: 'unknown'
    def targetEnv = params.env ?: env.ENV ?: 'unknown'
    def reason = params.reason ?: ''
    def operator = params.operator ?: env.BUILD_USER_ID ?: 'system'
    def rollbackFromTicket = params.rollbackFromTicket ?: ''
    def currentImage = params.currentImage ?: ''
    def rollbackImage = params.rollbackImage ?: ''

    def now = new Date().format("yyyy-MM-dd HH:mm:ss", TimeZone.getTimeZone(config.IMAGE_TAG_TIMEZONE))

    def record = [
        recordId: "ROLLBACK-${System.currentTimeMillis()}",
        ticketId: rollbackFromTicket,
        serviceName: serviceName,
        environment: targetEnv,
        action: 'rollback',
        currentImage: currentImage,
        rollbackImage: rollbackImage,
        reason: reason,
        operator: operator,
        rollbackTime: now,
        buildUrl: env.BUILD_URL ?: ''
    ]

    // 保存回滚记录
    appendToIndex(record, config)

    // 标记原发布记录为已回滚
    if (rollbackFromTicket) {
        markTicketAsRolledBack(rollbackFromTicket, record.recordId, config)
    }

    echo "📝 [回滚记录] 已记录：${serviceName} | ${targetEnv} | 原发布单：${rollbackFromTicket}"
    return record
}

// 查询服务在指定环境的发布历史
def getHistory(Map params = [:]) {
    def config = new com.devops.Config()
    def serviceName = params.serviceName ?: env.JOB_NAME ?: ''
    def targetEnv = params.env ?: env.ENV ?: ''
    def limit = params.limit ?: 20

    def records = loadIndex(config)

    // 过滤
    if (serviceName) {
        records = records.findAll { it.serviceName == serviceName }
    }
    if (targetEnv) {
        records = records.findAll { it.environment == targetEnv }
    }

    // 按时间倒序
    records = records.sort { -it.deployTime.hashCode() }.take(limit)

    return records
}

// 获取服务在指定环境的当前运行版本
def getCurrentDeployment(Map params = [:]) {
    def config = new com.devops.Config()
    def serviceName = params.serviceName ?: env.JOB_NAME ?: ''
    def targetEnv = params.env ?: env.ENV ?: ''

    def records = loadIndex(config)

    // 找到最近一次成功部署
    def latestSuccess = records.findAll {
        it.serviceName == serviceName &&
        it.environment == targetEnv &&
        it.result == 'success' &&
        !it.isRolledBack
    }.sort { -it.deployTime.hashCode() }

    return latestSuccess ? latestSuccess[0] : null
}

// ========== 内部方法 ==========

// 追加记录到索引文件
def appendToIndex(Map record, def config) {
    def indexPath = "${config.RELEASE_RECORD_DIR}/deploy-index.json"

    try {
        def dir = new File(config.RELEASE_RECORD_DIR)
        if (!dir.exists()) {
            dir.mkdirs()
        }

        def records = []
        def indexFile = new File(indexPath)
        if (indexFile.exists()) {
            try {
                records = new JsonSlurper().parse(indexFile) as List
            } catch (Exception e) {
                echo "⚠️ [发布记录] 索引文件解析失败，将重建：${e.getMessage()}"
                records = []
            }
        }

        records << record

        // 写回文件
        indexFile.write(JsonOutput.prettyPrint(JsonOutput.toJson(records)), 'UTF-8')
    } catch (Exception e) {
        echo "⚠️ [发布记录] 写入索引失败：${e.getMessage()}"
    }
}

// 加载索引文件
def loadIndex(def config) {
    def indexPath = "${config.RELEASE_RECORD_DIR}/deploy-index.json"

    try {
        def indexFile = new File(indexPath)
        if (indexFile.exists()) {
            return new JsonSlurper().parse(indexFile) as List
        }
    } catch (Exception e) {
        echo "⚠️ [发布记录] 加载索引失败：${e.getMessage()}"
    }
    return []
}

// 标记发布单为已回滚
def markTicketAsRolledBack(String ticketId, String rollbackRecordId, def config) {
    try {
        def baseDir = new File(config.RELEASE_RECORD_DIR)
        if (!baseDir.exists()) return

        baseDir.listFiles()?.findAll { it.isDirectory() }?.each { envDir ->
            def filePath = "${envDir.absolutePath}/${ticketId}.json"
            def file = new File(filePath)
            if (file.exists()) {
                def ticket = new JsonSlurper().parse(file) as Map
                ticket.isRolledBack = true
                ticket.rollbackRecordId = rollbackRecordId
                file.write(JsonOutput.prettyPrint(JsonOutput.toJson(ticket)), 'UTF-8')
            }
        }
    } catch (Exception e) {
        echo "⚠️ [发布记录] 标记回滚状态失败：${e.getMessage()}"
    }
}
