"""
High-level API for constraint solving and randomization.

This module provides the main user-facing API for randomizing
zuspec-dataclasses objects with constraints.
"""

from typing import Any, Dict, Optional, List, Tuple
import ast
import inspect
import sys
import textwrap
from zuspec.ir.core.data_type import DataTypeStruct, DataTypeClass
from .core.constraint_system import ConstraintSystem
from .core.variable import Variable
from .frontend.constraint_system_builder import ConstraintSystemBuilder, BuildError

# Shared implementation helpers and public exception/result types
from ._core_solve import (
    RandomizationError,
    RandomizationResult,
    _extract_struct_type,
    _solve_constraint_system,
    _apply_solution,
)

# Back-end registry — used by randomize()
from .backend.registry import get_backend


def randomize(obj: Any, 
              seed: Optional[int] = None,
              timeout_ms: Optional[int] = 1000) -> None:
    """
    Randomize all rand/randc fields in obj according to its constraints.
    
    This is the main entry point for constraint-based randomization.
    
    Args:
        obj: Object with @dataclass decorator and rand/randc fields.
             The object's class should have @constraint methods defining
             the constraints on random fields.
        seed: Optional random seed for reproducibility. If None, uses
              a random seed. Same seed produces same results.
        timeout_ms: Maximum time in milliseconds to spend solving.
                    Default is 1000ms (1 second). None means no timeout.
    
    Side Effects:
        Updates all rand/randc fields in obj with randomized values.
    
    Example:
        >>> from zuspec.dataclasses import dataclass, rand, constraint, randomize
        >>> 
        >>> @dataclass
        >>> class Packet:
        >>>     addr: rand(domain=(0, 255)) = 0
        >>>     data: rand(domain=(0, 255)) = 0
        >>>     
        >>>     @constraint
        >>>     def word_aligned(self):
        >>>         return self.addr % 4 == 0
        >>> 
        >>> pkt = Packet()
        >>> randomize(pkt, seed=42)
        >>> print(f"Randomized: addr={pkt.addr}, data={pkt.data}")
    
    Raises:
        RandomizationError: If object structure is invalid (no rand fields,
                           malformed constraints, etc.), if no solution exists
                           (UNSAT), or if timeout occurred.
    """
    get_backend().randomize(obj, seed=seed, timeout_ms=timeout_ms)


class _HandleAccessRewriter(ast.NodeTransformer):
    """Rewrite ``self.handle.field`` → ``self.field`` in constraint AST.

    When inline constraints are written inside ``async with self.rd():``, the
    expression ``self.rd.addr > 0`` references the sub-action's field via the
    handle name.  The solver only knows about the sub-action's own fields, so
    we strip the handle level: ``self.rd.addr`` → ``self.addr``.

    For expressions already written as ``rd.addr`` (label form), the
    AstToIrConverter already handles them correctly (ignores the object name
    when the field name is found in the struct), so no rewriting is needed.
    """

    def __init__(self, handle: str) -> None:
        self.handle = handle

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        self.generic_visit(node)
        if (
            isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "self"
            and node.value.attr == self.handle
        ):
            # self.handle.field → self.field
            return ast.Attribute(
                value=ast.Name(id="self", ctx=ast.Load()),
                attr=node.attr,
                ctx=node.ctx,
            )
        return node


def randomize_with_ast_constraints(
    obj: Any,
    stmts: List[ast.stmt],
    handle: Optional[str] = None,
    seed: Optional[int] = None,
    timeout_ms: int = 1000,
) -> None:
    """Randomize *obj* with pre-parsed AST constraint statements.

    Used by the activity runtime to apply ``async with self.handle():`` and
    ``with do(Type) as label:`` inline constraints collected by the activity
    parser (which now stores raw ``ast.stmt`` nodes).

    Args:
        obj: Action instance to randomize.
        stmts: Raw AST statements from the constraint body (assert / bare expr).
        handle: Handle or label name to strip from ``self.handle.field``
                references.  If *None* no rewriting is performed.
        seed: Random seed passed to the solver.
        timeout_ms: Solver timeout in milliseconds.
    """
    import copy

    if handle:
        rewriter = _HandleAccessRewriter(handle)
        rewritten: List[ast.stmt] = []
        for s in stmts:
            s2 = rewriter.visit(copy.deepcopy(s))
            ast.fix_missing_locations(s2)
            rewritten.append(s2)
        stmts = rewritten

    ctx = RandomizeWithContext(obj, seed, timeout_ms)
    ctx.inline_constraints = stmts
    try:
        ctx._randomize_with_constraints()
    except RandomizationError:
        raise
    except Exception as exc:
        raise RandomizationError(f"Randomization with constraints failed: {exc}") from exc


