import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages', 'zuspec-dm', 'src'))

import zuspec.dataclasses as zdc

def test_memory_basic():
    """Test basic memory read/write operations"""
    
    @zdc.dataclass
    class Top(zdc.Component):
        mem : zdc.Memory[zdc.uint32_t] = zdc.field(size=1024)

        def run(self):
            # Test basic write and read
            self.mem.write(0, 25)
            assert self.mem.read(0) == 25
            
            # Test another location
            self.mem.write(100, 0xDEADBEEF)
            assert self.mem.read(100) == 0xDEADBEEF
            
            # Test that unwritten locations return 0
            assert self.mem.read(50) == 0

    t = Top()
    t.run()
    print("test_memory_basic PASSED")

def test_memory_uint8():
    """Test memory with uint8_t element type"""
    
    @zdc.dataclass
    class Top(zdc.Component):
        mem : zdc.Memory[zdc.uint8_t] = zdc.field(size=256)

        def run(self):
            # Test basic write and read
            self.mem.write(0, 0xFF)
            assert self.mem.read(0) == 0xFF
            
            # Test overflow masking (8-bit values)
            self.mem.write(1, 0x1FF)  # Should be masked to 0xFF
            assert self.mem.read(1) == 0xFF
            
            self.mem.write(2, 0xAB)
            assert self.mem.read(2) == 0xAB

    t = Top()
    t.run()
    print("test_memory_uint8 PASSED")

def test_memory_uint64():
    """Test memory with uint64_t element type"""
    
    @zdc.dataclass
    class Top(zdc.Component):
        mem : zdc.Memory[zdc.uint64_t] = zdc.field(size=512)

        def run(self):
            # Test large values
            self.mem.write(0, 0xDEADBEEFCAFEBABE)
            assert self.mem.read(0) == 0xDEADBEEFCAFEBABE
            
            self.mem.write(511, 0xFFFFFFFFFFFFFFFF)
            assert self.mem.read(511) == 0xFFFFFFFFFFFFFFFF

    t = Top()
    t.run()
    print("test_memory_uint64 PASSED")

def test_memory_bounds():
    """Test memory bounds checking"""
    
    @zdc.dataclass
    class Top(zdc.Component):
        mem : zdc.Memory[zdc.uint32_t] = zdc.field(size=100)

        def run(self):
            # Valid access
            self.mem.write(0, 10)
            self.mem.write(99, 20)
            assert self.mem.read(0) == 10
            assert self.mem.read(99) == 20
            
            # Test out of bounds read
            try:
                self.mem.read(100)
                assert False, "Should have raised IndexError"
            except IndexError as e:
                assert "out of bounds" in str(e)
            
            # Test out of bounds write
            try:
                self.mem.write(100, 30)
                assert False, "Should have raised IndexError"
            except IndexError as e:
                assert "out of bounds" in str(e)
            
            # Test negative index
            try:
                self.mem.read(-1)
                assert False, "Should have raised IndexError"
            except IndexError as e:
                assert "out of bounds" in str(e)

    t = Top()
    t.run()
    print("test_memory_bounds PASSED")

def test_memory_multiple():
    """Test multiple memory instances in one component"""
    
    @zdc.dataclass
    class Top(zdc.Component):
        mem1 : zdc.Memory[zdc.uint32_t] = zdc.field(size=128)
        mem2 : zdc.Memory[zdc.uint16_t] = zdc.field(size=256)

        def run(self):
            # Write to both memories
            self.mem1.write(0, 0x12345678)
            self.mem2.write(0, 0xABCD)
            
            # Verify independent storage
            assert self.mem1.read(0) == 0x12345678
            assert self.mem2.read(0) == 0xABCD
            
            # Verify different widths
            assert self.mem1.width == 32
            assert self.mem2.width == 16
            
            # Verify different sizes
            assert self.mem1.size == 128
            assert self.mem2.size == 256

    t = Top()
    t.run()
    print("test_memory_multiple PASSED")

def test_memory_sparse():
    """Test that memory is sparse (doesn't allocate all elements)"""
    
    @zdc.dataclass
    class Top(zdc.Component):
        mem : zdc.Memory[zdc.uint32_t] = zdc.field(size=1000000)  # 1M elements

        def run(self):
            # Write to scattered addresses
            self.mem.write(0, 1)
            self.mem.write(500000, 2)
            self.mem.write(999999, 3)
            
            # Verify reads
            assert self.mem.read(0) == 1
            assert self.mem.read(500000) == 2
            assert self.mem.read(999999) == 3
            
            # Verify unwritten locations
            assert self.mem.read(1) == 0
            assert self.mem.read(100000) == 0

    t = Top()
    t.run()
    print("test_memory_sparse PASSED")

def test_memory_overwrite():
    """Test that memory values can be overwritten"""
    
    @zdc.dataclass
    class Top(zdc.Component):
        mem : zdc.Memory[zdc.uint32_t] = zdc.field(size=100)

        def run(self):
            # Write initial value
            self.mem.write(0, 100)
            assert self.mem.read(0) == 100
            
            # Overwrite with new value
            self.mem.write(0, 200)
            assert self.mem.read(0) == 200
            
            # Overwrite multiple times
            for i in range(10):
                self.mem.write(0, i)
                assert self.mem.read(0) == i

    t = Top()
    t.run()
    print("test_memory_overwrite PASSED")

if __name__ == '__main__':
    test_memory_basic()
    test_memory_uint8()
    test_memory_uint64()
    test_memory_bounds()
    test_memory_multiple()
    test_memory_sparse()
    test_memory_overwrite()
    print("\nAll memory tests PASSED!")
