# PLL

## 1. Basic Architecture

A typical PLL contains:
- Phase/Frequency Detector (PFD)
- Charge Pump (CP)
- Loop Filter (LF)
- Voltage-Controlled Oscillator (VCO)
- Frequency Divider

```text
REF_CLK
   |
   v
 +-----+      +-----+      +-------------+      +-----+
 | PFD | ---> | CP  | ---> | Loop Filter | ---> | VCO | ---> CLK_OUT
 +-----+      +-----+      +-------------+      +-----+
   ^                                               |
   |                                               |
   |                                               v
   +------------------- Divider <------------------+
```

The feedback clock is:

```text
FB_CLK = CLK_OUT / N
```

The PLL tries to make:

```text
FB_CLK ≈ REF_CLK
```

Therefore:

```text
Fout = N × Fref
```

---

## 3. PLL Locking Process

### 3.1 Initial Condition

When the PLL starts, the VCO frequency may be very different from the target frequency.

For example:

```text
Reference Clock = 50 MHz
Divider Ratio   = 20
Target Output   = 1 GHz
```

But the initial VCO frequency may be:

```text
Initial VCO = 700 MHz
```

Then:

```text
Feedback Clock = 700 MHz / 20
               = 35 MHz
```

Since:

```text
REF_CLK = 50 MHz
FB_CLK  = 35 MHz
```

the PLL detects that the feedback clock is slower than the reference clock.

---

## 4. PFD Operation

The Phase/Frequency Detector compares:

```text
REF_CLK
```

and

```text
FB_CLK
```

The PFD generates two signals:

```text
UP
DN
```

### Case 1: Feedback clock is slower

```text
REF_CLK > FB_CLK
```

The PFD generates more UP pulses.

```text
UP = active
DN = inactive
```

The charge pump increases the loop-filter voltage.

```text
VCTRL ↑
```

Therefore:

```text
VCO frequency ↑
```

---

### Case 2: Feedback clock is faster

```text
REF_CLK < FB_CLK
```

The PFD generates more DN pulses.

```text
UP = inactive
DN = active
```

The charge pump decreases the control voltage.

```text
VCTRL ↓
```

Therefore:

```text
VCO frequency ↓
```

---

## 5. Frequency Acquisition

At startup, the PLL first reduces the frequency difference between:

```text
REF_CLK
```

and

```text
FB_CLK
```

This process is called:

```text
Frequency Acquisition
```

A PFD can detect both:

- Phase difference
- Frequency difference

Therefore, unlike a simple XOR phase detector, a PFD can help the PLL acquire lock even when the initial frequency error is large.

---

## 6. Phase Acquisition

After the frequencies become close:

```text
Fref ≈ Ffb
```

the loop mainly adjusts the phase difference.

The PLL keeps correcting the VCO until:

```text
Phase Error ≈ 0
```

This process is called:

```text
Phase Acquisition
```

---

## 7. Locked State

When the PLL is locked:

```text
Fref = Ffb
```

and ideally:

```text
Phase Error ≈ 0
```

Since:

```text
Ffb = Fout / N
```

we obtain:

```text
Fout = N × Fref
```

Example:

```text
Fref = 50 MHz
N    = 20
```

Then:

```text
Fout = 50 MHz × 20
     = 1 GHz
```

---

## 8. Charge Pump

The charge pump converts PFD UP/DN pulses into current.

Typical behavior:

```text
UP = 1
→ Source current into loop filter
→ VCTRL increases
```

```text
DN = 1
→ Sink current from loop filter
→ VCTRL decreases
```

Charge pump current is often written as:

```text
Icp
```

A larger `Icp` generally increases the loop gain.

---

## 9. Loop Filter

The loop filter converts charge-pump current into the VCO control voltage.

A simple loop filter may contain:

```text
R
C1
C2
```

Example:

```text
       CP
       |
       +------ R ------+
       |               |
      C1              C2
       |               |
      GND             GND
```

The loop filter determines important PLL characteristics such as:

- Loop bandwidth
- Phase margin
- Lock time
- Noise filtering
- Reference spur
- Stability

---

## 10. VCO

The VCO output frequency depends on the control voltage.

A simplified equation is:

```text
Fvco = F0 + Kvco × Vctrl
```

where:

- `F0` = free-running frequency
- `Kvco` = VCO gain
- `Vctrl` = control voltage

The unit of `Kvco` may be:

```text
Hz/V
```

or

```text
rad/s/V
```

Example:

```text
Kvco = 500 MHz/V
```

If:

```text
ΔVctrl = 100 mV
```

then:

```text
ΔFvco = 500 MHz/V × 0.1 V
       = 50 MHz
```

---

## 11. Divider

The divider reduces the VCO frequency before feeding it back to the PFD.

