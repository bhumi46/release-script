#!/usr/bin/env python3

import yaml
import logging
import os
import sys

# Add the current directory to Python path
sys.path.append('/home/bhuminathan/rapid-deployment/imgtransfer/release-script/release/vidivi')

# Import vidivi functions
from vidivi import process_image, print_log, get_manifest_list

# Set up logging  
logging.basicConfig(level=logging.INFO)

def test_crane_transfer():
    print("=== Testing Crane Multi-Arch Transfer ===")
    
    # Load config
    with open('config.yml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Test image details
    srcImgName = "resident-service"
    srcImgtag = "1.2.1.2"
    destImgtag = "1.2.1.2-crane-direct"
    full_src_img_name = "mosipid/resident-service"
    
    # Test if this is multi-arch first
    manifest_list = get_manifest_list(full_src_img_name, srcImgtag)
    if manifest_list:
        print(f"Found multi-arch image with {len(manifest_list['manifests'])} architectures")
        for manifest in manifest_list['manifests']:
            arch = manifest['platform']['architecture']
            os_name = manifest['platform']['os'] 
            print(f"  - {os_name}/{arch}")
        
        # Run the process_image function directly
        try:
            process_image(config, srcImgName, srcImgtag, destImgtag, full_src_img_name, manifest_list)
            print("✅ Transfer completed successfully!")
            
            # Verify the result
            import subprocess
            result = subprocess.run([
                "crane", "manifest", "--insecure", 
                f"10.0.3.128:8080/mosipid/resident-service:{destImgtag}"
            ], capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                import json
                manifest = json.loads(result.stdout)
                media_type = manifest.get('mediaType', 'unknown')
                print(f"✅ Result manifest type: {media_type}")
                
                if 'manifests' in manifest:
                    print(f"✅ Multi-arch manifest with {len(manifest['manifests'])} architectures:")
                    for m in manifest['manifests']:
                        print(f"    - {m['platform']['os']}/{m['platform']['architecture']}")
                else:
                    print("❌ Single architecture manifest")
            else:
                print(f"❌ Failed to check result: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Transfer failed: {e}")
    else:
        print("❌ Not a multi-arch image")

if __name__ == "__main__":
    test_crane_transfer()