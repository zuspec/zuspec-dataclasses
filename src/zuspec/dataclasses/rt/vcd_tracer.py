"""VCD (Value Change Dump) tracer for generating waveform files.

This module provides a VCD file writer that implements the SignalTracer protocol
to record signal value changes during simulation.

The VCD format follows IEEE Std 1800-2017, Section 21.7.
"""
from typing import Dict, Any, Optional, TextIO, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from .tracer import Tracer, SignalTracer, Thread


@dataclass
class VCDSignal:
    """Metadata for a signal in the VCD file."""
    component_path: str
    signal_name: str
    width: int
    is_input: bool
    identifier: str  # VCD identifier code (e.g., "!", "#", etc.)


class VCDTracer:
    """VCD file writer implementing the SignalTracer protocol.
    
    Usage:
        vcd = VCDTracer("output.vcd")
        with with_tracer(vcd, enable_signals=True):
            comp = MyComponent()
        
        # Run simulation...
        asyncio.run(comp.run())
        
        # Close to finalize the file
        vcd.close()
    
    The VCD file format:
        - Header: date, version, timescale
        - Definitions: scope hierarchy and variable declarations
        - Value changes: timestamped value transitions
    """
    
    def __init__(
        self, 
        filename: str,
        timescale: str = "1 ns",
        date: Optional[str] = None,
        version: str = "zuspec-dataclasses VCD Writer 1.0"
    ):
        """Initialize VCD tracer.
        
        Args:
            filename: Path to output VCD file
            timescale: VCD timescale (e.g., "1 ns", "10 ps")
            date: Optional date string (defaults to current time)
            version: Version string for VCD header
        """
        self._filename = filename
        self._timescale = timescale
        self._date = date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._version = version
        
        self._file: Optional[TextIO] = None
        self._signals: Dict[str, VCDSignal] = {}  # (comp_path, signal_name) -> VCDSignal
        self._next_id: int = 0
        self._header_written: bool = False
        self._last_time: float = -1.0
        self._signal_values: Dict[str, Any] = {}  # identifier -> current value
        
        # Buffered value changes before header is written
        self._pending_changes: List[Tuple[float, str, Any, int]] = []
    
    def _generate_identifier(self) -> str:
        """Generate a unique VCD identifier code.
        
        VCD identifiers are composed of printable ASCII characters from ! (33) to ~ (126).
        We use a base-94 encoding to generate short unique identifiers.
        """
        chars = [chr(c) for c in range(33, 127)]  # ! to ~
        base = len(chars)
        
        n = self._next_id
        self._next_id += 1
        
        if n == 0:
            return chars[0]
        
        result = []
        while n > 0:
            result.append(chars[n % base])
            n //= base
        
        return ''.join(reversed(result))
    
    def _get_signal_key(self, component_path: str, signal_name: str) -> str:
        """Get unique key for a signal."""
        return f"{component_path}.{signal_name}"
    
    def register_signal(
        self,
        component_path: str,
        signal_name: str,
        width: int,
        is_input: bool
    ) -> None:
        """Register a signal for VCD output.
        
        Called during component construction to discover signals.
        """
        key = self._get_signal_key(component_path, signal_name)
        if key not in self._signals:
            identifier = self._generate_identifier()
            self._signals[key] = VCDSignal(
                component_path=component_path,
                signal_name=signal_name,
                width=width,
                is_input=is_input,
                identifier=identifier
            )
    
    def signal_change(
        self, 
        component_path: str,
        signal_name: str, 
        time_ns: float, 
        old_value: Any,
        new_value: Any, 
        width: int
    ) -> None:
        """Record a signal value change.
        
        Called when a signal value changes during simulation.
        """
        key = self._get_signal_key(component_path, signal_name)
        
        # Ensure signal is registered
        if key not in self._signals:
            self.register_signal(component_path, signal_name, width, is_input=False)
        
        sig = self._signals[key]
        
        if not self._header_written:
            # Buffer changes until header is written
            self._pending_changes.append((time_ns, sig.identifier, new_value, width))
            return
        
        # Write timestamp if time has advanced
        if time_ns > self._last_time:
            # VCD uses integer timestamps - convert ns to timescale units
            time_units = int(time_ns)  # Assuming 1ns timescale
            self._file.write(f"#{time_units}\n")
            self._last_time = time_ns
        
        # Write value change
        self._write_value_change(sig.identifier, new_value, width)
    
    def _write_value_change(self, identifier: str, value: Any, width: int):
        """Write a value change to the VCD file."""
        if width == 1:
            # Scalar value - no space between value and identifier
            bit_val = '1' if value else '0'
            self._file.write(f"{bit_val}{identifier}\n")
        else:
            # Vector value - binary format with space before identifier
            if value is None:
                bin_str = 'x' * width
            elif isinstance(value, int):
                if value < 0:
                    # Handle negative values as two's complement
                    value = value & ((1 << width) - 1)
                bin_str = format(value, f'b')
            else:
                bin_str = format(int(value), f'b')
            
            self._file.write(f"b{bin_str} {identifier}\n")
    
    def _write_header(self):
        """Write VCD header and variable definitions."""
        if self._header_written:
            return
        
        self._file = open(self._filename, 'w')
        
        # Date
        self._file.write(f"$date\n   {self._date}\n$end\n")
        
        # Version
        self._file.write(f"$version\n   {self._version}\n$end\n")
        
        # Timescale
        self._file.write(f"$timescale {self._timescale} $end\n")
        
        # Build scope hierarchy and write variable declarations
        self._write_scope_hierarchy()
        
        # End definitions
        self._file.write("$enddefinitions $end\n")
        
        # Write initial values ($dumpvars)
        self._file.write("$dumpvars\n")
        for sig in self._signals.values():
            # Initialize all signals to x (unknown)
            if sig.width == 1:
                self._file.write(f"x{sig.identifier}\n")
            else:
                self._file.write(f"bx {sig.identifier}\n")
        self._file.write("$end\n")
        
        self._header_written = True
        
        # Write any buffered changes
        for time_ns, identifier, value, width in self._pending_changes:
            if time_ns > self._last_time:
                time_units = int(time_ns)
                self._file.write(f"#{time_units}\n")
                self._last_time = time_ns
            self._write_value_change(identifier, value, width)
        
        self._pending_changes.clear()
    
    def _write_scope_hierarchy(self):
        """Write scope hierarchy and variable declarations.
        
        Groups signals by component path and creates nested scopes.
        """
        # Group signals by component path
        by_component: Dict[str, List[VCDSignal]] = {}
        for sig in self._signals.values():
            path = sig.component_path
            if path not in by_component:
                by_component[path] = []
            by_component[path].append(sig)
        
        # Sort component paths for consistent output
        sorted_paths = sorted(by_component.keys())
        
        # Track current scope depth for proper nesting
        current_scope: List[str] = []
        
        for path in sorted_paths:
            # Parse path into parts
            parts = path.split('.')
            
            # Find common prefix with current scope
            common_len = 0
            for i, (a, b) in enumerate(zip(current_scope, parts)):
                if a == b:
                    common_len = i + 1
                else:
                    break
            
            # Close scopes that are no longer in path
            while len(current_scope) > common_len:
                current_scope.pop()
                self._file.write("$upscope $end\n")
            
            # Open new scopes
            for part in parts[common_len:]:
                self._file.write(f"$scope module {part} $end\n")
                current_scope.append(part)
            
            # Write variable declarations for this scope
            for sig in by_component[path]:
                var_type = "wire" if sig.is_input else "reg"
                self._file.write(
                    f"$var {var_type} {sig.width} {sig.identifier} {sig.signal_name} $end\n"
                )
        
        # Close all remaining scopes
        while current_scope:
            current_scope.pop()
            self._file.write("$upscope $end\n")
    
    def finalize(self):
        """Finalize the VCD file.
        
        Writes the header if not already written and ensures file is complete.
        Call this before close() to ensure all signals are properly declared.
        """
        if not self._header_written and self._signals:
            self._write_header()
    
    def close(self):
        """Close the VCD file.
        
        Must be called to finalize the VCD output.
        """
        self.finalize()
        if self._file:
            self._file.close()
            self._file = None
    
    def __enter__(self):
        """Support context manager usage."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close on context exit."""
        self.close()
        return False
    
    # Implement Tracer protocol methods (method tracing)
    def enter(self, method: str, thread: Thread, time_ns: float, args: Dict[str, Any]) -> None:
        """Called when entering a traced method (from Tracer protocol)."""
        # VCDTracer focuses on signal tracing, method tracing is optional
        pass
    
    def leave(self, method: str, thread: Thread, time_ns: float, ret: Any, exc: Optional[Exception]) -> None:
        """Called when leaving a traced method (from Tracer protocol)."""
        # VCDTracer focuses on signal tracing, method tracing is optional
        pass
