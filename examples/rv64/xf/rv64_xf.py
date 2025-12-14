"""
RISC-V RV64I Transfer-Function Level Model

This is a functional model of the RV64I base integer instruction set.
It implements all 47 RV64I instructions without timing accuracy,
focusing on correct functional behavior.

Reference: RISC-V ISA Manual, Chapter 2 (RV32I) and Chapter 5 (RV64I)
"""

import zuspec.dataclasses as zdc
from typing import Optional, Callable


def sign_extend(value: int, bits: int) -> int:
    """Sign extend a value from 'bits' width to 64 bits."""
    sign_bit = 1 << (bits - 1)
    return (value & ((1 << bits) - 1)) - 2 * (value & sign_bit)


def sign_extend_32(value: int) -> int:
    """Sign extend a 32-bit value to 64 bits."""
    return sign_extend(value, 32)


def to_signed_64(value: int) -> int:
    """Convert unsigned 64-bit value to signed."""
    return sign_extend(value & 0xFFFFFFFFFFFFFFFF, 64)


def to_unsigned_64(value: int) -> int:
    """Mask to 64-bit unsigned."""
    return value & 0xFFFFFFFFFFFFFFFF


def to_unsigned_32(value: int) -> int:
    """Mask to 32-bit unsigned."""
    return value & 0xFFFFFFFF


