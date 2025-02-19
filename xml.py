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
import yaml
import os
from datetime import datetime
from flask import Flask, request, Response

app = Flask(__name__)
CONFIG_FILE = "config.yaml"

def create_empty_yaml():
    """Creates an empty config file if not exists."""
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            yaml.dump({"endpoints": {}}, f)

def read_config():
    """Reads the config file."""
    create_empty_yaml()
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f) or {"endpoints": {}}

def write_config(config):
    """Writes data to the config file."""
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

@app.route('/olbb-simulator/xml/register', methods=['POST'])
def register_generic_xml():
    """Handles generic XML requests and stores them in config.yaml."""
    try:
        # Parse XML from request
        xml_data = request.data.decode("utf-8")
        parsed_data = xmltodict.parse(xml_data)

        # Extract root tag (e.g., OrderInfo, LoanApplication)
        root_tag = list(parsed_data.keys())[0]
        data = parsed_data[root_tag]

        # Ensure the XML contains both Request and Response
        if "Request" not in data or "Response" not in data:
            return Response("<Error>Invalid XML Format: Missing Request or Response</Error>", status=400, mimetype="application/xml")

        request_data = data["Request"]
        response_data = data["Response"]

        config = read_config()
        endpoint_id = str(uuid.uuid4())

        # Check for duplicates
        for existing_endpoint in config["endpoints"].values():
            if existing_endpoint["request"] == request_data and existing_endpoint["response"] == response_data:
                return Response("<Error>Duplicate Entry</Error>", status=400, mimetype="application/xml")

        # Store request & response in config file
        config["endpoints"][endpoint_id] = {
            "id": endpoint_id,
            "root_tag": root_tag,
            "request": request_data,
            "response": response_data,
            "created_at": str(datetime.now())
        }
        write_config(config)

        # Success Response
        success_xml = f"""<Response>
                            <Status>Success</Status>
                            <Message>Request registered successfully</Message>
                            <EndpointID>{endpoint_id}</EndpointID>
                        </Response>"""
        return Response(success_xml, status=200, mimetype="application/xml")

    except Exception as e:
        error_xml = f"<Error>Server Error: {str(e)}</Error>"
        return Response(error_xml, status=500, mimetype="application/xml")

if __name__ == "__main__":
    app.run(debug=True)




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
