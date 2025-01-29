from flask import Flask, request, jsonify
import yaml
import os
from typing import Dict, Any, List, Union
from datetime import datetime
import jsonschema
import logging
from http import HTTPStatus


class SchemaValidator:
    """Handles OpenAPI schema validation."""
    
    @staticmethod
    def validate_type(value: Any, expected_type: str) -> bool:
        """Validate value against expected type."""
        type_map = {
            'string': str,
            'integer': int,
            'number': (int, float),
            'boolean': bool,
            'array': list,
            'object': dict
        }
        return isinstance(value, type_map.get(expected_type, object))

    @staticmethod
    def validate_schema(data: Dict, schema: Dict) -> List[str]:
        """Validate data against OpenAPI schema."""
        errors = []
        
        # Check required fields
        required_fields = schema.get('required', [])
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        # Validate properties
        properties = schema.get('properties', {})
        for field, value in data.items():
            if field in properties:
                field_schema = properties[field]
                field_type = field_schema.get('type')
                
                if field_type and not SchemaValidator.validate_type(value, field_type):
                    errors.append(f"Invalid type for field {field}. Expected {field_type}")
                
                # Validate enum
                if 'enum' in field_schema and value not in field_schema['enum']:
                    errors.append(f"Invalid value for field {field}. Must be one of {field_schema['enum']}")
                
                # Validate format
                if field_schema.get('format') == 'date-time':
                    try:
                        datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        errors.append(f"Invalid date-time format for field {field}")
        
        return errors


class GenericAPIHandler:
    """Handles CRUD operations for any entity dynamically."""
    def __init__(self, logger):
        self.store: Dict[str, Dict[int, Any]] = {}
        self.id_counters: Dict[str, int] = {}
        self.logger = logger

    def get_entity_type(self, path: str) -> str:
        """Extract entity type from the path."""
        parts = [p for p in path.split('/') if p and not p.startswith('{')]
        return parts[0] if parts else 'default'

    def get_or_create_store(self, entity_type: str) -> Dict[int, Any]:
        """Get or create a store for the entity type."""
        if entity_type not in self.store:
            self.store[entity_type] = {}
            self.id_counters[entity_type] = 1
        return self.store[entity_type]

    def create(self, entity_type: str, data: Dict) -> tuple:
        """Create a new entity."""
        try:
            store = self.get_or_create_store(entity_type)
            entity_id = self.id_counters[entity_type]
            data['id'] = entity_id
            data['created_at'] = datetime.utcnow().isoformat()
            store[entity_id] = data
            self.id_counters[entity_type] += 1
            return data, HTTPStatus.CREATED
        except Exception as e:
            self.logger.error(f"Error creating {entity_type}: {str(e)}")
            return {"error": f"Failed to create {entity_type}"}, HTTPStatus.INTERNAL_SERVER_ERROR

    def get_all(self, entity_type: str, query_params: Dict = None) -> tuple:
        """Get all entities with optional filtering."""
        try:
            store = self.get_or_create_store(entity_type)
            results = list(store.values())
            
            if query_params:
                for key, value in query_params.items():
                    results = [item for item in results if str(item.get(key)) == str(value)]
            
            return results, HTTPStatus.OK
        except Exception as e:
            self.logger.error(f"Error retrieving {entity_type}: {str(e)}")
            return {"error": f"Failed to retrieve {entity_type}"}, HTTPStatus.INTERNAL_SERVER_ERROR

    def get_one(self, entity_type: str, entity_id: int) -> tuple:
        """Get a single entity."""
        try:
            store = self.get_or_create_store(entity_type)
            if entity_id not in store:
                return {"error": f"{entity_type} not found"}, HTTPStatus.NOT_FOUND
            return store[entity_id], HTTPStatus.OK
        except Exception as e:
            self.logger.error(f"Error retrieving {entity_type} {entity_id}: {str(e)}")
            return {"error": f"Failed to retrieve {entity_type}"}, HTTPStatus.INTERNAL_SERVER_ERROR

    def update(self, entity_type: str, entity_id: int, data: Dict) -> tuple:
        """Update an existing entity."""
        try:
            store = self.get_or_create_store(entity_type)
            if entity_id not in store:
                return {"error": f"{entity_type} not found"}, HTTPStatus.NOT_FOUND
            
            existing_data = store[entity_id].copy()
            existing_data.update(data)
            existing_data['updated_at'] = datetime.utcnow().isoformat()
            store[entity_id] = existing_data
            
            return existing_data, HTTPStatus.OK
        except Exception as e:
            self.logger.error(f"Error updating {entity_type} {entity_id}: {str(e)}")
            return {"error": f"Failed to update {entity_type}"}, HTTPStatus.INTERNAL_SERVER_ERROR

    def delete(self, entity_type: str, entity_id: int) -> tuple:
        """Delete an entity."""
        try:
            store = self.get_or_create_store(entity_type)
            if entity_id not in store:
                return {"error": f"{entity_type} not found"}, HTTPStatus.NOT_FOUND
            return store.pop(entity_id), HTTPStatus.OK
        except Exception as e:
            self.logger.error(f"Error deleting {entity_type} {entity_id}: {str(e)}")
            return {"error": f"Failed to delete {entity_type}"}, HTTPStatus.INTERNAL_SERVER_ERROR


