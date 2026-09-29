// gitCheckoutStage.groovy — Git 检出（Groovy 轻编排，Jenkins checkout 插件）

def call(Map params = [:]) {
    def credentialsId = params.credentialsId ?: env.GIT_CREDENTIALS_ID ?: 'gitlab-credentials'
    def branch = params.branch ?: env.BRANCH_NAME ?: env.GIT_BRANCH ?: 'main'
    branch = branch.replace('refs/heads/', '')
    def repoUrl = params.repoUrl ?: env.GIT_REPO_URL ?: env.GIT_URL

    if (!repoUrl && scm != null) {
        repoUrl = scm.userRemoteConfigs?.getAt(0)?.url
        if (!credentialsId) {
            credentialsId = scm.userRemoteConfigs?.getAt(0)?.credentialsId ?: credentialsId
        }
    }

    echo "📥 Git 检出: ${repoUrl} @ ${branch}"

    if (!repoUrl && scm != null) {
        checkout scm
    } else if (!repoUrl) {
        error '❌ 未配置 Git 仓库地址，请在 Job SCM 或参数中设置 GIT_REPO_URL'
    } else {
        checkout([
            $class: 'GitSCM',
            branches: [[name: "*/${branch}"]],
            extensions: [[$class: 'CloneOption', timeout: 30]],
            userRemoteConfigs: [[url: repoUrl, credentialsId: credentialsId]]
        ])
    }

    sh "git log -1 --pretty=format:'%h %s (%an)'"
    env.GIT_COMMIT = sh(returnStdout: true, script: 'git rev-parse HEAD').trim()
}
