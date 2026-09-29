# 阿里云与 AWS 云平台基础知识指南

## 概述

本文档提供阿里云（Alibaba Cloud）和 AWS（Amazon Web Services）两大云平台的核心概念和基础知识，旨在帮助开发者理解云平台的架构、服务和资源模型，从而能够自行编写 Terraform 代码进行基础设施管理。

## 一、全球基础设施

### 1.1 区域（Region）

区域是云平台在全球范围内划分的地理区域，每个区域都是一个独立的地理单元，包含多个可用区。

#### 阿里云区域

| 区域标识 | 区域名称 | 地理位置 |
|----------|----------|----------|
| cn-hangzhou | 华东 1 | 杭州 |
| cn-shanghai | 华东 2 | 上海 |
| cn-beijing | 华北 1 | 北京 |
| cn-qingdao | 华北 2 | 青岛 |
| cn-zhangjiakou | 华北 3 | 张家口 |
| cn-huhehaote | 华北 5 | 呼和浩特 |
| cn-shenzhen | 华南 1 | 深圳 |
| cn-guangzhou | 华南 2 | 广州 |
| cn-chengdu | 西南 1 | 成都 |
| ap-northeast-1 | 亚太东北 1 | 东京 |
| ap-southeast-1 | 亚太东南 1 | 新加坡 |
| ap-southeast-2 | 亚太东南 2 | 悉尼 |
| ap-south-1 | 亚太南部 1 | 孟买 |
| eu-west-1 | 欧洲西部 1 | 法兰克福 |
| us-west-1 | 美国西部 1 | 硅谷 |
| us-east-1 | 美国东部 1 | 弗吉尼亚 |

#### AWS 区域

| 区域标识 | 区域名称 | 地理位置 |
|----------|----------|----------|
| us-east-1 | US East (N. Virginia) | 弗吉尼亚州阿什伯恩 |
| us-east-2 | US East (Ohio) | 俄亥俄州哥伦布 |
| us-west-1 | US West (N. California) | 加利福尼亚州旧金山 |
| us-west-2 | US West (Oregon) | 俄勒冈州波特兰 |
| eu-west-1 | EU (Ireland) | 爱尔兰都柏林 |
| eu-west-2 | EU (London) | 英国伦敦 |
| eu-central-1 | EU (Frankfurt) | 德国法兰克福 |
| ap-northeast-1 | Asia Pacific (Tokyo) | 日本东京 |
| ap-northeast-2 | Asia Pacific (Seoul) | 韩国首尔 |
| ap-southeast-1 | Asia Pacific (Singapore) | 新加坡 |
| ap-southeast-2 | Asia Pacific (Sydney) | 澳大利亚悉尼 |
| ap-south-1 | Asia Pacific (Mumbai) | 印度孟买 |
| sa-east-1 | South America (São Paulo) | 巴西圣保罗 |

### 1.2 可用区（Availability Zone, AZ）

可用区是区域内的物理隔离的数据中心，每个可用区都有独立的电力、网络和冷却系统，可用区间通过高速低延迟网络连接。

- **阿里云**：每个区域包含 2-8 个可用区，标识格式为 `区域标识+字母`，如 `cn-hangzhou-a`、`cn-hangzhou-b`
- **AWS**：每个区域包含 2-6 个可用区，标识格式为 `区域标识+数字`，如 `us-east-1a`、`us-east-1b`

### 1.3 边缘节点（Edge Node）

用于 CDN 和全球加速服务，分布在全球各大城市，提供低延迟的内容分发。

## 二、网络基础

### 2.1 虚拟私有云（VPC）

VPC 是用户在云平台上创建的隔离网络环境，类似于传统数据中心的私有网络。

#### 网络范围

| 平台 | 默认支持的 IP 范围 | 支持的 IP 版本 |
|------|-------------------|----------------|
| 阿里云 | 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 | IPv4 |
| AWS | 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 | IPv4/IPv6 |

#### 阿里云 VPC 组成

- **VPC**：虚拟私有云，包含一个或多个子网
- **VSwitch（虚拟交换机）**：子网，位于特定可用区，IP 范围必须在 VPC 范围内
- **Route Table（路由表）**：控制子网流量的路由规则
- **EIP（弹性公网 IP）**：可绑定到 ECS、SLB 等资源的公网 IP
- **NAT Gateway**：允许子网内的实例访问公网
- **VPN Gateway**：建立站点到站点的 VPN 连接
- **Express Connect**：专线连接

