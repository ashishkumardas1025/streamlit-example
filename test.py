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

def generate_dynamic_value(schema):
    """Use OpenAI to generate structured random responses based on the schema."""
    prompt = f"Generate a JSON object matching this schema: {schema}"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "You are a helpful AI that generates structured JSON objects."},
                  {"role": "user", "content": prompt}]
    )
    return response["choices"][0]["message"]["content"]

@app.route('/olbb-simulator/register', methods=['POST'])
def register_endpoint():
    """Registers a new endpoint with the actual request and response schema."""
    try:
        data = request.get_json()
        required_fields = ["method", "request", "response"]
        if not all(field in data for field in required_fields):
            return jsonify({"status": "error", "message": f"Missing required fields. Required: {required_fields}"}), 400

        path = normalize_path(data.get("path", ""))
        config = read_config()
        method = data["method"].upper()
        
        if path not in config["endpoints"]:
            config["endpoints"][path] = {}
        
        config["endpoints"][path][method] = {
            "method": method,
            "request_schema": data["request"],
            "response_schema": data["response"],
            "created_at": str(datetime.now())
        }
        write_config(config)

        return jsonify({"status": "success", "message": "New endpoint registered successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/olbb-simulator/<path:path>', methods=['POST'])
def handle_dynamic_request(path):
    """Handles requests and validates them against stored schema before generating responses."""
    try:
        config = read_config()
        normalized_path = normalize_path(path)
        method = "POST"

        if normalized_path in config["endpoints"] and method in config["endpoints"][normalized_path]:
            stored_data = config["endpoints"][normalized_path][method]
            request_schema = stored_data.get("request_schema", {})
            response_schema = stored_data.get("response_schema", {})
            
            # Validate request
            request_data = request.get_json()
            if not all(key in request_data for key in request_schema.keys()):
                return jsonify({"status": "error", "message": "Invalid request parameters"}), 400
            
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

@app.route('/olbb-simulator/<path:path>', methods=['PUT'])
def update_endpoint(path):
    try:
        data = request.get_json()
        config = read_config()
        normalized_path = normalize_path(path)
        method = "PUT"
        
        if normalized_path not in config["endpoints"]:
            return jsonify({"status": "error", "message": "Endpoint not found"}), 404
        
        config["endpoints"][normalized_path][method] = {
            "method": method,
            "request_schema": data.get("request", {}),
            "response_schema": data.get("response", {}),
            "updated_at": str(datetime.now())
        }
        write_config(config)

        return jsonify({"status": "success", "message": "Endpoint updated successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/olbb-simulator/<path:path>', methods=['DELETE'])
def delete_endpoint(path):
    config = read_config()
    normalized_path = normalize_path(path)
    
    if normalized_path in config["endpoints"]:
        del config["endpoints"][normalized_path]
        write_config(config)
        return jsonify({"status": "success", "message": "Endpoint deleted successfully"}), 200
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)



#register

def register_or_handle_request(path):
    """Handles both endpoint registration and request processing dynamically."""
    try:
        data = request.get_json()
        config = read_config()
        normalized_path = normalize_path(path)
        method = request.method.upper()

        if "method" in data and "request" in data and "response" in data:
            # Register new endpoint
            if normalized_path not in config["endpoints"]:
                config["endpoints"][normalized_path] = {}
            
            config["endpoints"][normalized_path][method] = {
                "method": method,
                "request_schema": data["request"],
                "response_schema": data["response"],
                "created_at": str(datetime.now())
            }
            write_config(config)
            return jsonify({"status": "success", "message": "New endpoint registered successfully"}), 200
        
        # Validate request schema before handling response
        if normalized_path in config["endpoints"] and method in config["endpoints"][normalized_path]:
            stored_data = config["endpoints"][normalized_path][method]
            request_schema = stored_data.get("request_schema", {})
            response_schema = stored_data.get("response_schema", {})
            
            # Validate request
            request_data = request.get_json()
            if not all(key in request_data for key in request_schema.keys()):
                return jsonify({"status": "error", "message": "Invalid request parameters"}), 400
            
            dynamic_response = generate_dynamic_value(response_schema)
            return jsonify(dynamic_response), 200

        return jsonify({"status": "error", "message": f"No endpoint found for {normalized_path}"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
