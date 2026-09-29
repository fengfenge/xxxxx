// cicdInit.groovy — 流水线初始化（调 Python pipeline_init）

def call(Map params = [:]) {
    bootstrapCicdLib(cicdRoot: params.cicdRoot)

    def appName = params.appName ?: env.APP_NAME ?: env.JOB_NAME
    def language = params.language ?: env.BUILD_LANGUAGE ?: 'java'
    def buildTool = params.buildTool ?: env.BUILD_TOOL ?: 'maven'
    def k8sNamespace = params.k8sNamespace ?: env.K8S_NAMESPACE ?: ''
    def harborProject = params.harborProject ?: env.HARBOR_PROJECT ?: 'backend-services'

    echo "🚀 Init: app=${appName}, language=${language}, namespace=${k8sNamespace}"

    pythonCicd('pipeline_init', [
        app_name      : appName,
        language      : language,
        build_tool    : buildTool,
        k8s_namespace : k8sNamespace,
        harbor_project: harborProject,
        workspace     : env.WORKSPACE
    ])
}