#### AWS VPC 组成

- **VPC**：虚拟私有云
- **Subnet（子网）**：位于特定可用区
- **Route Table（路由表）**：控制子网路由
- **Internet Gateway（IGW）**：连接 VPC 到公网
- **NAT Gateway**：允许私有子网访问公网
- **VPC Peering**：VPC 间对等连接
- **Transit Gateway**：跨区域 VPC 连接

### 2.2 子网类型

#### 阿里云子网类型

| 类型 | 说明 | 访问方式 |
|------|------|----------|
| 私网子网 | 无公网 IP | 通过 NAT 网关访问公网 |
| 公网子网 | 自动分配公网 IP | 直接访问公网 |

#### AWS 子网类型

| 类型 | 说明 | 访问方式 |
|------|------|----------|
| 公有子网 | 路由表指向 IGW | 直接访问公网 |
| 私有子网 | 路由表不指向 IGW | 通过 NAT 网关访问公网 |

### 2.3 安全组（Security Group）

安全组是虚拟防火墙，控制进出资源的网络流量。

#### 安全组特性

- **有状态**：入站规则允许的流量，其返回流量自动允许
- **最小权限原则**：默认拒绝所有入站流量
- **应用级别**：绑定到实例级别，而非子网级别

#### 阿里云安全组

- 支持内网和公网两种类型
- 规则优先级：数值越小优先级越高（1-100）
- 支持 IPv4 和 IPv6

#### AWS 安全组

- 无优先级概念，按规则匹配
- 默认允许所有出站流量
- 支持 IPv4 和 IPv6

### 2.4 网络 ACL（Network ACL）

AWS 特有的子网级别的无状态防火墙。

- 无状态：返回流量需要单独配置规则
- 子网级别：应用于整个子网的所有实例
- 规则编号：按编号顺序匹配（最低编号优先）

## 三、计算服务

### 3.1 实例类型（Instance Type）

#### 阿里云 ECS 实例规格族

| 规格族 | 特点 | 适用场景 |
|--------|------|----------|
| g6/g7 | 通用型 | Web 服务器、应用服务器 |
| c6/c7 | 计算型 | CPU 密集型应用、批处理 |
| r6/r7 | 内存型 | 数据库、缓存、大数据 |
| hfg6/hfg7 | 异构计算型 | GPU 加速、AI 训练 |
| i3/i4 | 本地 SSD 型 | 高性能数据库、NoSQL |
| d1/d2 | 大数据型 | Hadoop、Spark 集群 |

规格命名规则：`ecs.规格族.大小`
- 大小：nano、micro、small、medium、large、xlarge、2xlarge、4xlarge、8xlarge 等

#### AWS EC2 实例规格族

| 规格族 | 特点 | 适用场景 |
|--------|------|----------|
| t2/t3 | 突发性能型 | 开发测试、低流量应用 |
| m5/m6 | 通用型 | Web 服务器、应用服务器 |
| c5/c6 | 计算优化型 | CPU 密集型应用 |
| r5/r6 | 内存优化型 | 数据库、内存缓存 |
| p3/p4 | GPU 加速型 | AI 训练、深度学习 |
| i3/i4 | 存储优化型 | 高性能数据库 |
| z1d | 高频率型 | 高频交易、低延迟应用 |

规格命名规则：`规格族.大小`
- 大小：nano、micro、small、medium、large、xlarge、2xlarge、4xlarge、8xlarge、12xlarge、16xlarge、24xlarge 等

### 3.2 镜像（Image）

镜像是实例的模板，包含操作系统和预装软件。

#### 阿里云镜像类型

| 类型 | 说明 |
|------|------|
| 公共镜像 | 阿里云官方提供的操作系统镜像（CentOS、Ubuntu、Windows 等） |
| 自定义镜像 | 用户基于实例创建的镜像 |
| 共享镜像 | 其他账户共享的镜像 |
| 市场镜像 | 阿里云市场提供的预装软件镜像 |

#### AWS AMI 类型

