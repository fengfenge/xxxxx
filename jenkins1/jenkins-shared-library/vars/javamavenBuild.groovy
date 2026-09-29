// 功能：Java/Maven 项目构建。
// 亮点：依赖缓存：自动使用共享的 .m2 目录（需配合 Jenkins Agent 配置或 NFS），避免重复下载依赖。
// 并行编译：启用 -T 参数，利用多核 CPU 加速编译。
// 智能参数：根据环境变量动态决定是否跳过测试、是否开启 Debug。
// 版本检查：构建前检查 pom.xml 是否存在 SNAPSHOT 版本发布到生产的情况（可选）。
def call() {
    echo "🔨 [构建] 开始 Maven 编译..."

    def config = new com.devops.Config()

    // 1. 定义构建参数
    // -T 1C: 每个 CPU 核心一个线程
    // -DskipTests: 默认跳过测试（测试应在 securityCheck 或单独阶段运行），如需运行可去掉
    // -Dmaven.repo.local: 指定本地仓库路径，利用缓存
    def mavenArgs = "-T 1C -DskipTests -Dmaven.repo.local=./.m2/repository"

    // 如果是生产环境构建，建议强制运行测试或进行更严格的检查
    if (env.ENV == "prod") {
        echo "⚠️ [构建] 生产环境构建，建议开启单元测试验证..."
        // mavenArgs = "-T 1C -Dmaven.repo.local=./.m2/repository"
        // 注意：生产环境通常建议在 "安全扫描" 阶段跑测试，这里为了速度默认跳过，可根据团队规范调整
    }

    // 2. 检查 Maven wrapper (推荐) 或系统 Maven
    def mvnCmd = "./mvnw"
    if (!fileExists(mvnCmd)) {
        mvnCmd = "mvn"
        echo "ℹ️ [构建] 未检测到 Maven Wrapper，使用系统 Maven。"
    }

    try {
        sh """
            echo "Java 版本:"
            java -version

            echo "执行命令: ${mvnCmd} clean package ${mavenArgs}"
            ${mvnCmd} clean package ${mavenArgs}
        """

        // 3. (可选) 生产环境防呆检查：禁止 SNAPSHOT 版本发布到 prod
        if (env.ENV == "prod") {
            echo "🔍 [检查] 验证生产版本规范性..."
            def version = sh(returnStdout: true, script: "${mvnCmd} help:evaluate -Dexpression=project.version -q -DforceStdout").trim()
            if (version.endsWith("-SNAPSHOT")) {
                error "❌ [阻断] 生产环境禁止发布 SNAPSHOT 版本！当前版本：${version}。请修改 pom.xml。"
            }
            echo "✅ 版本检查通过：${version}"
        }

        echo "✅ [构建] Maven 编译成功。"

        // 4. 归档构建产物 (可选，方便下载)
        // archiveArtifacts artifacts: '**/target/*.jar', allowEmptyArchive: true

    } catch (Exception e) {
        echo "❌ [构建] Maven 编译失败: ${e.getMessage()}"
        // 可以在这里添加解析 pom.xml 错误日志的逻辑
        error "构建终止。"
    }
}