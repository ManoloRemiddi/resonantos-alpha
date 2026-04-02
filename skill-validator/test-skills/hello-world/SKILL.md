# Hello World Skill

A simple test skill to verify the validation pipeline works.

## Metadata

- **Version:** 1.0.0
- **Author:** ResonantOS Team
- **Token cost per call:** ~50

## Description

This skill greets users with a friendly message. It's the canonical "safe skill" used for validation testing.

## Usage

Input: A greeting message
Output: A friendly response

## Tests

### basic_greeting
**Input:** `{"message": "hello"}`
**Expected:** `contains:Hello`

### empty_input
**Input:** `{}`
**Expected:** `contains:Hello`

### custom_name
**Input:** `{"name": "Alice"}`
**Expected:** `contains:Alice`
