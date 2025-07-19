#!/usr/bin/env python3
"""
Debug test for lead assignment issue
"""

import requests
import json

BASE_URL = "https://1f537fa0-0dc7-4d58-a6ba-c6352bab82c8.preview.emergentagent.com/api"

def debug_lead_assignment():
    # Login as admin
    login_data = {
        "email": "sarah.admin@crmsystem.com",
        "password": "SecurePass123!"
    }
    
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    if response.status_code != 200:
        print(f"Login failed: {response.status_code}")
        return
    
    token_data = response.json()
    token = token_data["access_token"]
    user_info = token_data["user"]
    print(f"Logged in as: {user_info['full_name']} (ID: {user_info['id']})")
    
    # Get existing leads
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/leads", headers=headers)
    
    if response.status_code == 200:
        leads = response.json()
        print(f"\nFound {len(leads)} leads:")
        for lead in leads:
            print(f"  Lead: {lead['name']}, assigned_to: {lead.get('assigned_to', 'None')}")
            
            if lead.get('assigned_to'):
                # Try to create opportunity
                opp_data = {
                    "name": f"Test Opportunity for {lead['name']}",
                    "value": 50000.0,
                    "stage": "qualified",
                    "notes": "Debug test opportunity",
                    "lead_id": lead["id"]
                }
                
                response = requests.post(f"{BASE_URL}/opportunities", json=opp_data, headers=headers)
                print(f"  Opportunity creation: {response.status_code}")
                if response.status_code != 200:
                    print(f"    Error: {response.text}")
                break
    else:
        print(f"Failed to get leads: {response.status_code}")

if __name__ == "__main__":
    debug_lead_assignment()