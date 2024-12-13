## 不同:

### leader选举, 

**raft**先发起投票的会有优先取得leader的特点, 通過隨機喚醒降低同時被喚醒的可能, 如果同時喚醒導致不過半, 會重新選舉.
**zab**需要投票pk, 比ZXID, 比較完後, 小的會改成投大的.

leader重新選舉後, zab對外提供服務前, 還會同步follower, RAFT則延後處理(伴隨新的過半Proposal).

### 跨代處理

**ZAB** 選出 ZXID 最大的(包括未commit), 並提交/同步當前leader上, 所有**未commit/commit未過半**的Proposal到其他follower.
當然, 如果剩餘的未宕機的follower沒包含最新的ZXID, 那只能忽略(拋棄)這些未同步的消息.

**RAFT** 則選出**最大已commit**, 
但**不直接提交跨代**Proposal, 必须要**等到当前 term 有 Proposal 过半**了，才顺便将**之前** term 的 Proposals 进行**一起提交**。



### 心跳

ZAB: **leader檢測是否有过半 Follower 心跳回复**, **Follower 也检测 Leader 是否发送心跳了**.

RAFT: **只有Follower**檢查心跳, **超時就發起選舉**.



## 相同

写都只能在leader,
如果非leader接受到写请求, 会由`当前非leader`**代为转发**到`leader`

写都需要过半node





## 參考: 

[multi-paxos、raft和zab协议的核心区别](https://cloud.tencent.com/developer/article/1903522)

[分布式协议Paxos、Raft和ZAB](https://beritra.github.io/2020/06/12/%E5%88%86%E5%B8%83%E5%BC%8F%E5%8D%8F%E8%AE%AEPaxos%E3%80%81Raft%E5%92%8CZAB/)

