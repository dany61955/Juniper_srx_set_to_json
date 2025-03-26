import csv
import json
import os
from jinja2 import Template

# Load objects.json for UUID translation
def load_objects(file_path):
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found!")
        return {}
        
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
            # Handle both direct list and nested objects format
            objects = data.get("objects", data) if isinstance(data, dict) else data
    except json.JSONDecodeError:
        print(f"Error: {file_path} is not a valid JSON file!")
        return {}
    except Exception as e:
        print(f"Error reading {file_path}: {str(e)}")
        return {}
    
    obj_dict = {}
    for obj in objects:
        obj_uid = obj.get("uid")
        if not obj_uid:  # Skip objects without UID
            continue
            
        obj_type = obj.get("type", "").lower()
        obj_name = obj.get("name", obj_uid)
        obj_comment = obj.get("comments", "")
        
        if obj_type == "host":
            obj_dict[obj_uid] = obj.get("ipv4-address", obj_name)
        elif obj_type == "network":
            subnet = obj.get('subnet4', '?')
            mask = obj.get('mask-length4', '?')
            obj_dict[obj_uid] = f"{subnet}/{mask}" if subnet != '?' else obj_name
        elif obj_type in ["service-tcp", "service-udp"]:
            port = obj.get('port', '')
            protocol = "TCP" if obj_type == "service-tcp" else "UDP"
            obj_dict[obj_uid] = f"{protocol} {port}" if port else obj_name
        elif obj_type == "service-icmp":
            icmp_type = obj.get('icmp-type', '?')
            obj_dict[obj_uid] = f"ICMP {icmp_type}" if icmp_type != '?' else obj_name
        elif obj_type == "service-other":
            protocol = obj.get('protocol', '?')
            obj_dict[obj_uid] = f"{protocol} ({obj_name})"
        elif obj_type in ["accept", "drop"]:
            obj_dict[obj_uid] = obj_type.upper()
        elif obj_type == "group":
            members = obj.get("members", [])
            resolved_members = []
            for m in members:
                member_value = obj_dict.get(m)  # Try to get already processed member
                if member_value:
                    resolved_members.append(member_value)
                else:
                    resolved_members.append(m)  # Keep original if not found
            obj_dict[obj_uid] = resolved_members if resolved_members else [obj_name]
        elif obj_type == "range":
            start = obj.get('range-start', '?')
            end = obj.get('range-end', '?')
            obj_dict[obj_uid] = f"{start}-{end}" if start != '?' else obj_name
        else:
            obj_dict[obj_uid] = obj_name if not obj_comment else f"{obj_name} ({obj_comment})"
    
    return obj_dict

# Translate UUIDs to actual names
def translate_uuid(uuid_list, obj_dict, detailed=False):
    if not uuid_list or uuid_list[0] == '':
        return '-'
        
    result = []
    for uuid in uuid_list:
        uuid = uuid.strip()
        obj_value = obj_dict.get(uuid, uuid)
        
        if isinstance(obj_value, list):
            # For groups, show name: members format
            group_name = uuid.split('_')[-1] if '_' in uuid else uuid
            members = [str(item) for item in obj_value]
            if detailed:
                result.append(f"{group_name}: {', '.join(members)}")
            else:
                result.append(group_name)
        else:
            # For single objects, show name: value format
            obj_name = uuid.split('_')[-1] if '_' in uuid else uuid
            if detailed and ':' not in str(obj_value):
                result.append(f"{obj_name}: {obj_value}")
            else:
                result.append(str(obj_value))
                
    return ", ".join(result) if result else "-"

