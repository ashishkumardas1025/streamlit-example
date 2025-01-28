    def register_route(self, path: str, method: str, operation: Dict) -> None:
        """Register a single route."""
        def route_handler(**kwargs):
            entity_type = path.split('/')[1]
            try:
                # Handle GET for a single entity (with ID)
                if method == 'get' and 'id' in kwargs:
                    entity_id = kwargs['id']
                    return jsonify(self.handler.get_one(entity_type, int(entity_id))[0]), 200
                
                # Handle GET for all entities
                elif method == 'get':
                    return jsonify(self.handler.get_all(entity_type)[0]), 200
                
                # Handle POST (create)
                elif method == 'post':
                    data = request.get_json()
                    schema = operation.get('requestBody', {}).get('content', {}).get('application/json', {}).get('schema', {})
                    self.validate_request_body(data, schema)
                    return jsonify(self.handler.create(entity_type, data)[0]), 201
                
                # Handle PUT (update)
                elif method == 'put':
                    if 'id' not in kwargs:
                        return jsonify({"error": "ID is required for update operation"}), 400
                    data = request.get_json()
                    entity_id = kwargs['id']
                    schema = operation.get('requestBody', {}).get('content', {}).get('application/json', {}).get('schema', {})
                    self.validate_request_body(data, schema)
                    return jsonify(self.handler.update(entity_type, int(entity_id), data)[0]), 200
                
                # Handle DELETE
                elif method == 'delete':
                    if 'id' not in kwargs:
                        return jsonify({"error": "ID is required for delete operation"}), 400
                    entity_id = kwargs['id']
                    return jsonify(self.handler.delete(entity_type, int(entity_id))[0]), 204
                
                # Method not supported
                else:
                    return jsonify({"error": "Method not supported"}), 405
            
            except Exception as e:
                return jsonify({"error": str(e)}), 400

        # Define endpoint and register the route
        endpoint = f"{method}_{path}"
        self.app.add_url_rule(path, endpoint, route_handler, methods=[method.upper()])
