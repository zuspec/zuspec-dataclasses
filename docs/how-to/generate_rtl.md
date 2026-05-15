# How-to: Generate RTL from a Register File

Zuspec can synthesise an APB4-compliant SystemVerilog module directly from a
`RegisterFile` declaration.  The emitter lives in `zuspec-synth`.

---

## Prerequisites

```bash
pip install zuspec-synth   # or install from packages/zuspec-synth
```

---

## Standalone function — `synthesize_regfile()`

```python
from zuspec.synth.passes import synthesize_regfile
import zuspec.dataclasses as zdc

@zdc.regfile
class DMARegs(zdc.RegisterFile):

    @zdc.reg(offset=0x00)
    class CTRL:
        START: zdc.u1 = zdc.FieldAttr.Pulse
        ABORT: zdc.u1 = zdc.FieldAttr.Pulse

    @zdc.reg(offset=0x04)
    class STATUS:
        BUSY:  zdc.u1 = zdc.reg_field(sw=zdc.SW.RO, hw=zdc.HW.W,
                                       hwset=True, hwclr=True, default=0)
        DONE:  zdc.u1 = zdc.FieldAttr.StickyBit
        ERROR: zdc.u1 = zdc.FieldAttr.StickyBit


sv_module, sv_package = synthesize_regfile(DMARegs)

with open("dma_regs.sv",     "w") as f: f.write(sv_module)
with open("dma_regs_pkg.sv", "w") as f: f.write(sv_package)
```

`synthesize_regfile(cls, module_name=None)` returns a `(module_sv, package_sv)` tuple.
If `module_name` is omitted it is derived from the class name (snake_case).

---

## The generated RTL structure

The emitter produces a zero-wait-state APB4 slave:

```
module dma_regs (
    input  logic        clk,
    input  logic        rst,
    // APB4 subordinate port
    input  logic        psel,
    input  logic        penable,
    input  logic        pwrite,
    input  logic [31:0] paddr,
    input  logic [31:0] pwdata,
    input  logic [3:0]  pstrb,
    output logic        pready,
    output logic        pslverr,
    output logic [31:0] prdata,
    // Hardware interface
    input  dma_regs_hwif_in_t  hwif_in,
    output dma_regs_hwif_out_t hwif_out
);
```

The companion package file (`dma_regs_pkg.sv`) defines `dma_regs_hwif_in_t`
and `dma_regs_hwif_out_t` structs.

### `hwif_in` members

| Field property | Generated `hwif_in` member |
|---|---|
| `hw=HW.W` or `hw=HW.RW` | `hwif_in.REG.FIELD_next` |
| `stickybit=True` or `hwset=True` | `hwif_in.REG.FIELD_hwset` |
| `hwclr=True` | `hwif_in.REG.FIELD_hwclr` |
| `we=True` | `hwif_in.REG.FIELD_we` |

### `hwif_out` members

| Field property | Generated `hwif_out` member |
|---|---|
| `hw=HW.R` or `hw=HW.RW` | `hwif_out.REG.FIELD_value` |
| `singlepulse=True` or `swmod=True` | `hwif_out.REG.FIELD_swmod` |
| any stickybit in register | `hwif_out.REG.intr` |

---

## Synthesis pass — integration with `zuspec-synth`

For integration with the full synthesis pipeline use `MmrRegFileEmitPass`:

```python
from zuspec.synth import SynthIR
from zuspec.synth.passes import MmrRegFileEmitPass

ir = SynthIR()
pass_ = MmrRegFileEmitPass(DMARegs, field_name="regs")
pass_.run(ir)

# SV text is stored under these keys:
module_sv  = ir.lowered_sv["sv/regfile/regs"]
package_sv = ir.lowered_sv["sv/regfile/regs_pkg"]
```

---

## Supported field types

| Feature | `reg_field()` parameter | RTL behaviour |
|---|---|---|
| Read-write | `sw=RW, hw=R` | Standard flip-flop |
| Read-only (HW drives) | `sw=RO, hw=W` | `hwif_in.FIELD_next` drives storage |
| Write-only | `sw=WO` | No read path; always reads as 0 |
| Singlepulse | `singlepulse=True` | Auto-cleared to 0 one cycle after SW write |
| Stickybit | `stickybit=True` | HW OR-sets; SW write-1-to-clear |
| HW set/clear | `hwset=True`, `hwclr=True` | Separate set/clear strobes in `hwif_in` |

---

## Next steps

- [Generate SW artefacts](generate_sw_artefacts.md) — C header and Python driver
  that complement the generated RTL.
