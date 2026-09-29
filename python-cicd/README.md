# python-cicd — Jenkins 轻量 Groovy 编排 + Python 重逻辑

本项目作为 **Jenkins 共享库（Shared Library）**，目标是把 CI/CD 流程中的"重逻辑"（环境识别、镜像计算、发布单、K8s 部署、通知等）下沉到 Python 实现，Groovy 层只做**轻量编排**和**Jenkins 原生能力调用**（如 `checkout`、`withCredentials`、`input`）。

## 1. 目录结构

```
jenkins-shared-lib/
├── vars/                          # Groovy 共享库脚本（Jenkins 可自动识别）
│   ├── bootstrapCicdLib.groovy    # 初始化 python-cicd 库路径
│   ├── cicdInit.groovy            # 初始化环境变量并调用 Python pipeline_init
│   ├── paramBuildStage.groovy     # 参数化处理阶段（调 Python）
│   ├── shouldRunStage.groovy      # 根据 CICD_STEPS 参数过滤 Stage
│   ├── gitCheckoutStage.groovy    # Git 检出（Groovy 层）
│   ├── buildStage.groovy          # 构建阶段（调 Python）
│   ├── dockerBuildStage.groovy    # 镜像构建阶段（调 Python）
│   ├── securityScanStage.groovy   # 安全扫描阶段（调 Python）
│   ├── approvalStage.groovy       # 审批阶段（Python 判断 + Jenkins input）
│   ├── deployStage.groovy         # K8s 部署阶段（调 Python）
│   ├── rollbackStage.groovy       # K8s 回滚阶段（调 Python）
│   ├── notifyStage.groovy         # 通知阶段（调 Python）
│   └── pythonCicd.groovy          # 统一 Python 调用入口
├── src/com/cicd/PipelineDefaults.groovy  # Groovy 默认常量（可选）
├── cicd/                          # Python 重逻辑核心包
│   ├── cli.py                     # 命令行入口
│   ├── context.py                 # 流水线上下文（聚合 params + env）
│   ├── config.py                  # YAML 配置加载（镜像 Config.groovy）
│   ├── result.py                  # 步骤执行结果对象
│   ├── utils.py                   # 通用工具（shell、时间、分支处理）
│   └── steps/                     # 各步骤处理器
│       ├── pipeline_init.py       # 环境/镜像/策略识别
│       ├── param_build.py         # 参数化构建参数处理
│       ├── build.py               # 多语言构建分发
│       ├── maven_build.py         # Maven 构建
│       ├── docker_build.py        # Docker 镜像构建/推送
│       ├── security_check.py      # Trivy 镜像扫描
│       ├── approve.py             # 审批判断与通知
│       ├── release_ticket.py      # 发布单 CRUD
│       ├── release_record.py      # 发布记录索引
│       ├── k8s_deploy.py          # K8s 部署
│       ├── rollback.py            # K8s 回滚
│       └── notify.py              # 钉钉/企微通知
├── config/default.yaml            # 默认配置（与 Config.groovy 对齐）
├── Jenkinsfile                    # 共享库自测 Jenkinsfile
├── Jenkinsfile.example            # 业务仓库模板（pipeline 中直接调用各 Stage）
├── Jenkinsfile.pipeline-script    # Pipeline script 方式模板
├── Jenkinsfile.param              # 参数化发布流水线模板
├── Jenkinsfile.rollback           # 回滚流水线模板
└── requirements.txt               # Python 依赖
```

## 2. 设计原则

- **Groovy 只做编排**：stage 定义、参数声明、凭证注入、审批节点、Git 检出；各 Stage 通过 `pythonCicd()` 统一调用 Python。
- **Python 可独立运行**：`python -m cicd.cli --step <name> --params-json '{...}'`，便于本地调试。
- **参数驱动**：Jenkinsfile / Pipeline 中通过 `params` 传入应用名、语言、构建工具、部署环境、命名空间等，Python 根据参数执行对应步骤。
- **配置与代码分离**：`config/default.yaml` 提供默认配置，生产环境可通过 `CICD_CONFIG` 环境变量或 `config_path` 参数覆盖。

