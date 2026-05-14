"""AidEthos — Database Models"""
from datetime import datetime, date
from typing import Optional
from sqlmodel import SQLModel, Field


class NGO(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    org_name: str = Field(index=True)
    phone: Optional[str] = None
    email: str = Field(unique=True, index=True)
    password_hash: str
    location: Optional[str] = None
    volunteer_needs: Optional[str] = None
    credibility_score: float = Field(default=5.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Volunteer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: Optional[str] = None
    email: Optional[str] = Field(default=None, index=True)
    password_hash: Optional[str] = None
    location: Optional[str] = None
    skills: str
    crisis_id: Optional[int] = Field(default=None, foreign_key="crisis.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Crisis(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ngo_id: int = Field(foreign_key="ngo.id", index=True)
    ngo_name: Optional[str] = None
    title: str
    crisis_type: Optional[str] = None
    description: str
    required_skills: str
    urgency_level: int = Field(default=5, ge=1, le=10)
    location: Optional[str] = "Hyderabad, Telangana"
    deadline: Optional[date] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VolunteerActivity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    volunteer_id: int = Field(foreign_key="volunteer.id", index=True)
    crisis_id: int = Field(foreign_key="crisis.id", index=True)
    crisis_title: str
    status: str = Field(default="Registered")  # Registered | Completed
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Schemas ────────────────────────────────────────────────────

class NGORegister(SQLModel):
    org_name: str
    phone: Optional[str] = None
    email: str
    password: str
    location: Optional[str] = None
    volunteer_needs: Optional[str] = None

class NGOLogin(SQLModel):
    email: str
    password: str

class NGOOut(SQLModel):
    id: int
    org_name: str
    phone: Optional[str]
    email: str
    location: Optional[str]
    volunteer_needs: Optional[str]
    credibility_score: float
    created_at: datetime

class VolunteerRegister(SQLModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    location: Optional[str] = None
    skills: str

class VolunteerLogin(SQLModel):
    email: str
    password: str

class VolunteerOut(SQLModel):
    id: int
    name: str
    phone: Optional[str]
    email: Optional[str]
    location: Optional[str]
    skills: str
    crisis_id: Optional[int]
    match_score: Optional[float] = None
    created_at: datetime

class VolunteerCreate(SQLModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    location: Optional[str] = None
    skills: str
    crisis_id: Optional[int] = None

class SkillsUpdate(SQLModel):
    skills: str

class RegisterCrisis(SQLModel):
    crisis_id: int

class CrisisCreate(SQLModel):
    ngo_id: int
    title: str
    crisis_type: Optional[str] = None
    description: str
    required_skills: str
    urgency_level: int = 5
    location: Optional[str] = "Hyderabad, Telangana"
    deadline: Optional[date] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None

class CrisisOut(SQLModel):
    id: int
    ngo_id: int
    ngo_name: Optional[str]
    title: str
    crisis_type: Optional[str]
    description: str
    required_skills: str
    urgency_level: int
    location: Optional[str]
    deadline: Optional[date]
    contact_phone: Optional[str]
    contact_email: Optional[str]
    credibility_score: Optional[float] = None
    volunteer_count: Optional[int] = None
    match_score: Optional[float] = None
    is_active: bool
    created_at: datetime

class SkillMatchRequest(SQLModel):
    skills: str

class ActivityOut(SQLModel):
    crisis_title: str
    status: str
    time_ago: str
