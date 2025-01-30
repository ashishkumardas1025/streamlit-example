from flask import Flask, request, jsonify
import yaml
import os
from typing import Dict, Any
import jsonschema
from jsonschema import validate, ValidationError
from datetime import datetime

app = Flask(__name__)

# Global storage for different entity types
storage = {}
id_counters = {}
# Store OpenAPI spec globally
spec = {}

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
    current_id = str(id_counters[entity_type])  # Convert to string as per schema
    id_counters[entity_type] += 1
    return current_id

def initialize_storage(entity_type: str):
    """Initialize storage for an entity type if it doesn't exist"""
    if entity_type not in storage:
        storage[entity_type] = {}

def get_request_schema(path: str, method: str) -> Dict:
    """Get request schema from OpenAPI spec"""
    path_spec = spec.get('paths', {}).get(f'/{path}', {})
    if '{paymentId}' in path:
        path_spec = spec.get('paths', {}).get(f'/{path.split("/")[0]}/{{paymentId}}', {})
    
    method_spec = path_spec.get(method.lower(), {})
    request_body = method_spec.get('requestBody', {})
    schema = request_body.get('content', {}).get('application/json', {}).get('schema', {})
    return resolve_schema_reference(schema)

def get_response_schema(path: str, method: str, status_code: str) -> Dict:
    """Get response schema from OpenAPI spec"""
    path_spec = spec.get('paths', {}).get(f'/{path}', {})
    if '{paymentId}' in path:
        path_spec = spec.get('paths', {}).get(f'/{path.split("/")[0]}/{{paymentId}}', {})
    
    method_spec = path_spec.get(method.lower(), {})
    responses = method_spec.get('responses', {})
    response_spec = responses.get(str(status_code), {})
    schema = response_spec.get('content', {}).get('application/json', {}).get('schema', {})
    return resolve_schema_reference(schema)

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
    schema = get_request_schema(entity_type, method)
    if data and schema:
        validate_schema(data, schema, "Request")

def validate_response(entity_type: str, method: str, status_code: int, data: Dict):
    """Validate response data against OpenAPI spec"""
    schema = get_response_schema(entity_type, method, status_code)
    if schema:
        validate_schema(data, schema, "Response")

@app.route('/payments', methods=['POST'])
def create_payment():
    try:
        data = request.get_json()
        validate_request('payments', 'POST', data)
        
        initialize_storage('payments')
        payment_id = get_next_id('payments')
        
        # Add required fields
        data['id'] = payment_id
        data['created_at'] = datetime.utcnow().isoformat()
        if 'status' not in data:
            data['status'] = 'pending'
            
        storage['payments'][payment_id] = data
        validate_response('payments', 'POST', 201, data)
        return jsonify(data), 201
    
    except ValidationException as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/payments', methods=['GET'])
def get_all_payments():
    try:
        initialize_storage('payments')
        payments = list(storage['payments'].values())
        validate_response('payments', 'GET', 200, payments)
        return jsonify(payments), 200
    
    except ValidationException as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/payments/<payment_id>', methods=['GET'])
def get_payment(payment_id):
    try:
        initialize_storage('payments')
        if payment_id not in storage['payments']:
            return jsonify({"error": "Payment not found"}), 404
        
        payment = storage['payments'][payment_id]
        validate_response('payments/{paymentId}', 'GET', 200, payment)
        return jsonify(payment), 200
    
    except ValidationException as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/payments/<payment_id>', methods=['PUT'])
def update_payment(payment_id):
    try:
        data = request.get_json()
        validate_request('payments/{paymentId}', 'PUT', data)
        
        initialize_storage('payments')
        if payment_id not in storage['payments']:
            return jsonify({"error": "Payment not found"}), 404
        
        # Preserve id and created_at
        data['id'] = payment_id
        data['created_at'] = storage['payments'][payment_id]['created_at']
        
        storage['payments'][payment_id] = data
        validate_response('payments/{paymentId}', 'PUT', 200, data)
        return jsonify(data), 200
    
    except ValidationException as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/payments/<payment_id>', methods=['DELETE'])
def delete_payment(payment_id):
    try:
        initialize_storage('payments')
        if payment_id not in storage['payments']:
            return jsonify({"error": "Payment not found"}), 404
        
        storage['payments'].pop(payment_id)
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
    app.run(debug=True, port=5000)
