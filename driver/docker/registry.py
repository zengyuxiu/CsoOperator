import requests
import hashlib
import json
import os
import tarfile

url = '100.66.185.125:5000'
baserepo = "localregistry:5000"


class DockerRegistryClient:
    def __init__(self, registry_url, username=None, password=None):
        self.registry_url = registry_url
        self.auth = None
        if username and password:
            self.auth = (username, password)

    def push_repository(self, repositoryFile):
        file = tarfile.open(repositoryFile, 'r:gz')
        file.extractall(f"/tmp/{file.name}")
        with open(f"/tmp/{file.name}/manifest.json", "r") as manifestFile:
            manifests = json.load(manifestFile)
        for manifest in manifests:
            config = manifest["config"]
            tag = manifest["RepoTags"]
            for layer in config["Layers"]:
                self._push_blob(tag, layer)

    def push_image(self, image_name, image_tag):
        # 获取镜像的层信息
        layers = self._get_image_layers(image_name, image_tag)

        # 上传每一层的Blob
        for layer in layers:
            self._push_blob(image_name, layer)

        # 上传镜像的配置文件
        config_digest = self._upload_config(image_name, image_tag)

        # 上传镜像的Manifest
        manifest = {
            "schemaVersion": 2,
            "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
            "config": {
                "mediaType": "application/vnd.docker.container.image.v1+json",
                "size": len(json.dumps(config_digest)),
                "digest": config_digest
            },
            "layers": [
                {
                    "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
                    "size": layer["size"],
                    "digest": layer["digest"]
                }
                for layer in layers
            ]
        }
        self._upload_manifest(image_name, image_tag, manifest)

    def _get_image_layers(self, image_name, image_tag):
        # 使用docker inspect获取镜像的层信息
        output = os.popen(f"docker inspect {image_name}:{image_tag}").read()
        image_info = json.loads(output)[0]
        layers = []
        for layer in image_info["RootFS"]["Layers"]:
            layer_id = layer.split(":")[1]
            layer_size = image_info["Size"]
            layers.append({"id": layer_id, "size": layer_size})
        return layers

    def _push_blob(self, image_name, layer):
        # 上传Blob到Registry
        url = f"{self.registry_url}/v2/{image_name}/blobs/uploads/"
        response = requests.post(url, auth=self.auth)
        upload_url = response.headers["Location"]

        with open(layer, "rb") as f:
            data = f.read()
            dgst = hashlib.sha256(data).hexdigest()
            requests.put(f"{upload_url}&digest=sha256:{dgst}", data=data, auth=self.auth)

        return f"sha256:{dgst}"

    def _upload_config(self, image_name, image_tag):
        # 上传镜像的配置文件到Registry
        url = f"{self.registry_url}/v2/{image_name}/blobs/uploads/"
        response = requests.post(url, auth=self.auth)
        upload_url = response.headers["Location"]

        output = os.popen(f"docker inspect {image_name}:{image_tag}").read()
        config = json.loads(output)[0]["Config"]

        data = json.dumps(config).encode()
        dgst = hashlib.sha256(data).hexdigest()
        requests.put(f"{upload_url}&digest=sha256:{dgst}", data=data, auth=self.auth)

        return f"sha256:{dgst}"

    def _upload_manifest(self, image_name, image_tag, manifest):
        # 上传镜像的Manifest到Registry
        url = f"{self.registry_url}/v2/{image_name}/manifests/{image_tag}"
        headers = {
            "Content-Type": "application/vnd.docker.distribution.manifest.v2+json"
        }
        response = requests.put(url, json=manifest, headers=headers, auth=self.auth)
        if response.status_code == 201:
            print(f"Image {image_name}:{image_tag} pushed successfully.")
        else:
            print(f"Failed to push image {image_name}:{image_tag}. Status code: {response.status_code}")
