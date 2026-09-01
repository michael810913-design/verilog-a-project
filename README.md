# verilog-a-project
# USB 1.1 TX Design Note

## 1. Design Target

USB 1.1 Full-Speed TX design targets:

- Data Rate: **12 Mbps**
- Output Resistance: **31 ~ 41 Ω**
- Typical Target: **36 Ω**

## 2. Rise / Fall Time

| Parameter | Target |
|---|---:|
| Rise Time | 12 ns |
| Fall Time | 12 ns |
| Loading | 50 pF |

## 3. Design Concept

The output driver contains:

1. PMOS pull-up driver
2. NMOS pull-down driver
3. Output resistance trimming circuit

The main goal is to achieve:

- Good rise/fall matching
- Proper output impedance
- Stable crossing point

## 4. Verilog-A Example

```verilog
analog begin
    if (V(en) > 0.6)
        V(out) <+ transition(vtarget, 0, tr, tf);
end