| 类型 | 说明 |
|------|------|
| 公有 AMI | AWS 官方或社区提供的镜像 |
| 私有 AMI | 用户自己创建的镜像 |
| 共享 AMI | 其他账户共享的镜像 |
| AWS Marketplace AMI | 市场提供的预装软件镜像 |

### 3.3 存储类型

#### 阿里云 ECS 存储

| 类型 | 性能 | 适用场景 |
|------|------|----------|
| 高效云盘（ESSD PL0） | 5000 IOPS | 通用场景 |
| 性能云盘（ESSD PL1） | 10000 IOPS | 高 IO 场景 |
| 极速云盘（ESSD PL2） | 50000 IOPS | 超高性能场景 |
| 本地 SSD | 极高 IOPS，本地磁盘 | 大数据、临时存储 |
| 普通云盘 | 较低性能，性价比高 | 归档、日志 |

#### AWS EC2 存储

| 类型 | 性能 | 适用场景 |
|------|------|----------|
| General Purpose SSD (gp2/gp3) | 3000 IOPS (gp2) / 16000 IOPS (gp3) | 通用场景 |
| Provisioned IOPS SSD (io1/io2) | 64000 IOPS | 高 IO 数据库 |
| Throughput Optimized HDD (st1) | 高吞吐 | 大数据、日志 |
| Cold HDD (sc1) | 低成本 | 归档存储 |
| Instance Store | 本地 SSD，极高性能 | 临时存储 |

### 3.4 实例状态

| 阿里云状态 | AWS 状态 | 说明 |
|------------|----------|------|
| Running | running | 运行中 |
| Stopped | stopped | 已停止 |
| Starting | pending | 启动中 |
| Stopping | stopping | 停止中 |
| Terminated | terminated | 已释放 |

## 四、存储服务

### 4.1 对象存储

#### 阿里云 OSS（Object Storage Service）

- **存储类型**：
  - 标准存储：高频访问，毫秒级响应
  - 低频访问存储：访问频率低，30天以上不访问
  - 归档存储：长期归档，恢复时间小时级
  - 冷归档存储：极低频访问，恢复时间天数级

- **访问控制**：
  - Bucket ACL：私有、公共读、公共读写
  - RAM 权限：细粒度权限控制
  - 签名 URL：临时访问链接

- **生命周期管理**：自动转换存储类型或删除

#### AWS S3（Simple Storage Service）

- **存储类别**：
  - S3 Standard：高频访问
  - S3 Standard-IA：低频访问
  - S3 Intelligent-Tiering：智能分层
  - S3 Glacier：归档存储
  - S3 Glacier Deep Archive：深度归档

- **访问控制**：
  - Bucket Policy：资源级权限
  - IAM Policy：身份级权限
  - ACL：基础访问控制

### 4.2 块存储

见第三章"计算服务-存储类型"

### 4.3 文件存储

#### 阿里云 NAS

- 协议：NFS、SMB
- 场景：容器共享存储、大数据分析、内容管理

#### AWS EFS

- 协议：NFS
- 特点：可扩展、共享访问、区域冗余

## 五、数据库服务

### 5.1 关系型数据库（RDS）

#### 阿里云 RDS 支持的引擎

| 引擎 | 版本 | 说明 |
|------|------|------|
| MySQL | 5.6, 5.7, 8.0 | 开源关系型数据库 |
| PostgreSQL | 9.4-15 | 开源关系型数据库 |
| SQL Server | 2008-2022 | 微软商业数据库 |
| MariaDB | 10.2-10.6 | MySQL 分支 |
| Oracle | 11g, 12c, 19c | 商业数据库 |

#### AWS RDS 支持的引擎

| 引擎 | 版本 | 说明 |
|------|------|------|
| MySQL | 5.7, 8.0 | 开源关系型数据库 |
| PostgreSQL | 9.6-16 | 开源关系型数据库 |
| SQL Server | 2012-2022 | 微软商业数据库 |
| MariaDB | 10.2-10.6 | MySQL 分支 |
| Oracle | 11g-21c | 商业数据库 |
| Aurora | MySQL/PostgreSQL 兼容 | AWS 自研高性能数据库 |

### 5.2 数据库实例类型

