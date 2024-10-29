import docker

url = 'tcp://100.66.185.125:2375'


class DockerClient:
    def __init__(self):
        self.client = docker.DockerClient(url)

    def raise_registry(self):
        container_name = "registry"

        port_mapping = {"5000/tcp": 5000}

        restart_policy = {"Name": "always"}

        with open("/tmp/registry.tar", "rb") as f:
            image = self.client.images.load(f)

        container = self.client.containers.run(
            image,
            detach=True,
            name=container_name,
            ports=port_mapping,
            restart_policy=restart_policy
        )

        print(f"Registry container started with ID: {container.id}")

    def load_image_to_local_registry(self, file):
        images = self.client.images.load(file)
        for image in images:
            new_tag = f"localregistry:5000/myimage:{image.tags[0].split(':')[-1]}"
            image.tag(new_tag)
            print(f"Pushing image: {new_tag}")
            self.client.images.push(new_tag)
