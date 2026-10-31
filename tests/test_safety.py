import pytest
from soar.safety import is_whitelisted_ip, assert_not_whitelisted, SafetyViolation

SAMPLE_WHITELIST = [
    "127.0.0.0/8",
    "10.0.0.0/8",
    "192.168.1.1",
    "::1",
    "1.1.1.1",
]

def test_whitelist_ip_detection():
    # Loopback
    assert is_whitelisted_ip("127.0.0.1", SAMPLE_WHITELIST) is True
    assert is_whitelisted_ip("127.0.0.50", SAMPLE_WHITELIST) is True
    
    # Private CIDR
    assert is_whitelisted_ip("10.50.1.20", SAMPLE_WHITELIST) is True
    
    # Single IP
    assert is_whitelisted_ip("192.168.1.1", SAMPLE_WHITELIST) is True
    assert is_whitelisted_ip("1.1.1.1", SAMPLE_WHITELIST) is True
    
    # External attacker IP (NOT whitelisted)
    assert is_whitelisted_ip("198.51.100.45", SAMPLE_WHITELIST) is False
    assert is_whitelisted_ip("203.0.113.88", SAMPLE_WHITELIST) is False
    
    # Invalid IP
    assert is_whitelisted_ip("not-an-ip", SAMPLE_WHITELIST) is False
    assert is_whitelisted_ip("", SAMPLE_WHITELIST) is False
    assert is_whitelisted_ip(None, SAMPLE_WHITELIST) is False

def test_assert_not_whitelisted_raises_violation():
    with pytest.raises(SafetyViolation):
        assert_not_whitelisted("127.0.0.1", SAMPLE_WHITELIST)
        
    with pytest.raises(SafetyViolation):
        assert_not_whitelisted("10.0.0.1", SAMPLE_WHITELIST)

    # Should not raise for untrusted attacker IP
    assert_not_whitelisted("198.51.100.45", SAMPLE_WHITELIST)
