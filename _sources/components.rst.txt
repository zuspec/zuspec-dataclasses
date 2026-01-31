##########
Components
##########

Components provide the structural aspect of a Zuspec model. Depending
on their application, Zuspec components have close similarities to 
SystemVerilog `module`, SystemC `component`, and PSS `component` types.

Instances of Zuspec components are never created directly. Zuspec 
automatically creates component instances for fields of `Component` type.
Creating an instance of a Zuspec component class outside a component
hierarchy (for example, in a test) must be done using the runtime factory.

.. code-block:: python3

    import zuspec.dataclasses as zdc

    @zdc.dataclass
    class Top(zdc.Component):
        clock : zdc.bit = zdc.input()
        reset : zdc.bit = zdc.input()

    # Create root component - triggers full tree elaboration
    top_i = Top()

*******************
Component Lifecycle
*******************

When a root component is instantiated, the following sequence occurs:

1. **Construction** - Root component and all child component fields 
   are constructed via the ObjFactory
2. **Tree Building** - ``__comp_build__`` recursively initializes:
   
   - Creates runtime implementation (``CompImplRT``) for each component
   - Sets timebase on root component
   - Discovers ``@process`` decorated methods
   - Initializes Memory, RegFile, and AddressSpace fields
   - Applies ``__bind__`` mappings (bottom-up)

3. **Validation** - Top-level ports are validated as bound
4. **Process Start** - Processes start lazily when ``wait()`` is called


*****************
Ports and Binding
*****************

Fields that are initialized using `input`, `output`, `port`, `mirror`, 
or are of type `Bundle`, are considered ports. A port is either a 
producer (eg output) or a consumer (eg input). Ports are `bound` 
together as part of the component elaboration process. 

The following can be bound together:
- Input and output
- Input and input
- Port and export
- Export and export
- Port and port
- Bundle and bundle mirror
- Bundle mirror and bundle mirror

Binds may be specified in two ways:
- Inline as part of field declaration
- Within a `__bind__` method declared in the component

In both cases, the bind method shall return a `dict` of 
mappings between ports.

.. code-block:: python3

    @zdc.dataclass
    class Initiator(zdc.Component):
        clock : zdc.bit = zdc.input()
        reset : zdc.bit = zdc.input()
        wb_i : WishboneInitiator = zdc.field()

    @zdc.dataclass
    class Top(zdc.Component):
        clock : zdc.bit = zdc.input()
        reset : zdc.bit = zdc.input()
        initiator : Initiator = zdc.field(bind=zdc.bind[Self,Initiator](lambda s,f:{
            f.clock : s.clock,
            f.reset : s.reset,
            f.wb_i : s.consumer.wb_t,
        }))


The example above shows the "inline" form of binding. The `bind` 
parameter to the `field` method specifies a method to call that 
returns a dict. The method must accept two parameters: a handle
to the parent class `self` and a handle to the field


.. code-block:: python3

    @zdc.dataclass
    class Initiator(zdc.Component):
        clock : zdc.bit = zdc.input()
        reset : zdc.bit = zdc.input()
        wb_i : WishboneInitiator = zdc.field()

    @zdc.dataclass
    class Top(zdc.Component):
        clock : zdc.bit = zdc.input()
        reset : zdc.bit = zdc.input()
        initiator : Initiator = zdc.field()
        
        def __bind__(self): return {
            self.initiator.clock : self.clock,
            self.initiator.reset : self.reset,
            self.initiator.wb_i : self.consumer.wb_t,
        }
    
The example above shows the method form of binding. The `__bind__`
method returns a dict mapping ports.

***************************
Memory and RegFile Binding
***************************

AddressSpace fields can be bound to Memory and RegFile instances
using the ``At`` helper to specify address offsets.

.. code-block:: python3

    @zdc.dataclass
    class ControlRegs(zdc.RegFile):
        status : zdc.Reg[zdc.u32] = zdc.field()
        control : zdc.Reg[zdc.u32] = zdc.field()

    @zdc.dataclass
    class SoC(zdc.Component):
        mem : zdc.Memory[zdc.u32] = zdc.field(size=0x10000)
        regs : ControlRegs = zdc.field()
        aspace : zdc.AddressSpace = zdc.field()

        def __bind__(self): return {
            self.aspace.mmap : (
                zdc.At(0x0000_0000, self.mem),
                zdc.At(0x1000_0000, self.regs),
            )
        }

The ``aspace.base`` provides a ``MemIF`` handle for byte-level access
to the mapped regions.


***************************
Hierarchical Port Binding
***************************

When a parent component has a port that needs to be passed down to child 
components, there are two approaches:

Approach 1: Direct Reference Assignment
========================================

Recommended for behavioral models where ports need to be shared with 
child components.

