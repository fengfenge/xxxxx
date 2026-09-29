/**
 * shouldRunStage.groovy — 根据 CICD_STEPS 参数判断是否执行某阶段
 *
 * Jenkinsfile 用法:
 *   when { expression { shouldRunStage('build') } }
 *
 * CICD_STEPS 示例（逗号分隔，留空=执行全部）:
 *   init,checkout,build,docker,scan,approve,deploy,notify
 */

def call(String stageName, String stepsParam = null) {
    def steps = stepsParam
    if (steps == null) {
        steps = env.CICD_STEPS ?: params?.CICD_STEPS ?: ''
    }
    steps = steps?.trim()
    if (!steps) {
        return true
    }
    return steps.split(',').collect { it.trim().toLowerCase() }.contains(stageName.toLowerCase())
}
