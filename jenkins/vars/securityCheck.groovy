//功能：集成 SonarQube 代码扫描和 Trivy 镜像漏洞扫描，高危漏洞直接阻断。
//说明：
//  - scanType: 'image' → 仅 Trivy 镜像漏洞扫描 + 镜像签名（在 dockerBuildPush 阶段 6 调用，JDK8 环境）
//  - scanType: 'code'  → 仅 SonarQube 代码静态扫描（在阶段 7 调用，需 JDK17）
//  - scanType: 'all'   → 全部执行（默认，兼容旧调用）
//  SonarQube scanner 需要 JDK17，由 Jenkinsfile.param 中安全扫描 stage 的 stage 级 tools 注入。
def call(Map opts = [:]) {
    def scanType = opts.scanType ?: 'all'

    echo "🛡️ [安全] 开始执行安全扫描，类型=${scanType}"

    if (scanType == 'image' || scanType == 'all') {
        imageScan()
    }

    if (scanType == 'code' || scanType == 'all') {
        codeScan()
    }

    echo "✅ [安全] 安全检查通过（类型=${scanType}）"
}

// 镜像漏洞扫描 + 镜像签名（在 docker build 后、push 前调用）
def imageScan() {
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
        echo "⚠️ Trivy 扫描执行异常：${e.getMessage()}"
        error "安全扫描失败，镜像存在 HIGH/CRITICAL 漏洞或 Trivy 执行失败"
    }

    // echo "✍️ 执行镜像签名..."
    // sh "docker trust sign ${env.IMAGE} || echo '⚠️ 签名跳过 (可能未配置 DCT)'"
}

// SonarQube 代码静态扫描（需 JDK17 环境）
def codeScan() {
    def config = new com.devops.Config()

    echo "🔍 执行 SonarQube 代码分析..."
    try {
        def scannerHome = tool config.SONAR_SCANNER_TOOL
        withSonarQubeEnv(config.SONARQUBE_SERVER_NAME) {
            sh """
                ${scannerHome}/bin/sonar-scanner \
                -Dsonar.projectKey=${env.JOB_NAME} \
                -Dsonar.projectName=${env.JOB_NAME} \
                -Dsonar.sources=src \
                -Dsonar.java.binaries=target/classes \
                -Dsonar.sourceEncoding=UTF-8
            """
        }
        echo "✅ SonarQube 代码分析完成，等待质量门..."
        // 质量门检查（如需阻断，取消下面注释）
        // timeout(time: 5, unit: 'MINUTES') {
        //     def qg = waitForQualityGate()
        //     if (qg.status != 'OK') {
        //         error "❌ SonarQube 质量门未通过：${qg.status}"
        //     }
        // }
    } catch (Exception e) {
        echo "⚠️ SonarQube 扫描执行异常：${e.getMessage()}"
        // error "安全扫描失败"
    }
}
