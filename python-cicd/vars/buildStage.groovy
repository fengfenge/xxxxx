// buildStage.groovy — 构建阶段（调 Python）

def call(Map params = [:]) {
    def language = params.language ?: env.BUILD_LANGUAGE ?: 'java'
    def buildTool = params.buildTool ?: env.BUILD_TOOL ?: 'maven'

    echo "🔨 Build: language=${language}, tool=${buildTool}"

    pythonCicd('build', [
        language  : language,
        build_tool: buildTool,
        workspace : env.WORKSPACE
    ])
}