class OpenAPIFlask:
    """Dynamic Flask application based on OpenAPI specifications."""
    def __init__(self, spec_files: Union[str, List[str]]):
        # Initialize logging first
        self.setup_logging()
        
        self.app = Flask(__name__)
        self.handler = GenericAPIHandler(self.logger)  # Pass logger to handler
        self.specs = {}
        self.load_specs(spec_files)
        self.register_routes()

    def setup_logging(self):
        """Configure logging for the application."""
        # Create a logger for this class
        self.logger = logging.getLogger(__name__)
        
        # Configure logging if it hasn't been configured yet
        if not self.logger.handlers:
            # Create console handler
            handler = logging.StreamHandler()
            
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            
            # Add formatter to handler
            handler.setFormatter(formatter)
            
            # Add handler to logger
            self.logger.addHandler(handler)
            
            # Set level
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
                    base_path = spec.get('basePath', '').rstrip('/')
                    
                    # Store the spec with its base path as the key
                    self.specs[base_path] = spec
                    self.logger.info(f"Loaded API spec from {spec_file}")
            except Exception as e:
                self.logger.error(f"Error loading spec file {spec_file}: {str(e)}")
                raise

    def find_matching_spec(self, path: str) -> tuple:
        """Find the matching spec and adjusted path for a given request path."""
        for base_path, spec in self.specs.items():
            if path.startswith(base_path):
                return spec, path[len(base_path):] if base_path else path
        return None, path

    def register_routes(self) -> None:
        """Register routes dynamically based on all loaded OpenAPI specs."""
        for base_path, spec in self.specs.items():
            paths = spec.get('paths', {})
            for path, methods in paths.items():
                full_path = f"{base_path}{path}".replace('{', '<').replace('}', '>')
                for method, operation in methods.items():
                    self.register_route(full_path, method, operation, spec)

    def register_route(self, path: str, method: str, operation: Dict, spec: Dict) -> None:
        """Register a single route with enhanced error handling and validation."""
        def route_handler(**kwargs):
            try:
                entity_type = self.handler.get_entity_type(path)
                query_params = request.args.to_dict()

                if method == 'get' and 'id' in kwargs:
                    return self.handle_get_one(entity_type, kwargs['id'])
                elif method == 'get':
                    return self.handle_get_all(entity_type, query_params)
                elif method == 'post':
                    return self.handle_create(entity_type, operation, request.get_json())
                elif method == 'put':
                    return self.handle_update(entity_type, kwargs['id'], operation, request.get_json())
                elif method == 'delete':
                    return self.handle_delete(entity_type, kwargs['id'])
                else:
                    return jsonify({"error": "Method not supported"}), HTTPStatus.METHOD_NOT_ALLOWED

            except Exception as e:
                self.logger.error(f"Error handling {method} request to {path}: {str(e)}")
                return jsonify({"error": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR

        endpoint = f"{method}_{path}"
        self.app.add_url_rule(path, endpoint, route_handler, methods=[method.upper()])

    def handle_get_one(self, entity_type: str, entity_id: str) -> tuple:
        """Handle GET request for a single entity."""
        try:
            result, status_code = self.handler.get_one(entity_type, int(entity_id))
            return jsonify(result), status_code
        except ValueError:
            return jsonify({"error": "Invalid ID format"}), HTTPStatus.BAD_REQUEST

    def handle_get_all(self, entity_type: str, query_params: Dict) -> tuple:
        """Handle GET request for all entities."""
        result, status_code = self.handler.get_all(entity_type, query_params)
        return jsonify(result), status_code

    def handle_create(self, entity_type: str, operation: Dict, data: Dict) -> tuple:
        """Handle POST request to create an entity."""
        schema = operation.get('requestBody', {}).get('content', {}).get('application/json', {}).get('schema', {})
        validation_errors = SchemaValidator.validate_schema(data, schema)
        
        if validation_errors:
            return jsonify({"errors": validation_errors}), HTTPStatus.BAD_REQUEST
        
        result, status_code = self.handler.create(entity_type, data)
        return jsonify(result), status_code

    def handle_update(self, entity_type: str, entity_id: str, operation: Dict, data: Dict) -> tuple:
        """Handle PUT request to update an entity."""
        try:
            schema = operation.get('requestBody', {}).get('content', {}).get('application/json', {}).get('schema', {})
            validation_errors = SchemaValidator.validate_schema(data, schema)
            
            if validation_errors:
                return jsonify({"errors": validation_errors}), HTTPStatus.BAD_REQUEST
            
            result, status_code = self.handler.update(entity_type, int(entity_id), data)
            return jsonify(result), status_code
        except ValueError:
            return jsonify({"error": "Invalid ID format"}), HTTPStatus.BAD_REQUEST

    def handle_delete(self, entity_type: str, entity_id: str) -> tuple:
        """Handle DELETE request."""
        try:
            result, status_code = self.handler.delete(entity_type, int(entity_id))
            return jsonify(result), status_code
        except ValueError:
            return jsonify({"error": "Invalid ID format"}), HTTPStatus.BAD_REQUEST

    def run(self, *args, **kwargs):
        """Run the Flask application."""
        self.app.run(*args, **kwargs)


if __name__ == '__main__':
    import sys
    spec_files = sys.argv[1:] if len(sys.argv) > 1 else ['openapi.yaml']
    app = OpenAPIFlask(spec_files)
    app.run(debug=True, port=5000)
