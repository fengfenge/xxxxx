// 智能初始化 - 支持触发器自动触发
// 自动识别分支/标签、计算镜像Tag、注入环境变量、创建发布单、拦截非法构建

def call() {
    def config = new com.devops.Config()
    // 原始检出分支（用于镜像 tag、日志）
    def branchRaw = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ''
    def branch = normalizeCiBranchName(branchRaw)
    // GitLab MR / 等价场景：优先用「目标分支」匹配 dev/test
    def mrTarget = normalizeCiBranchName(env.gitlabTargetBranch ?: env.GITLAB_TARGET_BRANCH ?: env.CHANGE_TARGET ?: '')
    def branchForEnv = mrTarget ?: branch
    def tag = env.TAG_NAME ?: env.GIT_TAG_NAME
    def targetEnv = ""
    def shouldDeploy = true
    def triggerType = ""

    echo "[初始化] 正在解析构建策略..."

    // 1. 判断触发类型：标签构建还是分支构建
    if (tag) {
        triggerType = "tag"
        echo "[策略] 检测到标签构建：${tag}"

        targetEnv = matchTagToEnvironment(tag, config)

        if (!targetEnv) {
            error "[阻断] 不支持的标签格式：${tag}。请使用 分支-年月日时分-v版本 格式，例如：master-202605071401-v1.0.1"
        }

        def strategy = config.BUILD_STRATEGY[targetEnv]
        if (strategy && strategy.requireTag) {
            if (!tag.matches(strategy.versionPattern)) {
                error "[阻断] 标签 ${tag} 不符合环境 ${targetEnv} 的要求。"
            }
        }

        if (strategy && strategy.manualOnly) {
            if (!isManualTrigger()) {
                error "[阻断] 环境 ${targetEnv} 仅支持手动构建部署。请通过 Jenkins 界面手动触发构建。"
            }
            echo "[策略] 检测到手动触发，允许部署到 ${targetEnv} 环境。"
        }

    } else {
        triggerType = "branch"
        echo "[策略] 检测到分支构建：检出分支=${branch}${mrTarget ? "，MR/合并请求目标分支=${mrTarget}" : ""}"

        targetEnv = matchBranchToEnvironment(branchForEnv, config)

        if (!targetEnv) {
            error "[阻断] 不支持的分支：用于匹配环境的分支=${branchForEnv}（检出=${branch}）。仅允许 dev、test、dev-*、test-* 及 feature/* 分支。"
        }

        def strategy = config.BUILD_STRATEGY[targetEnv]
        if (strategy && strategy.trigger == "tag") {
            error "[阻断] 环境 ${targetEnv} 必须使用标签构建，不能使用分支构建。"
        }

        if (strategy && strategy.autoDeploy != null) {
            shouldDeploy = strategy.autoDeploy
        }

        def isFeatSource = branch.startsWith("feature/") || branch.startsWith("feat/")
        def mergesIntoDevOrTest = mrTarget && (mrTarget == 'dev' || mrTarget == 'test' || mrTarget.startsWith('dev-') || mrTarget.startsWith('test-'))
        if (isFeatSource && !mergesIntoDevOrTest) {
            shouldDeploy = false
            echo "[策略] 功能分支 ${branch} 未合并目标为 dev/test，仅构建，不部署。"
        } else if (targetEnv == 'dev' || targetEnv == 'test') {
            echo "[策略] ${targetEnv} 环境自动流水线：push/MR 合并触发将构建并部署。"
        }
    }

    // 参数强制环境
    if (env.FORCED_DEPLOY_ENV?.trim()) {
        def fe = env.FORCED_DEPLOY_ENV.trim()
        if (!config.K8S_CREDENTIALS.containsKey(fe)) {
            error "❌ [配置错误] 强制环境 ${fe} 未在 K8S_CREDENTIALS 中配置"
        }
        echo "[策略] 使用参数指定的环境覆盖自动识别：${targetEnv} -> ${fe}"
        targetEnv = fe
    }

    // 2. 注入全局变量
    env.ENV = targetEnv
    env.SHOULD_DEPLOY = "${shouldDeploy}"
    env.TRIGGER_TYPE = triggerType
    env.SERVICE_NAME = env.JOB_NAME

    // 3. 获取服务配置
    def serviceConfig = config.getServiceConfig(env.JOB_NAME)
    if (serviceConfig) {
        env.SERVICE_DISPLAY_NAME = serviceConfig.name
        echo "[服务] 识别到服务：${serviceConfig.name}"
    }

    // 4. 生成镜像信息
    // - 分支构建（dev/test）：tag = 分支-年月日时分秒
    // - 标签构建（uat/prod）：tag = Git 标签全文
    def imageTag = ""

    if (triggerType == "tag") {
        imageTag = tag
    } else {
        def branchSlug = sanitizeBranchForImageTag(branch)
        def tz = java.util.TimeZone.getTimeZone(config.IMAGE_TAG_TIMEZONE ?: 'Asia/Shanghai')
        def fmt = new java.text.SimpleDateFormat('yyyyMMddHHmmss')
        fmt.setTimeZone(tz)
        def ts = fmt.format(new Date())
        imageTag = "${branchSlug}-${ts}"
    }

    env.IMAGE_TAG = imageTag
    env.IMAGE_REPO = "${config.REGISTRY}/${config.PROJECT}/${env.JOB_NAME}"
    env.IMAGE = "${env.IMAGE_REPO}:${env.IMAGE_TAG}"

    // 5. 设置 K8s 配置
    if (!config.K8S_CREDENTIALS.containsKey(targetEnv)) {
        error "❌ [配置错误] 未找到环境 ${targetEnv} 的 K8s 配置。"
    }
    env.K8S_CREDENTIAL_ID = config.K8S_CREDENTIALS[targetEnv]
    if (!env.K8S_NAMESPACE?.trim()) {
        error "❌ [配置错误] 未指定 K8s 命名空间。请在 Pipeline 参数中设置 K8S_NAMESPACE。"
    }
    env.K8S_NAMESPACE = env.K8S_NAMESPACE.trim()

    // 6. 解析标签信息（仅标签构建）
    if (triggerType == "tag") {
        def tagInfo = parseTag(tag)
        env.TAG_BRANCH = tagInfo.branch
        env.TAG_TIMESTAMP = tagInfo.timestamp
        env.TAG_VERSION = tagInfo.version
        echo "[标签信息] 分支: ${tagInfo.branch}, 时间: ${tagInfo.timestamp}, 版本: ${tagInfo.version}"
    }

    // 7. 创建发布单（仅在需要部署时）
    if (shouldDeploy) {
        releaseTicket(
            serviceName: env.JOB_NAME,
            env: targetEnv,
            imageTag: imageTag,
            image: env.IMAGE,
            triggerType: triggerType,
            triggerUser: env.BUILD_USER_ID ?: 'system',
            buildUrl: env.BUILD_URL,
            buildMessage: env.BUILD_MESSAGE ?: ''
        )
    }

    // 8. 打印看板
    def approvalRequired = config.isApprovalRequired(targetEnv)
    echo "=========================================="
    echo "📦 服务: ${env.SERVICE_DISPLAY_NAME ?: env.JOB_NAME}"
    echo "🎯 环境: ${targetEnv.toUpperCase()}"
    echo "🔄 触发类型: ${triggerType.toUpperCase()}"
    echo "🌿 触发源: ${tag ?: branch}${mrTarget ? " (MR→${mrTarget})" : ""}"
    echo "🐳 镜像: ${env.IMAGE}"
    echo "📋 发布单: ${env.RELEASE_TICKET_ID ?: '无'}"
    if (triggerType == "branch") {
        echo "⏱️ 分支镜像 tag 时间戳为构建时刻 yyyyMMddHHmmss（时区=${config.IMAGE_TAG_TIMEZONE}）"
    }
    echo "📁 K8s 命名空间: ${env.K8S_NAMESPACE}"
    echo "🚀 部署: ${shouldDeploy ? 'ENABLED' : 'DISABLED'}"
    echo "🔐 审批: ${approvalRequired ? 'REQUIRED' : 'NOT REQUIRED'}"
    echo "=========================================="
}

