#!/usr/bin/env python3
"""
Tests for the RV64I Transfer-Function Level Model

These tests verify the correct functional behavior of all RV64I instructions.
"""

import sys
sys.path.insert(0, '../../../src')

import asyncio
import zuspec.dataclasses as zdc
from typing import Dict
from rv64_xf import Rv64XF, sign_extend, sign_extend_32


class SimpleMem:
    """Simple memory implementation for testing."""
    
    def __init__(self, size: int = 0x10000):
        self._mem: Dict[int, int] = {}
        self._size = size
    
    def load_program(self, addr: int, program: list):
        """Load a list of 32-bit instructions into memory."""
        for i, instr in enumerate(program):
            self._write32_sync(addr + i * 4, instr)
    
    def _write32_sync(self, addr: int, data: int):
        """Synchronous write32 for test setup."""
        for i in range(4):
            self._mem[addr + i] = (data >> (i * 8)) & 0xFF
    
    async def read8(self, addr: int) -> int:
        return self._mem.get(addr, 0) & 0xFF
    
    async def read16(self, addr: int) -> int:
        lo = self._mem.get(addr, 0) & 0xFF
        hi = self._mem.get(addr + 1, 0) & 0xFF
        return (hi << 8) | lo
    
    async def read32(self, addr: int) -> int:
        result = 0
        for i in range(4):
            result |= (self._mem.get(addr + i, 0) & 0xFF) << (i * 8)
        return result
    
    async def read64(self, addr: int) -> int:
        result = 0
        for i in range(8):
            result |= (self._mem.get(addr + i, 0) & 0xFF) << (i * 8)
        return result
    
    async def write8(self, addr: int, data: int):
        self._mem[addr] = data & 0xFF
    
    async def write16(self, addr: int, data: int):
        self._mem[addr] = data & 0xFF
        self._mem[addr + 1] = (data >> 8) & 0xFF
    
    async def write32(self, addr: int, data: int):
        for i in range(4):
            self._mem[addr + i] = (data >> (i * 8)) & 0xFF
    
    async def write64(self, addr: int, data: int):
        for i in range(8):
            self._mem[addr + i] = (data >> (i * 8)) & 0xFF


