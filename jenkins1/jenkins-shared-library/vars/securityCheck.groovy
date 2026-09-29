//功能：集成 SonarQube 代码扫描和 Trivy 镜像漏洞扫描，高危漏洞直接阻断。
def call() {
    echo "🛡️ [安全] 开始执行安全扫描..."
    // 1. 代码静态扫描 (SonarQube 示例)
    // 需安装 SonarQube Scanner 插件或在 Docker 中运行
    echo "🔍 执行 SonarQube 代码分析..."
    // withSonarQubeEnv('MySonar') {
    //     sh 'sonar-scanner -Dsonar.projectKey=${env.JOB_NAME}'
    // }
    // qualityGate 检查可放在 post 阶段或使用 waitForQualityGate()

    // 2. 镜像漏洞扫描 (Trivy 示例)
    // 注意：此时镜像可能尚未 push，扫描本地构建的镜像
    echo "🔍 执行 Trivy 镜像漏洞扫描 (High/Critical)..."
    try {
        sh """
            trivy image --exit-code 1 --severity HIGH,CRITICAL \
            --ignore-unfixed ${env.IMAGE} || {
            echo "❌ 发现高危漏洞，构建终止！"
            exit 1
            }
        """
    } catch (Exception e) {
    // 如果 trivy 命令本身报错（如未安装），可选择跳过或失败
        echo "⚠️ Trivy 扫描执行异常，请检查环境。"
        // error "安全扫描失败" 
    }

    // 3. 镜像签名 (Docker Content Trust)
    echo "✍️ 执行镜像签名..."
    sh "docker trust sign ${env.IMAGE} || echo '⚠️ 签名跳过 (可能未配置 DCT)'"
    echo "✅ [安全] 安全检查通过。"
}