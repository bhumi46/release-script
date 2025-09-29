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
        colon_index = image[0].find(":")
        if colon_index > -1:
            if len(image[0]) - 1 == colon_index:
                print_log('Image "' + image[0] + '" with tag doesn\'t exists', 'error')
                tagsNotAvailable.append(image[0])
                continue
            if len(image) == 1:
                image = [image[0]] + [image[0][colon_index + 1:]]
            images.append(image)
        if colon_index == -1:
            if len(image) == 1:
                print_log('Image "' + image[0] + '" with tag doesn\'t exists', 'error')
                tagsNotAvailable.append(image[0])
                continue
            if len(image) == 2:
                image = [image[0] + ':' + image[1]] + [image[1]]
            images.append(image)

    return images, tagsNotAvailable


def get_auth_token(image_name):
    """Get Docker Hub authentication token"""
    url = 'https://auth.docker.io/token?service=registry.docker.io&scope=repository:' + image_name + ':pull'
    token_req = requests.get(url=url, headers={"Content-Type": "text"})
    if token_req.status_code == 200:
        return token_req.json()['token']
    else:
        print_log("Failed to get auth token for " + image_name, 'error')
        return None


def chkImageExistence(image, tag, imageExitUrl):
    # Get the repository name
    if '@sha256' in image:
        image_name, image_digest = image.split('@sha256')
    else:
        image_name = image
    
    # Get the auth token
    token = get_auth_token(image_name)
    if not token:
        return False
    
    headers = {
        "Authorization": "Bearer " + token
    }
    
    if '@sha256' in image:
        image_name, image_digest = image.split('@sha256')
        url = imageExitUrl + image_name + "/manifests/" + "sha256:" + tag
    else:
        url = imageExitUrl + "repositories/" + image + "/tags/" + tag
    
    print("url= " + url)
    if 'sha256:' in url:
        r = requests.get(url=url, headers=headers)
    else:
        r = requests.get(url=url)
    # If image not found exit the script
    if int(r.status_code) == 404:
        print_log("Image \"" + image + ":" + tag + "\" does not exist", 'error')
        return False
    return True


def ignoreComment(csvfile):
    for row in csvfile:
        raw = row.split('#')[0].strip()
        if raw: yield raw


def getDockerHash(repo, tag):
    token = get_auth_token(repo)
    if not token:
        return ''
    
    headers = {
        "Accept": "application/vnd.docker.distribution.manifest.v2+json",
        "Authorization": "Bearer " + token
    }
    registryUrl = 'https://registry-1.docker.io/v2/' + repo + '/manifests/' + tag
    getImageHash = requests.get(registryUrl, headers=headers)
    if getImageHash.status_code == 200:
        return getImageHash.headers['etag']
    return ''


def get_manifest_list(repo, tag):
    """Get manifest list for multi-architecture images"""
    token = get_auth_token(repo)
    if not token:
        return None
    
    headers = {
        "Accept": "application/vnd.docker.distribution.manifest.list.v2+json",
        "Authorization": "Bearer " + token
    }
    registry_url = f'https://registry-1.docker.io/v2/{repo}/manifests/{tag}'
    response = requests.get(registry_url, headers=headers)
    
    if response.status_code == 200 and 'manifests' in response.json():
        return response.json()
    
    # If not a multi-arch image, try getting the regular manifest
    headers = {
        "Accept": "application/vnd.docker.distribution.manifest.v2+json",
        "Authorization": "Bearer " + token
    }
    response = requests.get(registry_url, headers=headers)
    if response.status_code == 200:
        # Return a single-item list for consistent handling
        return {"manifests": [{"digest": response.headers.get('docker-content-digest', ''), "platform": {"architecture": "unknown", "os": "unknown"}}]}
    
    print_log(f"Failed to get manifest for {repo}:{tag}", 'error')
    return None


