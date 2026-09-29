// 审批门禁 - 支持企业微信审批 + Jenkins input 双模式
// uat/prod 环境需要审批，dev/test 环境自动通过

def call(Map params = [:]) {
    def config = new com.devops.Config()
    def targetEnv = params.env ?: env.ENV ?: 'unknown'
    def ticketId = params.ticketId ?: env.RELEASE_TICKET_ID ?: ''

    // 检查是否需要审批
    if (!config.isApprovalRequired(targetEnv)) {
        echo "ℹ️ [审批] ${targetEnv} 环境无需审批，自动通过"

        // 自动审批：更新发布单状态
        if (ticketId) {
            releaseTicket.recordApproval(
                ticketId: ticketId,
                approver: 'auto',
                method: 'auto',
                comment: "${targetEnv} 环境自动审批"
            )
        }
        return
    }

    // 需要审批的环境（uat/prod）
    echo "🔐 [审批] ${targetEnv.toUpperCase()} 环境需要审批，启动审批流程..."

    // 更新发布单状态为待审批
    if (ticketId) {
        releaseTicket.updateStatus(
            ticketId: ticketId,
            status: 'pending',
            action: 'approval_requested',
            user: env.BUILD_USER_ID ?: 'system',
            detail: "请求${targetEnv.toUpperCase()}环境审批"
        )
    }

    // 调用企业微信审批流程
    def result = wecomApprove(
        env: targetEnv,
        ticketId: ticketId,
        serviceName: env.JOB_NAME,
        imageTag: env.IMAGE_TAG,
        image: env.IMAGE,
        triggerType: env.TRIGGER_TYPE,
        triggerUser: env.BUILD_USER_ID ?: 'system',
        buildUrl: env.BUILD_URL,
        mode: params.mode ?: config.WECOM_APPROVE_MODE ?: 'simple'
    )

    echo "✅ [审计] 审批通过！审批人：${result.approver}，方式：${result.method}，时间：${new Date()}"
}
