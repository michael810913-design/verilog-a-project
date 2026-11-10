# Spectre Hierarchical Leakage Current Analyzer

這套工具以 **sub-circuit terminal current** 找出供電電流最大的 sub-block；不修改
schematic、不插入 `iprobe`，也不往 transistor level 展開。資料流為：

**Required Python version: Python 3.6.6 or newer.** 所有 Python 程式均以
Python 3.6.6 為 compatibility baseline，不依賴外部 `dataclasses` backport。

```text
Spectre netlist -> gen_leakage_save.py -> leakage_save.scs + leakage_targets.csv
                -> Spectre transient PSF -> extract_leakage.ocn -> leakage_current.csv
                -> rank_leakage.py -> global / per-level / tree report
```

> **目前 repository 沒有 `input.scs`。** 因此實作以 `tests/fixtures/hierarchy.scs`
> 驗證需求中的 topology；正式使用前應以實際 netlist 再做一次 mapping review。
> 工具絕不建立或改寫原始 netlist。

## 檔案

* `spectre_parser.py`：解析 subckt、terminal ordering、instance connectivity、`
  +`/反斜線 continuation 與 local recursive include。
* `hierarchy.py`：建立 hierarchy，依每層 instance actual node 對 subckt formal terminal
  的**位置對應**遞迴追 supply。
* `gen_leakage_save.py`：Phase 1 CLI、共用 `generate()` API 與 `SaveGenerator`。
* `gen_leakage_save_gui__step_1.py`：Phase 1 的 Tk GUI，與 CLI 共用相同 parser/tracer/generator。
* `extract_leakage.ocn`：只依 targets manifest 從 transient PSF 讀 waveform。
* `run_extract.py`：驗證 measurement mode 並啟動 Cadence OCEAN。
* `run_extract_gui__step_2.py`：整合 Phase 3/4 的 Tk GUI，一次完成 OCEAN extraction 與 ranking。
* `rank_leakage.py`：以電流絕對值產生 global、per-level 與 tree ranking。
* `rank_leakage_gui.py`：Phase 4 的 Tk GUI，可預覽並儲存完整 ranking report。
* `tests/`：無 Cadence dependency 的 parser/tracer/ranking regression tests。

## Phase 1：產生 saves 與 manifest

### GUI 使用方式

若工作站有圖形桌面與 Python Tk，可以直接啟動：

```bash
python3 gen_leakage_save_gui__step_1.py
```

GUI 欄位與 CLI 完全對應：

| GUI 欄位 | CLI 參數 | 說明 |
|---|---|---|
| Spectre netlist | `--netlist` | 用 Browse 選擇 `input.scs` |
| Root instance | `--root` | 例如 `ANATOP_H` |
| Supply net / terminal | `--net` | 例如 `VDDI2` |
| Maximum level | `--level` | 從 root 起算，`3` 表示 Level 1～3 |
| Save output | `--output` | `leakage_save.scs` 的輸出路徑 |
| Targets output | `--targets` | `leakage_targets.csv` 的輸出路徑 |
| Debug connectivity mapping | `--debug` | 在 GUI log 顯示 mapping 診斷 |

填完後按 **Generate**。成功時 GUI 會顯示兩個實際輸出路徑；錯誤與 connectivity
warning 會顯示在下方 log，不會 silent fail。GUI 只包裝 Phase 1，後續仍需將
`leakage_save.scs` include 到 ADE、跑 Spectre，再用 `run_extract.py` 擷取 current。

GUI 會在按 **Generate** 或關閉視窗時保存最後一次輸入，下次啟動會自動還原 netlist、
root、supply、level、兩個 output path 與 debug 選項，不必每次重填。設定檔位於：

```text
~/.spectre_leakage_analyzer.json
```

設定檔只保存 GUI 欄位，不包含 PSF/current data；建立後會盡量設為 user-only (`0600`)。
若需要清除記憶值，關閉 GUI 後刪除此檔即可。站點或測試也可用
`SPECTRE_LEAKAGE_SETTINGS=/other/path/settings.json` 改用其他位置。

