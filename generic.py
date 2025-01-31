from flask import Flask, request, jsonify
import yaml
import os

app = Flask(__name__)

# In-memory storage for dynamic endpoints and data
storage = {}
dynamic_endpoints = {}

def get_or_create_storage(path):
    """Ensure storage exists for a specific endpoint path."""
    if path not in storage:
        storage[path] = []
    return storage[path]

@app.before_request
def handle_dynamic_routes():
    """Intercept requests and dynamically register endpoints if not found."""
    path = request.path
    method = request.method

    # If endpoint already registered, let Flask handle it
    if path in dynamic_endpoints and method in dynamic_endpoints[path]:
        return None  

    # Extract response schema dynamically from request data
    if method in ["POST", "PUT"]:
        data = request.get_json()
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON payload"}), 400
        response_schema = {key: type(value).__name__ for key, value in data.items()}
    else:
        response_schema = {}

    # Register the endpoint dynamically
    register_dynamic_endpoint(path, method, response_schema)

def register_dynamic_endpoint(path, method, response_schema):
    """Register a new endpoint dynamically."""
    if path not in dynamic_endpoints:
        dynamic_endpoints[path] = {}

    def dynamic_handler(petID=None):
        """Generic handler for dynamic endpoints."""
        if method == "GET":
            return jsonify(storage.get(path, [])), 200
        elif method == "POST":
            data = request.get_json()
            get_or_create_storage(path).append(data)
            return jsonify(data), 201
        elif method == "PUT":
            data = request.get_json()
            storage[path] = data
            return jsonify(data), 200
        elif method == "DELETE":
            storage.pop(path, None)
            return "", 204

    # Store endpoint details
    dynamic_endpoints[path][method] = response_schema

    # Dynamically add the route
    app.add_url_rule(path, path.replace("/", "_") + "_" + method, dynamic_handler, methods=[method])

@app.route("/list-endpoints", methods=["GET"])
def list_endpoints():
    """List dynamically registered endpoints."""
    return jsonify(dynamic_endpoints), 200

if __name__ == "__main__":
    app.run(debug=True, port=5000)
