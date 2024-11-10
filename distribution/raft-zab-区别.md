## 不同:

leader选举, raft先发起投票的会有优先取得leader的特点, zab需要投票pk.

## 相同

写都只能在leader,
如果非leader接受到写请求, 会由`当前非leader`**代为转发**到`leader`

写都需要过半node

