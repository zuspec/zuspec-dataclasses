
# Zuspec Registers and Memory

Registers and memory are core concepts in system modeling. Zuspec
provides first-class features to support both of these notions.

## Address Handle
Zuspec provides an AddrHandle class that is, effectively,
an abstraction over a pointer. Registers and memory are
accessed via methods on an object of this type.

## Address Spaces
An address space provides a software abstraction over storage 
(memory and registers). Its primary purpose is organizational -
associating storage (memories, register files) and sub-address 
spaces with an address range and optional meta-data. Its secondary 
purpose is to act as a source of Address Handles and allocators.

## Memory

A memory is an array of storage that can be accessed via an
API. A memory natively imposes no timing on access. 


## Registers

Zuspec supports the core set of register descriptions in SystemRDL, but
captured as Python dataclasses. A register model described in Zuspec is a 
set of Protocol classes that capture the register structure and behavior.

- A RegFile is a group of registers (SystemRDL terminology)
- Register layouts are described in packed structs

### SystemRDL Feature Implementation Checklist

#### Core Components
- [ ] **field** - Basic storage element abstraction
- [ ] **reg** - Register containing one or more fields
- [ ] **regfile** - Hierarchical grouping of registers
- [ ] **addrmap** - Address map organizing registers/regfiles/memories
- [ ] **mem** - Memory component (contiguous array of data elements)
- [ ] **signal** - Wire for interconnect or additional I/O
- [ ] **enum** - Enumeration for field encodings
- [ ] **constraint** - Verification assertions

#### Component Definition & Instantiation
- [ ] Definitive (named/reusable) component definitions
- [ ] Anonymous (inline) component definitions
- [ ] Verilog-style parameters for component generalization
- [ ] Parameter overrides at instantiation
- [ ] Scalar and array instantiation
- [ ] Multi-dimensional arrays
- [ ] Address allocation operators (@, +=, %)

#### Implementation
A register type is captured as a Python dataclass that inherits
from zdc.PackedStruct or zdc.RegType. Independent of base type,
fields in a register type must be width annotated. It is legal
for fields in a RegType class to specify hardware and software
field properties. 

```python
class MyField(zdc.PackedStruct):

class MyReg(zdc.RegType):
    en : zdc.uint1_t = zdc.field()
```

Access properties for hw and sw are captured as an enum 
FieldAccess with corresponding values (r, w, rw, etc). Software access
behavior is also encoded as enums for FieldOnWrite, FieldOnRead.


#### Field Properties

In SystemRDL, software and hardware access behavior is specified **per-field**, not per-register.
Each field within a register can have independent access modes and side-effects.

##### Basic Field Properties
- [ ] **hw** - Hardware access (r, w, rw, wr, w1, rw1, na)
- [ ] **sw** - Software access (r, w, rw, wr, w1, rw1, na)
- [ ] **reset** - Reset value
- [ ] **resetsignal** - Custom reset signal reference
- [ ] **encode** - Enumeration encoding reference
- [ ] **fieldwidth** - Field bit width

##### Software Access Behavior (per-field onread/onwrite)
- [ ] **onread=rclr** - Clear on read
- [ ] **onread=rset** - Set on read
- [ ] **onwrite=woset** - Write one to set
- [ ] **onwrite=woclr** - Write one to clear
- [ ] **onwrite=wot** - Write one to toggle
- [ ] **onwrite=wzs** - Write zero to set
- [ ] **onwrite=wzc** - Write zero to clear
- [ ] **onwrite=wzt** - Write zero to toggle
- [ ] **onwrite=wclr** - Write clears all bits
- [ ] **onwrite=wset** - Write sets all bits
- [ ] **swwe** - Software write enable
- [ ] **swwel** - Software write enable (active low)
- [ ] **swacc** - Software access strobe output
- [ ] **swmod** - Software modify strobe output
- [ ] **singlepulse** - Single-cycle pulse on write

##### Hardware Access Behavior
- [ ] **we** - Hardware write enable
- [ ] **wel** - Hardware write enable (active low)
- [ ] **hwset** - Hardware set
- [ ] **hwclr** - Hardware clear
- [ ] **hwenable** - Hardware enable signal
- [ ] **hwmask** - Hardware mask signal
- [ ] **next** - Next value input signal
- [ ] **precedence** - hw vs sw write precedence

