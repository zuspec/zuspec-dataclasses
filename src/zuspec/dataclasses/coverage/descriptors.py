"""
Coverage descriptors: coverpoint() and cross().
"""
from typing import Optional, Callable, Any, Union, List, Dict


def coverpoint(
    ref: Optional[Callable] = None,
    bins: Optional[Union[Dict, List, Callable]] = None,
    iff: Optional[Callable] = None,
    auto_bin_max: Optional[int] = None,
    weight: int = 1,
    goal: int = 100,
    comment: str = "",
) -> Any:
    """Declare a coverpoint field.
    
    Args:
        ref: Lambda expression to sample (e.g., lambda s: s.parent.addr)
        bins: Explicit bin specification (dict, list, or callable)
        iff: Guard condition lambda
        auto_bin_max: Maximum number of auto-generated bins
        weight: Coverpoint weight for coverage calculation
        goal: Goal percentage for this coverpoint
        comment: Documentation string
        
    Returns:
        Field descriptor with coverage metadata
    
    Example:
        @zdc.dataclass
        class MyCov(zdc.Covergroup):
            addr_cp: zdc.uint8_t = zdc.coverpoint(
                ref=lambda s: s.parent.addr,
                bins={'low': range(0, 128), 'high': range(128, 256)},
                weight=2
            )
    """
    # Return a CoverpointDescriptor that stores metadata
    return CoverpointDescriptor(
        ref=ref,
        bins=bins,
        iff=iff,
        auto_bin_max=auto_bin_max,
        weight=weight,
        goal=goal,
        comment=comment
    )


def cross(
    *coverpoint_refs,
    iff: Optional[Callable] = None,
    bins: Optional[Union[Dict, List, Callable]] = None,
    weight: int = 1,
    goal: int = 100,
    comment: str = "",
) -> Any:
    """Declare a cross coverage field.
    
    Args:
        *coverpoint_refs: Lambda references to coverpoints to cross
        iff: Guard condition lambda
        bins: Explicit cross bin specification
        weight: Cross weight for coverage calculation
        goal: Goal percentage for this cross
        comment: Documentation string
        
    Returns:
        Field descriptor with cross metadata
        
    Example:
        @zdc.dataclass
        class MyCov(zdc.Covergroup):
            addr_cp: zdc.uint8_t = zdc.coverpoint(ref=lambda s: s.parent.addr)
            data_cp: zdc.uint8_t = zdc.coverpoint(ref=lambda s: s.parent.data)
            addr_data_cross = zdc.cross(
                lambda s: s.addr_cp,
                lambda s: s.data_cp
            )
    """
    return CrossDescriptor(
        coverpoint_refs=list(coverpoint_refs),
        iff=iff,
        bins=bins,
        weight=weight,
        goal=goal,
        comment=comment
    )


class CoverpointDescriptor:
    """Descriptor for coverpoint fields."""
    
    def __init__(
        self,
        ref: Optional[Callable] = None,
        bins: Optional[Union[Dict, List, Callable]] = None,
        iff: Optional[Callable] = None,
        auto_bin_max: Optional[int] = None,
        weight: int = 1,
        goal: int = 100,
        comment: str = ""
    ):
        self.ref = ref
        self.bins = bins
        self.iff = iff
        self.auto_bin_max = auto_bin_max or 64
        self.weight = weight
        self.goal = goal
        self.comment = comment
        self.name: Optional[str] = None
    
    def __set_name__(self, owner, name):
        """Called when descriptor is assigned to class attribute."""
        self.name = name
    
    def __get__(self, obj, objtype=None):
        """Get coverpoint instance from covergroup instance."""
        if obj is None:
            return self
        
        # Return the coverpoint instance
        return obj._coverpoints.get(self.name)
    
    def __set__(self, obj, value):
        """Handle assignment during initialization."""
        # During dataclass __init__, the descriptor itself is being set
        # We should just ignore it since we'll create instances in __post_init__
        if isinstance(value, CoverpointDescriptor):
            return
        raise AttributeError(f"Cannot assign to coverpoint field '{self.name}'")


class CrossDescriptor:
    """Descriptor for cross coverage fields."""
    
    def __init__(
        self,
        coverpoint_refs: List[Callable],
        iff: Optional[Callable] = None,
        bins: Optional[Union[Dict, List, Callable]] = None,
        weight: int = 1,
        goal: int = 100,
        comment: str = ""
    ):
        self.coverpoint_refs = coverpoint_refs
        self.iff = iff
        self.bins = bins
        self.weight = weight
        self.goal = goal
        self.comment = comment
        self.name: Optional[str] = None
    
    def __set_name__(self, owner, name):
        """Called when descriptor is assigned to class attribute."""
        self.name = name
    
    def __get__(self, obj, objtype=None):
        """Get cross instance from covergroup instance."""
        if obj is None:
            return self
        
        # Return the cross instance
        return obj._crosses.get(self.name)
    
    def __set__(self, obj, value):
        """Handle assignment during initialization."""
        # During dataclass __init__, the descriptor itself is being set
        # We should just ignore it since we'll create instances in __post_init__
        if isinstance(value, CrossDescriptor):
            return
        raise AttributeError(f"Cannot assign to cross field '{self.name}'")
