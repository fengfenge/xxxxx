// rollbackStage.groovy — K8s 回滚（调 Python）

def call(Map params = [:]) {
    def action = params.action ?: env.ROLLBACK_ACTION ?: 'rollback'
    def environment = params.environment ?: env.ENV ?: 'prod'
    def namespace = params.namespace ?: env.K8S_NAMESPACE ?: ''
    def deploymentName = params.deploymentName ?: env.DEPLOYMENT_NAME ?: env.JOB_NAME
    def revision = params.revision ?: env.REVISION ?: ''
    def maxRevisions = params.maxRevisions ?: env.MAX_REVISIONS ?: '10'
    def reason = params.reason ?: env.ROLLBACK_REASON ?: ''
    def relatedTicketId = params.relatedTicketId ?: env.RELATED_TICKET_ID ?: ''
    def operator = params.operator ?: env.ROLLBACK_OPERATOR ?: env.BUILD_USER_ID ?: 'system'

    echo "↩️ Rollback: ${deploymentName} → ${environment}/${namespace} (action=${action})"

    def runStep = {
        pythonCicd('rollback', [
            action           : action,
            env              : environment,
            namespace        : namespace,
            deployment_name  : deploymentName,
            revision         : revision,
            max_revisions    : maxRevisions,
            reason           : reason,
            related_ticket_id: relatedTicketId,
            operator         : operator,
            workspace        : env.WORKSPACE
        ])
    }

    if (action in ['history', 'rollback']) {
        withCredentials([file(credentialsId: "kubeconfig-${environment}", variable: 'KUBECONFIG_FILE')]) {
            runStep()
        }
    } else {
        runStep()
    }
}
