import dataclasses as dc
from dataclasses import Field, MISSING
from typing import Callable, ClassVar, Dict, Type
from ..annotation import Annotation
from ..bit import Bit
from ..component import Component
from ..ports import Input, Output
from ..struct import Struct
import inspect
import ast
import textwrap

class _BindPathMock:
    def __init__(self, typ, path=None):
        self._typ = typ
        self._path = path or []

    def __getattribute__(self, name):
        if name in ("_typ", "_path", "__class__"):
            return object.__getattribute__(self, name)
        # Validate field exists
        fields = {f.name for f in dc.fields(self._typ)}
        if name not in fields:
            raise AttributeError(f"Invalid field '{name}' in path {'.'.join(self._path + [name])}")
        # Get field type
        field_type = next(f.type for f in dc.fields(self._typ) if f.name == name)
        # Return new mock for nested access
        return _BindPathMock(field_type, self._path + [name])

    def __call__(self):
        # For supporting callables if needed
        return self

    def __repr__(self):
        return f"_BindPathMock({self._typ}, {self._path})"

@dc.dataclass
class Visitor(object):
    _type_m : Dict[Type,Callable] = dc.field(default_factory=dict)
    _field_factory_m : Dict[Type,Callable] = dc.field(default_factory=dict)

    def __post_init__(self):
        self._type_m = {
            Component : self.visitComponentType
        }
        self._field_factory_m = {
            Input : self.visitInput,
            Output : self.visitOutput
        }

    def visit(self, t):
        # Accept both class and instance
        t_cls = t if isinstance(t, type) else type(t)
        found = False
        for base_t,method in self._type_m.items():
            if issubclass(t_cls, base_t):
                method(t)
                found = True
                break
        if not found:
            raise Exception("Unsupported class %s" % str(t))

    def visitComponentType(self, t):
        # Always work with the class, not the instance
        t_cls = t if isinstance(t, type) else type(t)
        self.visitStructType(t_cls)
        pass

    def _elabBinds(self, bind_lambda, root_type):
        # Instantiate mock for root
        root_mock = _BindPathMock(root_type, ["s"])
        # Evaluate lambda to get mapping
        mapping = bind_lambda(root_mock)
        result = {}
        for k, v in mapping.items():
            # Extract path from mock objects
            k_path = getattr(k, "_path", None)
            v_path = getattr(v, "_path", None)
            if k_path is None or v_path is None:
                raise ValueError("Bind keys/values must be _BindPathMock instances")
            # Get terminal Field for key
            k_typ = root_type
            for name in k_path[1:]:  # skip 's'
                field = next(f for f in dc.fields(k_typ) if f.name == name)
                k_typ = field.type
            k_field = field
            # Get terminal Field for value
            v_typ = root_type
            for name in v_path[1:]:
                field = next(f for f in dc.fields(v_typ) if f.name == name)
                v_typ = field.type
            v_field = field
            result[(k_field, tuple(k_path))] = (v_field, tuple(v_path))
        return result

    def _visitFields(self, t : Struct):
        print("--> visitFields")
        for f in dc.fields(t):
            print("Field: %s" % f.name)
            self._dispatchField(f)

    def _dispatchField(self, f : dc.Field):
        if f.default_factory not in (None, dc.MISSING):
            if issubclass(f.default_factory, Input):
                self.visitFieldInOut(f, False)
            elif issubclass(f.default_factory, Output):
                self.visitFieldInOut(f, True)
            else:
                raise Exception()
            pass
        elif f.type in (str, int, float):
            self.visitFieldData(f)
        else:
            self.visitFieldClass(f)

    def _visitFunctions(self, t):
        for e in dir(t):
            if not e.startswith("__") and callable(getattr(t, e)):
                print("Function: %s" % e)
                self.visitFunction(getattr(t, e))

    def visitFunction(self, f):
        pass

    def _visitDataType(self, t):

        if t == int:
            self.visitDataTypeInt()
        elif type(t) is type:
            zsp_base_t = (
                (Component, self.visitDataTypeComponent),
            )

            v = None
            for tt,vv in zsp_base_t:
                print("t: %s tt: %s vv: %s" % (t, tt, vv))
                if issubclass(t, tt):
                    v = vv
                    break
            
            v(t)
        else:
            raise Exception("Unknown type %s" % str(t))
        pass

    def visitDataTypeComponent(self, t):
        pass

    def visitDataTypeInt(self):
        pass

    def visitField(self, f : dc.Field):
        pass

    def visitFieldClass(self, f : dc.Field):
        self.visitField(f)

    def visitFieldInOut(self, f : dc.Field, is_out : bool):
        self.visitField(f)

    def visitFieldData(self, f : dc.Field):
        self.visitField(f)
        self._visitDataType(f.type)

    def visitStructType(self, t : Struct):
        self._visitFields(t)
        
        for f in dir(t):
            o = getattr(t, f)
            if callable(o) and hasattr(o, Annotation.NAME):
                # Extract source code of the method
                try:
                    src = inspect.getsource(o)
                    src = textwrap.dedent(src)
                    tree = ast.parse(src)
                    for stmt in tree.body[0].body:  # tree.body[0] is the FunctionDef
                        self.visit_statement(stmt)
                except Exception as e:
                    print(f"Could not process method {f}: {e}")
#                self.visitExec(f, o)
#                print("Found")

    def visitExec(self, name, m):
        pass

    def visitOutputField(self, f : dc.Field):
        self.visitField(f)

    def visitIntField(self, f : dc.Field):
        self.visitField(f)

    def visitStrField(self, f : dc.Field):
        self.visitField(f)

    def visit_statement(self, stmt):
        method = f"visit_{type(stmt).__name__}"
        visitor = getattr(self, method, self.generic_visit)
        return visitor(stmt)

    def generic_visit(self, stmt):
        # Recursively visit child statements if present
        for field, value in ast.iter_fields(stmt):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.stmt):
                        self.visit_statement(item)
            elif isinstance(value, ast.stmt):
                self.visit_statement(value)

    def visit_Assign(self, stmt: ast.Assign):
        # Example: handle assignment statements
        # Recursively visit child nodes if needed
        self.generic_visit(stmt)

    def visit_If(self, stmt: ast.If):
        # Example: handle if statements
        for s in stmt.body:
            self.visit_statement(s)
        for s in stmt.orelse:
            self.visit_statement(s)

    def visit_Expr(self, stmt: ast.Expr):
        # Example: handle expression statements
        self.generic_visit(stmt)

    def visitInput(self, f : dc.Field):
        self.visitField(f)
        pass

    def visitOutput(self, f : dc.Field):
        self.visitField(f)
        pass
