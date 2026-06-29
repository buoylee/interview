# 指標解碼器 metrics-decoder

> **一句話定位**:你看到 `top` / `vmstat` 一排數字**看不懂哪欄是哪欄**——來這裡查那一欄的意思 + **背後原語黑盒**,一站搞定,不用跳 5 個 track。

---

## 它解決什麼

你已經有一堆 OS / Linux track,但內容**散在各處**:指標表在 `cli-toolbox/02` 和 `perf-roadmap/02-linux-tools`,原語黑盒在 `linux/` primer,動手排查在 `linux-handson/`。看一個 `si` 要翻三個地方,而且常常翻完還是似懂非懂。

這個 track 把兩半合一:**「這欄是什麼」(解碼) + 「這欄為什麼變」(原語)** 寫進同一份。

```
        cli-toolbox/02 · perf-roadmap/02   ← 指標表(讀錶)
                  +                          ┐
        linux/ primer                      ← 原語黑盒(懂錶) ├─→ metrics-decoder(合一)
                  +                          ┘
        linux-handson                      ← 動手排查(用錶)
```

---

## 怎麼用

- **撞到哪欄,查哪欄。** 不用從頭讀。
- 每章兩層:
  - **① 逐欄解碼表**——快速反查,看一眼就走。
  - **② 原語黑盒**——只在「似懂非懂、想知道底層發生什麼」時才往下挖。底層全寫進正文,不外鏈。
- 真機輸出都是**先跑好貼進去的**(拋棄式 Docker 容器),你讀就好,不用自己跑。本機/Docker 復現不了的(如 `steal`)會明說「裸機 / 雲 VM 才有」。

---

## 目錄

| 章 | 主題 | 狀態 |
|----|------|------|
| [01 CPU 那行](./01-cpu.md) | `top` 的 `us sy ni id wa hi si st`(+`guest`)逐欄 + 中斷/切換/虛擬化原語 | ✅ |
| [02 記憶體](./02-memory.md) | `free`/`vmstat` 的 `si so`、`VIRT`/`RES`、page cache/available、swap、OOM | ✅ |
| [03 磁碟 IO](./03-disk-io.md) | `iostat -xz` 的 `await`/`aqu-sz`/`%util`(+ writeback/fsync/D 狀態) | ✅ |
| [04 網路](./04-network.md) | `ss` 的連線狀態、`Recv-Q`/`Send-Q` 雙重身分、`retrans`、TIME_WAIT | ✅ |

> 四類資源(CPU/記憶體/磁碟/網路)= 「機器慢」決策樹的四個分支,全做齊。每章獨立可查。

---

## 回鏈

- 原語底座更深 → [`../linux/`](../linux/)
- 動手排查七段式 → [`../linux-handson/07-troubleshooting-playbook`](../linux-handson/07-troubleshooting-playbook/)
- 快速反查心法 → [`../cli-toolbox/02-performance-and-resource-triage.md`](../cli-toolbox/02-performance-and-resource-triage.md)
- 更深的工具參數 → [`../performance-tuning-roadmap/02-linux-tools/01-cpu-tools.md`](../performance-tuning-roadmap/02-linux-tools/01-cpu-tools.md)
