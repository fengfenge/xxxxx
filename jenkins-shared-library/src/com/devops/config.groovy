package com.devops

class Config {
    // === 基础配置 ===
    static String REGISTRY = "harbor.your-company.com"
    static String PROJECT = "backend-services"

    // === 服务配置映射 ===（可选：展示名等；仓库 URL 由流水线参数 GIT_REPO_URL 指定）
    static Map SERVICES = [:]

    // === 分支 -> 环境 映射规则 ===
    static Map ENV_MAP = [
        "dev": "dev",
        "test": "test"
    ]

    // === 分支前缀 -> 环境 映射规则 ===
    static Map ENV_PREFIX_MAP = [
        "dev-": "dev",
        "test-": "test"
    ]

    // === 标签 -> 环境 映射规则 ===
    static Map TAG_ENV_MAP = [
        "release-\\d{12}-v\\d+\\.\\d+\\.\\d+": "uat",
        "master-\\d{12}-v\\d+\\.\\d+\\.\\d+": "prod"
    ]

    // === 构建策略配置 ===
    static Map BUILD_STRATEGY = [
        "dev": [
            "trigger": "branch",
            "source": "dev",
            "versionPattern": "^NA\$",
            "requireTag": false,
            "autoDeploy": true,
            "manualOnly": false,
            "skipTests": true,
            "requireApproval": false   // dev 环境无需审批
        ],
        "test": [
            "trigger": "branch",
            "source": "test",
            "versionPattern": "^NA\$",
            "requireTag": false,
            "autoDeploy": true,
            "manualOnly": false,
            "skipTests": false,
            "requireApproval": false   // test 环境无需审批
        ],
        "uat": [
            "trigger": "tag",
            "source": "release",
            "versionPattern": "release-\\d{12}-v\\d+\\.\\d+\\.\\d+",
            "requireTag": true,
            "autoDeploy": true,
            "manualOnly": true,
            "skipTests": false,
            "requireApproval": true    // uat 环境需要审批
        ],
        "prod": [
            "trigger": "tag",
            "source": "master",
            "versionPattern": "master-\\d{12}-v\\d+\\.\\d+\\.\\d+",
            "requireTag": true,
            "autoDeploy": true,
            "manualOnly": true,
            "skipTests": false,
            "requireApproval": true    // prod 环境必须审批
        ]
    ]

    // === K8s 集群配置 ===
    static Map K8S_CREDENTIALS = [
        "prod": "kubeconfig-prod",
        "uat": "kubeconfig-uat",
        "test": "kubeconfig-test",
        "dev": "kubeconfig-dev"
    ]

    // 分支构建镜像 tag 中时间戳所用时区
    static String IMAGE_TAG_TIMEZONE = "Asia/Shanghai"

    // === 通知配置 ===
    static String DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN"

    // 企业微信群机器人 Webhook
    static String WECOM_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"

    // === 企业微信审批配置 ===
    // 审批模式：simple(群机器人+Jenkins input) / app(企业微信应用审批)
    static String WECOM_APPROVE_MODE = "simple"

    // 企业微信应用配置（app 模式时使用）
    static String WECOM_CORP_ID = ""                          // 企业 ID
    static String WECOM_APP_AGENT_ID = ""                     // 应用 AgentId
    static String WECOM_APP_SECRET_CREDENTIALS_ID = ""        // Jenkins 中存储 Secret 的凭据 ID
    static String WECOM_APPROVAL_TEMPLATE_ID = ""             // 审批模板 ID

    // 审批超时（分钟）
    static int APPROVAL_TIMEOUT_MINUTES = 30

    // 审批人列表（Jenkins 用户 ID，逗号分隔）
    static String APPROVER_USERS = "admin,devops,release-manager"

    // === 发布单与发布记录配置 ===
    // 发布记录存储路径（Jenkins 服务器本地目录）
    static String RELEASE_RECORD_DIR = "/var/jenkins_home/release-records"

    // 发布单 ID 前缀
    static String RELEASE_TICKET_PREFIX = "REL"

    // 发布记录保留天数
    static int RELEASE_RECORD_RETENTION_DAYS = 180

    // === 审批环境阈值 ===
    // 哪些环境需要企业微信审批通知（即使 autoDeploy=true 也要审批确认）
    static List APPROVAL_ENV_LIST = ["uat", "prod"]

    // === 辅助方法 ===
    static Map getServiceConfig(String serviceName) {
        return SERVICES.get(serviceName, [:])
    }

    // 判断指定环境是否需要审批
    static boolean isApprovalRequired(String targetEnv) {
        return APPROVAL_ENV_LIST.contains(targetEnv)
    }

    // 判断指定环境是否使用标签构建
    static boolean isTagBasedBuild(String targetEnv) {
        def strategy = BUILD_STRATEGY[targetEnv]
        return strategy != null && strategy.trigger == "tag"
    }
}
