from flask import Flask, request, jsonify
import yaml
import os
from typing import Dict, Any, List, Union
from datetime import datetime
import jsonschema
import logging
from http import HTTPStatus
import re

# [Previous SchemaValidator class remains the same]

class GenericAPIHandler:
    """Handles CRUD operations for any entity dynamically."""
    def __init__(self, logger):
        self.store: Dict[str, Dict[int, Any]] = {}
        self.id_counters: Dict[str, int] = {}
        self.logger = logger

    def get_entity_type(self, path: str) -> str:
        """Extract entity type from the path."""
        parts = [p for p in path.split('/') if p and not p.startswith('<')]
        return parts[0] if parts else 'default'

    # [Previous get_or_create_store and other CRUD methods remain the same]


class OpenAPIFlask:
    """Dynamic Flask application based on OpenAPI specifications."""
    def __init__(self, spec_files: Union[str, List[str]]):
        self.setup_logging()
        self.app = Flask(__name__)
        self.handler = GenericAPIHandler(self.logger)
        self.specs = {}
        self.load_specs(spec_files)
        self.register_routes()

    def setup_logging(self):
        """Configure logging for the application."""
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def load_specs(self, spec_files: Union[str, List[str]]) -> None:
        """Load and parse multiple OpenAPI specifications."""
        if isinstance(spec_files, str):
            spec_files = [spec_files]

        for spec_file in spec_files:
            try:
                if not os.path.exists(spec_file):
                    raise FileNotFoundError(f"Specification file {spec_file} not found.")
                
                with open(spec_file, 'r') as file:
                    spec = yaml.safe_load(file)
                    # Extract base name from filename for entity type
                    base_name = os.path.splitext(os.path.basename(spec_file))[0]
                    base_path = f"/{base_name}"
                    
                    # Add base path if not present
                    if 'basePath' not in spec:
                        spec['basePath'] = base_path
                    
                    self.specs[base_path] = spec
                    self.logger.info(f"Loaded API spec from {spec_file}")
            except Exception as e:
                self.logger.error(f"Error loading spec file {spec_file}: {str(e)}")
                raise

    def extract_path_params(self, path: str) -> List[str]:
        """Extract path parameter names from OpenAPI path."""
        params = re.findall(r'\{([^}]+)\}', path)
        return params

    def register_routes(self) -> None:
        """Register routes dynamically based on all loaded OpenAPI specs."""
        for base_path, spec in self.specs.items():
            paths = spec.get('paths', {})
            for path, methods in paths.items():
                # Convert OpenAPI path parameters to Flask format
                flask_path = path.replace('{', '<').replace('}', '>')
                if not flask_path.startswith('/'):
                    flask_path = '/' + flask_path
                
                # Prepend base path
                full_path = f"{base_path}{flask_path}"
                
                for method, operation in methods.items():
                    self.register_route(full_path, method, operation, spec)
                    self.logger.info(f"Registered route: {method.upper()} {full_path}")

    def register_route(self, path: str, method: str, operation: Dict, spec: Dict) -> None:
        """Register a single route with enhanced error handling and validation."""
        def route_handler(**kwargs):
            try:
                entity_type = path.split('/')[1]  # Get entity type from first part of path
                query_params = request.args.to_dict()

                # Convert path parameters
                path_params = {}
                for key, value in kwargs.items():
                    if key.endswith('_id'):
                        try:
                            path_params[key] = int(value)
                        except ValueError:
                            return jsonify({"error": f"Invalid {key} format"}), HTTPStatus.BAD_REQUEST

                if method == 'get' and path_params:
                    return self.handle_get_one(entity_type, path_params.get('id'))
                elif method == 'get':
                    return self.handle_get_all(entity_type, query_params)
                elif method == 'post':
                    return self.handle_create(entity_type, operation, request.get_json())
                elif method == 'put':
                    return self.handle_update(entity_type, path_params.get('id'), operation, request.get_json())
                elif method == 'delete':
                    return self.handle_delete(entity_type, path_params.get('id'))
                else:
                    return jsonify({"error": "Method not supported"}), HTTPStatus.METHOD_NOT_ALLOWED

            except Exception as e:
                self.logger.error(f"Error handling {method} request to {path}: {str(e)}")
                return jsonify({"error": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR

        endpoint = f"{method}_{path}"
        self.app.add_url_rule(path, endpoint, route_handler, methods=[method.upper()])

    def handle_get_one(self, entity_type: str, entity_id: int) -> tuple:
        """Handle GET request for a single entity."""
        if entity_id is None:
            return jsonify({"error": "ID parameter is required"}), HTTPStatus.BAD_REQUEST
        return self.handler.get_one(entity_type, entity_id)

    def handle_get_all(self, entity_type: str, query_params: Dict) -> tuple:
        """Handle GET request for all entities."""
        return self.handler.get_all(entity_type, query_params)

    def handle_create(self, entity_type: str, operation: Dict, data: Dict) -> tuple:
        """Handle POST request to create an entity."""
        if not data:
            return jsonify({"error": "Request body is required"}), HTTPStatus.BAD_REQUEST
        
        schema = operation.get('requestBody', {}).get('content', {}).get('application/json', {}).get('schema', {})
        validation_errors = SchemaValidator.validate_schema(data, schema)
        
        if validation_errors:
            return jsonify({"errors": validation_errors}), HTTPStatus.BAD_REQUEST
        
        return self.handler.create(entity_type, data)

    def handle_update(self, entity_type: str, entity_id: int, operation: Dict, data: Dict) -> tuple:
        """Handle PUT request to update an entity."""
        if entity_id is None:
            return jsonify({"error": "ID parameter is required"}), HTTPStatus.BAD_REQUEST
        if not data:
            return jsonify({"error": "Request body is required"}), HTTPStatus.BAD_REQUEST
        
        schema = operation.get('requestBody', {}).get('content', {}).get('application/json', {}).get('schema', {})
        validation_errors = SchemaValidator.validate_schema(data, schema)
        
        if validation_errors:
            return jsonify({"errors": validation_errors}), HTTPStatus.BAD_REQUEST
        
        return self.handler.update(entity_type, entity_id, data)

    def handle_delete(self, entity_type: str, entity_id: int) -> tuple:
        """Handle DELETE request."""
        if entity_id is None:
            return jsonify({"error": "ID parameter is required"}), HTTPStatus.BAD_REQUEST
        return self.handler.delete(entity_type, entity_id)

    def run(self, *args, **kwargs):
        """Run the Flask application."""
        self.app.run(*args, **kwargs)


if __name__ == '__main__':
    import sys
    spec_files = sys.argv[1:] if len(sys.argv) > 1 else ['openapi.yaml']
    app = OpenAPIFlask(spec_files)
    app.run(debug=True, port=5000)
