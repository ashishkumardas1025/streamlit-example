from flask import Flask, request, jsonify
import yaml
import os
from typing import Dict, Any, Tuple, List
import jsonschema
from jsonschema import validate, ValidationError

app = Flask(__name__)

# Global storage for different entity types
storage = {}
id_counters = {}
# Store OpenAPI spec globally
spec = {}

class ValidationException(Exception):
    """Custom exception for schema validation errors"""
    pass

def get_next_id(entity_type: str) -> int:
    """Get next ID for an entity type"""
    if entity_type not in id_counters:
        id_counters[entity_type] = 1
    current_id = id_counters[entity_type]
    id_counters[entity_type] += 1
    return current_id

def initialize_storage(entity_type: str):
    """Initialize storage for an entity type if it doesn't exist"""
    if entity_type not in storage:
        storage[entity_type] = {}

def get_schema_for_request(path: str, method: str) -> Dict:
    """Get request schema from OpenAPI spec"""
    path_spec = spec.get('paths', {}).get(f'/{path}', {})
    if '{id}' in path:
        # Handle paths with ID parameter
        path_spec = spec.get('paths', {}).get(f'/{path.split("/")[0]}/{{id}}', {})
    
    method_spec = path_spec.get(method.lower(), {})
    request_body = method_spec.get('requestBody', {})
    content = request_body.get('content', {}).get('application/json', {})
    return content.get('schema', {})

def get_schema_for_response(path: str, method: str, status_code: str) -> Dict:
    """Get response schema from OpenAPI spec"""
    path_spec = spec.get('paths', {}).get(f'/{path}', {})
    if '{id}' in path:
        # Handle paths with ID parameter
        path_spec = spec.get('paths', {}).get(f'/{path.split("/")[0]}/{{id}}', {})
    
    method_spec = path_spec.get(method.lower(), {})
    responses = method_spec.get('responses', {})
    response_spec = responses.get(str(status_code), {})
    content = response_spec.get('content', {}).get('application/json', {})
    return content.get('schema', {})

def validate_schema(data: Dict, schema: Dict, context: str):
    """Validate data against schema"""
    if not schema:
        return  # Skip validation if no schema defined
    
    try:
        validate(instance=data, schema=schema)
    except ValidationError as e:
        raise ValidationException(f"{context} validation failed: {str(e)}")

def validate_request(entity_type: str, method: str, data: Dict = None):
    """Validate request data against OpenAPI spec"""
    schema = get_schema_for_request(entity_type, method)
    if data and schema:
        validate_schema(data, schema, "Request")

def validate_response(entity_type: str, method: str, status_code: int, data: Dict):
    """Validate response data against OpenAPI spec"""
    schema = get_schema_for_response(entity_type, method, status_code)
    if schema:
        validate_schema(data, schema, "Response")

@app.route('/<entity_type>', methods=['POST'])
def create_entity(entity_type):
    try:
        data = request.get_json()
        # Validate request data
        validate_request(entity_type, 'POST', data)
        
        initialize_storage(entity_type)
        entity_id = get_next_id(entity_type)
        data['id'] = entity_id
        storage[entity_type][entity_id] = data
        
        response_data = {"data": data}
        # Validate response data
        validate_response(entity_type, 'POST', 201, response_data)
        return jsonify(response_data), 201
    
    except ValidationException as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/<entity_type>', methods=['GET'])
def get_all_entities(entity_type):
    try:
        initialize_storage(entity_type)
        entities = list(storage[entity_type].values())
        response_data = {"data": entities}
        
        # Validate response data
        validate_response(entity_type, 'GET', 200, response_data)
        return jsonify(response_data), 200
    
    except ValidationException as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/<entity_type>/<int:id>', methods=['GET'])
def get_entity(entity_type, id):
    try:
        initialize_storage(entity_type)
        if id not in storage[entity_type]:
            error_response = {"error": f"{entity_type} not found"}
            validate_response(f"{entity_type}/{{id}}", 'GET', 404, error_response)
            return jsonify(error_response), 404
        
        entity = storage[entity_type][id]
        response_data = {"data": entity}
        
        # Validate response data
        validate_response(f"{entity_type}/{{id}}", 'GET', 200, response_data)
        return jsonify(response_data), 200
    
    except ValidationException as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/<entity_type>/<int:id>', methods=['PUT'])
def update_entity(entity_type, id):
    try:
        data = request.get_json()
        # Validate request data
        validate_request(f"{entity_type}/{{id}}", 'PUT', data)
        
        initialize_storage(entity_type)
        if id not in storage[entity_type]:
            error_response = {"error": f"{entity_type} not found"}
            validate_response(f"{entity_type}/{{id}}", 'PUT', 404, error_response)
            return jsonify(error_response), 404
        
        data['id'] = id
        storage[entity_type][id] = data
        response_data = {"data": data}
        
        # Validate response data
        validate_response(f"{entity_type}/{{id}}", 'PUT', 200, response_data)
        return jsonify(response_data), 200
    
    except ValidationException as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/<entity_type>/<int:id>', methods=['DELETE'])
def delete_entity(entity_type, id):
    try:
        initialize_storage(entity_type)
        if id not in storage[entity_type]:
            error_response = {"error": f"{entity_type} not found"}
            validate_response(f"{entity_type}/{{id}}", 'DELETE', 404, error_response)
            return jsonify(error_response), 404
        
        deleted_entity = storage[entity_type].pop(id)
        response_data = {"data": deleted_entity}
        
        # Validate response data
        validate_response(f"{entity_type}/{{id}}", 'DELETE', 200, response_data)
        return jsonify(response_data), 200
    
    except ValidationException as e:
        return jsonify({"error": str(e)}), 400
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
    # Load spec file globally
    spec = load_spec(spec_file)
    app.run(debug=True, port=5000)
