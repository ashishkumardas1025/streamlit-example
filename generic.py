from flask import Flask, request, jsonify
import uuid
import yaml
import os
import json
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from werkzeug.routing import Rule

app = Flask(__name__)

CONFIG_FILE = "config.yaml"

class APISimulator:
    @staticmethod
    def create_empty_yaml() -> None:
        if not os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "w") as f:
                initial_structure = {
                    "endpoints": {},
                    "responses": {}
                }
                yaml.dump(initial_structure, f)
            print("Config.yaml created successfully")
        else:
            print("Config.yaml already exists")

    @staticmethod
    def read_config() -> Dict[str, Any]:
        with open(CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f) or {"endpoints": {}, "responses": {}}
            if "endpoints" not in config:
                config["endpoints"] = {}
            if "responses" not in config:
                config["responses"] = {}
            return config

    @staticmethod
    def write_config(config: Dict[str, Any]) -> None:
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    @classmethod
    def find_matching_endpoint(cls, path: str, method: str) -> Optional[Tuple[str, Dict]]:
        config = cls.read_config()
        for endpoint_id, endpoint_data in config["endpoints"].items():
            if endpoint_data["path"] == path and endpoint_data["method"] == method:
                return endpoint_id, endpoint_data
        return None

    @classmethod
    def register_endpoint(cls, endpoint_data: Dict[str, Any]) -> Tuple[str, bool]:
        config = cls.read_config()
        
        # Normalize the path
        if not endpoint_data["path"].startswith("/"):
            endpoint_data["path"] = f"/{endpoint_data['path']}"
            
        # Check if endpoint exists
        existing = cls.find_matching_endpoint(endpoint_data["path"], endpoint_data["method"])
        
        endpoint_info = {
            'path': endpoint_data['path'],
            'method': endpoint_data['method'].upper(),
            'request_template': endpoint_data.get('request_template', {}),
            'response_template': endpoint_data.get('response_template', {}),
            'headers': endpoint_data.get('headers', {}),
            'status_code': endpoint_data.get('status_code', 200),
            'updated_at': datetime.now().isoformat()
        }

        if existing:
            # Update existing endpoint
            endpoint_id, _ = existing
            config["endpoints"][endpoint_id].update(endpoint_info)
            cls.write_config(config)
            return endpoint_id, False
        else:
            # Create new endpoint
            endpoint_id = str(uuid.uuid4())
            endpoint_info['created_at'] = endpoint_info['updated_at']
            config["endpoints"][endpoint_id] = endpoint_info
            cls.write_config(config)
            return endpoint_id, True

    @classmethod
    def save_response(cls, endpoint_id: str, endpoint_info: Dict[str, Any], 
                     request_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        config = cls.read_config()
        
        response_details = {
            'endpoint_id': endpoint_id,
            'method': endpoint_info['method'],
            'path': endpoint_info['path'],
            'headers': endpoint_info['headers'],
            'request_body': request_data,
            'response_status_code': endpoint_info['status_code'],
            'response_body': endpoint_info['response_template'],
            'timestamp': datetime.now().isoformat()
        }

        dynamic_key = f"response_{endpoint_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        config["responses"][dynamic_key] = response_details
        cls.write_config(config)
        
        return dynamic_key, response_details

# Dynamic route handler for all registered endpoints
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def handle_dynamic_route(path):
    if not path.startswith('/'):
        path = f"/{path}"
        
    # Don't handle admin routes
    if path.startswith(('/register_endpoint', '/endpoints', '/responses')):
        return jsonify({
            'status': 'error',
            'message': 'Invalid route'
        }), 404

    matching_endpoint = APISimulator.find_matching_endpoint(path, request.method)
    
    if not matching_endpoint:
        return jsonify({
            'status': 'error',
            'message': f'No endpoint registered for {request.method} {path}'
        }), 404
        
    endpoint_id, endpoint_info = matching_endpoint
    request_data = request.get_json() if request.is_json else {}
    
    dynamic_key, response_details = APISimulator.save_response(
        endpoint_id, endpoint_info, request_data
    )
    
    return jsonify(endpoint_info['response_template']), endpoint_info['status_code']

# Register new endpoint
@app.route('/register_endpoint', methods=['POST'])
def register_endpoint():
    try:
        data = request.get_json()
        required_fields = ['path', 'method']
        if not all(field in data for field in required_fields):
            return jsonify({
                'status': 'error',
                'message': f'Missing required fields: {required_fields}'
            }), 400

        APISimulator.create_empty_yaml()
        endpoint_id, is_new = APISimulator.register_endpoint(data)
        
        return jsonify({
            'status': 'success',
            'message': 'New endpoint registered successfully' if is_new else 'Endpoint updated successfully',
            'endpoint_id': endpoint_id
        }), 201 if is_new else 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# List all endpoints
@app.route('/endpoints', methods=['GET'])
def list_endpoints():
    try:
        config = APISimulator.read_config()
        return jsonify({
            'status': 'success',
            'endpoints': config["endpoints"]
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Get response history
@app.route('/responses', methods=['GET'])
def list_responses():
    try:
        config = APISimulator.read_config()
        path_filter = request.args.get('path')
        method_filter = request.args.get('method')
        
        responses = config["responses"]
        if path_filter or method_filter:
            filtered_responses = {}
            for key, response in responses.items():
                if path_filter and response['path'] != path_filter:
                    continue
                if method_filter and response['method'] != method_filter.upper():
                    continue
                filtered_responses[key] = response
            responses = filtered_responses
            
        return jsonify({
            'status': 'success',
            'responses': responses
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
