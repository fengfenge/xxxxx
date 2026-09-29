// securityScanStage.groovy — 安全扫描（调 Python）

def call(Map params = [:]) {
    def fullImage = params.fullImage ?: env.FULL_IMAGE ?: ''
    def scanLevel = params.scanLevel ?: env.SCAN_LEVEL ?: 'HIGH,CRITICAL'

    echo "🔒 Security Scan: ${fullImage}"

    pythonCicd('security_check', [
        full_image: fullImage,
        scan_level: scanLevel,
        workspace : env.WORKSPACE
    ])
}
