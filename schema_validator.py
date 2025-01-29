from flask import Flask, request, jsonify
import yaml
import os
from typing import Dict, Any, Optional, Tuple, List
import boto3
import json
import asyncio
from botocore.config import Config
from faker import Faker
import uuid
from datetime import datetime
import re

class DynamicResponseGenerator:
    """Handles dynamic response generation based on OpenAPI schema."""
    
    def __init__(self, region_name="us-east-1"):
        self.faker = Faker()
        self.bedrock_config = Config(
            region_name=region_name,
            retries={'max_attempts': 3, 'mode': 'standard'}
        )
        self.bedrock_runtime = boto3.client(
            service_name='bedrock-runtime',
            config=self.bedrock_config
        )
        self.model_id = "anthropic.claude-v2"
        self.cache = {}

    def generate_example_value(self, schema: Dict) -> Any:
        """Generate example value based on schema type."""
        schema_type = schema.get('type', 'string')
        schema_format = schema.get('format', '')
        example = schema.get('example')
        
        if example is not None:
            return example
            
        if schema_type == 'string':
            if schema_format == 'date-time':
                return datetime.now().isoformat()
            elif schema_format == 'email':
                return self.faker.email()
            elif schema_format == 'uuid':
                return str(uuid.uuid4())
            elif schema_format == 'uri':
                return self.faker.url()
            elif schema_format == 'password':
                return '********'
            else:
                return self.faker.word()
        elif schema_type == 'integer':
            return self.faker.random_int(min=schema.get('minimum', 0), 
                                      max=schema.get('maximum', 1000))
        elif schema_type == 'number':
            return self.faker.random_float(min=schema.get('minimum', 0), 
                                        max=schema.get('maximum', 1000))
        elif schema_type == 'boolean':
            return self.faker.boolean()
        elif schema_type == 'array':
            items = schema.get('items', {})
            min_items = schema.get('minItems', 1)
            max_items = schema.get('maxItems', 5)
            count = self.faker.random_int(min=min_items, max=max_items)
            return [self.generate_example_value(items) for _ in range(count)]
        elif schema_type == 'object':
            return self.generate_object_example(schema)
        return None

    def generate_object_example(self, schema: Dict) -> Dict:
        """Generate example object based on schema."""
        result = {}
        properties = schema.get('properties', {})
        required = schema.get('required', [])
        
        for prop_name, prop_schema in properties.items():
            if prop_name in required or self.faker.boolean(chance_of_getting_true=70):
                result[prop_name] = self.generate_example_value(prop_schema)
                
        return result

    async def generate_claude_response(self, prompt: str, schema: Dict) -> Any:
        """Generate response using Claude based on schema."""
        cache_key = f"{prompt}_{json.dumps(schema)}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            body = json.dumps({
                "prompt": f"Human: Generate a response for: {prompt}\nMake sure it matches this JSON schema: {json.dumps(schema)}\n\nAssistant:",
                "max_tokens_to_sample": 2000,
                "temperature": 0.7,
                "anthropic_version": "bedrock-2023-05-31"
            })

            response = self.bedrock_runtime.invoke_model(
                modelId=self.model_id,
                body=body
            )

            response_body = json.loads(response.get('body').read())
            generated_response = response_body.get('completion', '')
            
            try:
                # Try to parse as JSON if schema requires it
                parsed_response = json.loads(generated_response)
                self.cache[cache_key] = parsed_response
                return parsed_response
            except json.JSONDecodeError:
                # Return as string if not JSON
                self.cache[cache_key] = generated_response
                return generated_response

        except Exception as e:
            print(f"Error generating Claude response: {str(e)}")
            # Fallback to example generation
            return self.generate_example_value(schema)

