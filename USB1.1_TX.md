# verilog-a-project
# USB 1.1 TX Design Note

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

## 3. Input Data

USB1.1 Input Data Spec.

- PRBS 

## 4. Design Concept 測試

The output driver contains:

1. PMOS pull-up driver
2. NMOS pull-down driver
3. Output resistance trimming circuit

The main goal is to achieve:

- Good rise/fall matching
- Proper output impedance
- Stable crossing point
