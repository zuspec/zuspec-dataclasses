from typing import Callable, Optional, Type, Dict, Any, List, Tuple
from mypy.plugin import Plugin, FunctionContext, ClassDefContext, MethodContext
from mypy.types import Type as MypyType, CallableType, Instance
from mypy.nodes import (
    NameExpr, FuncDef, ClassDef, Block, ReturnStmt, DictExpr, 
    MemberExpr, CallExpr, AssignmentStmt, SymbolTableNode, Var,
    Expression, IntExpr, StrExpr, FloatExpr, TypeInfo, Decorator
)


def _import_profile_checker():
    """Lazy import to avoid circular dependencies."""
    try:
        from zuspec.dataclasses.profiles import ProfileChecker, DEFAULT_PROFILE
        return ProfileChecker, DEFAULT_PROFILE
    except ImportError:
        return None, None


class ZuspecPlugin(Plugin):
    def __init__(self, options):
        super().__init__(options)
        self._profile_cache: Dict[str, Any] = {}  # Cache profile checkers by class fullname
    def get_function_hook(self, fullname: str) -> Optional[Callable[[FunctionContext], MypyType]]:
        if fullname in (
            'zuspec.dataclasses.decorators.comb',
            'zuspec.dataclasses.decorators.process',
            'zuspec.dataclasses.decorators.sync',
            'zuspec.dataclasses.comb',
            'zuspec.dataclasses.process',
            'zuspec.dataclasses.sync'
        ):
            return self.check_process_decorator
        # Check for dynamic attribute access functions
        if fullname in ('builtins.hasattr', 'builtins.getattr', 'builtins.setattr', 'builtins.delattr'):
            return self.check_dynamic_function_call
        return None

    def get_method_signature_hook(self, fullname: str) -> Optional[Callable]:
        # Hook for checking method signatures after they are decorated
        return None

    def get_class_decorator_hook(self, fullname: str) -> Optional[Callable[[ClassDefContext], None]]:
        if fullname in (
            'zuspec.dataclasses.decorators.dataclass',
            'zuspec.dataclasses.dataclass'
        ):
            return self.check_dataclass_with_profile
        return None

    def check_dataclass_with_profile(self, ctx: ClassDefContext) -> None:
        """Check dataclass according to its profile."""
        # Get profile checker for this class
        profile_checker = self._get_profile_checker(ctx)
        
        if profile_checker is not None:
            # Run profile-specific class check
            if hasattr(profile_checker, 'check_class'):
                try:
                    profile_checker.check_class(ctx)
                except Exception:
                    pass  # Silently ignore to avoid crashing mypy
            
            # Check each field type
            # We need to check the original annotations from the AST
            for stmt in ctx.cls.defs.body:
                if isinstance(stmt, AssignmentStmt):
                    for lval in stmt.lvalues:
                        if isinstance(lval, NameExpr):
                            field_name = lval.name
                            # Get the raw type expression from the statement
                            # This is the UnboundType before resolution
                            raw_type_expr = stmt.unanalyzed_type if hasattr(stmt, 'unanalyzed_type') else stmt.type
                            
                            if raw_type_expr is not None and hasattr(profile_checker, 'check_field_type'):
                                try:
                                    # Pass both the raw expression and the assignment statement
                                    profile_checker.check_field_type(
                                        field_name,
                                        raw_type_expr,
                                        ctx,
                                        stmt
                                    )
                                except Exception:
                                    pass  # Silently ignore to avoid crashing mypy

                            # Profile-specific checks for zdc.field(...) arguments
                            if isinstance(stmt.rvalue, CallExpr) and hasattr(profile_checker, 'check_field_default_factory'):
                                try:
                                    call = stmt.rvalue
                                    callee_name = None
                                    if isinstance(call.callee, NameExpr):
                                        callee_name = call.callee.name
                                    elif isinstance(call.callee, MemberExpr):
                                        callee_name = call.callee.name

                                    if callee_name == 'field':
                                        for i, arg_name in enumerate(call.arg_names):
                                            if arg_name == 'default_factory':
                                                profile_checker.check_field_default_factory(
                                                    field_name,
                                                    call.args[i],
                                                    ctx,
                                                    stmt
                                                )
                                except Exception:
                                    pass
            
            # Check methods
            for stmt in ctx.cls.defs.body:
                func = None
                if isinstance(stmt, Decorator):
                    func = stmt.func
                elif isinstance(stmt, FuncDef):
                    func = stmt
                
                if func and hasattr(profile_checker, 'check_method'):
                    try:
                        profile_checker.check_method(func, ctx)
                    except Exception as e:
                        pass  # Silently ignore to avoid crashing mypy
        
        # Always run existing bind checks (these apply to all profiles)
        self.check_dataclass_bind(ctx)

    def _get_profile_checker(self, ctx: ClassDefContext) -> Optional[Any]:
        """Extract and cache profile checker for a class."""
        class_fullname = ctx.cls.fullname
        
        if class_fullname in self._profile_cache:
            return self._profile_cache[class_fullname]
        
        # Try to determine profile from decorator call
        profile_checker = self._extract_profile_from_decorator(ctx)
        
        # Cache and return
        self._profile_cache[class_fullname] = profile_checker
        return profile_checker
    
    def _extract_profile_from_decorator(self, ctx: ClassDefContext) -> Optional[Any]:
        """Extract profile parameter from @dataclass decorator."""
        # Look for the decorator in the class
        for decorator in ctx.cls.decorators:
            if isinstance(decorator, CallExpr):
                # Check if this is @dataclass(...) call
                callee_name = None
                if isinstance(decorator.callee, NameExpr):
                    callee_name = decorator.callee.fullname
                elif isinstance(decorator.callee, MemberExpr):
                    callee_name = decorator.callee.fullname
                
                if callee_name in ('zuspec.dataclasses.dataclass', 'zuspec.dataclasses.decorators.dataclass'):
                    # Look for 'profile' keyword argument
                    for i, arg_name in enumerate(decorator.arg_names):
                        if arg_name == 'profile':
                            profile_arg = decorator.args[i]
                            # Try to resolve profile type
                            return self._resolve_profile_checker(profile_arg, ctx)
        
        # No profile specified, use default
        _, DEFAULT_PROFILE = _import_profile_checker()
        if DEFAULT_PROFILE:
            return DEFAULT_PROFILE.get_checker()
        return None
    
    def _resolve_profile_checker(self, profile_expr: Expression, ctx: ClassDefContext) -> Optional[Any]:
        """Resolve profile expression to a checker instance."""
        if isinstance(profile_expr, (NameExpr, MemberExpr)):
            # Get the full name of the profile
            profile_fullname = None
            if isinstance(profile_expr, NameExpr):
                profile_fullname = profile_expr.fullname
            elif isinstance(profile_expr, MemberExpr):
                # Build fullname from member expression
                parts = []
                expr = profile_expr
                while isinstance(expr, MemberExpr):
                    parts.append(expr.name)
                    expr = expr.expr
                if isinstance(expr, NameExpr):
                    parts.append(expr.fullname if expr.fullname else expr.name)
                parts.reverse()
                profile_fullname = '.'.join(parts)
            
            if profile_fullname:
                # Extract profile class name
                profile_name = profile_fullname.split('.')[-1]
                
                # Try to import and get the profile
                try:
                    from zuspec.dataclasses.profiles import PROFILE_REGISTRY
                    
                    if profile_name in PROFILE_REGISTRY:
                        profile_cls = PROFILE_REGISTRY[profile_name]
                        return profile_cls.get_checker()
                except ImportError:
                    pass
        
        # Default fallback
        _, DEFAULT_PROFILE = _import_profile_checker()
        if DEFAULT_PROFILE:
            return DEFAULT_PROFILE.get_checker()
        return None

    def check_dynamic_function_call(self, ctx: FunctionContext) -> MypyType:
        """Check if dynamic attribute access is allowed in current profile.
        
        This is called for hasattr, getattr, setattr, delattr function calls.
        """
        # Try to find what profile applies to the current context
        # For now, we check all dynamic calls with a generic warning
        # since we don't have easy access to the enclosing class context
        
        # Get function name from the context
        callee = ctx.context
        if isinstance(callee, CallExpr) and isinstance(callee.callee, NameExpr):
            func_name = callee.callee.name
            
            # Get current class context if available
            # This is difficult in function context, so we'll apply profile checking
            # when we can determine the class
            
            # For now, return default type
            # Profile-specific checking will happen in check_method_call hook
        
        return ctx.default_return_type

    def check_process_decorator(self, ctx: FunctionContext) -> MypyType:
        arg_types = ctx.arg_types
        if not arg_types or not arg_types[0]:
            return ctx.default_return_type
        
        func_type = arg_types[0][0]
        if isinstance(func_type, CallableType):
             # Process methods should not have arguments other than 'self'
             # We allow 1 argument (assumed to be self) or 0 arguments (if static/function)
             if len(func_type.arg_types) > 1:
                 ctx.api.fail(f"Process method should not have arguments other than 'self'", ctx.context)
             
             # Check for unannotated variables in the function body
             # Get the function definition from the first argument
             if ctx.args and ctx.args[0]:
                 arg = ctx.args[0][0]
                 if isinstance(arg, Decorator):
                     func_def = arg.func
                 elif isinstance(arg, NameExpr) and isinstance(arg.node, Decorator):
                     func_def = arg.node.func
                 elif isinstance(arg, NameExpr) and isinstance(arg.node, FuncDef):
                     func_def = arg.node
                 else:
                     func_def = None
                 
                 if func_def and isinstance(func_def, FuncDef):
                     self.check_unannotated_variables(func_def, ctx)
        
        return ctx.default_return_type

    def check_unannotated_variables(self, func_def: FuncDef, ctx: FunctionContext) -> None:
        """Check for unannotated variable assignments in the function body."""
        if not func_def.body:
            return
        
        self._check_block_for_unannotated(func_def.body, ctx)
    
    def _check_block_for_unannotated(self, block: Block, ctx: FunctionContext) -> None:
        """Recursively check a block for unannotated variables."""
        for stmt in block.body:
            if isinstance(stmt, AssignmentStmt):
                # Check if this is a simple variable assignment without annotation
                if stmt.type is None and not stmt.new_syntax:
                    # This is an unannotated assignment
                    for lval in stmt.lvalues:
                        if isinstance(lval, NameExpr):
                            # Skip if it's assigning to self.something (field access)
                            if isinstance(stmt.rvalue, MemberExpr):
                                continue
                            # Warn about unannotated variable
                            ctx.api.fail(
                                f"Variable '{lval.name}' is not type-annotated. "
                                f"Zuspec may not be able to identify the desired type",
                                stmt,
                                code="var-annotated"
                            )

    def check_method_for_unannotated_variables(self, func_def: FuncDef, ctx: ClassDefContext) -> None:
        """Check for unannotated variable assignments in a method body."""
        if not func_def.body:
            return
        
        # Get profile checker to determine if annotation is required
        profile_checker = self._get_profile_checker(ctx)
        
        try:
            self._check_method_block_for_unannotated(func_def.body, ctx, profile_checker)
        except Exception:
            # Silently ignore errors to avoid crashing mypy
            pass
    
    def _check_method_block_for_unannotated(self, block: Block, ctx: ClassDefContext, profile_checker: Optional[Any] = None) -> None:
        """Recursively check a block for unannotated variables."""
        for stmt in block.body:
            if isinstance(stmt, AssignmentStmt):
                # Check if this is a simple variable assignment without annotation
                if stmt.type is None:
                    # This is an unannotated assignment
                    for lval in stmt.lvalues:
                        if isinstance(lval, NameExpr):
                            # This is a local variable assignment
                            # Use profile checker if available
                            if profile_checker and hasattr(profile_checker, 'check_variable_annotation'):
                                try:
                                    profile_checker.check_variable_annotation(lval.name, None, stmt.rvalue, ctx)
                                except Exception:
                                    pass
                            else:
                                # Default behavior - just warn
                                ctx.api.fail(
                                    f"Variable '{lval.name}' is not type-annotated. "
                                    f"Zuspec may not be able to identify the desired type",
                                    stmt
                                )
                        elif isinstance(lval, MemberExpr):
                            # Skip self.something assignments (field assignments)
                            continue

    def check_dataclass_bind(self, ctx: ClassDefContext) -> None:
        # Store field kinds in TypeInfo.metadata for later use
        # This helps when the class is imported and AST is not fully available
        if not ctx.cls.info.metadata.get('zuspec_fields'):
            field_kinds = {}
            for stmt in ctx.cls.defs.body:
                if isinstance(stmt, AssignmentStmt):
                    for lval in stmt.lvalues:
                        if isinstance(lval, NameExpr):
                            if isinstance(stmt.rvalue, CallExpr):
                                call = stmt.rvalue
                                if isinstance(call.callee, (NameExpr, MemberExpr)):
                                    callee_name = ""
                                    if isinstance(call.callee, NameExpr):
                                        callee_name = call.callee.name
                                    elif isinstance(call.callee, MemberExpr):
                                        callee_name = call.callee.name
                                    
                                    kind = 'component'
                                    if callee_name == 'input':
                                        kind = 'input'
                                    elif callee_name == 'output':
                                        kind = 'output'
                                    elif callee_name == 'port':
                                        kind = 'port'
                                    elif callee_name == 'export':
                                        kind = 'export'
                                    elif callee_name == 'field':
                                        # Check arguments for default_factory=Input/Output
                                        for i, arg_name in enumerate(call.arg_names):
                                            if arg_name == 'default_factory':
                                                arg_val = call.args[i]
                                                if isinstance(arg_val, NameExpr):
                                                    if arg_val.name == 'Input':
                                                        kind = 'input'
                                                    if arg_val.name == 'Output':
                                                        kind = 'output'
                                    
                                    field_kinds[lval.name] = kind
            
            ctx.cls.info.metadata['zuspec_fields'] = field_kinds

        # Check methods decorated with @process, @comb, or @sync for unannotated variables
        for stmt in ctx.cls.defs.body:
            if isinstance(stmt, Decorator):
                # Check if this is decorated with process, comb, or sync
                is_process_like = False
                for dec in stmt.decorators:
                    dec_name = None
                    if isinstance(dec, NameExpr):
                        dec_name = dec.name
                    elif isinstance(dec, MemberExpr):
                        dec_name = dec.name
                    elif isinstance(dec, CallExpr):
                        if isinstance(dec.callee, NameExpr):
                            dec_name = dec.callee.name
                        elif isinstance(dec.callee, MemberExpr):
                            dec_name = dec.callee.name
                    
                    # Check for process, comb, or sync decorators
                    if dec_name in ('process', 'comb', 'sync'):
                        is_process_like = True
                        break
                
                if is_process_like and isinstance(stmt.func, FuncDef):
                    self.check_method_for_unannotated_variables(stmt.func, ctx)

        # Find __bind__ method
        bind_method = None
        for stmt in ctx.cls.defs.body:
            if isinstance(stmt, FuncDef) and stmt.name == '__bind__':
                bind_method = stmt
                break
        
        if not bind_method:
            return

        # Inspect __bind__ body for return statement
        return_stmt = None
        for stmt in bind_method.body.body:
            if isinstance(stmt, ReturnStmt):
                return_stmt = stmt
                break
        
        if not return_stmt or not isinstance(return_stmt.expr, DictExpr):
            return

        # Check each bind pair
        for key, value in return_stmt.expr.items:
            lhs_kind = self.get_expr_kind(key, ctx)
            rhs_kind = self.get_expr_kind(value, ctx)
            
            if lhs_kind == 'unknown' or rhs_kind == 'unknown':
                continue

            valid = False
            # Valid: input:input, input:output, output:input, port:export, export:port, input:const, const:input
            valid_pairs = {
                ('input', 'input'),
                ('input', 'output'),
                ('output', 'input'),
                ('port', 'export'),
                ('export', 'port'),
                ('input', 'const'),
                ('const', 'input')
            }
            
            if (lhs_kind, rhs_kind) in valid_pairs:
                valid = True
            
            if not valid:
                ctx.api.fail(f"Invalid bind: {lhs_kind} cannot be bound to {rhs_kind}", key)

    def get_expr_kind(self, expr: Expression, ctx: ClassDefContext) -> str:
        if isinstance(expr, (IntExpr, StrExpr, FloatExpr)):
            return 'const'
        
        if isinstance(expr, MemberExpr):
            # Resolve the base
            if isinstance(expr.expr, NameExpr) and expr.expr.name == 'self':
                return self.get_field_kind(ctx.cls.info, expr.name, ctx)
            
            if isinstance(expr.expr, MemberExpr):
                # Recursively find the type of the base
                base_type_fullname = self.get_expr_type_fullname(expr.expr, ctx)
                if base_type_fullname:
                    # Look up the class
                    inst = ctx.api.named_type(base_type_fullname)
                    if inst and isinstance(inst, Instance):
                        return self.get_field_kind(inst.type, expr.name, ctx)
        
        return 'unknown'

    def get_expr_type_fullname(self, expr: Expression, ctx: ClassDefContext) -> Optional[str]:
        if isinstance(expr, NameExpr) and expr.name == 'self':
            return ctx.cls.fullname
            
        if isinstance(expr, MemberExpr):
            base_fullname = self.get_expr_type_fullname(expr.expr, ctx)
            if base_fullname:
                inst = ctx.api.named_type(base_fullname)
                if inst and isinstance(inst, Instance):
                    type_info = inst.type
                    # Look up member in type_info
                    sym = type_info.get(expr.name)
                    if sym and isinstance(sym.node, Var):
                        # Get the type of the var
                        if isinstance(sym.node.type, Instance):
                            return sym.node.type.type.fullname
        return None

    def get_field_kind(self, type_info: Any, field_name: str, ctx: ClassDefContext) -> str:
        # type_info should be TypeInfo (mypy.nodes.TypeInfo)
        # We need to find the assignment statement for this field in the class body
        
        # Iterate over MRO to find the field definition
        for base in type_info.mro:
            if not base.defn: continue
            
            for stmt in base.defn.defs.body:
                if isinstance(stmt, AssignmentStmt):
                    # Check if this assignment is for our field
                    for lval in stmt.lvalues:
                        if isinstance(lval, NameExpr) and lval.name == field_name:
                            # Found the assignment. Check RHS.
                            if isinstance(stmt.rvalue, CallExpr):
                                call = stmt.rvalue
                                if isinstance(call.callee, (NameExpr, MemberExpr)):
                                    callee_name = ""
                                    if isinstance(call.callee, NameExpr):
                                        callee_name = call.callee.name
                                    elif isinstance(call.callee, MemberExpr):
                                        callee_name = call.callee.name
                                    
                                    if callee_name == 'input':
                                        return 'input'
                                    if callee_name == 'output':
                                        return 'output'
                                    if callee_name == 'port':
                                        return 'port'
                                    if callee_name == 'export':
                                        return 'export'
                                    if callee_name == 'field':
                                        # Check arguments for default_factory=Input/Output
                                        for i, arg_name in enumerate(call.arg_names):
                                            if arg_name == 'default_factory':
                                                arg_val = call.args[i]
                                                if isinstance(arg_val, NameExpr):
                                                    if arg_val.name == 'Input':
                                                        return 'input'
                                                    if arg_val.name == 'Output':
                                                        return 'output'
                                        return 'component' # Default field is component/field
                            return 'component' # Assignment without call or unknown call
        
        return 'unknown'

    def get_expr_type_fullname(self, expr: Expression, ctx: ClassDefContext) -> Optional[str]:
        if isinstance(expr, NameExpr) and expr.name == 'self':
            return ctx.cls.fullname
            
        if isinstance(expr, MemberExpr):
            base_fullname = self.get_expr_type_fullname(expr.expr, ctx)
            if base_fullname:
                try:
                    inst = ctx.api.named_type(base_fullname)
                    if inst and isinstance(inst, Instance):
                        type_info = inst.type
                        # Look up member in type_info
                        sym = type_info.get(expr.name)
                        if sym and isinstance(sym.node, Var):
                            # Get the type of the var
                            if isinstance(sym.node.type, Instance):
                                return sym.node.type.type.fullname
                except:
                    pass
        return None

    def get_field_kind(self, type_info: Any, field_name: str, ctx: ClassDefContext) -> str:
        # type_info should be TypeInfo (mypy.nodes.TypeInfo)
        
        # Check metadata first
        if type_info.metadata.get('zuspec_fields'):
            fields = type_info.metadata['zuspec_fields']
            if field_name in fields:
                return fields[field_name]
        
        # Iterate over MRO to find the field definition
        for base in type_info.mro:
            # Check metadata of base
            if base.metadata.get('zuspec_fields'):
                fields = base.metadata['zuspec_fields']
                if field_name in fields:
                    return fields[field_name]

            if not base.defn: continue
            
            body = base.defn.defs.body
            
            # If body is empty, try to find the class definition in the module
            if not body:
                module_name = base.module_name
                if module_name in ctx.api.modules:
                    module = ctx.api.modules[module_name]
                    sym = module.names.get(base.name)
                    if sym:
                        if isinstance(sym.node, ClassDef):
                            body = sym.node.defs.body
                        elif isinstance(sym.node, TypeInfo) and sym.node.defn:
                            body = sym.node.defn.defs.body

            if not body:
                continue

            for stmt in body:
                if isinstance(stmt, AssignmentStmt):
                    # Check if this assignment is for our field
                    for lval in stmt.lvalues:
                        if isinstance(lval, NameExpr) and lval.name == field_name:
                            # Found the assignment. Check RHS.
                            if isinstance(stmt.rvalue, CallExpr):
                                call = stmt.rvalue
                                if isinstance(call.callee, (NameExpr, MemberExpr)):
                                    callee_name = ""
                                    if isinstance(call.callee, NameExpr):
                                        callee_name = call.callee.name
                                    elif isinstance(call.callee, MemberExpr):
                                        callee_name = call.callee.name
                                    
                                    if callee_name == 'input':
                                        return 'input'
                                    if callee_name == 'output':
                                        return 'output'
                                    if callee_name == 'port':
                                        return 'port'
                                    if callee_name == 'export':
                                        return 'export'
                                    if callee_name == 'field':
                                        # Check arguments for default_factory=Input/Output
                                        for i, arg_name in enumerate(call.arg_names):
                                            if arg_name == 'default_factory':
                                                arg_val = call.args[i]
                                                if isinstance(arg_val, NameExpr):
                                                    if arg_val.name == 'Input':
                                                        return 'input'
                                                    if arg_val.name == 'Output':
                                                        return 'output'
                                        return 'component' # Default field is component/field
                            return 'component' # Assignment without call or unknown call
        
        return 'unknown'

def plugin(version: str):
    return ZuspecPlugin
