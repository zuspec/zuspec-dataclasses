"""
Coverage bin helpers and select expressions.

Provides binsof() expressions for selective cross coverage and helpers
for explicit cross bin specifications.
"""
from typing import Optional, Any, List, Union, Callable


class BinsofExpr:
    """Select expression for cross bins.
    
    Used to select specific bins from coverpoints for cross coverage.
    Supports filtering and boolean operations.
    """
    
    def __init__(self, coverpoint_ref: Callable, bin_name: Optional[str] = None):
        """Initialize binsof expression.
        
        Args:
            coverpoint_ref: Lambda returning coverpoint instance
            bin_name: Optional specific bin name to select
        """
        self.coverpoint_ref = coverpoint_ref
        self.bin_name = bin_name
    
    def intersect(self, values):
        """Intersect selected bins with value set.
        
        Args:
            values: List, range, or single value to intersect with
            
        Returns:
            IntersectExpr combining this selection with values
        """
        return IntersectExpr(self, values)
    
    def __and__(self, other):
        """Logical AND - both expressions must match.
        
        Args:
            other: Another binsof expression
            
        Returns:
            AndExpr requiring both to match
        """
        return AndExpr(self, other)
    
    def __or__(self, other):
        """Logical OR - either expression matches.
        
        Args:
            other: Another binsof expression
            
        Returns:
            OrExpr allowing either to match
        """
        return OrExpr(self, other)
    
    def __invert__(self):
        """Logical NOT - exclude bins.
        
        Returns:
            NotExpr excluding selected bins
        """
        return NotExpr(self)
    
    def evaluate(self, context) -> List[str]:
        """Evaluate expression to get list of bin names.
        
        Args:
            context: Evaluation context with coverpoint instances
            
        Returns:
            List of bin names that match this expression
        """
        # Get coverpoint instance
        cp_inst = self.coverpoint_ref(context)
        
        # If specific bin name requested, return just that
        if self.bin_name:
            if self.bin_name in cp_inst.bins:
                return [self.bin_name]
            return []
        
        # Return all bins (except pending)
        return [name for name in cp_inst.bins.keys() if name != '_pending_']


class IntersectExpr:
    """Intersect expression - filter bins by values."""
    
    def __init__(self, binsof_expr: BinsofExpr, values):
        """Initialize intersect expression.
        
        Args:
            binsof_expr: Base binsof expression
            values: Values to intersect with
        """
        self.binsof_expr = binsof_expr
        self.values = values
    
    def evaluate(self, context) -> List[str]:
        """Evaluate to get filtered bin names.
        
        Args:
            context: Evaluation context
            
        Returns:
            List of bin names whose values intersect with filter
        """
        # Get bins from base expression
        bin_names = self.binsof_expr.evaluate(context)
        
        # Get coverpoint instance
        cp_inst = self.binsof_expr.coverpoint_ref(context)
        
        # Filter bins that contain any of the values
        filtered = []
        for bin_name in bin_names:
            if bin_name not in cp_inst.bins:
                continue
            
            bin_tracker = cp_inst.bins[bin_name]
            bin_values = bin_tracker.values
            
            # Check if bin values intersect with filter values
            if self._intersects(bin_values, self.values):
                filtered.append(bin_name)
        
        return filtered
    
    def _intersects(self, bin_values, filter_values) -> bool:
        """Check if two value sets intersect.
        
        Args:
            bin_values: Values from bin
            filter_values: Values to filter by
            
        Returns:
            True if sets intersect
        """
        # Convert to sets for intersection
        if isinstance(bin_values, range):
            bin_set = set(bin_values)
        elif isinstance(bin_values, list):
            bin_set = set(bin_values)
        elif bin_values is None:
            return True  # Match-all bin
        else:
            bin_set = {bin_values}
        
        if isinstance(filter_values, range):
            filter_set = set(filter_values)
        elif isinstance(filter_values, list):
            filter_set = set(filter_values)
        else:
            filter_set = {filter_values}
        
        return bool(bin_set & filter_set)


class AndExpr:
    """AND expression - both must match."""
    
    def __init__(self, left, right):
        """Initialize AND expression.
        
        Args:
            left: Left expression
            right: Right expression
        """
        self.left = left
        self.right = right
    
    def evaluate(self, context) -> tuple:
        """Evaluate to get tuple of bin name lists.
        
        Args:
            context: Evaluation context
            
        Returns:
            Tuple of (left_bins, right_bins) for cross product
        """
        left_bins = self.left.evaluate(context)
        right_bins = self.right.evaluate(context)
        return (left_bins, right_bins)


