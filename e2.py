import csv
import json
from jinja2 import Template

# Load objects.json for UUID translation
def load_objects(file_path):
    with open(file_path, "r") as f:
        objects = json.load(f)
    
    obj_dict = {}
    for obj in objects:
        obj_uuid = obj.get("uuid")
        obj_type = obj.get("type")
        obj_name = obj.get("name", obj_uuid)
        obj_comment = obj.get("comments", "")
        
        if obj_type == "host":
            obj_dict[obj_uuid] = obj.get("ipv4-address", obj_name)
        elif obj_type == "network":
            obj_dict[obj_uuid] = f"{obj.get('subnet4', '?')}/{obj.get('mask-length4', '?')}"
        elif obj_type in ["service-tcp", "service-udp"]:
            obj_dict[obj_uuid] = obj.get("port", obj_name)
        elif obj_type in ["accept", "drop"]:
            obj_dict[obj_uuid] = obj_type.capitalize()
        elif obj_type == "group":
            members = obj.get("members", [])
            obj_dict[obj_uuid] = ", ".join([obj_dict.get(m, m) for m in members])
        elif obj_type == "range":
            obj_dict[obj_uuid] = f"{obj.get('range-start', '?')} - {obj.get('range-end', '?')}"
        else:
            obj_dict[obj_uuid] = f"{obj_name} ({obj_comment})"
    
    return obj_dict

# Translate UUIDs to actual names
def translate_uuid(uuid_list, obj_dict):
    return [obj_dict.get(uuid, uuid) for uuid in uuid_list]

# Load CSV rules
def load_rules(csv_path, obj_dict):
    rules = []
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["Source"] = translate_uuid(row["Source"].split("; "), obj_dict)
            row["Destination"] = translate_uuid(row["Destination"].split("\n"), obj_dict)
            row["Service"] = translate_uuid(row["Service"].split("; "), obj_dict)
            row["Action"] = obj_dict.get(row["Action"], row["Action"])
            rules.append(row)
    return rules

# HTML Template
html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Firewall Rules</title>
    <style>
        body { font-family: Arial, sans-serif; }
        .rule { border: 1px solid #ddd; padding: 10px; margin: 10px; }
        .details { display: none; }
        button { margin: 5px; }
    </style>
    <script>
        function toggleDetails(id) {
            var details = document.getElementById(id);
            details.style.display = details.style.display === 'block' ? 'none' : 'block';
        }
    </script>
</head>
<body>
    <h2>Firewall Rules</h2>
    {% for rule in rules %}
    <div class="rule">
        <strong>Rule Name:</strong> {{ rule["Name"] }}<br>
        <strong>Action:</strong> {{ rule["Action"] }}<br>
        <button onclick="toggleDetails('details{{ loop.index }}')">Toggle Details</button>
        <div id="details{{ loop.index }}" class="details">
            <strong>Source:</strong> <br> {{ rule["Source"] | join('<br>') }}<br>
            <strong>Destination:</strong> <br> {{ rule["Destination"] | join('<br>') }}<br>
            <strong>Service:</strong> <br> {{ rule["Service"] | join('<br>') }}<br>
            <strong>Comments:</strong> {{ rule["Comments"] }}
        </div>
    </div>
    {% endfor %}
</body>
</html>
"""

# Generate HTML
def generate_html(rules, output_path):
    template = Template(html_template)
    html_content = template.render(rules=rules)
    with open(output_path, "w") as f:
        f.write(html_content)

# Main function
def main():
    objects_file = "objects.json"
    rules_file = "rules.csv"
    output_html = "rules_interactive.html"
    
    obj_dict = load_objects(objects_file)
    rules = load_rules(rules_file, obj_dict)
    generate_html(rules, output_html)
    print(f"Interactive report generated: {output_html}")

if __name__ == "__main__":
    main()
