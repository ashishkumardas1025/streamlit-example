from flask import Flask, request, jsonify
import yaml
import os
from typing import Dict, Any

app = Flask(__name__)

# Global storage for different entity types
storage = {}
id_counters = {}

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

@app.route('/<entity_type>', methods=['POST'])
def create_entity(entity_type):
    """Create a new entity"""
    try:
        initialize_storage(entity_type)
        data = request.get_json()
        entity_id = get_next_id(entity_type)
        data['id'] = entity_id
        storage[entity_type][entity_id] = data
        return jsonify({"data": data}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/<entity_type>', methods=['GET'])
def get_all_entities(entity_type):
    """Get all entities of a type"""
    try:
        initialize_storage(entity_type)
        entities = list(storage[entity_type].values())
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
    # Load spec file but use it only for validation if needed
    spec = load_spec(spec_file)
    app.run(debug=True, port=5000)
