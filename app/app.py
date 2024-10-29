import json

from flask import Flask, request
from flask_restful import Api, Resource
from driver.lxd import lxd
from driver.kubernetes.client import KubernetesClient
from net.topology import UserTopology

app = Flask(__name__)
api = Api(app)


class Scenario(Resource):
    def post(self):
        file = request.files['file']
        file_content = file.read()
        json_string = file_content.decode('utf-8')
        topo = UserTopology.from_json(json.loads(json_string))
        client = lxd.LXDManager()
        client.deploy(topo)
        return

    def delete(self):
        file = request.files['file']
        file_content = file.read()
        json_string = file_content.decode('utf-8')
        topo = UserTopology.from_json(json.loads(json_string))
        client = lxd.LXDManager()
        client.destroy(topo)
        k8sclient = KubernetesClient()
        k8sclient.clean_topo(topo)
        return


api.add_resource(Scenario, '/scenario')


class Deployment(Resource):
    def apply(self):
        k8sclient = KubernetesClient()
        file = request.files['file']
        k8sclient.ApplyConfigurationFile(file)

    def delete(self):
        k8sclient = KubernetesClient()
        file = request.files['file']


if __name__ == '__main__':
    app.run(debug=True)
