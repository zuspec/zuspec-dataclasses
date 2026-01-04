
# Design Abstraction Profiles

Overall guidelines:
- Fields are never manually constructed
- Use Tuple for fixed-size arrays and specify zdc.field(size=<elems>)
- Connect ports, exports, inputs, and outputs using '__bind__'. 
- Do not use name-based lookup (hasattr, getattr, setattr). Types must be statically-known

## Logical Interface

### [Future] Scenario 
Descriptions as the scenario level schedule Action execution. Actions
communicate via objects provided by Pools and obtained by an Action
via Claims.

### Operation
An operation-level description is captured in terms of async methods
that carry out key operations. The design implementation likely maintains
state between calls, but most control data for the operation should be 
passed into the operation method.

The operation interface of a device is defined as a Protocol class with
abstract async methods. The operation interface may be implemented in 
several ways:
- The device could implement it if the device's physical interface is
  at the operation level
- An implementation class could 

### MMIO
An MMIO interface consists of registers, memory, and events. The interface
is defined as a protocol class with a memory-model field and Event
fields (if applicable). Access to non-register memory may be provided via
a MemIF field on the MMIO API class. 

## Physical Interface

### Protocol 
A protocol-level interface is 

### TLM

### MMIO
A device may directly expose a MMIO interface as a physical interface. This is
often done to enable MMIO content (eg driver) to be implemented against a 
matching device model.

### Operation
A device may directly expose an operation interface as a physical interface.
This is often done early in the development process, and allows operation-level 
tests to be developed while minimizing the modeling effort.

## Internal Implementation

### Synthesizable RTL

Synthesizable RTL implementation is expressed in terms of inputs and outputs, 
and comb and sync methods. comb and sync methods are nonblocking (not async),
and react to changes to signals. 

### Behavioral RTL
Behavioral RTL is a superset of Synthesizable RTL that also allows 
`process` methods that are async and interact with other async methods. 
Processes can use the Component `wait` method to delay evaluation. They can
also set the value of signals.

### Cycle-Accurate TLM
Cycle-accurate transaction-level modeling 

# Savings Opportunities
- Access register model without wiring
  - Requires transformation to direct Verilog
- Good to have notion of selector
  - Key is the use of a 'ref'. 'ref' conveys multiplexing
  - How do we distribute references?
  -> Actually, pool might be useful here...
  -> Claim on <block>
  -> Engine has a claim on channel registers
  -> Bind connects that to a continuous claim
  -> Continuouskj0
  - Select one bank of registers -> 

class Engine(zdc.Component):
    regs : ChannelRegs = zdc.claim()
    - Event when bind changes?

class Dma(zdc.Component):
    regs : DmaRegs = zdc.field()
    regs_p : Pool[ChannelRegs] = zdc.pool()
    engine : Engine = zdc.field()
    channel : 

    // Modules are too 'structural'
    // Need a function-based way to specify
    //
    // - Steer, slice, combine data
    // -> Sort of what HLS is designed to do...
    // -> Probably need some way to allow this to be scheduled
    //
    // Make it easy to describe:
    // - Pool of 'N' things
    // - Reference one of those things
    // -> Ref means - mirror assign (microsoft design language)
    //
    // Use async functional programming to build up logic
    // This can be timed...
    // Methods must support local storage
    // Must be able to identify a storage-management strategy
    def __bind__(self): return {
        self.engine.regs : zdc.select(self.regs_p.get(self.))
    }

# Two big categories
- Pure-Python Runtime
- Retargetable
  - Elements have concrete types
  - name-based manipulation is disallowed (hasattr, getattr, etc)
    - Interesting angle to have a selector a.select(map i : name)
  - Handle enums directly
  - Async invocation is instantiation
  - Effectively, all data must either be
    - A width-annotated integer type, string, or float
    - A string
    - A Zuspec-derived class (Struct, Class, Component, etc)
    - A known collection type (list, dict, tuple)
    -> int is bad because it is infinite width
    -> object is bad because we can't translate it
  - @zdc.dataclass should accept a 'profile' optional parameter
    -> Use to tag content within the class as needing to conform to a 
      specific set of rules
    -> The Python profile is permissive and doesn't flag rules above
    -> The ZuspecFull profile is the default. Rules above are enforced