def randomize_with(obj: Any,
                   seed: Optional[int] = None,
                   timeout_ms: Optional[int] = 1000):
    """
    Context manager for randomization with inline constraints.
    
    This function returns a context manager that allows you to specify
    additional constraints at the call site using assert statements or
    control flow (if/for).
    
    Similar to SystemVerilog: obj.randomize() with { constraint_expr; }
    
    Args:
        obj: Object to randomize (must have rand/randc fields)
        seed: Optional random seed for reproducibility
        timeout_ms: Timeout in milliseconds
        
    Returns:
        RandomizeWithContext: Context manager for constraint specification
        
    Example:
        >>> from zuspec.dataclasses import dataclass, rand, randomize_with
        >>> 
        >>> @dataclass
        >>> class Packet:
        >>>     addr: rand(domain=(0, 65535)) = 0
        >>>     data: rand(domain=(0, 255)) = 0
        >>> 
        >>> pkt = Packet()
        >>> with randomize_with(pkt, seed=42):
        >>>     assert pkt.addr > 0x1000
        >>>     assert pkt.data < 128
        >>> 
        >>> print(f"addr=0x{pkt.addr:04x}, data={pkt.data}")
        
    Control Flow:
        >>> with randomize_with(pkt):
        >>>     if pkt.mode == 1:
        >>>         assert pkt.addr > 0x8000
        >>>     else:
        >>>         assert pkt.addr < 0x1000
        >>>     
        >>>     for i in range(4):
        >>>         assert pkt.buffer[i] < 64
    
    Raises:
        RandomizationError: If constraints are unsatisfiable or parsing fails
    """
    return RandomizeWithContext(obj, seed, timeout_ms)


