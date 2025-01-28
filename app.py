from flask import Flask, request, jsonify
import yaml
import os
from typing import Dict, Any


class GenericAPIHandler:
    """Handles CRUD operations for any entity dynamically."""
    def __init__(self):
        self.store: Dict[str, Dict[int, Any]] = {}
        self.id_counters: Dict[str, int] = {}

    def get_entity_type(self, path: str) -> str:
        """Extract entity type from the path."""
        return path.split('/')[1] if len(path.split('/')) > 1 else 'default'

    def get_or_create_store(self, entity_type: str) -> Dict[int, Any]:
        """Get or create a store for the entity type."""
        if entity_type not in self.store:
            self.store[entity_type] = {}
            self.id_counters[entity_type] = 1
        return self.store[entity_type]

    def create(self, entity_type: str, data: Dict) -> tuple:
        """Create a new entity."""
        store = self.get_or_create_store(entity_type)
        entity_id = self.id_counters[entity_type]
        data['id'] = entity_id
        store[entity_id] = data
        self.id_counters[entity_type] += 1
        return data, 201

    def get_all(self, entity_type: str) -> tuple:
        """Get all entities."""
        store = self.get_or_create_store(entity_type)
        return list(store.values()), 200

    def get_one(self, entity_type: str, entity_id: int) -> tuple:
        """Get a single entity."""
        store = self.get_or_create_store(entity_type)
        if entity_id not in store:
            return {"error": f"{entity_type} not found"}, 404
        return store[entity_id], 200

    def update(self, entity_type: str, entity_id: int, data: Dict) -> tuple:
        """Update an existing entity."""
        store = self.get_or_create_store(entity_type)
        if entity_id not in store:
            return {"error": f"{entity_type} not found"}, 404
        data['id'] = entity_id
        store[entity_id] = data
        return data, 200

    def delete(self, entity_type: str, entity_id: int) -> tuple:
        """Delete an entity."""
        store = self.get_or_create_store(entity_type)
        if entity_id not in store:
            return {"error": f"{entity_type} not found"}, 404
        return store.pop(entity_id), 200


class OpenAPIFlask:
    """Dynamic Flask application based on OpenAPI specifications."""
    def __init__(self, spec_file: str):
        self.app = Flask(__name__)
        self.handler = GenericAPIHandler()
        self.spec = self.load_spec(spec_file)
        self.register_routes()

    def load_spec(self, spec_file: str) -> Dict:
        """Load and parse the OpenAPI specification."""
        if not os.path.exists(spec_file):
            raise FileNotFoundError(f"Specification file {spec_file} not found.")
        with open(spec_file, 'r') as file:
            return yaml.safe_load(file)

    def validate_request_body(self, data: Dict, schema: Dict) -> None:
        """Validate request body against OpenAPI schema."""
        required_fields = schema.get('required', [])
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

    def register_routes(self) -> None:
        """Register routes dynamically based on OpenAPI spec."""
        paths = self.spec.get('paths', {})
        for path, methods in paths.items():
            flask_path = path.replace('{', '<').replace('}', '>')  # Convert OpenAPI path to Flask format
            for method, operation in methods.items():
                self.register_route(flask_path, method, operation)

    def register_route(self, path: str, method: str, operation: Dict) -> None:
        """Register a single route."""
        def route_handler(**kwargs):
            entity_type = path.split('/')[1]
            try:
                if method == 'get' and 'id' in kwargs:  # Get a single entity
                    return jsonify(self.handler.get_one(entity_type, int(kwargs['id']))[0]), 200
                elif method == 'get':  # Get all entities
                    return jsonify(self.handler.get_all(entity_type)[0]), 200
                elif method == 'post':  # Create an entity
                    data = request.get_json()
                    schema = operation.get('requestBody', {}).get('content', {}).get('application/json', {}).get('schema', {})
                    self.validate_request_body(data, schema)
                    return jsonify(self.handler.create(entity_type, data)[0]), 201
                elif method == 'put':  # Update an entity
                    data = request.get_json()
                    entity_id = int(kwargs['id'])
                    schema = operation.get('requestBody', {}).get('content', {}).get('application/json', {}).get('schema', {})
                    self.validate_request_body(data, schema)
                    return jsonify(self.handler.update(entity_type, entity_id, data)[0]), 200
                elif method == 'delete':  # Delete an entity
                    entity_id = int(kwargs['id'])
                    return jsonify(self.handler.delete(entity_type, entity_id)[0]), 200
                else:
                    return jsonify({"error": "Method not supported"}), 405
            except Exception as e:
                return jsonify({"error": str(e)}), 400

        endpoint = f"{method}_{path}"
        self.app.add_url_rule(path, endpoint, route_handler, methods=[method.upper()])

    def run(self, *args, **kwargs):
        """Run the Flask application."""
        self.app.run(*args, **kwargs)


if __name__ == '__main__':
    import sys
    spec_file = sys.argv[1] if len(sys.argv) > 1 else 'openapi.yaml'
    app = OpenAPIFlask(spec_file)
    app.run(debug=True, port=5000)
