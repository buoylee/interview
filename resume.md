<center><font size="5">李宏俊</font></center>

<center><font size="2">地址: 南山大新 || 手机: 15501899800 || 邮箱: buoy_lee@163.com || github.com/buoylee</font></center>

<center><font size="2">状态: 离职-随时到岗 || 期望薪资: 19-24K</font></center>

<center><font size="5"></font></center>

#### 概述 SUMMARY

寻找 golang / java 后端开发工作, 热衷机器学习或相关支持项目.

2016年 开始, 5年 java 和 2年 golang 开发经验. leetcode 1-400题 2刷. 

#### 教育经历 EDUCATION

本科, 广州大学华软软件学院, **网络工程**专业, 2008-2012

#### 个人技能 SKILLS

- 熟悉 java JVM / NIO / 并发编程
- 熟悉 golang routine / GC / 并发编程
- 熟悉 spring mvc, springboot, mybatis 及其部分源码.
- 熟悉 swagger-go / gorm 框架使用.
- 熟悉 netty, 熟悉 rpc, grpc, protobuf 使用.
- 熟悉 mysql, 了解 sharding-jdbc 分库分表.
- 熟悉 redis, 了解 twemproxy 使用.
- 熟悉 zookeeper, 作分布式协调或分布式锁使用.
- 熟悉 nginx / caddy 使用.
- 熟悉 docker / kubernetes(k8s), 有1年k8s运维, 4年使用经验.
- 熟悉 git / maven.
- 比较熟悉 mongo, 了解 elasticsearch 使用.
- 熟悉 数据结构与算法.
- 熟悉 基本 js / html, 前后端分离开发.
- 熟悉 分布式系统, 分布式缓存
- 了解 分布式事务, tcc/saga

#### 工作经验 WORK EXPERIENCE

##### java, 中软(外包交行), 2024.09 - 至今

- 押品服务迁移云上, 接入行内 skywalking.

##### java / golang, 深圳市赢胜数据科技有限公司(外包baidu), 2021.04 - 2024.03

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

#### 项目经验 PROJECTS

##### 押品服务; 外包(上海交行); 2024.03 - 至今

提供抵押品入库, 抵押品借用, 押品审定, 押品出库等业务. springcloud, mybatis, k8s, skywalking, seata等.

##### social media IM子系统; 外包(百度); 2021.04 - 2024.03

baidu im 服务前身 2次开发, 给 GRAVITY 提供 im 服务. 由 10+ c++ 子服务 和 5个 java 子服务 构成的分布式 im系统.  
im 同时在线人数一般在 1500 左右. 高峰有 4000.
包含 java 子服务 dev/test/prod 环境 和 ci/cd 搭建.  social media 与 im 相关部分的 golang 业务开发.

- 优化 IM msg handler 转发消息逻辑, 取消了只能由某台 msg handler 处理指定p2p消息的限制, 从而消除了带状态的服务, 使得qps更高, 也更方便容器部署扩容, 提高可用性. 单台 msg handler 的 qps
  由140+提高到150+, 提升了7%
- 所有 java 组件 k8s容器化. 由固定的IP配置, 改为从 k8s service 解析出ip, 动态更新负载均衡的实际ip.
- 负责上线, k8s容器化后, 使实例扩容半自动化, 灰度上线/测试半自动化.
- 通过springboot构建 msg-forward 服务, 用于在 gateway 发起向 chat bot 发送消息时, 通过 msg-forward 调用 chat bot 聊天接口. 然后 chat bot 异步调用 msg-forward 发送接口回传消息.
- 在 social media 后台取出活动user, 向 kafka 发送需要推送的消息. 在 msg-forward, 新增拉取 kafka 消息, 通过 gateway 给user发送活动消息推送.
- 将用户消息表单独提出来, 用 Sharding-JDBC 做分库分表
- 组件通信接口使用 netty, protobuf.

##### Prophecis: 机器学习支持平台; 外包(微众银行); 2019.04 - 2020.10

###### Github: https://github.com/WeBankFinTech/Prophecis

- 角色权限子服务, 前期java springboot, mybatis, mysql. 后序用go重写, 使用swagger-go, gorm.
- 使用 **nginx** 对 jupyter访问前的 发起校验与请求rewrite. **caddy** 作为 后端 api gateway.
- 优化 **平台资源校验** 与 **任务状态监控和日志收集(fluent-bit, es)**, 调整 执行队列. 任务命令行工具适配. 服务间调用使用
  **grpc**.
- 整合 kubeflow 多learner训练, jupyter 容器化.
- 使用 gitlab, jenkins, 进行项目 CI/CD.

##### 娱乐视频直播兼酒吧大屏; 海南乐狐网络; 2016.06-2017.10

- 主要负责java后端业务逻辑接口开发,部分数据表设计,H5端的js部分开发. 
- 真人视频直播,使用3方的网易云直播, 后改阿里云视频直播, 聊天室使用网易云IM, 短信服务阿里大鱼, 
- 后端涉及用户, 聊天室信息接口等,发礼物,霸屏,竞猜,酒吧大屏小游戏(数钱,抽奖,配对)逻辑等. 前端涉及客服im,数钱小游戏等. 
- aliyun服务器,tomcat,dubbo,springmvc,hibernate,mysql等. 
- 积极配合产品经理完善产品功能,用户量提高较慢.

#### 其他信息 ADDITIONAL INFORMATION

- 全国计算机技术与软件专业技术资格考试 网络工程师(中级)
