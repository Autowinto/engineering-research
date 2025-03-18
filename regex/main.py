import json
import re

def load_json(file_path):
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: The file at {file_path} was not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error: The file at {file_path} is not a valid JSON.")
        return None

def classify(data):
  pass
  

def main():
  file_path = input("Enter JSON file path: ")

  data = load_json(file_path)

  if data is None:
    print("Invalid JSON file")
    return

  if (isinstance(data, dict)):  
    for commit in data['commits']:
      classify(commit)
main()