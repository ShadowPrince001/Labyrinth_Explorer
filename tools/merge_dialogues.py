import json
import os
import shutil

def merge_dialogues():
    data_dir = r"c:\Users\Maheeyan Saha\Downloads\DnD\data"
    
    # Backup existing files
    shutil.copy(os.path.join(data_dir, "dialogues.json"), os.path.join(data_dir, "dialogues_backup.json"))
    shutil.copy(os.path.join(data_dir, "dialogues_fixed.json"), os.path.join(data_dir, "dialogues_fixed_backup.json"))
    
    # Load and merge dialogues
    with open(os.path.join(data_dir, "dialogues.json"), "r") as f:
        dialogues = json.load(f)
    with open(os.path.join(data_dir, "dialogues_fixed.json"), "r") as f:
        dialogues_fixed = json.load(f)
        
    # Deep merge the two dictionaries
    def deep_merge(d1, d2):
        merged = d1.copy()
        for key, value in d2.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged
        
    merged_dialogues = deep_merge(dialogues, dialogues_fixed)
    
    # Save the merged result
    with open(os.path.join(data_dir, "dialogues_final.json"), "w") as f:
        json.dump(merged_dialogues, f, indent=4)

if __name__ == "__main__":
    merge_dialogues()
    print("Dialogues successfully merged into dialogues_final.json")