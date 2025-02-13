import uuid
from datetime import datetime
from flask import Flask, request, jsonify
import yaml
import os

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

@app.route('/olbb-simulator/<path:path>', methods=['POST'])
def register_endpoint(path):
    """Registers a new endpoint with request and response."""
    try:
        data = request.get_json()
        config = read_config()
        normalized_path = normalize_path(path)
        method = data.get("method", "POST").upper()

        if "request" not in data or "response" not in data:
            return jsonify({"status": "error", "message": "Missing request or response"}), 400

        if normalized_path not in config["endpoints"]:
            config["endpoints"][normalized_path] = {"instances": []}

        instances = config["endpoints"][normalized_path]["instances"]
        
        for instance in instances:
            if instance["request"] == data["request"] and instance["response"] == data["response"]:
                return jsonify({"status": "error", "message": "Duplicate request and response"}), 400
        
        new_instance = {
            "id": str(uuid.uuid4()),
            "method": method,
            "request": data["request"],
            "response": data["response"],
            "created_at": str(datetime.now())
        }
        instances.append(new_instance)
        write_config(config)

        return jsonify({"status": "success", "message": "New endpoint registered successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/olbb-simulator/<path:path>', methods=['GET'])
def get_all_endpoints(path):
    """Fetches all endpoint data for the given path."""
    config = read_config()
    normalized_path = normalize_path(path)
    if normalized_path in config["endpoints"]:
        instances = config["endpoints"][normalized_path]["instances"]
        response_data = [{
            "id": instance["id"],
            "path": normalized_path,
            "request": instance["request"],
            "response": instance["response"]
        } for instance in instances]
        return jsonify({"status": "success", "message": f"{len(instances)} endpoints found", "endpoints": response_data}), 200
    return jsonify({"status": "error", "message": "No endpoints found for the given path"}), 404

@app.route('/olbb-simulator/<path:path>/<endpoint_id>', methods=['GET'])
def get_endpoint(path, endpoint_id):
    """Fetches a specific endpoint by ID."""
    config = read_config()
    normalized_path = normalize_path(path)
    if normalized_path in config["endpoints"]:
        for instance in config["endpoints"][normalized_path].get("instances", []):
            if instance["id"] == endpoint_id:
                return jsonify({"status": "success", "endpoint": instance}), 200
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404

@app.route('/olbb-simulator/<path:path>/<endpoint_id>', methods=['PUT'])
def update_endpoint(path, endpoint_id):
    """Updates an existing endpoint."""
    try:
        data = request.get_json()
        config = read_config()
        normalized_path = normalize_path(path)
        
        if normalized_path in config["endpoints"]:
            for instance in config["endpoints"][normalized_path].get("instances", []):
                if instance["id"] == endpoint_id:
                    instance.update(data)
                    instance["updated_at"] = str(datetime.now())
                    write_config(config)
                    return jsonify({"status": "success", "message": "Endpoint updated successfully", "endpoint": instance}), 200
        return jsonify({"status": "error", "message": "Endpoint not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/olbb-simulator/<path:path>', methods=['DELETE'])
def delete_all_endpoints(path):
    """Deletes all instances for a given path."""
    config = read_config()
    normalized_path = normalize_path(path)
    if normalized_path in config["endpoints"]:
        del config["endpoints"][normalized_path]
        write_config(config)
        return jsonify({"status": "success", "message": "All endpoints deleted for the given path"}), 200
    return jsonify({"status": "error", "message": "No endpoints found for the given path"}), 404

@app.route('/olbb-simulator/<path:path>/<endpoint_id>', methods=['DELETE'])
def delete_endpoint(path, endpoint_id):
    """Deletes a specific endpoint instance."""
    config = read_config()
    normalized_path = normalize_path(path)
    
    if normalized_path in config["endpoints"]:
        instances = config["endpoints"][normalized_path].get("instances", [])
        for i, instance in enumerate(instances):
            if instance["id"] == endpoint_id:
                del instances[i]
                write_config(config)
                return jsonify({"status": "success", "message": "Endpoint deleted successfully"}), 200
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)




#validation
def validate_schema(expected_schema, actual_data):
    """Validates if all required fields exist in the actual data."""
    missing_fields = [field for field in expected_schema if field not in actual_data]
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"
    return True, None

@app.route('/olbb-simulator/<path:path>', methods=['POST'])
def register_endpoint(path):
    """Registers a new endpoint with request and response validation."""
    try:
        data = request.get_json()
        config = read_config()
        normalized_path = normalize_path(path)
        method = data.get("method", "POST").upper()

        if "request" not in data or "response" not in data:
            return jsonify({"status": "error", "message": "Missing request or response"}), 400

        if normalized_path not in config["endpoints"]:
            config["endpoints"][normalized_path] = {"instances": []}

        instances = config["endpoints"][normalized_path]["instances"]

        # Validate request & response schema fields
        for instance in instances:
            if instance["request"] == data["request"] and instance["response"] == data["response"]:
                return jsonify({"status": "error", "message": "Duplicate request and response"}), 400

            # Check for missing fields
            is_valid_request, request_error = validate_schema(instance["request"], data["request"])
            is_valid_response, response_error = validate_schema(instance["response"], data["response"])

            if not is_valid_request:
                return jsonify({"status": "error", "message": request_error}), 400
            if not is_valid_response:
                return jsonify({"status": "error", "message": response_error}), 400

        # Store new request-response pair if validation passes
        new_instance = {
            "id": str(uuid.uuid4()),
            "method": method,
            "request": data["request"],
            "response": data["response"],
            "created_at": str(datetime.now())
        }
        instances.append(new_instance)
        write_config(config)

        return jsonify({"status": "success", "message": "New endpoint registered successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

