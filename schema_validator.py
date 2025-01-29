from flask import Flask, request, jsonify
import yaml
import os
import logging
from http import HTTPStatus
import re
import sys

class GenericAPIHandler:
    """Handles CRUD operations for any entity dynamically."""
    def __init__(self, logger):
        self.store = {}
        self.logger = logger

    def get_or_create_store(self, entity_type):
        if entity_type not in self.store:
            self.store[entity_type] = {}
        return self.store[entity_type]

    def get_all(self, entity_type):
        return jsonify(list(self.get_or_create_store(entity_type).values())), HTTPStatus.OK

    def get_one(self, entity_type, entity_id):
        entity = self.get_or_create_store(entity_type).get(entity_id)
        if entity:
            return jsonify(entity), HTTPStatus.OK
        return jsonify({"error": "Not Found"}), HTTPStatus.NOT_FOUND

    def create(self, entity_type, data):
        store = self.get_or_create_store(entity_type)
        entity_id = len(store) + 1
        data["id"] = entity_id
        store[entity_id] = data
        return jsonify(data), HTTPStatus.CREATED

    def update(self, entity_type, entity_id, data):
        store = self.get_or_create_store(entity_type)
        if entity_id not in store:
            return jsonify({"error": "Not Found"}), HTTPStatus.NOT_FOUND
        store[entity_id].update(data)
        return jsonify(store[entity_id]), HTTPStatus.OK

    def delete(self, entity_type, entity_id):
        store = self.get_or_create_store(entity_type)
        if entity_id in store:
            del store[entity_id]
            return '', HTTPStatus.NO_CONTENT
        return jsonify({"error": "Not Found"}), HTTPStatus.NOT_FOUND

class OpenAPIFlask:
    """Dynamic Flask application based on OpenAPI specifications."""
    def __init__(self, spec_file):
        self.setup_logging()
        self.app = Flask(__name__)
        self.handler = GenericAPIHandler(self.logger)
        self.load_spec(spec_file)
        self.register_routes()

    def setup_logging(self):
        self.logger = logging.getLogger(__name__)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def load_spec(self, spec_file):
        with open(spec_file, 'r') as file:
            self.spec = yaml.safe_load(file)

    def register_routes(self):
        for path, methods in self.spec.get('paths', {}).items():
            flask_path = path.replace('{', '<').replace('}', '>')
            for method, operation in methods.items():
                self.register_route(flask_path, method, operation)

    def register_route(self, path, method, operation):
        def route_handler(**kwargs):
            entity_type = path.split('/')[1]
            entity_id_key = next((key for key in kwargs if key.endswith('id')), None)
            entity_id = kwargs.get(entity_id_key, None)
            if entity_id:
                try:
                    entity_id = int(entity_id)
                except ValueError:
                    return jsonify({"error": "Invalid ID format"}), HTTPStatus.BAD_REQUEST
            
            if method == 'get' and entity_id:
                return self.handler.get_one(entity_type, entity_id)
            elif method == 'get':
                return self.handler.get_all(entity_type)
            elif method == 'post':
                return self.handler.create(entity_type, request.get_json())
            elif method == 'put':
                return self.handler.update(entity_type, entity_id, request.get_json())
            elif method == 'delete':
                return self.handler.delete(entity_type, entity_id)
            return jsonify({"error": "Method Not Allowed"}), HTTPStatus.METHOD_NOT_ALLOWED

        endpoint = f"{method}_{path}"
        self.app.add_url_rule(path, endpoint, route_handler, methods=[method.upper()])

    def run(self):
        self.app.run(debug=True, port=5000)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python script.py <openapi_spec.yaml>")
        sys.exit(1)
    
    spec_file = sys.argv[1]
    app = OpenAPIFlask(spec_file)
    app.run()
