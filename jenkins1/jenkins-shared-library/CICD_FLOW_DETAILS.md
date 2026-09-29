# Jenkins 共享库 CICD 流程详解

## 一、项目结构与核心模块

```
jenkins-shared-library/
├── Jenkinsfile.param          # 主发布流水线入口
├── Jenkinsfile.rollback       # 回滚专用流水线
├── src/com/devops/
│   └── config.groovy          # 全局配置（环境映射、审批规则、凭据配置）
└── vars/
    ├── paramBuild.groovy      # 参数化构建处理
    ├── pipelineInit.groovy    # 流水线初始化（核心：环境识别、发布单创建）
    ├── gitCheckout.groovy     # Git 代码拉取
    ├── javamavenBuild.groovy  # Java/Maven 编译
    ├── dockerBuildPush.groovy # Docker 镜像构建推送
    ├── securityCheck.groovy   # 安全扫描
    ├── approveProd.groovy     # 审批门禁
    ├── k8sDeploy.groovy       # K8s 部署
    ├── releaseTicket.groovy   # 发布单管理
    ├── releaseRecord.groovy   # 发布记录
    ├── messageNotify.groovy   # 消息通知
    ├── wecomApprove.groovy    # 企业微信审批集成
    └── rollbackDeploy.groovy  # 回滚部署
```

## 二、环境策略与触发机制

| 环境 | 触发方式 | 构建类型 | 审批要求 | 部署方式 |
|------|---------|---------|---------|---------|
| **dev** | GitLab Webhook (push dev) | 分支构建 | 无需 | 自动 |
| **test** | GitLab Webhook (push test) | 分支构建 | 无需 | 自动 |
| **uat** | 手动打 tag / Jenkins 手动触发 | 标签构建 | 企业微信审批 | 手动触发 |
| **prod** | 手动打 tag / Jenkins 手动触发 | 标签构建 | 企业微信审批 | 手动触发 |

### 关键配置（`config.groovy`）

```groovy
// 分支 → 环境 映射
static Map ENV_MAP = ["dev": "dev", "test": "test"]

// 标签格式 → 环境 映射（正则匹配）
static Map TAG_ENV_MAP = [
    "release-\\d{12}-v\\d+\\.\\d+\\.\\d+": "uat",   // release-202605151037-v1.0.1
    "master-\\d{12}-v\\d+\\.\\d+\\.\\d+": "prod"    // master-202605151037-v1.0.1
]

// 需要审批的环境
static List APPROVAL_ENV_LIST = ["uat", "prod"]
```

## 三、dev/test 环境 CICD 流程

### 完整执行链路

```
开发者 push 代码到 dev/test 分支
        ↓
GitLab Webhook 触发 Jenkins
        ↓
┌────────────────────────────────────────────────────────────────┐
│                  Jenkinsfile.param 执行流程                     │
├────────────────────────────────────────────────────────────────┤
│  Stage 0: 参数验证                                             │
│    └─ BUILD_TYPE=auto，校验分支白名单（仅允许 dev/test）         │
│                  ↓                                            │
│  Stage 1: 参数处理 (paramBuild)                                │
│    └─ 写入环境变量：BRANCH_NAME, FORCED_DEPLOY_ENV, SHOULD_DEPLOY│
│                  ↓                                            │
│  Stage 2: 拉代码 (gitCheckout)                                 │
│    └─ 根据分支拉取对应代码                                      │
│                  ↓                                            │
│  Stage 3: 初始化 (pipelineInit)  ← 核心决策点                   │
│    ├─ 解析分支 → 匹配环境 (dev/test)                           │
│    ├─ 生成镜像 Tag: {分支}-{yyyyMMddHHmmss}                    │
│    ├─ 设置 K8s 凭据: kubeconfig-dev/test                       │
│    └─ 创建发布单: REL-20260515-001                            │
│                  ↓                                            │
│  Stage 4: 编译 (javamavenBuild)                                │
│    └─ mvn clean package -DskipTests                           │
│                  ↓                                            │
│  Stage 5: 镜像构建推送 (dockerBuildPush)                       │
│    └─ docker build → docker push → Harbor                      │
│                  ↓                                            │
│  Stage 6: 安全扫描 (securityCheck)                            │
│    └─ Trivy 镜像安全扫描（可选）                                │
│                  ↓                                            │
│  Stage 7: 审批 (approveProd)  ← dev/test 自动通过               │
│    └─ 判断 isApprovalRequired(dev/test) → false → 自动通过      │
│                  ↓                                            │
│  Stage 8: K8s 部署 (k8sDeploy)                                │
│    ├─ kubectl set image deployment                            │
│    ├─ kubectl rollout status                                  │
│    └─ 记录发布结果到发布单                                      │
│                  ↓                                            │
│  Stage 9: 发布确认                                             │
│    └─ 打印发布单详情                                           │
└────────────────────────────────────────────────────────────────┘
        ↓
企业微信通知：✅ 部署成功
```

