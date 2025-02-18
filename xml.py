import uuid
from datetime import datetime
from flask import Flask, request, jsonify, Response
import yaml
import os
import xmltodict

app = Flask(__name__)
CONFIG_FILE = "config.xml.yaml"  # YAML file for storing XML data

def create_empty_yaml():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            yaml.dump({"xml_endpoints": {}}, f)

def read_config():
    create_empty_yaml()
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f) or {"xml_endpoints": {}}

def write_config(config):
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

def normalize_path(path):
    return '/' + path.strip('/')

@app.route('/xml-simulator/<path:path>', methods=['POST'])
def register_xml_endpoint(path):
    """Registers a new XML endpoint."""
    try:
        config = read_config()
        normalized_path = normalize_path(path)
        xml_data = request.data.decode("utf-8")

        if not xml_data:
            return jsonify({"status": "error", "message": "Empty XML data"}), 400

        # Convert XML to Dictionary
        try:
            parsed_xml = xmltodict.parse(xml_data)
        except Exception as e:
            return jsonify({"status": "error", "message": f"Invalid XML format: {str(e)}"}), 400

        if normalized_path not in config["xml_endpoints"]:
            config["xml_endpoints"][normalized_path] = {"instances": []}

        instances = config["xml_endpoints"][normalized_path]["instances"]

        # Duplicate check
        for instance in instances:
            if instance["request"] == parsed_xml:
                return jsonify({"status": "error", "message": "Duplicate XML request"}), 400

        # Store new XML request-response pair
        new_instance = {
            "id": str(uuid.uuid4()),
            "method": "POST",
            "request": parsed_xml,
            "response": "<response><message>Success</message></response>",  # Example Response
            "created_at": str(datetime.now())
        }
        instances.append(new_instance)
        write_config(config)

        return Response(new_instance["response"], mimetype="application/xml"), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/xml-simulator/<path:path>', methods=['GET'])
def get_all_xml_endpoints(path):
    """Fetches all XML endpoints for a given path."""
    config = read_config()
    normalized_path = normalize_path(path)

    if normalized_path in config["xml_endpoints"]:
        return jsonify({
            "status": "success",
            "endpoints": config["xml_endpoints"][normalized_path]["instances"]
        }), 200

    return jsonify({"status": "error", "message": "No endpoints found for the given path"}), 404

@app.route('/xml-simulator/<path:path>/<endpoint_id>', methods=['GET'])
def get_xml_endpoint(path, endpoint_id):
    """Fetches a specific XML endpoint by ID."""
    config = read_config()
    normalized_path = normalize_path(path)

    if normalized_path in config["xml_endpoints"]:
        for instance in config["xml_endpoints"][normalized_path]["instances"]:
            if instance["id"] == endpoint_id:
                return Response(xmltodict.unparse({"response": instance["response"]}), mimetype="application/xml"), 200

    return jsonify({"status": "error", "message": "Endpoint not found"}), 404

@app.route('/xml-simulator/<path:path>/<endpoint_id>', methods=['PUT'])
def update_xml_endpoint(path, endpoint_id):
    """Updates an existing XML endpoint."""
    try:
        config = read_config()
        normalized_path = normalize_path(path)
        xml_data = request.data.decode("utf-8")

        if not xml_data:
            return jsonify({"status": "error", "message": "Empty XML data"}), 400

        try:
            parsed_xml = xmltodict.parse(xml_data)
        except Exception as e:
            return jsonify({"status": "error", "message": f"Invalid XML format: {str(e)}"}), 400

        if normalized_path in config["xml_endpoints"]:
            for instance in config["xml_endpoints"][normalized_path]["instances"]:
                if instance["id"] == endpoint_id:
                    instance["request"] = parsed_xml
                    instance["updated_at"] = str(datetime.now())
                    write_config(config)
                    return jsonify({"status": "success", "message": "Endpoint updated successfully"}), 200

        return jsonify({"status": "error", "message": "Endpoint not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/xml-simulator/<path:path>/<endpoint_id>', methods=['DELETE'])
def delete_xml_endpoint(path, endpoint_id):
    """Deletes a specific XML endpoint."""
    config = read_config()
    normalized_path = normalize_path(path)

    if normalized_path in config["xml_endpoints"]:
        instances = config["xml_endpoints"][normalized_path]["instances"]
        for i, instance in enumerate(instances):
            if instance["id"] == endpoint_id:
                del instances[i]
                write_config(config)
                return jsonify({"status": "success", "message": "Endpoint deleted successfully"}), 200

    return jsonify({"status": "error", "message": "Endpoint not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)





# xml data
request:
<user>
    <id>12345</id>
    <name>John Doe</name>
    <email>john.doe@example.com</email>
    <age>30</age>
</user>
response:
<response>
    <message>Success</message>
</response>


request:
<order>
    <orderId>98765</orderId>
    <customer>
        <name>Jane Doe</name>
        <email>jane.doe@example.com</email>
    </customer>
    <items>
        <item>
            <name>Laptop</name>
            <price>1200.50</price>
            <quantity>1</quantity>
        </item>
        <item>
            <name>Mouse</name>
            <price>25.99</price>
            <quantity>2</quantity>
        </item>
    </items>
    <totalPrice>1252.48</totalPrice>
</order>

 response:
 <response>
    <message>Success</message>
</response>

