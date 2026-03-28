# CI 性能回归检测

## 为什么需要 CI 中的性能门禁

代码 review 能发现功能 bug，但很难发现性能退化。一个看起来无害的改动——多了一次数据库查询、换了一个序列化库、加了一层中间件——可能让 P99 从 50ms 涨到 200ms。

没有自动化性能门禁，这些退化会**悄悄合入主分支**，直到某天生产告警才被发现。到那时已经叠加了几十个 commit，很难定位是哪个改动引入的退化。

**性能门禁的目标**：让性能退化像单元测试失败一样，在 PR 阶段就被拦住。

---

## 一、性能基线管理

### 什么是基线

基线（Baseline）是性能指标的参考值——"正常情况下这个接口 P99 应该是多少"。

### 基线存储方案

| 方案 | 优点 | 缺点 |
|------|------|------|
| Git 仓库中的 JSON 文件 | 与代码版本绑定、可 review | 合并冲突 |
| 数据库/对象存储 | 查询方便、可追溯历史 | 需要额外基础设施 |
| CI 系统的 Artifact | 免费、自动关联 build | 过期清理、跨 build 访问 |

推荐方案：**JSON 文件存在代码仓库中**，简单可靠，并且基线变更本身也需要 review。

```json
// performance-baseline.json
{
  "version": "2024-01-15",
  "baselines": {
    "api/users/list": {
      "p50_ms": 12,
      "p95_ms": 35,
      "p99_ms": 60,
      "qps_min": 5000,
      "error_rate_max": 0.001
    },
    "api/orders/create": {
      "p50_ms": 25,
      "p95_ms": 80,
      "p99_ms": 150,
      "qps_min": 2000,
      "error_rate_max": 0.001
    }
  }
}
```

### 基线更新策略

基线不是一成不变的。当有合理的性能变化时（如增加了必要的安全校验），需要更新基线。

```
基线更新流程：
1. PR 中性能门禁报警
2. 确认是预期的性能变化（新功能引入的开销）
3. 更新 performance-baseline.json
4. 在 PR 描述中说明为什么基线需要更新
5. 由性能负责人 approve 基线变更
```

### 基线漂移处理

长期的小幅退化（每次 +2%）累积起来可能导致严重问题。

```bash
# 定期检查基线趋势（每月/每季度）
# 比较当前基线与 3 个月前的基线
git diff HEAD~100 -- performance-baseline.json
```

设定一个**绝对上限**：无论基线怎么更新，P99 不能超过某个绝对值（如 500ms）。

---

## 二、性能预算（Performance Budget）

性能预算是预先定义的性能指标红线，超过就不允许合入。

### 定义性能预算

```yaml
# performance-budget.yml
budgets:
  # 绝对阈值：不管基线是多少，不能超过这个值
  absolute:
    p99_max_ms: 500
    error_rate_max: 0.01

  # 相对退化：相对于基线的退化幅度
  relative:
    p99_regression_max: 0.10   # P99 不能退化超过 10%
    p50_regression_max: 0.20   # P50 不能退化超过 20%
    qps_regression_max: 0.05   # QPS 不能下降超过 5%
```

### 绝对阈值 vs 相对退化

| 类型 | 示例 | 优点 | 缺点 |
|------|------|------|------|
| 绝对阈值 | P99 < 500ms | 简单明确，防止极端退化 | 不能检测小幅退化 |
| 相对退化 | P99 退化 < 10% | 能检测微小退化 | 基线不准会误报 |

**建议同时使用两种**：相对退化检测小幅退化，绝对阈值兜底防止极端情况。

---

## 三、GitHub Actions 集成

### 方案 1：使用 k6 + 阈值

```yaml
# .github/workflows/performance.yml
name: Performance Gate

on:
  pull_request:
    branches: [main]
    paths:
      - 'src/**'
      - 'go.mod'
      - 'go.sum'

jobs:
  performance-test:
    runs-on: ubuntu-latest
    services:
      # 启动依赖服务
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: testdb
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Build and start service
        run: |
          go build -o server ./cmd/server
          ./server &
          sleep 5  # 等待服务启动
          curl -f http://localhost:8080/health || exit 1

      - name: Install k6
        run: |
          sudo gpg -k
          sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
            --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D68
          echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | \
            sudo tee /etc/apt/sources.list.d/k6.list
          sudo apt-get update && sudo apt-get install -y k6

      - name: Run performance test
        run: k6 run --out json=results.json tests/performance/load-test.js

      - name: Compare with baseline
        id: compare
        run: |
          python3 scripts/compare-perf.py \
            --baseline performance-baseline.json \
            --results results.json \
            --budget performance-budget.yml \
            > comparison.md

          # 如果有退化，设置输出标记
          if grep -q "REGRESSION" comparison.md; then
            echo "regression=true" >> $GITHUB_OUTPUT
          fi

      - name: Comment PR with results
        if: always()
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const comment = fs.readFileSync('comparison.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: comment
            });

      - name: Fail if regression detected
        if: steps.compare.outputs.regression == 'true'
        run: |
          echo "Performance regression detected! Check the PR comment for details."
          exit 1
```

### 对比脚本示例

