##########
Components
##########

Components provide the structural aspect of a Zuspec model. Depending
on their application, Zuspec components have close similiarities to 
SystemVerilog `module` and SystemC `component`.

components 

****************
Built-in Methods
****************

**********************
Supported Exec Methods
**********************


comb
****
A `@comb` async exec method is evaluated whenever one of 
the variables references changes. The `@comb` exec is 
exclusively used with RTL descriptions

process
*******
The `@process` exec method is evaluated when evaluation of 
the containing component begins. A `@process` exec method is
an independent thread of control in the model.

sync
****
A `@sync` async exec method is evaluated when its associated
timebase is evaluated (eg at a clock edge). All assignments
to outputs are considered nonblocking.
The `@sync` exec is exclusively used with RTL descriptions

*********************************
Supported Special-Purpose Methods
*********************************

activity
********
`@activity` decorated async methods may be declared on a component. 
The body of the method adheres to activity semantics. 



