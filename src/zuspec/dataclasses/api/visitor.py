import dataclasses as dc
from typing import Callable, ClassVar, Dict, Type
from ..annotation import Annotation
from ..component import Component
from ..struct import Struct
import inspect
import ast
import textwrap

@dc.dataclass
class Visitor(object):
    _type_m : Dict[Type,Callable] = dc.field(default_factory=dict)

    def __post_init__(self):
        self._type_m = {
            Component : self.visitComponentType
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

    def visitStructType(self, t : Struct):
        # Always work with the class, not the instance
        t_cls = t if isinstance(t, type) else type(t)
        for f in dc.fields(t_cls):
            self._dispatchField(f)
        
        for f in dir(t_cls):
            o = getattr(t_cls, f)
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

    def _dispatchField(self, f : dc.Field):
        self.visitField(f)

    def visitField(self, f : dc.Field):
        pass

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
        pass