class RandomizeWithContext:
    """Context manager for inline constraint specification.
    
    This class implements the context manager protocol to allow users
    to specify additional constraints at the call site using assert
    statements and control flow.
    
    The implementation parses the with block from source code before
    it executes, extracting constraints from:
    - assert statements: `assert pkt.addr > 0x1000`
    - bare expressions: `pkt.data < 128`  (legacy support)
    - if/elif/else: converted to implies() constraints
    - for loops: converted to forall constraints
    """
    
    # Cache parsed AST by (filename, lineno) for performance
    _ast_cache: Dict[Tuple[str, int], List[ast.stmt]] = {}
    
    def __init__(self, obj: Any, seed: Optional[int] = None, 
                 timeout_ms: Optional[int] = 1000):
        """Initialize context manager.
        
        Args:
            obj: Object to randomize
            seed: Optional random seed
            timeout_ms: Solver timeout in milliseconds
        """
        self.obj = obj
        self.seed = seed
        self.timeout_ms = timeout_ms
        self.inline_constraints = []
        self.frame = None
        
    def __enter__(self):
        """Parse constraints from with block before execution.
        
        This method is called before the with block body executes.
        We parse the with block from source to extract constraints.
        """
        # Get the calling frame
        self.frame = sys._getframe(1)
        
        # Parse the with block from source
        try:
            self.inline_constraints = self._parse_with_block()
        except Exception as e:
            raise RandomizationError(
                f"Failed to parse inline constraints: {e}"
            )
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Execute randomization with inline constraints.
        
        This method is called after the with block body executes.
        We suppress any exceptions that occurred during parsing
        (like AssertionError from assert statements that fail because
        fields aren't assigned yet, or TypeError from accessing arrays).
        """
        # Suppress expected exceptions from accessing uninitialized fields
        # - AssertionError: from assert statements
        # - TypeError: from array subscripting (obj.arr[i] where arr is still 0)
        # - AttributeError: from accessing nested objects
        # - IndexError: from accessing out of bounds
        if exc_type in (AssertionError, TypeError, AttributeError, IndexError):
            pass  # Expected - fields not yet assigned
        elif exc_type is not None:
            return False  # Propagate other exceptions
        
        # Now solve with inline constraints
        try:
            self._randomize_with_constraints()
        except RandomizationError:
            raise
        except Exception as e:
            raise RandomizationError(f"Randomization failed: {e}")
        
        # Suppress expected exceptions
        return exc_type in (AssertionError, TypeError, AttributeError, IndexError)
    
    def _parse_with_block(self) -> List[ast.stmt]:
        """Parse with block from source code.
        
        Returns:
            List of AST statements from the with block body
        """
        filename = self.frame.f_code.co_filename
        lineno = self.frame.f_lineno
        
        # Check cache
        cache_key = (filename, lineno)
        if cache_key in self._ast_cache:
            return self._ast_cache[cache_key]
        
        # Read source file
        try:
            with open(filename, 'r') as f:
                source = f.read()
        except Exception as e:
            raise RandomizationError(
                f"Cannot read source file {filename}: {e}. "
                f"Inline constraints require access to source code."
            )
        
        # Parse to AST
        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError as e:
            raise RandomizationError(f"Failed to parse {filename}: {e}")
        
        # Find the with statement at lineno
        with_stmt = self._find_with_statement(tree, lineno)
        if with_stmt is None:
            raise RandomizationError(
                f"Cannot find 'with' statement at {filename}:{lineno}"
            )
        
        # Extract body statements
        statements = with_stmt.body
        
        # Cache for future calls
        self._ast_cache[cache_key] = statements
        
        return statements
    
    def _find_with_statement(self, tree: ast.AST, lineno: int) -> Optional[ast.With]:
        """Find the With statement at the given line number.
        
        Args:
            tree: AST tree to search
            lineno: Line number to find
            
        Returns:
            ast.With statement or None
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.With) and node.lineno == lineno:
                return node
        return None
    
    def _randomize_with_constraints(self):
        """Execute randomization with inline constraints."""
        # Get the IR struct type
        struct_type = _extract_struct_type(self.obj)
        
        # Build constraint system from class constraints
        builder = ConstraintSystemBuilder()
        constraint_system = builder.build_from_struct(struct_type)
        
        # Add inline constraints to the system
        self._add_inline_constraints(constraint_system, struct_type)
        
        # Solve
        result = _solve_constraint_system(constraint_system, self.seed, self.timeout_ms)
        
        if result.success:
            # Apply solution
            _apply_solution(self.obj, result.assignment, constraint_system)
        else:
            raise RandomizationError(
                f"No solution found with inline constraints: {result.error}"
            )
    
    def _add_inline_constraints(self, constraint_system: ConstraintSystem,
                                struct_type: DataTypeStruct):
        """Add parsed inline constraints to the constraint system.
        
        Args:
            constraint_system: System to add constraints to
            struct_type: IR struct type for context
        """
        from zuspec.ir.core.data_type import Function
        from zuspec.ir.core.stmt import StmtExpr, StmtAssert, StmtReturn
        from .frontend.ast_to_ir_converter import AstToIrConverter
        
        # Create converter to translate AST -> IR
        converter = AstToIrConverter(struct_type)
        
        # Process each statement and create a Function for each constraint
        for i, stmt in enumerate(self.inline_constraints):
            ir_function = self._convert_statement_to_function(stmt, converter, i)
            if ir_function:
                # Parse the function as a constraint using constraint_system_builder
                # For now, directly add constraint statements to the builder's parsing
                # We'll parse the function body directly
                self._parse_inline_constraint_function(ir_function, constraint_system)
    
    def _parse_inline_constraint_function(self, func: 'Function', system: ConstraintSystem):
        """Parse an inline constraint function and add to system.
        
        This mirrors the logic in ConstraintSystemBuilder._parse_constraint_function
        but for inline constraints.
        """
        from .frontend.ir_parser import IRExpressionParser
        from zuspec.ir.core.stmt import StmtExpr, StmtAssert, StmtReturn, StmtFor
        
        # Create parser
        parser = IRExpressionParser()
        
        # Register variables
        for var_name, var in system.variables.items():
            parser.register_variable(var_name, var)
        
        # Register array fields
        parser.register_array_fields(system.array_metadata)
        
        # Parse each statement in function body using parse_statement
        # This now handles loops, if statements, etc.
        for stmt in func.body:
            try:
                constraints = parser.parse_statement(stmt)
                for constraint in constraints:
                    system.constraints.append(constraint)
            
            except Exception as e:
                import warnings
                warnings.warn(f"Failed to parse inline constraint: {e}")
    
    def _convert_statement_to_function(self, stmt: ast.stmt, converter, index: int):
        """Convert a single AST statement to IR Function.
        
        Args:
            stmt: AST statement
            converter: AstToIrConverter instance
            index: Statement index (for naming)
            
        Returns:
            IR Function or None
        """
        from zuspec.ir.core.data_type import Function
        from zuspec.ir.core.stmt import StmtExpr, StmtAssert
        
        # Create function with single statement body
        body = []
        
        # Handle assert statement
        if isinstance(stmt, ast.Assert):
            expr_ir = converter.convert_expr(stmt.test)
            body.append(StmtAssert(test=expr_ir))
        
        # Handle bare expression
        elif isinstance(stmt, ast.Expr):
            # Skip docstrings
            if isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                return None
            
            expr_ir = converter.convert_expr(stmt.value)
            body.append(StmtExpr(expr=expr_ir))
        
        # Handle if statement (convert to implies)
        elif isinstance(stmt, ast.If):
            # Convert if statement to implies constraints
            if_function = self._convert_if_to_function(stmt, converter, index)
            return if_function
        
        # Handle for loop (expand or convert to forall)
        elif isinstance(stmt, ast.For):
            # Convert for loop constraints
            for_function = self._convert_for_to_function(stmt, converter, index)
            return for_function
        
        # Unsupported statement type
        else:
            import warnings
            warnings.warn(
                f"Unsupported statement type in inline constraints: {type(stmt).__name__}. "
                f"Only assert, expressions, if, and for are supported."
            )
            return None
        
        if body:
            return Function(
                name=f"inline_{index}",
                body=body,
                metadata={'_is_constraint': True, '_is_inline': True}
            )
        return None
    
    def _convert_if_to_function(self, if_stmt: ast.If, converter, index: int):
        """Convert if statement to Function with implies constraints."""
        from zuspec.ir.core.data_type import Function
        from zuspec.ir.core.stmt import StmtExpr
        from zuspec.ir.core.expr import ExprCall, ExprAttribute
        
        body = []
        
        # Helper to process constraint statements in a branch
        def extract_branch_exprs(stmts):
            exprs = []
            for stmt in stmts:
                if isinstance(stmt, ast.Assert):
                    exprs.append(converter.convert_expr(stmt.test))
                elif isinstance(stmt, ast.Expr):
                    if not (isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str)):
                        exprs.append(converter.convert_expr(stmt.value))
            return exprs
        
        # Process if branch: condition.implies(body_expr)
        condition_ir = converter.convert_expr(if_stmt.test)
        if_body_exprs = extract_branch_exprs(if_stmt.body)
        
        for expr in if_body_exprs:
            # Create condition.implies(expr)
            implies_call = ExprCall(
                func=ExprAttribute(value=condition_ir, attr='implies'),
                args=[expr]
            )
            body.append(StmtExpr(expr=implies_call))
        
        # Process elif/else branches
        current = if_stmt
        while current.orelse:
            if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                # elif branch
                elif_stmt = current.orelse[0]
                elif_condition = converter.convert_expr(elif_stmt.test)
                elif_body_exprs = extract_branch_exprs(elif_stmt.body)
                
                for expr in elif_body_exprs:
                    # Create elif_condition.implies(expr)
                    implies_call = ExprCall(
                        func=ExprAttribute(value=elif_condition, attr='implies'),
                        args=[expr]
                    )
                    body.append(StmtExpr(expr=implies_call))
                
                current = elif_stmt
            else:
                # else branch - add as unconditional constraints
                else_exprs = extract_branch_exprs(current.orelse)
                for expr in else_exprs:
                    body.append(StmtExpr(expr=expr))
                break
        
        if body:
            return Function(
                name=f"inline_if_{index}",
                body=body,
                metadata={'_is_constraint': True, '_is_inline': True}
            )
        return None
    
    def _convert_for_to_function(self, for_stmt: ast.For, converter, index: int):
        """Convert for loop to Function with IR StmtFor (for IR parser to expand)."""
        from zuspec.ir.core.data_type import Function
        from zuspec.ir.core.stmt import StmtFor, StmtAssert, StmtExpr
        
        # Manually build IR StmtFor from AST for loop
        try:
            # Convert target (loop variable)
            target_ir = converter.convert_expr(for_stmt.target)
            
            # Convert iterator (e.g., range(...))
            iter_ir = converter.convert_expr(for_stmt.iter)
            
            # Convert body statements
            body_ir = []
            for stmt in for_stmt.body:
                if isinstance(stmt, ast.Assert):
                    body_ir.append(StmtAssert(test=converter.convert_expr(stmt.test)))
                elif isinstance(stmt, ast.For):
                    # Nested for loop
                    nested_target = converter.convert_expr(stmt.target)
                    nested_iter = converter.convert_expr(stmt.iter)
                    nested_body = []
                    for nested_stmt in stmt.body:
                        if isinstance(nested_stmt, ast.Assert):
                            nested_body.append(StmtAssert(test=converter.convert_expr(nested_stmt.test)))
                        elif isinstance(nested_stmt, ast.Expr):
                            if not (isinstance(nested_stmt.value, ast.Constant) and isinstance(nested_stmt.value.value, str)):
                                nested_body.append(StmtExpr(expr=converter.convert_expr(nested_stmt.value)))
                    body_ir.append(StmtFor(target=nested_target, iter=nested_iter, body=nested_body))
                elif isinstance(stmt, ast.Expr):
                    if not (isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str)):
                        body_ir.append(StmtExpr(expr=converter.convert_expr(stmt.value)))
            
            # Create IR StmtFor
            ir_for = StmtFor(
                target=target_ir,
                iter=iter_ir,
                body=body_ir
            )
            
            return Function(
                name=f"inline_for_{index}",
                body=[ir_for],
                metadata={'_is_constraint': True, '_is_inline': True}
            )
            
        except Exception as e:
            import warnings
            warnings.warn(f"Failed to convert for loop to IR: {e}")
            return None
    
    


# Export public API
__all__ = [
    'randomize',
    'randomize_with',
    'RandomizationError',
    'RandomizationResult',
]
