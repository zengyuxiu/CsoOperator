import os
import yaml
from jinja2 import Environment, FileSystemLoader

config_dir = os.path.dirname(os.path.abspath(__file__))


def load_config():
    with open(f"{config_dir}/base.yaml", 'r') as f:
        config = yaml.safe_load(f)

    env = Environment(loader=FileSystemLoader(config_dir))

    for root, dirs, files in os.walk(config_dir):
        for file in files:
            if file.endswith('.j2'):
                template_path = os.path.relpath(os.path.join(root, file), config_dir)
                template = env.get_template(template_path)
                output = template.render(config)

                output_path = os.path.splitext(template_path)[0] + '.yaml'
                output_file = os.path.join(config_dir, output_path)

                os.makedirs(os.path.dirname(output_file), exist_ok=True)

                with open(output_file, 'w') as f:
                    f.write(output)