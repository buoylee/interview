<center><font size="5">李宏俊</font></center>

<center><font size="2">Address: 南山大新 || Phone: 15501899800 || buoy_lee@163.com || github.com/buoylee</font></center>

<center><font size="2">状态: 离职-随时到岗 || 期望薪资: 30K</font></center>

<center><font size="5"></font></center>

#### SUMMARY

寻找 golang / java 后端开发工作, 热衷机器学习或相关支持项目.

2016年 开始, 7年**软件开发**经验. leetcode 1-400题 2刷. 上次离职原因: 考托福.

#### EDUCATION

本科, 广州大学华软软件学院, **网络工程**专业, 2008-2012

#### SKILLS

编程语言: java / golang.

Databases: MYSQL, redis, mongo, elasticsearch 经验.

CS: 熟练 数据结构与算法.

#### WORK EXPERIENCE

##### java / golang, 外包(百度), 2021.04 - 2022.09

- GRAVITY IM子系统的2次开发.
- 编写功能设计文档.
- 外包人员面试.
- 系统上线, aws操作等.

##### golang / java, 外包(微众银行), 2019.04 - 2020.10

- 6人开源项目团队中主要负责ML支持平台的golang开发, 已有部分代码开源.
- 编写功能设计文档.
- 外包人员面试.
- k8s运维.

#### PROJECTS

##### GRAVITY social media IM子系统

- 配合 GRAVITY chat 相关业务功能扩展.
- 优化 IM msg 收发存储处理逻辑, 消除带状态服务, 使得更方便容器部署扩容, 提高可用性. 单台 msg handler 的 msg/sec 由140+提高到150+, 提升了7%  
- java 服务 k8s容器化. 使实例扩容半自动化, 灰度上线/测试半自动化.
- 涉及 netty, protobuf, grpc, Sharding-JDBC, nginx 技术应用.

##### Prophecis: 机器学习支持平台

###### Github: https://github.com/WeBankFinTech/Prophecis

- 角色权限子服务, 前期java springboot, mybatis, mysql. 后序用go重写, 使用swagger-go, gorm.
- 使用 **nginx** 对 jupyter访问前的 发起校验与请求rewrite. **caddy** 作为 后端 api gateway.
- 优化 **平台资源校验** 与 **任务状态监控和日志收集(fluent-bit, es)**, 调整 执行队列. 任务命令行工具适配. 服务间调用使用**grpc**.
- 整合 kubeflow 多learner训练, jupyter 容器化.
- 使用 gitlab, jenkins, 进行项目 CI/CD.

#### ADDITIONAL INFORMATION

- 全国计算机技术与软件专业技术资格考试 网络工程师(中级)
