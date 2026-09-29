// approvalStage.groovy — 审批门禁（Python 判断 + Jenkins input）

def call(Map params = [:]) {
    def environment = params.environment ?: env.ENV ?: 'prod'
    def approvers = params.approvers ?: env.APPROVERS ?: 'admin,devops,release-manager'

    echo "⏸️ 审批检查: ${environment}"

    def check = pythonCicd('approve', [
        env        : environment,
        environment: environment,
        workspace  : env.WORKSPACE
    ])

    if (check.data?.required) {
        def approver = input(
            message: "⚠️ ${environment.toUpperCase()} 环境发布审批\n" +
                     "应用: ${env.APP_NAME ?: env.JOB_NAME}\n" +
                     "镜像: ${env.FULL_IMAGE ?: env.IMAGE ?: 'unknown'}",
            ok: '✅ 确认发布',
            submitter: approvers,
            submitterParameter: 'APPROVER_NAME'
        )

        pythonCicd('release_ticket', [
            action  : 'record_approval',
            approver: approver,
            method  : 'jenkins_input',
            env     : environment
        ])
        env.PROD_APPROVER = approver
    }
}
