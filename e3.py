import csv
import json
import os
import subprocess
import paramiko
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
        obj_type = obj.get("type", "").lower()
        
        # Skip groups and service-groups for second pass
        if not obj_uid or obj_type in ["group", "service-group"]:
            continue
            
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
        elif obj_type == "rulebaseaction":
            # Handle RulebaseAction type - use the name as is for the action
            obj_dict[obj_uid] = {"type": "action", "name": obj_name, "value": obj_name}
        elif obj_type == "range":
            start = obj.get('range-start', '?')
            end = obj.get('range-end', '?')
            obj_dict[obj_uid] = {"type": "range", "name": obj_name, "value": f"{start}-{end}" if start != '?' else obj_name}
        else:
            obj_dict[obj_uid] = {"type": "other", "name": obj_name, "value": obj_name if not obj_comment else f"{obj_name} ({obj_comment})"}
    
    def resolve_group_members(group_obj, processed=None, is_service_group=False):
        """Recursively resolve group members, handling nested groups"""
        if processed is None:
            processed = set()
            
        group_uid = group_obj.get("uid")
        if group_uid in processed:
            return []  # Avoid circular references
            
        processed.add(group_uid)
        members = group_obj.get("members", [])
        resolved_members = []
        
        # Valid member types for each group type
        valid_network_types = ["host", "network", "range", "group"]
        valid_service_types = ["service-tcp", "service-udp", "service-icmp", "service-other", "service-group"]
        
        for member_uid in members:
            # Find the member object in the original objects list
            member_obj = next((obj for obj in objects if obj.get("uid") == member_uid), None)
            if not member_obj:
                # Add unresolved member to the list with special handling
                resolved_members.append({
                    "type": "unresolved",
                    "name": member_uid,
                    "value": member_uid,
                    "uid": member_uid
                })
                continue
                
            member_obj_type = member_obj.get("type", "").lower()
            
            # Check if member type is valid for the group type
            if is_service_group and member_obj_type not in valid_service_types:
                print(f"Warning: Invalid member type '{member_obj_type}' in service-group '{group_obj.get('name')}'")
                continue
            elif not is_service_group and member_obj_type not in valid_network_types:
                print(f"Warning: Invalid member type '{member_obj_type}' in network group '{group_obj.get('name')}'")
                continue
            
            if member_obj_type in ["group", "service-group"]:
                # Recursively resolve nested group
                nested_members = resolve_group_members(
                    member_obj, 
                    processed,
                    is_service_group=(member_obj_type == "service-group")
                )
                if nested_members:
                    resolved_members.extend(nested_members)
            else:
                # Get the already processed member from obj_dict
                member = obj_dict.get(member_uid)
                if member:
                    resolved_members.append(member)
                else:
                    # Add unresolved member to the list with special handling
                    resolved_members.append({
                        "type": "unresolved",
                        "name": member_uid,
                        "value": member_uid,
                        "uid": member_uid
                    })
        
        return resolved_members
    
    # Second pass: Process groups and service-groups with recursive resolution
    for obj in objects:
        obj_type = obj.get("type", "").lower()
        if obj_type not in ["group", "service-group"]:
            continue
            
        obj_uid = obj.get("uid")
        if obj_uid in processed_groups:
            continue
            
        obj_name = obj.get("name", obj_uid)
        is_service_group = (obj_type == "service-group")
        resolved_members = resolve_group_members(obj, is_service_group=is_service_group)
        
        # Format members for display
        formatted_members = []
        for member in resolved_members:
            member_data = {
                "name": member["name"],
                "value": member["value"]
            }
            # Preserve the unresolved type and uid for display
            if member.get("type") == "unresolved":
                member_data["type"] = "unresolved"
                member_data["uid"] = member["uid"]
            formatted_members.append(member_data)
        
        obj_dict[obj_uid] = {
            "type": "group",
            "member_type": "service" if is_service_group else "network",
            "name": obj_name,
            "members": formatted_members,
            "is_service_group": is_service_group  # Add this flag to distinguish group types
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
            # Extract last 4 characters of the UID, or use the entire UID if it's shorter
            uid_suffix = uuid[-4:] if len(uuid) >= 4 else uuid
            if detailed:
                result.append(f'<div><span class="untranslated-uid" title="Full UID: {uuid}">(unresolved) {uuid}</span></div>')
            else:
                result.append(f'<span class="untranslated-uid" title="Full UID: {uuid}">(unresolved) {uuid}</span>')
            continue
            
        if obj["type"] == "group":
            group_name = obj["name"]
            if detailed:
                members_html = []
                for member in obj["members"]:
                    if member.get("type") == "unresolved":
                        # Handle unresolved members in groups
                        uid = member.get("uid", member.get("value"))
                        members_html.append(f'<div class="indent"><span class="untranslated-uid" title="Full UID: {uid}">(unresolved) {uid}</span></div>')
                    elif obj["member_type"] == "service":
                        members_html.append(f'<div class="indent"><span class="service-value">{member["value"]}</span></div>')
                    elif obj["member_type"] in ["host", "network"]:
                        members_html.append(f'<div class="indent"><span class="ip-value">{member["value"]}</span></div>')
                    else:
                        members_html.append(f'<div class="indent"><span class="obj-value">{member["value"]}</span></div>')
                result.append(f'<div><span class="group-name">{group_name}</span></div>{"".join(members_html)}')
            else:
                result.append(f'<span class="group-name">{group_name}</span>')
        else:
            if detailed:
                if obj["type"] == "service":
                    result.append(f'<div><span class="service-name">{obj["name"]}</span></div><div class="indent"><span class="service-value">{obj["value"]}</span></div>')
                elif obj["type"] in ["host", "network"]:
                    result.append(f'<div><span class="ip-name">{obj["name"]}</span></div><div class="indent"><span class="ip-value">{obj["value"]}</span></div>')
                else:
                    result.append(f'<div><span class="obj-name">{obj["name"]}</span></div><div class="indent"><span class="obj-value">{obj["value"]}</span></div>')
            else:
                result.append(f'<span class="obj-name">{obj["name"]}</span>')
                
    if not result:
        return "-"
    elif detailed:
        return "<div class='cell-content'>" + "".join(result) + "</div>"
    else:
        return "<div class='cell-content'>" + ", ".join(result) + "</div>"

# Load CSV rules
def load_rules(csv_path, obj_dict):
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found!")
        return []
        
    rules = []
    try:
        with open(csv_path, "r", encoding='utf-8-sig') as f:  # Handle BOM if present
            # First read the raw CSV to get the first column name
            first_line = f.readline().strip()
            f.seek(0)  # Go back to start of file
            
            reader = csv.DictReader(f)
            field_names = reader.fieldnames
            rule_no_field = field_names[0] if field_names else "RuleNo"  # Get the first column name
            
            for row in reader:
                # Clean up field names and values
                cleaned_row = {k.strip(): v.strip() for k, v in row.items() if k}
                
                # Get both simple and detailed versions
                source_simple = translate_uuid(cleaned_row.get("Source", "").split(";"), obj_dict, detailed=False)
                source_detailed = translate_uuid(cleaned_row.get("Source", "").split(";"), obj_dict, detailed=True)
                dest_simple = translate_uuid(cleaned_row.get("Destination", "").split(";"), obj_dict, detailed=False)
                dest_detailed = translate_uuid(cleaned_row.get("Destination", "").split(";"), obj_dict, detailed=True)
                service_simple = translate_uuid(cleaned_row.get("Service", "").split(";"), obj_dict, detailed=False)
                service_detailed = translate_uuid(cleaned_row.get("Service", "").split(";"), obj_dict, detailed=True)
                
                # Get action from obj_dict if it exists, otherwise use the raw value
                action = cleaned_row.get("Action", "")
                if action in obj_dict:
                    action = obj_dict[action]["name"]
                
                # Get rule number directly from the first column
                rule_no = cleaned_row.get(rule_no_field, "").strip()
                
                # Ensure all required fields exist with both simple and detailed values
                rule = {
                    "RuleNo": rule_no,
                    "Name": cleaned_row.get("Name", ""),
                    "Source_simple": source_simple,
                    "Source_detailed": source_detailed,
                    "Destination_simple": dest_simple,
                    "Destination_detailed": dest_detailed,
                    "Service_simple": service_simple,
                    "Service_detailed": service_detailed,
                    "Action": action.upper() if action else "",
                    "Comments": cleaned_row.get("Comments", "").replace(",", " ").replace("\n", " ")
                }
                rules.append(rule)
                
                # Debug output
                print(f"Processed rule {rule_no}: {rule['Name']}")
                print(f"  Source (simple): {rule['Source_simple']}")
                print(f"  Source (detailed): {rule['Source_detailed']}")
                print(f"  Destination (simple): {rule['Destination_simple']}")
                print(f"  Destination (detailed): {rule['Destination_detailed']}")
                print(f"  Service (simple): {rule['Service_simple']}")
                print(f"  Service (detailed): {rule['Service_detailed']}")
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
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; }
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
        
        /* Toggle visibility */
        .simple { display: block; }
        .detailed { display: none; }
        .toggle-active .simple { display: none !important; }
        .toggle-active .detailed { display: block !important; }

        /* Cell content styling */
        .cell-content { width: 100%; }
        .cell-content > div { margin-bottom: 4px; }
        .indent { padding-left: 20px; margin: 2px 0; }

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
        .action { font-weight: bold; }
        .action[data-action="ACCEPT"] { color: #4CAF50; }
        .action[data-action="DROP"] { color: #F44336; }
        .action[data-action="REJECT"] { color: #FF9800; }

        /* Rule number styling */
        .rule-no {
            font-weight: bold;
            color: #333;
            font-family: monospace;
        }

        /* Untranslated UID styling */
        .untranslated-uid {
            color: #ff0000;
            background-color: #fff3f3;
            padding: 2px 6px;
            border-radius: 3px;
            border: 1px solid #ffcdd2;
            font-style: italic;
            cursor: help;
        }
    </style>
</head>
<body>
    <h2>Firewall Rules</h2>
    <button onclick="toggleView()">Show Detailed View</button>
    {% if rules %}
    <table id="rulesTable">
        <tr>
            <th>Rule No</th>
            <th>Rule Name</th>
            <th>Action</th>
            <th>Source</th>
            <th>Destination</th>
            <th>Service</th>
            <th>Comments</th>
        </tr>
        {% for rule in rules %}
        <tr>
            <td><span class="rule-no">{{ rule["RuleNo"] }}</span></td>
            <td>{{ rule["Name"] }}</td>
            <td><span class="action" data-action="{{ rule['Action'] }}">{{ rule["Action"] }}</span></td>
            <td>
                <span class="simple">{{ rule["Source_simple"]|safe }}</span>
                <span class="detailed">{{ rule["Source_detailed"]|safe }}</span>
            </td>
            <td>
                <span class="simple">{{ rule["Destination_simple"]|safe }}</span>
                <span class="detailed">{{ rule["Destination_detailed"]|safe }}</span>
            </td>
            <td>
                <span class="simple">{{ rule["Service_simple"]|safe }}</span>
                <span class="detailed">{{ rule["Service_detailed"]|safe }}</span>
            </td>
            <td>{{ rule["Comments"] }}</td>
        </tr>
        {% endfor %}
    </table>
    {% else %}
    <p class="error">No rules found or error loading rules data.</p>
    {% endif %}

    <script>
        function toggleView() {
            const table = document.getElementById('rulesTable');
            const button = document.querySelector('button');
            
            if (table.classList.contains('toggle-active')) {
                table.classList.remove('toggle-active');
                button.textContent = 'Show Detailed View';
            } else {
                table.classList.add('toggle-active');
                button.textContent = 'Show Simple View';
            }
        }
    </script>
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

def connect_to_manager(mgmt_ip, username, password):
    """Establish SSH connection to Check Point manager"""
    try:
        # Initialize SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        print(f"Establishing SSH connection to {mgmt_ip}...")
        # Add timeout parameters
        ssh.connect(
            mgmt_ip,
            username=username,
            password=password,
            timeout=30,  # Connection timeout
            banner_timeout=30,  # Banner timeout
            auth_timeout=30  # Authentication timeout
        )
        return ssh
    except Exception as e:
        print(f"SSH connection failed: {str(e)}")
        return None

def login_to_manager(ssh):
    """Login to Check Point manager via mgmt_cli and return session ID"""
    try:
        # Execute mgmt_cli login with timeout
        stdin, stdout, stderr = ssh.exec_command('mgmt_cli login --format json', timeout=30)
        
        # Read output with timeout
        response = stdout.read().decode()
        error = stderr.read().decode()
        
        if error:
            print(f"Login failed: {error}")
            return None
            
        # Parse response to get sid
        session_data = json.loads(response)
        sid = session_data.get('sid')
        if not sid:
            print("No session ID received")
            return None
            
        print("Successfully logged in to manager")
        return sid
    except Exception as e:
        print(f"Error during login: {str(e)}")
        return None

def logout_from_manager(ssh, sid):
    """Logout from Check Point manager"""
    try:
        ssh.exec_command(f'mgmt_cli logout -s {sid}')
    except Exception as e:
        print(f"Error during logout: {str(e)}")

def extract_policy_data(ssh, policy_name, sid):
    """Extract policy data from Check Point manager in batches"""
    try:
        os.makedirs('temp', exist_ok=True)
        batch_size = 20
        
        # Get first batch of rules to determine total count
        print("Fetching first batch of rules to determine total count...")
        cmd = f'mgmt_cli show access-rulebase name "{policy_name}" limit {batch_size} offset 0 -s {sid} --format json'
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)  # Increased timeout for data fetch
        
        response = stdout.read().decode()
        error = stderr.read().decode()
        
        if error:
            print(f"Error fetching rules: {error}")
            return None, None
            
        first_batch = json.loads(response)
        total_rules = first_batch.get('total', 0)
        all_rules = first_batch.get('rulebase', [])
        
        # Calculate required iterations for rules
        required_iterations = (total_rules + batch_size - 1) // batch_size
        print(f"Total rules: {total_rules}, Required iterations: {required_iterations}")
        
        # Fetch remaining rule batches
        for iteration in range(1, required_iterations):
            offset = iteration * batch_size
            print(f"Fetching rules batch {iteration + 1}/{required_iterations} (offset: {offset})")
            
            cmd = f'mgmt_cli show access-rulebase name "{policy_name}" limit {batch_size} offset {offset} -s {sid} --format json'
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
            
            response = stdout.read().decode()
            error = stderr.read().decode()
            
            if error:
                print(f"Error fetching rules batch {iteration + 1}: {error}")
                continue
                
            batch_data = json.loads(response)
            batch_rules = batch_data.get('rulebase', [])
            all_rules.extend(batch_rules)
        
        # Convert combined rules to CSV
        print(f"Converting {len(all_rules)} rules to CSV...")
        rules_csv_path = 'temp/rules.csv'
        with open(rules_csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['RuleNo', 'Name', 'Source', 'Destination', 'Service', 'Action', 'Comments'])
            
            for idx, rule in enumerate(all_rules, 1):
                sources = ';'.join([src.get('uid', '') for src in rule.get('source', [])])
                destinations = ';'.join([dst.get('uid', '') for dst in rule.get('destination', [])])
                services = ';'.join([svc.get('uid', '') for svc in rule.get('service', [])])
                
                writer.writerow([
                    str(idx),
                    rule.get('name', ''),
                    sources,
                    destinations,
                    services,
                    rule.get('action', {}).get('uid', ''),
                    rule.get('comments', '')
                ])
        
        # Get first batch of objects to determine total count
        print("\nFetching first batch of objects to determine total count...")
        cmd = f'mgmt_cli show-objects limit {batch_size} offset 0 -s {sid} --format json'
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
        
        response = stdout.read().decode()
        error = stderr.read().decode()
        
        if error:
            print(f"Error fetching objects: {error}")
            return None, None
            
        first_batch = json.loads(response)
        total_objects = first_batch.get('total', 0)
        all_objects = first_batch.get('objects', [])
        
        # Calculate required iterations for objects
        required_iterations = (total_objects + batch_size - 1) // batch_size
        print(f"Total objects: {total_objects}, Required iterations: {required_iterations}")
        
        # Fetch remaining object batches
        for iteration in range(1, required_iterations):
            offset = iteration * batch_size
            print(f"Fetching objects batch {iteration + 1}/{required_iterations} (offset: {offset})")
            
            cmd = f'mgmt_cli show-objects limit {batch_size} offset {offset} -s {sid} --format json'
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
            
            response = stdout.read().decode()
            error = stderr.read().decode()
            
            if error:
                print(f"Error fetching objects batch {iteration + 1}: {error}")
                continue
                
            batch_data = json.loads(response)
            batch_objects = batch_data.get('objects', [])
            all_objects.extend(batch_objects)
        
        # Save combined objects to JSON
        print(f"Saving {len(all_objects)} objects to JSON...")
        objects_json_path = 'temp/objects.json'
        with open(objects_json_path, 'w') as f:
            json.dump({'objects': all_objects}, f, indent=2)
            
        return rules_csv_path, objects_json_path
        
    except Exception as e:
        print(f"Error extracting policy data: {str(e)}")
        return None, None

def main():
    # Get input from user
    mgmt_ip = input("Enter Check Point manager IP: ")
    username = input("Enter username: ")
    password = input("Enter password: ")
    policy_name = input("Enter policy name: ")
    
    # Establish SSH connection
    ssh = connect_to_manager(mgmt_ip, username, password)
    if not ssh:
        print("Failed to establish SSH connection. Exiting...")
        return
        
    try:
        # Login to manager
        print("Logging in to Check Point manager...")
        sid = login_to_manager(ssh)
        if not sid:
            print("Failed to login. Exiting...")
            return
            
        # Extract policy data
        rules_csv, objects_json = extract_policy_data(ssh, policy_name, sid)
        if not rules_csv or not objects_json:
            print("Failed to extract policy data. Exiting...")
            return
            
        # Process the data using existing code
        obj_dict = load_objects(objects_json)
        if not obj_dict:
            print("Error: Failed to load objects dictionary!")
            return
            
        rules = load_rules(rules_csv, obj_dict)
        if not rules:
            print("Error: Failed to load rules!")
            return
            
        # Generate HTML report
        output_html = f"rules_{policy_name.replace(' ', '_')}.html"
        generate_html(rules, output_html)
        
    finally:
        # Cleanup
        if sid:
            print("Logging out from Check Point manager...")
            logout_from_manager(ssh, sid)
        
        if ssh:
            ssh.close()
            print("Closed SSH connection")
            
        # Remove temporary files
        if os.path.exists('temp'):
            import shutil
            shutil.rmtree('temp')

if __name__ == "__main__":
    main()
