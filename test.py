from flask import Flask, request, jsonify
import yaml
import os
import jsonschema
from jsonschema import validate, ValidationError
from datetime import datetime

app = Flask(__name__)

# Global storage and configuration
storage = {}
id_counters = {}
spec = {}

class ValidationException(Exception):
    """Custom exception for schema validation errors"""
    pass

def resolve_schema_reference(schema):
    """Recursively resolve $ref in schema"""
    if isinstance(schema, dict) and "$ref" in schema:
        ref_path = schema['$ref'].lstrip('#/').split('/')
        ref_obj = spec
        try:
            for part in ref_path:
                ref_obj = ref_obj[part]
            return resolve_schema_reference(ref_obj)  # Ensure all nested references are resolved
        except KeyError:
            raise ValueError(f"Invalid reference path: {schema['$ref']}")
    elif isinstance(schema, dict):
        return {key: resolve_schema_reference(value) for key, value in schema.items()}
    elif isinstance(schema, list):
        return [resolve_schema_reference(item) for item in schema]
    return schema

def get_next_id(entity_type):
    """Get next ID for an entity type"""
    if entity_type not in id_counters:
        id_counters[entity_type] = 1
    current_id = str(id_counters[entity_type])
    id_counters[entity_type] += 1
    return current_id

def initialize_storage(entity_type):
    """Initialize storage for an entity type if it doesn't exist"""
    if entity_type not in storage:
        storage[entity_type] = {}

def get_request_schema(path, method):
    """Get request schema from OpenAPI spec"""
    schema = spec.get('paths', {}).get(path, {}).get(method.lower(), {}).get(
        'requestBody', {}).get('content', {}).get('application/json', {}).get('schema', {})
    return resolve_schema_reference(schema)

def get_response_schema(path, method, status_code):
    """Get response schema from OpenAPI spec"""
    schema = spec.get('paths', {}).get(path, {}).get(method.lower(), {}).get(
        'responses', {}).get(str(status_code), {}).get('content', {}).get('application/json', {}).get('schema', {})
    return resolve_schema_reference(schema)

def validate_schema(data, schema, context):
    """Validate data against schema"""
    if schema:
        try:
            validate(instance=data, schema=schema)
        except ValidationError as e:
            raise ValidationException(f"{context} validation failed: {str(e)}")

def extract_path_param(path):
    """Extract the path parameter name from a path template"""
    parts = path.split('{')
    return parts[1].split('}')[0] if len(parts) > 1 else None

def register_endpoints():
    """Register endpoints dynamically based on OpenAPI spec"""
    for path, path_spec in spec.get('paths', {}).items():
        parts = path.strip('/').split('/')
        if not parts:
            continue
        resource_type = parts[0]
        initialize_storage(resource_type)
        if len(parts) == 1:  # Collection endpoints
            if 'post' in path_spec:
                register_create_endpoint(resource_type, path)
            if 'get' in path_spec:
                register_list_endpoint(resource_type, path)
        elif len(parts) == 2 and '{' in parts[1]:  # Single resource endpoints
            id_param = extract_path_param(path)
            if 'get' in path_spec:
                register_get_endpoint(resource_type, path, id_param)
            if 'put' in path_spec:
                register_update_endpoint(resource_type, path, id_param)
            if 'delete' in path_spec:
                register_delete_endpoint(resource_type, path, id_param)

def register_create_endpoint(resource_type, path):
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

def register_list_endpoint(resource_type, path):
    """Register GET endpoint for listing resources"""
    @app.route(path, methods=['GET'])
    def list_resources():
        try:
            resources = list(storage[resource_type].values())
            validate_schema(resources, get_response_schema(path, 'get', 200), "Response")
            return jsonify(resources), 200
        except ValidationException as e:
            return jsonify({"error": str(e)}), 400

def register_get_endpoint(resource_type, path, id_param):
    """Register GET endpoint for retrieving a single resource"""
    @app.route(path.replace(f'{{{id_param}}}', '<string:resource_id>'), methods=['GET'])
    def get(resource_id):
        if resource_id not in storage[resource_type]:
            return jsonify({"error": f"{resource_type} not found"}), 404
        return jsonify(storage[resource_type][resource_id]), 200

def register_update_endpoint(resource_type, path, id_param):
    """Register PUT endpoint for updating resources"""
    @app.route(path.replace(f'{{{id_param}}}', '<string:resource_id>'), methods=['PUT'])
    def update(resource_id):
        if resource_id not in storage[resource_type]:
            return jsonify({"error": f"{resource_type} not found"}), 404
        data = request.get_json()
        validate_schema(data, get_request_schema(path, 'put'), "Request")
        data['id'] = resource_id
        storage[resource_type][resource_id] = data
        return jsonify(data), 200

def register_delete_endpoint(resource_type, path, id_param):
    """Register DELETE endpoint for removing resources"""
    @app.route(path.replace(f'{{{id_param}}}', '<string:resource_id>'), methods=['DELETE'])
    def delete(resource_id):
        if resource_id not in storage[resource_type]:
            return jsonify({"error": f"{resource_type} not found"}), 404
        storage[resource_type].pop(resource_id)
        return '', 204

def load_spec(spec_file):
    """Load and parse the OpenAPI specification"""
    with open(spec_file, 'r') as file:
        return yaml.safe_load(file)

if __name__ == '__main__':
    import sys
    spec_file = sys.argv[1] if len(sys.argv) > 1 else 'openapi.yaml'
    spec = load_spec(spec_file)
    register_endpoints()
    app.run(debug=True, port=5000)
