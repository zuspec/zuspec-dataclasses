"""Constraint System Builder - builds complete ConstraintSystem from IR"""

import dataclasses as _dc
import enum as _enum
import typing as _typing

from typing import Dict, List, Optional, Set, Tuple
from zuspec.ir.core.data_type import (
    DataType, DataTypeStruct, DataTypeClass, Function
)
from zuspec.ir.core.stmt import Stmt, StmtExpr, StmtAssert, StmtReturn, StmtFor
from zuspec.ir.core.expr import Expr
from ..core.constraint_system import ConstraintSystem
from ..core.constraint import Constraint, SourceLocation
from ..core.variable import Variable
from ..core.domain import IntDomain, EnumDomain
from .variable_extractor import VariableExtractor
from .ir_parser import IRExpressionParser, ParseError


class BuildError(Exception):
    """Exception raised when building constraint system fails"""
    pass


class _OutputBufferProxy:
    """Thin proxy that exposes an output-buffer payload via ``.t``.

    Installed by :meth:`ConstraintSystemBuilder._extract_output_nested_vars`
    (and :func:`_ensure_output_payloads` in ``_core_solve``) so that
    ``_apply_solution`` can navigate ``obj.out.t.field`` paths that mirror the
    constraint-syntax accessor ``self.out.t.field``.
    """
    __slots__ = ('t',)

    def __init__(self, payload: object) -> None:
        self.t = payload


