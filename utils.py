from flask import Flask, request, jsonify
import yaml
import os
from typing import Dict, Any, List
import jsonschema
from jsonschema import validate, ValidationError
from datetime import datetime

app = Flask(__name__)

# Global storage and configuration
storage = {}
id_counters = {}
spec = {}
endpoints = {}

class ValidationException(Exception):
    """Custom exception for schema validation errors"""
    pass

def resolve_schema_reference(schema: Dict) -> Dict:
    """Resolve $ref in schema"""
    if '$ref' in schema:
        ref_path = schema['$ref'].split('/')
        current = spec
        for part in ref_path[1:]:  # Skip the first '#'
            current = current[part]
        return current
    return schema

def get_next_id(entity_type: str) -> str:
    """Get next ID for an entity type"""
    if entity_type not in id_counters:
        id_counters[entity_type] = 1
    current_id = str(id_counters[entity_type])
    id_counters[entity_type] += 1
    return current_id

def initialize_storage(entity_type: str):
    """Initialize storage for an entity type if it doesn't exist"""
    if entity_type not in storage:
        storage[entity_type] = {}

def get_request_schema(path: str, method: str) -> Dict:
    """Get request schema from OpenAPI spec"""
    path_spec = spec.get('paths', {}).get(path, {})
    method_spec = path_spec.get(method.lower(), {})
    request_body = method_spec.get('requestBody', {})
    schema = request_body.get('content', {}).get('application/json', {}).get('schema', {})
    return resolve_schema_reference(schema)

def get_response_schema(path: str, method: str, status_code: str) -> Dict:
    """Get response schema from OpenAPI spec"""
    path_spec = spec.get('paths', {}).get(path, {})
    method_spec = path_spec.get(method.lower(), {})
    responses = method_spec.get('responses', {})
    response_spec = responses.get(str(status_code), {})
    schema = response_spec.get('content', {}).get('application/json', {}).get('schema', {})
    return resolve_schema_reference(schema)

def validate_schema(data: Dict, schema: Dict, context: str):
    """Validate data against schema"""
    if not schema:
        return
    try:
        validate(instance=data, schema=schema)
    except ValidationError as e:
        raise ValidationException(f"{context} validation failed: {str(e)}")

def extract_path_param(path: str) -> str:
    """Extract the path parameter name from a path template"""
    parts = path.split('{')
    if len(parts) > 1:
        return parts[1].split('}')[0]
    return None

def register_endpoints():
    """Register endpoints dynamically based on OpenAPI spec"""
    for path, path_spec in spec.get('paths', {}).items():
        # Extract the base resource type from the path
        parts = path.strip('/').split('/')
        if not parts:
            continue
            
        resource_type = parts[0]
        initialize_storage(resource_type)
        
        # Register collection endpoints (e.g., /books)
        if len(parts) == 1:
            if 'post' in path_spec:
                register_create_endpoint(resource_type, path)
            if 'get' in path_spec:
                register_list_endpoint(resource_type, path)
                
        # Register instance endpoints (e.g., /books/{bookId})
        elif len(parts) == 2 and '{' in parts[1]:
            id_param = extract_path_param(path)
            if 'get' in path_spec:
                register_get_endpoint(resource_type, path, id_param)
            if 'put' in path_spec:
                register_update_endpoint(resource_type, path, id_param)
            if 'delete' in path_spec:
                register_delete_endpoint(resource_type, path, id_param)

def register_create_endpoint(resource_type: str, path: str):
    """Register POST endpoint for creating resources"""
    @app.route(path, methods=['POST'])
    def create():
        try:
            data = request.get_json()
            validate_schema(data, get_request_schema(path, 'post'), "Request")
            
            resource_id = get_next_id(resource_type)
            data['id'] = resource_id
            data['created_at'] = datetime.utcnow().isoformat()
            
            storage[resource_type][resource_id] = data
            validate_schema(data, get_response_schema(path, 'post', 201), "Response")
            return jsonify(data), 201
        
        except ValidationException as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 400

def register_list_endpoint(resource_type: str, path: str):
    """Register GET endpoint for listing resources"""
    @app.route(path, methods=['GET'])
    def list_resources():
        try:
            resources = list(storage[resource_type].values())
            validate_schema(resources, get_response_schema(path, 'get', 200), "Response")
            return jsonify(resources), 200
        
        except ValidationException as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 400

def register_get_endpoint(resource_type: str, path: str, id_param: str):
    """Register GET endpoint for retrieving a single resource"""
    @app.route(path, methods=['GET'])
    def get(resource_id):
        try:
            if resource_id not in storage[resource_type]:
                return jsonify({"error": f"{resource_type} not found"}), 404
            
            resource = storage[resource_type][resource_id]
            validate_schema(resource, get_response_schema(path, 'get', 200), "Response")
            return jsonify(resource), 200
        
        except ValidationException as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 400

def register_update_endpoint(resource_type: str, path: str, id_param: str):
    """Register PUT endpoint for updating resources"""
    @app.route(path, methods=['PUT'])
    def update(resource_id):
        try:
            if resource_id not in storage[resource_type]:
                return jsonify({"error": f"{resource_type} not found"}), 404
                
            data = request.get_json()
            validate_schema(data, get_request_schema(path, 'put'), "Request")
            
            # Preserve id and created_at
            data['id'] = resource_id
            data['created_at'] = storage[resource_type][resource_id]['created_at']
            
            storage[resource_type][resource_id] = data
            validate_schema(data, get_response_schema(path, 'put', 200), "Response")
            return jsonify(data), 200
        
        except ValidationException as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 400

def register_delete_endpoint(resource_type: str, path: str, id_param: str):
    """Register DELETE endpoint for removing resources"""
    @app.route(path, methods=['DELETE'])
    def delete(resource_id):
        try:
            if resource_id not in storage[resource_type]:
                return jsonify({"error": f"{resource_type} not found"}), 404
            
            storage[resource_type].pop(resource_id)
            return '', 204
        
        except Exception as e:
            return jsonify({"error": str(e)}), 400

def load_spec(spec_file: str) -> Dict:
    """Load and parse the OpenAPI specification"""
    if not os.path.exists(spec_file):
        raise FileNotFoundError(f"Specification file {spec_file} not found.")
    with open(spec_file, 'r') as file:
        return yaml.safe_load(file)

if __name__ == '__main__':
    import sys
    spec_file = sys.argv[1] if len(sys.argv) > 1 else 'openapi.yaml'
    spec = load_spec(spec_file)
    register_endpoints()
    app.run(debug=True, port=5000)
