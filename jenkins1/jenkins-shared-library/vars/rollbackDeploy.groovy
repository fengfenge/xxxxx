// 回滚部署功能 - 支持手动指定参数
// 支持回滚到上一版本或指定版本
// 参数说明：
//   env - 目标环境（必填），如：prod, uat, test, dev
//   deploymentName - Deployment名称（可选，默认为JOB_NAME）
//   revision - 回滚到指定版本（可选，不指定则回滚到上一版本）
//   namespace - K8s命名空间（可选，不填则用 env.K8S_NAMESPACE 或 Config.K8S_DEPLOY_NAMESPACE）

def resolveK8sNamespace(Map params, def config) {
    def p = params.namespace?.toString()?.trim()
    if (p) {
        return p
    }
    def fromEnv = env.K8S_NAMESPACE?.trim()
    if (fromEnv) {
        return fromEnv
    }
    return config.K8S_DEPLOY_NAMESPACE
}

def call(Map params = [:]) {
    def config = new com.devops.Config()
    
    // 1. 参数解析和默认值设置
    def targetEnv = params.env ?: env.ENV
    def deploymentName = params.deploymentName ?: env.JOB_NAME
    def revision = params.revision ?: null
    def namespace = resolveK8sNamespace(params, config)
    
    echo "↩️ [回滚] 开始执行回滚操作..."
    
    // 2. 参数验证
    if (!targetEnv) {
        error "❌ [回滚] 必须指定目标环境。参数: env"
    }
    
    if (!deploymentName) {
        error "❌ [回滚] 必须指定 Deployment 名称。参数: deploymentName"
    }
    
    // 3. 验证环境是否支持回滚
    if (!config.K8S_CREDENTIALS.containsKey(targetEnv)) {
        error "❌ [回滚] 不支持的环境: ${targetEnv}。支持的环境: ${config.K8S_CREDENTIALS.keySet()}"
    }
    
    // 4. 获取 K8s 凭据
    def credentialsId = config.K8S_CREDENTIALS[targetEnv]
    
    // 5. 输出回滚信息
    echo "=========================================="
    echo "回滚环境：${targetEnv}"
    echo "Deployment：${deploymentName}"
    echo "命名空间：${namespace}"
    echo "回滚版本：${revision ? "版本 ${revision}" : "上一版本"}"
    echo "=========================================="
    
    // 6. 执行回滚
    try {
        withCredentials([file(credentialsId: credentialsId, variable: 'KUBECONFIG_FILE')]) {
            def rollbackCmd = "kubectl rollout undo deployment/${deploymentName} -n ${namespace}"
            if (revision) {
                rollbackCmd += " --to-revision=${revision}"
            }
            
            sh """
                export KUBECONFIG=${KUBECONFIG_FILE}
                
                echo "📋 当前 K8s 上下文："
                kubectl config current-context
                
                echo "📋 回滚前状态："
                kubectl get deployments -n ${namespace} ${deploymentName} -o wide
                
                echo "📋 最近版本历史："
                kubectl rollout history deployment/${deploymentName} -n ${namespace} --max=5
                
                echo "🔄 正在执行回滚..."
                ${rollbackCmd}
                
                echo "⏳ 等待回滚完成..."
                kubectl rollout status deployment/${deploymentName} -n ${namespace} --timeout=5m
                
                echo "✅ [回滚] 操作完成！"
                
                echo "📋 回滚后状态："
                kubectl get deployments -n ${namespace} ${deploymentName} -o wide
                
                echo "📋 当前版本："
                kubectl rollout history deployment/${deploymentName} -n ${namespace} --revision=1
            """
        }
    } catch (Exception e) {
        echo "❌ [回滚] 回滚失败: ${e.getMessage()}"
        error "回滚操作终止。"
    }
    
    echo "↩️ [回滚] 回滚操作已完成"
}

// 获取指定 Deployment 的版本历史
def getHistory(Map params = [:]) {
    def config = new com.devops.Config()
    def targetEnv = params.env ?: env.ENV
    def deploymentName = params.deploymentName ?: env.JOB_NAME
    def namespace = resolveK8sNamespace(params, config)
    def maxRevisions = params.maxRevisions ?: 5
    
    if (!targetEnv || !deploymentName) {
        error "❌ 必须指定环境和 Deployment 名称"
    }
    
    def credentialsId = config.K8S_CREDENTIALS[targetEnv]
    
    withCredentials([file(credentialsId: credentialsId, variable: 'KUBECONFIG_FILE')]) {
        def history = sh(
            script: """
                export KUBECONFIG=${KUBECONFIG_FILE}
                kubectl rollout history deployment/${deploymentName} -n ${namespace} --max=${maxRevisions}
            """,
            returnStdout: true
        ).trim()
        
        echo "📋 Deployment ${deploymentName} 的版本历史："
        echo history
        
        return history
    }
}

// 获取当前运行的版本
def getCurrentRevision(Map params = [:]) {
    def config = new com.devops.Config()
    def targetEnv = params.env ?: env.ENV
    def deploymentName = params.deploymentName ?: env.JOB_NAME
    def namespace = resolveK8sNamespace(params, config)
    
    if (!targetEnv || !deploymentName) {
        error "❌ 必须指定环境和 Deployment 名称"
    }
    
    def credentialsId = config.K8S_CREDENTIALS[targetEnv]
    
    withCredentials([file(credentialsId: credentialsId, variable: 'KUBECONFIG_FILE')]) {
        def revision = sh(
            script: """
                export KUBECONFIG=${KUBECONFIG_FILE}
                kubectl rollout history deployment/${deploymentName} -n ${namespace} | grep -A1 "REVISION" | tail -1 | awk '{print \$1}'
            """,
            returnStdout: true
        ).trim()
        
        echo "📋 当前版本：${revision}"
        return revision
    }
}