```python
#!/usr/bin/env python3
# scripts/compare-perf.py
import json
import sys
import argparse

def load_k6_results(path):
    """解析 k6 JSON 输出，提取关键指标"""
    metrics = {}
    with open(path) as f:
        for line in f:
            data = json.loads(line)
            if data.get("type") == "Point" and data["metric"] == "http_req_duration":
                # 收集延迟数据点
                pass
    # 简化示例：直接读取 summary
    return metrics

def compare(baseline, results, budget):
    """对比基线和测试结果"""
    report = []
    has_regression = False

    for endpoint, base_values in baseline["baselines"].items():
        result_values = results.get(endpoint, {})
        if not result_values:
            continue

        p99_base = base_values["p99_ms"]
        p99_actual = result_values.get("p99_ms", 0)
        regression_pct = (p99_actual - p99_base) / p99_base

        status = "PASS"
        if p99_actual > budget["absolute"]["p99_max_ms"]:
            status = "REGRESSION (absolute limit exceeded)"
            has_regression = True
        elif regression_pct > budget["relative"]["p99_regression_max"]:
            status = f"REGRESSION (+{regression_pct:.1%})"
            has_regression = True

        report.append(f"| {endpoint} | {p99_base}ms | {p99_actual}ms | {status} |")

    return report, has_regression

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--budget", required=True)
    args = parser.parse_args()

    # ... 实现完整逻辑
    print("## Performance Test Results")
    print("| Endpoint | Baseline P99 | Actual P99 | Status |")
    print("|----------|-------------|------------|--------|")
    # ... 输出对比表格
```

### 方案 2：使用 Locust + CSV 输出

```yaml
      - name: Run Locust
        run: |
          pip install locust
          locust -f tests/perf/locustfile.py \
            --host=http://localhost:8080 \
            --headless \
            -u 100 -r 10 -t 2m \
            --csv=results \
            --csv-full-history

          # results_stats.csv 包含各接口的统计数据
          # 解析 CSV 与基线对比
```

---

## 四、Jenkins Pipeline 集成

```groovy
// Jenkinsfile
pipeline {
    agent any

    stages {
        stage('Build') {
            steps {
                sh 'mvn clean package -DskipTests'
            }
        }

        stage('Deploy to Perf Env') {
            steps {
                sh './deploy-to-perf.sh'
                sh 'sleep 30'  // 等待服务启动
                sh 'curl -f http://perf-env:8080/health'
            }
        }

        stage('Performance Test') {
            steps {
                sh 'k6 run --out json=results.json tests/perf/load-test.js'
            }
            post {
                always {
                    archiveArtifacts artifacts: 'results.json'
                }
            }
        }

        stage('Performance Gate') {
            steps {
                script {
                    def result = sh(
                        script: 'python3 scripts/compare-perf.py --baseline performance-baseline.json --results results.json',
                        returnStatus: true
                    )
                    if (result != 0) {
                        currentBuild.result = 'UNSTABLE'
                        error 'Performance regression detected'
                    }
                }
            }
        }
    }
}
```

---

## 五、告警阈值设定

### 阈值设定的艺术

阈值太松 → 检测不到退化
阈值太紧 → 频繁误报，团队开始忽略

```
推荐阈值设定方法：

1. 收集 10+ 次稳定运行的结果
2. 计算各指标的标准差 (σ)
3. 设定阈值 = 基线 + 3σ（统计学上 99.7% 置信度）

示例：
  10 次运行 P99：[48, 52, 50, 55, 49, 53, 51, 47, 54, 50] ms
  均值 = 50.9 ms
  标准差 σ = 2.5 ms
  阈值 = 50.9 + 3 × 2.5 = 58.4 ms → 取整为 60 ms
```

### 处理 CI 环境的噪音

CI 环境（特别是共享 runner）性能波动大，这是性能门禁最大的挑战。

```
降低噪音的方法：
1. 使用专用的 performance runner（不与其他 job 共享）
2. 多次运行取中位数（如跑 3 次取中间值）
3. 放宽阈值但保留趋势监控
4. 对比同一 PR 的 base commit 和 head commit（而非固定基线）
```

```yaml
# 在同一 runner 上对比 base 和 head
- name: Benchmark base branch
  run: |
    git checkout ${{ github.event.pull_request.base.sha }}
    go build && ./run-bench.sh > base-results.txt

- name: Benchmark PR branch
  run: |
    git checkout ${{ github.event.pull_request.head.sha }}
    go build && ./run-bench.sh > head-results.txt

- name: Compare
  run: benchstat base-results.txt head-results.txt
```

这种"同环境对比"方式能有效消除 CI 环境差异带来的噪音。

---

## 六、实操：GitHub Actions 简单性能门禁

一个最小可用的性能门禁，适合快速落地：

```yaml
# .github/workflows/perf-gate.yml
name: Perf Gate

on:
  pull_request:
    branches: [main]

jobs:
  perf:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-go@v5
        with:
          go-version: '1.22'

      - name: Run benchmarks
        run: |
          go test -bench=. -benchmem -count=5 ./... > new.txt

      - name: Checkout base
        run: |
          git fetch origin ${{ github.base_ref }}
          git checkout FETCH_HEAD

      - name: Run base benchmarks
        run: |
          go test -bench=. -benchmem -count=5 ./... > old.txt

      - name: Compare
        run: |
          go install golang.org/x/perf/cmd/benchstat@latest
          benchstat old.txt new.txt | tee comparison.txt

          # 检查是否有显著退化（p < 0.05 且退化 > 10%）
          if grep -E '\+[1-9][0-9]\.[0-9]+%' comparison.txt; then
            echo "::warning::Significant performance regression detected"
          fi
```

---

## 总结

CI 性能门禁的落地路径：

1. **第一步**：在 CI 中跑 benchmark，输出结果但不阻断（观察期）
2. **第二步**：积累数据后设定合理阈值
3. **第三步**：开启阻断，不满足性能预算的 PR 不能合入
4. **第四步**：建立基线更新流程，避免僵化

核心原则：**宁可阈值稍松、减少误报，也不要让团队养成忽略性能告警的习惯**。一旦团队习惯性地跳过性能门禁，它就失去了全部价值。
