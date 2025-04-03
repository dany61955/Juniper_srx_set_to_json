import json

def extract_rules_to_json(input_file, output_file):
    try:
        # Load the input JSON file
        with open(input_file, 'r') as f:
            data = json.load(f)
        
        # Function to extract rules recursively
        def extract_rules(data):
            rules = []
            
            if 'rulebase' in data:
                rulebase = data['rulebase']
                
                if isinstance(rulebase, list):
                    for section in rulebase:
                        # Check if it's an access section
                        if section.get('type') == 'access-section':
                            if 'rulebase' in section:
                                for rule in section['rulebase']:
                                    if 'rule-number' in rule:
                                        # Create a clean rule object with only the necessary fields
                                        clean_rule = {
                                            'rule-number': rule.get('rule-number'),
                                            'source': rule.get('source', []),
                                            'destination': rule.get('destination', []),
                                            'action': rule.get('action', ''),
                                            'name': rule.get('name', '')
                                        }
                                        rules.append(clean_rule)
            
            return rules
        
        # Get all rules
        all_rules = extract_rules(data)
        
        # Sort rules by rule number
        all_rules.sort(key=lambda x: int(x.get('rule-number', 0)))
        
        # Write rules to output JSON file
        with open(output_file, 'w') as f:
            json.dump(all_rules, f, indent=2)
        
        print(f"Successfully extracted {len(all_rules)} rules to {output_file}")
        
    except FileNotFoundError:
        print(f"Error: File {input_file} not found")
    except json.JSONDecodeError:
        print("Error: Invalid JSON format")
    except Exception as e:
        print(f"Error processing file: {str(e)}")

# Example usage:
if __name__ == "__main__":
    input_file = "your_input_file.json"  # Replace with your input file path
    output_file = "rules_output.json"    # Replace with your desired output file path
    extract_rules_to_json(input_file, output_file)