.. code-block:: python3

    @zdc.dataclass
    class Child(zdc.Component):
        _mem_if = None  # Store as regular field (not a port)
        
        def set_interface(self, mem_if):
            """Set the interface reference"""
            self._mem_if = mem_if
            
        async def operation(self):
            # Use the interface
            data = await self._mem_if.read(0x1000)

    @zdc.dataclass  
    class Parent(zdc.Component):
        mem = zdc.port()  # Port bound to external interface
        child: Child = zdc.field()
        
        def setup(self):
            """Call after binding is complete"""
            self.child.set_interface(self.mem)

In tests or top-level components, call ``setup()`` at the start of your 
``run()`` method after the component tree is fully bound:

.. code-block:: python3

    @zdc.dataclass
    class Top(zdc.Component):
        parent: Parent = zdc.field()
        memory: Memory = zdc.field()
        
        def __bind__(self):
            return {
                self.parent.mem: self.memory.mem_if
            }
        
        async def run(self):
            self.parent.setup()  # Initialize child interfaces
            # Now proceed with operations
            await self.parent.child.operation()

Approach 2: Hierarchical Binding in __bind__
=============================================

For hierarchical port-to-port bindings, the parent's ``__bind__`` 
can include mappings for child ports. This approach works when 
child ports can be statically bound:

.. code-block:: python3

    @zdc.dataclass
    class Child(zdc.Component):
        mem = zdc.port()
        
    @zdc.dataclass
    class Parent(zdc.Component):
        mem = zdc.port()
        child: Child = zdc.field()
        
        def __bind__(self):
            return {
                self.child.mem: self.mem,  # Bind child port to parent port
            }

**Note:** Approach 1 is simpler and more flexible for operations-level 
behavioral models. Use Approach 2 when you need static port connectivity.


***************************
Supported Exec Methods
***************************

Exec methods are evaluated automatically based on events in the
model. User code may not invoke these methods directly.

comb
****
A `@comb` exec method is evaluated whenever one of 
the variables references changes. The `@comb` exec is 
exclusively used with RTL descriptions. 

process
****
The ``@process`` async exec method creates an independent background thread
that starts when the first ``wait()`` call is made anywhere in the component tree.
A ``@process`` exec method is an independent thread of control in the model.

Processes start lazily to allow the component tree to be fully
constructed before simulation begins.

When to Use @process
====================

- **Monitoring or reactive behaviors** that run continuously
- **Clock generation** or periodic activities  
- **Protocol monitors** or checkers
- Models requiring **concurrent background activity**

When NOT to Use @process
=========================

- **Operations-level behavioral models** (use direct async methods instead)
- **Synchronous operations** that complete immediately
- **Simple request/response patterns**

For operations-level models, implement async methods that perform their
work and return, rather than background processes.

Examples
========

**Good: Background monitoring process**

.. code-block:: python3

    @zdc.dataclass
    class Monitor(zdc.Component):
        regs: StatusRegs = zdc.field()
        
        @zdc.process
        async def monitor(self):
            """Continuous monitoring in background"""
            while True:
                status = await self.regs.status.read()
                if status.error:
                    print("Error detected!")
                await self.wait(zdc.Time.ns(100))

**Good: Operations-level behavioral model**

.. code-block:: python3

    @zdc.dataclass
    class Device(zdc.Component):
        regs: DeviceRegs = zdc.field()
        
        async def transfer(self, addr: int, size: int):
            """Direct async method - NOT @process"""
            # Perform operation and return immediately
            await self.regs.addr.write(addr)
            # ... perform transfer ...
            await self.regs.status.write(COMPLETE)

**Original example for reference:**

.. code-block:: python3

    @zdc.dataclass
    class Worker(zdc.Component):
        @zdc.process
        async def run(self):
            for i in range(10):
                await self.wait(zdc.Time.ns(100))
                print(f"Iteration {i} at {self.time()}")

sync
****
A `@sync` exec method is evaluated on the active transition of 
its associated clock or reset. All assignments
to outputs are considered nonblocking.  
The `@sync` exec is exclusively used with RTL descriptions

.. code-block:: python3

    import zuspec.dataclasses as zdc
    @zdc.dataclass
    class Counter(zdc.Component):
      clock : zdc.bit = zdc.input()
      reset : zdc.bit = zdc.input()
      count : zdc.u32 = zdc.output()

      @zdc.sync(clock=lambda s:s.clock, reset=lambda s:s.reset)
      def inc(self):
        if self.reset:
          self.count = 0
        else:
          self.count += 1
          self.count += 1

The synchronous counter above produces the value '0' on the
`count` output while reset is active. While reset is not active,
the `count` output increments by one on each active clock edge.
Assignments are delayed, so only the last increment statement takes
effect. The expected output is as follows:

======  =======  =======
reset   clock    count
======  =======  =======
1       1        0
0       1        1
0       1        2
0       1        3
0       1        ...
======  =======  =======


*********************************
Supported Special-Purpose Methods
*********************************

activity
********
`@activity` decorated async methods may be declared on a component. 
The body of the method adheres to activity semantics. 



