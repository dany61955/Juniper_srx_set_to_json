import re
import json

def set_to_json(input_file, output_file):
    # Regular expressions to match set, delete, and hierarchical set lines
    set_pattern = r'^set (\S+ (.+))$'
    delete_pattern = r'^delete (\S+ (.+))$'
    hierarchy_pattern = r'^set (\S+)$'

    # Initialize an empty configuration dictionary
    config = {}

    with open(input_file, 'r') as file:
        current_node = config
        for line in file:
            line = line.strip()
            
            # Match a set statement
            set_match = re.match(set_pattern, line)
            if set_match:
                path, value = set_match.groups()
                parts = path.split()
                for part in parts:
                    current_node = current_node.setdefault(part, {})
                current_node = value

            # Match a delete statement
            delete_match = re.match(delete_pattern, line)
            if delete_match:
                path, value = delete_match.groups()
                parts = path.split()
                current_node = config
                for part in parts:
                    current_node = current_node.setdefault(part, {})
                if value in current_node:
                    del current_node[value]

            # Match a hierarchical set statement
            hierarchy_match = re.match(hierarchy_pattern, line)
            if hierarchy_match:
                path = hierarchy_match.group(1)
                parts = path.split()
                for part in parts:
                    current_node = current_node.setdefault(part, {})

    # Write the JSON to the output file
    with open(output_file, 'w') as outfile:
        json.dump(config, outfile, indent=4)

if __name__ == '__main__':
    input_file = 'input.set'  # Replace with the path to your input set file
    output_file = 'output.json'  # Replace with the desired output JSON file

    set_to_json(input_file, output_file)