def chkDockerAccExistence(acc_name):
    accUrl = 'https://hub.docker.com/v2/users/' + acc_name
    req = requests.get(url=accUrl)
    if int(req.status_code) == 404:
        print_log("Docker account with Name " + acc_name + " does not exists", 'error')
        return False
    return True


def create_manifest_list(src_image_name, dest_image_name, tag, dest_arch_images, remote_client):
    """Create a multi-architecture manifest list from individual architecture digests"""
    try:
        # First, perform a CLI-based Docker login using the credentials from config.yaml
        print_log(f"Logging in to Docker CLI for manifest operations", 'info')
        # Use subprocess.run with list format to avoid shell interpretation issues
        login_process = subprocess.run(
            ["docker", "login", "-u", config['docker']['username'], "-p", config['docker']['token'], config['docker']['registry_url']], 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        
        # If login failed, report the error
        if login_process.returncode != 0:
            print_log(f"Docker CLI login failed: {login_process.stderr.decode('utf-8')}", 'error')
            return False
            
        # Create the manifest list with --amend flag to update if it exists
        # Reference the individual architecture images that were pushed to Harbor
        manifest_create_cmd = f"docker manifest create --amend {dest_image_name}:{tag}"
        
        # Add each destination architecture image to the manifest list
        for dest_arch_image in dest_arch_images:
            manifest_create_cmd += f" {dest_arch_image}"
        
        print_log(f"Creating manifest list with command: {manifest_create_cmd}", 'info')
        subprocess.run(manifest_create_cmd, shell=True, check=True)
        
        # Push the manifest list
        manifest_push_cmd = f"docker manifest push {dest_image_name}:{tag}"
        print_log(f"Pushing manifest list with command: {manifest_push_cmd}", 'info')
        subprocess.run(manifest_push_cmd, shell=True, check=True)
        
        return True
    except subprocess.CalledProcessError as e:
        print_log(f"Error creating/pushing manifest list: {str(e)}", 'error')
        return False


def process_image(image, client, remote_client):
    """Process a single image (regardless of architecture)"""
    srcImgRepo = image[0][: image[0].find("/")]
    srcImgName = image[0][image[0].find("/") + 1:image[0].find(":")]
    srcImgtag = image[0][image[0].find(":") + 1:]
    destImgtag = image[1]  # Use the tag from image.txt
    
    print_log("", 'info')
    print_log(10 * "*" + " [ " + config['docker']['destination_organization'] + "/" + srcImgName + ":" + destImgtag + " ] " + "*" * 52, 'info')
    
    # Get manifest list for the source image
    full_src_img_name = image[0][: image[0].find(":")]
    manifest_list = get_manifest_list(full_src_img_name, srcImgtag)
    
    # For multi-architecture images
    if manifest_list and 'manifests' in manifest_list and len(manifest_list['manifests']) > 1:
        print_log(f"Multi-arch image detected with {len(manifest_list['manifests'])} architectures", 'info')
        
        # List detected architectures for logging
        for manifest in manifest_list['manifests']:
            arch_type = manifest['platform']['architecture']
            arch_os = manifest['platform']['os']
            print_log(f"Detected architecture: {arch_os}/{arch_type}", 'info')
        
        # Direct multi-arch transfer using index digest approach
        print_log("Transferring complete multi-arch image to maintain exact Docker Hub structure...", 'info')
        try:
            dest_repo = f"{config['docker']['registry_url']}/{config['docker']['destination_organization']}/{srcImgName}"
            
            # Pull the entire multi-arch image using the source tag and push directly
            src_with_tag = f"{full_src_img_name}:{srcImgtag}"
            
            print_log(f"Pulling complete multi-arch image: {src_with_tag}", 'info')
            # Pull the complete multi-arch manifest by tag (this gets the manifest list)
            pull_status = remote_client.pull(repository=full_src_img_name, tag=srcImgtag, stream=True, decode=True)
            status_update(pull_status)
            
            # Tag it for destination
            remote_client.tag(image=src_with_tag, repository=dest_repo, tag=destImgtag, force=True)
            remote_client.tag(image=src_with_tag, repository=dest_repo, tag="latest", force=True)
            
            # Push the complete multi-arch manifest list
            print_log(f"Pushing complete multi-arch image to: {dest_repo}:{destImgtag}", 'info')
            push_status = remote_client.push(repository=dest_repo, tag=destImgtag, stream=True, decode=True)
            status_update(push_status)
            
            # Also push latest tag
            print_log(f"Pushing latest tag to: {dest_repo}:latest", 'info')
            latest_push_status = remote_client.push(repository=dest_repo, tag="latest", stream=True, decode=True)
            status_update(latest_push_status)
            
            print_log(f"Successfully transferred complete multi-arch manifest list for {full_src_img_name}:{srcImgtag}", 'info')
                
        except Exception as e:
            print_log(f"Error in multi-arch transfer: {str(e)}", 'error')
            raise e
                
    else:
        # Handle single architecture image
        promote(
            srcImgRepo, 
            srcImgName, 
            srcImgtag, 
            destImgtag,
            config['docker']['registry_url'] + '/' + config['docker']['destination_organization'], 
            remote_client, 
            client
        )

    return f"Completed processing {image[0]} to {config['docker']['destination_organization']}/{srcImgName}:{destImgtag}"


def pull_tag_arch_image(src_repo, src_image_name, digest, tag, dst_repo, remote_client, local_client, arch_type="unknown", arch_os="unknown"):
    """Pull image digest and tag it for manifest list creation"""
    src_repository = src_repo + "/" + src_image_name
    src_image = src_repository + "@sha256:" + digest
    force = True
    dst_repository = dst_repo + "/" + src_image_name
    dst_image = dst_repository + ":" + tag
    
    print_log("", 'info')
    print_log(f"[ PULL {arch_os}/{arch_type} ----------------------> " + src_image + " ] ", 'info')
    
    # Pull the image by digest
    pull_status = remote_client.pull(repository=src_repository, tag=f"sha256:{digest}", stream=True, decode=True)
    status_update(pull_status)
    
    # Tag for this architecture
    remote_client.tag(image=src_image, repository=dst_repository, tag=tag, force=force)
    
    # Push the architecture-specific image
    print_log("", 'info')
    print_log(f"[ PUSH {arch_os}/{arch_type} -----> " + src_image + "\t------> " + dst_image + " ] ", 'info')
    push_status = remote_client.push(repository=dst_repository, tag=tag, stream=True, decode=True)
    status_update(push_status)
    
    print_log(f"Completed pulling/tagging {src_image} \t------> {dst_image} ({arch_os}/{arch_type})", 'info')
    return True


def load_config():
    global config
    with open("config.yml", "r") as configfile:
        config = yaml.safe_load(configfile)


def strip_tag(image_name):
    image_version = ""
    stripped_list = image_name[0].split('/')
    repository = stripped_list[0]
    image = stripped_list[1]
    image_version = image_name[1]
    return repository, image, image_version


def promote(src_repo, src_image_name, src_image_version, tag, dst_repo, remote_client, local_client):
    src_repository = src_repo + "/" + src_image_name
    src_tag = tag if src_image_version == "" else src_image_version
    src_image = src_repository + ":" + src_tag
    force = True
    dst_repository = dst_repo + "/" + src_image_name
    dst_tag = tag  # Use the tag from image.txt
    dst_image = dst_repository + ":" + dst_tag
    dst_latest = dst_repository + ":" + "latest"
    
    if '@sha256:' in dst_image:
        dst_image = re.sub(r'@sha256','',dst_image)
        dst_repository = re.sub(r'@sha256','',dst_repository)
    
    print_log("", 'info')
    src_tag=':'+src_tag
    if '@sha256:' in src_image:
        src_repository = re.sub(r'@sha256','',src_repository)
        src_tag='@sha256'+src_tag
    
    print_log("[ PULL ----------------------> " + src_image + " ] ", 'info')
    print("src_repository : ",src_repository,'src_tag',src_tag, 'src_image : ',src_image )
    print('dst_repository : ',dst_repository, 'dst_tag : ', dst_tag)
    
    pull_status = remote_client.pull(repository=src_repository+src_tag, stream=True, decode=True)
    status_update(pull_status)
    
    remote_client.tag(image=src_image, repository=dst_repository, tag=dst_tag, force=force)
    print_log("", 'info')
    print_log("[ PUSH -----> " + src_image + "\t------> " + dst_image + " ] ", 'info')
    push_status = remote_client.push(repository=dst_repository, tag=dst_tag, stream=True, decode=True)
    status_update(push_status)
    
    print_log("", 'info')
    print_log("[ PUSH -----> " + src_image + "\t------> " + dst_latest + " ] ", 'info')
    remote_client.tag(image=src_image, repository=dst_repository, tag='latest', force=force)
    latest_push = remote_client.push(repository=dst_repository, tag='latest', stream=True, decode=True)
    status_update(latest_push)
    
    # remove docker images from local machine
    rm_local_img = [src_image, dst_image, dst_latest]
    for img in rm_local_img:
        if len(local_client.images.list(img)) != 0:
            local_client.images.remove(img)
    
    print_log("Completed " + src_image + "\t------> " + dst_image, 'info')


def status_update(output):
    status = ''
    for line in output:
        if line.get("error"):
            raise InterruptedError(line.get("error"))
        if line.get("progress"):
            print(line.get("status"), line.get("progress"), end="\r")
        if line.get('status'):
            status = line.get('status')
    print_log(status, 'info')


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
        srcImgName = image[0][: image[0].find(":")]
        srcImgtag = image[0][image[0].find(":") + 1:]
        print_log("", 'info')
        print_log("src = \"" + srcImgName + "\" tag = \"" + srcImgtag + "\"", 'info')
        # call function to check existence of source images
        if not chkImageExistence(srcImgName, srcImgtag, imageExitUrl):
            srcImgNotExist.append([srcImgName + ":" + srcImgtag])
        # check if source and destination images are same (same registry, same name, same tag)
        destImgName = config['docker']['destination_organization'] + "/" + (srcImgName.split('/')[-1])
        destImgtag = image[1]
        
        # Only consider them the same if they're on the same registry AND have same name/tag
        src_registry = "docker.io"  # Source is always Docker Hub (hardcoded in the script)
        dest_registry_url = config['docker']['registry_url'].lower()
        dest_is_dockerhub = 'docker.io' in dest_registry_url or 'hub.docker' in dest_registry_url or 'index.docker.io' in dest_registry_url
        
        # Images are the same only if: same registry + same name + same tag
        if dest_is_dockerhub and destImgName == srcImgName and destImgtag == srcImgtag:
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
    for image in images:
        imgName = image[0][: image[0].find(":")]
        destImgName = config['docker']['destination_organization'] + "/" + (imgName.split('/')[-1])
        destImgTag = image[1]
        destImgHash = getDockerHash(destImgName, destImgTag)
        print_log("", 'info')
        print_log("[ " + destImgName + " ] ", 'info')
        print_log("Destination Image = \"" + destImgName + "\" Destination Image tag = \"" + str(destImgTag) + "\" IMAGE_ID : " + destImgHash, 'info')

        # call function to check existence of destination images
        if not chkImageExistence(destImgName, destImgTag, imageExitUrl):
            destImgNotExist.append([destImgName + ":" + destImgTag])
            continue

        # compare only when performing hash operation
        if sys.argv[1] == "hash":
            srcImgHash = getDockerHash(imgName, image[0][image[0].find(":") + 1:])
            destImgHash = getDockerHash(destImgName, destImgTag)

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
    
    # Process all images in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor() as executor:
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
