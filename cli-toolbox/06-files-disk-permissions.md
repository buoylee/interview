# 06 · 檔案・磁碟・權限

> 找檔案、磁碟滿了誰佔的、權限報 Permission denied、掛載 umount 不掉——日常雜事最多的一章,收成三塊。

---

## 收口地圖(三塊 + 兩個原語)

| 塊 | 工具 | 一句話 |
|---|---|---|
| **找檔案** | `find` / `stat` / `file` | 按名字/大小/時間找,並對找到的批量處理 |
| **看空間** | `df` / `du` / `ncdu` | 哪個分區滿了、空間被誰吃了 |
| **權限與掛載** | `chmod` / `chown` / `mount` / `lsblk` | 誰能讀寫、磁碟掛哪 |

兩個要記的原語:

1. **磁碟「滿」有兩種**:**空間**滿(`df -h`)或 **inode** 滿(`df -i`)。後者:空間明明還很多,卻寫不進——因為小檔太多把 inode 用光了。
2. **權限看「三組 `rwx` + 特殊位」**:`rwxr-xr-x` = 擁有者/群組/其他人各一組;數字 `r=4 w=2 x=1` 相加。

---

## 1. `find` —— 找檔案 + 批量處理

| 命令 | 作用 |
|---|---|
| 🔧 `find . -name '*.log'` | 按檔名找(`-iname` 忽略大小寫) |
| `find . -type f -size +100M` | 找大於 100M 的**檔案** |
| `find . -mtime -1` | **24 小時內**改過的(`-mmin -10` = 10 分鐘內) |
| `find . -name '*.tmp' -delete` | 找到並刪除 |
| `find . -type f -exec cmd {} +` | 對每個結果跑命令(`+` 批量、`\;` 逐個) |
| `find . -name '*.c' -print0 \| xargs -0 grep foo` | 安全傳給 xargs(處理含空格檔名) |
| `find /path -maxdepth 1` | 不遞迴進子目錄 |

配套:`stat file`(看 inode / 權限 / 三種時間戳)、`file x`(看檔案**真實類型**,不靠副檔名)。

---

## 2. 磁碟空間:`df` / `du`

| 命令 | 作用 | 底層一兩句 |
|---|---|---|
| `df -h` | 各分區剩多少空間 | **「磁碟滿」第一條** |
| `df -i` | 各分區 **inode** 用量 | 空間夠卻寫不進 → 多半 inode 耗盡(小檔海) |
| `df -hT` | 同上 + 檔案系統**類型** | 看是 ext4/xfs/overlay |
| 🔧 `du -sh *` | 當前目錄下**各項**大小 | `-s`=匯總 `-h`=人類可讀 |
| `du -sh * \| sort -rh \| head` | **揪空間大戶 top-N** | `sort -rh` = 按人類可讀大小逆序 |
| `ncdu` | 互動式磁碟分析 | 上下鍵鑽進去看,最直觀(需安裝) |

> **回扣 04 的經典坑**:`df` 說滿了,`du` 卻加不出那麼多 → **檔案被刪了但有進程還開著**(空間沒釋放)。`lsof | grep deleted` 抓元兇,重啟那進程才會真正釋放。

---

## 3. 權限

讀懂 `ls -l` 的權限位:

```
-rwxr-xr-x   = 檔案類型(-檔案 d目錄 l連結) + 擁有者 rwx + 群組 r-x + 其他人 r-x
   數字算法:r=4 w=2 x=1  →  rwx=7  r-x=5  rw-=6
```

| 命令 | 作用 |
|---|---|
| 🔧 `chmod 644 file` | 擁有者讀寫、其他人唯讀(一般檔案) |
| `chmod 755 file` | 加可執行(腳本、目錄要 `x` 才能進) |
| `chmod +x script.sh` | 只加執行位 |
| `chmod -R 755 dir/` | 遞迴 |
| `chown user:group file` | 改擁有者:群組(`-R` 遞迴) |
| `umask` | 看新建檔的預設權限遮罩 |

**特殊位(面試常問)**:

- **setuid(4xxx)**:執行時用**檔案擁有者**的身份跑。`passwd` 為什麼普通用戶能改 `/etc/shadow`?因為它是 setuid root。
- **setgid(2xxx)**:用群組身份;用在目錄上時,新建檔自動繼承該群組。
- **sticky(1xxx)**:用在目錄(如 `/tmp`)上,**只有擁有者能刪自己的檔**,防別人刪你的。

> 進階:細到「單一使用者額外授權」用 ACL —— `getfacl` / `setfacl`(標準 `rwx` 不夠用時)。

---

## 4. 掛載與塊設備

