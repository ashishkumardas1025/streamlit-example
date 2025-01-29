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
        # Remove path parameters and clean the path
        clean_path = re.sub(r'{[^}]+}', '', path).strip('/')
        return clean_path or 'root'

    def get_path_param_name(self, path: str) -> Optional[str]:
        """Extract the path parameter name if it exists."""
        match = re.search(r'{([^}]+)}', path)
        return match.group(1) if match else None

    def validate_request_data(self, data: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not schema:
            return True, None
            
        required = schema.get('required', [])
        properties = schema.get('properties', {})
        
        if not isinstance(data, dict):
            return False, "Request data must be a JSON object"
            
        for field in required:
            if field not in data:
                return False, f"Missing required field: {field}"
                
        return True, None

    async def handle_request(self, path: str, method: str, request_data: Optional[Dict[str, Any]] = None, 
                           path_params: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], int]:
        try:
            store_key = self.get_store_key(path)
            if store_key not in self.data_stores:
                self.data_stores[store_key] = {}

            store = self.data_stores[store_key]
            request_schema = self.get_request_schema(path, method)
            param_name = self.get_path_param_name(path)
            
            if request_data and request_schema:
                is_valid, error = self.validate_request_data(request_data, request_schema)
                if not is_valid:
                    return {"error": error}, 400

            if method.lower() == 'get':
                # Handle GET request with or without ID
                if path_params and param_name and path_params.get(param_name):
                    record_id = path_params[param_name]
                    if record_id not in store:
                        return {"error": "Record not found"}, 404
                    return store[record_id], 200
                return {"items": list(store.values())}, 200

            elif method.lower() == 'post':
                # Handle POST request
                new_id = str(uuid.uuid4())
                new_record = request_data if request_data else {}
                new_record['id'] = new_id
                store[new_id] = new_record
                return new_record, 201

            elif method.lower() == 'put':
                # Handle PUT request
                if not path_params or not param_name or path_params.get(param_name) is None:
                    return {"error": "ID is required for update"}, 400
                record_id = path_params[param_name]
                if record_id not in store:
                    return {"error": "Record not found"}, 404
                updated_record = request_data if request_data else {}
                updated_record['id'] = record_id
                store[record_id] = updated_record
                return store[record_id], 200

            elif method.lower() == 'delete':
                # Handle DELETE request
                if not path_params or not param_name or path_params.get(param_name) is None:
                    return {"error": "ID is required for delete"}, 400
                record_id = path_params[param_name]
                if record_id not in store:
                    return {"error": "Record not found"}, 404
                del store[record_id]
                return {}, 204

            return {"error": "Method not supported"}, 405

        except Exception as e:
            return {"error": f"Internal server error: {str(e)}"}, 500

    def get_response_schema(self, path: str, method: str) -> Optional[Dict[str, Any]]:
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
        paths = self.spec.get('paths', {})

        async def handle_request_wrapper(path: str, method: str, **path_params):
            try:
                request_data = request.get_json() if request.is_json else None
                response, status_code = await self.handler.handle_request(path, method, request_data, path_params)
                return jsonify(response), status_code
            except Exception as e:
                return jsonify({"error": f"Request handling error: {str(e)}"}), 500

        for path, methods in paths.items():
            param_name = self.handler.get_path_param_name(path)
            if param_name:
                # Convert OpenAPI path params to Flask format using the actual parameter name
                flask_path = path.replace(f'{{{param_name}}}', f'<regex("[^/]+"):{param_name}>')
            else:
                flask_path = path

            for method in methods.keys():
                endpoint = f"{method}_{path}"
                self.app.add_url_rule(
                    flask_path,
                    endpoint,
                    lambda **params, p=path, m=method: asyncio.run(handle_request_wrapper(p, m, **params)),
                    methods=[method.upper()]
                )

def run_app(spec_file: str, host: str = '0.0.0.0', port: int = 5000, debug: bool = True):
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
