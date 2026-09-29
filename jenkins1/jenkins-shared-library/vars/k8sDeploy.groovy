// K8s 部署 - 集成发布记录
// 部署前获取当前镜像版本（用于回滚），部署后记录发布结果

def call() {
    echo "🚀 [部署] 开始部署到 Kubernetes..."

    def config = new com.devops.Config()
    def deployEnv = env.ENV ?: 'dev'
    def targetNamespace = env.K8S_NAMESPACE?.trim() ?: config.K8S_DEPLOY_NAMESPACE
    def imageRef = env.IMAGE
    def deployName = env.JOB_NAME
    def containerName = env.JOB_NAME
    def credentialsId = config.K8S_CREDENTIALS[deployEnv]
    def ticketId = env.RELEASE_TICKET_ID ?: ''
    def previousImage = ''

    if (!credentialsId) {
        error "❌ 未找到环境 ${deployEnv} 的 kubeconfig 凭据"
    }

    // 更新发布单状态为部署中
    if (ticketId) {
        releaseTicket.updateStatus(
            ticketId: ticketId,
            status: 'deploying',
            action: 'deploy_start',
            user: env.BUILD_USER_ID ?: 'system',
            detail: "开始部署到 ${deployEnv} 环境"
        )
    }

    try {
        withCredentials([file(credentialsId: credentialsId, variable: 'KUBECONFIG_FILE')]) {
            // 获取当前运行的镜像版本（用于发布记录和回滚参考）
            previousImage = sh(
                script: """
                    export KUBECONFIG=${KUBECONFIG_FILE}
                    kubectl get deployment/${deployName} -n ${targetNamespace} \
                        -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || echo ""
                """,
                returnStdout: true
            ).trim()
            if (previousImage) {
                echo "📋 当前运行镜像：${previousImage}"
            }

            // 执行部署
            sh """
                export KUBECONFIG=${KUBECONFIG_FILE}
                echo "📋 当前 K8s 上下文："
                kubectl config current-context
                echo "📋 本次部署命名空间：${targetNamespace}"
                
                echo "🔄 开始部署应用：${imageRef} (deployment=${deployName}, container=${containerName})"
                kubectl set image deployment/${deployName} ${containerName}=${imageRef} -n ${targetNamespace}
                
                echo "⏳ 等待部署完成..."
                kubectl rollout status deployment/${deployName} -n ${targetNamespace} --timeout=5m
                
                echo "✅ 部署成功！"
                kubectl get pods -n ${targetNamespace} -l app=${deployName}
            """
        }

        // 记录发布成功
        if (ticketId) {
            releaseTicket.recordDeployResult(
                ticketId: ticketId,
                result: 'success'
            )
        }

        // 创建发布记录
        releaseRecord(
            serviceName: env.JOB_NAME,
            env: deployEnv,
            imageTag: env.IMAGE_TAG,
            image: imageRef,
            ticketId: ticketId,
            result: 'success',
            approver: env.PROD_APPROVER ?: '',
            previousImage: previousImage
        )

        // 发送部署成功通知（通过企业微信审批模块）
        wecomApprove.sendDeployResultNotification(
            status: 'SUCCESS',
            env: deployEnv,
            ticketId: ticketId,
            serviceName: env.JOB_NAME,
            imageTag: env.IMAGE_TAG,
            approver: env.PROD_APPROVER
        )

        echo "✅ [部署] 部署成功！发布单：${ticketId}"

    } catch (Exception e) {
        // 记录发布失败
        if (ticketId) {
            releaseTicket.recordDeployResult(
                ticketId: ticketId,
                result: 'failed',
                detail: e.getMessage()
            )
        }

        // 发送部署失败通知
        wecomApprove.sendDeployResultNotification(
            status: 'FAILED',
            env: deployEnv,
            ticketId: ticketId,
            serviceName: env.JOB_NAME,
            imageTag: env.IMAGE_TAG,
            approver: env.PROD_APPROVER
        )

        echo "❌ [部署] 部署失败: ${e.getMessage()}"
        error "部署终止。"
    }
}
