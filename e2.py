import csv
import json
from jinja2 import Template

# Load objects.json for UUID translation
def load_objects(file_path):
    with open(file_path, "r") as f:
        objects = json.load(f)
    
    obj_dict = {}
    for obj in objects:
        obj_uuid = obj.get("uid")
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
def translate_uuid(uuid_list, obj_dict, detailed=False):
    if detailed:
        return [f"{obj_dict.get(uuid, uuid)} ({uuid})" for uuid in uuid_list]
    return [obj_dict.get(uuid, uuid) for uuid in uuid_list]

# Load CSV rules
def load_rules(csv_path, obj_dict, detailed=False):
    rules = []
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["Source"] = translate_uuid(row.get("Source", "").split("; "), obj_dict, detailed)
            row["Destination"] = translate_uuid(row.get("Destination", "").split("\n"), obj_dict, detailed)
            row["Service"] = translate_uuid(row.get("Service", "").split("; "), obj_dict, detailed)
            row["Action"] = obj_dict.get(row.get("Action", ""), row.get("Action", ""))
            row["Comments"] = row.get("Comments", "").replace(",", " ").replace("\n", " ")
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
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
    <script>
        function toggleDetails() {
            var elements = document.querySelectorAll(".details");
            for (var i = 0; i < elements.length; i++) {
                elements[i].style.display = elements[i].style.display === 'none' ? 'block' : 'none';
            }
        }
    </script>
</head>
<body>
    <h2>Firewall Rules</h2>
    <button onclick="toggleDetails()">Toggle Object Details</button>
    <table>
        <tr>
            <th>Rule Name</th>
            <th>Action</th>
            <th>Source</th>
            <th>Destination</th>
            <th>Service</th>
            <th>Comments</th>
        </tr>
        {% for rule in rules %}
        <tr>
            <td>{{ rule["Name"] }}</td>
            <td>{{ rule["Action"] }}</td>
            <td class="details">{{ rule["Source"] | join('<br>') }}</td>
            <td class="details">{{ rule["Destination"] | join('<br>') }}</td>
            <td class="details">{{ rule["Service"] | join('<br>') }}</td>
            <td>{{ rule["Comments"] }}</td>
        </tr>
        {% endfor %}
    </table>
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
    rules = load_rules(rules_file, obj_dict, detailed=True)
    generate_html(rules, output_html)
    print(f"Interactive report generated: {output_html}")

if __name__ == "__main__":
    main()
