#****************************************************************************
# SPI Master Core Protocol-Level Model
# Based on OpenCores SPI Master Core Specification Rev 0.6
#****************************************************************************

from .spi_model import (
    SpiCtrl,
    SpiDivider,
    SpiSS,
    SpiRegs,
    SpiMaster,
    SpiDataIF,
    create_spi_master
)

__all__ = [
    'SpiCtrl',
    'SpiDivider', 
    'SpiSS',
    'SpiRegs', 
    'SpiMaster',
    'SpiDataIF',
    'create_spi_master'
]