```text
Ffb = Fout / N
```

For example:

```text
Fout = 1 GHz
N    = 20
```

Then:

```text
Ffb = 1 GHz / 20
    = 50 MHz
```

The PLL compares this feedback clock with the reference clock.

---

## 12. Integer-N PLL

For an Integer-N PLL:

```text
Fout = N × Fref
```

where `N` is an integer.

Example:

```text
Fref = 25 MHz
N    = 40
```

Then:

```text
Fout = 1 GHz
```

---

## 13. Important PLL Parameters

| Parameter | Description |
|---|---|
| Reference Frequency | Input reference clock frequency |
| Output Frequency | PLL output frequency |
| Divider Ratio | Feedback divider value |
| Lock Time | Time required for the PLL to reach lock |
| Loop Bandwidth | Frequency range where the loop can track disturbances |
| Phase Margin | Stability indicator |
| Jitter | Timing variation in time domain |
| Phase Noise | Phase fluctuation in frequency domain |
| Kvco | VCO gain |
| Icp | Charge-pump current |
| Reference Spur | Periodic sidebands related to reference frequency |
| Lock Range | Frequency range where the PLL can remain locked |
| Capture Range | Frequency range where the PLL can acquire lock |

---

## 14. Loop Bandwidth

Loop bandwidth is one of the most important PLL design parameters.

### Wider Loop Bandwidth

Advantages:

- Faster lock time
- Faster tracking
- Better suppression of low-frequency VCO noise

Disadvantages:

- More reference noise passes to the output
- More reference spur may appear
- Stability may become more difficult

---

### Narrower Loop Bandwidth

Advantages:

- Better suppression of high-frequency reference noise
- Better reference spur filtering

Disadvantages:

- Slower lock time
- More VCO noise may dominate
- Slower tracking

---

## 15. PLL Noise Transfer

Different PLL noise sources have different transfer characteristics.

### Reference Noise

Reference noise generally has a:

```text
Low-Pass characteristic
```

through the PLL.

Therefore, noise below the loop bandwidth tends to appear at the PLL output.

---

### VCO Noise

VCO noise generally has a:

```text
High-Pass characteristic
```

through the PLL.

Inside the loop bandwidth:

```text
VCO noise is suppressed
```

Outside the loop bandwidth:

```text
VCO noise dominates
```

---

## 16. Jitter

Jitter is timing variation in the time domain.

Common jitter types include:

- Period jitter
- Cycle-to-cycle jitter
- Long-term jitter
- Random jitter
- Deterministic jitter

Example:

Ideal clock:

```text
|----10 ns----|----10 ns----|----10 ns----|
```

Clock with jitter:

```text
|---9.8 ns---|----10.2 ns----|---9.9 ns---|
```

---

## 17. Phase Noise

Phase noise describes clock phase fluctuation in the frequency domain.

It is usually expressed as:

```text
dBc/Hz
```

at a certain offset frequency.

Example:

```text
-100 dBc/Hz @ 1 MHz offset
```

Lower phase noise generally means better clock quality.

---

## 18. Lock Time

Lock time is the time required for the PLL to reach the desired frequency and phase.

Lock time depends on:

- Loop bandwidth
- Phase margin
- Charge-pump current
- Kvco
- Divider ratio
- Initial frequency error
- Loop-filter values

Generally:

```text
Larger Loop Bandwidth
→ Faster Lock Time
```

but there is a trade-off with noise and stability.

---

## 19. PLL Stability

PLL stability is commonly evaluated using:

```text
Phase Margin
```

A commonly used target is approximately:

```text
45° ~ 60°
```

Higher phase margin generally provides better damping.

Too little phase margin may cause:

- Ringing
- Long settling time
- Instability
- Excessive jitter

---

## 20. PLL and CDR

A PLL-based CDR uses a similar feedback concept.

The main difference is that a CDR does not usually have a clean periodic reference clock.

Instead, the phase detector extracts timing information from the incoming data.

Simplified architecture:

```text
Incoming Data
     |
     v
Phase Detector
     |
     v
Loop Filter
     |
     v
VCO / DCO
     |
     v
Recovered Clock
```

The recovered clock is then used to sample the incoming data.

---

## 21. Summary

The basic PLL control loop is:

```text
Phase/Frequency Error
        ↓
       PFD
        ↓
   Charge Pump
        ↓
   Loop Filter
        ↓
      VCTRL
        ↓
       VCO
        ↓
     Divider
        ↓
Feedback Clock
```

The PLL continuously adjusts the VCO until:

```text
Fref = Fout / N
```

Therefore:

```text
Fout = N × Fref
```

A PLL design is mainly a trade-off between:

- Lock time
- Stability
- Jitter
- Phase noise
- Reference spur
- Power consumption
- Loop bandwidth
