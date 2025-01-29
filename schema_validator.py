from flask import Flask, request, jsonify
import yaml
import os
import json
import asyncio
from faker import Faker
import uuid
from datetime import datetime
import re

class DynamicResponseGenerator:
    """Handles dynamic response generation based on OpenAPI schema."""
    
    def __init__(self):
        self.faker = Faker()
        self.cache = {}

    def generate_example_value(self, schema):
        """Generate example value based on schema type."""
        schema_type = schema.get('type', 'string')
        schema_format = schema.get('format', '')
        example = schema.get('example')
        
        if example is not None:
            return example
            
        if schema_type == 'string':
            if schema_format == 'date-time':
                return datetime.now().isoformat()
            elif schema_format == 'uuid':
                return str(uuid.uuid4())
            else:
                return self.faker.word()
        elif schema_type == 'integer':
            return self.faker.random_int(min=schema.get('minimum', 0), 
                                      max=schema.get('maximum', 1000))
        elif schema_type == 'number':
            return self.faker.random_float(min=schema.get('minimum', 0), 
                                        max=schema.get('maximum', 1000))
        elif schema_type == 'boolean':
            return self.faker.boolean()
        elif schema_type == 'array':
            items = schema.get('items', {})
            return [self.generate_example_value(items) for _ in range(3)]
        elif schema_type == 'object':
            return self.generate_object_example(schema)
        return None

    def generate_object_example(self, schema):
        """Generate example object based on schema."""
        result = {}
        properties = schema.get('properties', {})
        for prop_name, prop_schema in properties.items():
            result[prop_name] = self.generate_example_value(prop_schema)
        return result

class DynamicAPIHandler:
    """Handles dynamic API operations based on OpenAPI spec."""
    
    def __init__(self, spec):
        self.spec = spec
        self.response_generator = DynamicResponseGenerator()
        self.data_store = {}  # In-memory storage for CRUD operations

    def get_path_id_param(self, path):
        """Extract the ID field from path parameters, if any."""
        match = re.search(r'{([^}]+)}', path)
        return match.group(1) if match else None

    def get_response_schema(self, path, method):
        """Get response schema for path and method."""
        path_obj = self.spec.get('paths', {}).get(path, {})
        operation = path_obj.get(method.lower(), {})
        responses = operation.get('responses', {})
        for status_code in ['200', '201', '202']:
            if status_code in responses:
                return responses[status_code].get('content', {}).get('application/json', {}).get('schema', {})
        return None

    def get_request_schema(self, path, method):
        """Get request body schema for path and method."""
        path_obj = self.spec.get('paths', {}).get(path, {})
        operation = path_obj.get(method.lower(), {})
        return operation.get('requestBody', {}).get('content', {}).get('application/json', {}).get('schema', {})

    async def handle_request(self, path, method, request_data=None, path_params=None):
        """Handle API request dynamically."""
        response_schema = self.get_response_schema(path, method)
        if not response_schema:
            return {"error": "No response schema defined"}, 500

        path_id = self.get_path_id_param(path)

        # Handle CRUD operations dynamically
        if method == 'get':
            if path_id and path_id in path_params:
                record_id = path_params[path_id]
                return self.data_store.get(record_id, {"error": "Not found"}), 200
            return list(self.data_store.values()), 200

        elif method == 'post':
            new_id = str(uuid.uuid4())
            request_data['id'] = new_id  # Assign a unique ID
            self.data_store[new_id] = request_data
            return request_data, 201

        elif method == 'put':
            if not path_id or path_id not in path_params:
                return {"error": "ID is required for update operation"}, 400
            record_id = path_params[path_id]
            if record_id not in self.data_store:
                return {"error": "Record not found"}, 404
            self.data_store[record_id] = request_data
            return request_data, 200

        elif method == 'delete':
            if not path_id or path_id not in path_params:
                return {"error": "ID is required for delete operation"}, 400
            record_id = path_params[path_id]
            if record_id not in self.data_store:
                return {"error": "Record not found"}, 404
            del self.data_store[record_id]
            return {}, 204

        return {"error": "Unsupported method"}, 405

class OpenAPIFlask:
    """Dynamic Flask application that generates responses based on OpenAPI spec."""
    
    def __init__(self, spec_file):
        self.app = Flask(__name__)
        self.spec = self.load_spec(spec_file)
        self.handler = DynamicAPIHandler(self.spec)
        self.register_routes()

    def load_spec(self, spec_file):
        """Load and parse OpenAPI specification."""
        if not os.path.exists(spec_file):
            raise FileNotFoundError(f"Specification file {spec_file} not found.")
        with open(spec_file, 'r') as file:
            return yaml.safe_load(file)

    def register_routes(self):
        """Register routes dynamically based on OpenAPI spec."""
        paths = self.spec.get('paths', {})

        async def handle_request_wrapper(path, method, **path_params):
            request_data = request.get_json() if request.is_json else None
            response, status_code = await self.handler.handle_request(path, method, request_data, path_params)
            return jsonify(response), status_code

        for path, methods in paths.items():
            flask_path = path.replace('{', '<').replace('}', '>')

            for method in methods.keys():
                endpoint = f"{method}_{path}"
                self.app.add_url_rule(
                    flask_path,
                    endpoint,
                    lambda **params, p=path, m=method: asyncio.run(handle_request_wrapper(p, m, **params)),
                    methods=[method.upper()]
                )

def run_app(spec_file):
    """Run the application."""
    app = OpenAPIFlask(spec_file)
    app.app.run(host='0.0.0.0', port=5000, debug=True)

if __name__ == '__main__':
    import sys
    spec_file = sys.argv[1] if len(sys.argv) > 1 else 'openapi.yaml'
    run_app(spec_file)
