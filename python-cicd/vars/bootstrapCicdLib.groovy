/**
 * bootstrapCicdLib.groovy — 初始化 Python CI/CD 库路径
 *
 * 优先级:
 *   1. cfg.cicdRoot — Master 预装路径，如 /opt/jenkins/python-cicd
 *   2. cfg.libGitUrl — 克隆共享库仓库到 workspace/.ci-lib
 *   3. env.PYTHON_CICD_ROOT — 已存在则跳过
 */

def call(Map cfg = [:]) {
    if (env.PYTHON_CICD_ROOT?.trim() && fileExists("${env.PYTHON_CICD_ROOT}/cicd/cli.py")) {
        echo "ℹ️ 使用已有 PYTHON_CICD_ROOT: ${env.PYTHON_CICD_ROOT}"
        return env.PYTHON_CICD_ROOT
    }

    if (cfg.cicdRoot?.trim()) {
        def root = cfg.cicdRoot.trim()
        if (!fileExists("${root}/cicd/cli.py")) {
            error "❌ cicdRoot 无效: ${root}（缺少 cicd/cli.py）"
        }
        env.PYTHON_CICD_ROOT = root
        echo "✅ PYTHON_CICD_ROOT = ${root}（预装路径）"
        return root
    }

    def libDir = "${env.WORKSPACE}/.ci-lib"
    def libGitUrl = cfg.libGitUrl?.trim()
    def libBranch = cfg.libBranch ?: 'main'
    def libCredentials = cfg.libCredentials ?: ''

    if (!libGitUrl) {
        error '''❌ 未配置 Python CI/CD 库路径。请在 cicdInit / Jenkinsfile 中设置:
  cicdRoot: "/opt/jenkins/python-cicd"   # Master 预装（推荐单节点）
  或
  libGitUrl: "https://git.xxx.com/devops/python-cicd.git"'''
    }

    if (!fileExists("${libDir}/cicd/cli.py")) {
        echo "📦 克隆 CI/CD 共享库: ${libGitUrl} @ ${libBranch}"
        dir(libDir) {
            def scmConfig = [
                $class                           : 'GitSCM',
                branches                         : [[name: "*/${libBranch}"]],
                doGenerateSubmoduleConfigurations: false,
                extensions                       : [[$class: 'CloneOption', shallow: true, depth: 1, timeout: 10]],
                userRemoteConfigs                : [[url: libGitUrl, credentialsId: libCredentials]]
            ]
            checkout(scmConfig)
        }
    }

    env.PYTHON_CICD_ROOT = libDir
    echo "✅ PYTHON_CICD_ROOT = ${libDir}"
    return libDir
}
