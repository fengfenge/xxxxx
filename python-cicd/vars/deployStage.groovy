// deployStage.groovy — K8s 部署（调 Python）

def call(Map params = [:]) {
    def environment = params.environment ?: env.ENV ?: 'dev'
    def namespace = params.namespace ?: env.K8S_NAMESPACE ?: ''
    def appName = params.appName ?: env.APP_NAME ?: env.JOB_NAME

    echo "🚀 Deploy: ${appName} → ${environment}/${namespace}"

    withCredentials([file(credentialsId: "kubeconfig-${environment}", variable: 'KUBECONFIG_FILE')]) {
        pythonCicd('k8s_deploy', [
            environment: environment,
            namespace  : namespace,
            app_name   : appName,
            workspace  : env.WORKSPACE
        ])
    }
}
