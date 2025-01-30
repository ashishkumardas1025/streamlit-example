import json
import os
from typing import Any, Dict, List, Optional
from flask import Flask, request, jsonify, Response
import yaml
from jsonschema import validate, ValidationError

class SchemaValidator:
    def __init__(self, schema: Dict[str, Any]):
        self.schema = schema
        self.definitions = schema.get('components', {}).get('schemas', {})

    def validate_schema(self, data: Dict[str, Any], schema_name: str) -> None:
        """Validate data against schema, handling reference resolution"""
        if schema_name not in self.definitions:
            raise ValueError(f"Schema {schema_name} not found in definitions")
        schema = self.definitions[schema_name]
        try:
            # Create a schema context with definitions for reference resolution
            schema_with_refs = {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "definitions": self.definitions,
                **schema
            }
            validate(instance=data, schema=schema_with_refs)
        except ValidationError as e:
            raise ValidationError(f"Schema validation failed: {str(e)}")

class GenericAPIHandler:
    def __init__(self, schema_validator: SchemaValidator):
        self.validator = schema_validator
        self.storage: Dict[str, List[Dict[str, Any]]] = {}

    def create_entity(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        schema_name = self._get_schema_name(entity_type)
        self.validator.validate_schema(data, schema_name)
        
        if entity_type not in self.storage:
            self.storage[entity_type] = []
        
        entity_id = len(self.storage[entity_type]) + 1
        entity = {**data, 'id': entity_id}
        self.storage[entity_type].append(entity)
        return entity

    def get_entities(self, entity_type: str) -> List[Dict[str, Any]]:
        return self.storage.get(entity_type, [])

    def get_entity(self, entity_type: str, entity_id: int) -> Optional[Dict[str, Any]]:
        return next((e for e in self.storage.get(entity_type, []) if e['id'] == entity_id), None)

    def update_entity(self, entity_type: str, entity_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        schema_name = self._get_schema_name(entity_type)
        self.validator.validate_schema(data, schema_name)
        
        entities = self.storage.get(entity_type, [])
        for i, entity in enumerate(entities):
            if entity['id'] == entity_id:
                updated_entity = {**entity, **data, 'id': entity_id}
                self.storage[entity_type][i] = updated_entity
                return updated_entity
        return None

    def delete_entity(self, entity_type: str, entity_id: int) -> bool:
        entities = self.storage.get(entity_type, [])
        for i, entity in enumerate(entities):
            if entity['id'] == entity_id:
                del self.storage[entity_type][i]
                return True
        return False

    @staticmethod
    def _get_schema_name(entity_type: str) -> str:
        """Convert entity type to proper schema name format"""
        return entity_type.strip('/').capitalize()

class OpenAPIFlask:
    def __init__(self, yaml_file: str):
        self.app = Flask(__name__)
        self.spec = self._load_spec(yaml_file)
        self.validator = SchemaValidator(self.spec)
        self.handler = GenericAPIHandler(self.validator)
        self._register_routes()
        self._setup_error_handlers()

    def _load_spec(self, yaml_path: str) -> Dict[str, Any]:
        try:
            full_path = os.path.join(os.path.dirname(__file__), yaml_path)
            with open(full_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"Failed to load OpenAPI specification: {str(e)}")

    def _setup_error_handlers(self):
        @self.app.errorhandler(ValidationError)
        def handle_validation_error(error):
            return jsonify({'error': str(error)}), 400

        @self.app.errorhandler(404)
        def handle_not_found(error):
            return jsonify({'error': 'Resource not found'}), 404

        @self.app.errorhandler(Exception)
        def handle_generic_error(error):
            return jsonify({'error': str(error)}), 500

    def _register_routes(self) -> None:
        """Register routes based on OpenAPI specification"""
        paths = self.spec.get('paths', {})
        for path, path_spec in paths.items():
            entity_type = path.strip('/').lower()
            self._register_endpoints(entity_type, path_spec)

    def _create_endpoint_handler(self, entity_type: str, operation: str, operation_spec: Dict):
        """Create a closure for handling endpoint operations with proper response handling"""
        def get_all():
            try:
                entities = self.handler.get_entities(entity_type)
                return jsonify(entities), 200
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        def create():
            try:
                if not request.is_json:
                    return jsonify({'error': 'Content-Type must be application/json'}), 415
                
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'No data provided'}), 400
                
                created_entity = self.handler.create_entity(entity_type, data)
                return jsonify(created_entity), 201
            except ValidationError as e:
                return jsonify({'error': str(e)}), 400
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        def get_one(entity_id):
            try:
                entity = self.handler.get_entity(entity_type, entity_id)
                if not entity:
                    return jsonify({'error': 'Entity not found'}), 404
                return jsonify(entity), 200
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        def update(entity_id):
            try:
                if not request.is_json:
                    return jsonify({'error': 'Content-Type must be application/json'}), 415
                
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'No data provided'}), 400
                
                updated_entity = self.handler.update_entity(entity_type, entity_id, data)
                if not updated_entity:
                    return jsonify({'error': 'Entity not found'}), 404
                return jsonify(updated_entity), 200
            except ValidationError as e:
                return jsonify({'error': str(e)}), 400
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        def delete(entity_id):
            try:
                if self.handler.delete_entity(entity_type, entity_id):
                    return '', 204
                return jsonify({'error': 'Entity not found'}), 404
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        operations_map = {
            'get_all': get_all,
            'create': create,
            'get_one': get_one,
            'update': update,
            'delete': delete
        }
        return operations_map.get(operation)

    def _register_endpoints(self, entity_type: str, path_spec: Dict) -> None:
        """Register endpoints with proper request methods based on OpenAPI spec"""
        base_path = f'/api/{entity_type}'

        # Map HTTP methods to operations
        method_map = {
            'get': ('get_all', 'GET'),
            'post': ('create', 'POST'),
        }

        # Register collection endpoints
        for method, (operation, http_method) in method_map.items():
            if method in path_spec:
                self.app.add_url_rule(
                    base_path,
                    f'{operation}_{entity_type}',
                    self._create_endpoint_handler(entity_type, operation, path_spec[method]),
                    methods=[http_method]
                )

        # Register individual entity endpoints
        entity_path = f'{base_path}/<int:entity_id>'
        entity_method_map = {
            'get': ('get_one', 'GET'),
            'put': ('update', 'PUT'),
            'delete': ('delete', 'DELETE')
        }

        for method, (operation, http_method) in entity_method_map.items():
            self.app.add_url_rule(
                entity_path,
                f'{operation}_{entity_type}',
                self._create_endpoint_handler(entity_type, operation, {}),
                methods=[http_method]
            )

    def run(self, host='localhost', port=5000, debug=True):
        self.app.run(host=host, port=port, debug=debug)

# Example usage
if __name__ == "__main__":
    with open('sample_openapi.yaml', 'w') as f:
        f.write(SAMPLE_YAML)
        api = OpenAPIFlask('sample_openapi.yaml')
        api.run(debug=True)
