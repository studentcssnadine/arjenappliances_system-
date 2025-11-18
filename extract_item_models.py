#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from myapp.models import CustomerHistory

def extract_item_model(item_name):
    """Extract model from item name"""
    if not item_name:
        return "Unknown Model"
    
    # Common patterns for extracting model
    item_name = item_name.strip()
    
    # Look for model patterns (usually at the end)
    # Examples: "SDT-7586", "012-A", "ASTRN_09", etc.
    import re
    
    # Pattern 1: Alphanumeric with dashes/underscores (SDT-7586, ASTRN_09)
    model_pattern1 = re.search(r'([A-Z0-9_-]+(?:\d+[A-Z]*|[A-Z]+\d+))\s*$', item_name)
    if model_pattern1:
        return model_pattern1.group(1)
    
    # Pattern 2: Numbers with letters (012-A)
    model_pattern2 = re.search(r'(\d+-[A-Z]+)\s*$', item_name)
    if model_pattern2:
        return model_pattern2.group(1)
    
    # Pattern 3: Last word if it looks like a model
    words = item_name.split()
    if len(words) > 1:
        last_word = words[-1]
        # Check if last word contains numbers and/or special chars
        if re.search(r'[0-9_-]', last_word):
            return last_word
    
    # Fallback: use last 2 words or "Generic Model"
    if len(words) >= 2:
        return ' '.join(words[-2:])
    
    return "Generic Model"

print("=== EXTRACTING ITEM MODELS ===")

# Test the extraction function
test_items = [
    "Astron 7.5kg Twintub Washing Machine SDT-7586",
    "Refrigatratoj 012-A", 
    "Sala Set w/ Center Table Bianca",
    "Astron 24\" Smart Tv ASTRN_09",
    "Sala Set w/ Center Table Myra"
]

print("Testing extraction:")
for item in test_items:
    model = extract_item_model(item)
    print(f"  '{item}' -> '{model}'")

print("\n=== UPDATING CUSTOMERHISTORY RECORDS ===")

# Update existing CustomerHistory records
updated_count = 0
for record in CustomerHistory.objects.all():
    old_model = record.item_model
    new_model = extract_item_model(record.item_name)
    
    if old_model != new_model:
        record.item_model = new_model
        record.save()
        print(f"Updated {record.customers_name}: '{old_model}' -> '{new_model}'")
        updated_count += 1

print(f"\nUpdated {updated_count} records")

print("\n=== FINAL RESULTS ===")
for record in CustomerHistory.objects.all():
    print(f"{record.customers_name} | {record.item_name} | {record.item_model}")
