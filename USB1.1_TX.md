# verilog-a-project
# USB 1.1 TX Design Note
===
## 1. Design Target

USB 1.1 Full-Speed TX design targets:

- Data Rate: **12 Mbps**
- Output Resistance: **36 Ω**
- Output High: **3.3 V**
- Output Low: **0 V**

## 2. Rise / Fall Time

| Parameter | Target |
|---|---:|
| Rise Time | 12 ns |
| Fall Time | 12 ns |
| Output Loading | 50 pF |

## 3. USB11_input.va

USB1.1 Input Data Spec.

- PRBS7 data and data rate 12Mbps
- Output high level: 1.2 V
- Output low level: 0 V

## 4. USB11_buf.va

USB1.1 Output Buffer Spec.

- Input Threshold: 0.6 V
- Output high level: 3.3 V
- Output low level: 0 V
- Rise time: 12 ns (10%-90%)
- Fall time: 12 ns (90%-10%)