## 四、uat/prod 环境 CICD 流程

### 完整执行链路

```
运维手动打 tag（如 master-202605151037-v1.0.1）
        ↓
Jenkins 手动触发 Build with Parameters
        ↓
┌────────────────────────────────────────────────────────────────┐
│                  Jenkinsfile.param 执行流程                      │
├────────────────────────────────────────────────────────────────┤
│  Stage 0: 参数验证                                               │
│    └─ BUILD_TYPE=tag，校验 TAG_NAME 和 GIT_REPO_URL 必填         │
│                  ↓                                             │
│  Stage 1: 参数处理                                              │
│    └─ 设置 TAG_NAME, FORCED_DEPLOY_ENV=uat/prod                │
│                  ↓                                             │
│  Stage 2: 拉代码                                                │
│    └─ 根据 TAG_NAME 拉取对应标签代码                              │
│                  ↓                                            │
│  Stage 3: 初始化 (pipelineInit)                                │
│    ├─ 解析标签 → 匹配环境 (uat/prod)                            │
│    ├─ 镜像 Tag = 标签名（如 master-202605151037-v1.0.1）        │
│    ├─ 设置 K8s 凭据: kubeconfig-uat/prod                       │
│    └─ 创建发布单: REL-20260515-005                             │
│                  ↓                                            │
│  Stage 4-6: 编译 → 镜像 → 安全扫描                              │
│                  ↓                                            │
│  Stage 7: 审批 (approveProd)  ← uat/prod 强制审批               │
│    ├─ 发送企业微信通知（Markdown 卡片）                           │
│    └─ 等待审批人确认（Jenkins input 或企微应用审批）               │
│                  ↓                                            │
│  Stage 8: K8s 部署                                             │
│    └─ kubectl set image + rollout status                      │
│                  ↓                                            │
│  Stage 9: 发布确认                                              │
└────────────────────────────────────────────────────────────────┘
        ↓
企业微信通知：✅ 部署成功（含审批人信息）
```

### 审批模式对比

| 模式 | 配置方式 | 审批流程 | 适用场景 |
|------|---------|---------|---------|
| **simple**（推荐） | 仅需配置群机器人 Webhook | 群通知 + Jenkins input 确认 | 中小团队，配置简单 |
| **app** | 需要配置企业微信应用 | 企微审批应用内完成审批 | 大型团队，流程规范 |

## 五、发布单生命周期

```
                    ┌──────────┐
                    │ pending  │  (创建)
                    └────┬─────┘
                         │ 审批通过
                    ┌────▼─────┐
              ┌─────│ approved │
              │     └────┬─────┘
              │          │ 开始部署
              │     ┌────▼─────┐
              │     │deploying │
              │     └────┬─────┘
              │          │
         ┌────┴────┐ ┌───┴────┐
         │ rollback│ │success │
         └─────────┘ └───┬────┘
                         │
                    ┌────▼─────┐
                    │ failed   │
                    └──────────┘
```

**发布单存储结构**：

```
/var/jenkins_home/release-records/
├── deploy-index.json
├── dev/REL-20260515-001.json
├── test/REL-20260515-002.json
├── uat/REL-20260515-003.json
└── prod/REL-20260515-005.json
```

## 六、回滚流程

### `Jenkinsfile.rollback` 执行流程

```
┌──────────────────────────────────────────────────────────────┐
│ Stage 1: 参数验证                                            │
│   └─ 确认 TARGET_ENV, DEPLOYMENT_NAME, ROLLBACK_REASON       │
├──────────────────────────────────────────────────────────────┤
│ Stage 2: 显示版本历史（可选）                                  │
│   └─ rollbackDeploy.getHistory() 显示最近 10 个版本           │
├──────────────────────────────────────────────────────────────┤
│ Stage 3: 回滚审批（仅 uat/prod）                              │
│   ├─ 发送企业微信回滚通知                                     │
│   └─ Jenkins input 确认                                      │
├──────────────────────────────────────────────────────────────┤
│ Stage 4: 执行回滚                                            │
│   └─ rollbackDeploy() → kubectl rollout undo                 │
├──────────────────────────────────────────────────────────────┤
│ Stage 5: 记录回滚                                            │
│   ├─ releaseRecord.recordRollback()                          │
│   └─ releaseTicket.recordRollback()（关联原发布单）            │
└──────────────────────────────────────────────────────────────┘
```