#### 阿里云 RDS 规格族

| 规格族 | 特点 |
|--------|------|
| rds.mysql.c1 | 入门级 |
| rds.mysql.c2 | 标准级 |
| rds.mysql.c3 | 高性能级 |
| rds.mysql.c6 | 新一代通用型 |
| rds.mysql.r6 | 内存优化型 |

#### AWS RDS 规格族

| 规格族 | 特点 |
|--------|------|
| db.t2/db.t3 | 突发性能型 |
| db.m5/db.m6 | 通用型 |
| db.c5/db.c6 | 计算优化型 |
| db.r5/db.r6 | 内存优化型 |
| db.p3/db.p4 | GPU 加速型 |

### 5.3 高可用架构

- **阿里云**：主备架构，自动故障切换，跨可用区部署
- **AWS**：多可用区部署，自动故障切换，读取副本

### 5.4 数据库连接

- **阿里云**：通过内网或外网地址连接，支持 SSL
- **AWS**：通过端点（Endpoint）连接，支持 SSL

## 六、安全体系

### 6.1 身份与权限管理

#### 阿里云 RAM（Resource Access Management）

- **用户（User）**：独立的身份，有自己的 AccessKey
- **用户组（Group）**：用户的集合，便于批量授权
- **角色（Role）**：临时权限，用于跨账户或服务间访问
- **权限策略（Policy）**：JSON 格式的权限定义

#### AWS IAM（Identity and Access Management）

- **用户（User）**：独立身份
- **用户组（Group）**：用户集合
- **角色（Role）**：临时权限
- **策略（Policy）**：JSON 格式权限定义
- **权限边界（Permission Boundary）**：限制最大权限

### 6.2 密钥管理

#### 阿里云 KMS（Key Management Service）

- 对称加密密钥
- 非对称加密密钥
- HSM 支持（硬件安全模块）
- 密钥轮换

#### AWS KMS（Key Management Service）

- 对称加密密钥
- 非对称加密密钥
- HSM 支持（AWS CloudHSM）
- 密钥轮换

### 6.3 网络安全

见第二章"网络基础"

### 6.4 数据保护

- **快照（Snapshot）**：磁盘或卷的时间点备份
- **备份（Backup）**：数据库的定期备份
- **加密（Encryption）**：静态数据加密、传输加密

## 七、负载均衡

### 7.1 阿里云 SLB（Server Load Balancer）

#### SLB 类型

| 类型 | 说明 | 协议 |
|------|------|------|
| 经典型负载均衡 | 基础版，支持四层和七层 | TCP/UDP/HTTP/HTTPS |
| 应用型负载均衡 | 增强版，更多高级功能 | HTTP/HTTPS/QUIC |
| 网络型负载均衡 | 纯四层，高性能 | TCP/UDP |

#### SLB 组件

- **负载均衡实例**：接收和分发流量
- **监听（Listener）**：定义端口和协议
- **后端服务器（Backend Server）**：处理实际请求
- **健康检查**：自动检测后端服务器状态

### 7.2 AWS ELB（Elastic Load Balancing）

#### ELB 类型

| 类型 | 说明 | 协议 |
|------|------|------|
| Application Load Balancer (ALB) | 七层负载均衡 | HTTP/HTTPS/WebSocket |
| Network Load Balancer (NLB) | 四层负载均衡 | TCP/UDP/TLS |
| Classic Load Balancer (CLB) | 传统负载均衡 | TCP/SSL/HTTP/HTTPS |

#### ELB 组件

- **负载均衡器**：接收和分发流量
- **监听（Listener）**：定义端口和协议
- **目标组（Target Group）**：管理后端目标
- **健康检查**：自动检测目标状态

## 八、监控与运维

### 8.1 监控服务

#### 阿里云 CloudMonitor

- 云服务监控
- 自定义监控
- 告警服务
- 仪表盘

#### AWS CloudWatch

- 指标监控
- 日志管理
- 告警服务
- 仪表盘

### 8.2 日志服务

#### 阿里云 Log Service

- 日志采集
- 日志存储
- 日志分析
- 实时查询

#### AWS CloudWatch Logs

- 日志采集
- 日志存储
- 日志分析
- 跨账户日志

### 8.3 运维管理

