"""Example of creating and using a custom profile."""
import zuspec.dataclasses as zdc
from zuspec.dataclasses.profiles import Profile, ProfileChecker, PROFILE_REGISTRY
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from mypy.plugin import ClassDefContext
    from mypy.nodes import FuncDef, Expression
    from mypy.types import Type as MypyType


class RestrictedRTLChecker:
    """Custom checker for restricted RTL subset.
    
    Only allows:
    - Unsigned integer types (uint8_t, uint16_t, etc.)
    - No async methods
    - No dynamic operations
    """
    
    def check_field_type(self, field_name: str, field_type: 'MypyType', 
                        ctx: 'ClassDefContext') -> None:
        """Only allow unsigned integer types."""
        from mypy.types import Instance
        
        if isinstance(field_type, Instance):
            type_name = field_type.type.fullname
            # Check if it's an integer type
            if 'int' in type_name and type_name.startswith('zuspec.dataclasses.types.'):
                # Only allow unsigned types
                if not type_name.startswith('zuspec.dataclasses.types.uint'):
                    ctx.api.fail(
                        f"Field '{field_name}' uses signed type '{type_name}'. "
                        f"RestrictedRTL only allows unsigned types (uint8_t, uint16_t, etc.)",
                        ctx.cls
                    )
    
    def check_method(self, method: 'FuncDef', ctx: 'ClassDefContext') -> None:
        """Disallow async methods in RTL."""
        if method.is_coroutine:
            ctx.api.fail(
                f"Method '{method.name}' is async. "
                f"RestrictedRTL does not allow async methods",
                method
            )
    
    def check_variable_annotation(self, var_name: str, var_type: Optional['MypyType'], 
                                  expr: 'Expression', ctx: 'ClassDefContext') -> None:
        """Require type annotations."""
        if var_type is None:
            ctx.api.fail(
                f"Variable '{var_name}' is not type-annotated. "
                f"RestrictedRTL requires explicit type annotations",
                expr
            )


class RestrictedRTLProfile(Profile):
    """Custom profile for restricted RTL synthesis.
    
    This profile enforces a subset of Retargetable that only allows
    unsigned integer types and synchronous methods.
    """
    
    @classmethod
    def get_checker(cls) -> Optional['ProfileChecker']:
        return RestrictedRTLChecker()  # type: ignore


# Register the custom profile
PROFILE_REGISTRY['RestrictedRTL'] = RestrictedRTLProfile


# Example usage: This should be OK
@zdc.dataclass(profile=RestrictedRTLProfile)
class SimpleCounter(zdc.Component):
    count: zdc.uint8_t = zdc.output()
    clk: zdc.uint1_t = zdc.input()
    
    @zdc.sync(clock=lambda s: s.clk)
    def _count(self):
        val: zdc.uint8_t = self.count + 1
        self.count = val


# Example usage: This should produce errors
@zdc.dataclass(profile=RestrictedRTLProfile)
class BadCounter(zdc.Component):
    # error: signed type not allowed in RestrictedRTL
    count: zdc.int8_t = zdc.output()
    
    # error: async method not allowed in RestrictedRTL
    @zdc.process
    async def _process(self):
        pass


if __name__ == '__main__':
    print("Custom profile example")
    counter = SimpleCounter()
    print(f"Counter: {counter.count}")
