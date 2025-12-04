
# Bindmap and binding
A bindmap is a mapping of objects that specify how to connect elements
inside the model. A bindmap contains static reference that are interpreted
to make proper assignments.

A bindmap is implemented as a list of tuples where the element referenced by
the first tuple entry must be assigned the value of the element 
referenced by the second tuple entry.

A bindmap is formed by calling the __bind__ function with a special object 
that computes the proper bind entries by indexing the type model.

There are several legal variants of bindmap entries. Others must result
in an exception.

```python3

    class DataIF(Protocol):
        async def call(self, req : int) -> int: ...

    @zdc.dataclass
    class MyConsC(zdc.Component):
        # Bind, in this context, must work in one of two ways
        # -  
        cons : DataIF = zdc.export()

        def __bind__(self): return {
            self.cons.call : self.target
        }

        async def target(self, req : int) -> int:
            return req+2
```

In this case, the code is binding a method (self.target) to the
API of an export. The elements of the path must be:
- ExportMethod( ("cons", "call") )
- Method( ("target") )

```python3
    @zdc.dataclass
    class MyC(zdc.Component):
        p : MyProdC = zdc.field() # default_factory=MySubC)
        c : MyConsC = zdc.field()

        def __post_init__(self):
            print("MyC.__post_init__: %s" % str(self), flush=True)
#            super().__post_init__()

        def __bind__(self): return {
            self.p.prod : self.c.cons
        }
```

In this case, assume MyProdC has a port named 'prod', while MyConsC has an 
export named 'cons'. The elements of the path must be:
- Port( ("p", "prod") )
- Export( ("c", "cons") )

# Ordering the bindmap
After the bindmap is produced, the binds must be ordered and sorted.
- Targets must be listed as the first elements. Targets are:
  - Port
  - ExportMethod
- Sources must be listed as the second element. Sources are:
  - Export
- If both entries of a target are targets, the entry must placed after 
  one of the entries is assigned

# Applying the bindmap
bindmaps are applied bottom-up during the component build process (see obj_factory.py). 
At a given level, the bindmap is processed to:
- Identify the parent object of the target (starting from self)
- Get the value of the source
- Set the value of the target to the value of the source


