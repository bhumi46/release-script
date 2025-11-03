import subprocess
import csv
import yaml
import sys
import json
from concurrent.futures import ThreadPoolExecutor
import concurrent
import requests
import string
import re
import logging
import os
from datetime import datetime

# Function to install Docker module
def install_docker_module():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "docker"])
    except subprocess.CalledProcessError:
        print("Error: Failed to install the Docker module.")
        sys.exit(1)

# Install Docker module
install_docker_module()

# Now import the Docker module
import docker as dock

config = {}


def print_log(msg, loglevel):
    print(msg)
    if loglevel == 'debug':
        logging.debug(msg)
    if loglevel == 'info':
        logging.info(msg)
    if loglevel == 'error':
        logging.error(msg)
    if loglevel == 'critical':
        logging.critical(msg)
    if loglevel == 'warning':
        logging.warning(msg)
    return


def parse_image_reference(image_ref):
    """
    Parse image reference to extract repo, tag/digest
    Handles formats:
    - repo/name:tag
    - repo/name@sha256:digest
    - repo/name:tag@sha256:digest
    """
    result = {
        'full_ref': image_ref,
        'repo': '',
        'tag': '',
        'digest': '',
        'has_digest': False,
        'has_tag': False
    }
    
    # Check for digest
    if '@sha256:' in image_ref:
        result['has_digest'] = True
        parts = image_ref.split('@sha256:')
        result['digest'] = 'sha256:' + parts[1]
        image_ref = parts[0]  # Continue parsing the part before @
    
    # Check for tag
    if ':' in image_ref:
        result['has_tag'] = True
        parts = image_ref.rsplit(':', 1)
        result['repo'] = parts[0]
        result['tag'] = parts[1]
    else:
        result['repo'] = image_ref
        result['tag'] = 'latest'
    
    return result


def chkImagesList(images):
    # set src image and dest image with tag
    filtered_images = [[i for i in image if i != ''] for image in images if image != '']
    images_list=[]
    for image in filtered_images:
        for i in image:
            if len(image)<2:
                j=i.split("\t")
                images_list.append([img for img in j if img != ''])
            else:
                if image not in images_list:
                    images_list.append(image)
                    continue

    print("image_list = ",[i for i in images_list])
    images = []
    tagsNotAvailable = []
    
    for image in images_list:
        # Parse the source image reference
        src_parsed = parse_image_reference(image[0])
        
        # If destination tag is not provided
        if len(image) == 1:
            if not src_parsed['has_tag'] and not src_parsed['has_digest']:
                print_log('Image "' + image[0] + '" with tag doesn\'t exists', 'error')
                tagsNotAvailable.append(image[0])
                continue
            # Use source tag as destination tag
            dest_tag = src_parsed['tag'] if src_parsed['has_tag'] else 'latest'
            images.append([image[0], dest_tag])
        else:
            # Destination tag provided
            images.append([image[0], image[1]])

    return images, tagsNotAvailable


def get_auth_token(image_name, registry="docker.io"):
    """Get authentication token for registry"""
    if registry == "docker.io":
        url = 'https://auth.docker.io/token?service=registry.docker.io&scope=repository:' + image_name + ':pull'
        token_req = requests.get(url=url, headers={"Content-Type": "text"})
        if token_req.status_code == 200:
            return token_req.json()['token']
    else:
        # For private registries, you might need different auth
        # Return None and rely on docker credentials
        return None
    print_log("Failed to get auth token for " + image_name, 'error')
    return None


