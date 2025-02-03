#openai code.
import random
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
import yaml
import os
import openai

app = Flask(__name__)
CONFIG_FILE = "config.yaml"

openai.api_key = "your-openai-api-key"  # Replace with your actual OpenAI API key

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

@app.route('/olbb-simulator/register', methods=['POST'])
def register_endpoint():
    """Registers a new endpoint with the actual response schema."""
    try:
        data = request.get_json()
        required_fields = ["method", "request", "response"]
        if not all(field in data for field in required_fields):
            return jsonify({"status": "error", "message": f"Missing required fields. Required: {required_fields}"}), 400

        path = normalize_path(data.get("path", ""))
        config = read_config()
        method = data["method"].upper()
        endpoint_id = str(uuid.uuid4())

        if path not in config["endpoints"]:
            config["endpoints"][path] = {}

        config["endpoints"][path][endpoint_id] = {
            "id": endpoint_id,
            "method": method,
            "request": data["request"],
            "response_schema": data["response"],  # Store response schema
            "created_at": str(datetime.now())
        }
        write_config(config)

        return jsonify({"status": "success", "message": "New endpoint registered successfully", "endpoint_id": endpoint_id}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/olbb-simulator/<path:path>', methods=['POST'])
def handle_dynamic_request(path):
    """Handles requests and generates dynamic responses based on stored schema."""
    try:
        config = read_config()
        normalized_path = normalize_path(path)

        if normalized_path in config["endpoints"]:
            for endpoint in config["endpoints"][normalized_path].values():
                response_schema = endpoint.get("response_schema", {})
                dynamic_response = generate_dynamic_value(response_schema)
                return jsonify(dynamic_response), 200

        return jsonify({"status": "error", "message": f"No endpoint found for {normalized_path}"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

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
    if normalized_path in config["endpoints"] and endpoint_id in config["endpoints"][normalized_path]:
        return jsonify({"status": "success", "endpoint": config["endpoints"][normalized_path][endpoint_id]}), 200
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404

@app.route('/olbb-simulator/<path:path>/<endpoint_id>', methods=['PUT'])
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

@app.route('/olbb-simulator/<path:path>/<endpoint_id>', methods=['DELETE'])
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

if __name__ == '__main__':
    app.run(debug=True)