#### 阿里云运维服务

- 云助手：远程执行命令
- 运维编排：自动化运维流程
- 弹性伸缩：自动调整实例数量

#### AWS 运维服务

- Systems Manager：远程管理
- Step Functions：工作流编排
- Auto Scaling：自动伸缩

## 九、资源命名规范

### 9.1 通用命名规范

```
{环境}-{服务类型}-{用途}-{序号}
```

示例：
- `dev-ecs-web-01`
- `prod-rds-mysql-primary`
- `test-slb-api-gateway`

### 9.2 标签规范

| 标签键 | 说明 | 示例值 |
|--------|------|--------|
| Environment | 环境 | dev, test, prod |
| Application | 应用名称 | web, api, database |
| Owner | 负责人 | team-a, john.doe |
| CostCenter | 成本中心 | cc-1234 |
| CreatedBy | 创建方式 | terraform, manual |

## 十、阿里云与 AWS 服务对照表

| 类别 | 阿里云 | AWS | 说明 |
|------|--------|-----|------|
| **计算** | ECS | EC2 | 云服务器 |
| | ECI | Fargate | 容器实例 |
| | Serverless 应用引擎 | Lambda | 无服务器计算 |
| **网络** | VPC | VPC | 虚拟私有云 |
| | VSwitch | Subnet | 子网 |
| | EIP | Elastic IP | 弹性公网 IP |
| | NAT Gateway | NAT Gateway | NAT 网关 |
| | VPN Gateway | VPN | VPN 连接 |
| | Express Connect | Direct Connect | 专线连接 |
| **存储** | OSS | S3 | 对象存储 |
| | ESSD/EBS | EBS | 块存储 |
| | NAS | EFS | 文件存储 |
| | 本地 SSD | Instance Store | 本地存储 |
| **数据库** | RDS | RDS | 关系型数据库 |
| | Redis | ElastiCache | 缓存服务 |
| | MongoDB | DocumentDB | 文档数据库 |
| | PolarDB | Aurora | 云原生数据库 |
| **安全** | RAM | IAM | 身份权限管理 |
| | KMS | KMS | 密钥管理服务 |
| | 安全组 | Security Group | 虚拟防火墙 |
| | 云安全中心 | GuardDuty | 安全检测 |
| **负载均衡** | SLB | ALB/NLB | 负载均衡 |
| **监控** | CloudMonitor | CloudWatch | 云监控 |
| | Log Service | CloudWatch Logs | 日志服务 |
| **消息队列** | MQ | SQS/SNS | 消息队列 |
| **大数据** | MaxCompute | EMR | 大数据计算 |
| **容器** | ACK | EKS | 容器服务 |
| **CDN** | CDN | CloudFront | 内容分发 |

## 十一、常见资源参数速查

### 11.1 实例规格速查

#### 阿里云常用规格

| 规格 | vCPU | 内存(GB) | 适用场景 |
|------|------|----------|----------|
| ecs.g6.large | 2 | 8 | 通用型 |
| ecs.g6.xlarge | 4 | 16 | 通用型 |
| ecs.c6.large | 2 | 4 | 计算型 |
| ecs.c6.xlarge | 4 | 8 | 计算型 |
| ecs.r6.large | 2 | 16 | 内存型 |
| ecs.r6.xlarge | 4 | 32 | 内存型 |

#### AWS 常用规格

| 规格 | vCPU | 内存(GB) | 适用场景 |
|------|------|----------|----------|
| t3.medium | 2 | 4 | 开发测试 |
| t3.large | 2 | 8 | 开发测试 |
| m5.large | 2 | 8 | 通用型 |
| m5.xlarge | 4 | 16 | 通用型 |
| c5.large | 2 | 4 | 计算型 |
| r5.large | 2 | 16 | 内存型 |

### 11.2 磁盘类型速查

#### 阿里云磁盘类型

| 类型 | IOPS | 吞吐量(MB/s) | 价格 |
|------|------|--------------|------|
| 高效云盘 | 5000 | 300 | 中 |
| 性能云盘 | 10000 | 500 | 较高 |
| 极速云盘 | 50000 | 1000 | 高 |

#### AWS EBS 类型

