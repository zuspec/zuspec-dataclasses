"""Tests for the Time class."""

import zuspec.dataclasses as zdc


def test_time_scalar_mul_int():
    """Test Time multiplication by integer."""
    t = zdc.Time.ns(10)
    result = t * 5
    
    assert result.unit == zdc.TimeUnit.NS
    assert result.amt == 50
    

def test_time_scalar_mul_float():
    """Test Time multiplication by float."""
    t = zdc.Time.us(100)
    result = t * 2.5
    
    assert result.unit == zdc.TimeUnit.US
    assert result.amt == 250.0


def test_time_rmul_int():
    """Test integer * Time (right multiplication)."""
    t = zdc.Time.ms(5)
    result = 3 * t
    
    assert result.unit == zdc.TimeUnit.MS
    assert result.amt == 15


def test_time_rmul_float():
    """Test float * Time (right multiplication)."""
    t = zdc.Time.ns(20)
    result = 0.5 * t
    
    assert result.unit == zdc.TimeUnit.NS
    assert result.amt == 10.0


def test_time_mul_time_same_unit():
    """Test Time * Time with same units."""
    t1 = zdc.Time.ns(10)
    t2 = zdc.Time.ns(5)
    result = t1 * t2
    
    assert result.unit == zdc.TimeUnit.NS
    assert result.amt == 50  # 10 * 5 = 50


def test_time_mul_time_different_units():
    """Test Time * Time with different units - result uses finer unit."""
    t1 = zdc.Time.us(2)  # 2 microseconds = 2000 nanoseconds
    t2 = zdc.Time.ns(3)  # 3 nanoseconds
    result = t1 * t2
    
    # Result should be in NS (finer unit)
    # 2us = 2000ns, 3ns = 3ns
    # 2000 * 3 = 6000 ns
    assert result.unit == zdc.TimeUnit.NS
    assert result.amt == 6000


def test_time_mul_time_ms_us():
    """Test Time * Time with ms and us."""
    t1 = zdc.Time.ms(1)   # 1 millisecond = 1000 microseconds
    t2 = zdc.Time.us(10)  # 10 microseconds
    result = t1 * t2
    
    # Result should be in US (finer unit)
    # 1ms = 1000us, 10us = 10us
    # 1000 * 10 = 10000 us
    assert result.unit == zdc.TimeUnit.US
    assert result.amt == 10000


def test_time_mul_time_s_ns():
    """Test Time * Time with seconds and nanoseconds."""
    t1 = zdc.Time.s(1)    # 1 second = 1e9 nanoseconds
    t2 = zdc.Time.ns(2)   # 2 nanoseconds
    result = t1 * t2
    
    # Result should be in NS (finer unit)
    # 1s = 1e9 ns, 2ns = 2ns
    # 1e9 * 2 = 2e9 ns
    assert result.unit == zdc.TimeUnit.NS
    assert result.amt == 2e9


def test_time_convert_to_unit():
    """Test the internal _convert_to_unit method."""
    t = zdc.Time.us(1)  # 1 microsecond
    
    # Convert to nanoseconds (finer)
    ns_amt = t._convert_to_unit(zdc.TimeUnit.NS)
    assert ns_amt == 1000  # 1us = 1000ns
    
    # Convert to milliseconds (coarser)
    ms_amt = t._convert_to_unit(zdc.TimeUnit.MS)
    assert ms_amt == 0.001  # 1us = 0.001ms


def test_time_str():
    """Test Time string representation."""
    assert str(zdc.Time.s(1)) == "1s"
    assert str(zdc.Time.ms(10)) == "10ms"
    assert str(zdc.Time.us(100)) == "100us"
    assert str(zdc.Time.ns(1000)) == "1000ns"
    assert str(zdc.Time.ps(5)) == "5ps"
    assert str(zdc.Time.fs(2)) == "2fs"


def test_time_delta():
    """Test Time.delta() singleton."""
    d1 = zdc.Time.delta()
    d2 = zdc.Time.delta()
    
    assert d1 is d2  # Should be same instance
    assert d1.amt == 0
    assert d1.unit == zdc.TimeUnit.S
