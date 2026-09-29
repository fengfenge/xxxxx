// 参数化构建：仅根据 UI 参数写入环境变量，不执行 checkout / pipelineInit（由 Jenkinsfile 分阶段调用）
def call(Map params = [:]) {
    def buildType = params.buildType ?: 'auto'
    def targetBranch = params.branch ?: ''
    def targetTag = params.tag ?: ''
    def targetEnv = params.env ?: ''
    def shouldDeploy = params.deploy ?: true
    def gitRepoUrl = params.gitRepoUrl
    def gitCredentialsId = params.gitCredentialsId

    echo "[参数化构建] 开始处理构建参数..."

    if (buildType == 'tag' && targetTag) {
        env.TAG_NAME = targetTag
        env.BRANCH_NAME = ''
        echo "[参数化构建] 标签构建模式：${targetTag}"
    } else if (buildType == 'branch' && targetBranch) {
        env.BRANCH_NAME = targetBranch
        env.TAG_NAME = ''
        echo "[参数化构建] 分支构建模式：${targetBranch}"
    } else {
        // auto 模式：如果传入了 branch 参数则手动设置
        if (params.branch?.trim()) {
            env.BRANCH_NAME = params.branch.trim()
        }
        env.TAG_NAME = ''
        echo "[参数化构建] 自动模式${params.branch?.trim() ? "，手动指定分支 ${env.BRANCH_NAME}" : "，使用 Jenkins 触发值"}"        
        // echo "[参数化构建] 自动模式，使用 Jenkins 触发值"
    }

    if (targetEnv) {
        env.FORCED_DEPLOY_ENV = targetEnv
        echo "[参数化构建] 强制指定环境（将在 pipelineInit 中生效）：${targetEnv}"
    } else {
        env.FORCED_DEPLOY_ENV = ''
    }

    env.SHOULD_DEPLOY = "${shouldDeploy}"
    echo "[参数化构建] 部署开关：${shouldDeploy ? 'ENABLED' : 'DISABLED'}"

    if (gitRepoUrl != null) {
        env.GIT_REPO_URL = gitRepoUrl.toString().trim()
    }
    if (gitCredentialsId != null) {
        env.GIT_CREDENTIALS_ID = gitCredentialsId.toString().trim()
    }

    // K8s 命名空间：由 Pipeline 参数传入，必填
    if (!params.k8sNamespace?.trim()) {
        error "❌ [参数化构建] 未指定 K8s 命名空间。请在 Pipeline 参数中设置 K8S_NAMESPACE。"
    }
    env.K8S_NAMESPACE = params.k8sNamespace.trim()
    echo "[参数化构建] K8s 命名空间：${env.K8S_NAMESPACE}"

    echo "[参数化构建] 参数处理完成（请在此之后 gitCheckout 并调用 pipelineInit）"
}
