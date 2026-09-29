// K8s 部署，并记录发布状态。

def call() {
    echo "INFO [部署] 开始部署到 Kubernetes"

    def config = new com.devops.Config()
    def deployEnv = (env.ENV ?: 'dev').toString().trim().toLowerCase()
    def targetNamespace = env.K8S_NAMESPACE?.trim()
    if (!targetNamespace) {
        error "[部署] K8S_NAMESPACE 不能为空"
    }

    def imageRef = env.IMAGE
    def deployName = env.JOB_NAME
    def containerName = env.JOB_NAME
    def credentialsId = config.K8S_CREDENTIALS[deployEnv]
    def ticketId = env.RELEASE_TICKET_ID ?: ''
    def previousImage = ''
    def approver = (env.PROD_APPROVER ?: '').toString().trim()

    if (!credentialsId) {
        error "[部署] 未找到环境 ${deployEnv} 的 kubeconfig 凭据"
    }

    try {
        withCredentials([file(credentialsId: credentialsId, variable: 'KUBECONFIG_FILE')]) {
            previousImage = sh(
                script: """
                    export KUBECONFIG=${KUBECONFIG_FILE}
                    kubectl get deployment/${deployName} -n ${targetNamespace} \\
                        -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || echo ""
                """,
                returnStdout: true
            ).trim()

            sh """
                export KUBECONFIG=${KUBECONFIG_FILE}
                kubectl config current-context
                kubectl set image deployment/${deployName} ${containerName}=${imageRef} -n ${targetNamespace}
                kubectl rollout status deployment/${deployName} -n ${targetNamespace} --timeout=5m
                kubectl get pods -n ${targetNamespace} -l app=${deployName}
            """
        }

        if (!approver && ticketId) {
            def ticket = releaseTicket.getTicket(ticketId: ticketId, env: deployEnv)
            approver = (ticket?.approver ?: ticket?.approvedBy ?: '').toString().trim()
        }

        if (ticketId) {
            releaseTicket.recordDeployResult(
                ticketId: ticketId,
                env: deployEnv,
                result: 'success',
                approver: approver,
                approveMethod: env.PROD_APPROVE_METHOD ?: '',
                previousImage: previousImage
            )
        }

        releaseRecord(
            serviceName: env.JOB_NAME,
            env: deployEnv,
            imageTag: env.IMAGE_TAG,
            image: imageRef,
            ticketId: ticketId,
            result: 'success',
            approver: approver,
            previousImage: previousImage
        )

        echo "INFO [部署] 部署成功，发布单=${ticketId}"
    } catch (Exception e) {
        if (ticketId) {
            releaseTicket.recordDeployResult(
                ticketId: ticketId,
                env: deployEnv,
                result: 'failed',
                approver: approver,
                approveMethod: env.PROD_APPROVE_METHOD ?: '',
                previousImage: previousImage,
                detail: e.getMessage()
            )
        }

        echo "ERROR [部署] ${e.getMessage()}"
        error "部署终止"
    }
}
