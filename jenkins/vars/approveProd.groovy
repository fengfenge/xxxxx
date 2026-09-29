// 审批门禁。
// dev/test：无需审批
// uat/prod：人工审批

def call(Map params = [:]) {
    def config = new com.devops.Config()
    def targetEnv = (params.env ?: env.ENV ?: 'unknown').toString().trim().toLowerCase()
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID ?: ''

    if (!config.isApprovalRequired(targetEnv)) {
        echo "INFO [审批] ${targetEnv} 环境无需审批，跳过审批阶段"
        return [approver: '', method: 'skip']
    }

    echo "INFO [审批] ${targetEnv.toUpperCase()} 环境需要人工审批"

    def result = wecomApprove(
        env: targetEnv,
        ticketId: ticketId,
        serviceName: env.JOB_NAME,
        imageTag: env.IMAGE_TAG,
        image: env.IMAGE,
        triggerType: env.TRIGGER_TYPE,
        triggerUser: env.BUILD_USER_ID ?: 'system',
        buildUrl: env.BUILD_URL,
        buildMessage: env.BUILD_MESSAGE ?: '',
        mode: params.mode ?: config.WECOM_APPROVE_MODE ?: 'simple'
    )

    def approver = result?.approver?.toString()?.trim()
    if (!approver) {
        error "[审批] ${targetEnv.toUpperCase()} 环境审批通过但未获取到审批人"
    }

    env.PROD_APPROVER = approver
    env.PROD_APPROVE_METHOD = result.method ?: ''
    echo "INFO [审批] 审批通过，审批人：${approver}，方式：${result.method}"
    return result
}
