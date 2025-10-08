#!/usr/bin/env python3

import requests
import json
import base64
from urllib.parse import quote

# Harbor configuration
HARBOR_URL = "http://10.0.3.128:8080"
USERNAME = "robot$mosipid"
PASSWORD = "tydf6FU5YjMLP62iYBKOY9UqtaiMWeTt"
PROJECT = "mosipid"

# Images to verify (from user's list)
IMAGES_TO_VERIFY = [
    ("mosipid/mock-abis", "1.2.0.2"),
    ("mosipid/mock-mv", "1.2.0.2"),
    ("mosipid/hotlist-service", "1.2.1.3"),
    ("mosipid/admin-service", "1.2.1.3"),
    ("mosipid/biosdk-server", "1.2.0.1"),
    ("mosipid/captcha-validation-service", "0.1.0-beta.1"),
    ("mosipid/config-server", "1.1.2"),
    ("mosipid/data-share-service", "1.2.0.2"),
    ("mosipid/authentication-service", "1.2.1.2-beta.1"),
    ("mosipid/authentication-internal-service", "1.2.1.2-beta.1"),
    ("mosipid/keys-generator", "1.2.0.1"),
    ("mosipid/authentication-otp-service", "1.2.1.2-beta.1"),
    ("mosipid/credential-service", "1.2.2.3"),
    ("mosipid/credential-request-generator", "1.2.2.3"),
    ("mosipid/id-repository-identity-service", "1.2.2.3"),
    ("mosipid/id-repository-salt-generator", "1.2.2.3"),
    ("mosipid/id-repository-vid-service", "1.2.2.3"),
    ("mosipid/kernel-auditmanager-service", "1.2.0.1"),
    ("mosipid/kernel-auth-service", "1.2.0.2"),
    ("mosipid/kernel-idgenerator-service", "1.2.0.2"),
    ("mosipid/kernel-masterdata-service", "1.2.1.3"),
    ("mosipid/kernel-notification-service", "1.2.0.2"),
    ("mosipid/kernel-otpmanager-service", "1.2.0.1"),
    ("mosipid/kernel-pridgenerator-service", "1.2.0.2"),
    ("mosipid/kernel-ridgenerator-service", "1.2.0.2"),
    ("mosipid/kernel-syncdata-service", "1.2.1.3"),
    ("mosipid/mosip-artemis-keycloak", "1.2.0.1"),
    ("mosipid/kernel-keymanager-service", "1.2.1.0"),
    ("mosipid/masterdata-loader", "1.2.0.1"),
    ("mosipid/mock-smtp", "1.0.0"),
    ("mosipid/commons-packet-service", "1.2.0.4"),
    ("mosipid/pmp-revamp-ui", "1.2.2.2"),
    ("mosipid/partner-management-service", "1.2.2.2"),
    ("mosipid/policy-management-service", "1.2.2.2"),
    ("mosipid/postgres-init", "1.2.0.1"),
    ("mosipid/pre-registration-application-service", "1.2.0.3"),
    ("mosipid/pre-registration-batchjob", "1.2.0.3"),
    ("mosipid/pre-registration-booking-service", "1.2.0.1"),
    ("mosipid/pre-registration-datasync-service", "1.2.0.3"),
    ("mosipid/pre-registration-ui", "1.2.0.1"),
    ("mosipid/print", "1.2.0.1"),
    ("mosipid/regclient-keystore", "1.3.0-beta.1"),
    ("mosipid/registration-client", "1.2.0.2"),
    ("mosipid/registration-processor-common-camel-bridge", "1.2.1.2"),
    ("mosipid/registration-processor-stage-group-1", "1.2.1.2"),
    ("mosipid/registration-processor-stage-group-2", "1.2.1.2"),
    ("mosipid/registration-processor-stage-group-3", "1.2.1.2"),
    ("mosipid/registration-processor-stage-group-4", "1.2.1.2"),
    ("mosipid/registration-processor-stage-group-5", "1.2.1.2"),
    ("mosipid/registration-processor-stage-group-6", "1.2.1.2"),
    ("mosipid/registration-processor-stage-group-7", "1.2.1.2"),
    ("mosipid/registration-processor-landing-zone", "1.2.1.2"),
    ("mosipid/registration-processor-notification-service", "1.2.1.2"),
    ("mosipid/registration-processor-dmz-packet-server", "1.2.1.2"),
    ("mosipid/registration-processor-reprocessor", "1.2.1.2"),
    ("mosipid/kernel-salt-generator", "1.2.0.2"),
    ("mosipid/registration-processor-registration-status-service", "1.2.1.2"),
    ("mosipid/registration-processor-registration-transaction-service", "1.2.1.2"),
    ("mosipid/registration-processor-workflow-manager-service", "1.2.1.2"),
    ("mosipid/resident-service", "1.2.1.2"),
    ("mosipid/resident-ui", "0.9.1"),
    ("mosipid/softhsm", "v2"),
    ("mosipid/websub-service", "1.2.0.1"),
    ("mosipid/consolidator-websub-service", "1.2.0.1"),
    ("mosipid/pre-registration-captcha-service", "1.2.0.2"),
    ("mosipid/partner-onboarder", "1.2.0.1"),
    ("mosipid/dsl-packetcreator", "1.2.1.0"),
    ("mosipid/apitest-prereg", "1.2.0.3"),
    ("mosipid/apitest-masterdata", "1.2.1.3"),
    ("mosipid/apitest-idrepo", "1.2.2.2"),
    ("mosipid/apitest-pms", "1.2.2.2"),
    ("mosipid/apitest-resident", "1.2.1.2"),
    ("mosipid/apitest-auth", "1.2.1.2-beta.1"),
    ("mosipid/dsl-orchestrator", "1.2.1.0"),
    ("mosipid/admintest", "1.2.0.1"),
    ("mosipid/pmptest", "1.2.0.2"),
]