def chkImageExistence(image, tag_or_digest, imageExitUrl, is_digest=False):
    """
    Check if image exists
    image: repository name (e.g., 'mosipdev/inji-web')
    tag_or_digest: either a tag name or digest hash
    is_digest: True if tag_or_digest is a digest, False if it's a tag
    """
    # Get the auth token
    token = get_auth_token(image)
    if not token:
        return False
    
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.docker.distribution.manifest.v2+json,application/vnd.docker.distribution.manifest.list.v2+json"
    }
    
    if is_digest:
        # For digest-based checks, use registry API directly
        # tag_or_digest should be the full digest like "sha256:db84a3e..."
        if not tag_or_digest.startswith('sha256:'):
            tag_or_digest = 'sha256:' + tag_or_digest
        url = f"https://registry-1.docker.io/v2/{image}/manifests/{tag_or_digest}"
        print(f"url= {url}")
        r = requests.get(url=url, headers=headers)
    else:
        # For tag-based checks, use Docker Hub API
        url = imageExitUrl + "repositories/" + image + "/tags/" + tag_or_digest
        print(f"url= {url}")
        r = requests.get(url=url)
    
    # If image not found
    if int(r.status_code) == 404:
        if is_digest:
            print_log(f"Image \"{image}@{tag_or_digest}\" does not exist", 'error')
        else:
            print_log(f"Image \"{image}:{tag_or_digest}\" does not exist", 'error')
        return False
    elif int(r.status_code) != 200:
        print_log(f"Error checking image existence: HTTP {r.status_code}", 'warning')
        return False
    
    return True


def ignoreComment(csvfile):
    for row in csvfile:
        raw = row.split('#')[0].strip()
        if raw: yield raw


def getDockerHash(repo, tag, registry="docker.io", accept_header=None):
    """
    Get Docker image hash/digest
    registry: registry URL (e.g., 'docker.io' or 'myregistry.com')
    accept_header: manifest format to request
    """
    # Default to manifest list format to get the top-level digest
    if accept_header is None:
        accept_header = "application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.docker.distribution.manifest.v2+json"
    
    if registry == "docker.io":
        token = get_auth_token(repo)
        if not token:
            return ''
        
        headers = {
            "Accept": accept_header,
            "Authorization": "Bearer " + token
        }
        registryUrl = 'https://registry-1.docker.io/v2/' + repo + '/manifests/' + tag
    else:
        # For private registries, construct URL differently
        headers = {
            "Accept": accept_header
        }
        # Remove protocol from registry if present
        registry_clean = registry.replace('https://', '').replace('http://', '').split('/')[0]
        registryUrl = f'https://{registry_clean}/v2/{repo}/manifests/{tag}'
    
    try:
        getImageHash = requests.get(registryUrl, headers=headers)
        if getImageHash.status_code == 200:
            # Return the Docker-Content-Digest header which is the canonical digest
            digest = getImageHash.headers.get('Docker-Content-Digest') or getImageHash.headers.get('etag')
            return digest.replace('"', '') if digest else ''
        else:
            print_log(f"Failed to get hash for {repo}:{tag}, status: {getImageHash.status_code}", 'warning')
    except Exception as e:
        print_log(f"Exception getting hash for {repo}:{tag}: {str(e)}", 'warning')
    
    return ''


