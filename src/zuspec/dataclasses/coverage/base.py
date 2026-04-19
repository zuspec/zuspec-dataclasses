"""
Covergroup base class and core coverage infrastructure.
"""
from typing import Optional, Dict, Any, List
import dataclasses


class Covergroup:
    """Base class for functional coverage models.
    
    Usage:
        @zdc.dataclass
        class MyCov(zdc.Covergroup):
            parent: Any = zdc.field(default=None)
            addr_cp: zdc.uint8_t = zdc.coverpoint(ref=lambda s: s.parent.addr)
    """
    
    class options:
        """Instance-level options."""
        name: Optional[str] = None
        weight: int = 1
        goal: int = 100
        comment: str = ""
        at_least: int = 1
        auto_bin_max: int = 64
        per_instance: bool = False
        detect_overlap: bool = False
    
    class type_options:
        """Type-level options."""
        weight: int = 1
        goal: int = 100
        comment: str = ""
        merge_instances: bool = False
    
    def __post_init__(self):
        """Initialize coverage after dataclass __init__.
        
        This is called by dataclasses after the generated __init__.
        """
        self._enabled = True
        self._coverpoints: Dict[str, 'CoverpointInstance'] = {}
        self._crosses: Dict[str, 'CrossInstance'] = {}
        
        # Initialize coverpoints from descriptors
        self._initialize_coverpoints()
        
        # Initialize runtime if not already done
        if not hasattr(self.__class__, '_runtime_initialized'):
            self._initialize_runtime()
    
    def _initialize_coverpoints(self):
        """Initialize coverpoint instances from descriptors."""
        from .descriptors import CoverpointDescriptor, CrossDescriptor
        from zuspec.ir.core.coverage import CoverpointDef, CrossDef, BinDef
        
        # Find all coverpoint descriptors in the class
        for attr_name in dir(self.__class__):
            if attr_name.startswith('_'):
                continue
            
            attr = getattr(self.__class__, attr_name)
            
            if isinstance(attr, CoverpointDescriptor):
                # Parse bins specification
                bin_defs = []
                auto_bins = True
                
                if attr.bins is not None:
                    bin_defs = self._parse_bins(attr.bins)
                    # Empty bins spec (like {}) means auto-bins
                    auto_bins = (len(bin_defs) == 0)
                
                # Create IR definition
                cp_def = CoverpointDef(
                    name=attr_name,
                    field_type=None,  # TODO: extract from type hint
                    ref=attr.ref,
                    bins=bin_defs,
                    auto_bins=auto_bins,
                    auto_bin_max=attr.auto_bin_max,
                    iff=attr.iff,
                    weight=attr.weight,
                    goal=attr.goal,
                    comment=attr.comment
                )
                
                # Create runtime instance
                self._coverpoints[attr_name] = CoverpointInstance(cp_def, self)
            
            elif isinstance(attr, CrossDescriptor):
                # Create IR definition
                cross_def = CrossDef(
                    name=attr_name,
                    coverpoint_refs=attr.coverpoint_refs,
                    bins=attr.bins if attr.bins else [],
                    auto_bins=(attr.bins is None or len(attr.bins) == 0),
                    iff=attr.iff,
                    weight=attr.weight,
                    goal=attr.goal,
                    comment=attr.comment
                )
                
                # Create runtime instance
                self._crosses[attr_name] = CrossInstance(cross_def, self)
    
    def _parse_bins(self, bins_spec):
        """Parse bins specification into BinDef objects.
        
        Args:
            bins_spec: Dict, list, or other bins specification
            
        Returns:
            List of BinDef objects
        """
        from zuspec.ir.core.coverage import BinDef
        
        bin_defs = []
        
        if isinstance(bins_spec, dict):
            # Dictionary: {name: values}
            if not bins_spec:  # Empty dict -> treat as auto-bins
                return []
            
            for bin_name, values in bins_spec.items():
                bin_defs.append(BinDef(
                    name=bin_name,
                    values=values
                ))
        
        elif isinstance(bins_spec, list):
            # List: [val1, val2, val3] -> creates bin per value
            for i, value in enumerate(bins_spec):
                bin_defs.append(BinDef(
                    name=f'bin_{i}',
                    values=[value]
                ))
        
        return bin_defs
    
    def _initialize_runtime(self):
        """Initialize coverage runtime (called once per class)."""
        # Placeholder - will be implemented with runtime
        self.__class__._runtime_initialized = True
    
    def sample(self, **kwargs):
        """Sample all coverpoints in this covergroup.
        
        Args:
            **kwargs: Optional sample arguments
        """
        if not self._enabled:
            return
        
        # Sample each coverpoint
        for cp_name, cp_inst in self._coverpoints.items():
            cp_inst.sample()
        
        # Sample each cross
        for cross_name, cross_inst in self._crosses.items():
            cross_inst.sample()
    
    def get_coverage(self) -> float:
        """Get overall coverage percentage for this covergroup.
        
        Returns:
            Coverage percentage (0.0 - 100.0)
        """
        if not self._coverpoints and not self._crosses:
            return 0.0
        
        total_weight = 0.0
        weighted_coverage = 0.0
        
        # Aggregate coverpoint coverage
        for cp_inst in self._coverpoints.values():
            weight = cp_inst.weight
            coverage = cp_inst.get_coverage()
            weighted_coverage += coverage * weight
            total_weight += weight
        
        # Aggregate cross coverage
        for cross_inst in self._crosses.values():
            weight = cross_inst.weight
            coverage = cross_inst.get_coverage()
            weighted_coverage += coverage * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        return weighted_coverage / total_weight
    
    def get_inst_coverage(self) -> float:
        """Get instance coverage percentage.
        
        Same as get_coverage() for per-instance covergroups.
        For merged instances, returns type-level coverage.
        """
        return self.get_coverage()
    
    def start(self):
        """Enable coverage collection."""
        self._enabled = True
    
    def stop(self):
        """Disable coverage collection."""
        self._enabled = False
    
    @classmethod
    def type_inst(cls, **kwargs):
        """Get or create type-level coverage instance (singleton).
        
        Returns:
            Singleton coverage instance for this type
        """
        if not hasattr(cls, '_type_instance'):
            cls._type_instance = cls(**kwargs)
        return cls._type_instance


