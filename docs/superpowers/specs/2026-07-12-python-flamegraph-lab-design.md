# PerfShop Python 火焰圖 Lab 設計

- 日期：2026-07-12
- 狀態：設計已批准，待 implementation plan
- 範圍：`performance-tuning-roadmap/labs/perfshop-p0`
- 工具：`py-spy==0.4.2`

## 1. 背景

`02-linux-tools/05-tracing-profiling.md` 已解釋通用火焰圖流程，Python profiling 章節亦示範 `py-spy`。PerfShop P0 已有可執行 CPU hotspot `burn_cpu_if_enabled`，README 也要求產出 CPU profile、top 3 熱點、QPS/P99 對比；但目前 App image 未包含 profiler，Compose 未提供 attach 權限，也沒有把採樣、判讀、驗證串成可重現 lab。

本設計補齊 Python 路線。實驗用相同負載比較 CPU chaos 開啟與 reset 後的兩張火焰圖，驗證 profiling 能否找到已知 hotspot。這是故障 on/off 診斷驗證，不宣稱為真實程式優化成果。

## 2. 目標

- 在 PerfShop App container 內以 `py-spy` attach PID 1。
- CPU chaos 開啟、reset 後各產出一張 SVG 火焰圖。
- 兩輪使用相同壓測參數與採樣時間。
- 學習者能指出 top 3 熱點、解釋調用路徑，並比較 QPS/P99。
- profiling 權限 opt-in；一般 `docker compose up` 不取得 `SYS_PTRACE`。
- 產物留在本機，不提交 repo。

## 3. 非目標

- 不修改 `server.py` 或 CPU hotspot 行為。
- 不建立 Java、Go profiling lab。
- 不引入 Brendan Gregg `FlameGraph` Perl scripts；`py-spy` 直接輸出 SVG。
- 不加入 profiler sidecar、多階段 profiling image 或 helper script。
- 不使用 `privileged`，也不修改主 `docker-compose.yml` 權限。
- 不提交 sample SVG。
- 不把 chaos reset 描述為程式碼優化。

## 4. 已批准決策

1. `py-spy` 固定安裝於 App image；不在實驗執行時下載。
2. 使用獨立 `docker-compose.profiling.yml` 加入 `SYS_PTRACE` 與 artifact bind mount。
3. Lab 深度為 hotspot on/off 雙份 SVG、top 3、QPS/P99 對比。
4. 新增獨立 `PYTHON-FLAMEGRAPH-LAB.md`，由 PerfShop README 與 Python profiling 章節連入。
5. SVG 保留於本機並 git ignore。
6. 採用「App image 內建 profiler + opt-in 權限」方案；不採執行時安裝或專用 image target。

版本固定為 `py-spy==0.4.2`。此版本是 2026-04-24 發布的穩定版；官方文件確認 `record` 可輸出 SVG，Docker attach 需 `SYS_PTRACE`：

- <https://pypi.org/project/py-spy/>
- <https://github.com/benfred/py-spy#how-do-i-run-py-spy-in-docker>

## 5. 檔案變更

### `labs/perfshop-p0/app/requirements.txt`

加入：

```text
py-spy==0.4.2
```

App 仍使用原本 `CMD ["python", "src/server.py"]`。Profiler 存在於 image，但沒有 profiling override 時缺少 attach capability。

### `labs/perfshop-p0/docker-compose.profiling.yml`

只擴充 `app` service：

```yaml
services:
  app:
    cap_add:
      - SYS_PTRACE
    volumes:
      - ./artifacts/profiling:/artifacts/profiling
```

不加入 `privileged` 或 `seccomp=unconfined`。使用 override 後必須 recreate App，確保 capability 生效。

### `labs/perfshop-p0/artifacts/profiling/.gitignore`

忽略目錄內所有生成物，只保留 `.gitignore`：

```gitignore
*
!.gitignore
```

預期產物：

- `cpu-hotspot.svg`
- `cpu-reset.svg`

### `labs/perfshop-p0/PYTHON-FLAMEGRAPH-LAB.md`

新文件包含：

1. 目的、前置條件與安全說明。
2. 使用主 Compose + profiling override build/start。
3. 健康檢查與 `py-spy --version` 驗證。
4. Terminal A 壓測、Terminal B 採樣的明確分工。
5. CPU chaos on、reset 兩輪完整命令。
6. 火焰圖閱讀方式、預期 hotspot 與 top 3 記錄欄位。
7. QPS/P99 對比表。
8. 常見錯誤與 cleanup。

### 導覽連結

