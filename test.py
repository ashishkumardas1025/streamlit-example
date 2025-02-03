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

@app.route('/endpoint/<path:path>', methods=['POST'])
def register_endpoint(path):
    try:
        data = request.get_json()
        required_fields = ["method", "request", "response"]
        if not all(field in data for field in required_fields):
            return jsonify({"status": "error", "message": f"Missing required fields. Required: {required_fields}"}), 400

        path = normalize_path(path)
        method = data["method"].upper()
        endpoint_id = str(uuid.uuid4())
        config = read_config()
        
        if path not in config["endpoints"]:
            config["endpoints"][path] = {}

        endpoint_config = {"id": endpoint_id, "method": method, "request": data["request"], "response": data["response"], **{k: v for k, v in data.items() if k not in required_fields}, "created_at": str(datetime.now())}
        config["endpoints"][path][endpoint_id] = endpoint_config
        write_config(config)

        return jsonify({"status": "success", "message": "New endpoint registered successfully", "endpoint_id": endpoint_id}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/endpoints', methods=['GET'])
def get_all_post_endpoints():
    config = read_config()
    post_endpoints = {}
    
    for path, endpoints in config["endpoints"].items():
        for endpoint_id, endpoint in endpoints.items():
            if endpoint["method"] == "POST":
                if path not in post_endpoints:
                    post_endpoints[path] = {}
                post_endpoints[path][endpoint_id] = endpoint
    
    return jsonify({"status": "success", "post_endpoints": post_endpoints}), 200

@app.route('/endpoints/<path:path>', methods=['GET'])
def list_endpoints_by_path(path):
    config = read_config()
    normalized_path = normalize_path(path)
    if normalized_path in config["endpoints"]:
        return jsonify({"status": "success", "endpoints": config["endpoints"][normalized_path]}), 200
    return jsonify({"status": "error", "message": "No endpoints found for the given path"}), 404

@app.route('/endpoints/<path:path>/<endpoint_id>', methods=['GET'])
def get_endpoint(path, endpoint_id):
    config = read_config()
    normalized_path = normalize_path(path)
    if normalized_path in config["endpoints"] and endpoint_id in config["endpoints"][normalized_path]:
        return jsonify({"status": "success", "endpoint": config["endpoints"][normalized_path][endpoint_id]}), 200
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404

@app.route('/endpoints/<path:path>/<endpoint_id>', methods=['PUT'])
def update_endpoint(path, endpoint_id):
    try:
        data = request.get_json()
        config = read_config()
        normalized_path = normalize_path(path)
        
        if normalized_path not in config["endpoints"] or endpoint_id not in config["endpoints"][normalized_path]:
            return jsonify({"status": "error", "message": "Endpoint not found"}), 404
        
        endpoint = config["endpoints"][normalized_path][endpoint_id]
        for key, value in data.items():
            endpoint[key] = value
        endpoint["updated_at"] = str(datetime.now())
        write_config(config)

        return jsonify({"status": "success", "message": "Endpoint updated successfully", "endpoint": endpoint}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/endpoints/<path:path>/<endpoint_id>', methods=['DELETE'])
def delete_endpoint(path, endpoint_id):
    config = read_config()
    normalized_path = normalize_path(path)
    
    if normalized_path in config["endpoints"] and endpoint_id in config["endpoints"][normalized_path]:
        deleted_endpoint = config["endpoints"][normalized_path].pop(endpoint_id)
        if not config["endpoints"][normalized_path]:
            del config["endpoints"][normalized_path]
        write_config(config)
        return jsonify({"status": "success", "message": "Endpoint deleted successfully", "deleted_endpoint": deleted_endpoint}), 200
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404

@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def handle_request(path):
    try:
        config = read_config()
        normalized_path = normalize_path(path)
        
        if normalized_path in config["endpoints"]:
            for endpoint in config["endpoints"][normalized_path].values():
                if endpoint["method"] == request.method:
                    return jsonify(endpoint["response"]), 200
        
        return jsonify({"status": "error", "message": f"No endpoint found for {request.method} {normalized_path}"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
