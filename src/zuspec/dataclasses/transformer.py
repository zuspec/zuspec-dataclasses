import zuspec.dm as dm
import dataclasses as dc
from .types import Struct, SignWidth

class DataclassesTransformer:
    """Maps Zuspec dataclasses types to zuspec.dm types collected
    in a dm.Context. 
    """
    def __init__(self):
        self.ctxt = dm.Context()

    def process(self, *args):
        for T in args:
            if issubclass(T, Struct):
                self.add_struct(T)
            else:
                # Future: handle other types
                pass

    def add_struct(self, T):
        name = T.__qualname__
        # If already processed, return
        if name in self.ctxt.type_m:
            return
        # Process base Struct subtype (excluding Struct itself)
        base_struct_cls = None
        for b in T.__bases__:
            if issubclass(b, Struct) and b is not Struct:
                base_struct_cls = b
                break
        # Ensure base is added first
        base_dt = None
        if base_struct_cls is not None:
            self.add_struct(base_struct_cls)
            base_dt = self.ctxt.type_m[base_struct_cls.__qualname__]
        s = dm.DataTypeStruct(super=base_dt)
        # Map fields
        from typing import get_origin, get_args, Annotated
        declared_names = set(getattr(T, '__annotations__', {}).keys())
        for f in dc.fields(T):
            if f.name not in declared_names:
                continue
            dt = None
            t = f.type
            # Handle Annotated[int, U(width)]
            if get_origin(t) is Annotated:
                base_t, *annots = get_args(t)
                if base_t is int:
                    width = -1
                    signed = True
                    for a in annots:
                        if isinstance(a, SignWidth):
                            width = a.width
                            signed = a.signed
                    dt = dm.DataTypeInt(bits=width, signed=signed)
            elif t is int:
                dt = dm.DataTypeInt(bits=-1, signed=True)
            elif t is str:
                dt = dm.DataTypeString()
            else:
                # Future: handle other types
                dt = dm.DataTypeInt(bits=-1, signed=True)  # placeholder
            s.fields.append(dm.Field(name=f.name, datatype=dt))
        self.ctxt.type_m[name] = s

    def result(self) -> dm.Context:
        return self.ctxt
