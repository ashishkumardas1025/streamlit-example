import random
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from jinja2 import escape
import yaml
import os
# import openai

app = Flask(__name__)
CONFIG_FILE = "config.yaml"

# openai.api_key = "your-openai-api-key"  # Replace with your actual OpenAI API key

# Ensure config file exists
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

# def generate_dynamic_value(schema):
#     """Use OpenAI to generate structured random responses based on the schema."""
#     prompt = f"Generate a JSON response matching this schema: {schema}"
#     response = openai.ChatCompletion.create(
#         model="gpt-3.5-turbo",
#         messages=[{"role": "system", "content": "You are a helpful AI that generates structured JSON responses."},
#                   {"role": "user", "content": prompt}]
#     )
#     return response["choices"][0]["message"]["content"]
@app.route('/olbb-simulator/<path:path>', methods=['POST'])
def register_endpoint(path):
    """Registers a new endpoint with request and response schemas."""
    try:
        data = request.get_json()
        config = read_config()
        normalized_path = normalize_path(path)
        method = data.get("method", "POST").upper()

        if "request" not in data or "response" not in data:
            return jsonify({"status": "error", "message": "Missing request or response schema"}), 400

        if normalized_path not in config["endpoints"]:
            config["endpoints"][normalized_path] = {"instances": []}

        instances = config["endpoints"][normalized_path]["instances"]
        
        if len(instances) == 0:
            instance_id = None  # No UUID for first request
        else:
            instance_id = str(uuid.uuid4())
        
        new_instance = {
            "id": instance_id,
            "method": method,
            "request_schema": data["request"],
            "response_schema": data["response"],
            "created_at": str(datetime.now())
        }
        instances.append(new_instance)
        write_config(config)

        return jsonify({"status": "success", "message": "New endpoint registered successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# @app.route('/olbb-simulator/ai/<path:path>', methods=['POST'])
# def handle_dynamic_request(path):
#     """Handles dynamic API requests, generating responses based on stored schemas."""
#     try:
#         config = read_config()
#         normalized_path = normalize_path(path)
#         request_data = request.get_json()

#         if normalized_path in config["endpoints"]:
#             endpoint_data = config["endpoints"][normalized_path]
#             response_schema = endpoint_data.get("response_schema", {})
#             dynamic_response = generate_dynamic_value(response_schema)

#             if "instances" not in endpoint_data:
#                 endpoint_data["instances"] = []

#             if len(endpoint_data["instances"]) == 0:
#                 instance_id = None  # No UUID for first request
#             else:
#                 instance_id = str(uuid.uuid4())

#             new_entry = {
#                 "id": instance_id,
#                 "method": "POST",
#                 "request": request_data,
#                 "response": dynamic_response,
#                 "created_at": str(datetime.now())
#             }
#             endpoint_data["instances"].append(new_entry)
#             write_config(config)

#             return jsonify(dynamic_response), 200

#         return jsonify({"status": "error", "message": f"No endpoint found for {normalized_path}"}), 404
#     except Exception as e:
#         return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/olbb-simulator/<path:path>', methods=['GET'])
def get_all_endpoints(path):
    config = read_config()
    normalized_path = normalize_path(path)
    if normalized_path in config["endpoints"]:
        return jsonify({"status": "success", "endpoints": config["endpoints"][normalized_path]}), 200
    return jsonify({"status": "error", "message": "No endpoints found for the given path"}), 404

@app.route('/olbb-simulator/<path:path>/<endpoint_id>', methods=['GET'])
def get_endpoint(path, endpoint_id):
    config = read_config()
    normalized_path = normalize_path(path)
    if normalized_path in config["endpoints"]:
        for instance in config["endpoints"][normalized_path].get("instances", []):
            if instance["id"] == endpoint_id:
                return jsonify({"status": "success", "endpoint": instance}), 200
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404

@app.route('/olbb-simulator/<path:path>/<endpoint_id>', methods=['PUT'])
def update_endpoint(path, endpoint_id):
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

@app.route('/olbb-simulator/<path:path>/<endpoint_id>', methods=['DELETE'])
def delete_endpoint(path, endpoint_id):
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






#changes
@app.route('/olbb-simulator/<path:path>', methods=['GET'])
def get_all_endpoints(path):
    config = read_config()
    normalized_path = normalize_path(path)
    if normalized_path in config["endpoints"]:
        return jsonify({"status": "success", "endpoints": config["endpoints"][normalized_path]["instances"]}), 200
    return jsonify({"status": "error", "message": "No endpoints found for the given path"}), 404

@app.route('/olbb-simulator/<path:path>', methods=['PUT'])
def update_endpoint_general(path):
    try:
        data = request.get_json()
        config = read_config()
        normalized_path = normalize_path(path)

        if normalized_path in config["endpoints"]:
            instances = config["endpoints"][normalized_path]["instances"]
            if len(instances) == 1:
                instances[0].update(data)
                instances[0]["updated_at"] = str(datetime.now())
                write_config(config)
                return jsonify({"status": "success", "message": "Endpoint updated successfully", "endpoint": instances[0]}), 200
        return jsonify({"status": "error", "message": "Endpoint not found or multiple instances exist"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/olbb-simulator/<path:path>/<endpoint_id>', methods=['PUT'])
def update_endpoint_by_id(path, endpoint_id):
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
    config = read_config()
    normalized_path = normalize_path(path)
    if normalized_path in config["endpoints"]:
        del config["endpoints"][normalized_path]
        write_config(config)
        return jsonify({"status": "success", "message": "All endpoints deleted successfully"}), 200
    return jsonify({"status": "error", "message": "No endpoints found for the given path"}), 404

@app.route('/olbb-simulator/<path:path>/<endpoint_id>', methods=['DELETE'])
def delete_endpoint_by_id(path, endpoint_id):
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

