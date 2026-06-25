#!/usr/bin/env bash
set -euo pipefail

B=http://localhost:18082
N=10  # 每路徑連發次數（並行）

send_requests() {
    local path=$1
    local tmpdir
    tmpdir=$(mktemp -d)

    # 全部並行發出，結果存到獨立檔案保留順序
    for i in $(seq 1 $N); do
        curl -s -o /dev/null -w "%{http_code}" "${B}${path}" > "${tmpdir}/${i}" &
    done
    wait

    # 按序號讀回
    local codes=()
    for i in $(seq 1 $N); do
        codes+=("$(cat "${tmpdir}/${i}")")
    done
    rm -rf "${tmpdir}"
    echo "${codes[@]}"
}

echo "=== /strict/ (無 burst) ==="
strict_codes=$(send_requests "/strict/")
echo "狀態碼: $strict_codes"
strict_200=$(echo "$strict_codes" | tr ' ' '\n' | grep -c "^200$" || true)
strict_429=$(echo "$strict_codes" | tr ' ' '\n' | grep -c "^429$" || true)
echo "200 數: $strict_200  |  429 數: $strict_429"

echo ""
echo "=== /burst/ (burst=5 nodelay) ==="
burst_codes=$(send_requests "/burst/")
echo "狀態碼: $burst_codes"
burst_200=$(echo "$burst_codes" | tr ' ' '\n' | grep -c "^200$" || true)
burst_429=$(echo "$burst_codes" | tr ' ' '\n' | grep -c "^429$" || true)
echo "200 數: $burst_200  |  429 數: $burst_429"

echo ""
echo "=== 驗證 ==="
PASS=true

if [ "$strict_200" -ge "$burst_200" ]; then
    echo "FAIL: strict 200($strict_200) >= burst 200($burst_200)，burst 應放行更多"
    PASS=false
fi

if [ "$strict_429" -eq 0 ]; then
    echo "FAIL: /strict/ 沒有出現 429"
    PASS=false
fi

if [ "$burst_429" -eq 0 ]; then
    echo "FAIL: /burst/ 沒有出現 429"
    PASS=false
fi

if [ "$PASS" = true ]; then
    echo "PASS: strict 200($strict_200) < burst 200($burst_200)，兩者都有 429"
    exit 0
else
    exit 1
fi
