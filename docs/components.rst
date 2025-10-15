##########
Components
##########

Components provide the structural aspect of a Zuspec model. Depending
on their application, Zuspec components have close similarities to 
SystemVerilog `module`, SystemC `component`, and PSS `component` types.

Instances of Zuspec components are never created directly. Zuspec 
automatically creates component instances for fields of `Component` type.
Creating an instance of a Zuspec component class outside a component
hierarchy (for example, in a test) must be done using a factory class.

.. code-block:: python3

    import zuspec.dataclasses as zdc
    import zuspec.be.py as zpy

    @zdc.dataclass
    class Top(zdc.Component):
        clock : zdc.Bit = zdc.input()
        reset : zdc.Bit = zdc.input()

    top_i = zpy.Factory().build(Top)


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
        clock : zdc.Bit = zdc.input()
        reset : zdc.Bit = zdc.input()
        wb_i : WishboneInitiator = zdc.field()

    @zdc.dataclass
    class Top(zdc.Component):
        clock : zdc.Bit = zdc.input()
        reset : zdc.Bit = zdc.input()
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
        clock : zdc.Bit = zdc.input()
        reset : zdc.Bit = zdc.input()
        wb_i : WishboneInitiator = zdc.field()

    @zdc.dataclass
    class Top(zdc.Component):
        clock : zdc.Bit = zdc.input()
        reset : zdc.Bit = zdc.input()
        initiator : Initiator = zdc.field()
        
        def __bind__(self): return {
            self.initiator.clock : self.clock,
            self.initiator.reset : self.reset,
            self.initiator.wb_i : self.consumer.wb_t,
        }
    
The example above shows the method form of binding. The `__bind__`
method returns a dict mapping ports.


**********************
Supported Exec Methods
**********************

Exec methods are evaluated automatically based on events in the
model. User code may not invoke these methods directly.

comb
****
A `@comb` exec method is evaluated whenever one of 
the variables references changes. The `@comb` exec is 
exclusively used with RTL descriptions. 

process
*******
The `@process` async exec method is evaluated when evaluation of 
the containing component begins. A `@process` exec method is
an independent thread of control in the model.

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
      clock : zdc.Bit = zdc.input()
      reset : zdc.Bit = zdc.input()
      count : zdc.Bit[32] = zdc.output()

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

reset | clock | count
------|-------|------
1     | 1     | 0
0     | 1     | 1
0     | 1     | 2
0     | 1     | 3
0     | 1     | ...


*********************************
Supported Special-Purpose Methods
*********************************

activity
********
`@activity` decorated async methods may be declared on a component. 
The body of the method adheres to activity semantics. 