##### Counter Properties
- [ ] **counter** - Enable counter behavior
- [ ] **incr** - Increment signal
- [ ] **incrvalue** - Increment value
- [ ] **incrwidth** - Increment value width
- [ ] **incrsaturate** - Saturate on increment
- [ ] **incrthreshold** - Increment threshold
- [ ] **decr** - Decrement signal
- [ ] **decrvalue** - Decrement value
- [ ] **decrwidth** - Decrement value width
- [ ] **decrsaturate** - Saturate on decrement
- [ ] **decrthreshold** - Decrement threshold
- [ ] **overflow** - Overflow output signal
- [ ] **underflow** - Underflow output signal
- [ ] **saturate** - Counter saturation value
- [ ] **threshold** - Counter threshold value

##### Interrupt Properties
- [ ] **intr** - Interrupt field
- [ ] **enable** - Interrupt enable reference
- [ ] **mask** - Interrupt mask reference
- [ ] **halt** - Interrupt halt
- [ ] **haltenable** - Halt enable reference
- [ ] **haltmask** - Halt mask reference
- [ ] **sticky** - Sticky interrupt (level-sensitive)
- [ ] **stickybit** - Sticky bit interrupt (edge-sensitive)
- [ ] **nonsticky** - Non-sticky interrupt

##### Field Reduction Operations
- [ ] **anded** - Reduction AND output
- [ ] **ored** - Reduction OR output
- [ ] **xored** - Reduction XOR output

#### Register Properties
- [ ] **regwidth** - Register width in bits (default 32)
- [ ] **accesswidth** - CPU interface access width
- [ ] **shared** - Shared register across multiple address maps
- [ ] Field ordering (lsb0/msb0)
- [ ] Alias registers
- [ ] Internal vs external registers

#### Register File Properties
- [ ] **alignment** - Address alignment for contained elements
- [ ] **sharedextbus** - Shared external bus
- [ ] Hierarchical nesting of regfiles

#### Address Map Properties
- [ ] **alignment** - Address alignment
- [ ] **addressing** - Addressing mode (compact, regalign, fullalign)
- [ ] **bigendian** / **littleendian** - Byte ordering
- [ ] **lsb0** / **msb0** - Bit ordering
- [ ] **bridge** - Bridge to different address domain
- [ ] **rsvdset** / **rsvdsetX** - Reserved field handling
- [ ] **errextbus** - External bus error handling
- [ ] **sharedextbus** - Shared external bus

#### Memory Properties
- [ ] **mementries** - Number of memory entries
- [ ] **memwidth** - Memory data width
- [ ] **sw** - Software access mode
- [ ] Virtual registers within memory

#### Signal Properties
- [ ] **signalwidth** - Signal bit width
- [ ] **sync** / **async** - Synchronization
- [ ] **activehigh** / **activelow** - Active level
- [ ] **cpuif_reset** - CPU interface reset signal
- [ ] **field_reset** - Field reset signal

#### Universal Properties (All Components)
- [ ] **name** - Descriptive name string
- [ ] **desc** - Description string
- [ ] **ispresent** - Conditional presence (for parameterized designs)

#### Verification Constructs
- [ ] **hdl_path** - HDL hierarchy path for backdoor access
- [ ] **hdl_path_slice** - HDL path for field slices
- [ ] **hdl_path_gate** - Gate-level HDL path
- [ ] **donttest** - Exclude from automated testing
- [ ] **dontcompare** - Exclude from comparison checks
- [ ] **constraint** - Constraint definitions

#### User-Defined Properties
- [ ] Custom property definitions
- [ ] Property binding to component types
- [ ] Struct definitions for complex properties

#### Data Types
- [ ] **bit** - Unsigned integer (parameterized width)
- [ ] **longint unsigned** - 64-bit unsigned integer
- [ ] **boolean** - true/false
- [ ] **string** - Character string
- [ ] **accesstype** - r, w, rw, wr, w1, rw1, na
- [ ] **onreadtype** - rclr, rset
- [ ] **onwritetype** - woset, woclr, wot, wzs, wzc, wzt, wclr, wset
- [ ] **addressingtype** - compact, regalign, fullalign
- [ ] **precedencetype** - hw, sw
- [ ] Enumerations
- [ ] Arrays
- [ ] Structures

#### Preprocessor
- [ ] `include directive
- [ ] `define / `undef macros
- [ ] `ifdef / `ifndef / `else / `endif conditionals
- [ ] Embedded Perl preprocessing




