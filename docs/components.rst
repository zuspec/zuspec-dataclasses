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

*********************************
Supported Special-Purpose Methods
*********************************

activity
********
`@activity` decorated async methods may be declared on a component. 
The body of the method adheres to activity semantics. 