| 命令 | 作用 | 底層一兩句 |
|---|---|---|
| `lsblk` | 塊設備樹(磁碟/分區/掛載點) | 看「有哪些盤、掛在哪」 |
| `MAJ:MIN` | 主/次設備號 | 內核識別設備用,日常排查通常只作識別 |
| `RM` | removable | `1` 常見於可移除設備 |
| `RO` | read-only | `1` 表示唯讀設備 |
| `mount /dev/sdb1 /mnt` | 掛載 | 臨時掛;開機自動掛要寫 `/etc/fstab` |
| `umount /mnt` | 卸載 | 報 `target is busy` → 有進程在用 |
| `fuser -m /mnt` | **誰在用這個掛載點** | `umount` 不掉時揪元兇(或 `lsof +D /mnt`) |
| `cat /etc/fstab` | 開機自動掛載表 | 改錯會開不了機,小心 |

---

## 5. 軟硬連結 + 打包

**軟連結 vs 硬連結(從 inode 角度,面試點)**:

| | 硬連結 `ln a b` | 軟連結 `ln -s a b` |
|---|---|---|
| 本質 | 多一個名字指向**同一個 inode** | 一個**指向路徑**的捷徑檔 |
| 刪原檔 | **不受影響**(inode 還被引用) | **斷掉**(指向的路徑沒了) |
| 跨檔案系統 | 不行 | 可以 |
| 連目錄 | 不行 | 可以 |

打包壓縮:

| 命令 | 作用 |
|---|---|
| `tar -czf x.tar.gz dir/` | 打包 + gzip 壓縮(`c`建立 `z`壓縮 `f`檔名) |
| `tar -xzf x.tar.gz` | 解開 |
| `tar -xzf x.tar.gz -C /dest` | 解到指定目錄 |
| `tar -tzf x.tar.gz` | 只**列出內容**不解開 |

> 記憶:`czf`=create、`xzf`=extract、`tzf`=list。`z`=gzip,換 `j`=bzip2、`J`=xz。

---

## 🔧 主力命令深講 + 速驗

> 先進 README 的沙盒。以下用例自帶造檔,跑完即丟。

### find — 找檔案 + 批量處理

| 寫法 | 作用 |
|---|---|
| `find . -name '*.log'` / `-iname` | 按檔名(忽略大小寫) |
| `find . -type f` / `-type d` | 只找檔案 / 目錄 |
| `find . -size +100M` / `-size -1k` | 按大小 |
| `find . -mtime -1` / `-mmin -10` | 1 天 / 10 分鐘內改過 |
| `find . -maxdepth 1` | 不遞迴進子目錄 |
| `find . -empty` | 空檔案 / 空目錄 |
| `find . -name '*.tmp' -delete` | 找到並刪 |
| `find . -type f -exec cmd {} +` | 對結果跑命令(`+` 批量 / `\;` 逐個) |

**⚡ 驗證**:
```bash
mkdir -p /tmp/ft/sub && touch /tmp/ft/a.log /tmp/ft/b.txt /tmp/ft/sub/c.log
find /tmp/ft -name '*.log'              # 預期:/tmp/ft/a.log 和 /tmp/ft/sub/c.log
find /tmp/ft -maxdepth 1 -name '*.log'  # 預期:只 /tmp/ft/a.log
find /tmp/ft -type d                    # 預期:/tmp/ft 與 /tmp/ft/sub
find /tmp/ft -name '*.txt' -delete; find /tmp/ft -name '*.txt'   # 預期:第二條無輸出(已刪)
```

### du / df — 看空間

| 寫法 | 作用 |
|---|---|
| `du -sh dir` | 目錄總大小 |
| `du -ah dir \| sort -rh \| head` | 各檔大小降序 top-N |
| `du -h --max-depth=1 dir` | 只展開一層 |
| `df -h` | 各分區空間 |
| `df -i` | 各分區 inode |
| `df -hT` | 加檔案系統類型 |

`df -h` 看空間,`df -i` 看 inode,兩個都可能滿:

```text
Filesystem      Size  Used Avail Use% Mounted on
/dev/vda1        40G   35G  5.0G  88% /

Filesystem      Inodes IUsed  IFree IUse% Mounted on
/dev/vda1      2621440 20000 2601440    1% /
```

| 命令 | 看什麼 | 怎麼判讀 |
|---|---|---|
| `df -h` | block 空間 | `Use%` 高 = 容量快滿 |
| `df -i` | inode 數量 | 小檔太多會 inode 滿,即使 GB 還夠也寫不進 |
| `Avail` / `IFree` | 剩餘空間/剩餘 inode | 這兩欄才是還能不能寫 |
| `Mounted on` | 掛載點 | 確認滿的是哪個分區 |

> 小坑:報 `No space left on device` 不一定是 GB 滿,也可能是 inode 滿。

