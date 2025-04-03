def extract_and_print_rules(data, level=0):
    rules = []
    indent = "  " * level
    
    if 'rulebase' in data:
        rulebase = data['rulebase']
        
        if isinstance(rulebase, list):
            for entry in rulebase:
                # Check for direct rules
                if 'rule-number' in entry:
                    rule = {
                        'rule_number': entry.get('rule-number'),
                        'source': entry.get('source', []),
                        'destination': entry.get('destination', []),
                        'action': entry.get('action', ''),
                        'name': entry.get('name', '')
                    }
                    rules.append(rule)
                    print(f"\nRule No: {rule['rule_number']}")
                    print(f"Name: {rule['name']}")
                    print(f"Source: {', '.join(rule['source'])}")
                    print(f"Destination: {', '.join(rule['destination'])}")
                    print(f"Action: {rule['action']}")
                    print("-" * 50)  # Separator line
                
                # Check for nested rulebases
                elif 'rulebase' in entry:
                    print(f"{indent}Processing section: {entry.get('name', 'Unnamed Section')}")
                    nested_rules = extract_and_print_rules(entry, level + 1)
                    rules.extend(nested_rules)
    
    return rules

# Example usage:
def process_checkpoint_file(json_file_path):
    try:
        with open(json_file_path, 'r') as f:
            full_data = json.load(f)
            
        print("Starting to process rules...")
        print("=" * 50)  # Header separator
        
        all_rules = extract_and_print_rules(full_data)
        
        print("\nSummary:")
        print(f"Total rules processed: {len(all_rules)}")
        
    except FileNotFoundError:
        print(f"Error: File {json_file_path} not found")
    except json.JSONDecodeError:
        print("Error: Invalid JSON format")
    except Exception as e:
        print(f"Error processing file: {str(e)}")

# To use it:
process_checkpoint_file('your_checkpoint_file.json')
