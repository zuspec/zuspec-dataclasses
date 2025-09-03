#######
Actions
#######

Actions are dynamic behavioral elements that are frequently used for
modeling test behavior. In most cases, Actions are associated with a
component.

.. code-block:: python3
    import zuspec.dataclasses as zdc

    class MyC(zdc.Component):
        a : int = 5

    class MyA(zdc.Action[MyC]):

        def post_solve(self):
            print("comp.a=%d" % self.comp.a)

`MyA` must be evaluated inside a scope that provides `MyC` services.

****************
Built-in Methods
****************

activity
********
If defined, the `activity` async method is evaluated to provide
the implementation of the containing action. The code within an 
`activity` method is evaluated according to activity semantics.


body
****
If defined, the `body` async method is evaluated to provide the 
implementation of the containing action.

***************************
Supported Decorated Methods
***************************

activity
********
A method decorated with `@activity` is 