## 七、GitLab Webhook 配置

### 配置步骤

1. **GitLab 端**：
   - URL: `http://your-jenkins-url/project/your-job-name`
   - 触发事件: `Push events` + `Tag push events`
   - 分支过滤: `^(dev|test)$`（仅允许 dev/test 分支自动触发）

2. **Jenkins 端**（`Jenkinsfile.param`）：
   ```groovy
   triggers {
       GenericTrigger(
           genericVariables: [
               [key: 'GIT_BRANCH', value: '$.ref'],
               [key: 'GIT_REPO_URL', value: '$.project.git_http_url']
           ],
           token: 'k8s-devops-abc123',
           regexpFilterText: '$ref',
           regexpFilterExpression: '^(refs/heads/dev|refs/heads/test)$'  // Jenkins 端过滤
       )
   }
   ```

### GitLab Webhook 推荐配置

| Trigger 事件 | 是否勾选 | 说明 |
|-------------|---------|------|
| **Push events** | ✓ | 分支过滤填 `^(dev|test)$`，仅自动触发 dev/test |
| **Tag push events** | ❌ 不勾选 | uat/prod 通过 Jenkins 手动触发，避免自动触发被阻断 |
| **Merge request events** | ✓（可选） | 用于 MR 代码验证构建，不影响 uat/prod |

### Tag push events 配置说明

根据 `config.groovy` 设计，uat/prod 环境配置了 `manualOnly: true`：

```groovy
"uat": [
    "trigger": "tag",
    "manualOnly": true,        // 仅支持手动触发
    "requireApproval": true
],
"prod": [
    "trigger": "tag",
    "manualOnly": true,        // 仅支持手动触发
    "requireApproval": true
]
```

如果勾选 `Tag push events`，打 tag 后会触发 Jenkins，但会被代码逻辑阻断：

```
运维打 tag: master-202605151037-v1.0.1
        ↓
GitLab 发送 Webhook 到 Jenkins
        ↓
Jenkins 开始执行
        ↓
pipelineInit() 检测到 Webhook 触发（非手动）
        ↓
error "[阻断] 环境 prod 仅支持手动构建部署"
        ↓
❌ 构建失败
```

### Merge request events 配置说明

MR events 的作用是：
- 当有人提交 Merge Request（如 `feature/xxx` → `dev`）时触发 Jenkins
- 用于 **代码验证构建**（仅构建，不部署）
- 与 uat/prod 构建无关

## 八、Jenkins 凭据配置

| 凭据 ID | 类型 | 用途 |
|---------|------|------|
| `harbor-credentials` | Username with password | Harbor 镜像仓库登录 |
| `kubeconfig-dev` | Secret file | 开发环境 K8s 配置 |
| `kubeconfig-test` | Secret file | 测试环境 K8s 配置 |
| `kubeconfig-uat` | Secret file | 预发布环境 K8s 配置 |
| `kubeconfig-prod` | Secret file | 生产环境 K8s 配置 |
| `wecom-app-secret`（可选） | Secret text | 企业微信应用 Secret |

## 九、总结

### 核心设计理念

1. **环境隔离**：通过分支/标签自动识别目标环境，避免误部署
2. **安全门禁**：uat/prod 强制审批，dev/test 自动放行
3. **全链路追溯**：发布单贯穿整个流程，支持回滚追溯
4. **消息通知**：关键节点自动推送企业微信通知
5. **灵活配置**：Dockerfile 支持 Job 级配置，无需修改代码仓库

### 流程对比

| 维度 | dev/test | uat/prod |
|------|---------|----------|
| 触发 | Webhook 自动 | 手动打 tag / Jenkins 手动 |
| 镜像 Tag | `{分支}-{时间戳}` | `{标签名}` |
| 审批 | 自动通过 | 企业微信审批 |
| 部署 | 自动 | 审批后自动 |
| 适用场景 | 日常开发测试 | 预发布/生产发布 |