GUI 使用 Python 內建的 `tkinter`，沒有額外 pip dependency。若顯示
`ImportError: No module named tkinter` 或 `$DISPLAY` 相關錯誤，代表該 compute node 沒有
Tk/X11；請在有圖形桌面的 login/workstation 執行 GUI，或繼續使用下方 CLI。透過 SSH
使用 GUI 時需由現場環境正確設定 X11 forwarding。

### CLI 使用方式

`gen_leakage_save.py` 的四個必要參數是：

| 參數 | 意義 | 範例 |
|---|---|---|
| `--netlist` | 要解析的 Spectre netlist 路徑 | `input.scs` |
| `--root` | top-level 中要開始分析的 subckt instance 名稱 | `IA` |
| `--net` | root 的 parent-scope actual supply net，或 root subckt formal supply terminal | `VDD12` |
| `--level` | 從 root 算起要分析到的最大層數 | `3` |

畫面中的訊息表示程式是在**沒有帶必要參數**的情況下執行；請不要只執行
`python3 gen_leakage_save.py`，而應在包含 netlist 的目錄執行完整命令：

```bash
python3 gen_leakage_save.py \
  --netlist input.scs --root IA --net VDD12 --level 3 \
  --output leakage_save.scs
```

反斜線 `\` 必須放在 shell 每一個續行的最後一個字元；也可以全部寫在同一行：

```bash
python3 gen_leakage_save.py --netlist input.scs --root IA --net VDD12 --level 3 --output leakage_save.scs
```

若 netlist 不在目前目錄，請使用絕對或相對路徑，例如
`--netlist /project/run/input.scs`。執行成功會顯示：

```text
Wrote leakage_save.scs and leakage_targets.csv
```

可先用 `python3 gen_leakage_save.py --help` 查看相同的參數說明與完整範例。

### `cannot determine terminal connected to supply net` debug

`--net` 可以使用下列任一種名稱：

1. root instance 在 top-level 所連接的 **actual net**；或
2. root subckt definition 中的 **formal terminal**。

例如 netlist 若為：

```spectre
subckt ANA_TOP (VDDI2 VSS ...)
...
ends ANA_TOP
ANATOP_H (net0123 0 ...) ANA_TOP
```

以下兩種寫法都會選到 `ANATOP_H:VDDI2`：

```bash
python3 gen_leakage_save.py --netlist input.scs --root ANATOP_H --net net0123 --level 2
python3 gen_leakage_save.py --netlist input.scs --root ANATOP_H --net VDDI2 --level 2
```

若仍失敗，錯誤訊息現在會列出 root cell 及 `formal=actual` mapping。也可加入
`--debug`；當 `--net` 是 formal terminal 時，程式會顯示它實際對應的 top-level net：

```bash
python3 gen_leakage_save.py --netlist /full/path/input.scs \
  --root ANATOP_H --net VDDI2 --level 2 --debug
