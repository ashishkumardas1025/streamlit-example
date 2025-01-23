# Welcome to Streamlit!

Edit `/streamlit_app.py` to customize this app to your heart's desire. :heart:

If you have any questions, checkout our [documentation](https://docs.streamlit.io) and [community
forums](https://discuss.streamlit.io).
      


import yaml
import random
import re
from typing import Dict, Any
from flask import Flask, jsonify, request
from faker import Faker

class ComprehensiveAPISimulator:
    def __init__(self, config_path: str):
        """Initialize API simulator with OpenAPI configuration"""
        self.app = Flask(__name__)
        self.faker = Faker()
        self.config = self._load_config(config_path)
        self._setup_routes()
    
    def _load_config(self, config_path: str) -> Dict:
        """Load OpenAPI configuration"""
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    
    def _resolve_reference(self, ref: str) -> Dict:
        """Resolve OpenAPI $ref references"""
        if not ref.startswith('#/'):
            return {}
        
        path = ref.split('/')[1:]
        current = self.config
        for part in path:
            current = current.get(part, {})
        return current
    
    def _generate_dynamic_value(self, schema: Dict) -> Any:
        """Generate dynamic values based on schema type"""
        if '$ref' in schema:
            schema = self._resolve_reference(schema['$ref'])
        
        schema_type = schema.get('type')
        
        # Comprehensive value generation
        if schema_type == 'string':
            format_type = schema.get('format')
            if format_type == 'email':
                return self.faker.email()
            elif format_type == 'date':
                return self.faker.date()
            elif format_type == 'date-time':
                return self.faker.date_time().isoformat()
            elif format_type == 'uuid':
                return str(self.faker.uuid4())
            return self.faker.text(max_nb_chars=50)
        
        elif schema_type == 'integer':
            return self.faker.random_int(min=1, max=1000)
        
        elif schema_type == 'number':
            return round(random.uniform(0.1, 1000.0), 2)
        
        elif schema_type == 'boolean':
            return random.choice([True, False])
        
        elif schema_type == 'array':
            items_schema = schema.get('items', {})
            return [
                self._generate_dynamic_value(items_schema) 
                for _ in range(random.randint(1, 5))
            ]
        
        elif schema_type == 'object':
            return self._generate_object_response(schema)
        
        return None
    
    def _generate_object_response(self, schema: Dict) -> Dict:
        """Generate dynamic object response"""
        response = {}
        properties = schema.get('properties', {})
        
        for prop_name, prop_schema in properties.items():
            response[prop_name] = self._generate_dynamic_value(prop_schema)
        
        return response
    
    def _setup_routes(self):
        """Dynamically create routes from OpenAPI specification"""
        paths = self.config.get('paths', {})
        for path, path_methods in paths.items():
            # Convert OpenAPI path parameters to Flask format
            flask_path = re.sub(r'{([^}]+)}', r'<\1>', path)
            
            for method, operation in path_methods.items():
                method = method.lower()
                if method in ['get', 'post', 'put', 'delete', 'patch']:
                    handler = self._create_endpoint_handler(operation)
                    self.app.route(flask_path, methods=[method.upper()])(handler)
    
    def _create_endpoint_handler(self, operation: Dict):
        """Create a handler for a specific endpoint"""
        def handler(*args, **kwargs):
            try:
                # Determine response based on HTTP method
                method = request.method.lower()
                responses = operation.get('responses', {})
                
                # Select appropriate status code
                status_codes = {
                    'post': ['201', '400', '404'],
                    'get': ['200', '404'],
                    'put': ['200', '204', '400'],
                    'delete': ['204', '404'],
                    'patch': ['200', '400']
                }
                
                # Choose a status code based on method
                possible_codes = status_codes.get(method, ['200'])
                status_code = random.choice(possible_codes)
                
                # Find response schema
                response_config = responses.get(status_code, {})
                content = response_config.get('content', {})
                json_content = content.get('application/json', {})
                response_schema = json_content.get('schema', {})
                
                # Generate response
                if status_code in ['200', '201']:
                    response_data = self._generate_dynamic_value(response_schema)
                    return jsonify(response_data), int(status_code)
                else:
                    # Error responses
                    error_responses = {
                        '400': {"error": "Bad Request", "message": self.faker.sentence()},
                        '404': {"error": "Not Found", "message": self.faker.sentence()},
                        '204': None
                    }
                    error_response = error_responses.get(status_code)
                    return jsonify(error_response) if error_response else '', int(status_code)
            
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        return handler
    
    def run(self, host: str = "0.0.0.0", port: int = 5000, debug: bool = True):
        """Run the API simulator"""
        self.app.run(host=host, port=port, debug=debug)

# Example usage
if __name__ == "__main__":
    simulator = ComprehensiveAPISimulator(config_path="openapi_config.yaml")
    simulator.run()
```

Key Enhancements:
1. Multiple HTTP method support
2. Dynamic status code generation
3. Different response handling for each method
4. Error response simulation
5. Preserved previous dynamic generation capabilities

Improvements:
- Supports POST, GET, PUT, DELETE, PATCH methods
- Generates appropriate status codes
- Creates mock error responses
- Maintains flexible schema-based generation

Usage remains the same:
1. Prepare OpenAPI specification
2. Run the simulator
3. Send requests to simulated endpoints

Would you like me to elaborate on any specific aspect?
