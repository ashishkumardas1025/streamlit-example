from flask import Flask, request, jsonify, make_response, send_file
import yaml
import json
from werkzeug.utils import secure_filename
import os
import datetime
from schema_validator import validate_request, generate_response
from utils import parse_parameters, get_operation_id

class OpenAPIFlask:
    def __init__(self, spec_file):
        self.app = Flask(__name__)
        self.load_spec(spec_file)
        self.register_routes()
        
        # Storage for in-memory data
        self.data_store = {
            'pets': {},
            'users': {},
            'stores': {},
            'orders': {}
        }
        
    def load_spec(self, spec_file):
        """Load and parse OpenAPI specification"""
        with open(spec_file, 'r') as file:
            self.spec = yaml.safe_load(file)
            
    def register_routes(self):
        """Register all routes from OpenAPI spec"""
        paths = self.spec.get('paths', {})
        
        for path, methods in paths.items():
            # Convert path parameters from OpenAPI format to Flask format
            flask_path = path.replace('{', '<').replace('}', '>')
            
            for method, operation in methods.items():
                self.register_route(flask_path, method, operation)
                
    def register_route(self, path, method, operation):
        """Register a single route"""
        def handler(**kwargs):
            operation_id = operation.get('operationId')
            
            try:
                # Parse parameters
                params = parse_parameters(operation, request, kwargs)
                
                # Validate request body if present
                request_body = None
                if request.is_json and request.get_json():
                    request_body = request.get_json()
                    if 'requestBody' in operation:
                        schema = operation['requestBody']['content']['application/json']['schema']
                        validate_request(request_body, schema, self.spec)
                
                # Handle operation
                response_data = self.handle_operation(operation_id, params, request_body)
                
                # Generate response based on schema
                status_code = '200'
                if status_code in operation.get('responses', {}):
                    response_schema = operation['responses'][status_code].get('content', {}).get('application/json', {}).get('schema', {})
                    response_data = generate_response(response_data, response_schema, self.spec)
                
                # Handle custom headers
                headers = {}
                if 'headers' in operation['responses'].get(status_code, {}):
                    for header_name, header_spec in operation['responses'][status_code]['headers'].items():
                        headers[header_name] = str(datetime.datetime.now())  # Example header value
                
                return make_response(jsonify(response_data), 200, headers)
            
            except Exception as e:
                return jsonify({'error': str(e)}), 400
        
        # Register the route with Flask
        endpoint = f"{method}_{path}"
        self.app.add_url_rule(
            path,
            endpoint,
            handler,
            methods=[method.upper()]
        )
    
    def handle_operation(self, operation_id, params, body):
        """Handle different operations based on operationId"""
        # This is where you would implement the actual business logic
        # Here's a simple example implementation
        
        entity_type = operation_id.split('_')[0] if '_' in operation_id else operation_id
        action = operation_id.split('_')[1] if '_' in operation_id else 'get'
        
        if 'create' in operation_id or 'add' in operation_id:
            return self.create_entity(entity_type, body)
        elif 'update' in operation_id:
            return self.update_entity(entity_type, params.get('id'), body)
        elif 'delete' in operation_id:
            return self.delete_entity(entity_type, params.get('id'))
        elif 'get' in operation_id and 'id' in params:
            return self.get_entity(entity_type, params.get('id'))
        elif 'find' in operation_id:
            return self.find_entities(entity_type, params)
        else:
            return self.get_all_entities(entity_type)
    
    def create_entity(self, entity_type, data):
        """Create a new entity"""
        entity_id = len(self.data_store[entity_type]) + 1
        data['id'] = entity_id
        self.data_store[entity_type][entity_id] = data
        return data
    
    def update_entity(self, entity_type, entity_id, data):
        """Update an existing entity"""
        if entity_id in self.data_store[entity_type]:
            data['id'] = entity_id
            self.data_store[entity_type][entity_id] = data
            return data
        return None
    
    def delete_entity(self, entity_type, entity_id):
        """Delete an entity"""
        if entity_id in self.data_store[entity_type]:
            return self.data_store[entity_type].pop(entity_id)
        return None
    
    def get_entity(self, entity_type, entity_id):
        """Get a single entity"""
        return self.data_store[entity_type].get(entity_id)
    
    def get_all_entities(self, entity_type):
        """Get all entities of a type"""
        return list(self.data_store[entity_type].values())
    
    def find_entities(self, entity_type, params):
        """Find entities based on parameters"""
        results = []
        for entity in self.data_store[entity_type].values():
            matches = True
            for key, value in params.items():
                if key in entity and entity[key] != value:
                    matches = False
                    break
            if matches:
                results.append(entity)
        return results
    
    def run(self, *args, **kwargs):
        """Run the Flask application"""
        self.app.run(*args, **kwargs)

if __name__ == '__main__':
    app = OpenAPIFlask('openapi.yaml')
    app.run(debug=True, port=5000)