```

若 mapping 顯示 `<missing>`、多出 actual nodes，或 cell/terminal 清單不正確，通常代表
該 netlist 的 instance/subckt syntax 尚未被 parser 正確解析；請保留完整錯誤輸出及 root
instance、root subckt definition 的原始 netlist 片段進一步 debug，而不要猜 supply pin。

### 同一 supply net 連到多個 power terminals

實際 schematic 中 `VDDI2` 可能同時接到 `ANATOP_H` 的多個 formal terminals，例如
`VDDI2_USB`、`VDDI2_OSC`、`VDDI2_APR`。這不是 ambiguous error：工具會為每個由
connectivity 證實的 terminal 各產生一條 save 與 CSV row：

```spectre
save ANATOP_H:VDDI2_USB
save ANATOP_H:VDDI2_OSC
save ANATOP_H:VDDI2_APR
```

OCEAN 逐一量測這些 terminal currents；`rank_leakage.py` 再依相同 `hierarchy` 將它們
相加，因此 ranking 中 `ANATOP_H` 只出現一次，current 是該 supply domain 所有已追蹤
terminals 的總和。每個 terminal 同時成為下一層 connectivity tracing 的 local supply net。
使用 `--debug` 時會列出例如
`resolved root supply terminals: VDDI2_USB<-VDDI2, VDDI2_OSC<-VDDI2`，可直接與
schematic/netlist connectivity 核對。

`--level 3` 是 Level 1 到 3，不是只有 Level 3。預設同時寫
`leakage_targets.csv`，可用 `--targets path.csv` 改名。解析器會追蹤存在的相對路徑
`include`（同一檔案只讀一次）；找不到的 PDK/model include 會略過，因為它通常不包含
待分析的 design hierarchy。

### Connectivity 如何判定

若 parent definition 內是 `IB1 (VDD12 VSS ...) B1`，而 `B1` 的 formal terminals
是 `(VDD VSS ...)`，actual node `VDD12` 的 index 對到 formal terminal `VDD`，故輸出
`IA.IB1:VDD`。下一層以 `VDD` 作為該 block 內的 local supply 繼續做相同位置 mapping；
**程式不依 VDD、AVDD、VPWR 等名字猜測**。同一 instance 有多個 identical actual supply
node 時無法唯一決定 terminal，會 warning 而不猜。

範例 `leakage_save.scs`：

```spectre
// Auto-generated leakage current save file
// Root   : IA
// Supply : VDD12
// Level  : 3

