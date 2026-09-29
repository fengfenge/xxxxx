// pythonCicd.groovy — 统一 Python 调用入口
//
// 职责：把 Groovy 层收集到的参数序列化后交给 Python，并把 Python 返回的
// 环境变量更新回 Jenkins env。各 Stage.groovy 通过此函数调用 Python，
// 避免每个 Stage 重复写 sh + readJSON + env 更新。

def call(String step, Map params = [:]) {
    return invokePython(step, params)
}

def call(Map args) {
    def step = args.step ?: args.name
    if (!step) {
        error '❌ pythonCicd: 必须指定 step 参数'
    }
    def params = args.findAll { k, v -> k != 'step' && k != 'name' }
    return invokePython(step, params)
}

def invokePython(String step, Map params) {
    def pythonBin = params.pythonBin ?: env.PYTHON_BIN ?: 'python3'
    def cicdRoot = params.cicdRoot ?: env.PYTHON_CICD_ROOT

    if (!cicdRoot?.trim()) {
        error '❌ PYTHON_CICD_ROOT 未设置，请先调用 bootstrapCicdLib()'
    }

    // 合并 Jenkins 环境快照
    def envSnapshot = [:]
    [
        'JOB_NAME', 'BUILD_URL', 'BUILD_USER_ID', 'BUILD_CAUSE', 'WORKSPACE', 'BUILD_NUMBER',
        'BRANCH_NAME', 'GIT_BRANCH', 'TAG_NAME', 'GIT_TAG_NAME', 'GIT_URL', 'GIT_REPO_URL',
        'GIT_CREDENTIALS_ID', 'K8S_NAMESPACE', 'ENV', 'IMAGE', 'IMAGE_TAG', 'IMAGE_REPO',
        'FULL_IMAGE', 'RELEASE_TICKET_ID', 'SHOULD_DEPLOY', 'TRIGGER_TYPE', 'BUILD_MESSAGE',
        'APP_NAME', 'BUILD_LANGUAGE', 'BUILD_TOOL', 'HARBOR_PROJECT',
        'PROD_APPROVER', 'CHANGE_ID', 'CHANGE_TARGET',
        'DOCKER_USER', 'DOCKER_PASS', 'GIT_USER', 'GIT_PASS', 'KUBECONFIG', 'KUBECONFIG_FILE',
        'BUILD_TYPE', 'TARGET_ENV', 'FORCED_DEPLOY_ENV',
        'DEPLOYMENT_NAME', 'REVISION', 'MAX_REVISIONS', 'ROLLBACK_REASON', 'RELATED_TICKET_ID',
        'ROLLBACK_OPERATOR', 'ROLLBACK_ACTION', 'NOTIFY_STATUS'
    ].each { key ->
        if (env."${key}" != null && env."${key}" != '') {
            envSnapshot[key] = env."${key}"
        }
    }

    def merged = envSnapshot + params
    merged.step = step
    merged.job_name = merged.job_name ?: env.JOB_NAME
    merged.build_url = merged.build_url ?: env.BUILD_URL
    merged.workspace = merged.workspace ?: env.WORKSPACE

    def paramsFile = "${env.WORKSPACE}/cicd_params_${step}_${env.BUILD_NUMBER ?: 'local'}.json"
    writeJSON file: paramsFile, json: merged

    def outputFile = "${paramsFile}.out"
    def cmd = "${pythonBin} -m cicd.cli --step ${step} --params '${paramsFile}'"

    echo "🐍 [python-cicd] step=${step} root=${cicdRoot}"

    dir(cicdRoot) {
        sh(script: """
            if [ -f requirements.txt ]; then
                ${pythonBin} -m pip install -q -r requirements.txt 2>/dev/null || true
            fi
            ${cmd} > '${outputFile}' 2>&1 || true
        """)
    }

    def output = readFile(outputFile).trim()
    if (!output) {
        error "❌ pythonCicd 步骤 ${step} 无输出，请检查 Master 是否安装 Python3 及 ${cicdRoot}/cicd"
    }

    def result = readJSON text: output
    result.messages?.each { msg -> echo "${msg}" }

    result.env?.each { k, v ->
        if (v != null) {
            env."${k}" = "${v}"
        }
    }

    if (!result.success) {
        error "❌ pythonCicd 步骤 ${step} 失败: ${result.error ?: '未知错误'}"
    }

    echo "✅ [python-cicd] 步骤 ${step} 完成"
    return result
}