- `labs/perfshop-p0/README.md` 的 CPU hotspot 場景加入 runnable lab 連結。
- `06a-python-profiling/01-python-profiling-tools.md` 的 `py-spy` 實操段加入 PerfShop lab 連結。

不改 Java／Go 文件、`LEARNING-GUIDE.md`、主 Compose 或 App source。

## 6. 實驗流程

### 6.1 啟動

從 `labs/perfshop-p0` 執行：

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.profiling.yml \
  up --build -d
```

驗證：

```bash
curl http://127.0.0.1:8080/health
docker exec perfshop-p0-app py-spy --version
```

版本輸出必須為 `py-spy 0.4.2`。

### 6.2 Hotspot 輪

先啟用足夠長的 chaos window：

```bash
curl -X POST 'http://127.0.0.1:8080/chaos/cpu?duration=90'
```

Terminal A 執行固定負載：

```bash
wrk --latency -t2 -c20 -d30s http://127.0.0.1:8080/api/products/1
```

Terminal B 在負載開始後立即採樣：

```bash
docker exec perfshop-p0-app py-spy record \
  --pid 1 \
  --duration 30 \
  --rate 100 \
  --format flamegraph \
  -o /artifacts/profiling/cpu-hotspot.svg
```

保存該輪 QPS 與 P99。`cpu-hotspot.svg` 應清楚顯示 `burn_cpu_if_enabled` 及其 busy loop 路徑。

### 6.3 Reset 輪

```bash
curl -X POST http://127.0.0.1:8080/chaos/reset
```

以完全相同 `wrk` 參數重跑 Terminal A；Terminal B 將輸出改為：

```text
/artifacts/profiling/cpu-reset.svg
```

保存第二輪 QPS/P99。`burn_cpu_if_enabled` 仍可能因快速 guard return 出現在樣本中，但寬度應明顯縮窄；文件不得把「完全消失」列為硬性條件。

### 6.4 判讀與記錄

文件要求填寫：

| 輪次 | QPS | P99 | top 1 | top 2 | top 3 |
|---|---:|---:|---|---|---|
| CPU hotspot |  |  |  |  |  |
| CPU reset |  |  |  |  |  |

判讀至少回答：

- 哪個 stack path 直接支持 CPU hotspot 假設？
- hotspot reset 後，frame 寬度、QPS、P99 如何變化？
- 這份證據能證明什麼，不能證明什麼？

## 7. 錯誤處理

- `Permission denied`：確認兩份 Compose file 都有使用，並 recreate App；不要建議 `privileged`。
- `Failed to get process executable name` 或 PID 錯誤：確認 target 是 container 內 PID 1，App health check 正常。
- SVG 沒有預期 hotspot：確認 chaos 回傳成功、90 秒尚未過期、壓測與採樣確實重疊。
- 圖被 idle frame 主導：確認 Terminal A 已開始產生持續負載。
- 輸出檔不存在：確認使用 profiling override、host artifact 目錄存在、container 路徑為 `/artifacts/profiling`。
- 兩輪數字不可比：必須保持 threads、connections、duration、endpoint、採樣 rate 與測試環境一致。

## 8. 安全邊界

`py-spy` 透過讀取其他 process memory 工作；`SYS_PTRACE` 會擴大 container 的 process inspection 能力。因此 capability 只存在於 opt-in profiling override，文件明確標記僅供本機 lab，完成後使用相同 Compose file 組合停止服務。主 Compose 維持原權限。

## 9. 驗證策略

實作完成後依序驗證：

1. `docker compose -f docker-compose.yml -f docker-compose.profiling.yml config` 成功。
2. Build App image 成功，`py-spy --version` 回報 `0.4.2`。
3. `/health`、商品 API、`/metrics` 原 smoke checks 通過。
4. 啟用 CPU chaos 並在持續負載下做短採樣，生成非空 SVG。
5. SVG 包含 `burn_cpu_if_enabled` symbol。
6. Reset 後以相同負載生成第二張非空 SVG。
7. 人工確認 hotspot frame 在 reset 圖中明顯縮窄；數值差異不設固定門檻，避免硬體差異造成 flaky 驗收。
8. `git status` 不出現生成 SVG。
9. 文件內命令逐條可複製執行，所有相對路徑以 `labs/perfshop-p0` 為 working directory。

## 10. 完成標準

- 一條 opt-in Compose 啟動路徑可跑通 profiling。
- 兩張本機 SVG 皆成功生成。
- hotspot 圖能定位 `burn_cpu_if_enabled`。
- 學習者能完成 top 3、QPS/P99 與證據邊界說明。
- 主 Compose、App 行為與現有 smoke checks 不退化。
- repo 不追蹤生成 artifact，也不授予常態 profiling 權限。