class CoverpointInstance:
    """Runtime instance of a coverpoint."""
    
    def __init__(self, defn: 'CoverpointDef', parent: Covergroup):
        """Initialize coverpoint instance.
        
        Args:
            defn: IR definition
            parent: Parent covergroup
        """
        self.defn = defn
        self.parent = parent
        self.weight = defn.weight
        self.goal = defn.goal
        self.bins: Dict[str, 'BinTracker'] = {}
        
        # Create bins (auto or explicit)
        self._create_bins()
    
    def _create_bins(self):
        """Create bin trackers."""
        if self.defn.auto_bins:
            self._create_auto_bins()
        else:
            self._create_explicit_bins()
    
    def _create_auto_bins(self):
        """Create automatic bins based on field type."""
        # Lazy auto-bin generation - create bins on first sample
        self._auto_bin_pending = True
        self.bins['_pending_'] = BinTracker('_pending_', values=None)
    
    def _finalize_auto_bins(self, sample_value):
        """Finalize auto-bins based on first sampled value.
        
        Args:
            sample_value: First value sampled, used to detect type
        """
        from enum import IntEnum, Enum
        
        # Remove pending bin
        self.bins.clear()
        self._auto_bin_pending = False
        
        # Detect enum and create bin per value
        if isinstance(sample_value, (IntEnum, Enum)):
            enum_class = type(sample_value)
            for member in enum_class:
                self.bins[member.name] = BinTracker(member.name, values=[member.value])
            return
        
        # For integral types with small range, create bins
        # For now, just create a single catch-all bin
        # TODO: Implement range-based binning
        self.bins['auto'] = BinTracker('auto', values=None)
    
    def _create_explicit_bins(self):
        """Create explicit bins from definition."""
        for bin_def in self.defn.bins:
            self.bins[bin_def.name] = BinTracker(bin_def.name, bin_def.values)
    
    def sample(self):
        """Sample this coverpoint."""
        if not self.parent.parent:
            return
        
        # Evaluate ref lambda to get sample value
        if self.defn.ref:
            try:
                # Create a simple object with parent attribute
                context = type('Context', (), {'parent': self.parent.parent})()
                value = self.defn.ref(context)
                
                # Finalize auto-bins on first sample
                if hasattr(self, '_auto_bin_pending') and self._auto_bin_pending:
                    self._finalize_auto_bins(value)
                
                # Find matching bin and increment
                for bin_tracker in self.bins.values():
                    if bin_tracker.matches(value):
                        bin_tracker.hit_count += 1
                        break
            except Exception:
                # Silently ignore sampling errors
                pass
    
    def get_coverage(self) -> float:
        """Get coverage percentage for this coverpoint.
        
        Returns:
            Coverage percentage (0.0 - 100.0)
        """
        if not self.bins:
            return 0.0
        
        # Skip pending bins
        real_bins = {name: b for name, b in self.bins.items() if name != '_pending_'}
        if not real_bins:
            return 0.0
        
        hit_bins = sum(1 for b in real_bins.values() if b.hit_count > 0)
        total_bins = len(real_bins)
        
        return (hit_bins / total_bins) * 100.0


