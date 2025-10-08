#!/usr/bin/env python3

import re

def parse_vidivi_log():
    log_file = 'logs/vidivi.log'
    
    # Extract all images from the beginning of the log
    with open(log_file, 'r') as f:
        content = f.read()
    
    # Find all images that were processed
    images_pattern = r'IMAGES= \[(.*?)\]'
    images_match = re.search(images_pattern, content, re.DOTALL)
    
    if images_match:
        images_str = images_match.group(1)
        # Extract individual image entries
        image_entries = re.findall(r"'([^']+:[^']+)', '[^']+'", images_str)
        all_images = set(image_entries)
    else:
        all_images = set()
    
    # Find successfully completed images
    completed_pattern = r'Completed ([^\s]+:[^\s]+)\s+----->'
    completed_images = set(re.findall(completed_pattern, content))
    
    # Find images that failed with specific errors
    failed_patterns = [
        r'ERROR.*Image "([^"]+)" does not exist',
        r'ERROR.*Failed to get manifest for ([^\s]+)',
        r'ERROR.*Crane transfer failed.*Error: fetching "([^"]+)"'
    ]
    
    failed_images = set()
    for pattern in failed_patterns:
        failed_images.update(re.findall(pattern, content))
    
    # Find crane multi-arch successful transfers
    crane_pattern = r'Executing: crane copy --insecure ([^\s]+:[^\s]+) '
    crane_success_pattern = r'Successfully transferred multi-arch manifest list with crane'
    
    crane_images = set()
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'Successfully transferred multi-arch manifest list with crane' in line:
            # Look backwards for the crane command
            for j in range(max(0, i-10), i):
                crane_match = re.search(crane_pattern, lines[j])
                if crane_match:
                    crane_images.add(crane_match.group(1))
                    break
    
    # Calculate final status
    success_images = completed_images - failed_images
    truly_failed = (all_images - completed_images) | (failed_images - completed_images)
    
    return {
        'all_images': sorted(all_images),
        'successful': sorted(success_images), 
        'failed': sorted(truly_failed),
        'crane_multiarch': sorted(crane_images),
        'total_all': len(all_images),
        'total_success': len(success_images),
        'total_failed': len(truly_failed),
        'total_crane': len(crane_images)
    }

def main():
    results = parse_vidivi_log()
    
    print("=" * 80)
    print("📊 VIDIVI IMAGE TRANSFER RESULTS SUMMARY")
    print("=" * 80)
    
    print(f"\n📈 OVERALL STATISTICS:")
    print(f"   Total Images Processed: {results['total_all']}")
    print(f"   ✅ Successfully Transferred: {results['total_success']}")
    print(f"   ❌ Failed Transfers: {results['total_failed']}")
    print(f"   🚀 Multi-Arch with Crane: {results['total_crane']}")
    print(f"   Success Rate: {results['total_success']/results['total_all']*100:.1f}%")
    
    print(f"\n✅ SUCCESSFULLY TRANSFERRED IMAGES ({results['total_success']}):")
    print("-" * 60)
    for i, img in enumerate(results['successful'], 1):
        marker = "🚀" if img in results['crane_multiarch'] else "📦"
        print(f"{i:2d}. {marker} {img}")
    
    print(f"\n❌ FAILED IMAGES ({results['total_failed']}):")
    print("-" * 60)
    for i, img in enumerate(results['failed'], 1):
        print(f"{i:2d}. ❌ {img}")
    
    print(f"\n🚀 CRANE MULTI-ARCH TRANSFERS ({results['total_crane']}):")
    print("-" * 60)
    for i, img in enumerate(results['crane_multiarch'], 1):
        print(f"{i:2d}. 🚀 {img}")
    
    print("\n" + "=" * 80)
    print("Legend: 🚀 = Multi-arch with Crane, 📦 = Single-arch transfer")
    print("=" * 80)

if __name__ == "__main__":
    main()