| 类型 | IOPS | 吞吐量(MB/s) | 价格 |
|------|------|--------------|------|
| gp2 | 3000 | 250 | 中 |
| gp3 | 16000 | 1000 | 中 |
| io1/io2 | 64000 | 1000 | 高 |

### 11.3 区域与可用区速查

#### 阿里云（国内常用）

| 区域 | 可用区数量 | 可用区标识 |
|------|-----------|-----------|
| cn-hangzhou | 8 | a, b, c, d, e, f, g, h |
| cn-shanghai | 5 | a, b, c, d, e |
| cn-beijing | 6 | a, b, c, d, e, f |
| cn-shenzhen | 4 | a, b, c, d |

#### AWS（常用）

| 区域 | 可用区数量 | 可用区标识 |
|------|-----------|-----------|
| us-east-1 | 6 | a, b, c, d, e, f |
| us-west-2 | 4 | a, b, c, d |
| eu-west-1 | 3 | a, b, c |
| ap-southeast-1 | 3 | a, b, c |

## 十二、Terraform 资源属性与依赖关系

### 12.1 资源属性类型

Terraform 中云资源的属性分为以下几类：

| 属性类型 | 说明 | 示例 |
|----------|------|------|
| **ID 属性** | 资源的唯一标识符，通常用于依赖引用 | `id`, `vpc_id`, `instance_id` |
| **网络属性** | 网络相关配置，用于建立网络连接 | `cidr_block`, `public_ip`, `private_ip` |
| **配置属性** | 用户指定的配置参数 | `instance_type`, `engine_version`, `storage_size` |
| **计算属性** | Terraform 自动计算的值 | `arn`, `connection_string`, `dns_name` |
| **状态属性** | 资源运行时状态 | `status`, `availability`, `health_status` |

### 12.2 常用资源属性速查

#### 网络资源属性

| 资源 | 属性 | 说明 | 依赖用途 |
|------|------|------|----------|
| **VPC** | `id` | VPC 唯一标识 | 子网、安全组、实例引用 |
| | `cidr_block` | IP 地址范围 | 子网规划 |
| **VSwitch/Subnet** | `id` | 子网唯一标识 | 实例、RDS、SLB 引用 |
| | `vpc_id` | 所属 VPC | 隐式依赖 VPC |
| | `availability_zone` | 可用区 | 实例部署 |
| **Security Group** | `id` | 安全组唯一标识 | 实例、RDS、SLB 引用 |
| | `vpc_id` | 所属 VPC | 隐式依赖 VPC |
| **EIP/Elastic IP** | `id` | EIP 唯一标识 | 绑定到实例/SLB |
| | `public_ip` | 公网 IP 地址 | 输出或配置 |
| **NAT Gateway** | `id` | NAT 网关唯一标识 | 路由表引用 |
| **Internet Gateway** | `id` | IGW 唯一标识 | 路由表引用 |

#### 计算资源属性

| 资源 | 属性 | 说明 | 依赖用途 |
|------|------|------|----------|
| **ECS/EC2** | `id` | 实例唯一标识 | 输出、负载均衡后端 |
| | `instance_id` | 实例 ID | 同 `id` |
| | `vpc_id` | 所属 VPC | 隐式依赖 VPC |
| | `vswitch_id/subnet_id` | 所属子网 | 隐式依赖子网 |
| | `security_groups` | 安全组列表 | 隐式依赖安全组 |
| | `public_ip` | 公网 IP | 输出、访问配置 |
| | `private_ip` | 私网 IP | 内部通信 |
| | `availability_zone` | 可用区 | 高可用部署 |
| | `image_id` | 镜像 ID | 依赖镜像 data source |

#### 存储资源属性

| 资源 | 属性 | 说明 | 依赖用途 |
|------|------|------|----------|
| **OSS/S3 Bucket** | `id` | Bucket 唯一标识 | 输出、其他资源引用 |
| | `bucket` | Bucket 名称 | 访问配置 |
| | `arn` | AWS ARN | IAM 策略引用 |
| | `region` | 区域 | 跨区域复制 |
| **ESSD/EBS Volume** | `id` | 磁盘唯一标识 | 附加到实例 |
| | `size` | 磁盘大小 | 容量规划 |
| | `instance_id` | 挂载的实例 | 隐式依赖实例 |