@zdc.dataclass
class Rv64XF(zdc.Component):
    """RV64I Transfer-Function Model
    
    A functional model of the RISC-V 64-bit base integer instruction set.
    This model executes instructions without timing accuracy, suitable for
    fast simulation and software development.
    
    Attributes:
        memif: Memory interface for instruction fetch and load/store operations
        reset_v: Reset vector - address to start fetching from on reset
        running: Flag indicating if the processor is running
        halted: Flag indicating if EBREAK was executed
    """
    memif: zdc.MemIF = zdc.port()
    reset_v: zdc.uint64_t = zdc.field(default=0x80000000)
    running: bool = zdc.field(default=False)
    halted: bool = zdc.field(default=False)
    
    # Program counter
    _pc: zdc.uint64_t = zdc.field(default=0)
    
    # General-purpose registers x0-x31 (x0 is always 0)
    _regs: list = zdc.field(default_factory=lambda: [0] * 32)
    
    # Instruction count for debugging/profiling
    _instr_count: int = zdc.field(default=0)
    
    # Optional ECALL handler callback
    _ecall_handler: Optional[Callable[['Rv64XF'], None]] = zdc.field(default=None)
    
    def reset(self):
        """Reset the processor state."""
        self._pc = self.reset_v
        self._regs = [0] * 32
        self._instr_count = 0
        self.halted = False
        self.running = False
    
    def get_reg(self, idx: int) -> int:
        """Read a general-purpose register."""
        if idx == 0:
            return 0
        return self._regs[idx] & 0xFFFFFFFFFFFFFFFF
    
    def set_reg(self, idx: int, value: int):
        """Write a general-purpose register (x0 writes are ignored)."""
        if idx != 0:
            self._regs[idx] = value & 0xFFFFFFFFFFFFFFFF
    
    @property
    def pc(self) -> int:
        """Get the current program counter."""
        return self._pc
    
    @pc.setter
    def pc(self, value: int):
        """Set the program counter."""
        self._pc = value & 0xFFFFFFFFFFFFFFFF
    
    def set_ecall_handler(self, handler: Callable[['Rv64XF'], None]):
        """Set a callback for ECALL instructions."""
        self._ecall_handler = handler
    
    async def fetch(self) -> int:
        """Fetch a 32-bit instruction from memory."""
        return await self.memif.read32(self._pc)
    
    async def step(self) -> bool:
        """Execute one instruction. Returns True if execution should continue."""
        if self.halted:
            return False
            
        instr = await self.fetch()
        self._instr_count += 1
        
        # Decode opcode (bits 6:0)
        opcode = instr & 0x7F
        
        # Extract common fields
        rd = (instr >> 7) & 0x1F
        funct3 = (instr >> 12) & 0x7
        rs1 = (instr >> 15) & 0x1F
        rs2 = (instr >> 20) & 0x1F
        funct7 = (instr >> 25) & 0x7F
        
        # Default: advance PC by 4
        next_pc = self._pc + 4
        
        if opcode == 0x37:  # LUI
            imm = instr & 0xFFFFF000
            self.set_reg(rd, sign_extend_32(imm))
            
        elif opcode == 0x17:  # AUIPC
            imm = instr & 0xFFFFF000
            self.set_reg(rd, to_unsigned_64(self._pc + sign_extend_32(imm)))
            
        elif opcode == 0x6F:  # JAL
            # J-type immediate
            imm = (((instr >> 31) & 1) << 20 |
                   ((instr >> 12) & 0xFF) << 12 |
                   ((instr >> 20) & 1) << 11 |
                   ((instr >> 21) & 0x3FF) << 1)
            imm = sign_extend(imm, 21)
            self.set_reg(rd, next_pc)
            next_pc = to_unsigned_64(self._pc + imm)
            
        elif opcode == 0x67:  # JALR
            # I-type immediate
            imm = sign_extend(instr >> 20, 12)
            target = (self.get_reg(rs1) + imm) & ~1  # Clear LSB
            self.set_reg(rd, next_pc)
            next_pc = to_unsigned_64(target)
            
        elif opcode == 0x63:  # Branch instructions
            # B-type immediate
            imm = (((instr >> 31) & 1) << 12 |
                   ((instr >> 7) & 1) << 11 |
                   ((instr >> 25) & 0x3F) << 5 |
                   ((instr >> 8) & 0xF) << 1)
            imm = sign_extend(imm, 13)
            
            rs1_val = self.get_reg(rs1)
            rs2_val = self.get_reg(rs2)
            rs1_signed = to_signed_64(rs1_val)
            rs2_signed = to_signed_64(rs2_val)
            
            take_branch = False
            if funct3 == 0x0:  # BEQ
                take_branch = rs1_val == rs2_val
            elif funct3 == 0x1:  # BNE
                take_branch = rs1_val != rs2_val
            elif funct3 == 0x4:  # BLT
                take_branch = rs1_signed < rs2_signed
            elif funct3 == 0x5:  # BGE
                take_branch = rs1_signed >= rs2_signed
            elif funct3 == 0x6:  # BLTU
                take_branch = rs1_val < rs2_val
            elif funct3 == 0x7:  # BGEU
                take_branch = rs1_val >= rs2_val
                
            if take_branch:
                next_pc = to_unsigned_64(self._pc + imm)
                
        elif opcode == 0x03:  # Load instructions
            imm = sign_extend(instr >> 20, 12)
            addr = to_unsigned_64(self.get_reg(rs1) + imm)
            
            if funct3 == 0x0:  # LB
                data = await self.memif.read8(addr)
                self.set_reg(rd, sign_extend(data, 8))
            elif funct3 == 0x1:  # LH
                data = await self.memif.read16(addr)
                self.set_reg(rd, sign_extend(data, 16))
            elif funct3 == 0x2:  # LW
                data = await self.memif.read32(addr)
                self.set_reg(rd, sign_extend_32(data))
            elif funct3 == 0x3:  # LD (RV64I)
                data = await self.memif.read64(addr)
                self.set_reg(rd, data)
            elif funct3 == 0x4:  # LBU
                data = await self.memif.read8(addr)
                self.set_reg(rd, data & 0xFF)
            elif funct3 == 0x5:  # LHU
                data = await self.memif.read16(addr)
                self.set_reg(rd, data & 0xFFFF)
            elif funct3 == 0x6:  # LWU (RV64I)
                data = await self.memif.read32(addr)
                self.set_reg(rd, data & 0xFFFFFFFF)
                
        elif opcode == 0x23:  # Store instructions
            # S-type immediate
            imm = sign_extend(((instr >> 25) << 5) | ((instr >> 7) & 0x1F), 12)
            addr = to_unsigned_64(self.get_reg(rs1) + imm)
            rs2_val = self.get_reg(rs2)
            
            if funct3 == 0x0:  # SB
                await self.memif.write8(addr, rs2_val & 0xFF)
            elif funct3 == 0x1:  # SH
                await self.memif.write16(addr, rs2_val & 0xFFFF)
            elif funct3 == 0x2:  # SW
                await self.memif.write32(addr, rs2_val & 0xFFFFFFFF)
            elif funct3 == 0x3:  # SD (RV64I)
                await self.memif.write64(addr, rs2_val)
                
        elif opcode == 0x13:  # Integer Register-Immediate instructions
            imm = sign_extend(instr >> 20, 12)
            rs1_val = self.get_reg(rs1)
            shamt = (instr >> 20) & 0x3F  # 6 bits for RV64I
            
            if funct3 == 0x0:  # ADDI
                self.set_reg(rd, to_unsigned_64(rs1_val + imm))
            elif funct3 == 0x2:  # SLTI
                self.set_reg(rd, 1 if to_signed_64(rs1_val) < imm else 0)
            elif funct3 == 0x3:  # SLTIU
                self.set_reg(rd, 1 if rs1_val < (imm & 0xFFFFFFFFFFFFFFFF) else 0)
            elif funct3 == 0x4:  # XORI
                self.set_reg(rd, to_unsigned_64(rs1_val ^ imm))
            elif funct3 == 0x6:  # ORI
                self.set_reg(rd, to_unsigned_64(rs1_val | imm))
            elif funct3 == 0x7:  # ANDI
                self.set_reg(rd, to_unsigned_64(rs1_val & imm))
            elif funct3 == 0x1:  # SLLI
                self.set_reg(rd, to_unsigned_64(rs1_val << shamt))
            elif funct3 == 0x5:  # SRLI/SRAI
                if (instr >> 26) & 0x3F == 0:  # SRLI
                    self.set_reg(rd, rs1_val >> shamt)
                else:  # SRAI
                    self.set_reg(rd, to_unsigned_64(to_signed_64(rs1_val) >> shamt))
                    
        elif opcode == 0x1B:  # RV64I-only: *W instructions (immediate)
            imm = sign_extend(instr >> 20, 12)
            rs1_val = to_unsigned_32(self.get_reg(rs1))
            shamt = (instr >> 20) & 0x1F  # 5 bits for 32-bit ops
            
            if funct3 == 0x0:  # ADDIW
                result = to_unsigned_32(rs1_val + imm)
                self.set_reg(rd, sign_extend_32(result))
            elif funct3 == 0x1:  # SLLIW
                result = to_unsigned_32(rs1_val << shamt)
                self.set_reg(rd, sign_extend_32(result))
            elif funct3 == 0x5:  # SRLIW/SRAIW
                if funct7 == 0:  # SRLIW
                    result = rs1_val >> shamt
                    self.set_reg(rd, sign_extend_32(result))
                else:  # SRAIW
                    result = to_unsigned_32(sign_extend_32(rs1_val) >> shamt)
                    self.set_reg(rd, sign_extend_32(result))
                    
        elif opcode == 0x33:  # Integer Register-Register instructions
            rs1_val = self.get_reg(rs1)
            rs2_val = self.get_reg(rs2)
            shamt = rs2_val & 0x3F  # Lower 6 bits for shift amount
            
            if funct3 == 0x0:
                if funct7 == 0:  # ADD
                    self.set_reg(rd, to_unsigned_64(rs1_val + rs2_val))
                else:  # SUB
                    self.set_reg(rd, to_unsigned_64(rs1_val - rs2_val))
            elif funct3 == 0x1:  # SLL
                self.set_reg(rd, to_unsigned_64(rs1_val << shamt))
            elif funct3 == 0x2:  # SLT
                self.set_reg(rd, 1 if to_signed_64(rs1_val) < to_signed_64(rs2_val) else 0)
            elif funct3 == 0x3:  # SLTU
                self.set_reg(rd, 1 if rs1_val < rs2_val else 0)
            elif funct3 == 0x4:  # XOR
                self.set_reg(rd, rs1_val ^ rs2_val)
            elif funct3 == 0x5:
                if funct7 == 0:  # SRL
                    self.set_reg(rd, rs1_val >> shamt)
                else:  # SRA
                    self.set_reg(rd, to_unsigned_64(to_signed_64(rs1_val) >> shamt))
            elif funct3 == 0x6:  # OR
                self.set_reg(rd, rs1_val | rs2_val)
            elif funct3 == 0x7:  # AND
                self.set_reg(rd, rs1_val & rs2_val)
                
        elif opcode == 0x3B:  # RV64I-only: *W register-register instructions
            rs1_val = to_unsigned_32(self.get_reg(rs1))
            rs2_val = to_unsigned_32(self.get_reg(rs2))
            shamt = rs2_val & 0x1F  # Lower 5 bits for 32-bit shifts
            
            if funct3 == 0x0:
                if funct7 == 0:  # ADDW
                    result = to_unsigned_32(rs1_val + rs2_val)
                    self.set_reg(rd, sign_extend_32(result))
                else:  # SUBW
                    result = to_unsigned_32(rs1_val - rs2_val)
                    self.set_reg(rd, sign_extend_32(result))
            elif funct3 == 0x1:  # SLLW
                result = to_unsigned_32(rs1_val << shamt)
                self.set_reg(rd, sign_extend_32(result))
            elif funct3 == 0x5:
                if funct7 == 0:  # SRLW
                    result = rs1_val >> shamt
                    self.set_reg(rd, sign_extend_32(result))
                else:  # SRAW
                    result = to_unsigned_32(sign_extend_32(rs1_val) >> shamt)
                    self.set_reg(rd, sign_extend_32(result))
                    
        elif opcode == 0x0F:  # FENCE/FENCE.I
            # No-op in this functional model
            pass
            
        elif opcode == 0x73:  # SYSTEM instructions
            if instr == 0x00000073:  # ECALL
                if self._ecall_handler:
                    self._ecall_handler(self)
            elif instr == 0x00100073:  # EBREAK
                self.halted = True
                return False
            # Other CSR instructions not implemented in base model
            
        else:
            # Unknown opcode - halt
            self.halted = True
            return False
        
        self._pc = next_pc
        return True
    
    async def run(self, max_instructions: int = 0) -> int:
        """Run the processor until halt or max_instructions reached.
        
        Args:
            max_instructions: Maximum instructions to execute (0 = unlimited)
            
        Returns:
            Number of instructions executed
        """
        self.running = True
        self.halted = False
        count = 0
        
        while self.running and not self.halted:
            if max_instructions > 0 and count >= max_instructions:
                break
            if not await self.step():
                break
            count += 1
            
        self.running = False
        return count
    
    @zdc.process
    async def _run(self):
        """Process entry point - reset and wait."""
        self.reset()
