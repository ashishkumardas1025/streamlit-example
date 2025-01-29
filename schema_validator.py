from flask import Flask, request, jsonify
import yaml
import os
import json
import asyncio
from faker import Faker
import uuid
from datetime import datetime
import re
from typing import Dict, Any, Tuple, Optional
from werkzeug.routing import BaseConverter

class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]

class DynamicResponseGenerator:
    def __init__(self):
        self.faker = Faker()
        self.cache: Dict[str, Any] = {}

    def generate_example_value(self, schema: Dict[str, Any]) -> Any:
        """Generate example value based on schema type with improved type handling."""
        if not isinstance(schema, dict):
            return None

        schema_type = schema.get('type', 'string')
        schema_format = schema.get('format', '')
        example = schema.get('example')
        enum_values = schema.get('enum')
        
        if example is not None:
            return example
        
        if enum_values:
            return self.faker.random_element(elements=enum_values)
            
        if schema_type == 'string':
            if schema_format == 'date-time':
                return datetime.now().isoformat()
            elif schema_format == 'date':
                return datetime.now().date().isoformat()
            elif schema_format == 'uuid':
                return str(uuid.uuid4())
            elif schema_format == 'email':
                return self.faker.email()
            elif schema_format == 'uri':
                return self.faker.url()
            else:
                return self.faker.word()
        elif schema_type == 'integer':
            return self.faker.random_int(
                min=schema.get('minimum', -1000),
                max=schema.get('maximum', 1000)
            )
        elif schema_type == 'number':
            return round(self.faker.random_float(
                min=float(schema.get('minimum', -1000)),
                max=float(schema.get('maximum', 1000))
            ), 2)
        elif schema_type == 'boolean':
            return self.faker.boolean()
        elif schema_type == 'array':
            items = schema.get('items', {})
            min_items = schema.get('minItems', 1)
            max_items = schema.get('maxItems', 3)
            num_items = self.faker.random_int(min=min_items, max=max_items)
            return [self.generate_example_value(items) for _ in range(num_items)]
        elif schema_type == 'object':
            return self.generate_object_example(schema)
        return None

    def generate_object_example(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Generate example object based on schema with required fields handling."""
        result = {}
        properties = schema.get('properties', {})
        required_fields = schema.get('required', [])
        
        for prop_name, prop_schema in properties.items():
            if prop_name in required_fields or self.faker.boolean(chance_of_getting_true=75):
                result[prop_name] = self.generate_example_value(prop_schema)
        return result

class DynamicAPIHandler:
    def __init__(self, spec: Dict[str, Any]):
        self.spec = spec
        self.response_generator = DynamicResponseGenerator()
        self.data_stores: Dict[str, Dict[str, Any]] = {}

    def get_store_key(self, path: str) -> str:
        """Generate a unique key for each path's data store."""
        return re.sub(r'{[^}]+}', '', path).strip('/')

    def get_path_params(self, path: str) -> list:
        """Extract all path parameters."""
        return re.findall(r'{([^}]+)}', path)

    def validate_request_data(self, data: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Basic request data validation against schema."""
        if not schema:
            return True, None
            
        required = schema.get('required', [])
        properties = schema.get('properties', {})
        
        if not isinstance(data, dict):
            return False, "Request data must be a JSON object"
            
        for field in required:
            if field not in data:
                return False, f"Missing required field: {field}"
                
        for field, value in data.items():
            if field in properties:
                field_type = properties[field].get('type')
                if field_type == 'string' and not isinstance(value, str):
                    return False, f"Field {field} must be a string"
                elif field_type == 'number' and not isinstance(value, (int, float)):
                    return False, f"Field {field} must be a number"
                elif field_type == 'boolean' and not isinstance(value, bool):
                    return False, f"Field {field} must be a boolean"
                    
        return True, None

    async def handle_request(self, path: str, method: str, request_data: Optional[Dict[str, Any]] = None, 
                           path_params: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], int]:
        """Handle API request with improved error handling and validation."""
        try:
            store_key = self.get_store_key(path)
            if store_key not in self.data_stores:
                self.data_stores[store_key] = {}

            store = self.data_stores[store_key]
            request_schema = self.get_request_schema(path, method)
            
            if request_data and request_schema:
                is_valid, error = self.validate_request_data(request_data, request_schema)
                if not is_valid:
                    return {"error": error}, 400

            if method.lower() == 'get':
                if path_params and path_params.get('id'):
                    record = store.get(path_params['id'])
                    if not record:
                        return {"error": "Record not found"}, 404
                    return record, 200
                return {"items": list(store.values())}, 200

            elif method.lower() == 'post':
                new_id = str(uuid.uuid4())
                if request_data:
                    request_data['id'] = new_id
                else:
                    request_data = {'id': new_id}
                store[new_id] = request_data
                return request_data, 201

            elif method.lower() == 'put':
                if not path_params or 'id' not in path_params:
                    return {"error": "ID is required for update"}, 400
                record_id = path_params['id']
                if record_id not in store:
                    return {"error": "Record not found"}, 404
                if request_data:
                    request_data['id'] = record_id
                    store[record_id] = request_data
                return store[record_id], 200

            elif method.lower() == 'delete':
                if not path_params or 'id' not in path_params:
                    return {"error": "ID is required for delete"}, 400
                record_id = path_params['id']
                if record_id not in store:
                    return {"error": "Record not found"}, 404
                del store[record_id]
                return {}, 204

            return {"error": "Method not supported"}, 405

        except Exception as e:
            return {"error": f"Internal server error: {str(e)}"}, 500

    def get_response_schema(self, path: str, method: str) -> Optional[Dict[str, Any]]:
        """Get response schema with better error handling."""
        try:
            path_obj = self.spec.get('paths', {}).get(path, {})
            operation = path_obj.get(method.lower(), {})
            responses = operation.get('responses', {})
            
            for status_code in ['200', '201', '202']:
                if status_code in responses:
                    return responses[status_code].get('content', {}).get('application/json', {}).get('schema', {})
            return None
        except Exception:
            return None

    def get_request_schema(self, path: str, method: str) -> Optional[Dict[str, Any]]:
        """Get request schema with better error handling."""
        try:
            path_obj = self.spec.get('paths', {}).get(path, {})
            operation = path_obj.get(method.lower(), {})
            return operation.get('requestBody', {}).get('content', {}).get('application/json', {}).get('schema', {})
        except Exception:
            return None

class OpenAPIFlask:
    def __init__(self, spec_file: str):
        self.app = Flask(__name__)
        self.app.url_map.converters['regex'] = RegexConverter
        self.spec = self.load_spec(spec_file)
        self.handler = DynamicAPIHandler(self.spec)
        self.register_routes()

    def load_spec(self, spec_file: str) -> Dict[str, Any]:
        """Load and validate OpenAPI specification."""
        if not os.path.exists(spec_file):
            raise FileNotFoundError(f"Specification file {spec_file} not found")
        
        try:
            with open(spec_file, 'r') as file:
                spec = yaml.safe_load(file)
                
            if not isinstance(spec, dict):
                raise ValueError("Invalid OpenAPI specification format")
                
            if 'paths' not in spec:
                raise ValueError("No paths defined in OpenAPI specification")
                
            return spec
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file: {str(e)}")

    def register_routes(self):
        """Register routes with improved error handling."""
        paths = self.spec.get('paths', {})

        async def handle_request_wrapper(path: str, method: str, **path_params):
            try:
                request_data = request.get_json() if request.is_json else None
                response, status_code = await self.handler.handle_request(path, method, request_data, path_params)
                return jsonify(response), status_code
            except Exception as e:
                return jsonify({"error": f"Request handling error: {str(e)}"}), 500

        for path, methods in paths.items():
            # Convert OpenAPI path params to Flask format
            flask_path = re.sub(r'{([^}]+)}', lambda m: f'<regex("[^/]+"):id>', path)

            for method in methods.keys():
                endpoint = f"{method}_{path}"
                self.app.add_url_rule(
                    flask_path,
                    endpoint,
                    lambda **params, p=path, m=method: asyncio.run(handle_request_wrapper(p, m, **params)),
                    methods=[method.upper()]
                )

def run_app(spec_file: str, host: str = '0.0.0.0', port: int = 5000, debug: bool = True):
    """Run the application with configurable parameters."""
    try:
        app = OpenAPIFlask(spec_file)
        app.app.run(host=host, port=port, debug=debug)
    except Exception as e:
        print(f"Error starting application: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    import sys
    spec_file = sys.argv[1] if len(sys.argv) > 1 else 'openapi.yaml'
    run_app(spec_file)
