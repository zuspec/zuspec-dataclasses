"""Preprocessing pipeline orchestrator."""

from typing import List, Dict
from ..core.constraint_system import ConstraintSystem
from ..core.variable import Variable
from ..core.constraint import Constraint
from .constant_folder import ConstantFolder
from .range_analyzer import RangeAnalyzer
from .dependency_analyzer import DependencyAnalyzer
from .algebraic_simplifier import AlgebraicSimplifier


class PreprocessingPipeline:
    """
    Orchestrates the full preprocessing pipeline:
    1. Constant folding
    2. Range analysis
    3. Dependency analysis
    4. Algebraic simplification
    """
    
    def __init__(self, bit_width: int = 64):
        self.bit_width = bit_width
        self.constant_folder = ConstantFolder()
        self.range_analyzer = RangeAnalyzer(bit_width)
        self.dependency_analyzer = DependencyAnalyzer()
        self.algebraic_simplifier = AlgebraicSimplifier()
    
    def preprocess(self, system: ConstraintSystem) -> Dict:
        """
        Run full preprocessing pipeline on constraint system.
        Returns dict with analysis results.
        """
        results = {
            'unsat': False,
            'domains_pruned': {},
            'constraints_simplified': 0,
            'components': [],
            'ordering': [],
        }
        
        # Phase 1: Constant folding
        system.constraints = self.constant_folder.fold_constraints(system.constraints)
        
        # Phase 2: Range analysis
        ranges = self.range_analyzer.analyze(system.variables)
        pruned = self.range_analyzer.prune_domains(system.variables)
        results['domains_pruned'] = pruned
        
        # Check for UNSAT
        if self.range_analyzer.detect_unsat():
            results['unsat'] = True
            return results
        
        # Phase 3: Dependency analysis
        self.dependency_analyzer.analyze(system.constraints, system.variables)
        results['components'] = self.dependency_analyzer.get_components()
        results['ordering'] = self.dependency_analyzer.get_ordering()
        
        # Phase 4: Algebraic simplification
        original_count = len(system.constraints)
        system.constraints = self.algebraic_simplifier.simplify_constraints(system.constraints)
        results['constraints_simplified'] = original_count - len(system.constraints)
        
        return results
    
    def get_dependency_analyzer(self) -> DependencyAnalyzer:
        """Get the dependency analyzer for further queries."""
        return self.dependency_analyzer
    
    def get_range_analyzer(self) -> RangeAnalyzer:
        """Get the range analyzer for further queries."""
        return self.range_analyzer
