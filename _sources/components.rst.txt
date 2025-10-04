##########
Components
##########

Components provide the structural aspect of a Zuspec model. Depending
on their application, Zuspec components have close similarities to 
SystemVerilog `module`, SystemC `component`, and PSS `component` types.


****************
Built-in Methods
****************

**********************
Supported Exec Methods
**********************

Exec methods are evaluated automatically based on events in the
model. User code may not invoke these methods directly.

comb
****
A `@comb` exec method is evaluated whenever one of 
the variables references changes. The `@comb` exec is 
exclusively used with RTL descriptions

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



