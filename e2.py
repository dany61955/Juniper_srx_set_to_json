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
    processed_groups = set()  # Track processed groups to avoid circular references
    
    # First pass: Load all non-group objects
    for obj in objects:
        obj_uid = obj.get("uid")
        if not obj_uid or obj.get("type", "").lower() == "group":
            continue
            
        obj_type = obj.get("type", "").lower()
        obj_name = obj.get("name", obj_uid)
        obj_comment = obj.get("comments", "")
        
        if obj_type == "host":
            obj_dict[obj_uid] = {"type": "host", "name": obj_name, "value": obj.get("ipv4-address", obj_name)}
        elif obj_type == "network":
            subnet = obj.get('subnet4', '?')
            mask = obj.get('mask-length4', '?')
            obj_dict[obj_uid] = {"type": "network", "name": obj_name, "value": f"{subnet}/{mask}" if subnet != '?' else obj_name}
        elif obj_type in ["service-tcp", "service-udp"]:
            port = obj.get('port', '')
            protocol = "TCP" if obj_type == "service-tcp" else "UDP"
            obj_dict[obj_uid] = {"type": "service", "name": obj_name, "value": f"{protocol} {port}" if port else obj_name}
        elif obj_type == "service-icmp":
            icmp_type = obj.get('icmp-type', '?')
            obj_dict[obj_uid] = {"type": "service", "name": obj_name, "value": f"ICMP {icmp_type}" if icmp_type != '?' else obj_name}
        elif obj_type == "service-other":
            protocol = obj.get('protocol', '?')
            obj_dict[obj_uid] = {"type": "service", "name": obj_name, "value": f"{protocol} ({obj_name})"}
        elif obj_type in ["accept", "drop"]:
            obj_dict[obj_uid] = {"type": "action", "name": obj_name, "value": obj_type.upper()}
        elif obj_type == "range":
            start = obj.get('range-start', '?')
            end = obj.get('range-end', '?')
            obj_dict[obj_uid] = {"type": "range", "name": obj_name, "value": f"{start}-{end}" if start != '?' else obj_name}
        else:
            obj_dict[obj_uid] = {"type": "other", "name": obj_name, "value": obj_name if not obj_comment else f"{obj_name} ({obj_comment})"}
    
    def resolve_group_members(group_obj, processed=None):
        """Recursively resolve group members, handling nested groups"""
        if processed is None:
            processed = set()
            
        group_uid = group_obj.get("uid")
        if group_uid in processed:
            return []  # Avoid circular references
            
        processed.add(group_uid)
        members = group_obj.get("members", [])
        resolved_members = []
        member_type = None
        
        for member_uid in members:
            # Find the member object in the original objects list
            member_obj = next((obj for obj in objects if obj.get("uid") == member_uid), None)
            if not member_obj:
                continue
                
            if member_obj.get("type", "").lower() == "group":
                # Recursively resolve nested group
                nested_members = resolve_group_members(member_obj, processed)
                if nested_members:
                    member_type = member_type or nested_members[0].get("type")
                    resolved_members.extend(nested_members)
            else:
                # Get the already processed member from obj_dict
                member = obj_dict.get(member_uid)
                if member:
                    member_type = member_type or member["type"]
                    resolved_members.append(member)
        
        return resolved_members
    
    # Second pass: Process groups with recursive resolution
    for obj in objects:
        if obj.get("type", "").lower() == "group":
            obj_uid = obj.get("uid")
            if obj_uid in processed_groups:
                continue
                
            obj_name = obj.get("name", obj_uid)
            resolved_members = resolve_group_members(obj)
            
            # Determine group type from members
            member_type = resolved_members[0]["type"] if resolved_members else "other"
            
            # Format members for display
            formatted_members = []
            for member in resolved_members:
                formatted_members.append({
                    "name": member["name"],
                    "value": member["value"]
                })
            
            obj_dict[obj_uid] = {
                "type": "group",
                "member_type": member_type,
                "name": obj_name,
                "members": formatted_members
            }
            processed_groups.add(obj_uid)
    
    return obj_dict

# Translate UUIDs to actual names
def translate_uuid(uuid_list, obj_dict, detailed=False):
    if not uuid_list or uuid_list[0] == '':
        return '-'
        
    result = []
    for uuid in uuid_list:
        uuid = uuid.strip()
        obj = obj_dict.get(uuid)
        
        if not obj:
            result.append(f'<span class="obj-name">{uuid}</span>')
            continue
            
        if obj["type"] == "group":
            group_name = obj["name"]
            if detailed:
                members_html = []
                for member in obj["members"]:
                    if obj["member_type"] == "service":
                        members_html.append(f'<span class="service-value">{member["value"]}</span>')
                    elif obj["member_type"] in ["host", "network"]:
                        members_html.append(f'<span class="ip-value">{member["value"]}</span>')
                    else:
                        members_html.append(f'<span class="obj-value">{member["value"]}</span>')
                result.append(f'<span class="group-name">{group_name}</span>: <span class="group-members">{", ".join(members_html)}</span>')
            else:
                result.append(f'<span class="group-name">{group_name}</span>')
        else:
            if detailed:
                if obj["type"] == "service":
                    result.append(f'<span class="service-name">{obj["name"]}</span>: <span class="service-value">{obj["value"]}</span>')
                elif obj["type"] in ["host", "network"]:
                    result.append(f'<span class="ip-name">{obj["name"]}</span>: <span class="ip-value">{obj["value"]}</span>')
                else:
                    result.append(f'<span class="obj-name">{obj["name"]}</span>: <span class="obj-value">{obj["value"]}</span>')
            else:
                result.append(f'<span class="obj-name">{obj["name"]}</span>')
                
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
        th { background-color: #f2f2f2; font-weight: bold; }
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

        /* Object type styling */
        .group-name { color: #2196F3; font-weight: bold; }
        .group-members { color: #666; font-style: italic; }
        .service-name { color: #4CAF50; font-weight: bold; }
        .service-value { color: #388E3C; }
        .ip-name { color: #F44336; font-weight: bold; }
        .ip-value { color: #D32F2F; }
        .obj-name { color: #9C27B0; font-weight: bold; }
        .obj-value { color: #7B1FA2; }
        
        /* Action column styling */
        .action-accept { color: #4CAF50; font-weight: bold; }
        .action-drop { color: #F44336; font-weight: bold; }
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
            <td class="action-{{ rule['Action']|lower }}">{{ rule["Action"] }}</td>
            <td>
                <span class="simple">{{ rule["Source"]|safe }}</span>
                <span class="detailed">{{ rule["Source"]|safe }}</span>
            </td>
            <td>
                <span class="simple">{{ rule["Destination"]|safe }}</span>
                <span class="detailed">{{ rule["Destination"]|safe }}</span>
            </td>
            <td>
                <span class="simple">{{ rule["Service"]|safe }}</span>
                <span class="detailed">{{ rule["Service"]|safe }}</span>
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
