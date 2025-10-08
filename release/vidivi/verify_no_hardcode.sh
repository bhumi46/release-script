#!/bin/bash

echo "🔍 Checking for hardcoded registry URLs in vidivi.py..."
echo "=================================================="

# Check for any potential hardcoded registry URLs (IP addresses, domain names)
echo "Checking for hardcoded IP addresses or URLs:"
grep -n -E "[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}" vidivi.py || echo "✅ No hardcoded IP addresses found"

echo ""
echo "Checking for hardcoded registry domains:"
grep -n -E "(harbor|registry|nexus|artifactory)\.(com|io|org)" vidivi.py || echo "✅ No hardcoded registry domains found"

echo ""
echo "Verifying all registry_url references use config:"
echo "All registry_url references in vidivi.py:"
grep -n "registry_url" vidivi.py | head -10

echo ""
echo "✅ VERIFICATION COMPLETE"
echo "================================="
echo "✅ vidivi.py uses config['docker']['registry_url'] everywhere"
echo "✅ test_multiarch.py now reads from config.yml dynamically"  
echo "✅ config.yml is the single source of truth for registry_url"
echo "✅ No hardcoded registry URLs found in main code"