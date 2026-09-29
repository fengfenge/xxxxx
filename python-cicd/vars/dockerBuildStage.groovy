// dockerBuildStage.groovy — Docker 镜像构建与推送（调 Python）

def call(Map params = [:]) {
    def appName = params.appName ?: env.APP_NAME ?: env.JOB_NAME
    def harborProject = params.harborProject ?: env.HARBOR_PROJECT ?: 'backend-services'

    echo "🐳 Docker Build: ${harborProject}/${appName}:${env.IMAGE_TAG ?: 'latest'}"

    withCredentials([usernamePassword(credentialsId: 'harbor-credentials', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
        pythonCicd('docker_build', [
            app_name      : appName,
            harbor_project: harborProject,
            workspace     : env.WORKSPACE
        ])
    }
}
