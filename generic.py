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
        print("Config.yaml created successfully")

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
        
        # Validate required fields
        required_fields = ["path", "method", "request", "response"]
        if not all(field in data for field in required_fields):
            return jsonify({
                "status": "error",
                "message": f"Missing required fields. Required: {required_fields}"
            }), 400

        # Normalize path and method
        path = normalize_path(data["path"])
        method = data["method"].upper()

        # Generate UUID for the endpoint
        endpoint_id = str(uuid.uuid4())
        
        config = read_config()
        
        # Create endpoint configuration
        endpoint_config = {
            "id": endpoint_id,
            "path": path,
            "method": method,
            "request": data["request"],
            "response": data["response"],
            "created_at": str(datetime.now())
        }
        
        # Store endpoint by UUID
        config["endpoints"][endpoint_id] = endpoint_config
        write_config(config)
        
        return jsonify({
            "status": "success",
            "message": "Endpoint registered successfully",
            "endpoint_id": endpoint_id,
            "endpoint": endpoint_config
        }), 201
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/endpoints', methods=['GET'])
def list_endpoints():
    config = read_config()
    return jsonify({
        "status": "success",
        "endpoints": config["endpoints"]
    }), 200

@app.route('/endpoints/<endpoint_id>', methods=['GET'])
def get_endpoint(endpoint_id):
    config = read_config()
    
    if endpoint_id in config["endpoints"]:
        return jsonify({
            "status": "success",
            "endpoint": config["endpoints"][endpoint_id]
        }), 200
    
    return jsonify({
        "status": "error",
        "message": "Endpoint not found"
    }), 404

@app.route('/endpoints/<endpoint_id>', methods=['PUT'])
def update_endpoint(endpoint_id):
    try:
        data = request.get_json()
        config = read_config()
        
        if endpoint_id not in config["endpoints"]:
            return jsonify({
                "status": "error",
                "message": "Endpoint not found"
            }), 404
        
        endpoint = config["endpoints"][endpoint_id]
        
        # Update allowed fields
        if "request" in data:
            endpoint["request"] = data["request"]
        if "response" in data:
            endpoint["response"] = data["response"]
        if "method" in data:
            endpoint["method"] = data["method"].upper()
            
        endpoint["updated_at"] = str(datetime.now())
        write_config(config)
        
        return jsonify({
            "status": "success",
            "message": "Endpoint updated successfully",
            "endpoint": endpoint
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/endpoints/<endpoint_id>', methods=['DELETE'])
def delete_endpoint(endpoint_id):
    config = read_config()
    
    if endpoint_id in config["endpoints"]:
        deleted_endpoint = config["endpoints"].pop(endpoint_id)
        write_config(config)
        return jsonify({
            "status": "success",
            "message": "Endpoint deleted successfully",
            "deleted_endpoint": deleted_endpoint
        }), 200
    
    return jsonify({
        "status": "error",
        "message": "Endpoint not found"
    }), 404

@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def handle_request(path):
    try:
        config = read_config()
        normalized_path = normalize_path(path)
        
        # Find matching endpoint by path and method
        matching_endpoint = None
        for endpoint in config["endpoints"].values():
            if endpoint["path"] == normalized_path and endpoint["method"] == request.method:
                matching_endpoint = endpoint
                break
                
        if not matching_endpoint:
            return jsonify({
                "status": "error",
                "message": f"No endpoint found for {request.method} {normalized_path}"
            }), 404
            
        # Return the configured response
        return jsonify(matching_endpoint["response"]), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
