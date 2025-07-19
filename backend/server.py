from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from passlib.context import CryptContext
import jwt
import os
import logging
from pathlib import Path
import uuid
from enum import Enum

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Create the main app without a prefix
app = FastAPI(title="CRM API", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Enums
class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    SALES_REP = "sales_rep"

class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    LOST = "lost"

class OpportunityStage(str, Enum):
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"

class CallType(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"

# Models
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.SALES_REP

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(UserBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: User

class LeadBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    status: LeadStatus = LeadStatus.NEW

class LeadCreate(LeadBase):
    assigned_to: Optional[str] = None

class Lead(LeadBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    assigned_to: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class OpportunityBase(BaseModel):
    name: str
    value: float
    stage: OpportunityStage = OpportunityStage.QUALIFIED
    expected_close_date: Optional[datetime] = None
    notes: Optional[str] = None

class OpportunityCreate(OpportunityBase):
    lead_id: str

class Opportunity(OpportunityBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lead_id: str
    assigned_to: str
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CallLogBase(BaseModel):
    call_type: CallType
    duration: Optional[int] = None  # in minutes
    notes: Optional[str] = None

class CallLogCreate(CallLogBase):
    lead_id: Optional[str] = None
    opportunity_id: Optional[str] = None

class CallLog(CallLogBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lead_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Utility functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    user = await db.users.find_one({"email": email})
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return User(**user)

# Auth Routes
@api_router.post("/auth/register", response_model=User)
async def register(user_create: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"email": user_create.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    hashed_password = get_password_hash(user_create.password)
    user_dict = user_create.dict()
    user_dict.pop("password")
    user_obj = User(**user_dict)
    user_with_password = user_obj.dict()
    user_with_password["hashed_password"] = hashed_password
    
    await db.users.insert_one(user_with_password)
    return user_obj

@api_router.post("/auth/login", response_model=Token)
async def login(user_login: UserLogin):
    user = await db.users.find_one({"email": user_login.email})
    if not user or not verify_password(user_login.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )
    user_obj = User(**user)
    return Token(access_token=access_token, token_type="bearer", user=user_obj)

@api_router.get("/auth/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user

# Users Routes
@api_router.get("/users", response_model=List[User])
async def get_users(current_user: User = Depends(get_current_user)):
    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        raise HTTPException(status_code=403, detail="Not authorized")
    users = await db.users.find().to_list(1000)
    return [User(**user) for user in users]

# Leads Routes
@api_router.post("/leads", response_model=Lead)
async def create_lead(lead_create: LeadCreate, current_user: User = Depends(get_current_user)):
    lead_dict = lead_create.dict()
    lead_dict["created_by"] = current_user.id
    if not lead_dict.get("assigned_to"):
        lead_dict["assigned_to"] = current_user.id
    
    lead_obj = Lead(**lead_dict)
    await db.leads.insert_one(lead_obj.dict())
    return lead_obj

@api_router.get("/leads", response_model=List[Lead])
async def get_leads(current_user: User = Depends(get_current_user)):
    query = {}
    if current_user.role == UserRole.SALES_REP:
        query = {"assigned_to": current_user.id}
    
    leads = await db.leads.find(query).to_list(1000)
    return [Lead(**lead) for lead in leads]

@api_router.get("/leads/{lead_id}", response_model=Lead)
async def get_lead(lead_id: str, current_user: User = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Check permissions
    if current_user.role == UserRole.SALES_REP and lead["assigned_to"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return Lead(**lead)

@api_router.put("/leads/{lead_id}", response_model=Lead)
async def update_lead(lead_id: str, lead_update: LeadCreate, current_user: User = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Check permissions
    if current_user.role == UserRole.SALES_REP and lead["assigned_to"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    lead_dict = lead_update.dict()
    lead_dict["updated_at"] = datetime.utcnow()
    
    await db.leads.update_one({"id": lead_id}, {"$set": lead_dict})
    updated_lead = await db.leads.find_one({"id": lead_id})
    return Lead(**updated_lead)

@api_router.delete("/leads/{lead_id}")
async def delete_lead(lead_id: str, current_user: User = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Check permissions
    if current_user.role == UserRole.SALES_REP and lead["assigned_to"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    await db.leads.delete_one({"id": lead_id})
    return {"message": "Lead deleted successfully"}

# Opportunities Routes
@api_router.post("/opportunities", response_model=Opportunity)
async def create_opportunity(opp_create: OpportunityCreate, current_user: User = Depends(get_current_user)):
    # Verify lead exists and user has access
    lead = await db.leads.find_one({"id": opp_create.lead_id})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    if current_user.role == UserRole.SALES_REP and lead["assigned_to"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    opp_dict = opp_create.dict()
    opp_dict["created_by"] = current_user.id
    opp_dict["assigned_to"] = lead["assigned_to"]
    
    opp_obj = Opportunity(**opp_dict)
    await db.opportunities.insert_one(opp_obj.dict())
    
    # Update lead status to qualified
    await db.leads.update_one({"id": opp_create.lead_id}, {"$set": {"status": LeadStatus.QUALIFIED}})
    
    return opp_obj

@api_router.get("/opportunities", response_model=List[Opportunity])
async def get_opportunities(current_user: User = Depends(get_current_user)):
    query = {}
    if current_user.role == UserRole.SALES_REP:
        query = {"assigned_to": current_user.id}
    
    opportunities = await db.opportunities.find(query).to_list(1000)
    return [Opportunity(**opp) for opp in opportunities]

@api_router.put("/opportunities/{opp_id}", response_model=Opportunity)
async def update_opportunity(opp_id: str, opp_update: OpportunityBase, current_user: User = Depends(get_current_user)):
    opp = await db.opportunities.find_one({"id": opp_id})
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    
    # Check permissions
    if current_user.role == UserRole.SALES_REP and opp["assigned_to"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    opp_dict = opp_update.dict()
    opp_dict["updated_at"] = datetime.utcnow()
    
    await db.opportunities.update_one({"id": opp_id}, {"$set": opp_dict})
    updated_opp = await db.opportunities.find_one({"id": opp_id})
    return Opportunity(**updated_opp)

# Call Logs Routes
@api_router.post("/call-logs", response_model=CallLog)
async def create_call_log(call_create: CallLogCreate, current_user: User = Depends(get_current_user)):
    call_dict = call_create.dict()
    call_dict["created_by"] = current_user.id
    
    call_obj = CallLog(**call_dict)
    await db.call_logs.insert_one(call_obj.dict())
    return call_obj

@api_router.get("/call-logs", response_model=List[CallLog])
async def get_call_logs(current_user: User = Depends(get_current_user)):
    query = {}
    if current_user.role == UserRole.SALES_REP:
        query = {"created_by": current_user.id}
    
    call_logs = await db.call_logs.find(query).to_list(1000)
    return [CallLog(**call) for call in call_logs]

# Dashboard Stats
@api_router.get("/dashboard/stats")
async def get_dashboard_stats(current_user: User = Depends(get_current_user)):
    stats = {}
    
    if current_user.role == UserRole.SALES_REP:
        query = {"assigned_to": current_user.id}
    else:
        query = {}
    
    # Lead stats
    total_leads = await db.leads.count_documents(query)
    new_leads = await db.leads.count_documents({**query, "status": LeadStatus.NEW})
    qualified_leads = await db.leads.count_documents({**query, "status": LeadStatus.QUALIFIED})
    
    # Opportunity stats
    opp_query = query.copy() if current_user.role == UserRole.SALES_REP else {}
    total_opportunities = await db.opportunities.count_documents(opp_query)
    won_opportunities = await db.opportunities.count_documents({**opp_query, "stage": OpportunityStage.WON})
    
    # Calculate total opportunity value
    pipeline = [
        {"$match": opp_query},
        {"$group": {"_id": None, "total_value": {"$sum": "$value"}}}
    ]
    value_result = await db.opportunities.aggregate(pipeline).to_list(1)
    total_value = value_result[0]["total_value"] if value_result else 0
    
    stats = {
        "total_leads": total_leads,
        "new_leads": new_leads,
        "qualified_leads": qualified_leads,
        "total_opportunities": total_opportunities,
        "won_opportunities": won_opportunities,
        "total_opportunity_value": total_value
    }
    
    return stats

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()