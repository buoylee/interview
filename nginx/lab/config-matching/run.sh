#!/usr/bin/env bash
set -euo pipefail

B=http://localhost:18080

check () {
    local path="$1" want="$2"
    local got
    got=$(curl -s "$B$path")
    echo "$path -> $got"
    [[ "$got" == *"$want"* ]] || { echo "FAIL: $path expected '$want', got '$got'"; exit 1; }
}

# 優先級 1:= 精確比對
check /exact            "matched: exact"

# 優先級 2:^~ 前綴止步(不再看正則)
check /prefix-stop/x    "matched: prefix-stop"

# 優先級 3b:~* 大小寫不敏感正則(大寫 .JPG)
check /a.JPG            "matched: regex-image"

# 優先級 3a:~ 大小寫敏感正則
check /api/users        "matched: regex-api"

# 優先級 4:最長一般前綴回退
check /whatever         "matched: longest-prefix"

# ch02 rewrite last:改 URI 後重走 location 匹配,命中 /new/
check /old/thing        "matched: new"

echo "ALL PASS"
