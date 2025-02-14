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



#ai operation
@app.route('/olbb-simulator/ai/<path:path>', methods=['POST'])
def handle_dynamic_request_response(path):
    """Handles request and response schema-based dynamic generation and stores results."""
    try:
        config = read_config()
        normalized_path = normalize_path(path)

        if normalized_path not in config["endpoints"]:
            return jsonify({
                "status": "error", 
                "message": "No endpoints found for the given path"
            }), 404

        # Get instances for the path
        instances = config["endpoints"][normalized_path].get("instances", [])
        if not instances:
            return jsonify({
                "status": "error", 
                "message": "No request/response schemas found for this endpoint"
            }), 404

        # Use the first instance's schema as template
        template_instance = instances[0]
        
        # Generate dynamic values based on the template schemas
        generated_request = generate_dynamic_value(template_instance["request"])
        generated_response = generate_dynamic_value(template_instance["response"])

        # Create new instance with generated values
        new_instance = {
            "id": str(uuid.uuid4()),
            "method": "POST",
            "request": generated_request,
            "response": generated_response,
            "created_at": str(datetime.now())
        }

        # Add to instances
        instances.append(new_instance)
        write_config(config)

        return jsonify({
            "status": "success",
            "data": {
                "generated_request": generated_request,
                "generated_response": generated_response,
                "instance_id": new_instance["id"]
            }
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": f"Error processing request: {str(e)}"
        }), 500