save IA:VDD12
save IA.IB1:VDD
save IA.IB1.IC1:AVDD
save IA.IB1.IC2:VPWR
```

Vector instance 的 angle brackets 在產生的 Spectre save expression 中會使用反斜線
escape。這在 instance array 位於 hierarchy 中間時尤其必要；未 escape 的
`R2<0>.N1` 會被 Spectre 將 `>` 解讀成 operator，並回報 SFE-874/SFE-841。新版輸出為：

```spectre
save Top.I_R_calibration.R2\<0\>:VDD33
save Top.I_R_calibration.R2\<0\>.N1:5
```

`leakage_targets.csv` 仍保留原始的 `R2<0>` hierarchy，供 OCEAN fallback 與 report 顯示；
escape 僅套用於 `leakage_save.scs` 的 Spectre 語法。

範例 `leakage_targets.csv`：

```csv
level,hierarchy,cell,supply_terminal,parent_supply_net,supply_terminal_index
1,IA,A,VDD12,VDD12,1
2,IA.IB1,B1,VDD,VDD12,1
3,IA.IB1.IC1,C1,AVDD,VDD,1
3,IA.IB1.IC2,C2,VPWR,VDD,1
```

`supply_terminal_index` 是 subckt formal terminal list 中的 1-based 位置。一般 PSF 使用
`<hierarchy>:<supply_terminal>`；但部分 Spectre/PSF 版本會把 vector instance（例如
`B1<0>`、`B1<1>`）的 terminal current 存成 `Top.B1<0>:1`，而不是
`Top.B1<0>:VDDA`。Extractor 會先嘗試 formal terminal name，找不到時再使用 CSV 中經
connectivity 確認的 terminal index，不會猜 power pin。

### Mapping 驗證 checklist

1. 執行 `python3 -m unittest discover -s tests -v`，確認位置 mapping regression 通過。
2. 對每列 targets 找到 parent subckt 裡的 instance；確認 `parent_supply_net` 是 actual
   node，且同一位置的 child formal pin 等於 `supply_terminal`。
3. 比對 `leakage_save.scs` 與 CSV：每列必須恰好有一條 save；vector hierarchy 在 save
   檔中會將 `<`、`>` 寫成 `\<`、`\>`，CSV 則保留原始名稱。
4. 注意 stderr 的 `WARNING`；global supply 沒走 terminal 時，terminal current 本來就無法
   量，應調整量測邊界而非猜 pin。

## Phase 2：Spectre simulation

是的，`leakage_save.scs` 產生後，下一步就是讓 **ADE 產生的 Spectre netlist include
這個檔案**，然後重新執行 simulation。檔案只是出現在目錄中並不會自動生效；
`leakage_targets.csv` 也不需要餵給 ADE，它留到 OCEAN extraction 階段使用。

### 在 ADE 中加入 `leakage_save.scs`

1. 開啟原本 testbench 的 ADE session。
2. 在 ADE L 使用 **Setup → Model Libraries**；在 ADE Explorer/Assembler 使用對應的
   **Setup/Models → Model Libraries** 設定頁（不同 IC 版本的文字可能略有不同）。
3. 新增 `leakage_save.scs` 的**絕對路徑**，例如：

   ```text
   /user/nas3/project/pis800/ana_800/mikew800/A01/sch/gen_scs/leakage_save.scs
   ```

   此檔案沒有 model section，因此 section 欄位留空。
4. 重新 netlist/run，而不是只開啟舊的 PSF。可先只保留短時間 transient，驗證少量
   terminals，再執行正式 simulation。
5. 在 ADE 產生的 input netlist 中搜尋 `leakage_save.scs`，應看到類似：

   ```spectre
   include "/user/nas3/project/.../gen_scs/leakage_save.scs"
   ```

6. 檢查 Spectre log，確認沒有 `save` 的 unknown instance、unknown terminal 或 syntax
   warning。完成後 PSF 才會包含這次要求的 terminal currents。

> 若公司的 ADE flow 不允許把純 save 檔加入 Model Libraries，請使用該 flow 提供的
> **Spectre include/definition file** 欄位；驗證標準相同：最終 generated netlist 必須真的
> 出現 `include ".../leakage_save.scs"`，而且該 include 必須位於 simulator 可接受
> `save` statement 的位置。不要直接修改 ADE 每次 run 都會重建的 generated `input.scs`。

若不透過 ADE，也可建立獨立 wrapper netlist（不要修改原始 `input.scs`）：

```spectre
include "input.scs"
include "leakage_save.scs"
```

以原本 flow 跑 transient analysis 並寫出 `psf/`。確認 Spectre log 沒有 save statement
的 unknown instance/terminal warning。可在 OCEAN 做小量 smoke test：

```lisp
openResults("./psf")
selectResult('tran)
getData("IA.IB1:VDD" ?result "tran")
getData("IA.IB2:AVDD" ?result "tran")
```

回傳 waveform（而非 `nil`）即代表 Spectre 確實保存 terminal current。不同 Spectre/ADE
版本可能在 PSF 中使用不同 signal spelling；以上 spelling 以生成的 Spectre save syntax
為準，但仍須在现场 Cadence 版本驗證。

以題圖為例，建議先挑兩條做 smoke test，例如：

```lisp
openResults("/absolute/path/to/psf")
selectResult('tran)
getData("ANATOP_H:VDDA12_USB" ?result "tran")
getData("ANATOP_H.USB20:VDD12_USB" ?result "tran")
```

若兩者都回傳 waveform，再用 `run_extract.py` 按照完整的
`leakage_targets.csv` 擷取；若回傳 `nil`，先依下方 debug checklist 處理，不要直接進入
ranking。

## Phase 3：OCEAN extraction

`leakage_current.csv` **不是** `gen_leakage_save.py` 產生的。各檔案的產生順序是：

```text
gen_leakage_save.py  -> leakage_save.scs + leakage_targets.csv
ADE/Spectre run      -> psf/
run_extract.py       -> leakage_current.csv
rank_leakage.py      -> leakage_report.txt
```

因此在執行 ranking 前，必須先完成 ADE/Spectre simulation，找到該次 run 的 PSF
目錄，然後執行下面其中一種 OCEAN extraction。

### GUI 使用方式

在有圖形桌面與 Cadence OCEAN environment 的 terminal 啟動：

```bash
python3 run_extract_gui__step_2.py
```

GUI 欄位如下：

| GUI 欄位 | CLI 參數 | 說明 |
|---|---|---|
| PSF directory | `--psf` | ADE/Spectre 此次 simulation 的 PSF 目錄 |
| Targets CSV | `--targets` | Phase 1 產生的 `leakage_targets.csv` |
| Current CSV output | `--output` | 要產生的 `leakage_current.csv` |
| Ranking report output | ranking `--output` | 要產生的 `leakage_report.txt` |
| Time point | `--time` | 取得單一時間點的 current，例如 `10u` |
| Average window | `--start`、`--stop` | 計算時間範圍平均，建議用於 leakage ranking |
| OCEAN executable | `--ocean` | OCEAN command 或完整 executable path，預設 `ocean` |

選擇 **Time point** 或 **Average window**，填入時間後按 **Extract and Rank**。GUI 會先檢查
PSF 與 targets 是否存在，再於背景執行 OCEAN，避免視窗在 extraction 期間凍結。OCEAN
startup、license、SKILL error 與 waveform warning 會即時顯示在下方 log，不再只有
`Running OCEAN extraction...`。成功時顯示實際輸出的 `leakage_current.csv` 路徑；OCEAN
找不到、輸入不存在、OCEAN 回傳非零狀態、沒有產生 CSV，或 CSV 只有 header 而沒有任何
current data 時，都會顯示明確錯誤。Extraction 成功後會立即執行 ranking，在同一個 log
顯示完整 Global/Per-Level/Tree report，並寫出 `leakage_current.csv` 和
`leakage_report.txt`。GUI 分別與 CLI 共用 `run_extraction()` 和 `generate_report()`，所以
兩個階段的行為一致；不需要再手動啟動 `rank_leakage_gui.py`。

GUI 會先拒絕負時間以及 `stop <= start`。OCEAN 讀到每一條 waveform 後，還會比對實際
transient time range；若 average window 超出 waveform 範圍，不會讓 `clip()` 靜默縮短
window，而會停止並在 GUI log 顯示例如：

```text
ERROR: average window 5e-07 to 1e-06 s is outside waveform
IA.IB1:VDD range 0 to 8e-07 s
```

此時不會進入 ranking。請將 Start/Stop 改到 log 顯示的 waveform 範圍內，或回 ADE 延長
transient stop time 並重新模擬。

`extract_leakage.ocn` 會用 `errset` 捕捉 range/SKILL error，並以非零狀態主動結束 OCEAN。
因此錯誤後不會停在互動式 `>` prompt，也不會讓 **Extract and Rank** 永久維持 disabled；
GUI 會顯示 **Extraction failed** 並恢復按鈕。如果現場仍停在 `>`，表示使用的是舊版
`extract_leakage.ocn`，請更新該檔（它必須與 `run_extract.py` 放在相同目錄）後重試。

GUI 使用 Python 內建 `tkinter`，不需要 pip package，但仍需要 Tk 與 X11/display。無圖形
環境時請繼續使用下方 CLI；GUI 不會取代 Cadence OCEAN，也不會直接解析 binary PSF。

Extraction GUI 也會在按 **Extract and Rank** 或關閉視窗時，將 PSF、targets、兩個 output
path、measurement mode、time/start/stop 與 OCEAN executable 保存到共用設定檔：

```text
~/.spectre_leakage_analyzer.json
```

下次啟動 `python3 run_extract_gui__step_2.py` 時會自動還原，不必重新輸入。刪除該設定檔可同時
重設 generator 與 extractor GUI；也可使用 `SPECTRE_LEAKAGE_SETTINGS` 指定其他位置。

時間點：

```bash
python3 run_extract.py --psf psf --targets leakage_targets.csv --time 10u
```

建議的區間平均（避免 switching spike）：

```bash
python3 run_extract.py --psf psf --targets leakage_targets.csv --start 9u --stop 10u
```

多行輸入時，每一行尾端必須加反斜線 `\`。以下是一個完整可直接貼上的命令：

```bash
python3 run_extract.py \
  --psf /user/nas3/project/pis800/ana_800/mikew800/A01/sch/simulation/simfor_USB20_11_ANATOP_369_usb11_pd_mode_nsc/spectre/schematic/psf \
  --targets ./leakage_targets.csv \
  --start 0.5u \
  --stop 1u \
  --output ./leakage_current.csv
```

若沒有 `\`，shell 會先單獨執行 `python3 run_extract.py`，接著把 `--psf`、`--targets`
等各行當成獨立 command，因此不會產生 CSV。也可以把所有參數寫在同一行。新版 CLI 在
沒有參數時會印出完整範例；OCEAN 回傳成功但未建立 CSV，或 CSV 只有 header 時，也會以
非零狀態結束並顯示原因，不會假裝 extraction 成功。

`--psf psf` 只適用於 PSF 剛好位於目前目錄的情況。ADE 的結果通常在其他 run
directory，應改成實際的絕對路徑，例如：

```bash
python3 run_extract.py \
  --psf /project/simulation/testbench/spectre/schematic/psf \
  --targets ./leakage_targets.csv \
  --start 9u --stop 10u \
  --output ./leakage_current.csv
```

完成後先確認檔案存在且不是只有 header：

```bash
pwd
ls -l leakage_current.csv
head leakage_current.csv
```

launcher 不解析 binary PSF，只設定 OCEAN 環境並執行
`ocean -nograph -restore extract_leakage.ocn`。OCN 僅讀 CSV 指定的 signals，不掃描 PSF。
輸出 SI ampere：

```csv
level,hierarchy,cell,supply_terminal,current_A
1,IA,A,VDD12,0.00105
2,IA.IB1,B1,VDD,0.000900
3,IA.IB1.IC2,C2,VPWR,0.000820
```

### OCEAN 找不到 waveform

若 log 顯示 `Top.B1<0>:VDDA not found`，但 Results Browser 中存在
`Top.B1<0>:1`，請用新版 Step 1 重新產生 `leakage_targets.csv`，確認它包含
`supply_terminal_index` 欄位，再執行 Step 2。成功 fallback 時 log 會顯示：

```text
INFO: waveform Top.B1<0>:VDDA resolved as PSF signal Top.B1<0>:1
```

如果 formal-name 與 ordinal 兩種 key 都不存在，extraction 會以 error 結束，不會再拿只有
`Top`/`A1` 的不完整 CSV 產生看似成功的 partial ranking。

部分 Cadence/OCEAN 版本雖然在 Results Browser 顯示 `Top.B1<0>:1`，`getData()` 實際需要
escaped vector key `Top.B1\<0\>:1`。新版依序嘗試 formal name、escaped formal name、
ordinal、escaped ordinal；這四個候選都由同一筆 manifest connectivity 產生，並不掃描
PSF 或猜測 hierarchy。成功時 GUI log 會明確列出實際命中的 key。

1. 確認 `psf` 路徑、`tran` result 名稱、simulation 已成功結束。
2. 查 Spectre log，確認 `save IA.IB1:VDD` 被接受且沒有 hierarchy typo。
3. 先用上方兩個 `getData` 做少量 smoke test；用 Cadence Results Browser 確認實際名稱。
4. 確認 analysis 沒有設定只保留 selected signals 之外的另一套 output database。
5. 比對 simulator 使用的 hierarchy delimiter/case/escaped name。若现场版本的 OCEAN
   waveform key 和 Spectre save expression不同，只調整 `extract_leakage.ocn` 的
   `signal=strcat(...)`，不要重新猜 hierarchy 或掃整個 PSF。
6. 若是 global supply warning，該 block 沒有可量的 supply terminal；改到有 terminal 的
   parent boundary 量測。

## Phase 4：ranking

### GUI 使用方式

```bash
python3 rank_leakage_gui.py
```

1. 在 **Current CSV** 選擇 OCEAN 產生的 `leakage_current.csv`。
2. 在 **Report output** 選擇 `leakage_report.txt` 的儲存位置；留空時只在視窗顯示。
3. 按 **Generate Ranking**。

GUI 會在可捲動的等寬字型文字區域顯示 Global Ranking、Per-Level Ranking 與 Hierarchy
Tree Summary，並以 UTF-8 儲存 report。GUI 與 CLI 共用 `generate_report()`，因此 aggregation、
排序與 sibling maximum `<<<` 標記完全相同。若 CSV 不存在、只有 header、欄位不完整或
current 不是數字，GUI 會顯示錯誤而不產生錯誤報告。GUI 使用 Python 內建 `tkinter`，仍需
Tk 與有效的 X11/display；無圖形環境可繼續使用下方 CLI。

### CLI 使用方式

```bash
python3 rank_leakage.py leakage_current.csv
# 同時存檔
python3 rank_leakage.py leakage_current.csv --output leakage_report.txt
```

若輸入檔不存在，新版不再顯示 Python traceback，而會提示先執行 `run_extract.py`。
也可以直接指定其他目錄中的 current CSV：

```bash
python3 rank_leakage.py /path/to/leakage_current.csv \
  --output /path/to/leakage_report.txt
```

若舊環境曾出現以下錯誤：

```text
SyntaxError: Non-UTF-8 code starting with ... in file rank_leakage.py
```

通常是檔案經由舊版 editor、FTP 或不同 locale 傳送時，tree drawing 字元的 UTF-8 bytes
被改寫。新版 `rank_leakage.py` 已把 `├──`、`└──`、`│` 寫成 ASCII-safe Unicode escape，
並明確宣告 UTF-8 source encoding；輸出的 report 仍會正常顯示 tree。請重新複製完整的
`rank_leakage.py`，不要只修改錯誤行，然後依序確認：

```bash
python3 --version
python3 -m py_compile rank_leakage.py
python3 rank_leakage.py leakage_current.csv --output leakage_report.txt
```

第一行應顯示 Python 3.6.6 或更新版本。若 `python3 --version` 並非 Python 3，應改用現場
Python 3.6 executable 的完整路徑；本工具不能由 Python 2 執行。

若 terminal locale 是 ASCII（常見於舊版 compute farm），舊版可能在 `print(report)`
出現：

```text
UnicodeEncodeError: 'ascii' codec can't encode characters
```

新版會自動偵測 stdout encoding：UTF-8 terminal 維持 `├──` tree，ASCII terminal 則顯示
`+--`、`` `-- ``、`|`，不再中止。`--output leakage_report.txt` 永遠以 UTF-8 寫檔，
而且會先寫檔再顯示 terminal output，因此 console locale 不會阻止 report 產生。也可在
shell 設定 UTF-8 locale 後重跑，以保留 terminal 的 tree drawing 字元。

節錄：

```text
Leakage Current Global Ranking
Rank  Level  Hierarchy  Current
1     1      IA         1.050 mA
2     2      IA.IB1     900.0 uA

===== Level 2 =====
1     IA.IB1     900.0 uA
2     IA.IB2     150.0 uA

Hierarchy Tree Summary
IA                       1.050 mA
├── IB1                  900.0 uA  <<<
│   └── IC2              820.0 uA
└── IB2                  150.0 uA
```

排序依 `abs(current_A)`，保留显示的电流正负号，因为 Spectre terminal reference direction
可能使 supply current 为负。

## 解讀與已知限制

Parent current **包含** descendants：`IA=1050 uA`、`IA.IB1=900 uA`、
`IA.IB1.IC2=820 uA` 不代表 IA 比 IC2 更漏電。因此 global ranking 只是 overview，debug
應主要比較**同一 hierarchy level**；tree 的 `<<<` 也标记同一 parent 下最大的 sibling。

第一版限制：

* parser 是 connectivity parser，不是完整 Spectre grammar；支持本 fixture 中两种 subckt
  terminal syntax、parenthesized instance、parameters、continuation、bus/escaped token 和
  local include，但不展开 PDK library `section`、条件式 preprocessing 或 netlist macro。
* CSV 字段不应含逗号；OCN 使用简单 comma split，不支持 quoted comma。
* 只实现 transient `tran`；没有 DC/op result extraction。
* global power 没通过 subckt terminal 时无法用本方法量测，并会明确 warning。
* OCEAN/Spectre 属于商业 Cadence 环境，本 repository 只能静态检查 OCN；需在实际版本
  用少量 target 完成 Phase 2 smoke test 后再扩展全部 targets。