**⚡ 驗證**:
```bash
du -sh /tmp/ft                     # 預期:/tmp/ft 總大小
du -ah /tmp/ft | sort -rh | head   # 預期:各檔/目錄大小降序
df -h /                            # 預期:根分區 Size/Used/Avail/Use%
df -i /                            # 預期:根分區 inode 使用量
```

### chmod / chown — 權限

| 寫法 | 作用 |
|---|---|
| `chmod 644 / 755 file` | 數字法設權限 |
| `chmod +x` / `-x file` | 加 / 去執行位 |
| `chmod u+x,g-w,o=r file` | 符號法(精細調某一組) |
| `chmod -R 755 dir` | 遞迴 |
| `chown user:group file` (`-R`) | 改擁有者(需 root) |

`ls -l` 第一欄拆開看:

```text
-rwxr-xr-x 1 root root 123 Jun 26 10:00 app.sh
```

| 片段 | 意思 | 怎麼判讀 |
|---|---|---|
| `-` | 檔案類型 | `-` 普通檔,`d` 目錄,`l` 軟連結 |
| `rwx` | owner 權限 | 檔案擁有者能讀/寫/執行 |
| `r-x` | group 權限 | 同組使用者能讀/執行 |
| `r-x` | others 權限 | 其他人能讀/執行 |
| `1` | hard link 數 | 目錄或硬連結場景會變大 |
| `root root` | owner / group | 權限排查要配這兩欄 |
| `123` | 大小 bytes | `ls -lh` 會變成人類可讀 |

> 小坑:目錄的 `x` 代表能進入/穿越目錄;只有 `r` 沒 `x` 很多操作仍會失敗。

**⚡ 驗證**:
```bash
touch /tmp/perm.sh
ls -l /tmp/perm.sh           # 預期:-rw-r--r--(644,新建預設)
chmod 755 /tmp/perm.sh
ls -l /tmp/perm.sh           # 預期:-rwxr-xr-x
chmod -x /tmp/perm.sh
ls -l /tmp/perm.sh           # 預期:x 位被拿掉 → -rw-r--r--
# chown 需 root + 已存在的用戶,例:chown nobody:nogroup /tmp/perm.sh
```

### ⚡ 配角速驗(`stat` / `ln` / `tar` / `file` / `lsblk`)

`stat` 的三種時間不要混:

| 欄位 | 意思 | 常見用途 |
|---|---|---|
| `Access` | 上次讀取時間 | 誰最近讀過;很多系統會弱化更新 |
| `Modify` | 檔案內容上次修改 | 排查內容何時變了 |
| `Change` | metadata 上次改變 | chmod/chown/rename/link 也會更新 |

`lsblk` 看塊設備樹:

| 欄位 | 意思 | 怎麼判讀 |
|---|---|---|
| `NAME` | 設備名 | 樹狀縮排表示磁碟、分區、LVM 關係 |
| `MAJ:MIN` | 主/次設備號 | 內核識別設備用,日常排查通常只作識別 |
| `SIZE` | 容量 | 對照 `df` 看分區是否掛上 |
| `TYPE` | 類型 | `disk` 磁碟,`part` 分區,`lvm` 邏輯卷 |
| `RM` | removable | `1` 常見於可移除設備 |
| `RO` | read-only | `1` 表示唯讀設備 |
| `MOUNTPOINTS` | 掛載點 | 空白代表目前沒掛載 |

> 小坑:`Modify` 是內容變,`Change` 是 inode metadata 變;不是建立時間。`lsblk` 不同版本可能顯示 `MOUNTPOINT` 或 `MOUNTPOINTS`。

```bash
stat /tmp/perm.sh            # 預期:Inode、Access/Modify/Change 三種時間戳
echo hi > /tmp/orig
ln -s /tmp/orig /tmp/soft    # 軟連結
ls -l /tmp/soft             # 預期:/tmp/soft -> /tmp/orig
ln /tmp/orig /tmp/hard       # 硬連結
ls -li /tmp/orig /tmp/hard  # 預期:兩者「inode 號相同」(最左欄)
tar -czf /tmp/a.tgz -C /tmp orig
tar -tzf /tmp/a.tgz         # 預期:列出 orig
file /tmp/a.tgz             # 預期:gzip compressed data
lsblk 2>/dev/null | head    # 預期:塊設備樹(容器內可能只見 overlay/host 盤)
```

---

## 深挖

- 檔案系統、inode、權限模型的完整原理 → **`linux-handson/02-filesystem-and-permissions`**
- IO、檔案讀寫、fd → **`linux-handson/05-io-and-files`**
- 「磁碟滿了 `du` 卻對不上」的 deleted-but-open → **`04 觀測內幕`**
