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




def handle_dynamic_request_response(path):
    """Handles request and response schema-based dynamic generation and stores results."""
    try:
        config = read_config()
        normalized_path = normalize_path(path)

        if normalized_path not in config["endpoints"]:
            return jsonify({"status": "error", "message": "No endpoints found for the given path"}), 404

        endpoint_id = str(uuid.uuid4())
        instances = config["endpoints"][normalized_path].get("instances", [])
        
        if not instances:
            return jsonify({"status": "error", "message": "No schema instances found for this path"}), 404

        generated_data = []
        
        for instance in instances:
            request_schema = instance.get("request_schema")
            response_schema = instance.get("response_schema")
            
            if not request_schema or not response_schema:
                continue
                
            # Generate data with explicit error logging
            print(f"Generating request for schema: {json.dumps(request_schema)}")
            generated_request = generate_dynamic_value(request_schema, "request")
            print(f"Generated request: {json.dumps(generated_request)}")
            
            print(f"Generating response for schema: {json.dumps(response_schema)}")
            generated_response = generate_dynamic_value(response_schema, "response")
            print(f"Generated response: {json.dumps(generated_response)}")

            new_instance = {
                "id": endpoint_id,
                "method": "POST",
                "generated_request": generated_request,
                "generated_response": generated_response,
                "created_at": str(datetime.now())
            }
            
            instances.append(new_instance)
            generated_data.append({
                "id": endpoint_id,
                "request": generated_request,
                "response": generated_response,
                "timestamp": str(datetime.now())
            })

        if generated_data:
            write_config(config)
            return jsonify({
                "status": "success",
                "message": f"{len(generated_data)} dynamic request-response pairs generated",
                "data": generated_data
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "No data could be generated. Check if schemas are properly defined."
            }), 400

    except Exception as e:
        print(f"Error in handle_dynamic_request_response: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