class CrossInstance:
    """Runtime instance of a cross."""
    
    def __init__(self, defn: 'CrossDef', parent: Covergroup):
        """Initialize cross instance.
        
        Args:
            defn: IR definition
            parent: Parent covergroup
        """
        self.defn = defn
        self.parent = parent
        self.weight = defn.weight
        self.goal = defn.goal
        self.bins: Dict[tuple, int] = {}
        self.bin_specs: Dict[str, Any] = {}  # name -> CrossBinSpec
        self._initialized = False
        self._coverpoint_names: List[str] = []
    
    def _initialize(self):
        """Initialize cross bins after coverpoints are finalized."""
        if self._initialized:
            return
        
        # Resolve coverpoint references
        coverpoint_instances = []
        context = type('Context', (), {})()
        
        for cp_ref in self.defn.coverpoint_refs:
            # Set up context to reference coverpoints
            for cp_name, cp_inst in self.parent._coverpoints.items():
                setattr(context, cp_name, cp_inst)
            
            # Call ref lambda to get coverpoint instance
            try:
                cp_inst = cp_ref(context)
                if isinstance(cp_inst, CoverpointInstance):
                    coverpoint_instances.append(cp_inst)
                    self._coverpoint_names.append(cp_inst.defn.name)
            except Exception:
                pass
        
        if not coverpoint_instances:
            return
        
        # Generate cross-product bins
        if self.defn.auto_bins:
            self._generate_auto_bins(coverpoint_instances)
        else:
            self._generate_explicit_bins(coverpoint_instances, context)
        
        self._initialized = True
    
    def _generate_explicit_bins(self, coverpoint_instances: List[CoverpointInstance], context):
        """Generate explicit cross bins from specifications.
        
        Args:
            coverpoint_instances: List of coverpoint instances
            context: Context for evaluating binsof expressions
        """
        from .bins import CrossBinSpec, AndExpr
        
        # Process each bin spec
        for bin_spec in self.defn.bins:
            if not isinstance(bin_spec, CrossBinSpec):
                continue
            
            # Store bin spec for later reference
            self.bin_specs[bin_spec.name] = bin_spec
            
            # Skip ignore bins from coverage calculation
            if bin_spec.is_ignore:
                continue
            
            # Evaluate expression to get bin combinations
            if isinstance(bin_spec.expr, AndExpr):
                # AND expression returns tuple of bin name lists
                result = bin_spec.expr.evaluate(context)
                if isinstance(result, tuple) and len(result) == 2:
                    # Create cross product of the two bin lists
                    import itertools
                    for combo in itertools.product(result[0], result[1]):
                        # Store with bin spec name as prefix
                        self.bins[combo] = 0
            else:
                # For single binsof or other expressions, try to evaluate
                try:
                    bin_names = bin_spec.expr.evaluate(context)
                    if bin_names:
                        # Create bins for each
                        for bin_name in bin_names:
                            self.bins[(bin_name,)] = 0
                except Exception:
                    pass
    
    def _generate_auto_bins(self, coverpoint_instances: List[CoverpointInstance]):
        """Generate automatic cross-product bins.
        
        Args:
            coverpoint_instances: List of coverpoint instances to cross
        """
        import itertools
        
        # Get bin names from each coverpoint
        bin_name_sets = []
        for cp_inst in coverpoint_instances:
            # Skip pending bins
            bin_names = [name for name in cp_inst.bins.keys() if name != '_pending_']
            if bin_names:
                bin_name_sets.append(bin_names)
        
        if not bin_name_sets:
            return
        
        # Create cross product of bin names
        for combo in itertools.product(*bin_name_sets):
            self.bins[combo] = 0
    
    def sample(self):
        """Sample this cross."""
        # Check guard condition
        if self.defn.iff:
            try:
                context = type('Context', (), {'parent': self.parent.parent})()
                if not self.defn.iff(context):
                    return
            except Exception:
                return
        
        # Initialize on first sample if needed
        if not self._initialized:
            self._initialize()
        
        if not self.bins:
            return
        
        # Get bin hit by each coverpoint
        bin_names = []
        context = type('Context', (), {})()
        
        for cp_ref in self.defn.coverpoint_refs:
            # Set up context to reference coverpoints
            for cp_name, cp_inst in self.parent._coverpoints.items():
                setattr(context, cp_name, cp_inst)
            
            # Call ref lambda to get coverpoint instance
            try:
                cp_inst = cp_ref(context)
                if isinstance(cp_inst, CoverpointInstance):
                    # Find which bin was hit (look for bin with hit in this sample)
                    # We need to get the current sampled value's bin
                    if not self.parent.parent:
                        return
                    
                    # Evaluate the coverpoint ref to get value
                    sample_context = type('Context', (), {'parent': self.parent.parent})()
                    value = cp_inst.defn.ref(sample_context)
                    
                    # Find matching bin
                    matched_bin = None
                    for bin_name, bin_tracker in cp_inst.bins.items():
                        if bin_name == '_pending_':
                            continue
                        if bin_tracker.matches(value):
                            matched_bin = bin_name
                            break
                    
                    if matched_bin is None:
                        return  # No bin matched, skip this cross sample
                    
                    bin_names.append(matched_bin)
            except Exception:
                return
        
        # Record hit for this cross bin
        if len(bin_names) == len(self.defn.coverpoint_refs):
            bin_tuple = tuple(bin_names)
            
            # Check if this is an illegal combination
            for bin_spec in self.bin_specs.values():
                if bin_spec.is_illegal:
                    # Check if this tuple matches the illegal spec
                    if self._matches_spec(bin_tuple, bin_spec, context):
                        raise RuntimeError(f"Illegal cross bin sampled: {bin_tuple}")
            
            # Check where filters for explicit bins
            if not self.defn.auto_bins:
                # Find matching bin spec
                for bin_spec in self.bin_specs.values():
                    if bin_spec.is_ignore or bin_spec.is_illegal:
                        continue
                    
                    if self._matches_spec(bin_tuple, bin_spec, context):
                        # Check where filter
                        if bin_spec.where:
                            try:
                                filter_context = type('Context', (), {'parent': self.parent.parent})()
                                if not bin_spec.where(filter_context):
                                    return  # Filter failed, don't count
                            except Exception:
                                return
            
            # Record hit
            if bin_tuple in self.bins:
                self.bins[bin_tuple] += 1
    
    def _matches_spec(self, bin_tuple: tuple, bin_spec, context) -> bool:
        """Check if bin tuple matches a bin specification.
        
        Args:
            bin_tuple: Tuple of bin names from sample
            bin_spec: CrossBinSpec to check against
            context: Evaluation context
            
        Returns:
            True if bin tuple matches the spec
        """
        from .bins import AndExpr
        
        try:
            if isinstance(bin_spec.expr, AndExpr):
                # Evaluate to get expected bin tuple
                result = bin_spec.expr.evaluate(context)
                if isinstance(result, tuple) and len(result) == 2:
                    # Check if our bin_tuple is in the cross product
                    import itertools
                    for combo in itertools.product(result[0], result[1]):
                        if combo == bin_tuple:
                            return True
            return False
        except Exception:
            return False
    
    def get_coverage(self) -> float:
        """Get coverage percentage for this cross.
        
        Returns:
            Coverage percentage (0.0 - 100.0)
        """
        if not self._initialized:
            return 0.0
        
        if not self.bins:
            return 0.0
        
        hit_bins = sum(1 for count in self.bins.values() if count > 0)
        total_bins = len(self.bins)
        
        return (hit_bins / total_bins) * 100.0
    
    def get_total_bins(self) -> int:
        """Get total number of cross bins.
        
        Returns:
            Total number of bins in this cross
        """
        if not self._initialized:
            return 0
        return len(self.bins)
    
    def get_hit_bins(self) -> int:
        """Get number of bins with at least one hit.
        
        Returns:
            Number of bins that have been hit
        """
        if not self._initialized:
            return 0
        return sum(1 for count in self.bins.values() if count > 0)


class BinTracker:
    """Tracks hits for a single bin."""
    
    def __init__(self, name: str, values):
        """Initialize bin tracker.
        
        Args:
            name: Bin name
            values: Values in this bin (range, list, or single value)
        """
        self.name = name
        self.values = values
        self.hit_count = 0
    
    def matches(self, value: Any) -> bool:
        """Check if value falls in this bin.
        
        Args:
            value: Value to check
            
        Returns:
            True if value is in this bin
        """
        # Check for match-all auto bin first
        if self.values == [] or self.values is None:
            return True
        elif isinstance(self.values, range):
            return value in self.values
        elif isinstance(self.values, list):
            return value in self.values
        else:
            return value == self.values
