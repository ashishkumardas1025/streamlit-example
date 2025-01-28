from jsonschema import validate as jsonschema_validate
import random
import string
import datetime

def resolve_schema_ref(schema_ref, spec):
    """Resolve schema reference from OpenAPI spec"""
    if not isinstance(schema_ref, str):
        return schema_ref
        
    ref_path = schema_ref.replace('#/', '').split('/')
    current = spec
    for path in ref_path:
        current = current[path]
    return current

def validate_request(data, schema, spec):
    """Validate request data against schema"""
    if '$ref' in schema:
        schema = resolve_schema_ref(schema['$ref'], spec)
    jsonschema_validate(instance=data, schema=schema)

def generate_response(data, schema, spec):
    """Generate response based on schema"""
    if not data:
        return generate_mock_data(schema, spec)
    return data

def generate_mock_data(schema, spec):
    """Generate mock data based on schema"""
    if '$ref' in schema:
        schema = resolve_schema_ref(schema['$ref'], spec)
        
    if schema['type'] == 'object':
        result = {}
        for prop, prop_schema in schema.get('properties', {}).items():
            result[prop] = generate_mock_data(prop_schema, spec)
        return result
        
    elif schema['type'] == 'array':
        return [generate_mock_data(schema['items'], spec) for _ in range(2)]
        
    elif schema['type'] == 'string':
        if 'enum' in schema:
            return random.choice(schema['enum'])
        if schema.get('format') == 'date-time':
            return datetime.datetime.now().isoformat()
        if schema.get('format') == 'email':
            return f"user{random.randint(1,100)}@example.com"
        return ''.join(random.choices(string.ascii_letters, k=8))
        
    elif schema['type'] == 'integer':
        return random.randint(1, 100)
        
    elif schema['type'] == 'number':
        return round(random.uniform(1, 100), 2)
        
    elif schema['type'] == 'boolean':
        return random.choice([True, False])
        
    return None