# Instruction encoding helpers
def encode_r_type(opcode, rd, funct3, rs1, rs2, funct7):
    """Encode an R-type instruction."""
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def encode_i_type(opcode, rd, funct3, rs1, imm):
    """Encode an I-type instruction."""
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def encode_s_type(opcode, funct3, rs1, rs2, imm):
    """Encode an S-type instruction."""
    imm_11_5 = (imm >> 5) & 0x7F
    imm_4_0 = imm & 0x1F
    return (imm_11_5 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (imm_4_0 << 7) | opcode


def encode_b_type(opcode, funct3, rs1, rs2, imm):
    """Encode a B-type instruction."""
    imm_12 = (imm >> 12) & 1
    imm_10_5 = (imm >> 5) & 0x3F
    imm_4_1 = (imm >> 1) & 0xF
    imm_11 = (imm >> 11) & 1
    return (imm_12 << 31) | (imm_10_5 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (imm_4_1 << 8) | (imm_11 << 7) | opcode


def encode_u_type(opcode, rd, imm):
    """Encode a U-type instruction."""
    return (imm & 0xFFFFF000) | (rd << 7) | opcode


def encode_j_type(opcode, rd, imm):
    """Encode a J-type instruction."""
    imm_20 = (imm >> 20) & 1
    imm_10_1 = (imm >> 1) & 0x3FF
    imm_11 = (imm >> 11) & 1
    imm_19_12 = (imm >> 12) & 0xFF
    return (imm_20 << 31) | (imm_10_1 << 21) | (imm_11 << 20) | (imm_19_12 << 12) | (rd << 7) | opcode


# Instruction opcodes
OP_LUI = 0x37
OP_AUIPC = 0x17
OP_JAL = 0x6F
OP_JALR = 0x67
OP_BRANCH = 0x63
OP_LOAD = 0x03
OP_STORE = 0x23
OP_OP_IMM = 0x13
OP_OP_IMM_32 = 0x1B
OP_OP = 0x33
OP_OP_32 = 0x3B
OP_SYSTEM = 0x73

# EBREAK instruction
EBREAK = 0x00100073


@zdc.dataclass
class Rv64TestHarness(zdc.Component):
    """Test harness for RV64I model."""
    cpu: Rv64XF = zdc.field()
    mem: SimpleMem = zdc.field(default_factory=SimpleMem)
    
    def __bind__(self):
        return {
            self.cpu.memif: self.mem
        }


async def run_test(program: list, setup=None, reset_v=0x1000) -> Rv64XF:
    """Run a test program and return the CPU state."""
    harness = Rv64TestHarness()
    harness.cpu.reset_v = reset_v
    harness.mem.load_program(reset_v, program)
    harness.cpu.reset()
    
    if setup:
        setup(harness.cpu)
    
    await harness.cpu.run(max_instructions=1000)
    return harness.cpu


# =============================================================================
# LUI and AUIPC tests
# =============================================================================

def test_lui_basic():
    """Test LUI instruction."""
    async def _test():
        program = [
            encode_u_type(OP_LUI, 1, 0x12345000),  # lui x1, 0x12345
            EBREAK
        ]
        cpu = await run_test(program)
        assert cpu.get_reg(1) == sign_extend_32(0x12345000), f"Expected {sign_extend_32(0x12345000):#x}, got {cpu.get_reg(1):#x}"
        print("test_lui_basic PASSED")
    
    asyncio.run(_test())


def test_lui_negative():
    """Test LUI with negative (sign-extended) value."""
    async def _test():
        program = [
            encode_u_type(OP_LUI, 1, 0xFFFFF000),  # lui x1, 0xFFFFF (negative)
            EBREAK
        ]
        cpu = await run_test(program)
        # Should sign extend to 64-bit negative
        expected = 0xFFFFFFFFFFFFF000
        assert cpu.get_reg(1) == expected, f"Expected {expected:#x}, got {cpu.get_reg(1):#x}"
        print("test_lui_negative PASSED")
    
    asyncio.run(_test())


def test_auipc_basic():
    """Test AUIPC instruction."""
    async def _test():
        program = [
            encode_u_type(OP_AUIPC, 1, 0x1000),  # auipc x1, 1
            EBREAK
        ]
        cpu = await run_test(program, reset_v=0x1000)
        # AUIPC adds upper immediate to PC (0x1000 + 0x1000 = 0x2000)
        assert cpu.get_reg(1) == 0x2000, f"Expected 0x2000, got {cpu.get_reg(1):#x}"
        print("test_auipc_basic PASSED")
    
    asyncio.run(_test())


# =============================================================================
# Integer Register-Immediate tests (ADDI, SLTI, etc.)
# =============================================================================

def test_addi_basic():
    """Test ADDI instruction."""
    async def _test():
        program = [
            encode_u_type(OP_LUI, 1, 0x0),  # Clear x1
            encode_i_type(OP_OP_IMM, 1, 0, 1, 100),  # addi x1, x1, 100
            EBREAK
        ]
        cpu = await run_test(program)
        assert cpu.get_reg(1) == 100, f"Expected 100, got {cpu.get_reg(1)}"
        print("test_addi_basic PASSED")
    
    asyncio.run(_test())


def test_addi_negative():
    """Test ADDI with negative immediate."""
    async def _test():
        program = [
            encode_u_type(OP_LUI, 1, 0x0),
            encode_i_type(OP_OP_IMM, 1, 0, 1, 100),  # addi x1, x1, 100
            encode_i_type(OP_OP_IMM, 1, 0, 1, -50 & 0xFFF),  # addi x1, x1, -50
            EBREAK
        ]
        cpu = await run_test(program)
        assert cpu.get_reg(1) == 50, f"Expected 50, got {cpu.get_reg(1)}"
        print("test_addi_negative PASSED")
    
    asyncio.run(_test())


def test_slti():
    """Test SLTI instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 10)
            cpu.set_reg(2, -5 & 0xFFFFFFFFFFFFFFFF)  # Negative value
        
        program = [
            encode_i_type(OP_OP_IMM, 3, 2, 1, 20),   # slti x3, x1, 20 -> x3=1 (10 < 20)
            encode_i_type(OP_OP_IMM, 4, 2, 1, 5),    # slti x4, x1, 5  -> x4=0 (10 >= 5)
            encode_i_type(OP_OP_IMM, 5, 2, 2, 0),    # slti x5, x2, 0  -> x5=1 (-5 < 0)
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(3) == 1, f"Expected x3=1, got {cpu.get_reg(3)}"
        assert cpu.get_reg(4) == 0, f"Expected x4=0, got {cpu.get_reg(4)}"
        assert cpu.get_reg(5) == 1, f"Expected x5=1, got {cpu.get_reg(5)}"
        print("test_slti PASSED")
    
    asyncio.run(_test())


def test_sltiu():
    """Test SLTIU instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 10)
            cpu.set_reg(2, 0xFFFFFFFFFFFFFFFF)  # Max unsigned
        
        program = [
            encode_i_type(OP_OP_IMM, 3, 3, 1, 20),   # sltiu x3, x1, 20 -> x3=1
            encode_i_type(OP_OP_IMM, 4, 3, 2, 1),    # sltiu x4, x2, 1  -> x4=0 (max unsigned >= 1)
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(3) == 1, f"Expected x3=1, got {cpu.get_reg(3)}"
        assert cpu.get_reg(4) == 0, f"Expected x4=0, got {cpu.get_reg(4)}"
        print("test_sltiu PASSED")
    
    asyncio.run(_test())


def test_xori():
    """Test XORI instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 0xFF00FF00)
        
        program = [
            encode_i_type(OP_OP_IMM, 2, 4, 1, 0xFFF),  # xori x2, x1, -1 (all 1s)
            EBREAK
        ]
        cpu = await run_test(program, setup)
        # XOR with -1 (sign extended) inverts all bits
        expected = 0xFF00FF00 ^ 0xFFFFFFFFFFFFFFFF
        assert cpu.get_reg(2) == expected, f"Expected {expected:#x}, got {cpu.get_reg(2):#x}"
        print("test_xori PASSED")
    
    asyncio.run(_test())


def test_ori():
    """Test ORI instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 0xFF00)
        
        program = [
            encode_i_type(OP_OP_IMM, 2, 6, 1, 0x0FF),  # ori x2, x1, 0xFF
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(2) == 0xFFFF, f"Expected 0xFFFF, got {cpu.get_reg(2):#x}"
        print("test_ori PASSED")
    
    asyncio.run(_test())


def test_andi():
    """Test ANDI instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 0xFFFF)
        
        program = [
            encode_i_type(OP_OP_IMM, 2, 7, 1, 0x0FF),  # andi x2, x1, 0xFF
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(2) == 0xFF, f"Expected 0xFF, got {cpu.get_reg(2):#x}"
        print("test_andi PASSED")
    
    asyncio.run(_test())


def test_slli():
    """Test SLLI instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 1)
        
        program = [
            encode_i_type(OP_OP_IMM, 2, 1, 1, 4),  # slli x2, x1, 4
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(2) == 16, f"Expected 16, got {cpu.get_reg(2)}"
        print("test_slli PASSED")
    
    asyncio.run(_test())


def test_srli():
    """Test SRLI instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 0x100)
        
        program = [
            encode_i_type(OP_OP_IMM, 2, 5, 1, 4),  # srli x2, x1, 4
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(2) == 0x10, f"Expected 0x10, got {cpu.get_reg(2):#x}"
        print("test_srli PASSED")
    
    asyncio.run(_test())


def test_srai():
    """Test SRAI instruction (arithmetic right shift)."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 0xFFFFFFFFFFFFFF00)  # Negative value
        
        # SRAI encoding: imm[11:5] = 0x20 (bit 10 set for arithmetic shift)
        srai_imm = (0x20 << 5) | 4  # Shift by 4
        program = [
            encode_i_type(OP_OP_IMM, 2, 5, 1, srai_imm),  # srai x2, x1, 4
            EBREAK
        ]
        cpu = await run_test(program, setup)
        # Arithmetic shift should preserve sign
        expected = 0xFFFFFFFFFFFFFFF0
        assert cpu.get_reg(2) == expected, f"Expected {expected:#x}, got {cpu.get_reg(2):#x}"
        print("test_srai PASSED")
    
    asyncio.run(_test())


# =============================================================================
# Integer Register-Register tests (ADD, SUB, etc.)
# =============================================================================

def test_add():
    """Test ADD instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 100)
            cpu.set_reg(2, 200)
        
        program = [
            encode_r_type(OP_OP, 3, 0, 1, 2, 0),  # add x3, x1, x2
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(3) == 300, f"Expected 300, got {cpu.get_reg(3)}"
        print("test_add PASSED")
    
    asyncio.run(_test())


def test_sub():
    """Test SUB instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 300)
            cpu.set_reg(2, 100)
        
        program = [
            encode_r_type(OP_OP, 3, 0, 1, 2, 0x20),  # sub x3, x1, x2
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(3) == 200, f"Expected 200, got {cpu.get_reg(3)}"
        print("test_sub PASSED")
    
    asyncio.run(_test())


def test_sll():
    """Test SLL instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 1)
            cpu.set_reg(2, 8)
        
        program = [
            encode_r_type(OP_OP, 3, 1, 1, 2, 0),  # sll x3, x1, x2
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(3) == 256, f"Expected 256, got {cpu.get_reg(3)}"
        print("test_sll PASSED")
    
    asyncio.run(_test())


def test_slt():
    """Test SLT instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, -10 & 0xFFFFFFFFFFFFFFFF)
            cpu.set_reg(2, 10)
        
        program = [
            encode_r_type(OP_OP, 3, 2, 1, 2, 0),  # slt x3, x1, x2 -> 1 (-10 < 10)
            encode_r_type(OP_OP, 4, 2, 2, 1, 0),  # slt x4, x2, x1 -> 0 (10 >= -10)
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(3) == 1, f"Expected x3=1, got {cpu.get_reg(3)}"
        assert cpu.get_reg(4) == 0, f"Expected x4=0, got {cpu.get_reg(4)}"
        print("test_slt PASSED")
    
    asyncio.run(_test())


def test_sltu():
    """Test SLTU instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 10)
            cpu.set_reg(2, 0xFFFFFFFFFFFFFFFF)  # Max unsigned
        
        program = [
            encode_r_type(OP_OP, 3, 3, 1, 2, 0),  # sltu x3, x1, x2 -> 1 (10 < max)
            encode_r_type(OP_OP, 4, 3, 2, 1, 0),  # sltu x4, x2, x1 -> 0 (max >= 10)
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(3) == 1, f"Expected x3=1, got {cpu.get_reg(3)}"
        assert cpu.get_reg(4) == 0, f"Expected x4=0, got {cpu.get_reg(4)}"
        print("test_sltu PASSED")
    
    asyncio.run(_test())


def test_xor():
    """Test XOR instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 0xFF00FF00)
            cpu.set_reg(2, 0x00FF00FF)
        
        program = [
            encode_r_type(OP_OP, 3, 4, 1, 2, 0),  # xor x3, x1, x2
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(3) == 0xFFFFFFFF, f"Expected 0xFFFFFFFF, got {cpu.get_reg(3):#x}"
        print("test_xor PASSED")
    
    asyncio.run(_test())


def test_srl():
    """Test SRL instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 0x100)
            cpu.set_reg(2, 4)
        
        program = [
            encode_r_type(OP_OP, 3, 5, 1, 2, 0),  # srl x3, x1, x2
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(3) == 0x10, f"Expected 0x10, got {cpu.get_reg(3):#x}"
        print("test_srl PASSED")
    
    asyncio.run(_test())


def test_sra():
    """Test SRA instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 0xFFFFFFFFFFFFFF00)
            cpu.set_reg(2, 4)
        
        program = [
            encode_r_type(OP_OP, 3, 5, 1, 2, 0x20),  # sra x3, x1, x2
            EBREAK
        ]
        cpu = await run_test(program, setup)
        expected = 0xFFFFFFFFFFFFFFF0
        assert cpu.get_reg(3) == expected, f"Expected {expected:#x}, got {cpu.get_reg(3):#x}"
        print("test_sra PASSED")
    
    asyncio.run(_test())


def test_or():
    """Test OR instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 0xFF00)
            cpu.set_reg(2, 0x00FF)
        
        program = [
            encode_r_type(OP_OP, 3, 6, 1, 2, 0),  # or x3, x1, x2
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(3) == 0xFFFF, f"Expected 0xFFFF, got {cpu.get_reg(3):#x}"
        print("test_or PASSED")
    
    asyncio.run(_test())


def test_and():
    """Test AND instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 0xFFFF)
            cpu.set_reg(2, 0x0FF0)
        
        program = [
            encode_r_type(OP_OP, 3, 7, 1, 2, 0),  # and x3, x1, x2
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(3) == 0x0FF0, f"Expected 0x0FF0, got {cpu.get_reg(3):#x}"
        print("test_and PASSED")
    
    asyncio.run(_test())


# =============================================================================
# RV64I-specific instruction tests (ADDIW, ADDW, etc.)
# =============================================================================

def test_addiw():
    """Test ADDIW instruction (32-bit add with sign extension)."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 0x7FFFFFFF)  # Max positive 32-bit
        
        program = [
            encode_i_type(OP_OP_IMM_32, 2, 0, 1, 1),  # addiw x2, x1, 1 -> overflow
            EBREAK
        ]
        cpu = await run_test(program, setup)
        # 0x7FFFFFFF + 1 = 0x80000000, sign extended to negative
        expected = 0xFFFFFFFF80000000
        assert cpu.get_reg(2) == expected, f"Expected {expected:#x}, got {cpu.get_reg(2):#x}"
        print("test_addiw PASSED")
    
    asyncio.run(_test())


def test_addw():
    """Test ADDW instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 0x7FFFFFFF)
            cpu.set_reg(2, 1)
        
        program = [
            encode_r_type(OP_OP_32, 3, 0, 1, 2, 0),  # addw x3, x1, x2
            EBREAK
        ]
        cpu = await run_test(program, setup)
        expected = 0xFFFFFFFF80000000
        assert cpu.get_reg(3) == expected, f"Expected {expected:#x}, got {cpu.get_reg(3):#x}"
        print("test_addw PASSED")
    
    asyncio.run(_test())


