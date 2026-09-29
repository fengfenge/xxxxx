package com.cicd

/**
 * PipelineDefaults — 共享库默认配置（可选）
 * Groovy 层可通过 new PipelineDefaults() 读取，Python 层对应 config/default.yaml
 */
class PipelineDefaults implements Serializable {
    static String REGISTRY = 'harbor.your-company.com'
    static String HARBOR_PROJECT = 'backend-services'
    static String LIB_GIT_URL = ''
    static String LIB_BRANCH = 'main'
    static String CICD_ROOT = '/opt/jenkins/python-cicd'
    static List APPROVAL_ENVS = ['uat', 'staging', 'prod', 'production']
    static List NOTIFY_CHANNELS = ['wecom']
}
