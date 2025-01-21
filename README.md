# Welcome to Streamlit!

Edit `/streamlit_app.py` to customize this app to your heart's desire. :heart:

If you have any questions, checkout our [documentation](https://docs.streamlit.io) and [community
forums](https://discuss.streamlit.io).
import yaml
from fastapi import FastAPI, Request
from anthropic import Anthropic
import json
from typing import Dict, Any
import uvicorn
from pydantic import BaseModel
import random

class APISimulator:
    def __init__(self, config_path: str, anthropic_api_key: str):
        """
        Initialize the API simulator with config file and Anthropic API key
        """
        self.app = FastAPI()
        self.anthropic = Anthropic(api_key=anthropic_api_key)
        self.config = self._load_config(config_path)
        self._setup_routes()
    
    def _load_config(self, config_path: str) -> Dict:
        """
        Load and parse the YAML configuration file
        """
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    
    def _setup_routes(self):
        """
        Dynamically create FastAPI routes based on the YAML configuration
        """
        for endpoint, config in self.config['endpoints'].items():
            path = config['path']
            method = config['method'].lower()
            
            async def create_endpoint_handler(endpoint_config=config):
                return await self._handle_request(endpoint_config)
            
            # Register the route with FastAPI
            getattr(self.app, method)(path)(create_endpoint_handler)
    
    def _generate_dynamic_value(self, field_type: str, field_constraints: Dict = None) -> Any:
        """
        Generate dynamic values based on field type and constraints
        """
        if field_type == 'string':
            return ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=10))
        elif field_type == 'integer':
            min_val = field_constraints.get('minimum', 0)
            max_val = field_constraints.get('maximum', 100)
            return random.randint(min_val, max_val)
        elif field_type == 'boolean':
            return random.choice([True, False])
        elif field_type == 'array':
            return []
        return None
    
    async def _generate_response_with_claude(self, schema: Dict) -> Dict:
        """
        Use Claude to generate a response matching the schema
        """
        prompt = f"""
        Generate a JSON response following this schema:
        {json.dumps(schema, indent=2)}
        
        The response should:
        1. Match all required fields and types
        2. Include realistic but randomized values
        3. Be properly formatted as JSON
        
        Response:
        """
        
        response = await self.anthropic.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        # Extract JSON from Claude's response
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            # Fallback to basic schema-based generation
            return self._generate_basic_response(schema)
    
    def _generate_basic_response(self, schema: Dict) -> Dict:
        """
        Generate a basic response following the schema without Claude
        """
        response = {}
        for field_name, field_spec in schema['properties'].items():
            if 'type' in field_spec:
                response[field_name] = self._generate_dynamic_value(
                    field_spec['type'],
                    field_spec.get('constraints', {})
                )
        return response
    
    async def _handle_request(self, endpoint_config: Dict) -> Dict:
        """
        Handle incoming requests and generate responses
        """
        try:
            response_schema = endpoint_config['response']['schema']
            
            # Use Claude for complex schemas, fallback to basic generation
            if endpoint_config.get('use_claude', False):
                return await self._generate_response_with_claude(response_schema)
            else:
                return self._generate_basic_response(response_schema)
                
        except Exception as e:
            return {"error": str(e)}
    
    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """
        Run the API simulator
        """
        uvicorn.run(self.app, host=host, port=port)

# Example usage
if __name__ == "__main__":
    config_yaml = """
    endpoints:
      get_user:
        path: /api/users/{user_id}
        method: GET
        use_claude: true
        response:
          schema:
            type: object
            properties:
              id:
                type: integer
              name:
                type: string
              email:
                type: string
              active:
                type: boolean
            required: [id, name, email]
    """
    
    # Save config to a temporary file
    with open("temp_config.yaml", "w") as f:
        f.write(config_yaml)
    
    # Initialize and run the simulator
    simulator = APISimulator(
        config_path="temp_config.yaml",
        anthropic_api_key="your-api-key-here"
    )
    simulator.run()
