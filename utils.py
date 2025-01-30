import json
import os
from typing import Any, Dict, List, Optional
from flask import Flask, request, jsonify
import yaml
from jsonschema import validate, ValidationError

class SchemaValidator:
    def __init__(self, schema: Dict[str, Any]):
        self.schema = schema
        self.definitions = schema.get('components', {}).get('schemas', {})

    def validate_schema(self, data: Dict[str, Any], schema_name: str) -> None:
        if schema_name not in self.definitions:
            raise ValueError(f"Schema {schema_name} not found in definitions")
        schema = self.definitions[schema_name]
        try:
            validate(instance=data, schema=schema)
        except ValidationError as e:
            raise ValidationError(f"Schema validation failed: {str(e)}")

class GenericAPIHandler:
    def __init__(self, schema_validator: SchemaValidator):
        self.validator = schema_validator
        self.storage: Dict[str, List[Dict[str, Any]]] = {}

    def create_entity(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        self.validator.validate_schema(data, entity_type)
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
        self.validator.validate_schema(data, entity_type)
        for i, entity in enumerate(self.storage.get(entity_type, [])):
            if entity['id'] == entity_id:
                self.storage[entity_type][i] = {**entity, **data, 'id': entity_id}
                return self.storage[entity_type][i]
        return None

    def delete_entity(self, entity_type: str, entity_id: int) -> bool:
        for i, entity in enumerate(self.storage.get(entity_type, [])):
            if entity['id'] == entity_id:
                del self.storage[entity_type][i]
                return True
        return False

class OpenAPIFlask:
    def __init__(self, yaml_file: str):
        self.app = Flask(__name__)
        self.spec = self._load_spec(yaml_file)
        self.validator = SchemaValidator(self.spec)
        self.handler = GenericAPIHandler(self.validator)
        self._register_routes()

    def _load_spec(self, yaml_path: str) -> Dict[str, Any]:
        full_path = os.path.join(os.path.dirname(__file__), yaml_path)
        with open(full_path, 'r') as f:
            return yaml.safe_load(f)

    def _register_routes(self) -> None:
        for path in self.spec.get('paths', {}):
            entity_type = path.strip('/').split('/')[-1]
            self._register_endpoints(entity_type)

    def _register_endpoints(self, entity_type: str) -> None:
        path = f'/api/{entity_type}'
        
        @self.app.route(path, methods=['GET'])
        def get_all():
            return jsonify(self.handler.get_entities(entity_type))
        
        @self.app.route(path, methods=['POST'])
        def create():
            data = request.get_json()
            try:
                return jsonify(self.handler.create_entity(entity_type, data)), 201
            except ValidationError as e:
                return jsonify({'error': str(e)}), 400

        entity_path = f'{path}/<int:entity_id>'
        
        @self.app.route(entity_path, methods=['GET'])
        def get_one(entity_id):
            entity = self.handler.get_entity(entity_type, entity_id)
            return jsonify(entity) if entity else (jsonify({'error': 'Not found'}), 404)
        
        @self.app.route(entity_path, methods=['PUT'])
        def update(entity_id):
            data = request.get_json()
            try:
                entity = self.handler.update_entity(entity_type, entity_id, data)
                return jsonify(entity) if entity else (jsonify({'error': 'Not found'}), 404)
            except ValidationError as e:
                return jsonify({'error': str(e)}), 400
        
        @self.app.route(entity_path, methods=['DELETE'])
        def delete(entity_id):
            return ('', 204) if self.handler.delete_entity(entity_type, entity_id) else (jsonify({'error': 'Not found'}), 404)

    def run(self, host='localhost', port=5000):
        self.app.run(host=host, port=port)

if __name__ == "__main__":
    api = OpenAPIFlask("openapi.yaml")
    api.run()
