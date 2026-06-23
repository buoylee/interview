-- 固定窗口限流,原子執行(對應 ch05 §2 解法 B)。
-- KEYS[1] = 計數 key(如 rate:alice)
-- ARGV[1] = limit(窗口內允許的最大次數)
-- ARGV[2] = window 秒數
-- 回傳:當前計數(>=1),或 -1 表示已超限。
--
-- 為什麼要 Lua:INCR 之後「判斷是否首次以設定 EXPIRE」是讀-改-寫多步,
-- 多個網關節點並發時會競態。Redis 單線程內把整段腳本原子執行,杜絕競態。
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
end
if current > tonumber(ARGV[1]) then
    return -1
end
return current
