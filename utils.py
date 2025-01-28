def parse_parameters(operation, request, path_params):
    """Parse and validate request parameters"""
    params = {}
    
    # Add path parameters
    params.update(path_params)
    
    # Parse query parameters
    if 'parameters' in operation:
        for param in operation['parameters']:
            if param['in'] == 'query' and param['name'] in request.args:
                params[param['name']] = request.args[param['name']]
            elif param['in'] == 'header' and param['name'] in request.headers:
                params[param['name']] = request.headers[param['name']]
    
    return params

def get_operation_id(path, method, operation):
    """Get or generate operation ID"""
    if 'operationId' in operation:
        return operation['operationId']
    
    # Generate operation ID if not provided
    path_parts = [p for p in path.split('/') if p and not p.startswith('{')]
    return f"{method}_{'_'.join(path_parts)}"
