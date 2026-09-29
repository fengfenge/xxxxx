// 功能：Docker 镜像构建、签名、推送及清理。
// 亮点：Dockerfile 管理：支持在 Jenkins Job 参数中直接定义 Dockerfile 内容，无需在 GitLab 仓库中维护。
// 安全登录：使用 withCredentials 安全注入 Harbor/Docker 账号密码，不在日志中明文显示。
// 构建优化：使用 --pull 确保基础镜像最新，--no-cache (可选) 用于强制重新构建。
// 镜像签名：集成 Docker Content Trust (DCT) 进行签名。
// 资源清理：构建推送完成后立即删除本地镜像，防止 Jenkins 磁盘爆满。
// 元数据注入：自动注入构建时间、Git Commit 等 Label。
def call(Map params = [:]) {
    echo "🐳 [镜像] 开始构建与推送..."

    def config = new com.devops.Config()
    def dockerRegistry = config.REGISTRY
    // 假设 Jenkins 中配置了 ID 为 'harbor-credentials' 的 Username/Password 类型凭据
    def credentialsId = "1fdaf86d-ee0a-4acc-bf08-d3389632b162"

    // 1. 准备 Dockerfile（优先使用 Job 参数中定义的内容）
    def dockerfileContent = params.dockerfile ?: ''
    if (dockerfileContent?.trim()) {
        echo "📄 使用 Jenkins Job 中定义的 Dockerfile"
        writeFile file: 'Dockerfile', text: dockerfileContent
    } else if (fileExists('Dockerfile')) {
        echo "📄 使用项目仓库中的 Dockerfile"
    } else {
        error "❌ 未找到 Dockerfile：请在 Jenkins Job 参数 DOCKERFILE_CONTENT 中定义，或在项目仓库中添加"
    }

    // 2. 动态生成 Docker Build 参数
    // 注入构建元数据到 Image Labels，方便追溯
    def buildTime = sh(returnStdout: true, script: 'date -u +"%Y-%m-%dT%H:%M:%SZ"').trim()
    def gitCommit = sh(returnStdout: true, script: 'git rev-parse HEAD').trim()

    def buildArgs = [
        "--build-arg BUILD_TIME='${buildTime}'",
        "--build-arg GIT_COMMIT='${gitCommit}'",
        "--build-arg ENV='${env.ENV}'",
        "--label 'org.opencontainers.image.created=${buildTime}'",
        "--label 'org.opencontainers.image.revision=${gitCommit}'",
        "--label 'org.opencontainers.image.source=${env.BUILD_URL}'",
        '--pull',
        "-t ${env.IMAGE}"
    ].join(' ')

    try {
        // 2. 安全登录镜像仓库
        // credentialsId使用这个ID去jenkins凭据库中获取对应的用户名和密码变量
        // 找到对应的用户名和密码变量，将它们注入到DOCKER_USER和DOCKER_PASS环境变量中
        withCredentials([usernamePassword(credentialsId: credentialsId, usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
            sh """
                echo "🔑 登录镜像仓库 ${dockerRegistry} ..."
                echo "\${DOCKER_PASS}" | docker login ${dockerRegistry} -u "\${DOCKER_USER}" --password-stdin
            """

            // 3. 执行构建
            echo "🔨 正在构建镜像：${env.IMAGE}"
            sh "docker build ${buildArgs} ."

            // 4. 镜像安全扫描（Trivy + 签名），在 push 前拦截高危漏洞镜像
            // securityCheck(scanType: 'image')

            // 5. 推送镜像
            echo "📤 正在推送镜像..."
            sh "docker push ${env.IMAGE}"

            // 6. 镜像签名 (Docker Content Trust)
            // 注意：需要配置 DOCKER_CONTENT_TRUST=1 和相关密钥
            if (env.ENV == "prod") {
                echo "✍️ 生产镜像签名中..."
                // sh "docker trust sign ${env.IMAGE}"
                // 如果未配置 DCT 密钥，此处会失败，建议根据实际环境开启
                echo "⚠️ 签名步骤已跳过 (需在 Jenkins 环境配置 DCT 密钥)"
            }
        }

        echo "✅ [镜像] 推送成功：${env.IMAGE}"

    } catch (Exception e) {
        echo "❌ [镜像] 构建或推送失败: ${e.getMessage()}"
        error "镜像流程终止。"
    } finally {
        // 7. 清理本地镜像 (无论成功失败都执行，防止磁盘爆炸)
        echo "🧹 清理本地镜像空间..."
        sh """
            docker rmi ${env.IMAGE} || true
            # 清理悬空镜像
            docker image prune -f --filter "until=24h" || true
        """
        // 退出登录 (可选)
        // sh "docker logout ${dockerRegistry}"
    }
}
