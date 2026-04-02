#!/usr/bin/env python3
"""
Hello World Skill - Safe test skill for validation pipeline.
"""

import os
import json
import sys

def main():
    # Get input from environment
    input_str = os.environ.get('SKILL_TEST_INPUT', '{}')
    
    try:
        input_data = json.loads(input_str)
    except json.JSONDecodeError:
        input_data = {}
    
    # Generate greeting
    name = input_data.get('name', 'World')
    message = input_data.get('message', '')
    
    if name != 'World':
        response = f"Hello, {name}! Nice to meet you."
    elif message:
        response = f"Hello! You said: {message}"
    else:
        response = "Hello! How can I help you today?"
    
    print(response)

if __name__ == "__main__":
    main()
