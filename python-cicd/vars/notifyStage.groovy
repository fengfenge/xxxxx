// notifyStage.groovy — 通知（调 Python）

def call(Map params = [:]) {
    def status = params.status ?: env.NOTIFY_STATUS ?: 'SUCCESS'
    def appName = params.appName ?: env.APP_NAME ?: env.JOB_NAME

    echo "📣 Notify: ${appName} status=${status}"

    pythonCicd('notify', [
        app_name: appName,
        status  : status,
        workspace: env.WORKSPACE
    ])
}
