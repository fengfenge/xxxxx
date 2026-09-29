// 代码拉取：由 Jenkins 参数指定仓库与凭据（REPOSITORY + GIT_CREDENTIALS_ID + 分支/标签）
// 不再依赖 resources/microservices.yaml。BUILD_TYPE=auto 且未填仓库时，回退为 checkout scm（需 Pipeline/Job 已配置 SCM）
// 支持 PR/MR 合并模拟（与 CHANGE_ID 等环境变量配合）
// 使用//注释

def call(Map params = [:]) {
    echo "📥 [代码] 开始拉取源代码..."

    def buildType = (params.buildType ?: 'auto').toString()
    def repoUrl = (params.repoUrl ?: env.GIT_REPO_URL ?: '').toString().trim()
    def credentialsId = (params.credentialsId ?: env.GIT_CREDENTIALS_ID ?: '').toString().trim()
    def branch = (params.branch ?: env.BRANCH_NAME ?: env.GIT_BRANCH ?: 'main').toString()
    def tag = (params.tag ?: env.TAG_NAME ?: env.GIT_TAG_NAME ?: '').toString().trim()

    // 是否为 PR/MR 合并
    def isPullRequest = (env.CHANGE_ID != null && env.CHANGE_ID != "")

    if (!repoUrl && scm != null) {
        repoUrl = scm.userRemoteConfigs?.getAt(0)?.url
        if (!credentialsId) {
            credentialsId = scm.userRemoteConfigs?.getAt(0)?.credentialsId
        }
    }

    if (!repoUrl) {
        if (buildType == 'auto' && scm != null) {
            echo "ℹ️ [代码] 未指定 GIT_REPO_URL，使用 Job / Multibranch 的 Pipeline SCM"
            checkout scm
            sh "git log -1 --pretty=format:'%h %s (%an)'"
            echo "✅ [代码] 代码拉取成功（checkout scm）。"
            return
        }
        error "❌ [代码] 请填写参数 GIT_REPO_URL，或在 Pipeline 中配置 SCM（BUILD_TYPE=auto 时可省略 GIT_REPO_URL）。"
    }

    def checkoutTarget
    // 标签构建：直接检出标签
    if (buildType == 'tag' && tag) {
        checkoutTarget = "refs/tags/${tag}"
    }
    // PR/MR 合并：检出目标分支
    else if (isPullRequest) {
        checkoutTarget = "*/${env.CHANGE_TARGET}"
    }
    // 分支构建：检出分支
    else {
        checkoutTarget = "*/${branch}"
    }

    // 设置超时时间为 30 秒
    def extensions = [
        [$class: 'CloneOption', timeout: 30]
    ]

    echo "=========================================="
    echo "仓库: ${repoUrl}"
    echo "凭据ID: ${credentialsId ?: '（未设置）'}"
    echo "BUILD_TYPE: ${buildType}"
    echo "检出目标: ${checkoutTarget}"
    echo "PR/MR: ${isPullRequest ? "是 (#${env.CHANGE_ID})" : "否"}"
    echo "标签名称: ${tag ?: '未指定'}"
    echo "=========================================="

    def retryCount = 3
    for (int i = 0; i < retryCount; i++) {
        try {
            def checkoutConfig = [
                $class                           : 'GitSCM',
                branches                         : [[name: checkoutTarget]],
                doGenerateSubmoduleConfigurations: false,
                extensions                       : extensions,
                userRemoteConfigs                : [[
                    credentialsId: credentialsId ?: '',
                    url          : repoUrl,
                    refspec      : isPullRequest ? "+refs/heads/${env.CHANGE_TARGET}:refs/remotes/origin/${env.CHANGE_TARGET} +refs/pull/${env.CHANGE_ID}/head:refs/remotes/origin/pr_${env.CHANGE_ID}" : ""
                ]]
            ]

            checkout(checkoutConfig)

            if (isPullRequest) {
                echo "🔀 [代码] 检测到合并请求 (#${env.CHANGE_ID})，正在模拟合并 ${env.CHANGE_TARGET}..."
                sh """
                    git config user.name "Jenkins Bot"
                    git config user.email "jenkins@devops.local"
                    git fetch origin pull/${env.CHANGE_ID}/head:pr_${env.CHANGE_ID}
                    git checkout -f pr_${env.CHANGE_ID}
                    git merge --no-edit origin/${env.CHANGE_TARGET} || {
                        echo "❌ 合并冲突，请解决冲突后重新提交"
                        exit 1
                    }
                """
            }

            sh "git log -1 --pretty=format:'%h %s (%an)'"
            echo "✅ [代码] 代码拉取成功。"
            return
        } catch (Exception e) {
            echo "⚠️ [代码] 拉取失败 (尝试 ${i + 1}/${retryCount}): ${e.getMessage()}"
            if (i == retryCount - 1) {
                error "❌ [代码] 拉取代码最终失败，请检查网络、凭据或分支/标签是否存在。"
            }
            sleep(5)
        }
    }
}