def test_subw():
    """Test SUBW instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 0x80000000)  # Min negative 32-bit (when sign extended)
            cpu.set_reg(2, 1)
        
        program = [
            encode_r_type(OP_OP_32, 3, 0, 1, 2, 0x20),  # subw x3, x1, x2
            EBREAK
        ]
        cpu = await run_test(program, setup)
        # 0x80000000 - 1 = 0x7FFFFFFF (positive)
        expected = 0x7FFFFFFF
        assert cpu.get_reg(3) == expected, f"Expected {expected:#x}, got {cpu.get_reg(3):#x}"
        print("test_subw PASSED")
    
    asyncio.run(_test())


def test_slliw():
    """Test SLLIW instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 0x40000000)  # Will become negative when shifted
        
        program = [
            encode_i_type(OP_OP_IMM_32, 2, 1, 1, 1),  # slliw x2, x1, 1
            EBREAK
        ]
        cpu = await run_test(program, setup)
        # 0x40000000 << 1 = 0x80000000, sign extended to negative
        expected = 0xFFFFFFFF80000000
        assert cpu.get_reg(2) == expected, f"Expected {expected:#x}, got {cpu.get_reg(2):#x}"
        print("test_slliw PASSED")
    
    asyncio.run(_test())


def test_srliw():
    """Test SRLIW instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 0xFFFFFFFF80000000)  # Upper bits should be ignored
        
        program = [
            encode_i_type(OP_OP_IMM_32, 2, 5, 1, 1),  # srliw x2, x1, 1
            EBREAK
        ]
        cpu = await run_test(program, setup)
        # Works on lower 32 bits: 0x80000000 >> 1 = 0x40000000
        expected = 0x40000000
        assert cpu.get_reg(2) == expected, f"Expected {expected:#x}, got {cpu.get_reg(2):#x}"
        print("test_srliw PASSED")
    
    asyncio.run(_test())


def test_sraiw():
    """Test SRAIW instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 0xFFFFFFFF80000000)
        
        # SRAIW: imm[11:5] = 0x20 for arithmetic shift
        sraiw_imm = (0x20 << 5) | 1  # Shift by 1
        program = [
            encode_i_type(OP_OP_IMM_32, 2, 5, 1, sraiw_imm),  # sraiw x2, x1, 1
            EBREAK
        ]
        cpu = await run_test(program, setup)
        # 0x80000000 (negative) >> 1 = 0xC0000000, sign extended
        expected = 0xFFFFFFFFC0000000
        assert cpu.get_reg(2) == expected, f"Expected {expected:#x}, got {cpu.get_reg(2):#x}"
        print("test_sraiw PASSED")
    
    asyncio.run(_test())


