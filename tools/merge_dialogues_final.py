# merge_dialogues.py
import json
import os
import shutil
from pathlib import Path

def deep_merge(d1, d2):
    merged = d1.copy()
    for key, value in d2.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged

def main():
    # Get the current working directory and data directory
    workspace_dir = Path.cwd()
    data_dir = workspace_dir / 'data'
    
    # Define file paths
    dialogues_path = data_dir / 'dialogues.json'
    dialogues_fixed_path = data_dir / 'dialogues_fixed.json'
    output_path = data_dir / 'dialogues_final.json'
    
    try:
        # Read and parse JSON files
        with open(dialogues_path, 'r', encoding='utf-8') as f:
            dialogues = json.load(f)
            
        with open(dialogues_fixed_path, 'r', encoding='utf-8') as f:
            dialogues_fixed = json.load(f)
            
        # Merge the dialogues
        merged_dialogues = deep_merge(dialogues, dialogues_fixed)
        
        # Save the result
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(merged_dialogues, f, indent=4, ensure_ascii=False)
            
        print("Successfully merged dialogues into dialogues_final.json")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == '__main__':
    main()