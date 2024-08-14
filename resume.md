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

##### java / golang, 深圳市赢胜数据科技有限公司(外包baidu), 2021.04 - 2022.09

- GRAVITY IM子系统的2次开发.
- 编写功能设计文档.
- 外包人员面试.
- 系统上线, aws操作等.

##### golang / java, 深圳文思海辉信息技术有限公司(外包微众银行), 2019.04 - 2020.10

- 6人开源项目团队中主要负责ML支持平台的golang开发, 已有部分代码开源.
- 编写功能设计文档.
- 外包人员面试.
- k8s运维.

##### java, 符号树, 2019.01 - 2019.04

- 项目主要的背单词功能,及数学学习功能.
- 背单词模块反响不错,目前在实体店面有100+体验用户.
- 实现了单词学习记录同步redis与db同步, 记录重复提交问题, redis中数据一致性问题.

##### java, 深圳蜜平台科技有限公司, 2018.04 - 2018.08

- 香港保险经纪团队管理系统. 后端开发. 部分数据库设计,架构分析. 极少部分前端开发.
- 保单审批,佣金计算,保费预算,通知提醒模块等.
- 阿里云,mysql,springboot,nginx. 缓存使用guava loadingcache. gitlab,docker持续集成,tapd项目管理.

##### java, 海南乐狐网络, 2016.06-2017.10

- 网络直播兼酒吧大屏系统综合社交app, java 后端, 只要使用 ssm 框架.
- 聊天室及成员等级管理.
- 网易云信后端api接入,群发系统消息,关联本地用户信息与云信用户信息等功能.
- 首页活动宣传广告banner 乐活live(大屏互动功能),建立在群组基础上的玩法.

#### PROJECTS

##### GRAVITY social media IM子系统; 外包(百度)

- 配合 GRAVITY chat 相关业务功能扩展.
- 优化 IM msg 收发存储处理逻辑, 消除带状态服务, 使得更方便容器部署扩容, 提高可用性. 单台 msg handler 的 msg/sec
  由140+提高到150+, 提升了7%
- java 服务 k8s容器化. 使实例扩容半自动化, 灰度上线/测试半自动化.
- 涉及 netty, protobuf, grpc, Sharding-JDBC, nginx 技术应用.

##### Prophecis: 机器学习支持平台; 外包(微众银行)

###### Github: https://github.com/WeBankFinTech/Prophecis

- 角色权限子服务, 前期java springboot, mybatis, mysql. 后序用go重写, 使用swagger-go, gorm.
- 使用 **nginx** 对 jupyter访问前的 发起校验与请求rewrite. **caddy** 作为 后端 api gateway.
- 优化 **平台资源校验** 与 **任务状态监控和日志收集(fluent-bit, es)**, 调整 执行队列. 任务命令行工具适配. 服务间调用使用
  **grpc**.
- 整合 kubeflow 多learner训练, jupyter 容器化.
- 使用 gitlab, jenkins, 进行项目 CI/CD.

#### ADDITIONAL INFORMATION

- 全国计算机技术与软件专业技术资格考试 网络工程师(中级)
