##########
Data Types
##########

Zuspec datatypes include Python data types (int, str, list, dict, set, tuple),
as well as types derived from Zuspec base classes.

Zuspec class 

- maximize benefits of a dynamically-typed language

A modeling type is: base type + const param values (public fields?)

```python3
class C1(zdc.Component):
  p1 : int = zdc.const()
  p2 : int = zdc.const()
  pass

class T(zdc.Component):
  c1_1 : C1 = zdc.field(init=dict(p1=20,p2=30))
  c1_2 : C1 = zdc.field(init=dict(p1=10,p2=20))

  def __post_init__(self):
    pass

```

c1_1 and c1_2 are tracked as two distinct types because the final
public-constant values are different. 

If __post_init__ is defined, then the type must be elaborated 
to determine the specific type.

