// 功能：将 Maven 项目依赖/产物上传到 Nexus。
// 说明：依赖 pom.xml 中 <distributionManagement> 配置，
//       凭据通过 Maven settings.xml 中对应 server id 提供，
//       调用前需确保 settings.xml 已在 Jenkins Agent 配置好。
def call(Map opts = [:]) {
    echo "INFO [Nexus 上传] 开始上传 Maven 依赖到 Nexus"

    def mvnCmd = "./mvnw"
    if (!fileExists(mvnCmd)) {
        mvnCmd = "mvn"
        echo "INFO [Nexus 上传] 未检测到 Maven Wrapper，使用系统 Maven。"
    }

    def mavenArgs = opts.mavenArgs ?: "-T 1C -DskipTests -Dmaven.repo.local=./.m2/repository"

    try {
        sh """
            echo "Java 版本:"
            java -version
            echo "执行命令: ${mvnCmd} clean deploy ${mavenArgs}"
            ${mvnCmd} clean deploy ${mavenArgs}
        """
        echo "INFO [Nexus 上传] Maven 依赖上传成功"
    } catch (Exception e) {
        echo "ERROR [Nexus 上传] Maven 依赖上传失败: ${e.getMessage()}"
        error "Nexus 上传终止"
    }
}
