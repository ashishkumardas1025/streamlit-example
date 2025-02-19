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

#sample post
import uuid
import xmltodict
from datetime import datetime
from flask import Flask, request, jsonify
import yaml
import os

app = Flask(__name__)
CONFIG_FILE = "config.yaml"

def create_empty_yaml():
    """Ensures the config file exists."""
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            yaml.dump({"xml_endpoints": {}}, f)

def read_config():
    """Reads the configuration file."""
    create_empty_yaml()
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f) or {"xml_endpoints": {}}

def write_config(config):
    """Writes to the configuration file."""
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

def normalize_path(path):
    """Standardizes path format."""
    return '/' + path.strip('/')

@app.route('/olbb-simulator/xml/<path:path>', methods=['POST'])
def register_generic_xml(path):
    """Registers a generic XML-based request and response under a given path."""
    try:
        # Read XML data from request body
        xml_data = request.data.decode('utf-8')
        parsed_data = xmltodict.parse(xml_data)  # Convert XML to dict

        # Dynamically identify the root node
        root_key = list(parsed_data.keys())[0]  # Get the first key (root)
        if root_key not in parsed_data:
            return jsonify({"status": "error", "message": "Invalid XML format"}), 400

        root_content = parsed_data[root_key]

        # Ensure request and response parts exist dynamically
        request_data = None
        response_data = None

        for key, value in root_content.items():
            if "request" in key.lower():
                request_data = value
            elif "response" in key.lower():
                response_data = value

        if not request_data or not response_data:
            return jsonify({"status": "error", "message": "XML must contain both <Request> and <Response> sections"}), 400

        # Load config and normalize path
        config = read_config()
        normalized_path = normalize_path(path)

        # Initialize path if not present
        if normalized_path not in config["xml_endpoints"]:
            config["xml_endpoints"][normalized_path] = {"instances": []}

        instances = config["xml_endpoints"][normalized_path]["instances"]

        # Check for duplicate request-response pairs
        for instance in instances:
            if instance["request"] == request_data and instance["response"] == response_data:
                return jsonify({"status": "error", "message": "Duplicate request and response"}), 400

        # Generate unique ID for this registration
        new_instance = {
            "id": str(uuid.uuid4()),
            "method": "POST",
            "request": request_data,
            "response": response_data,
            "created_at": str(datetime.now())
        }

        # Store in config
        instances.append(new_instance)
        write_config(config)

        return jsonify({"status": "success", "message": "XML endpoint registered successfully", "id": new_instance["id"]}), 200
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500





# xml data
<OrderInfo>
    <Request>
        <OrderDetails>
            <OrderID>ORD123456</OrderID>
            <OrderDate>2023-10-01T14:30:00Z</OrderDate>
            <TotalAmount currency="USD">250.00</TotalAmount>
        </OrderDetails>
        
        <Customer>
            <CustomerID>CU12345</CustomerID>
            <FirstName>Jane</FirstName>
            <LastName>Smith</LastName>
            <Email>jane.smith@example.com</Email>
            <PhoneNumber>+1234567890</PhoneNumber>
            <ShippingAddress>
                <Street>123 Elm St</Street>
                <City>Springfield</City>
                <State>IL</State>
                <ZipCode>62701</ZipCode>
                <Country>USA</Country>
            </ShippingAddress>
        </Customer>
        
        <Items>
            <Item>
                <ItemID>ITM001</ItemID>
                <ProductName>Wireless Mouse</ProductName>
                <Quantity>2</Quantity>
                <Price currency="USD">25.00</Price>
            </Item>
            <Item>
                <ItemID>ITM002</ItemID>
                <ProductName>Mechanical Keyboard</ProductName>
                <Quantity>1</Quantity>
                <Price currency="USD">100.00</Price>
            </Item>
            <Item>
                <ItemID>ITM003</ItemID>
                <ProductName>HD Monitor</ProductName>
                <Quantity>1</Quantity>
                <Price currency="USD">150.00</Price>
            </Item>
        </Items>
        
        <PaymentInformation>
            <PaymentMethod>CreditCard</PaymentMethod>
            <CardDetails>
                <CardNumber>************1111</CardNumber>
                <ExpiryDate>12/25</ExpiryDate>
                <CVV>***</CVV>
            </CardDetails>
            <BillingAddress>
                <Street>456 Oak St</Street>
                <City>Springfield</City>
                <State>IL</State>
                <ZipCode>62701</ZipCode>
                <Country>USA</Country>
            </BillingAddress>
        </PaymentInformation>
    </Request>
    <Response>
        <Status>Success</Status>
        <Message>Order processed successfully.</Message>
        <OrderID>ORD123456</OrderID>
        <TransactionID>TXN987654</TransactionID>
        <Timestamp>2023-10-01T14:35:00Z</Timestamp>
    </Response>
</OrderInfo>
