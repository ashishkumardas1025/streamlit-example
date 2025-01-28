from flask import Flask, request, jsonify, Response
import yaml
import json
from werkzeug.utils import secure_filename
import os
import datetime
from typing import Dict, Any

class GenericAPIHandler:
    def __init__(self):
        # In-memory storage for different entities
        self.store: Dict[str, Dict[int, Any]] = {}
        self.id_counters: Dict[str, int] = {}

    def get_entity_type(self, path: str) -> str:
        """Extract entity type from path"""
        parts = path.split('/')
        return parts[1] if len(parts) > 1 else 'default'

    def get_or_create_store(self, entity_type: str) -> Dict[int, Any]:
        """Get or create store for entity type"""
        if entity_type not in self.store:
            self.store[entity_type] = {}
            self.id_counters[entity_type] = 1
        return self.store[entity_type]

    def create(self, path: str, data: Dict) -> tuple:
        """Create new entity"""
        entity_type = self.get_entity_type(path)
        store = self.get_or_create_store(entity_type)
        
        entity_id = self.id_counters[entity_type]
        data['id'] = entity_id
        store[entity_id] = data
        self.id_counters[entity_type] += 1
        
        return data, 201

    def get_all(self, path: str) -> tuple:
        """Get all entities"""
        entity_type = self.get_entity_type(path)
        store = self.get_or_create_store(entity_type)
        return list(store.values()), 200

    def get_one(self, path: str, entity_id: int) -> tuple:
        """Get single entity"""
        entity_type = self.get_entity_type(path)
        store = self.get_or_create_store(entity_type)
        
        if entity_id not in store:
            return {"error": f"{entity_type} not found"}, 404
            
        return store[entity_id], 200

    def update(self, path: str, entity_id: int, data: Dict) -> tuple:
        """Update entity"""
        entity_type = self.get_entity_type(path)
        store = self.get_or_create_store(entity_type)
        
        if entity_id not in store:
            return {"error": f"{entity_type} not found"}, 404
            
        data['id'] = entity_id
        store[entity_id] = data
        return store[entity_id], 200

    def delete(self, path: str, entity_id: int) -> tuple:
        """Delete entity"""
        entity_type = self.get_entity_type(path)
        store = self.get_or_create_store(entity_type)
        
        if entity_id not in store:
            return {"error": f"{entity_type} not found"}, 404
            
        deleted = store.pop(entity_id)
        return deleted, 200

    def query(self, path: str, params: Dict) -> tuple:
        """Query entities based on parameters"""
        entity_type = self.get_entity_type(path)
        store = self.get_or_create_store(entity_type)
        
        results = []
        for entity in store.values():
            if all(entity.get(k) == v for k, v in params.items()):
                results.append(entity)
                
        return results, 200

class OpenAPIFlask:
    def __init__(self, spec_file: str):
        self.app = Flask(__name__)
        self.handler = GenericAPIHandler()
        self.load_spec(spec_file)
        self.register_routes()

    def load_spec(self, spec_file: str) -> None:
        """Load OpenAPI specification"""
        with open(spec_file, 'r') as file:
            self.spec = yaml.safe_load(file)

    def get_request_body_schema(self, operation: Dict) -> Dict:
        """Extract request body schema from operation"""
        if 'requestBody' in operation:
            content = operation['requestBody'].get('content', {})
            for content_type in ['application/json', 'application/x-www-form-urlencoded']:
                if content_type in content:
                    return content[content_type].get('schema', {})
        return {}

    def validate_request_body(self, data: Dict, schema: Dict) -> None:
        """Validate request body against schema"""
        required = schema.get('required', [])
        for field in required:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

    def register_routes(self) -> None:
        """Register routes from OpenAPI spec"""
        paths = self.spec.get('paths', {})
        
        for path, methods in paths.items():
            # Convert path parameters from OpenAPI to Flask format
            flask_path = path.replace('{', '<').replace('}', '>')
            
            for method, operation in methods.items():
                self.register_route(flask_path, method, operation)

    def register_route(self, path: str, method: str, operation: Dict) -> None:
        """Register a single route"""
        def handler(**kwargs):
            try:
                # Handle query parameters for GET requests
                if method.lower() == 'get' and request.args:
                    response, status_code = self.handler.query(path, request.args.to_dict())
                    return jsonify(response), status_code

                # Handle request body for POST/PUT requests
                if method.lower() in ['post', 'put']:
                    if not request.is_json:
                        return jsonify({"error": "Content-Type must be application/json"}), 400
                    
                    data = request.get_json()
                    schema = self.get_request_body_schema(operation)
                    
                    try:
                        self.validate_request_body(data, schema)
                    except ValueError as e:
                        return jsonify({"error": str(e)}), 400

                    if method.lower() == 'post':
                        response, status_code = self.handler.create(path, data)
                    else:  # PUT
                        entity_id = kwargs.get('id') or kwargs.get('petId') or kwargs.get('orderId')
                        response, status_code = self.handler.update(path, int(entity_id), data)
                    
                    return jsonify(response), status_code

                # Handle GET requests for single entities
                if method.lower() == 'get' and ('id' in kwargs or 'petId' in kwargs or 'orderId' in kwargs):
                    entity_id = kwargs.get('id') or kwargs.get('petId') or kwargs.get('orderId')
                    response, status_code = self.handler.get_one(path, int(entity_id))
                    return jsonify(response), status_code

                # Handle GET requests for collections
                if method.lower() == 'get':
                    response, status_code = self.handler.get_all(path)
                    return jsonify(response), status_code

                # Handle DELETE requests
                if method.lower() == 'delete':
                    entity_id = kwargs.get('id') or kwargs.get('petId') or kwargs.get('orderId')
                    response, status_code = self.handler.delete(path, int(entity_id))
                    return jsonify(response), status_code

                return jsonify({"error": "Method not implemented"}), 501

            except Exception as e:
                return jsonify({"error": str(e)}), 400

        # Register the route with Flask
        endpoint = f"{method}_{path}"
        self.app.add_url_rule(
            flask_path,
            endpoint,
            handler,
            methods=[method.upper()]
        )

    def run(self, *args, **kwargs):
        """Run the Flask application"""
        self.app.run(*args, **kwargs)

if __name__ == '__main__':
    # Get spec file from command line argument or use default
    import sys
    spec_file = sys.argv[1] if len(sys.argv) > 1 else 'openapi.yaml'
    
    app = OpenAPIFlask(spec_file)
    app.run(debug=True, port=5000)