# =============================================================================
# Branch instruction tests
# =============================================================================

def test_beq_taken():
    """Test BEQ when branch is taken."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 100)
            cpu.set_reg(2, 100)
        
        program = [
            encode_b_type(OP_BRANCH, 0, 1, 2, 8),  # beq x1, x2, +8
            encode_i_type(OP_OP_IMM, 3, 0, 0, 1),  # addi x3, x0, 1 (skipped)
            encode_i_type(OP_OP_IMM, 4, 0, 0, 2),  # addi x4, x0, 2 (target)
            EBREAK
        ]
        cpu = await run_test(program)
        assert cpu.get_reg(3) == 0, f"Expected x3=0 (skipped), got {cpu.get_reg(3)}"
        assert cpu.get_reg(4) == 2, f"Expected x4=2, got {cpu.get_reg(4)}"
        print("test_beq_taken PASSED")
    
    asyncio.run(_test())


def test_beq_not_taken():
    """Test BEQ when branch is not taken."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 100)
            cpu.set_reg(2, 200)
        
        program = [
            encode_b_type(OP_BRANCH, 0, 1, 2, 8),  # beq x1, x2, +8 (not taken)
            encode_i_type(OP_OP_IMM, 3, 0, 0, 1),  # addi x3, x0, 1 (executed)
            encode_i_type(OP_OP_IMM, 4, 0, 0, 2),  # addi x4, x0, 2
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(3) == 1, f"Expected x3=1, got {cpu.get_reg(3)}"
        assert cpu.get_reg(4) == 2, f"Expected x4=2, got {cpu.get_reg(4)}"
        print("test_beq_not_taken PASSED")
    
    asyncio.run(_test())


def test_bne():
    """Test BNE instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 100)
            cpu.set_reg(2, 200)
        
        program = [
            encode_b_type(OP_BRANCH, 1, 1, 2, 8),  # bne x1, x2, +8 (taken)
            encode_i_type(OP_OP_IMM, 3, 0, 0, 1),  # addi x3, x0, 1 (skipped)
            encode_i_type(OP_OP_IMM, 4, 0, 0, 2),  # addi x4, x0, 2 (target)
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(3) == 0, f"Expected x3=0 (skipped), got {cpu.get_reg(3)}"
        print("test_bne PASSED")
    
    asyncio.run(_test())


def test_blt():
    """Test BLT instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, -10 & 0xFFFFFFFFFFFFFFFF)
            cpu.set_reg(2, 10)
        
        program = [
            encode_b_type(OP_BRANCH, 4, 1, 2, 8),  # blt x1, x2, +8 (taken, -10 < 10)
            encode_i_type(OP_OP_IMM, 3, 0, 0, 1),  # addi x3, x0, 1 (skipped)
            encode_i_type(OP_OP_IMM, 4, 0, 0, 2),  # addi x4, x0, 2 (target)
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(3) == 0, f"Expected x3=0 (skipped), got {cpu.get_reg(3)}"
        print("test_blt PASSED")
    
    asyncio.run(_test())


def test_bge():
    """Test BGE instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 10)
            cpu.set_reg(2, 10)
        
        program = [
            encode_b_type(OP_BRANCH, 5, 1, 2, 8),  # bge x1, x2, +8 (taken, 10 >= 10)
            encode_i_type(OP_OP_IMM, 3, 0, 0, 1),  # addi x3, x0, 1 (skipped)
            encode_i_type(OP_OP_IMM, 4, 0, 0, 2),  # addi x4, x0, 2 (target)
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(3) == 0, f"Expected x3=0 (skipped), got {cpu.get_reg(3)}"
        print("test_bge PASSED")
    
    asyncio.run(_test())


def test_bltu():
    """Test BLTU instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 10)
            cpu.set_reg(2, 0xFFFFFFFFFFFFFFFF)  # Max unsigned
        
        program = [
            encode_b_type(OP_BRANCH, 6, 1, 2, 8),  # bltu x1, x2, +8 (taken)
            encode_i_type(OP_OP_IMM, 3, 0, 0, 1),  # addi x3, x0, 1 (skipped)
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(3) == 0, f"Expected x3=0 (skipped), got {cpu.get_reg(3)}"
        print("test_bltu PASSED")
    
    asyncio.run(_test())


def test_bgeu():
    """Test BGEU instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 0xFFFFFFFFFFFFFFFF)  # Max unsigned
            cpu.set_reg(2, 10)
        
        program = [
            encode_b_type(OP_BRANCH, 7, 1, 2, 8),  # bgeu x1, x2, +8 (taken)
            encode_i_type(OP_OP_IMM, 3, 0, 0, 1),  # addi x3, x0, 1 (skipped)
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(3) == 0, f"Expected x3=0 (skipped), got {cpu.get_reg(3)}"
        print("test_bgeu PASSED")
    
    asyncio.run(_test())


# =============================================================================
# Jump instruction tests
# =============================================================================

def test_jal():
    """Test JAL instruction."""
    async def _test():
        program = [
            encode_j_type(OP_JAL, 1, 8),  # jal x1, +8
            encode_i_type(OP_OP_IMM, 2, 0, 0, 1),  # addi x2, x0, 1 (skipped)
            encode_i_type(OP_OP_IMM, 3, 0, 0, 2),  # addi x3, x0, 2 (target)
            EBREAK
        ]
        cpu = await run_test(program)
        assert cpu.get_reg(1) == 0x1004, f"Expected x1=0x1004 (return addr), got {cpu.get_reg(1):#x}"
        assert cpu.get_reg(2) == 0, f"Expected x2=0 (skipped), got {cpu.get_reg(2)}"
        assert cpu.get_reg(3) == 2, f"Expected x3=2, got {cpu.get_reg(3)}"
        print("test_jal PASSED")
    
    asyncio.run(_test())


def test_jalr():
    """Test JALR instruction."""
    async def _test():
        def setup(cpu):
            cpu.set_reg(1, 0x1008)  # Target address
        
        program = [
            encode_i_type(OP_JALR, 2, 0, 1, 0),  # jalr x2, x1, 0
            encode_i_type(OP_OP_IMM, 3, 0, 0, 1),  # addi x3, x0, 1 (skipped)
            encode_i_type(OP_OP_IMM, 4, 0, 0, 2),  # addi x4, x0, 2 (target)
            EBREAK
        ]
        cpu = await run_test(program, setup)
        assert cpu.get_reg(2) == 0x1004, f"Expected x2=0x1004 (return addr), got {cpu.get_reg(2):#x}"
        assert cpu.get_reg(3) == 0, f"Expected x3=0 (skipped), got {cpu.get_reg(3)}"
        assert cpu.get_reg(4) == 2, f"Expected x4=2, got {cpu.get_reg(4)}"
        print("test_jalr PASSED")
    
    asyncio.run(_test())


# =============================================================================
# Load/Store instruction tests
# =============================================================================

def test_lb_lbu():
    """Test LB and LBU instructions."""
    async def _test():
        harness = Rv64TestHarness()
        harness.cpu.reset_v = 0x1000
        
        program = [
            encode_i_type(OP_LOAD, 2, 0, 1, 0),  # lb x2, 0(x1)
            encode_i_type(OP_LOAD, 3, 4, 1, 0),  # lbu x3, 0(x1)
            EBREAK
        ]
        harness.mem.load_program(0x1000, program)
        await harness.mem.write8(0x2000, 0x80)  # Store a negative byte at 0x2000
        harness.cpu.reset()
        harness.cpu.set_reg(1, 0x2000)
        
        await harness.cpu.run(max_instructions=1000)
        
        # LB should sign extend
        assert harness.cpu.get_reg(2) == 0xFFFFFFFFFFFFFF80, f"Expected sign-extended, got {harness.cpu.get_reg(2):#x}"
        # LBU should zero extend
        assert harness.cpu.get_reg(3) == 0x80, f"Expected 0x80, got {harness.cpu.get_reg(3):#x}"
        print("test_lb_lbu PASSED")
    
    asyncio.run(_test())


def test_lh_lhu():
    """Test LH and LHU instructions."""
    async def _test():
        harness = Rv64TestHarness()
        harness.cpu.reset_v = 0x1000
        
        program = [
            encode_i_type(OP_LOAD, 2, 1, 1, 0),  # lh x2, 0(x1)
            encode_i_type(OP_LOAD, 3, 5, 1, 0),  # lhu x3, 0(x1)
            EBREAK
        ]
        harness.mem.load_program(0x1000, program)
        await harness.mem.write16(0x2000, 0x8000)
        harness.cpu.reset()
        harness.cpu.set_reg(1, 0x2000)
        
        await harness.cpu.run(max_instructions=1000)
        
        assert harness.cpu.get_reg(2) == 0xFFFFFFFFFFFF8000, f"Expected sign-extended, got {harness.cpu.get_reg(2):#x}"
        assert harness.cpu.get_reg(3) == 0x8000, f"Expected 0x8000, got {harness.cpu.get_reg(3):#x}"
        print("test_lh_lhu PASSED")
    
    asyncio.run(_test())


def test_lw_lwu():
    """Test LW and LWU instructions."""
    async def _test():
        harness = Rv64TestHarness()
        harness.cpu.reset_v = 0x1000
        
        program = [
            encode_i_type(OP_LOAD, 2, 2, 1, 0),  # lw x2, 0(x1)
            encode_i_type(OP_LOAD, 3, 6, 1, 0),  # lwu x3, 0(x1)
            EBREAK
        ]
        harness.mem.load_program(0x1000, program)
        await harness.mem.write32(0x2000, 0x80000000)
        harness.cpu.reset()
        harness.cpu.set_reg(1, 0x2000)
        
        await harness.cpu.run(max_instructions=1000)
        
        assert harness.cpu.get_reg(2) == 0xFFFFFFFF80000000, f"Expected sign-extended, got {harness.cpu.get_reg(2):#x}"
        assert harness.cpu.get_reg(3) == 0x80000000, f"Expected 0x80000000, got {harness.cpu.get_reg(3):#x}"
        print("test_lw_lwu PASSED")
    
    asyncio.run(_test())


def test_ld():
    """Test LD instruction."""
    async def _test():
        harness = Rv64TestHarness()
        harness.cpu.reset_v = 0x1000
        
        program = [
            encode_i_type(OP_LOAD, 2, 3, 1, 0),  # ld x2, 0(x1)
            EBREAK
        ]
        harness.mem.load_program(0x1000, program)
        await harness.mem.write64(0x2000, 0xDEADBEEFCAFEBABE)
        harness.cpu.reset()
        harness.cpu.set_reg(1, 0x2000)
        
        await harness.cpu.run(max_instructions=1000)
        
        assert harness.cpu.get_reg(2) == 0xDEADBEEFCAFEBABE, f"Expected 0xDEADBEEFCAFEBABE, got {harness.cpu.get_reg(2):#x}"
        print("test_ld PASSED")
    
    asyncio.run(_test())


def test_sb():
    """Test SB instruction."""
    async def _test():
        harness = Rv64TestHarness()
        harness.cpu.reset_v = 0x1000
        
        program = [
            encode_s_type(OP_STORE, 0, 1, 2, 0),  # sb x2, 0(x1)
            EBREAK
        ]
        harness.mem.load_program(0x1000, program)
        harness.cpu.reset()
        harness.cpu.set_reg(1, 0x2000)
        harness.cpu.set_reg(2, 0xABCDEF12)
        
        await harness.cpu.run(max_instructions=1000)
        
        val = await harness.mem.read8(0x2000)
        assert val == 0x12, f"Expected 0x12, got {val:#x}"
        print("test_sb PASSED")
    
    asyncio.run(_test())


def test_sh():
    """Test SH instruction."""
    async def _test():
        harness = Rv64TestHarness()
        harness.cpu.reset_v = 0x1000
        
        program = [
            encode_s_type(OP_STORE, 1, 1, 2, 0),  # sh x2, 0(x1)
            EBREAK
        ]
        harness.mem.load_program(0x1000, program)
        harness.cpu.reset()
        harness.cpu.set_reg(1, 0x2000)
        harness.cpu.set_reg(2, 0xABCDEF12)
        
        await harness.cpu.run(max_instructions=1000)
        
        val = await harness.mem.read16(0x2000)
        assert val == 0xEF12, f"Expected 0xEF12, got {val:#x}"
        print("test_sh PASSED")
    
    asyncio.run(_test())


def test_sw():
    """Test SW instruction."""
    async def _test():
        harness = Rv64TestHarness()
        harness.cpu.reset_v = 0x1000
        
        program = [
            encode_s_type(OP_STORE, 2, 1, 2, 0),  # sw x2, 0(x1)
            EBREAK
        ]
        harness.mem.load_program(0x1000, program)
        harness.cpu.reset()
        harness.cpu.set_reg(1, 0x2000)
        harness.cpu.set_reg(2, 0x123456789ABCDEF0)
        
        await harness.cpu.run(max_instructions=1000)
        
        val = await harness.mem.read32(0x2000)
        assert val == 0x9ABCDEF0, f"Expected 0x9ABCDEF0, got {val:#x}"
        print("test_sw PASSED")
    
    asyncio.run(_test())


def test_sd():
    """Test SD instruction."""
    async def _test():
        harness = Rv64TestHarness()
        harness.cpu.reset_v = 0x1000
        
        program = [
            encode_s_type(OP_STORE, 3, 1, 2, 0),  # sd x2, 0(x1)
            EBREAK
        ]
        harness.mem.load_program(0x1000, program)
        harness.cpu.reset()
        harness.cpu.set_reg(1, 0x2000)
        harness.cpu.set_reg(2, 0xDEADBEEFCAFEBABE)
        
        await harness.cpu.run(max_instructions=1000)
        
        val = await harness.mem.read64(0x2000)
        assert val == 0xDEADBEEFCAFEBABE, f"Expected 0xDEADBEEFCAFEBABE, got {val:#x}"
        print("test_sd PASSED")
    
    asyncio.run(_test())


# =============================================================================
# Register x0 tests
# =============================================================================

def test_x0_always_zero():
    """Test that x0 is always zero."""
    async def _test():
        program = [
            encode_i_type(OP_OP_IMM, 0, 0, 0, 100),  # addi x0, x0, 100 (write to x0)
            encode_r_type(OP_OP, 1, 0, 0, 0, 0),  # add x1, x0, x0
            EBREAK
        ]
        cpu = await run_test(program)
        assert cpu.get_reg(0) == 0, f"Expected x0=0, got {cpu.get_reg(0)}"
        assert cpu.get_reg(1) == 0, f"Expected x1=0, got {cpu.get_reg(1)}"
        print("test_x0_always_zero PASSED")
    
    asyncio.run(_test())


# =============================================================================
# ECALL handler test
# =============================================================================

def test_ecall():
    """Test ECALL with handler."""
    async def _test():
        ecall_called = [False]
        
        def ecall_handler(cpu):
            ecall_called[0] = True
            # Simulate exit by setting halted flag
            cpu.halted = True
        
        program = [
            encode_i_type(OP_OP_IMM, 1, 0, 0, 42),  # addi x1, x0, 42
            0x00000073,  # ecall
            encode_i_type(OP_OP_IMM, 2, 0, 0, 100),  # addi x2, x0, 100 (not reached)
            EBREAK
        ]
        harness = Rv64TestHarness()
        harness.cpu.reset_v = 0x1000
        harness.mem.load_program(0x1000, program)
        harness.cpu.reset()
        harness.cpu.set_ecall_handler(ecall_handler)
        
        await harness.cpu.run(max_instructions=1000)
        
        assert ecall_called[0], "ECALL handler should have been called"
        assert harness.cpu.get_reg(1) == 42, f"Expected x1=42, got {harness.cpu.get_reg(1)}"
        assert harness.cpu.get_reg(2) == 0, f"Expected x2=0 (not reached), got {harness.cpu.get_reg(2)}"
        print("test_ecall PASSED")
    
    asyncio.run(_test())


# =============================================================================
# Integration test - simple loop
# =============================================================================

def test_simple_loop():
    """Test a simple counting loop."""
    async def _test():
        # Loop that counts from 0 to 10
        # x1 = counter, x2 = limit
        program = [
            encode_i_type(OP_OP_IMM, 1, 0, 0, 0),    # addi x1, x0, 0  (counter = 0)
            encode_i_type(OP_OP_IMM, 2, 0, 0, 10),   # addi x2, x0, 10 (limit = 10)
            # loop:
            encode_b_type(OP_BRANCH, 5, 1, 2, 12),   # bge x1, x2, exit (+12 bytes)
            encode_i_type(OP_OP_IMM, 1, 0, 1, 1),    # addi x1, x1, 1
            encode_j_type(OP_JAL, 0, -8 & 0x1FFFFF), # jal x0, loop (-8 bytes)
            # exit:
            EBREAK
        ]
        cpu = await run_test(program)
        assert cpu.get_reg(1) == 10, f"Expected x1=10, got {cpu.get_reg(1)}"
        print("test_simple_loop PASSED")
    
    asyncio.run(_test())


# =============================================================================
# Integration test - Fibonacci
# =============================================================================

def test_fibonacci():
    """Test computing Fibonacci numbers."""
    async def _test():
        # Compute fib(10) = 55
        # x1 = n, x2 = fib(n-2), x3 = fib(n-1), x4 = fib(n), x5 = counter
        program = [
            encode_i_type(OP_OP_IMM, 1, 0, 0, 10),   # addi x1, x0, 10 (n = 10)
            encode_i_type(OP_OP_IMM, 2, 0, 0, 0),    # addi x2, x0, 0  (fib(0) = 0)
            encode_i_type(OP_OP_IMM, 3, 0, 0, 1),    # addi x3, x0, 1  (fib(1) = 1)
            encode_i_type(OP_OP_IMM, 5, 0, 0, 2),    # addi x5, x0, 2  (counter = 2)
            # loop:
            encode_b_type(OP_BRANCH, 4, 1, 5, 24),   # blt x1, x5, exit (+24 bytes to EBREAK)
            encode_r_type(OP_OP, 4, 0, 2, 3, 0),     # add x4, x2, x3  (fib(n) = fib(n-2) + fib(n-1))
            encode_r_type(OP_OP, 2, 0, 3, 0, 0),     # add x2, x3, x0  (fib(n-2) = fib(n-1))
            encode_r_type(OP_OP, 3, 0, 4, 0, 0),     # add x3, x4, x0  (fib(n-1) = fib(n))
            encode_i_type(OP_OP_IMM, 5, 0, 5, 1),    # addi x5, x5, 1  (counter++)
            encode_j_type(OP_JAL, 0, -20 & 0x1FFFFF),# jal x0, loop (-20 bytes)
            # exit:
            EBREAK
        ]
        cpu = await run_test(program)
        assert cpu.get_reg(4) == 55, f"Expected x4=55 (fib(10)), got {cpu.get_reg(4)}"
        print("test_fibonacci PASSED")
    
    asyncio.run(_test())


# =============================================================================
# Main test runner
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RV64I Transfer-Function Model Tests")
    print("=" * 60)
    
    # LUI/AUIPC tests
    print("\n--- LUI/AUIPC Tests ---")
    test_lui_basic()
    test_lui_negative()
    test_auipc_basic()
    
    # Integer Register-Immediate tests
    print("\n--- Integer Register-Immediate Tests ---")
    test_addi_basic()
    test_addi_negative()
    test_slti()
    test_sltiu()
    test_xori()
    test_ori()
    test_andi()
    test_slli()
    test_srli()
    test_srai()
    
    # Integer Register-Register tests
    print("\n--- Integer Register-Register Tests ---")
    test_add()
    test_sub()
    test_sll()
    test_slt()
    test_sltu()
    test_xor()
    test_srl()
    test_sra()
    test_or()
    test_and()
    
    # RV64I-specific tests
    print("\n--- RV64I-Specific Tests ---")
    test_addiw()
    test_addw()
    test_subw()
    test_slliw()
    test_srliw()
    test_sraiw()
    
    # Branch tests
    print("\n--- Branch Tests ---")
    test_beq_taken()
    test_beq_not_taken()
    test_bne()
    test_blt()
    test_bge()
    test_bltu()
    test_bgeu()
    
    # Jump tests
    print("\n--- Jump Tests ---")
    test_jal()
    test_jalr()
    
    # Load/Store tests
    print("\n--- Load/Store Tests ---")
    test_lb_lbu()
    test_lh_lhu()
    test_lw_lwu()
    test_ld()
    test_sb()
    test_sh()
    test_sw()
    test_sd()
    
    # Special tests
    print("\n--- Special Tests ---")
    test_x0_always_zero()
    test_ecall()
    
    # Integration tests
    print("\n--- Integration Tests ---")
    test_simple_loop()
    test_fibonacci()
    
    print("\n" + "=" * 60)
    print("All tests PASSED!")
    print("=" * 60)
