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


def chkDockerAccExistence(acc_name):
    accUrl = 'https://hub.docker.com/v2/users/' + acc_name
    req = requests.get(url=accUrl)
    if int(req.status_code) == 404:
        print_log("Docker account with Name " + acc_name + " does not exists", 'error')
        return False
    return True


def process_image(image, client, remote_client):
    """Process a single image using crane for all cases (single-arch and multi-arch)"""
    srcImgRepo = image[0][: image[0].find("/")]
    srcImgName = image[0][image[0].find("/") + 1:image[0].find(":")]
    srcImgtag = image[0][image[0].find(":") + 1:]
    destImgtag = image[1]  # Use the tag from image.txt
    
    print_log("", 'info')
    print_log(10 * "*" + " [ " + config['docker']['destination_organization'] + "/" + srcImgName + ":" + destImgtag + " ] " + "*" * 52, 'info')
    
    # Use crane for ALL images (single or multi-arch)
    print_log("Transferring image using crane...", 'info')
    try:
        # Extract registry hostname from URL (remove http:// or https://)
        registry_url = config['docker']['registry_url']
        registry_host = registry_url.replace('https://', '').replace('http://', '').split('/')[0]
        
        full_src_img_name = image[0][: image[0].find(":")]
        dest_repo = f"{registry_host}/{config['docker']['destination_organization']}/{srcImgName}"
        
        import shutil
        
        if not shutil.which("crane"):
            print_log("ERROR: crane tool not found. Please install crane to use this script.", 'error')
            print_log("Install instructions: https://github.com/google/go-containerregistry/blob/main/cmd/crane/README.md", 'error')
            raise Exception("Crane tool required for image transfer")
        
        # Determine if destination registry needs --insecure flag (HTTP)
        use_insecure = registry_url.startswith('http://') or not registry_url.startswith('https://')
        
        # Build crane command with conditional --insecure flag
        crane_cmd = ["crane", "copy"]
        if use_insecure:
            crane_cmd.append("--insecure")
            print_log("Using --insecure flag for HTTP registry", 'info')
        else:
            print_log("Using secure connection for HTTPS registry", 'info')
        
        crane_cmd.extend([
            f"{full_src_img_name}:{srcImgtag}",
            f"{dest_repo}:{destImgtag}"
        ])
        
        print_log(f"Executing: {' '.join(crane_cmd)}", 'info')
        result = subprocess.run(crane_cmd, capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            print_log(f"Successfully transferred image with crane", 'info')
            
            # Also create latest tag with same insecure setting
            latest_cmd = ["crane", "copy"]
            if use_insecure:
                latest_cmd.append("--insecure")
            latest_cmd.extend([
                f"{full_src_img_name}:{srcImgtag}",
                f"{dest_repo}:latest"
            ])
            
            print_log(f"Creating latest tag: {' '.join(latest_cmd)}", 'info')
            latest_result = subprocess.run(latest_cmd, capture_output=True, text=True, check=False)
            if latest_result.returncode == 0:
                print_log("Successfully created latest tag", 'info')
            else:
                print_log(f"Latest tag creation failed: {latest_result.stderr}", 'warning')
            
            print_log(f"Image available at: {dest_repo}:{destImgtag}", 'info')
            print_log("Crane automatically preserves all architectures and manifest structures", 'info')
            
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