#### 数据库资源属性

| 资源 | 属性 | 说明 | 依赖用途 |
|------|------|------|----------|
| **RDS** | `id` | 数据库唯一标识 | 输出、配置 |
| | `connection_string` | 连接地址 | 应用配置 |
| | `port` | 端口号 | 应用配置 |
| | `vswitch_id/subnet_group_name` | 子网 | 隐式依赖子网 |
| | `security_group_ids` | 安全组列表 | 隐式依赖安全组 |
| | `db_instance_id` | 实例 ID | 同 `id` |

#### 负载均衡属性

| 资源 | 属性 | 说明 | 依赖用途 |
|------|------|------|----------|
| **SLB/ALB** | `id` | 负载均衡唯一标识 | 输出、配置 |
| | `dns_name` | 域名 | 应用配置、DNS 记录 |
| | `vswitch_id/subnets` | 子网 | 隐式依赖子网 |
| | `security_group_ids` | 安全组列表 | 隐式依赖安全组 |
| | `load_balancer_arn` | AWS ARN | 监听、目标组引用 |
| **Target Group** | `id` | 目标组唯一标识 | 监听引用 |
| | `arn` | AWS ARN | 监听引用 |

### 12.3 资源依赖关系

#### 依赖关系类型

| 依赖类型 | 说明 | 示例 |
|----------|------|------|
| **显式依赖** | 通过 `depends_on` 显式声明 | 资源创建顺序控制 |
| **隐式依赖** | 通过属性引用自动推断 | `vpc_id = alicloud_vpc.example.id` |
| **模块依赖** | 跨模块的输出引用 | 模块输出作为输入 |

#### 典型依赖链

```
VPC → VSwitch/Subnet → ECS/EC2
       ↓                ↓
       ↓                ↓
  Security Group ←───────┘
       ↓
       ↓
  RDS / SLB / NAT Gateway
```

#### 详细依赖关系图

```
                     ┌──────────────────────────────────────┐
                     │              VPC                      │
                     │  (cidr_block, id)                     │
                     └───────────────┬──────────────────────┘
                                     │
          ┌──────────────────────────┼──────────────────────────┐
          │                          │                          │
          ↓                          ↓                          ↓
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│    VSwitch       │    │  Security Group  │    │  Route Table     │
│ (vpc_id, id)     │    │  (vpc_id, id)    │    │  (vpc_id)        │
└────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
         │                       │                       │
┌────────┴─────────┐    ┌────────┴─────────┐    ┌────────┴─────────┐
│     ECS/EC2      │    │      RDS         │    │   NAT Gateway    │
│ (vswitch_id,     │    │ (vswitch_id,     │    │ (vswitch_id,     │
│  security_groups)│    │  security_groups)│    │  security_groups)│
└────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
         │                       │                       │
         ↓                       ↓                       ↓
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│    EIP           │    │    OSS/S3        │    │   SLB/ALB        │
│ (instance_id)    │    │  (region)        │    │ (vswitch_id,     │
└──────────────────┘    └──────────────────┘    │  security_groups)│
                                                 └────────┬─────────┘
                                                          │
                                                  ┌────────┴─────────┐
                                                  │   Target Group    │
                                                  │ (vpc_id)          │
                                                  └──────────────────┘
```

#### 阿里云资源依赖关系表

| 资源 | 必须依赖 | 可选依赖 |
|------|----------|----------|
| VSwitch | VPC | — |
| Security Group | VPC | — |
| ECS | VSwitch, Security Group | EIP |
| RDS | VSwitch, Security Group | — |
| SLB | VSwitch | Security Group |
| NAT Gateway | VSwitch | — |
| OSS Bucket | — | — |
| EIP | — | ECS, SLB |

#### AWS 资源依赖关系表

| 资源 | 必须依赖 | 可选依赖 |
|------|----------|----------|
| Subnet | VPC | — |
| Security Group | VPC | — |
| EC2 | Subnet, Security Group | Elastic IP |
| RDS | DB Subnet Group, Security Group | — |
| ALB | Subnets, Security Group | — |
| NAT Gateway | Subnet, Elastic IP | — |
| S3 Bucket | — | — |
| Internet Gateway | VPC | — |