class ConstraintSystemBuilder:
    """Builds a complete ConstraintSystem from IR structures"""
    
    def __init__(self):
        # The constraint system being built
        self.system = ConstraintSystem()
        
        # Variable extractor
        self.variable_extractor = VariableExtractor()
        
        # Expression parser
        self.expr_parser = IRExpressionParser()
        
        # Bidirectional mapping for error reporting
        # Function name -> List of solver Constraints
        self.func_to_constraint_map: Dict[str, List[Constraint]] = {}
        # Solver Constraint -> IR Expr
        self.constraint_to_ir_map: Dict[Constraint, Expr] = {}
        
        # Track constraint functions
        self.constraint_functions: List[Function] = []
    
    def build_from_struct(
        self,
        struct_type: DataTypeStruct,
        field_metadata: Optional[Dict[str, Dict]] = None,
        obj: object = None,
    ) -> ConstraintSystem:
        """
        Build a complete constraint system from an IR struct/class.
        
        Args:
            struct_type: IR struct/class type
            field_metadata: Optional explicit metadata for fields
            obj: Optional object instance.  When provided, the concrete values
                of non-rand fields are extracted and used to constant-fold
                cross-field references in constraints (e.g. a constraint
                ``self.next_.domain_A == self.prev.domain_A + self.step``
                becomes ``3 == 2 + step`` when *next_* and *prev* are already
                bound flow objects).
            
        Returns:
            Complete ConstraintSystem ready for solving
            
        Raises:
            BuildError: If system cannot be built
        """
        # Reset state
        self.system = ConstraintSystem()
        self.func_to_constraint_map.clear()
        self.constraint_to_ir_map.clear()
        self.constraint_functions.clear()
        
        # Step 1: Extract variables (IR-level rand fields)
        if field_metadata:
            variables = self.variable_extractor.extract_with_metadata(
                struct_type, field_metadata
            )
        else:
            variables = self.variable_extractor.extract_from_struct(struct_type)

        # Step 1a: Also extract rand fields nested inside output buffer payloads
        # (Python-level rand fields invisible to the IR struct).
        nested_vars = (
            self._extract_output_nested_vars(obj, struct_type) if obj is not None else []
        )

        # Step 1b: Synthesize rand id variables for resource_ref fields (e.g. rs1.id).
        resource_id_vars = self._extract_resource_id_vars(obj) if obj is not None else []

        all_variables = list(variables) + nested_vars + resource_id_vars
        if not all_variables:
            raise BuildError("No random variables found in struct")

        # Add variables to system
        for var in all_variables:
            self.system.add_variable(var)
        
        # Copy array metadata from extractor to system
        self.system.array_metadata = self.variable_extractor.array_metadata.copy()
        
        # Register variables in parser
        for var in all_variables:
            self.expr_parser.register_variable(var.name, var)
        
        # Register field index mappings (rand fields from extractor)
        for idx, name in self.variable_extractor.field_index_map.items():
            self.expr_parser.register_field(idx, name)
        
        # Also register non-rand fields by positional index so that constraints
        # referencing bound objects (e.g. flow-in/out) can resolve ExprRefField.
        rand_indexed = set(self.variable_extractor.field_index_map.keys())
        for idx, field in enumerate(struct_type.fields):
            if idx not in rand_indexed:
                self.expr_parser.register_field(idx, field.name)
        
        # Register array field metadata for array indexing support
        self.expr_parser.register_array_fields(self.variable_extractor.array_metadata)
        
        # Step 1b: Register bound values for non-rand fields if obj provided.
        # This allows constraints like ``self.next_.domain_A == self.prev.domain_A
        # + self.step`` to be constant-folded (``3 == 2 + step``) when next_/prev
        # are bound flow objects whose values are already known.
        if obj is not None:
            rand_names = {var.name for var in all_variables}
            self._register_bound_values(obj, struct_type, rand_names)
        
        # Step 2: Extract and parse constraint functions
        self._extract_constraint_functions(struct_type)
        
        # Step 3: Parse constraints and add to system
        for func in self.constraint_functions:
            self._parse_constraint_function(func)
        
        # After parsing: record which lock write variables were actually referenced.
        self.system.referenced_lock_writes = self.expr_parser._referenced_lock_writes.copy()
        
        # Step 4: Validate the system
        self._validate_system()
        
        # Step 5: Compute metadata
        self.system.compute_connected_components()
        
        return self.system
    
    def _register_bound_values(self, obj: object, struct_type, rand_names: set):
        """Extract concrete values from non-rand fields of *obj* and register them
        in the expression parser's bound_values map so constraint parsing can fold
        them to constants.

        Output buffer fields (FieldInOut.is_out=True) are skipped — their payload
        fields are solver variables, not bound constants.  Input buffer fields
        (FieldInOut.is_out=False) are registered under both ``field.name.*`` and
        ``field.name.t.*`` so that ``self.fetch.field`` and ``self.fetch.t.field``
        both resolve correctly in constraints.
        """
        try:
            from zuspec.ir.core.fields import FieldInOut
        except ImportError:
            FieldInOut = None

        for field in struct_type.fields:
            if field.name in rand_names:
                continue  # skip rand fields — they remain solver variables
            if FieldInOut is not None and isinstance(field, FieldInOut) and field.is_out:
                continue  # output fields: payload vars handled separately
            field_val = getattr(obj, field.name, None)
            if field_val is None:
                continue
            self._collect_bound_values(field.name, field_val)
            # Also register under .t.* for input buffer payloads so that
            # ``self.fetch.t.instr`` resolves to the same bound value as
            # ``self.fetch.instr``.
            if (
                FieldInOut is not None
                and isinstance(field, FieldInOut)
                and not field.is_out
                and _dc.is_dataclass(field_val)
                and not isinstance(field_val, type)
            ):
                self._collect_bound_values(f"{field.name}.t", field_val)

    def _extract_output_nested_vars(
        self, obj: object, struct_type
    ) -> List[Variable]:
        """Return solver Variables for rand fields nested inside output-buffer payloads.

        The IR struct only sees top-level fields; Python ``zdc.rand()`` metadata
        on the payload dataclass fields is invisible to the IR.  This method
        walks every output buffer field (FieldInOut.is_out=True), inspects the
        Python dataclass for rand-annotated fields, and creates matching
        Variables whose names use the ``"field.t.subfield"`` dotted path
        that constraints produce via ``self.out.t.subfield`` accessor chains.

        If the field still holds the ``Output()``/``Input()`` marker (i.e. the
        activity runner hasn't bound a payload yet), a fresh default payload
        instance is created and installed so that ``_apply_solution`` can write
        solved values into it after the solve step.
        """
        try:
            from zuspec.ir.core.fields import FieldInOut
        except ImportError:
            return []

        nested: List[Variable] = []
        for field in struct_type.fields:
            if not (isinstance(field, FieldInOut) and field.is_out):
                continue
            payload = getattr(obj, field.name, None)

            # Unwrap an existing proxy so we work with the raw payload.
            if isinstance(payload, _OutputBufferProxy):
                payload = payload.t

            # If the field hasn't been bound to a payload yet (still holds the
            # Output() marker), find the concrete payload type from the Python
            # class annotation and install a fresh default instance.
            if payload is None or not _dc.is_dataclass(payload):
                payload_cls = self._get_buffer_payload_type(obj, field.name)
                if payload_cls is None or not _dc.is_dataclass(payload_cls):
                    continue
                payload = payload_cls()

            # Wrap the payload in a proxy so that obj.out.t.field navigation
            # works during _apply_solution write-back (mirrors constraint syntax).
            setattr(obj, field.name, _OutputBufferProxy(payload))

            payload_cls = type(payload)
            try:
                hints = _typing.get_type_hints(payload_cls, include_extras=True)
            except Exception:
                hints = {}
            for dc_field in _dc.fields(payload_cls):
                annotation = hints.get(dc_field.name)
                if annotation is None:
                    continue
                domain = self._py_annotation_to_domain(annotation)
                if domain is None:
                    continue  # Not a zdc typed field — skip
                var_name = f"{field.name}.t.{dc_field.name}"
                nested.append(Variable(name=var_name, domain=domain))
        return nested

    @staticmethod
    def _get_resource_elem_domain(rf, pool) -> Optional['Domain']:
        """Infer the solver domain for the element type of a lock() resource field.

        Tries to extract ``T`` from a ``Resource[T]`` / ``ClaimPool[T]`` annotation
        on *rf* and calls :meth:`_py_annotation_to_domain`.  Falls back to a 32-bit
        unsigned domain when the annotation is unavailable or unrecognisable.
        """
        import typing
        try:
            args = typing.get_args(rf.type)
            if args:
                domain = ConstraintSystemBuilder._py_annotation_to_domain(args[0])
                if domain is not None:
                    return domain
        except Exception:
            pass
        # Fallback: 32-bit unsigned (covers u32 / bv32 resources)
        return IntDomain([(0, 0xFFFFFFFF)], width=32, signed=False)

    @staticmethod
    def _get_buffer_payload_type(obj: object, field_name: str) -> Optional[type]:
        """Return the payload type T for a ``Buffer[T]`` field on *obj*'s class."""
        obj_cls = type(obj)
        if not _dc.is_dataclass(obj_cls):
            return None
        for f in _dc.fields(obj_cls):
            if f.name != field_name:
                continue
            args = _typing.get_args(f.type)
            if args and isinstance(args[0], type) and _dc.is_dataclass(args[0]):
                return args[0]
        return None

    @staticmethod
    def _py_annotation_to_domain(annotation) -> Optional['Domain']:
        """Convert a Python type annotation to a solver Domain.

        Handles:
        - ``Annotated[int, U(width=N)]`` / ``Annotated[int, S(width=N)]``
          (covers all ``zdc.uN`` / ``zdc.sN`` types)
        - ``bv`` subclasses (e.g. ``zdc.bv32``)
        - ``IntEnum`` subclasses (discrete enum domain)
        """
        from zuspec.dataclasses.types import bv as _bv

        origin = _typing.get_origin(annotation)
        if origin is _typing.Annotated:
            args = _typing.get_args(annotation)
            for arg in args[1:]:
                if hasattr(arg, 'width') and hasattr(arg, 'signed'):
                    bits = arg.width
                    signed = bool(arg.signed)
                    if signed:
                        lo = -(1 << (bits - 1))
                        hi = (1 << (bits - 1)) - 1
                    else:
                        lo = 0
                        hi = (1 << bits) - 1
                    return IntDomain([(lo, hi)], width=bits, signed=signed)
            return None

        if origin is None and isinstance(annotation, type):
            if issubclass(annotation, _bv):
                bits = annotation._width
                return IntDomain([(0, (1 << bits) - 1)], width=bits, signed=False)
            if issubclass(annotation, _enum.IntEnum):
                values = {int(e) for e in annotation}
                return EnumDomain(values, enum_type=annotation)

        return None

    def _collect_bound_values(self, prefix: str, obj: object, depth: int = 0):
        """Recursively collect integer leaf values from *obj* under *prefix*."""
        if depth > 4:
            return  # guard against infinite recursion on cyclic structures
        if isinstance(obj, int):
            self.expr_parser.register_bound_value(prefix, obj)
            return
        if isinstance(obj, bool):
            self.expr_parser.register_bound_value(prefix, int(obj))
            return
        # For composite objects: walk public non-callable attributes.
        # Use __slots__ as fallback for objects without __dict__ (e.g. _OutputBufferProxy).
        try:
            attrs = vars(obj)
        except TypeError:
            # Slotted class — collect slot names from the MRO
            attrs = {}
            for cls in type(obj).__mro__:
                for slot in getattr(cls, '__slots__', ()):
                    if slot not in attrs:
                        attrs[slot] = getattr(obj, slot, None)
        for attr, val in attrs.items():
            if attr.startswith('_'):
                continue
            if val is None:
                continue
            self._collect_bound_values(f"{prefix}.{attr}", val, depth + 1)


    def _extract_resource_id_vars(self, obj: object) -> List[Variable]:
        """Synthesize rand id variables for resource_ref fields on *obj*.

        For each field declared with ``zdc.lock()`` or ``zdc.share()``, the
        pool slot index (``field.id``) is a rand integer that the constraint
        solver can assign.  After solving, the assigned value is written to
        ``obj._zdc_resource_hints[field_name]`` so that ``acquire_resources``
        can filter to the correct pool slot.

        The associated pool is discovered via ``obj.__bind__()``, which is
        called through an :class:`ActionBindProxy` so that ``self.rs1`` returns
        a field-name sentinel rather than ``None``.
        """
        from ..core.variable import VarKind
        from ...action_bind import parse_action_bind
        import math

        result: List[Variable] = []
        try:
            py_fields = _dc.fields(obj)
        except TypeError:
            return result

        resource_fields = [f for f in py_fields if f.metadata.get('kind') == 'resource_ref']
        if not resource_fields:
            return result

        bind_map = parse_action_bind(obj)
        if not bind_map:
            return result

        for rf in resource_fields:
            pool = bind_map.get(rf.name)
            if pool is None:
                continue
            pool_resources = getattr(pool, 'resources', None) or getattr(pool, 'items', None)
            if not pool_resources:
                continue
            pool_size = len(pool_resources)
            var_name = f"{rf.name}.id"
            id_width = max(1, math.ceil(math.log2(pool_size + 1)))
            domain = IntDomain(intervals=[(0, pool_size - 1)], width=id_width, signed=False)
            variable = Variable(name=var_name, domain=domain, kind=VarKind.RAND)
            result.append(variable)
            # Register the pool so the parser can expand field.t to an ITE chain.
            self.expr_parser.register_resource_pool(rf.name, pool)
            # For lock() resources, also create a write-target variable 'field.t'.
            # The solver will assign the new resource value; acquire_resources
            # writes it back to the pool slot after the claim is acquired.
            if rf.metadata.get('claim') == 'lock':
                elem_domain = self._get_resource_elem_domain(rf, pool)
                if elem_domain is not None:
                    write_var = Variable(name=f"{rf.name}.t", domain=elem_domain, kind=VarKind.RAND)
                    result.append(write_var)
                    self.expr_parser.register_lock_field(rf.name)

        return result

    def _extract_constraint_functions(self, struct_type: DataTypeStruct):
        """Extract functions marked as constraints"""
        for func in struct_type.functions:
            # Check if function is marked as constraint
            if self._is_constraint_function(func):
                self.constraint_functions.append(func)
    
    def _is_constraint_function(self, func: Function) -> bool:
        """Check if function is a constraint (and should be injected into solver)."""
        # Skip ensures-role constraints — they are post-conditions checked at runtime
        if func.metadata.get('_constraint_role') == 'ensures':
            return False

        # Check metadata for constraint marker
        if func.metadata.get('_is_constraint', False):
            return True
        
        # Check for is_invariant flag
        if func.is_invariant:
            return True
        
        return False
    
    def _parse_constraint_function(self, func: Function):
        """
        Parse a constraint function and add constraints to system.
        
        Args:
            func: IR Function marked as constraint
        """
        # Track constraints from this function
        func_constraints = []
        
        # Get source location
        source_loc = None
        if func.loc is not None:
            source_loc = SourceLocation(
                file=func.loc.file or "unknown",
                line=func.loc.line,
                column=func.loc.pos
            )
        
        # Parse each statement in function body
        for stmt in func.body:
            try:
                constraints_from_stmt = self._parse_constraint_stmt(stmt, source_loc)
                for constraint in constraints_from_stmt:
                    # Add to system
                    self.system.add_constraint(constraint)
                    func_constraints.append(constraint)
                    
                    # Track mapping for error reporting
                    # Extract the expression from the statement
                    if isinstance(stmt, StmtExpr):
                        self.constraint_to_ir_map[constraint] = stmt.expr
                    elif isinstance(stmt, StmtAssert):
                        self.constraint_to_ir_map[constraint] = stmt.test
                    # For StmtFor, we don't have a single expression
            
            except ParseError as e:
                # Enhance error with function context
                raise BuildError(
                    f"Error parsing constraint in function '{func.name}': {e}"
                ) from e
        
        # Sync witness variables declared inside this constraint into the system.
        # _parse_ann_assign registers them in expr_parser.variable_map but the
        # system.variables dict is populated independently; we must bridge the gap.
        from ..core.variable import VarKind as _VarKind
        for var_name, var in self.expr_parser.variable_map.items():
            if getattr(var, 'kind', None) == _VarKind.WITNESS and var_name not in self.system.variables:
                self.system.add_variable(var)

        # Store mapping
        if func_constraints:
            self.func_to_constraint_map[func.name] = func_constraints
    
    def _parse_constraint_stmt(
        self,
        stmt: Stmt,
        source_loc: Optional[SourceLocation]
    ) -> List[Constraint]:
        """
        Parse a constraint statement.
        
        Args:
            stmt: IR statement
            source_loc: Source location for error reporting
            
        Returns:
            List of parsed constraints (may be empty)
        """
        # Set source location in parser
        self.expr_parser.current_source = source_loc
        
        # Use the parser's statement parsing method (handles loops, etc.)
        return self.expr_parser.parse_statement(stmt)
    
    def _validate_system(self):
        """
        Validate the constraint system.
        
        Raises:
            BuildError: If validation fails
        """
        # Check that we have at least one variable
        if not self.system.variables:
            raise BuildError("No random variables found in system")
        
        # Note: We allow systems with no constraints - this just means
        # we're picking random values from variable domains without additional constraints
        
        # Check that all variables are used in at least one constraint
        # (This is a warning, not an error)
        if self.system.constraints:
            used_vars = set()
            for constraint in self.system.constraints:
                used_vars.update(constraint.variables)
            
            unused_vars = set(self.system.variables.values()) - used_vars
            if unused_vars:
                # Just track for now, might want to warn
                pass
    
    def add_ordering_constraint(
        self,
        before_var_name: str,
        after_var_name: str
    ):
        """
        Add a solve...before ordering constraint.
        
        Args:
            before_var_name: Variable to solve before
            after_var_name: Variable to solve after
            
        Raises:
            BuildError: If variables don't exist or creates circular dependency
        """
        before_var = self.system.get_variable(before_var_name)
        after_var = self.system.get_variable(after_var_name)
        
        if before_var is None:
            raise BuildError(f"Unknown variable: {before_var_name}")
        if after_var is None:
            raise BuildError(f"Unknown variable: {after_var_name}")
        
        try:
            self.system.add_ordering_constraint(before_var, after_var)
        except ValueError as e:
            raise BuildError(str(e)) from e
    
    def get_constraint_source(self, constraint: Constraint) -> Optional[Expr]:
        """
        Get the IR expression that produced a constraint.
        
        Args:
            constraint: Solver constraint
            
        Returns:
            IR expression or None
        """
        return self.constraint_to_ir_map.get(constraint)
    
    def get_function_constraints(self, func_name: str) -> List[Constraint]:
        """
        Get all constraints from a given function by name.
        
        Args:
            func_name: Function name
            
        Returns:
            List of constraints from that function
        """
        return self.func_to_constraint_map.get(func_name, [])
    
    def build_simple(
        self,
        variables: List[Variable],
        constraint_exprs: List[Expr],
        ordering_constraints: Optional[List[Tuple[str, str]]] = None
    ) -> ConstraintSystem:
        """
        Build a simple constraint system from variables and expressions.
        
        This is a convenience method for testing and simple use cases.
        
        Args:
            variables: List of solver variables
            constraint_exprs: List of IR expressions representing constraints
            ordering_constraints: Optional list of (before, after) variable name tuples
            
        Returns:
            Complete ConstraintSystem
            
        Raises:
            BuildError: If system cannot be built
        """
        # Reset state
        self.system = ConstraintSystem()
        self.func_to_constraint_map.clear()
        self.constraint_to_ir_map.clear()
        
        # Add variables
        for var in variables:
            self.system.add_variable(var)
            self.expr_parser.register_variable(var.name, var)
        
        # Parse and add constraints
        for expr in constraint_exprs:
            try:
                constraint = self.expr_parser.parse(expr)
                self.system.add_constraint(constraint)
                self.constraint_to_ir_map[constraint] = expr
            except ParseError as e:
                raise BuildError(f"Error parsing constraint: {e}") from e
        
        # Add ordering constraints
        if ordering_constraints:
            for before, after in ordering_constraints:
                self.add_ordering_constraint(before, after)
        
        # Validate
        if not self.system.constraints:
            raise BuildError("No constraints in system")
        
        # Compute metadata
        self.system.compute_connected_components()
        
        return self.system