# Load CSV rules
def load_rules(csv_path, obj_dict, detailed=False):
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found!")
        return []
        
    rules = []
    try:
        with open(csv_path, "r", encoding='utf-8-sig') as f:  # Handle BOM if present
            reader = csv.DictReader(f)
            for row in reader:
                # Clean up field names and values
                cleaned_row = {k.strip(): v.strip() for k, v in row.items() if k}
                
                # Ensure all required fields exist with default values
                rule = {
                    "Name": cleaned_row.get("Name", ""),
                    "Source": translate_uuid(cleaned_row.get("Source", "").split(";"), obj_dict, detailed),
                    "Destination": translate_uuid(cleaned_row.get("Destination", "").split(";"), obj_dict, detailed),
                    "Service": translate_uuid(cleaned_row.get("Service", "").split(";"), obj_dict, detailed),
                    "Action": obj_dict.get(cleaned_row.get("Action", ""), cleaned_row.get("Action", "").upper()),
                    "Comments": cleaned_row.get("Comments", "").replace(",", " ").replace("\n", " ")
                }
                rules.append(rule)
                
                # Debug output
                print(f"Processed rule: {rule['Name']}")
                print(f"  Source: {rule['Source']}")
                print(f"  Destination: {rule['Destination']}")
                print(f"  Service: {rule['Service']}")
                print(f"  Action: {rule['Action']}")
                
    except Exception as e:
        print(f"Error reading {csv_path}: {str(e)}")
        return []
        
    return rules

# HTML Template
html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Firewall Rules</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        tr:hover { background-color: #f5f5f5; }
        button { 
            padding: 10px 20px; 
            margin: 10px 0; 
            cursor: pointer;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
        }
        button:hover {
            background-color: #45a049;
        }
        .error { color: red; font-weight: bold; }
        .simple { display: table-cell; }
        .detailed { display: none; }
        .toggle-active .simple { display: none; }
        .toggle-active .detailed { display: table-cell; }
    </style>
    <script>
        function toggleDetails() {
            var table = document.querySelector('table');
            table.classList.toggle('toggle-active');
            var button = document.querySelector('button');
            button.textContent = table.classList.contains('toggle-active') ? 
                'Show Simple View' : 'Show Detailed View';
        }
    </script>
</head>
<body>
    <h2>Firewall Rules</h2>
    <button onclick="toggleDetails()">Show Detailed View</button>
    {% if rules %}
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
            <td>
                <span class="simple">{{ rule["Source"].split(':')[0] if ':' in rule["Source"] else rule["Source"] }}</span>
                <span class="detailed">{{ rule["Source"] }}</span>
            </td>
            <td>
                <span class="simple">{{ rule["Destination"].split(':')[0] if ':' in rule["Destination"] else rule["Destination"] }}</span>
                <span class="detailed">{{ rule["Destination"] }}</span>
            </td>
            <td>
                <span class="simple">{{ rule["Service"].split(':')[0] if ':' in rule["Service"] else rule["Service"] }}</span>
                <span class="detailed">{{ rule["Service"] }}</span>
            </td>
            <td>{{ rule["Comments"] }}</td>
        </tr>
        {% endfor %}
    </table>
    {% else %}
    <p class="error">No rules found or error loading rules data.</p>
    {% endif %}
</body>
</html>
"""

# Generate HTML
def generate_html(rules, output_path):
    try:
        template = Template(html_template)
        html_content = template.render(rules=rules)
        with open(output_path, "w") as f:
            f.write(html_content)
        print(f"Interactive report generated: {output_path}")
    except Exception as e:
        print(f"Error generating HTML: {str(e)}")

# Main function
def main():
    objects_file = "objects.json"
    rules_file = "rules.csv"
    output_html = "rules_interactive.html"
    
    if not os.path.exists(objects_file):
        print(f"Error: {objects_file} not found!")
        return
        
    if not os.path.exists(rules_file):
        print(f"Error: {rules_file} not found!")
        return
    
    obj_dict = load_objects(objects_file)
    if not obj_dict:
        print("Error: Failed to load objects dictionary!")
        return
        
    rules = load_rules(rules_file, obj_dict, detailed=False)
    if not rules:
        print("Error: Failed to load rules!")
        return
        
    generate_html(rules, output_html)

if __name__ == "__main__":
    main()