// 判断是否为手动触发
def isManualTrigger() {
    if (env.BUILD_USER_ID) {
        echo "[触发检测] 检测到手动触发，用户: ${env.BUILD_USER_ID}"
        return true
    }

    if (env.BUILD_CAUSE) {
        def buildCause = env.BUILD_CAUSE.toLowerCase()
        if (buildCause.contains('userid') || buildCause.contains('manual')) {
            echo "[触发检测] 检测到手动触发，原因: ${env.BUILD_CAUSE}"
            return true
        }
    }

    if (params && params.size() > 0) {
        echo "[触发检测] 检测到参数化构建，可能是手动触发"
        return true
    }

    echo "[触发检测] 检测到自动触发（Webhook）"
    return false
}

// 根据标签匹配环境
def matchTagToEnvironment(String tag, def config) {
    for (Map.Entry<String, String> entry : config.TAG_ENV_MAP.entrySet()) {
        def pattern = entry.key
        def env = entry.value
        if (tag.matches(pattern)) {
            return env
        }
    }
    return null
}

// 统一 Jenkins / GitLab 常见分支字符串
def normalizeCiBranchName(String raw) {
    if (!raw) return ''
    def b = raw.trim()
    if (b.startsWith('refs/heads/')) {
        b = b.substring('refs/heads/'.length())
    }
    if (b.startsWith('origin/')) {
        b = b.substring('origin/'.length())
    }
    return b
}

// 根据分支匹配环境
def matchBranchToEnvironment(String branch, def config) {
    if (config.ENV_MAP.containsKey(branch)) {
        return config.ENV_MAP[branch]
    }

    for (Map.Entry<String, String> entry : config.ENV_PREFIX_MAP.entrySet()) {
        def prefix = entry.key
        def env = entry.value
        if (branch.startsWith(prefix)) {
            echo "[策略] 分支 ${branch} 匹配前缀 ${prefix} -> 环境 ${env}"
            return env
        }
    }

    if (branch.startsWith("feature/") || branch.startsWith("feat/")) {
        return "dev"
    }

    return null
}

// 分支名 → 镜像 tag 合法片段
def sanitizeBranchForImageTag(String raw) {
    if (!raw) return "unknown"
    def b = raw.trim()
    if (b.startsWith('origin/')) {
        b = b.substring('origin/'.length())
    }
    def s = b.replaceAll('/', '-').replaceAll('[^a-zA-Z0-9._-]', '-').replaceAll('-+', '-').replaceAll(/^[.-]+|[.-]+$/, '')
    return s ? s : 'unknown'
}

// 解析标签格式
def parseTag(String tag) {
    def matcher = tag =~ /^([a-zA-Z-]+)-(\d{12})-v(\d+\.\d+\.\d+)$/
    if (matcher.matches()) {
        return [
            branch: matcher[0][1],
            timestamp: matcher[0][2],
            version: matcher[0][3]
        ]
    }
    return [branch: "", timestamp: "", version: ""]
}