class OrExpr:
    """OR expression - either can match."""
    
    def __init__(self, left, right):
        """Initialize OR expression.
        
        Args:
            left: Left expression
            right: Right expression
        """
        self.left = left
        self.right = right
    
    def evaluate(self, context) -> List[str]:
        """Evaluate to get union of bin names.
        
        Args:
            context: Evaluation context
            
        Returns:
            Combined list of bin names from both expressions
        """
        left_bins = self.left.evaluate(context)
        right_bins = self.right.evaluate(context)
        # Union - remove duplicates
        return list(set(left_bins) | set(right_bins))


class NotExpr:
    """NOT expression - exclude bins."""
    
    def __init__(self, expr):
        """Initialize NOT expression.
        
        Args:
            expr: Expression to negate
        """
        self.expr = expr
    
    def evaluate(self, context) -> List[str]:
        """Evaluate to get inverted bin names.
        
        Args:
            context: Evaluation context
            
        Returns:
            List of bin names not in the expression
        """
        # Get bins to exclude
        exclude_bins = set(self.expr.evaluate(context))
        
        # Get coverpoint instance and all its bins
        cp_inst = self.expr.coverpoint_ref(context)
        all_bins = [name for name in cp_inst.bins.keys() if name != '_pending_']
        
        # Return bins not in exclusion set
        return [name for name in all_bins if name not in exclude_bins]


class CrossBinSpec:
    """Specification for explicit cross bin."""
    
    def __init__(
        self,
        name: str,
        expr: Any,
        where: Optional[Callable] = None,
        matches: Optional[int] = None,
        is_ignore: bool = False,
        is_illegal: bool = False
    ):
        """Initialize cross bin specification.
        
        Args:
            name: Bin name
            expr: binsof expression or tuple of expressions
            where: Optional filter lambda
            matches: Optional match count
            is_ignore: If True, ignore this combination
            is_illegal: If True, mark as illegal
        """
        self.name = name
        self.expr = expr
        self.where = where
        self.matches = matches
        self.is_ignore = is_ignore
        self.is_illegal = is_illegal


def binsof(coverpoint_ref: Callable, bin_name: Optional[str] = None) -> BinsofExpr:
    """Create a bin selection expression for cross coverage.
    
    Args:
        coverpoint_ref: Lambda returning coverpoint instance (e.g., lambda s: s.addr_cp)
        bin_name: Optional specific bin name to select from coverpoint
        
    Returns:
        BinsofExpr that can be used in cross bin specifications
        
    Example:
        # Select all bins from addr_cp
        binsof(lambda s: s.addr_cp)
        
        # Select specific 'low' bin from addr_cp
        binsof(lambda s: s.addr_cp, 'low')
        
        # Intersect with values
        binsof(lambda s: s.addr_cp).intersect(range(0, 64))
        
        # Boolean operations
        binsof(lambda s: s.addr_cp, 'low') & binsof(lambda s: s.data_cp, 'even')
    """
    return BinsofExpr(coverpoint_ref, bin_name)


def cross_bins(
    name: str,
    expr: Any,
    where: Optional[Callable] = None,
    matches: Optional[int] = None
) -> CrossBinSpec:
    """Create an explicit cross bin specification.
    
    Args:
        name: Name for this cross bin
        expr: binsof expression or tuple of expressions
        where: Optional filter lambda
        matches: Optional expected match count
        
    Returns:
        CrossBinSpec for use in cross bins= parameter
        
    Example:
        # Cross specific bins
        cross_bins('low_even',
                   binsof(lambda s: s.addr_cp, 'low') &
                   binsof(lambda s: s.data_cp, 'even'))
    """
    return CrossBinSpec(name=name, expr=expr, where=where, matches=matches)


def cross_ignore(name: str, expr: Any) -> CrossBinSpec:
    """Create an ignored cross bin specification.
    
    Args:
        name: Name for this ignored bin
        expr: binsof expression
        
    Returns:
        CrossBinSpec marked as ignored
        
    Example:
        # Ignore certain combinations
        cross_ignore('ignore_low_odd',
                     binsof(lambda s: s.addr_cp, 'low') &
                     binsof(lambda s: s.data_cp, 'odd'))
    """
    return CrossBinSpec(name=name, expr=expr, is_ignore=True)


def cross_illegal(name: str, expr: Any) -> CrossBinSpec:
    """Create an illegal cross bin specification.
    
    Args:
        name: Name for this illegal bin
        expr: binsof expression
        
    Returns:
        CrossBinSpec marked as illegal
        
    Example:
        # Mark invalid combinations as illegal
        cross_illegal('illegal_high_zero',
                      binsof(lambda s: s.addr_cp, 'high') &
                      binsof(lambda s: s.data_cp, 'zero'))
    """
    return CrossBinSpec(name=name, expr=expr, is_illegal=True)