### 12.4 属性引用示例

#### 阿里云属性引用

```hcl
resource "alicloud_vpc" "main" {
  name       = "main-vpc"
  cidr_block = "10.0.0.0/16"
}

resource "alicloud_vswitch" "public" {
  vpc_id            = alicloud_vpc.main.id        # 依赖 VPC
  cidr_block        = "10.0.1.0/24"
  availability_zone = "cn-hangzhou-a"
}

resource "alicloud_security_group" "web" {
  name   = "web-sg"
  vpc_id = alicloud_vpc.main.id                   # 依赖 VPC
}

resource "alicloud_instance" "web" {
  instance_name     = "web-server"
  image_id          = data.alicloud_images.centos.images[0].id  # 依赖 data source
  instance_type     = "ecs.g6.large"
  vswitch_id        = alicloud_vswitch.public.id  # 依赖子网
  security_groups   = [alicloud_security_group.web.id]  # 依赖安全组
}

resource "alicloud_slb_load_balancer" "web" {
  load_balancer_name = "web-slb"
  vswitch_id         = alicloud_vswitch.public.id  # 依赖子网
}

output "instance_ip" {
  value = alicloud_instance.web.public_ip         # 输出实例公网 IP
}

output "slb_dns" {
  value = alicloud_slb_load_balancer.web.dns_name # 输出 SLB 域名
}
```

#### AWS 属性引用

```hcl
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_subnet" "public" {
  vpc_id            = aws_vpc.main.id             # 依赖 VPC
  cidr_block        = "10.0.1.0/24"
  availability_zone = "us-east-1a"
}

resource "aws_security_group" "web" {
  name   = "web-sg"
  vpc_id = aws_vpc.main.id                        # 依赖 VPC
}

resource "aws_instance" "web" {
  ami                    = data.aws_ami.amazon_linux.id  # 依赖 data source
  instance_type          = "t3.medium"
  subnet_id              = aws_subnet.public.id         # 依赖子网
  vpc_security_group_ids = [aws_security_group.web.id]  # 依赖安全组
}

resource "aws_lb" "web" {
  name               = "web-alb"
  subnets            = [aws_subnet.public.id]           # 依赖子网
  security_groups    = [aws_security_group.web.id]      # 依赖安全组
}

output "instance_ip" {
  value = aws_instance.web.public_ip                  # 输出实例公网 IP
}

output "lb_dns" {
  value = aws_lb.web.dns_name                         # 输出 ALB 域名
}
```

### 12.5 常用 Data Source 属性

#### 阿里云 Data Source

| Data Source | 常用属性 | 用途 |
|-------------|----------|------|
| `alicloud_images` | `images[*].id`, `images[*].name` | 获取镜像 ID |
| `alicloud_zones` | `zones[*].id`, `zones[*].local_name` | 获取可用区列表 |
| `alicloud_instance_types` | `instance_types[*].instance_type` | 获取可用实例规格 |
| `alicloud_vpcs` | `vpcs[*].id`, `vpcs[*].cidr_block` | 查询现有 VPC |

#### AWS Data Source

| Data Source | 常用属性 | 用途 |
|-------------|----------|------|
| `aws_ami` | `id`, `name`, `owner` | 获取 AMI ID |
| `aws_availability_zones` | `names` | 获取可用区列表 |
| `aws_instance_types` | `instance_types` | 获取可用实例规格 |
| `aws_vpcs` | `id`, `cidr_block` | 查询现有 VPC |

#### Data Source 使用示例

```hcl
data "alicloud_images" "centos" {
  name_regex = "^centos_7_9_x64_20G_alibase.*"
  owners     = "system"
}

resource "alicloud_instance" "example" {
  image_id = data.alicloud_images.centos.images[0].id
}

data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

resource "aws_instance" "example" {
  ami = data.aws_ami.amazon_linux.id
}
```

## 十三、参考资料

- [阿里云官方文档](https://help.aliyun.com)
- [AWS 官方文档](https://docs.aws.amazon.com)
- [阿里云 Terraform Provider](https://registry.terraform.io/providers/aliyun/alicloud/latest)
- [AWS Terraform Provider](https://registry.terraform.io/providers/hashicorp/aws/latest)