def get_all_repositories():
    """Get all repositories from Harbor"""
    credentials = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "accept": "application/json"
    }
    
    url = f"{HARBOR_URL}/api/v2.0/projects/{PROJECT}/repositories?page_size=100"
    
    try:
        response = requests.get(url, headers=headers, verify=False)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching repositories: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error: {str(e)}")
        return []

def check_image_in_harbor(repo_name, tag, harbor_repos):
    """Check if a specific image tag exists in Harbor"""
    
    # First check if repository exists
    repo_exists = False
    for repo in harbor_repos:
        if repo['name'] == repo_name:
            repo_exists = True
            break
    
    if not repo_exists:
        return False, "Repository not found"
    
    # Create basic auth header
    credentials = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "accept": "application/json"
    }
    
    # Get artifacts for the repository
    encoded_repo = quote(repo_name, safe='')
    url = f"{HARBOR_URL}/api/v2.0/projects/{PROJECT}/repositories/{encoded_repo}/artifacts"
    
    try:
        response = requests.get(url, headers=headers, verify=False)
        if response.status_code == 200:
            artifacts = response.json()
            
            # Check if any artifact has the required tag
            available_tags = []
            tag_found = False
            
            for artifact in artifacts:
                if 'tags' in artifact and artifact['tags']:
                    for tag_info in artifact['tags']:
                        available_tags.append(tag_info['name'])
                        if tag_info['name'] == tag:
                            tag_found = True
            
            if tag_found:
                return True, "Found"
            else:
                return False, f"Tag not found. Available tags: {available_tags}"
            
        else:
            return False, f"API Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        return False, f"Error: {str(e)}"

def main():
    print("=" * 80)
    print("HARBOR IMAGE VERIFICATION REPORT")
    print("=" * 80)
    print(f"Harbor URL: {HARBOR_URL}")
    print(f"Project: {PROJECT}")
    print(f"Total images to verify: {len(IMAGES_TO_VERIFY)}")
    print("=" * 80)
    
    # Get all repositories first
    print("Fetching Harbor repositories...")
    harbor_repos = get_all_repositories()
    print(f"Found {len(harbor_repos)} repositories in Harbor")
    print("=" * 80)
    
    found_count = 0
    missing_count = 0
    tag_missing_count = 0
    repo_missing_count = 0
    missing_images = []
    
    for repo_name, tag in IMAGES_TO_VERIFY:
        found, message = check_image_in_harbor(repo_name, tag, harbor_repos)
        
        status = "✅ FOUND" if found else "❌ MISSING"
        print(f"{status:12} | {repo_name:50} | {tag:20} | {message}")
        
        if found:
            found_count += 1
        else:
            missing_count += 1
            missing_images.append((repo_name, tag, message))
            if "Repository not found" in message:
                repo_missing_count += 1
            else:
                tag_missing_count += 1
    
    print("=" * 80)
    print("SUMMARY:")
    print(f"Total images checked: {len(IMAGES_TO_VERIFY)}")
    print(f"Found in Harbor: {found_count}")
    print(f"Missing from Harbor: {missing_count}")
    print(f"  - Repositories not found: {repo_missing_count}")
    print(f"  - Wrong/missing tags: {tag_missing_count}")
    print("=" * 80)
    
    if missing_images:
        print("\nMISSING IMAGES DETAILS:")
        print("-" * 80)
        repo_missing = []
        tag_missing = []
        
        for repo_name, tag, message in missing_images:
            if "Repository not found" in message:
                repo_missing.append((repo_name, tag))
            else:
                tag_missing.append((repo_name, tag, message))
        
        if repo_missing:
            print("\n🔴 REPOSITORIES NOT FOUND:")
            for repo_name, tag in repo_missing:
                print(f"   ❌ {repo_name}:{tag}")
        
        if tag_missing:
            print(f"\n🟡 REPOSITORIES FOUND BUT WRONG/MISSING TAGS:")
            for repo_name, tag, message in tag_missing:
                print(f"   ⚠️  {repo_name}:{tag}")
                print(f"      {message}")
    
    if missing_count == 0:
        print("🎉 SUCCESS: All images have been successfully transferred to Harbor!")
    elif repo_missing_count > 0:
        print(f"🔴 CRITICAL: {repo_missing_count} repositories are completely missing from Harbor")
        print(f"🟡 WARNING: {tag_missing_count} repositories exist but have wrong/missing tags")
    else:
        print(f"🟡 WARNING: All repositories exist but {tag_missing_count} have wrong/missing tags")
    
    return missing_count == 0

if __name__ == "__main__":
    main()