def getCraneDigest(image_ref, insecure=False):
    """Get image digest using crane digest command"""
    try:
        crane_cmd = ["crane", "digest"]
        if insecure:
            crane_cmd.append("--insecure")
        crane_cmd.append(image_ref)
        
        result = subprocess.run(
            crane_cmd,
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print_log(f"Crane digest failed for {image_ref}: {result.stderr}", 'warning')
            return ''
    except Exception as e:
        print_log(f"Exception running crane digest: {str(e)}", 'warning')
        return ''


def getImageManifestInfo(image_ref, insecure=False):
    """
    Get detailed manifest information including both index and platform manifests
    Returns dict with manifest_type, digest, and platform_digests
    """
    try:
        crane_cmd = ["crane", "manifest"]
        if insecure:
            crane_cmd.append("--insecure")
        crane_cmd.append(image_ref)
        
        manifest_result = subprocess.run(crane_cmd, capture_output=True, text=True, check=False)
        if manifest_result.returncode != 0:
            return None
        
        manifest_json = json.loads(manifest_result.stdout)
        
        info = {
            'manifest_type': manifest_json.get('mediaType', 'unknown'),
            'digest': getCraneDigest(image_ref, insecure),
            'platforms': []
        }
        
        # Check if it's a manifest list (multi-arch)
        if manifest_json.get('mediaType') in [
            'application/vnd.docker.distribution.manifest.list.v2+json',
            'application/vnd.oci.image.index.v1+json'
        ]:
            info['is_multiarch'] = True
            info['index_digest'] = info['digest']  # This is the index/manifest list digest
            
            # Get individual platform manifests
            for m in manifest_json.get('manifests', []):
                platform = m.get('platform', {})
                platform_info = {
                    'os': platform.get('os', 'unknown'),
                    'architecture': platform.get('architecture', 'unknown'),
                    'variant': platform.get('variant', ''),
                    'digest': m.get('digest', '')
                }
                info['platforms'].append(platform_info)
        else:
            # Single-arch image
            info['is_multiarch'] = False
            info['platform_digest'] = info['digest']
        
        return info
        
    except Exception as e:
        print_log(f"Exception getting manifest info: {str(e)}", 'warning')
        return None


def chkDockerAccExistence(acc_name):
    accUrl = 'https://hub.docker.com/v2/users/' + acc_name
    req = requests.get(url=accUrl)
    if int(req.status_code) == 404:
        print_log("Docker account with Name " + acc_name + " does not exists", 'error')
        return False
    return True


def process_image(image, client, remote_client):
    """Process a single image using crane for all cases (single-arch and multi-arch)"""
    
    # Parse source image reference
    src_parsed = parse_image_reference(image[0])
    destImgtag = image[1]  # Use the tag from image.txt
    
    # Extract image name (last part of repo path)
    srcImgName = src_parsed['repo'].split('/')[-1]
    
    print_log("", 'info')
    print_log(10 * "*" + " [ " + config['docker']['destination_organization'] + "/" + srcImgName + ":" + destImgtag + " ] " + "*" * 52, 'info')
    
    # Use crane for ALL images (single or multi-arch)
    print_log("Transferring image using crane...", 'info')
    try:
        # Extract registry hostname from URL (remove http:// or https://)
        registry_url = config['docker']['registry_url']
        registry_host = registry_url.replace('https://', '').replace('http://', '').split('/')[0]
        
        dest_repo = f"{registry_host}/{config['docker']['destination_organization']}/{srcImgName}"
        
        import shutil
        
        if not shutil.which("crane"):
            print_log("ERROR: crane tool not found. Please install crane to use this script.", 'error')
            print_log("Install instructions: https://github.com/google/go-containerregistry/blob/main/cmd/crane/README.md", 'error')
            raise Exception("Crane tool required for image transfer")
        
        # Determine if destination registry needs --insecure flag (HTTP)
        use_insecure = registry_url.startswith('http://') or not registry_url.startswith('https://')
        
        # Construct source image reference
        # If source has digest, use it; otherwise use full reference with tag
        if src_parsed['has_digest']:
            src_image_ref = f"{src_parsed['repo']}@{src_parsed['digest']}"
            print_log(f"Source uses digest reference: {src_image_ref}", 'info')
        else:
            src_image_ref = f"{src_parsed['repo']}:{src_parsed['tag']}"
            print_log(f"Source uses tag reference: {src_image_ref}", 'info')
        
        # Get source manifest info BEFORE transfer
        print_log("Analyzing source image manifest...", 'info')
        src_manifest_info = getImageManifestInfo(src_image_ref, insecure=False)
        
        if src_manifest_info:
            if src_manifest_info['is_multiarch']:
                print_log(f"Source is MULTI-ARCH image", 'info')
                print_log(f"Source Index Digest (Manifest List): {src_manifest_info['index_digest']}", 'info')
                print_log(f"Source has {len(src_manifest_info['platforms'])} platform(s):", 'info')
                for p in src_manifest_info['platforms']:
                    variant = f"/{p['variant']}" if p['variant'] else ""
                    print_log(f"  - {p['os']}/{p['architecture']}{variant}: {p['digest']}", 'info')
            else:
                print_log(f"Source is SINGLE-ARCH image", 'info')
                print_log(f"Source Platform Digest: {src_manifest_info['platform_digest']}", 'info')
        else:
            print_log(f"Warning: Could not retrieve source manifest info", 'warning')
        
        # Build crane copy command
        crane_cmd = ["crane", "copy"]
        if use_insecure:
            crane_cmd.append("--insecure")
            print_log("Using --insecure flag for HTTP registry", 'info')
        else:
            print_log("Using secure connection for HTTPS registry", 'info')
        
        # Add all-tags flag to preserve multi-arch manifests properly
        crane_cmd.extend([
            src_image_ref,
            f"{dest_repo}:{destImgtag}"
        ])
        
        print_log(f"Executing: {' '.join(crane_cmd)}", 'info')
        result = subprocess.run(crane_cmd, capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            print_log(f"Successfully transferred image with crane", 'info')
            
            # Analyze destination manifest after transfer
            print_log("", 'info')
            print_log("Analyzing destination image manifest...", 'info')
            dest_image_ref = f"{dest_repo}:{destImgtag}"
            dest_manifest_info = getImageManifestInfo(dest_image_ref, insecure=use_insecure)
            
            if dest_manifest_info:
                if dest_manifest_info['is_multiarch']:
                    print_log(f"Destination is MULTI-ARCH image", 'info')
                    print_log(f"Destination Index Digest (Manifest List): {dest_manifest_info['index_digest']}", 'info')
                    print_log(f"Destination has {len(dest_manifest_info['platforms'])} platform(s):", 'info')
                    for p in dest_manifest_info['platforms']:
                        variant = f"/{p['variant']}" if p['variant'] else ""
                        print_log(f"  - {p['os']}/{p['architecture']}{variant}: {p['digest']}", 'info')
                else:
                    print_log(f"Destination is SINGLE-ARCH image", 'info')
                    print_log(f"Destination Platform Digest: {dest_manifest_info['platform_digest']}", 'info')
            else:
                print_log(f"Warning: Could not retrieve destination manifest info", 'warning')
            
            # Compare digests
            print_log("", 'info')
            print_log("=== DIGEST VERIFICATION ===", 'info')
            
            if src_manifest_info and dest_manifest_info:
                # For multi-arch images, compare index digests
                if src_manifest_info['is_multiarch'] and dest_manifest_info['is_multiarch']:
                    src_digest = src_manifest_info['index_digest']
                    dest_digest = dest_manifest_info['index_digest']
                    
                    print_log(f"Comparing Index Digests (Manifest Lists):", 'info')
                    print_log(f"  Source:      {src_digest}", 'info')
                    print_log(f"  Destination: {dest_digest}", 'info')
                    
                    if src_digest == dest_digest:
                        print_log("✓ Index Digest MATCH - Multi-arch structure preserved perfectly!", 'info')
                    else:
                        print_log("✗ Index Digest MISMATCH - This may indicate registry differences", 'warning')
                    
                    # Also compare individual platform manifests
                    print_log("", 'info')
                    print_log("Comparing Platform Manifests:", 'info')
                    platform_match_count = 0
                    for src_p in src_manifest_info['platforms']:
                        src_plat = f"{src_p['os']}/{src_p['architecture']}"
                        if src_p.get('variant'):
                            src_plat += f"/{src_p['variant']}"
                        
                        # Find corresponding dest platform
                        dest_p = next((p for p in dest_manifest_info['platforms'] 
                                     if p['os'] == src_p['os'] and p['architecture'] == src_p['architecture']
                                     and p.get('variant') == src_p.get('variant')), None)
                        if dest_p:
                            if src_p['digest'] == dest_p['digest']:
                                print_log(f"  ✓ {src_plat}: {src_p['digest']} (MATCH)", 'info')
                                platform_match_count += 1
                            else:
                                print_log(f"  ✗ {src_plat}: Source={src_p['digest']}, Dest={dest_p['digest']} (MISMATCH)", 'warning')
                        else:
                            print_log(f"  ✗ {src_plat}: Platform not found in destination!", 'error')
                    
                    if platform_match_count == len(src_manifest_info['platforms']):
                        print_log(f"✓ All {platform_match_count} platform manifest(s) match perfectly!", 'info')
                    else:
                        print_log(f"✗ Only {platform_match_count}/{len(src_manifest_info['platforms'])} platform(s) match", 'warning')
                
                # For single-arch images
                elif not src_manifest_info['is_multiarch'] and not dest_manifest_info['is_multiarch']:
                    src_digest = src_manifest_info['platform_digest']
                    dest_digest = dest_manifest_info['platform_digest']
                    
                    print_log(f"Comparing Platform Digests:", 'info')
                    print_log(f"  Source:      {src_digest}", 'info')
                    print_log(f"  Destination: {dest_digest}", 'info')
                    
                    if src_digest == dest_digest:
                        print_log("✓ Platform Digest MATCH - Images are identical!", 'info')
                    else:
                        print_log("✗ Platform Digest MISMATCH", 'warning')
                else:
                    print_log("✗ Architecture type mismatch (single-arch vs multi-arch)", 'error')
            else:
                print_log("Unable to verify digests (manifest info retrieval failed)", 'warning')
            
            # Also create latest tag with same insecure setting
            latest_cmd = ["crane", "copy"]
            if use_insecure:
                latest_cmd.append("--insecure")
            latest_cmd.extend([
                src_image_ref,
                f"{dest_repo}:latest"
            ])
            
            print_log(f"Creating latest tag: {' '.join(latest_cmd)}", 'info')
            latest_result = subprocess.run(latest_cmd, capture_output=True, text=True, check=False)
            if latest_result.returncode == 0:
                print_log("Successfully created latest tag", 'info')
            else:
                print_log(f"Latest tag creation failed: {latest_result.stderr}", 'warning')
            
            print_log(f"Image available at: {dest_repo}:{destImgtag}", 'info')
            
            # Summary
            print_log("", 'info')
            if src_manifest_info and src_manifest_info['is_multiarch']:
                print_log("NOTE: For multi-arch images, the Index Digest (manifest list) is what matters most.", 'info')
                print_log("Individual platform manifests should also match to ensure identical content.", 'info')
            
        else:
            print_log(f"Crane transfer failed: {result.stderr}", 'error')
            raise Exception(f"Crane transfer failed: {result.stderr}")
            
    except Exception as e:
        print_log(f"Error in crane transfer: {str(e)}", 'error')
        raise e

    return f"Completed processing {image[0]} to {config['docker']['destination_organization']}/{srcImgName}:{destImgtag}"


def load_config():
    global config
    with open("config.yml", "r") as configfile:
        config = yaml.safe_load(configfile)


def main():
    client = dock.from_env()
    registry_url = config['docker']['registry_url']
    imageExitUrl = config['docker']['imageExitUrl']
    # create log file with format date-time.log
    if not os.path.exists('./logs/'):
        os.makedirs('./logs/')
    logFile = "vidivi.log"
    logging.basicConfig(filename='logs/' + logFile, level=logging.DEBUG, filemode='w',
                        format=' %(asctime)s  %(levelname)s  %(message)s ',
                        datefmt='%d-%b-%y %H:%M:%S')
    print_log('LOGFILE CREATED : ' + logFile, 'info')

    header = config['csv']['has_header']
    with open(config['csv']['filename'], newline='') as image_data:
        images = csv.reader(ignoreComment(image_data), delimiter=' ')
        # calling chkImagesList function
        print_log("", 'info')
        print_log('*' * 20 + " Check Images List " + '*' * 84, 'info')
        images, tagsNotAvailable = chkImagesList(images)
        print_log("", 'info')
        print_log("IMAGES= " + str(images), 'info')
    if len(tagsNotAvailable) > 0:
        print_log("", 'info')
        print_log("Tag not provided for the images list below: \n\t" + str(tagsNotAvailable) + "", 'error')
        exit(1)

    # check the existence of srcImage+tag
    print_log("", 'info')
    print_log('*' * 20 + " Check existence of Source Images " + '*' * 67, 'info')
    srcImgNotExist = []
    srcDestSameImg = []
    destImgNotExist = []
    srcDestNotSameHash = []
    srcDestSameHash = []
    
    for image in images:
        src_parsed = parse_image_reference(image[0])
        
        print_log("", 'info')
        if src_parsed['has_digest']:
            print_log("src = \"" + src_parsed['repo'] + "\" digest = \"" + src_parsed['digest'] + "\"", 'info')
        else:
            print_log("src = \"" + src_parsed['repo'] + "\" tag = \"" + src_parsed['tag'] + "\"", 'info')
        
        # call function to check existence of source images
        # For digest-based references, check using the repo and digest
        if src_parsed['has_digest']:
            # Pass the full digest (sha256:hash) and mark as digest check
            if not chkImageExistence(src_parsed['repo'], src_parsed['digest'], imageExitUrl, is_digest=True):
                srcImgNotExist.append([image[0]])
        else:
            if not chkImageExistence(src_parsed['repo'], src_parsed['tag'], imageExitUrl, is_digest=False):
                srcImgNotExist.append([image[0]])
        
        # check if source and destination images are same (same registry, same name, same tag)
        srcImgName = src_parsed['repo'].split('/')[-1]
        destImgName = config['docker']['destination_organization'] + "/" + srcImgName
        destImgtag = image[1]
        
        # Only consider them the same if they're on the same registry AND have same name/tag
        src_registry = "docker.io"  # Source is always Docker Hub (hardcoded in the script)
        dest_registry_url = config['docker']['registry_url'].lower()
        dest_is_dockerhub = 'docker.io' in dest_registry_url or 'hub.docker' in dest_registry_url or 'index.docker.io' in dest_registry_url
        
        # Images are the same only if: same registry + same name + same tag
        if dest_is_dockerhub and destImgName == src_parsed['repo'] and destImgtag == src_parsed['tag']:
            srcDestSameImg.append([destImgName, destImgtag])
    
    # print list of source images which does not exist
    if len(srcImgNotExist) > 0:
        print_log("", 'info')
        print_log("Below Source Images doesn't exists; EXITING;\n\t" + str(srcImgNotExist), 'error')
        exit(1)
    # print list of same source and destination images
    if len(srcDestSameImg) > 0:
        print_log("", 'info')
        print_log("Below list consist of same source and destination images; EXITING;\n\t" + str(srcDestSameImg),
                  'error')
        exit(1)

    # stop if user passed is equal to 'check' as an argument
    if sys.argv[1] == "check":
        print_log("", 'info')
        print_log("Operation to check the existence of Source Images completed; EXITING;", 'info')
        exit(0)

    # check the existence of destImg+tag
    print_log("", 'info')
    print_log('*' * 20 + " Check existence of Destination Docker Account " + '*' * 63, 'info')
    # Skip Docker Hub account check for non-Docker Hub registries
    if 'docker.io' in config['docker']['registry_url'].lower() or 'hub.docker' in config['docker']['registry_url'].lower():
        if not chkDockerAccExistence(config['docker']['destination_organization']):
            exit(1)
    else:
        print_log("Skipping Docker Hub account check for non-Docker Hub registry", 'info')
    
    print_log("", 'info')
    print_log('*' * 20 + " Check existence of Destination Images " + '*' * 63, 'info')
    
    # Extract registry info for destination
    dest_registry_url = config['docker']['registry_url'].lower()
    dest_is_dockerhub = 'docker.io' in dest_registry_url or 'hub.docker' in dest_registry_url or 'index.docker.io' in dest_registry_url
    dest_registry = "docker.io" if dest_is_dockerhub else config['docker']['registry_url']
    use_insecure = config['docker']['registry_url'].startswith('http://') or not config['docker']['registry_url'].startswith('https://')
    
    for image in images:
        src_parsed = parse_image_reference(image[0])
        srcImgName = src_parsed['repo'].split('/')[-1]
        destImgName = config['docker']['destination_organization'] + "/" + srcImgName
        destImgTag = image[1]
        
        print_log("", 'info')
        print_log("[ " + destImgName + " ] ", 'info')
        
        # Use crane to get destination hash
        registry_host = config['docker']['registry_url'].replace('https://', '').replace('http://', '').split('/')[0]
        dest_ref = f"{registry_host}/{destImgName}:{destImgTag}"
        destImgHash = getCraneDigest(dest_ref, insecure=use_insecure)
        
        print_log("Destination Image = \"" + destImgName + "\" Destination Image tag = \"" + str(destImgTag) + "\" IMAGE_ID : " + destImgHash, 'info')

        # Check existence
        if not destImgHash:
            destImgNotExist.append([destImgName + ":" + destImgTag])
            print_log(f"Destination image {destImgName}:{destImgTag} does not exist", 'info')
            continue

        # compare only when performing hash operation
        if sys.argv[1] == "hash":
            # Get source hash using crane
            if src_parsed['has_digest']:
                src_ref = f"{src_parsed['repo']}@{src_parsed['digest']}"
            else:
                src_ref = f"{src_parsed['repo']}:{src_parsed['tag']}"
            
            srcImgHash = getCraneDigest(src_ref, insecure=False)

            if srcImgHash != destImgHash:
                print_log("", 'info')
                print_log("Source Image = \"" + image[0] + "\" IMAGE_ID :" + str(srcImgHash), 'info')
                print_log(
                    "Destination Image = \"" + destImgName + ":" + destImgTag + "\" IMAGE_ID :" + str(destImgHash),
                    'info')
                print_log("does not have same HASH ID ", 'info')
                srcDestNotSameHash.append(
                    {"srcImg": image[0], "srcImgHash": srcImgHash, "destImg": destImgName + ":" + destImgTag,
                     "destImgHash": destImgHash})
                continue

            print_log("", 'info')
            print_log("Source Image = \"" + image[0] + "\" IMAGE_ID :" + str(srcImgHash), 'info')
            print_log("Destination Image = \"" + destImgName + ":" + destImgTag + "\"IMAGE_ID : " + destImgHash, 'info')
            print_log("does have same HASH ID ", 'info')
            srcDestSameHash.append(
                {"srcImg": image[0], "srcImgHash": srcImgHash, "destImg": destImgName + ":" + destImgTag,
                 "destImgHash": destImgHash})

    print_log("", 'info')
    print_log('*' * 20 + " HASH Operation Results " + '*' * 70, 'info')
    if len(destImgNotExist) > 0:
        print_log("", 'info')
        print_log("Below Destination Images doesn't exists; CONTINUE;\n\t" + str(destImgNotExist), 'info')
    if len(srcDestNotSameHash) > 0:
        print_log("", 'info')
        print_log("Below List of Images does not contains same HASH / IMAGE ID \n\t" + str(srcDestNotSameHash), 'info')
    if len(srcDestSameHash) > 0:
        print_log("", 'info')
        print_log("Below List of Images does contains same HASH / IMAGE ID \n\t" + str(srcDestSameHash), 'info')

    # stop if user passed is not 'push' as an argument
    if sys.argv[1] != "push":
        print_log("", 'info')
        print_log("Check and HASH operation completed; EXITING;", 'info')
        exit(0)

    print_log("", 'info')
    print_log('*' * 20 + " Start Image Transfer operation " + '*' * 71, 'info')
    remote_client = dock.APIClient(base_url='unix:///var/run/docker.sock', version='auto')
    remote_client.login(username=config['docker']['username'], password=config['docker']['token'],
                        registry=config['docker']['registry_url'])
    
    # Process all images in parallel using ThreadPoolExecutor with configured limit
    max_workers = config.get('process', {}).get('count', 3)
    print_log(f'Using {max_workers} parallel workers for image transfers', 'info')
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for image in images:
            try:
                future = executor.submit(process_image, image, client, remote_client)
                futures.append(future)
            except Exception as e:
                print_log(f"Error submitting task to executor: {str(e)}", 'error')
                executor.shutdown(wait=False)
                exit(1)
        
        # Wait for all threads to complete
        for future in futures:
            try:
                result = future.result()
                print_log(result, 'info')
            except Exception as e:
                print_log(f"Error occurred in thread: {str(e)}", 'error')
                executor.shutdown(wait=False)
                exit(1)


if __name__ == "__main__":
    if len(sys.argv[1:]) == 0:
        print_log("check / hash / push operation not passed as an argument; EXITING;", 'error')
        exit(1)
    if sys.argv[1] != "check" and sys.argv[1] != "push" and sys.argv[1] != "hash":
        print_log("INVALID operation provided; EXITING;", 'error')
        exit(1)

    load_config()

    if not config['docker']['destination_organization']:
        print_log("Destination Organization name not provided in config.yml; EXITING;", 'error')
        exit(1)
    main()
