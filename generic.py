from flask import Flask, request, jsonify
import uuid
import yaml
import os
from datetime import datetime

app = Flask(__name__)
CONFIG_FILE = "config.yaml"

def create_empty_yaml():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            yaml.dump({"endpoints": {}}, f)

def read_config():
    create_empty_yaml()
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f) or {"endpoints": {}}

def write_config(config):
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

def normalize_path(path):
    return '/' + path.strip('/')

@app.route('/register', methods=['POST'])
def register_endpoint():
    try:
        data = request.get_json()
        required_fields = ["path", "method", "response"]
        if not all(field in data for field in required_fields):
            return jsonify({"status": "error", "message": f"Missing required fields. Required: {required_fields}"}), 400

        path = normalize_path(data["path"])
        method = data["method"].upper()
        endpoint_id = str(uuid.uuid4())
        config = read_config()
        endpoint_config = {
            "id": endpoint_id,
            "path": path,
            "method": method,
            "response": data["response"],
            "created_at": str(datetime.now())
        }
        config["endpoints"][endpoint_id] = endpoint_config
        write_config(config)

        return jsonify({"status": "success", "message": "New endpoint registered successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def handle_request(path):
    try:
        config = read_config()
        normalized_path = normalize_path(path)
        matching_endpoint = next((endpoint for endpoint in config["endpoints"].values() if endpoint["path"] == normalized_path and endpoint["method"] == request.method), None)

        if not matching_endpoint:
            return jsonify({"status": "error", "message": f"No endpoint found for {request.method} {normalized_path}"}), 404
        
        return jsonify(matching_endpoint["response"]), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
