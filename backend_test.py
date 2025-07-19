#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for CRM System
Tests all authentication, user management, leads, opportunities, call logs, and dashboard APIs
"""

import requests
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Backend URL from frontend .env
BASE_URL = "https://1f537fa0-0dc7-4d58-a6ba-c6352bab82c8.preview.emergentagent.com/api"

class CRMTester:
    def __init__(self):
        self.session = requests.Session()
        self.tokens = {}  # Store tokens for different users
        self.users = {}   # Store user data
        self.leads = {}   # Store created leads
        self.opportunities = {}  # Store created opportunities
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, message: str = "", details: Any = None):
        """Log test results"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if message:
            print(f"   {message}")
        if details and not success:
            print(f"   Details: {details}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message,
            "details": details
        })
        print()
    
    def make_request(self, method: str, endpoint: str, data: Dict = None, token: str = None) -> requests.Response:
        """Make HTTP request with optional authentication"""
        url = f"{BASE_URL}{endpoint}"
        headers = {"Content-Type": "application/json"}
        
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, headers=headers)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, headers=headers)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data, headers=headers)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            return response
        except Exception as e:
            print(f"Request failed: {e}")
            raise
    
    def test_user_registration(self):
        """Test user registration with different roles"""
        print("=== Testing User Registration ===")
        
        test_users = [
            {
                "email": "sarah.admin@crmsystem.com",
                "password": "SecurePass123!",
                "full_name": "Sarah Johnson",
                "role": "admin"
            },
            {
                "email": "mike.manager@crmsystem.com", 
                "password": "ManagerPass456!",
                "full_name": "Mike Thompson",
                "role": "manager"
            },
            {
                "email": "alex.sales@crmsystem.com",
                "password": "SalesPass789!",
                "full_name": "Alex Rodriguez",
                "role": "sales_rep"
            }
        ]
        
        for user_data in test_users:
            response = self.make_request("POST", "/auth/register", user_data)
            
            if response.status_code == 201 or response.status_code == 200:
                user_info = response.json()
                self.users[user_data["role"]] = {**user_data, "id": user_info.get("id")}
                self.log_test(
                    f"Register {user_data['role']} user",
                    True,
                    f"User {user_data['full_name']} registered successfully"
                )
            else:
                self.log_test(
                    f"Register {user_data['role']} user",
                    False,
                    f"Registration failed with status {response.status_code}",
                    response.text
                )
    
    def test_user_login(self):
        """Test login functionality and JWT token generation"""
        print("=== Testing User Login ===")
        
        for role, user_data in self.users.items():
            login_data = {
                "email": user_data["email"],
                "password": user_data["password"]
            }
            
            response = self.make_request("POST", "/auth/login", login_data)
            
            if response.status_code == 200:
                token_data = response.json()
                if "access_token" in token_data:
                    self.tokens[role] = token_data["access_token"]
                    self.log_test(
                        f"Login {role} user",
                        True,
                        f"Login successful, token received"
                    )
                else:
                    self.log_test(
                        f"Login {role} user",
                        False,
                        "No access token in response",
                        token_data
                    )
            else:
                self.log_test(
                    f"Login {role} user",
                    False,
                    f"Login failed with status {response.status_code}",
                    response.text
                )
    
    def test_protected_routes(self):
        """Test protected routes with and without valid tokens"""
        print("=== Testing Protected Routes ===")
        
        # Test without token
        response = self.make_request("GET", "/auth/me")
        self.log_test(
            "Access protected route without token",
            response.status_code == 401,
            f"Correctly rejected with status {response.status_code}"
        )
        
        # Test with invalid token
        response = self.make_request("GET", "/auth/me", token="invalid_token")
        self.log_test(
            "Access protected route with invalid token",
            response.status_code == 401,
            f"Correctly rejected with status {response.status_code}"
        )
        
        # Test with valid token
        if "admin" in self.tokens:
            response = self.make_request("GET", "/auth/me", token=self.tokens["admin"])
            self.log_test(
                "Access protected route with valid token",
                response.status_code == 200,
                f"Successfully accessed with status {response.status_code}"
            )
    
    def test_role_based_access(self):
        """Test role-based access control"""
        print("=== Testing Role-Based Access Control ===")
        
        # Test admin/manager can access users endpoint
        for role in ["admin", "manager"]:
            if role in self.tokens:
                response = self.make_request("GET", "/users", token=self.tokens[role])
                self.log_test(
                    f"{role.capitalize()} access to users endpoint",
                    response.status_code == 200,
                    f"Status: {response.status_code}"
                )
        
        # Test sales_rep cannot access users endpoint
        if "sales_rep" in self.tokens:
            response = self.make_request("GET", "/users", token=self.tokens["sales_rep"])
            self.log_test(
                "Sales rep blocked from users endpoint",
                response.status_code == 403,
                f"Correctly blocked with status {response.status_code}"
            )
    
    def test_leads_crud(self):
        """Test leads CRUD operations"""
        print("=== Testing Leads CRUD Operations ===")
        
        # Test creating leads
        test_leads = [
            {
                "name": "Jennifer Martinez",
                "email": "jennifer.martinez@techcorp.com",
                "phone": "+1-555-0123",
                "company": "TechCorp Solutions",
                "source": "Website",
                "notes": "Interested in enterprise software solutions",
                "status": "new"
            },
            {
                "name": "David Chen",
                "email": "david.chen@innovate.io",
                "phone": "+1-555-0456", 
                "company": "Innovate.io",
                "source": "Referral",
                "notes": "Looking for CRM integration",
                "status": "contacted"
            }
        ]
        
        # Create leads with admin token
        if "admin" in self.tokens:
            for i, lead_data in enumerate(test_leads):
                response = self.make_request("POST", "/leads", lead_data, token=self.tokens["admin"])
                
                if response.status_code in [200, 201]:
                    lead_info = response.json()
                    self.leads[f"lead_{i+1}"] = lead_info
                    self.log_test(
                        f"Create lead {i+1}",
                        True,
                        f"Lead '{lead_data['name']}' created successfully"
                    )
                else:
                    self.log_test(
                        f"Create lead {i+1}",
                        False,
                        f"Failed with status {response.status_code}",
                        response.text
                    )
        
        # Test fetching leads
        for role in ["admin", "manager", "sales_rep"]:
            if role in self.tokens:
                response = self.make_request("GET", "/leads", token=self.tokens[role])
                self.log_test(
                    f"Fetch leads as {role}",
                    response.status_code == 200,
                    f"Status: {response.status_code}, Count: {len(response.json()) if response.status_code == 200 else 'N/A'}"
                )
        
        # Test updating a lead
        if "lead_1" in self.leads and "admin" in self.tokens:
            lead_id = self.leads["lead_1"]["id"]
            update_data = {
                "name": "Jennifer Martinez",
                "email": "jennifer.martinez@techcorp.com",
                "phone": "+1-555-0123",
                "company": "TechCorp Solutions",
                "source": "Website",
                "notes": "Updated: Very interested in enterprise solutions - follow up next week",
                "status": "qualified"
            }
            
            response = self.make_request("PUT", f"/leads/{lead_id}", update_data, token=self.tokens["admin"])
            self.log_test(
                "Update lead",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
    
    def test_opportunities_pipeline(self):
        """Test opportunities creation and pipeline management"""
        print("=== Testing Opportunities Pipeline ===")
        
        # Create opportunities from leads
        if "lead_1" in self.leads and "admin" in self.tokens:
            opp_data = {
                "name": "TechCorp Enterprise Deal",
                "value": 75000.0,
                "stage": "qualified",
                "expected_close_date": (datetime.now() + timedelta(days=30)).isoformat(),
                "notes": "Large enterprise deal with high potential",
                "lead_id": self.leads["lead_1"]["id"]
            }
            
            response = self.make_request("POST", "/opportunities", opp_data, token=self.tokens["admin"])
            
            if response.status_code in [200, 201]:
                opp_info = response.json()
                self.opportunities["opp_1"] = opp_info
                self.log_test(
                    "Create opportunity from lead",
                    True,
                    f"Opportunity '{opp_data['name']}' created successfully"
                )
            else:
                self.log_test(
                    "Create opportunity from lead",
                    False,
                    f"Failed with status {response.status_code}",
                    response.text
                )
        
        # Test fetching opportunities
        for role in ["admin", "manager", "sales_rep"]:
            if role in self.tokens:
                response = self.make_request("GET", "/opportunities", token=self.tokens[role])
                self.log_test(
                    f"Fetch opportunities as {role}",
                    response.status_code == 200,
                    f"Status: {response.status_code}, Count: {len(response.json()) if response.status_code == 200 else 'N/A'}"
                )
        
        # Test updating opportunity stage
        if "opp_1" in self.opportunities and "admin" in self.tokens:
            opp_id = self.opportunities["opp_1"]["id"]
            update_data = {
                "name": "TechCorp Enterprise Deal",
                "value": 85000.0,
                "stage": "proposal",
                "expected_close_date": (datetime.now() + timedelta(days=25)).isoformat(),
                "notes": "Proposal sent, increased deal value after requirements analysis"
            }
            
            response = self.make_request("PUT", f"/opportunities/{opp_id}", update_data, token=self.tokens["admin"])
            self.log_test(
                "Update opportunity stage",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
    
    def test_call_logs(self):
        """Test call logs functionality"""
        print("=== Testing Call Logs ===")
        
        # Create call logs
        if "lead_1" in self.leads and "admin" in self.tokens:
            call_data = {
                "call_type": "outbound",
                "duration": 25,
                "notes": "Initial discovery call - discussed requirements and timeline",
                "lead_id": self.leads["lead_1"]["id"]
            }
            
            response = self.make_request("POST", "/call-logs", call_data, token=self.tokens["admin"])
            self.log_test(
                "Create call log for lead",
                response.status_code in [200, 201],
                f"Status: {response.status_code}"
            )
        
        if "opp_1" in self.opportunities and "admin" in self.tokens:
            call_data = {
                "call_type": "inbound",
                "duration": 15,
                "notes": "Follow-up call regarding proposal questions",
                "opportunity_id": self.opportunities["opp_1"]["id"]
            }
            
            response = self.make_request("POST", "/call-logs", call_data, token=self.tokens["admin"])
            self.log_test(
                "Create call log for opportunity",
                response.status_code in [200, 201],
                f"Status: {response.status_code}"
            )
        
        # Test fetching call logs
        for role in ["admin", "manager", "sales_rep"]:
            if role in self.tokens:
                response = self.make_request("GET", "/call-logs", token=self.tokens[role])
                self.log_test(
                    f"Fetch call logs as {role}",
                    response.status_code == 200,
                    f"Status: {response.status_code}, Count: {len(response.json()) if response.status_code == 200 else 'N/A'}"
                )
    
    def test_dashboard_stats(self):
        """Test dashboard statistics API"""
        print("=== Testing Dashboard Stats ===")
        
        for role in ["admin", "manager", "sales_rep"]:
            if role in self.tokens:
                response = self.make_request("GET", "/dashboard/stats", token=self.tokens[role])
                
                if response.status_code == 200:
                    stats = response.json()
                    expected_fields = [
                        "total_leads", "new_leads", "qualified_leads",
                        "total_opportunities", "won_opportunities", "total_opportunity_value"
                    ]
                    
                    has_all_fields = all(field in stats for field in expected_fields)
                    self.log_test(
                        f"Dashboard stats for {role}",
                        has_all_fields,
                        f"Status: {response.status_code}, Fields present: {has_all_fields}"
                    )
                    
                    if has_all_fields:
                        print(f"   Stats: Leads: {stats['total_leads']}, Opportunities: {stats['total_opportunities']}, Value: ${stats['total_opportunity_value']}")
                else:
                    self.log_test(
                        f"Dashboard stats for {role}",
                        False,
                        f"Failed with status {response.status_code}",
                        response.text
                    )
    
    def run_full_workflow_test(self):
        """Test the complete workflow: register → login → create leads → convert to opportunities → update stages → check stats"""
        print("=== Running Full Workflow Test ===")
        
        workflow_steps = [
            ("User Registration", self.test_user_registration),
            ("User Login", self.test_user_login),
            ("Protected Routes", self.test_protected_routes),
            ("Role-Based Access", self.test_role_based_access),
            ("Leads CRUD", self.test_leads_crud),
            ("Opportunities Pipeline", self.test_opportunities_pipeline),
            ("Call Logs", self.test_call_logs),
            ("Dashboard Stats", self.test_dashboard_stats)
        ]
        
        for step_name, test_func in workflow_steps:
            try:
                test_func()
            except Exception as e:
                self.log_test(
                    f"Workflow step: {step_name}",
                    False,
                    f"Exception occurred: {str(e)}",
                    str(e)
                )
    
    def print_summary(self):
        """Print test summary"""
        print("=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\nFAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"❌ {result['test']}: {result['message']}")
        
        print("\n" + "=" * 60)
        
        return failed_tests == 0

def main():
    """Main test execution"""
    print("Starting Comprehensive CRM Backend API Testing")
    print(f"Backend URL: {BASE_URL}")
    print("=" * 60)
    
    tester = CRMTester()
    
    try:
        tester.run_full_workflow_test()
        success = tester.print_summary()
        
        if success:
            print("🎉 All tests passed! Backend APIs are working correctly.")
            sys.exit(0)
        else:
            print("⚠️  Some tests failed. Check the details above.")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Critical error during testing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()