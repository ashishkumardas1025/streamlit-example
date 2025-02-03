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

def generate_dynamic_value(schema):
    """Use OpenAI to generate structured random responses based on the schema."""
    prompt = f"Generate a JSON response matching this schema: {schema}"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "You are a helpful AI that generates structured JSON responses."},
                  {"role": "user", "content": prompt}]
    )
    return response["choices"][0]["message"]["content"]

@app.route('/endpoint/<path:path>', methods=['POST'])
def register_endpoint(path):
    """Registers a new endpoint with AI-generated dynamic values."""
    try:
        data = request.get_json()
        required_fields = ["method", "request", "response"]
        if not all(field in data for field in required_fields):
            return jsonify({"status": "error", "message": f"Missing required fields. Required: {required_fields}"}), 400

        path = normalize_path(path)
        config = read_config()
        method = data["method"].upper()
        endpoint_id = str(uuid.uuid4())

        # Generate AI-powered response
        ai_generated_response = generate_dynamic_value(data["response"])

        if path not in config["endpoints"]:
            config["endpoints"][path] = {}

        config["endpoints"][path][endpoint_id] = {
            "id": endpoint_id,
            "method": method,
            "request": data["request"],
            "response": ai_generated_response,
            "created_at": str(datetime.now())
        }
        write_config(config)

        return jsonify({"status": "success", "message": "New endpoint registered successfully", "endpoint_id": endpoint_id}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/endpoint/<path:path>', methods=['GET'])
def get_all_endpoints(path):
    config = read_config()
    normalized_path = normalize_path(path)
    if normalized_path in config["endpoints"]:
        return jsonify({"status": "success", "endpoints": config["endpoints"][normalized_path]}), 200
    return jsonify({"status": "error", "message": "No endpoints found for the given path"}), 404

@app.route('/endpoint/<path:path>/<endpoint_id>', methods=['GET'])
def get_endpoint(path, endpoint_id):
    config = read_config()
    normalized_path = normalize_path(path)
    if normalized_path in config["endpoints"] and endpoint_id in config["endpoints"][normalized_path]:
        return jsonify({"status": "success", "endpoint": config["endpoints"][normalized_path][endpoint_id]}), 200
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404

@app.route('/endpoint/<path:path>/<endpoint_id>', methods=['PUT'])
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

@app.route('/endpoint/<path:path>/<endpoint_id>', methods=['DELETE'])
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


#bedrock improvements

import random
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
import yaml
import os
import boto3
import json

app = Flask(__name__)
CONFIG_FILE = "config.yaml"

# Initialize Bedrock client
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')  # Adjust region as needed

def generate_dynamic_value(schema):
    """
    Use AWS Bedrock Claude to generate structured random responses based on the schema.
    
    Args:
        schema (dict/str): The response schema to use for generation
    
    Returns:
        str: AI-generated response matching the schema
    """
    # Prepare the prompt for Claude
    prompt = f"""You are an AI assistant generating a JSON response that strictly matches the following schema structure:
{json.dumps(schema, indent=2)}

Please generate a realistic, varied response that follows the exact structure of the given schema. 
Important rules:
- Maintain the exact same keys as in the original schema
- Generate plausible, random values for each key
- Preserve the data types of the original schema
- Do not include any explanatory text, only return the pure JSON

Generate the response now:"""

    # Prepare the request body for Bedrock Claude
    body = json.dumps({
        "prompt": prompt,
        "max_tokens": 1000,
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 250
    })

    # Invoke the model
    try:
        response = bedrock_runtime.invoke_model(
            modelId="anthropic.claude-v2",  # Use the appropriate Claude model ID
            body=body
        )
        
        # Extract and parse the response
        response_body = json.loads(response["body"].read())
        
        # Try to parse the response text as JSON
        try:
            # Extract the text and attempt to parse it
            generated_response = json.loads(response_body['completion'].strip())
            return generated_response
        except (json.JSONDecodeError, KeyError):
            # Fallback: use the raw text if JSON parsing fails
            return response_body['completion'].strip()

    except Exception as e:
        # Handle any errors in generation
        print(f"Error generating dynamic value: {e}")
        return {"error": "Could not generate dynamic response"}

# The rest of the code remains the same as in the original file
# Only the generate_dynamic_value() function has been replaced

# Existing routes and methods remain unchanged
