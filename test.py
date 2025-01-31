from flask import Flask, request, jsonify
import yaml
import os
from typing import Dict, Any

app = Flask(__name__)

# Global storage for different entity types
storage = {}
id_counters = {}
OPENAPI_FILE = "openapi.yaml"

def get_next_id(entity_type: str) -> int:
    """Get next ID for an entity type"""
    if entity_type not in id_counters:
        id_counters[entity_type] = 1
    current_id = id_counters[entity_type]
    id_counters[entity_type] += 1
    return current_id

def initialize_storage(entity_type: str):
    """Initialize storage for an entity type if it doesn't exist"""
    if entity_type not in storage:
        storage[entity_type] = {}

def load_openapi_spec() -> Dict:
    """Load the OpenAPI YAML file"""
    if os.path.exists(OPENAPI_FILE):
        with open(OPENAPI_FILE, "r") as file:
            try:
                return yaml.safe_load(file) or {}
            except yaml.YAMLError:
                return {}
    return {}

def save_openapi_spec(spec: Dict):
    """Save the updated OpenAPI YAML file"""
    with open(OPENAPI_FILE, "w") as file:
        yaml.dump(spec, file, default_flow_style=False)

def update_response_schema(entity_type: str, response_data: Dict):
    """Update the OpenAPI spec with the latest response schema"""
    spec = load_openapi_spec()

    # Ensure the OpenAPI structure exists
    if "components" not in spec:
        spec["components"] = {}
    if "schemas" not in spec["components"]:
        spec["components"]["schemas"] = {}

    # Update the schema for the entity type
    spec["components"]["schemas"][entity_type] = response_data

    # Save the updated spec back to the file
    save_openapi_spec(spec)

@app.route('/<entity_type>', methods=['POST'])
def create_entity(entity_type):
    """Create a new entity"""
    try:
        initialize_storage(entity_type)
        data = request.get_json()
        entity_id = get_next_id(entity_type)
        data['id'] = entity_id
        storage[entity_type][entity_id] = data

        # Store response schema inside openapi.yaml
        update_response_schema(entity_type, data)

        return jsonify({"data": data}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/<entity_type>', methods=['GET'])
def get_all_entities(entity_type):
    """Get all entities of a type"""
    try:
        initialize_storage(entity_type)
        entities = list(storage[entity_type].values())

        # Store response schema inside openapi.yaml
        update_response_schema(entity_type, entities)

        return jsonify({"data": entities}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/<entity_type>/<int:id>', methods=['GET'])
def get_entity(entity_type, id):
    """Get a single entity by ID"""
    try:
        initialize_storage(entity_type)
        if id not in storage[entity_type]:
            return jsonify({"error": f"{entity_type} not found"}), 404
        entity = storage[entity_type][id]

        # Store response schema inside openapi.yaml
        update_response_schema(entity_type, entity)

        return jsonify({"data": entity}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/<entity_type>/<int:id>', methods=['PUT'])
def update_entity(entity_type, id):
    """Update an entity"""
    try:
        initialize_storage(entity_type)
        if id not in storage[entity_type]:
            return jsonify({"error": f"{entity_type} not found"}), 404
        data = request.get_json()
        data['id'] = id
        storage[entity_type][id] = data

        # Store response schema inside openapi.yaml
        update_response_schema(entity_type, data)

        return jsonify({"data": data}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/<entity_type>/<int:id>', methods=['DELETE'])
def delete_entity(entity_type, id):
    """Delete an entity"""
    try:
        initialize_storage(entity_type)
        if id not in storage[entity_type]:
            return jsonify({"error": f"{entity_type} not found"}), 404
        deleted_entity = storage[entity_type].pop(id)

        # Store deleted entity schema inside openapi.yaml
        update_response_schema(entity_type, deleted_entity)

        return jsonify({"data": deleted_entity}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

def load_spec(spec_file: str) -> Dict:
    """Load and parse the OpenAPI specification"""
    if not os.path.exists(spec_file):
        raise FileNotFoundError(f"Specification file {spec_file} not found.")
    with open(spec_file, 'r') as file:
        return yaml.safe_load(file)

if __name__ == '__main__':
    import sys
    spec_file = sys.argv[1] if len(sys.argv) > 1 else 'openapi.yaml'
    spec = load_spec(spec_file)
    app.run(debug=True, port=5000)
