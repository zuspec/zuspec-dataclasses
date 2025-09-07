import dataclasses as dc
from typing import Callable, ClassVar, Dict, Type
from ..annotation import Annotation
from ..bit import Bit
from ..component import Component
from ..ports import Input, Output
from ..struct import Struct
import inspect
import ast
import textwrap

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

    def _visitFields(self, t : Struct):
        print("--> visitFields")
        for f in dc.fields(t):
            print("Field: %s" % f.name)
            self._dispatchField(f)

    def _dispatchField(self, f : dc.Field):
        if f.default_factory not in (None, dc.MISSING):
            print("default_factory=%s" % f.default_factory)
            # if issubclass(f.default_factory, input):
            #     self.visitFieldInput(f)
            # elif issubclass(f.default_factory, Output):
            #     self.visitOutputField(f)
            pass
        else:
            # Plain-data field
            self.visitFieldData(f)

            # if f.type == int:
            #     self.visitIntField(f)
            # elif f.type == str:
            #     self.visitStrField(f)
            # elif callable(f.type):
            #     if issubclass(f.type, Bit):
            #         visitBitField(f)
            #     print("class")
            # else:
            #     print("Error: unhandled: %s" % str(f.type))

    def _visitDataType(self, t):
        if t == int:
            self.visitDataTypeInt()
        else:
            raise Exception("Unknown type %s" % str(t))
        pass

    def visitDataTypeInt(self):
        pass

    def visitFieldData(self, f : dc.Field):
        self._visitDataType(f.type)
        pass

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
