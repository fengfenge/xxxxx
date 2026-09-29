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

### git 命令
```
切换分支：
# 1. 查看所有分支
git branch -a
# 输出：
#   dev
# * feature/login
#   main
#   remotes/origin/dev
#   remotes/origin/main

# 2. 切换到已存在的分支
git checkout dev
# 输出：Switched to branch 'dev'

# 3. 创建并切换到新分支
git checkout -b feature/new-feature
# 输出：Switched to a new branch 'feature/new-feature'

使用 git switch （推荐，Git 2.23+）
# 1. 切换到已存在的分支
git switch dev
# 输出：Switched to branch 'dev'

# 2. 创建并切换到新分支
git switch -c feature/new-feature
# 输出：Switched to a new branch 'feature/new-feature'

# 3. 切换回上一个分支
git switch -
# 输出：Switched to branch 'main'

从远程分支创建并切换
# 1. 查看远程分支
git branch -r
# 输出：origin/dev, origin/test, origin/main

# 2. 从远程分支创建本地分支并切换
git checkout -b feature/login origin/feature/login
# 或
git switch -c feature/login origin/feature/login


切换分支前的注意事项
# 切换分支前检查工作区状态
git status

# 如果有未提交的修改，有三种处理方式：

# 方式1：暂存修改（推荐）
git stash
git switch dev
# 恢复暂存的修改
git stash pop

# 方式2：提交修改
git add .
git commit -m "Save changes before switch"
git switch dev

# 方式3：强制切换（会丢失未提交的修改，谨慎使用）
git switch -f dev

常用分支操作命令
# 查看本地分支（* 表示当前分支）
git branch

# 查看所有分支（包含远程）
git branch -a

# 删除本地分支
git branch -d feature/login

# 删除远程分支
git push origin --delete feature/login

# 重命名分支
git branch -m old-name new-name

实战示例
# 完整流程：从主分支创建功能分支，开发后合并
git switch main              # 切换到主分支
git pull origin main         # 拉取最新代码
git switch -c feature/pay    # 创建并切换到支付功能分支
# ... 开发代码 ...
git add .
git commit -m "完成支付功能"
git push origin feature/pay  # 推送到远程
# 创建 MR/PR 请求合并到 main
```

```
git checkout dev
error: pathspec 'dev' did not match any file(s) known to git
表示本地仓库中 没有找到 dev 分支 。


$ git fetch origin
fatal: 'origin' does not appear to be a git repository
fatal: Could not read from remote repository.
表示本地仓库 还没有配置远程仓库地址
原因 ：本地仓库刚初始化，还没有关联到远程 GitLab 仓库。

```

## 完整解决方案
### 步骤 1：检查当前仓库状态
```
# 查看远程仓库配置（应该是空的）
git remote -v

# 查看本地分支
git branch -a

# 查看当前目录内容
ls -la
```
### 步骤 2：添加远程仓库地址
首先需要在 GitLab 上创建项目，获取仓库地址：
```
# 添加远程仓库（替换为你的 GitLab 地址）
git remote add origin git@gitlab.example.com:devops/jenkins-shared-library.git

# 验证配置
git remote -v
# 输出：
# origin  git@gitlab.example.com:devops/jenkins-shared-library.git (fetch)
# origin  git@gitlab.example.com:devops/jenkins-shared-library.git (push)
```
### 步骤 3：从远程拉取分支或创建本地分支 
情况 A：远程已有 dev 分支
```
# 获取远程分支信息
git fetch origin

# 查看所有分支（包括远程）
git branch -a

# 创建本地 dev 分支并跟踪远程
git checkout -b dev origin/dev
```
情况 B：远程没有 dev 分支（需要自己创建）
```
# 创建并切换到 dev 分支
git checkout -b dev

# 推送到远程（第一次需要设置上游）
git push -u origin dev
```

### 步骤 4：完整操作示例
```
# 1. 进入项目目录
cd e:\pythonProject\jenkins-shared-library

# 2. 初始化 Git（如果还没初始化）
git init

# 3. 配置用户信息
git config user.name "Your Name"
git config user.email "your.email@example.com"

# 4. 添加远程仓库
git remote add origin git@gitlab.example.com:devops/jenkins-shared-library.git

# 5. 创建并切换到 dev 分支
git checkout -b dev

# 6. 添加文件并提交
git add .
git commit -m "Initial commit: Jenkins shared library"

# 7. 推送到远程
git push -u origin dev
```