class DynamicAPIHandler:
    """Handles dynamic API operations based on OpenAPI spec."""
    
    def __init__(self, spec: Dict):
        self.spec = spec
        self.response_generator = DynamicResponseGenerator()
        
    def get_operation_id(self, path: str, method: str) -> str:
        """Get operation ID from path and method."""
        path_obj = self.spec.get('paths', {}).get(path, {})
        operation = path_obj.get(method.lower(), {})
        return operation.get('operationId', f"{method.lower()}_{path}")

    def get_response_schema(self, path: str, method: str) -> Optional[Dict]:
        """Get response schema for path and method."""
        path_obj = self.spec.get('paths', {}).get(path, {})
        operation = path_obj.get(method.lower(), {})
        responses = operation.get('responses', {})
        
        # Get success response schema (2XX)
        for status_code in ['200', '201', '202']:
            if status_code in responses:
                return (responses[status_code]
                       .get('content', {})
                       .get('application/json', {})
                       .get('schema', {}))
        return None

    def get_request_schema(self, path: str, method: str) -> Optional[Dict]:
        """Get request body schema for path and method."""
        path_obj = self.spec.get('paths', {}).get(path, {})
        operation = path_obj.get(method.lower(), {})
        return (operation.get('requestBody', {})
                .get('content', {})
                .get('application/json', {})
                .get('schema', {}))

    async def handle_request(self, path: str, method: str, request_data: Optional[Dict] = None) -> Tuple[Any, int]:
        """Handle API request based on path and method."""
        operation_id = self.get_operation_id(path, method)
        response_schema = self.get_response_schema(path, method)
        
        if not response_schema:
            return {"error": "No response schema defined"}, 500

        # Generate dynamic prompt based on path, method and request data
        prompt = f"Generate a response for {method.upper()} {path}"
        if request_data:
            prompt += f"\nRequest data: {json.dumps(request_data)}"
            
        # Add operation-specific context
        path_params = re.findall(r'{([^}]+)}', path)
        if path_params:
            prompt += f"\nPath parameters: {', '.join(path_params)}"
            
        path_obj = self.spec.get('paths', {}).get(path, {})
        operation = path_obj.get(method.lower(), {})
        if 'description' in operation:
            prompt += f"\nOperation description: {operation['description']}"
            
        # Generate response
        try:
            response = await self.response_generator.generate_claude_response(
                prompt, response_schema)
            return response, 200
        except Exception as e:
            return {"error": str(e)}, 500

class OpenAPIFlask:
    """Dynamic Flask application that generates responses based on OpenAPI spec."""
    
    def __init__(self, spec_file: str):
        self.app = Flask(__name__)
        self.spec = self.load_spec(spec_file)
        self.handler = DynamicAPIHandler(self.spec)
        self.register_routes()

    def load_spec(self, spec_file: str) -> Dict:
        """Load and parse OpenAPI specification."""
        if not os.path.exists(spec_file):
            raise FileNotFoundError(f"Specification file {spec_file} not found.")
        with open(spec_file, 'r') as file:
            return yaml.safe_load(file)

    def register_routes(self):
        """Register routes dynamically based on OpenAPI spec."""
        paths = self.spec.get('paths', {})
        
        async def handle_request(path, method):
            request_data = request.get_json() if request.is_json else None
            response, status_code = await self.handler.handle_request(
                path, method, request_data)
            return jsonify(response), status_code

        for path, methods in paths.items():
            flask_path = path.replace('{', '<').replace('}', '>')
            
            for method in methods.keys():
                endpoint = f"{method}_{path}"
                self.app.add_url_rule(
                    flask_path,
                    endpoint,
                    lambda p=path, m=method: asyncio.run(handle_request(p, m)),
                    methods=[method.upper()]
                )

def run_app(spec_file: str):
    """Run the application."""
    app = OpenAPIFlask(spec_file)
    
    config = {
        'bind': '0.0.0.0:5000',
        'worker_class': 'uvicorn.workers.UvicornWorker'
    }
    
    return app.app

if __name__ == '__main__':
    import sys
    from hypercorn.config import Config
    from hypercorn.asyncio import serve

    spec_file = sys.argv[1] if len(sys.argv) > 1 else 'openapi.yaml'
    app = run_app(spec_file)
    
    config = Config()
    config.bind = ["0.0.0.0:5000"]
    
    asyncio.run(serve(app, config))
