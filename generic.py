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
            initial_data = {
                "paths": {},        # Store path configurations
                "responses": {}     # Store response history
            }
            yaml.dump(initial_data, f)
        print("Config.yaml created successfully")

def read_config():
    create_empty_yaml()
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f) or {"paths": {}, "responses": {}}

def write_config(config):
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

def normalize_path(path):
    # Ensure path starts with / and remove trailing /
    return '/' + path.strip('/')

@app.route('/register_path', methods=['POST'])
def register_path():
    try:
        data = request.get_json()
        
        if not data.get("path"):
            return jsonify({
                "status": "error", 
                "message": "Path is required"
            }), 400

        # Normalize the path
        path = normalize_path(data["path"])
        
        # Get or default the methods
        methods = data.get("methods", ["GET"])
        if isinstance(methods, str):
            methods = [methods.upper()]
        else:
            methods = [m.upper() for m in methods]

        config = read_config()
        
        # Create path entry
        path_config = {
            "methods": methods,
            "request_template": data.get("request", {}),
            "response": data.get("response", {}),
            "created_at": str(datetime.now())
        }
        
        # Store by path instead of UUID
        config["paths"][path] = path_config
        write_config(config)
        
        return jsonify({
            "status": "success",
            "message": "Path registered successfully",
            "path": path
        }), 201
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/paths', methods=['GET'])
def list_paths():
    config = read_config()
    return jsonify({
        "status": "success",
        "paths": config["paths"]
    }), 200

@app.route('/paths/<path:path>', methods=['GET'])
def get_path_config(path):
    config = read_config()
    normalized_path = normalize_path(path)
    
    if normalized_path in config["paths"]:
        return jsonify({
            "status": "success",
            "path_config": config["paths"][normalized_path]
        }), 200
    
    return jsonify({
        "status": "error",
        "message": "Path not found"
    }), 404

@app.route('/paths/<path:path>', methods=['PUT'])
def update_path(path):
    try:
        data = request.get_json()
        config = read_config()
        normalized_path = normalize_path(path)
        
        if normalized_path not in config["paths"]:
            return jsonify({
                "status": "error",
                "message": "Path not found"
            }), 404
            
        # Update existing path configuration
        path_config = config["paths"][normalized_path]
        if "methods" in data:
            methods = data["methods"]
            if isinstance(methods, str):
                methods = [methods.upper()]
            else:
                methods = [m.upper() for m in methods]
            path_config["methods"] = methods
            
        if "request" in data:
            path_config["request_template"] = data["request"]
        if "response" in data:
            path_config["response"] = data["response"]
        
        path_config["updated_at"] = str(datetime.now())
        write_config(config)
        
        return jsonify({
            "status": "success",
            "message": "Path updated successfully",
            "path_config": path_config
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/paths/<path:path>', methods=['DELETE'])
def delete_path(path):
    config = read_config()
    normalized_path = normalize_path(path)
    
    if normalized_path in config["paths"]:
        del config["paths"][normalized_path]
        write_config(config)
        return jsonify({
            "status": "success",
            "message": "Path deleted successfully"
        }), 200
    
    return jsonify({
        "status": "error",
        "message": "Path not found"
    }), 404

@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def handle_request(path):
    try:
        config = read_config()
        normalized_path = normalize_path(path)
        
        # Find matching path
        path_config = config["paths"].get(normalized_path)
        if not path_config:
            return jsonify({
                "status": "error",
                "message": "Path not found"
            }), 404
            
        # Check if method is allowed
        if request.method not in path_config["methods"]:
            return jsonify({
                "status": "error",
                "message": f"Method {request.method} not allowed for this path"
            }), 405
            
        # Store the request/response history
        response_id = str(uuid.uuid4())
        response_record = {
            "path": normalized_path,
            "method": request.method,
            "request_data": request.get_json() if request.is_json else {},
            "response_data": path_config["response"],
            "timestamp": str(datetime.now())
        }
        
        config["responses"][response_id] = response_record
        write_config(config)
        
        # Return the configured response
        return jsonify(path_config["response"]), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/responses', methods=['GET'])
def get_responses():
    config = read_config()
    path_filter = request.args.get('path')
    
    if path_filter:
        normalized_path = normalize_path(path_filter)
        filtered_responses = {
            k: v for k, v in config["responses"].items() 
            if v["path"] == normalized_path
        }
        return jsonify({
            "status": "success",
            "responses": filtered_responses
        }), 200
        
    return jsonify({
        "status": "success",
        "responses": config["responses"]
    }), 200

if __name__ == '__main__':
    app.run(debug=True)
