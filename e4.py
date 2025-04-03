import json

def print_rules_simple(json_file_path):
    try:
        # Load the JSON file
        with open(json_file_path, 'r') as f:
            data = json.load(f)
        
        print("Processing rules...")
        print("=" * 50)
        
        # Function to extract rules recursively
        def extract_rules(data):
            rules = []
            
            if 'rulebase' in data:
                rulebase = data['rulebase']
                
                if isinstance(rulebase, list):
                    for entry in rulebase:
                        # If it's a direct rule
                        if 'rule-number' in entry:
                            rules.append(entry)
                        # If it has a nested rulebase
                        elif 'rulebase' in entry:
                            nested_rules = extract_rules(entry)
                            rules.extend(nested_rules)
            
            return rules
        
        # Get all rules
        all_rules = extract_rules(data)
        
        # Sort rules by rule number
        all_rules.sort(key=lambda x: int(x.get('rule-number', 0)))
        
        # Print rules in order
        for rule in all_rules:
            print(f"\nRule No: {rule.get('rule-number', 'N/A')}")
            print(f"Name: {rule.get('name', 'N/A')}")
            print(f"Source: {', '.join(rule.get('source', []))}")
            print(f"Destination: {', '.join(rule.get('destination', []))}")
            print(f"Action: {rule.get('action', 'N/A')}")
            print("-" * 50)
        
        print(f"\nTotal rules processed: {len(all_rules)}")
        
    except FileNotFoundError:
        print(f"Error: File {json_file_path} not found")
    except json.JSONDecodeError:
        print("Error: Invalid JSON format")
    except Exception as e:
        print(f"Error processing file: {str(e)}")

# Example usage:
if __name__ == "__main__":
    json_file_path = "your_rules_file.json"  # Replace with your file path
    print_rules_simple(json_file_path)
