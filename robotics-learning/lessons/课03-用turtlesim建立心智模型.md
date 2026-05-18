# 课 3:用 turtlesim 建立心智模型

> 阶段 0 · 模块 A ｜ 时长 ~2h ｜ 前置:课 2
> **自学讲义** —— 这节不写代码,目标是"看见"四个核心概念。

## 这节课结束时,你能……

用大白话讲清 node / topic / service / action 各是什么,并各举一个 turtlesim 里的例子。

---

## 📖 讲解:机器人软件长什么样

### 它不是一个大程序,是一堆小程序

一个机器人系统不是一个巨型程序。它是**很多个小程序**,每个只管一摊事,彼此之间互相通话。

这跟你熟的**微服务架构**几乎一模一样:不是一个单体后端,而是一堆服务各司其职。区别只是——机器人这些"服务"要跟传感器、马达、物理世界打交道。

ROS 2 的全部意义,就是**让这些小程序方便地互相通话**。下面四个概念,就是它们通话的四种方式。

### 四个核心概念(用微服务类比)

**1. 节点 Node = 一个小程序 / 一个微服务**
每个节点干一件事。turtlesim 里:
- `turtlesim_node`:管小乌龟、画窗口 —— 一个节点。
- `turtle_teleop_key`:读你的键盘 —— 另一个节点。

**2. 话题 Topic = 持续的、单向的数据广播**
像消息队列里的一个 channel:有人源源不断往里发,有人订阅着源源不断收。**发的人和收的人互不认识。**
turtlesim 里:键盘节点把"速度命令"一直发到 `/turtle1/cmd_vel` 这个话题,乌龟节点订阅它、照着动。

**3. 服务 Service = 一问一答,要等回复**
像调一个同步 API:发一个请求,等一个响应。用完即止,不是持续的流。
turtlesim 里:"生成一只新乌龟"`/spawn`、"清屏"`/clear` —— 你调用它,它做完返回结果。

**4. 动作 Action = 有过程的长任务,能看进度、能中途取消**
像一个带进度条、可以取消的后台 job。
turtlesim 里:"把乌龟转到某个绝对角度"`/turtle1/rotate_absolute` —— 转需要时间,过程中能收到进度,也能喊停。

### 一句话记住区别

> **话题** = 持续广播的流 ｜ **服务** = 快问快答 ｜ **动作** = 可取消的长任务

后面模块 B/C/E 会分别动手做这三种。这节课只要"见过、玩过"。

---

## 🛠️ 动手

跟官方教程:**"Using turtlesim, ros2, and rqt"**
<https://docs.ros.org/en/jazzy/Tutorials/Beginner-CLI-Tools/Introducing-Turtlesim/Introducing-Turtlesim.html>

1. **开乌龟模拟器**(终端 1):
   ```bash
   ros2 run turtlesim turtlesim_node
   ```

2. **开键盘控制节点**(终端 2):
   ```bash
   ros2 run turtlesim turtle_teleop_key
   ```
   让终端 2 保持焦点,用方向键控制乌龟走动。← 你正在用**话题**。

3. **开 rqt**(终端 3):
   ```bash
   rqt
   ```
   在 rqt 里找到 "Service Caller" 插件,调用 `/spawn` 服务生成第二只乌龟。← 你正在用**服务**。

4. 边玩边对照上面四个概念,把"我现在用的是哪一种"想清楚。

---

## ⚠️ 踩坑预警

- **键盘控制没反应**:`turtle_teleop_key` 那个终端必须是当前焦点窗口,它才收得到按键。
- **每个节点要单独一个终端**:别想在一个终端里跑两个节点。
- **rqt 界面空白**:菜单 Plugins → Services → Service Caller 手动加载插件。

---

## ✅ 小检查(过了才算毕业)

在 `notes/课03-心智模型.md` 里,**用你自己的大白话**(不准抄教程原文)写出:
- node / topic / service / action 各是什么;
- 各举一个 turtlesim 里的具体例子。

写得出 → 课 3 通过。

---

## 🏁 收尾

1. 笔记 `notes/课03-心智模型.md` 写好(就是上面小检查的内容)。
2. 更新 `进度地图.md`:课 3 打勾、当前课→课 4、写交接笔记。
3. 提交:
   ```bash
   git add robotics-learning/
   git commit -m "robotics(phase0): 通过课 3,建立 ROS 2 心智模型"
   ```

---

## 📚 资源

- 官方教程 "Using turtlesim, ros2, and rqt":见上方链接。
- 卡壳超 ~2h → 带问题问 Claude。
