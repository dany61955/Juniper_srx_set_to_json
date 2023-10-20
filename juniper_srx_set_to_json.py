import re
import json

def set_to_json(input_file, output_file):
    def add_to_dict(d, path, value):
        if len(path) == 1:
            d[path[0]] = value
        else:
            key = path[0]
            if key not in d:
                d[key] = {}
            add_to_dict(d[key], path[1:], value)

    config = {}
    current_path = []

    with open(input_file, 'r') as file:
        for line in file:
            line = line.strip()
            if line.startswith("set "):
                set_match = re.match(r'set (.+)', line)
                if set_match:
                    path = set_match.group(1).split()
                    current_path = path
                else:
                    add_to_dict(config, current_path, line)
            elif line.startswith("delete "):
                delete_match = re.match(r'delete (.+)', line)
                if delete_match:
                    path = delete_match.group(1).split()
                    if path:
                        key = path[-1]
                        if key in config:
                            del config[path[0]]
            else:
                current_path = []

    # Write the JSON to the output file
    with open(output_file, 'w') as outfile:
        json.dump(config, outfile, indent=4)

if __name__ == '__main__':
    input_file = 'input.set'  # Replace with the path to your input set file
    output_file = 'output.json'  # Replace with the desired output JSON file

    set_to_json(input_file, output_file)
