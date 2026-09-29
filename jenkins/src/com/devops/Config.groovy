// class Config {
// class Config implements Serializable 是什么意思？class Config是一个配置类，用于存储流水线的配置信息。
// implements Serializable 是为了在流水线中传递配置信息时能够序列化和反序列化。
// 怎么使用java的Serializable接口？groovy是用的java的语法吗？
// groovy是用的java的语法，但是groovy是动态语言，所以不需要显式实现Serializable接口。
// 只需要在类定义时添加 implements Serializable 即可。
// zhushi111


package com.devops

import java.io.Serializable

class Config implements Serializable {
    private static final long serialVersionUID = 1L

    // Base registry settings
    static String REGISTRY = "harbor.tian-power.cloud"
    static String PROJECT = "ess-saas-temp"

    // Optional service metadata
    static Map SERVICES = [:]

    // Branch to environment mapping
    static Map ENV_MAP = [
        "dev" : "dev",
        "test": "test"
    ]

    // Branch prefix to environment mapping
    static Map ENV_PREFIX_MAP = [
        "dev-" : "dev",
        "test-": "test"
    ]

    // Tag pattern to environment mapping
    static Map TAG_ENV_MAP = [
        "release-\\d{12}-v\\d+\\.\\d+\\.\\d+": "uat",
        "main-\\d{12}-v\\d+\\.\\d+\\.\\d+"   : "prod"
    ]

    // Build strategy per environment
    static Map BUILD_STRATEGY = [
        "dev": [
            "trigger"        : "branch",
            "source"         : "dev",
            "versionPattern" : "^NA\$",
            "requireTag"     : false,
            "autoDeploy"     : true,
            "manualOnly"     : false,
            "skipTests"      : true,
            "requireApproval": false
        ],
        "test": [
            "trigger"        : "branch",
            "source"         : "test",
            "versionPattern" : "^NA\$",
            "requireTag"     : false,
            "autoDeploy"     : true,
            "manualOnly"     : false,
            "skipTests"      : false,
            "requireApproval": false
        ],
        "uat": [
            "trigger"        : "tag",
            "source"         : "release",
            "versionPattern" : "release-\\d{12}-v\\d+\\.\\d+\\.\\d+",
            "requireTag"     : true,
            "autoDeploy"     : true,
            "manualOnly"     : true,
            "skipTests"      : false,
            "requireApproval": true
        ],
        "prod": [
            "trigger"        : "tag",
            "source"         : "main",
            "versionPattern" : "main-\\d{12}-v\\d+\\.\\d+\\.\\d+",
            "requireTag"     : true,
            "autoDeploy"     : true,
            "manualOnly"     : true,
            "skipTests"      : false,
            "requireApproval": true
        ]
    ]

    // K8s credentials by environment
    static Map K8S_CREDENTIALS = [
        "prod": "kubeconfig-prod",
        "uat" : "kubeconfig-uat",
        "test": "kubeconfig-test",
        "dev" : "kubeconfig-dev"
    ]

    static String IMAGE_TAG_TIMEZONE = "Asia/Shanghai"

    // Notification config
    static String DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN"
    static String WECOM_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=7dad5faf-36e7-444d-8a27-9341ff32cca3"

    // WeCom approval config
    static String WECOM_APPROVE_MODE = "simple"
    static String WECOM_CORP_ID = ""
    static String WECOM_APP_AGENT_ID = ""
    static String WECOM_APP_SECRET_CREDENTIALS_ID = ""
    static String WECOM_APPROVAL_TEMPLATE_ID = ""

    static int APPROVAL_TIMEOUT_MINUTES = 30
    static String APPROVER_USERS = "admin,devops,release-manager"

    // Release record config
    static String RELEASE_RECORD_DIR = "/var/jenkins_home/release-records"
    static String RELEASE_TICKET_PREFIX = "REL"
    static int RELEASE_RECORD_RETENTION_DAYS = 180

    // Environments requiring approval
    static List APPROVAL_ENV_LIST = ["uat", "prod"]

    // SonarQube 配置
    // SONARQUBE_SERVER_NAME: Jenkins > 系统配置 > SonarQube servers 中配置的名称
    // SONAR_SCANNER_TOOL: Jenkins > Global Tool Configuration > SonarQube Scanner 中配置的名称
    static String SONARQUBE_SERVER_NAME = "SonarQube"
    static String SONAR_SCANNER_TOOL = "SonarScanner4"

    static Map getServiceConfig(String serviceName) {
        return SERVICES.get(serviceName, [:])
    }

    static boolean isApprovalRequired(String targetEnv) {
        if (!targetEnv) {
            return false
        }
        return APPROVAL_ENV_LIST.contains(targetEnv.toString().trim().toLowerCase())
    }

    static boolean isTagBasedBuild(String targetEnv) {
        if (!targetEnv) {
            return false
        }
        def strategy = BUILD_STRATEGY[targetEnv.toString().trim().toLowerCase()]
        return strategy != null && strategy.trigger == "tag"
    }
}
