publish 写到文件(只有配置中心的数据写到mysql, 集群注册信息在本地file)
publish完,应该同步其他node. 但是nacos 直接更新内存, 然后再1阶段提交直接commit其他node. 这里使用了 countdownLatch,包括自己



## 流程

有master的心跳, 有 client心跳.

选举期间, 有随机休眠. 避免同时发起投票, 因为raft遇到同时发起选举, 会继续再休一轮. 再次尝试.
resetLeaderDue, resetHeartbeatDue; 重置nacos选举/心跳时间, 这2个是nacos节点间的检测, 只能由leader发起. (如果是client, 由client发起心跳)
local.term.incrementAndGet, local.voteFor = local.ip；local.state = RaftPeer.State.CANDIDATE; 选举世代+1, 投自己, 自己变成候选者.
发到其他nacos sendVote() `/raft/vote`, 异步回调等结果投给谁

同步数据时, 有个map 的 key : 0本地, 1远端. 
如果最后剩下0, 说明, 远端不存在这些数据, 需要删掉.