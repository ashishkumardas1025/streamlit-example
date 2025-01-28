from flask import Flask, request, jsonify
import yaml
import os
from typing import Dict, Any


class GenericAPIHandler:
    """Handles CRUD operations for any entity dynamically."""
    def __init__(self):
        self.store: Dict[str, Dict[str, Any]] = {}
        self.id_fields: Dict[str, str] = {}  # Stores the ID field for each entity type

    def get_or_create_store(self, entity_type: str) -> Dict[str, Any]:
        """Get or create a store for the entity type."""
        if entity_type not in self.store:
            self.store[entity_type] = {}
        return self.store[entity_type]

    def get_id_field(self, entity_type: str, schema: Dict) -> str:
        """Determine the ID field for the entity based on the OpenAPI schema."""
        if entity_type not in self.id_fields:
            properties = schema.get('properties', {})
            # Default to 'id' if available, otherwise pick the first property
            self.id_fields[entity_type] = next((k for k in properties if k.lower() == 'id'), list(properties.keys())[0])
        return self.id_fields[entity_type]

    def create(self, entity_type: str, data: Dict, schema: Dict) -> tuple:
        """Create a new entity."""
        store = self.get_or_create_store(entity_type)
        id_field = self.get_id_field(entity_type, schema)

        # Check for duplicate ID
        if id_field in data and str(data[id_field]) in store:
            return {"error": f"{entity_type} with {id_field}={data[id_field]} already exists"}, 400

        if id_field not in data:
            return {"error": f"Missing required field: {id_field}"}, 400

        entity_id = str(data[id_field])
        store[entity_id] = data
        return data, 201

    def get_all(self, entity_type: str) -> tuple:
        """Get all entities."""
        store = self.get_or_create_store(entity_type)
        return list(store.values()), 200

    def get_one(self, entity_type: str, entity_id: str) -> tuple:
        """Get a single entity."""
        store = self.get_or_create_store(entity_type)
        if entity_id not in store:
            return {"error": f"{entity_type} with ID {entity_id} not found"}, 404
        return store[entity_id], 200

    def update(self, entity_type: str, entity_id: str, data: Dict, schema: Dict) -> tuple:
        """Update an existing entity."""
        store = self.get_or_create_store(entity_type)
        id_field = self.get_id_field(entity_type, schema)

        if entity_id not in store:
            return {"error": f"{entity_type} with ID {entity_id} not found"}, 404

        # Ensure ID consistency in the update
        data[id_field] = entity_id
        store[entity_id] = data
        return data, 200

    def delete(self, entity_type: str, entity_id: str) -> tuple:
        """Delete an entity."""
        store = self.get_or_create_store(entity_type)
        if entity_id not in store:
            return {"error": f"{entity_type} with ID {entity_id} not found"}, 404
        del store[entity_id]
        return {}, 204


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
                # Extract the schema for requestBody
                schema = operation.get('requestBody', {}).get('content', {}).get('application/json', {}).get('schema', {})

                # Handle GET for a single entity (with ID)
                if method == 'get' and 'id' in kwargs:
                    return jsonify(self.handler.get_one(entity_type, kwargs['id'])[0]), 200

                # Handle GET for all entities
                elif method == 'get':
                    return jsonify(self.handler.get_all(entity_type)[0]), 200

                # Handle POST (create)
                elif method == 'post':
                    data = request.get_json()
                    self.validate_request_body(data, schema)
                    return jsonify(self.handler.create(entity_type, data, schema)[0]), 201

                # Handle PUT (update)
                elif method == 'put':
                    if 'id' not in kwargs:
                        return jsonify({"error": "ID is required for update operation"}), 400
                    data = request.get_json()
                    self.validate_request_body(data, schema)
                    return jsonify(self.handler.update(entity_type, kwargs['id'], data, schema)[0]), 200

                # Handle DELETE
                elif method == 'delete':
                    if 'id' not in kwargs:
                        return jsonify({"error": "ID is required for delete operation"}), 400
                    return jsonify(self.handler.delete(entity_type, kwargs['id'])[0]), 204

                # Method not supported
                else:
                    return jsonify({"error": "Method not supported"}), 405

            except Exception as e:
                return jsonify({"error": str(e)}), 400

        # Define endpoint and register the route
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
