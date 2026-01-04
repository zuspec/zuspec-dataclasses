"""Edge detection utilities for simulation."""

import asyncio
from typing import Any


async def posedge(signal: Any) -> None:
    """Wait for positive edge of a signal.
    
    Args:
        signal: Signal to wait on (should be a bit or clock signal)
    """
    # This is a placeholder that will be replaced by simulation backend
    # In actual simulation, this would trigger SystemVerilog @(posedge signal)
    await asyncio.sleep(0)


async def negedge(signal: Any) -> None:
    """Wait for negative edge of a signal.
    
    Args:
        signal: Signal to wait on (should be a bit or clock signal)
    """
    # This is a placeholder that will be replaced by simulation backend
    # In actual simulation, this would trigger SystemVerilog @(negedge signal)
    await asyncio.sleep(0)


async def edge(signal: Any) -> None:
    """Wait for any edge (positive or negative) of a signal.
    
    Args:
        signal: Signal to wait on (should be a bit or clock signal)
    """
    # This is a placeholder that will be replaced by simulation backend
    await asyncio.sleep(0)
