#!/usr/bin/env python3

import yaml
import subprocess

def test_crane_flexibility():
    print("=== Testing Crane HTTP/HTTPS Flexibility ===")
    
    # Test 1: HTTP Registry (current Harbor setup)
    print("\n1. Testing HTTP Registry (Harbor):")
    http_cmd = [
        "crane", "copy", "--insecure",
        "mosipid/resident-service:1.2.1.2",
        "10.0.3.128:8080/mosipid/resident-service:http-test"
    ]
    print(f"Command: {' '.join(http_cmd)}")
    result = subprocess.run(http_cmd, capture_output=True, text=True, check=False)
    if result.returncode == 0:
        print("✅ HTTP Registry: SUCCESS")
    else:
        print(f"❌ HTTP Registry: FAILED - {result.stderr}")
    
    # Test 2: HTTPS Registry (Docker Hub to Docker Hub)
    print("\n2. Testing HTTPS Registry (Docker Hub):")
    # Note: This would normally require push permissions, so we'll just test manifest inspection
    https_cmd = ["crane", "manifest", "mosipid/resident-service:1.2.1.2"]
    print(f"Command: {' '.join(https_cmd)}")
    result = subprocess.run(https_cmd, capture_output=True, text=True, check=False)
    if result.returncode == 0:
        print("✅ HTTPS Registry: SUCCESS")
        print("    Manifest retrieved successfully from Docker Hub")
    else:
        print(f"❌ HTTPS Registry: FAILED - {result.stderr}")
    
    # Test 3: Check config detection logic
    print("\n3. Testing Config Detection Logic:")
    
    test_configs = [
        "http://10.0.3.128:8080",      # HTTP - should use --insecure
        "https://harbor.example.com",   # HTTPS - should NOT use --insecure  
        "10.0.3.128:8080",             # No protocol - should use --insecure
        "harbor.example.com",          # No protocol - should use --insecure (assumed HTTP)
    ]
    
    for registry_url in test_configs:
        use_insecure = registry_url.startswith('http://') or not registry_url.startswith('https://')
        flag_status = "--insecure" if use_insecure else "secure"
        print(f"    {registry_url:<25} → {flag_status}")

if __name__ == "__main__":
    test_crane_flexibility()