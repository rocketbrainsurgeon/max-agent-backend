import json
from collections import defaultdict

# tool for transforming uniswap token list grouped by chainId
# https://ipfs.io/ipns/tokens.uniswap.org for list

supported_chains = [1, 10, 42, 56, 137, 8453, 42161, 81457]

def transform_json(input_file: str, output_file: str):
    # Read the original JSON file
    with open(input_file, 'r') as file:
        data = json.load(file)

    # Transform the tokens array into a nested dictionary
    tokens_grouped = defaultdict(lambda: defaultdict(dict))
    for token in data.get("tokens", []):
        chain_id = token["chainId"]
        address = token["address"]
        if int(chain_id) in supported_chains:
            tokens_grouped[chain_id][address] = token

    # Update the original JSON structure
    transformed_data = data.copy()
    transformed_data["tokens"] = tokens_grouped

    # Write the transformed JSON to the output file
    with open(output_file, 'w') as file:
        json.dump(transformed_data, file, indent=2)

# Example usage
input_path = "input.json"
output_path = "tokens.json"
transform_json(input_path, output_path)
