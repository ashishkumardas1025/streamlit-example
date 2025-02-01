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
            yaml.dump({}, f)
        print("Config.yaml created successfully")

def read_config():
    create_empty_yaml()
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f) or {}

def write_config(config):
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

@app.route('/addendpoint', methods=['POST'])
def add_endpoint():
    data = request.get_json()
    path = data.get("path")
    methods = data.get("method")
    if isinstance(methods, str):
        methods = [methods.upper()]
    else:
        methods = [m.upper() for m in methods]
    
    request_data = data.get("request", {})
    response_data = data.get("response", {})
    
    if not path or not methods:
        return jsonify({"status": "error", "message": "Path and methods are required"}), 400
    
    config = read_config()
    endpoint_id = str(uuid.uuid4())
    config[endpoint_id] = {
        "path": path,
        "methods": methods,
        "request": request_data,
        "response": response_data,
        "created_at": str(datetime.now())
    }
    write_config(config)
    
    return jsonify({"status": "success", "message": "Endpoint added successfully", "id": endpoint_id}), 201

@app.route('/endpoints', methods=['GET'])
def get_all_endpoints():
    config = read_config()
    return jsonify({"status": "success", "endpoints": config}), 200

@app.route('/endpoints/<endpoint_id>', methods=['GET'])
def get_endpoint(endpoint_id):
    config = read_config()
    if endpoint_id in config:
        return jsonify({"status": "success", "endpoint": config[endpoint_id]}), 200
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404

@app.route('/endpoints/<endpoint_id>', methods=['PUT'])
def update_endpoint(endpoint_id):
    data = request.get_json()
    config = read_config()
    if endpoint_id in config:
        config[endpoint_id].update(data)
        write_config(config)
        return jsonify({"status": "success", "message": "Endpoint updated successfully", "updated_endpoint": config[endpoint_id]}), 200
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404

@app.route('/endpoints/<endpoint_id>', methods=['DELETE'])
def delete_endpoint(endpoint_id):
    config = read_config()
    if endpoint_id in config:
        del config[endpoint_id]
        write_config(config)
        return jsonify({"status": "success", "message": "Endpoint deleted successfully"}), 200
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404

@app.route('/<path:endpoint_path>', methods=['POST', 'GET', 'PUT', 'DELETE'])
def dynamic_endpoint(endpoint_path):
    config = read_config()
    matching_endpoints = [v for v in config.values() if v["path"] == f"/{endpoint_path}"]
    
    if not matching_endpoints:
        return jsonify({"status": "error", "message": "Endpoint not found"}), 404
    
    matching_endpoint = matching_endpoints[0]
    if request.method not in matching_endpoint["methods"]:
        return jsonify({"status": "error", "message": "Method not allowed for this endpoint"}), 405
    
    return jsonify({
        "status": "success",
        "message": "Endpoint consumed successfully",
        "response": matching_endpoint["response"]
    }), 200

if __name__ == '__main__':
    app.run(debug=True)
