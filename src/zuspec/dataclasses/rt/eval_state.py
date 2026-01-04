#****************************************************************************
# Copyright 2019-2025 Matthew Ballance and contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#****************************************************************************
"""State Management for synchronous and combinational evaluation."""

from __future__ import annotations
import dataclasses as dc
from typing import Dict, Any, List, Callable, Optional


@dc.dataclass
class EvalState:
    """Manages signal values and deferred assignments for evaluation.
    
    Evaluation requires careful management of signal values to correctly
    model behavior:
    - Sync processes read current values and write to next values (deferred)
    - Comb processes read and write current values (immediate)
    - Signal changes trigger watchers (for comb process re-evaluation)
    """
    
    # Current values (what reads see)
    current_values: Dict[str, Any] = dc.field(default_factory=dict)
    
    # Next values (pending writes from sync processes)
    next_values: Dict[str, Any] = dc.field(default_factory=dict)
    
    # Signal change callbacks (for comb process triggering)
    # Maps field_path -> list of callback functions
    watchers: Dict[str, List[Callable]] = dc.field(default_factory=dict)
    
    def read(self, field_path: str) -> Any:
        """Read current value of a signal.
        
        Both sync and comb processes read from current_values.
        This implements the correct semantics where reads see
        the value at the start of the evaluation cycle.
        
        Args:
            field_path: Path to the field (e.g., "count", "child.data")
            
        Returns:
            Current value of the signal (default 0 if not set)
        """
        return self.current_values.get(field_path, 0)
    
    def write_deferred(self, field_path: str, value: Any):
        """Schedule a deferred write (sync process).
        
        Sync process assignments are deferred - they write to next_values
        and only take effect when commit() is called at the end of the
        clock cycle.
        
        Args:
            field_path: Path to the field to write
            value: Value to write
        """
        self.next_values[field_path] = value
    
    def write_immediate(self, field_path: str, value: Any):
        """Perform an immediate write (comb process).
        
        Comb process assignments take effect immediately. If the value
        changes, registered watchers are triggered to re-evaluate
        dependent comb processes.
        
        Args:
            field_path: Path to the field to write
            value: Value to write
        """
        old_value = self.current_values.get(field_path)
        self.current_values[field_path] = value
        
        # Trigger watchers if value changed
        if old_value != value:
            for watcher in self.watchers.get(field_path, []):
                watcher()
    
    def commit(self):
        """Commit all deferred writes to current values.
        
        Called at the end of a cycle to make all sync process
        writes visible. This models the behavior where all state
        updates occur simultaneously.
        """
        changed_signals = []
        
        for field_path, value in self.next_values.items():
            old_value = self.current_values.get(field_path)
            self.current_values[field_path] = value
            
            # Track which signals changed
            if old_value != value:
                changed_signals.append(field_path)
        
        self.next_values.clear()
        
        # Trigger watchers for changed signals
        for field_path in changed_signals:
            for watcher in self.watchers.get(field_path, []):
                watcher()
    
    def register_watcher(self, field_path: str, callback: Callable):
        """Register a callback to be invoked when a field changes.
        
        Used to implement comb process sensitivity - when a signal
        changes, all comb processes that read it are re-evaluated.
        
        Args:
            field_path: Path to the field to watch
            callback: Function to call when the field changes
        """
        if field_path not in self.watchers:
            self.watchers[field_path] = []
        self.watchers[field_path].append(callback)
    
    def set_value(self, field_path: str, value: Any):
        """Set initial value for a field (bypasses watchers).
        
        Used during initialization to set starting values without
        triggering comb process evaluation.
        
        Args:
            field_path: Path to the field
            value: Initial value
        """
        self.current_values[field_path] = value