## 3. 业务项目用法

把 `Jenkinsfile.example` 复制到业务仓库根目录并重命名为 `Jenkinsfile`，然后在 pipeline 中直接调用各 Stage：

```groovy
@Library('ci-shared-lib@main') _

pipeline {
    agent any
    parameters {
        string(name: 'APP_NAME', defaultValue: 'order-service')
        choice(name: 'LANGUAGE', choices: ['java', 'python', 'nodejs', 'go'])
        string(name: 'DEPLOY_ENVS', defaultValue: 'dev')
        string(name: 'K8S_NAMESPACE', defaultValue: 'order-system')
        string(name: 'CICD_ROOT', defaultValue: '/opt/jenkins/python-cicd')
    }
    stages {
        stage('Init') {
            steps {
                script {
                    cicdInit(
                        cicdRoot     : params.CICD_ROOT,
                        appName      : params.APP_NAME,
                        language     : params.LANGUAGE,
                        buildTool    : params.BUILD_TOOL,
                        envs         : params.DEPLOY_ENVS.split(','),
                        k8sNamespace : params.K8S_NAMESPACE
                    )
                }
            }
        }
        stage('Checkout') { steps { script { gitCheckoutStage() } } }
        stage('Build')    { steps { script { buildStage() } } }
        stage('Docker')   { steps { script { dockerBuildStage() } } }
        stage('Deploy')   {
            steps {
                script {
                    params.DEPLOY_ENVS.split(',').each { env ->
                        deployStage(environment: env, namespace: params.K8S_NAMESPACE)
                    }
                }
            }
        }
    }
}
```

完整示例请参见 [Jenkinsfile.example](Jenkinsfile.example)。

## 4. 关键参数说明

| 参数名 | 说明 | 示例 |
|---|---|---|
| `CICD_ROOT` | python-cicd 在 Jenkins Master 上的预装路径 | `/opt/jenkins/python-cicd` |
| `APP_NAME` | 应用/服务名，决定镜像名和 Deployment 名 | `order-service` |
| `LANGUAGE` / `BUILD_TOOL` | 语言和构建工具 | `java`/`maven` |
| `DEPLOY_ENVS` | 部署环境，逗号分隔 | `dev,test` / `staging,prod` |
| `K8S_NAMESPACE` | K8s 命名空间 | `order-system` |
| `HARBOR_PROJECT` | Harbor 项目名 | `backend-services` |
| `CICD_STEPS` | 选择执行的 Stage，留空=全部 | `init,checkout,build,docker,deploy` |
| `SKIP_SECURITY` | 是否跳过安全扫描 | `false` |
| `REQUIRE_APPROVAL` | uat/staging/prod 是否启用审批 | `true` |

## 5. Python 本地调试

```bash
cd /opt/jenkins/python-cicd
pip install -r requirements.txt

# 列出可用步骤
python -m cicd.cli --list-steps

# 执行 pipeline_init
python -m cicd.cli --step pipeline_init \
  --params-json '{"app_name":"demo","language":"java","envs":["dev"],"k8s_namespace":"demo"}'
```

## 6. 与原始 src/vars 的关系

- 本仓库**不改动**原始 `jenkins/src` 和 `jenkins/vars` 中的代码。
- `python-cicd` 中的 Python 逻辑是对原始 Groovy 逻辑的等价实现和扩展，使其可被多项目复用、可本地调试、可单元测试。

## 7. 扩展步骤

如需新增步骤：

1. 在 `cicd/steps/` 下新建 `xxx.py`，用 `@register("xxx")` 装饰 `run(ctx)` 函数。
2. 在 `vars/` 下新建 `xxxStage.groovy` 做 Groovy 层参数处理。
3. 在 `Jenkinsfile` 的 pipeline 中调用新的 Stage。
