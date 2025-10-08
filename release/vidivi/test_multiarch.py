#!/usr/bin/env python3

import docker
import requests
import json
import base64
import yaml

def check_multiarch_support():
    """Test script to verify multi-arch support in transferred images"""
    
    # Load config to get registry URL
    with open("config.yml", "r") as configfile:
        config = yaml.safe_load(configfile)
    
    registry_url = config['docker']['registry_url']
    destination_org = config['docker']['destination_organization']
    
    # Test 1: Check original Docker Hub image
    print("=== Testing Original Docker Hub Image ===")
    try:
        client = docker.from_env()
        
        # Get manifest from Docker Hub
        auth_url = "https://auth.docker.io/token?service=registry.docker.io&scope=repository:mosipid/resident-service:pull"
        auth_response = requests.get(auth_url)
        token = auth_response.json()['token']
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.docker.distribution.manifest.v2+json'
        }
        
        manifest_url = "https://registry-1.docker.io/v2/mosipid/resident-service/manifests/1.2.1.2"
        manifest_response = requests.get(manifest_url, headers=headers)
        
        if manifest_response.status_code == 200:
            manifest = manifest_response.json()
            print(f"Docker Hub manifest type: {manifest.get('mediaType', 'Unknown')}")
            if 'manifests' in manifest:
                print(f"Number of architectures: {len(manifest['manifests'])}")
                for m in manifest['manifests']:
                    platform = m.get('platform', {})
                    print(f"  - {platform.get('os', 'unknown')}/{platform.get('architecture', 'unknown')}")
            else:
                print("Single architecture image")
        else:
            print(f"Failed to get Docker Hub manifest: {manifest_response.status_code}")
    
    except Exception as e:
        print(f"Error checking Docker Hub: {e}")
    
    print(f"\n=== Testing {registry_url} Image ===")
    
    # Test 2: Check Harbor image (simpler approach - just try to pull different architectures)
    harbor_image = f"{registry_url}/{destination_org}/resident-service:1.2.1.2"
    
    # Test AMD64
    try:
        result = client.api.pull(harbor_image, platform="linux/amd64", stream=False)
        print(f"✅ AMD64 architecture available in {registry_url}")
    except Exception as e:
        print(f"❌ AMD64 not available: {e}")
    
    # Test ARM64
    try:
        result = client.api.pull(harbor_image, platform="linux/arm64", stream=False) 
        print(f"✅ ARM64 architecture available in {registry_url}")
    except Exception as e:
        print(f"❌ ARM64 not available: {e}")
    
    # Test 3: Check what we have locally
    print("\n=== Local Images ===")
    try:
        images = client.images.list()
        for img in images:
            if 'resident-service' in str(img.tags):
                print(f"Local image: {img.tags}")
                try:
                    # Get detailed info
                    inspect = client.api.inspect_image(img.id)
                    arch = inspect.get('Architecture', 'unknown')
                    os = inspect.get('Os', 'unknown')
                    print(f"  Architecture: {os}/{arch}")
                except Exception as e:
                    print(f"  Could not inspect: {e}")
    except Exception as e:
        print(f"Error listing local images: {e}")

if __name__ == "__main__":
    check_multiarch_support()