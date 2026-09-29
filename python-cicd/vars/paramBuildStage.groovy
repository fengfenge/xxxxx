// paramBuildStage.groovy — 参数化处理阶段（调 Python param_build）

def call(Map params = [:]) {
    def buildType = params.buildType ?: env.BUILD_TYPE ?: 'auto'
    def tag = params.tag ?: env.TAG_NAME ?: ''
    def branch = params.branch ?: env.BRANCH_NAME ?: env.GIT_BRANCH ?: ''
    def targetEnv = params.targetEnv ?: env.TARGET_ENV ?: 'auto'
    def deploy = params.deploy != null ? params.deploy : true
    def gitRepoUrl = params.gitRepoUrl ?: env.GIT_REPO_URL ?: ''
    def gitCredentialsId = params.gitCredentialsId ?: env.GIT_CREDENTIALS_ID ?: ''
    def k8sNamespace = params.k8sNamespace ?: env.K8S_NAMESPACE ?: ''
    def dockerfileContent = params.dockerfileContent ?: env.DOCKERFILE_CONTENT ?: ''
    def buildMessage = params.buildMessage ?: env.BUILD_MESSAGE ?: ''

    echo "📝 Param Build: type=${buildType}, targetEnv=${targetEnv}"

    pythonCicd('param_build', [
        build_type        : buildType,
        tag               : tag,
        branch            : branch,
        env               : targetEnv,
        deploy            : deploy,
        git_repo_url      : gitRepoUrl,
        git_credentials_id: gitCredentialsId,
        k8s_namespace     : k8sNamespace,
        dockerfile_content: dockerfileContent,
        build_message     : buildMessage,
        workspace         : env.WORKSPACE
    ])
}
