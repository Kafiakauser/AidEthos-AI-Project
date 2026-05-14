"""
AidEthos — FastAPI Backend
Run: uvicorn backend.main:app --reload
"""
import hashlib
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from backend.db.database import create_tables, get_session, engine
from backend.db.models import (
    NGO, Volunteer, Crisis, VolunteerActivity,
    NGORegister, NGOLogin, NGOOut,
    VolunteerRegister, VolunteerLogin, VolunteerOut, VolunteerCreate,
    SkillsUpdate, RegisterCrisis,
    CrisisCreate, CrisisOut,
    SkillMatchRequest, ActivityOut,
)
from backend.ai.matcher import (
    match_volunteer_to_crises,
    match_crisis_to_volunteers,
    calculate_credibility,
)


def _hash(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()


def _time_ago(dt: datetime) -> str:
    diff = datetime.utcnow() - dt
    if diff.days >= 14:   return f"{diff.days // 7} weeks ago"
    if diff.days >= 1:    return f"{diff.days} day{'s' if diff.days>1 else ''} ago"
    hours = diff.seconds // 3600
    if hours >= 1:        return f"{hours} hour{'s' if hours>1 else ''} ago"
    return "Just now"


# ── Seed data (64 real volunteers from Kaggle dataset + demo NGO + crises) ──
def _seed():
    with Session(engine) as s:
        if s.exec(select(NGO)).first():
            return  # Already seeded

        # Demo NGO
        demo = NGO(
            org_name="HelpingHand Foundation",
            phone="+91 40 2345 6789",
            email="demo@helpinghand.org",
            password_hash=_hash("demo1234"),
            location="Hyderabad, Telangana",
            volunteer_needs="data analysts, medical volunteers, logistics coordinators",
            credibility_score=8.5,
        )
        s.add(demo)
        s.commit()
        s.refresh(demo)

        # Crises
        crises_data = [
            dict(ngo_id=demo.id, ngo_name=demo.org_name,
                 title="Hyderabad Flood Response 2025", crisis_type="Flood",
                 description="Massive flooding in low-lying areas of Hyderabad. Immediate assistance needed for evacuation, shelter management, and relief distribution to over 2,000 affected families.",
                 required_skills="data analysis, logistics management, shelter coordination, flood relief, python programming",
                 urgency_level=9, location="Hyderabad, Telangana",
                 contact_phone="+91 40 2345 6789", contact_email="flood@helpinghand.org"),
            dict(ngo_id=demo.id, ngo_name=demo.org_name,
                 title="Earthquake Relief — Coastal Andhra", crisis_type="Earthquake",
                 description="Severe earthquake damage in coastal Andhra Pradesh. Volunteers needed for rescue operations, medical aid, infrastructure assessment and setting up temporary shelters.",
                 required_skills="first aid, medical aid, rescue operations, construction, coordination, driving",
                 urgency_level=8, location="Coastal Andhra Pradesh",
                 contact_phone="+91 40 2345 6790", contact_email="quake@helpinghand.org"),
            dict(ngo_id=demo.id, ngo_name=demo.org_name,
                 title="Orphanage Education Support Program", crisis_type="Orphanage",
                 description="Weekly educational support needed for children in Hyderabad orphanages. Teaching mathematics, English, and computer skills. Digital literacy programs also required.",
                 required_skills="teaching, education, computer skills, english, mathematics, data analysis, tutoring",
                 urgency_level=4, location="Hyderabad, Telangana",
                 contact_phone="+91 40 2345 6791", contact_email="edu@helpinghand.org"),
            dict(ngo_id=demo.id, ngo_name=demo.org_name,
                 title="Animal Rescue — Street Dogs Vaccination Drive", crisis_type="Animal Rescue",
                 description="Large-scale street dog vaccination and rescue operation across Hyderabad. Need veterinary volunteers, animal handlers and transport coordinators.",
                 required_skills="veterinary assistance, animal care, animal rescue, dog walking, first aid, driving",
                 urgency_level=6, location="Hyderabad, Telangana",
                 contact_phone="+91 40 2345 6792", contact_email="animals@helpinghand.org"),
            dict(ngo_id=demo.id, ngo_name=demo.org_name,
                 title="Healthcare Camp — Rural Telangana", crisis_type="Medical",
                 description="Setting up mobile healthcare camps in rural Telangana villages. Need doctors, nurses, lab technicians and health educators to provide basic medical care and vaccinations.",
                 required_skills="nursing, medical assistance, health education, lab assistance, first aid, clinical research",
                 urgency_level=7, location="Rural Telangana",
                 contact_phone="+91 40 2345 6793", contact_email="health@helpinghand.org"),
        ]
        for cd in crises_data:
            s.add(Crisis(**cd))
        s.commit()

        # 64 real volunteers from Kaggle dataset (with Hyderabad added)
        volunteers_data = [
            ("John Smith",      "+91 9800000001", "john.smith@email.com",      "Delhi",     "Animal care, Customer service"),
            ("Sarah Johnson",   "+91 9800000002", "sarah.j@email.com",         "Mumbai",    "Healthcare, Communication"),
            ("Michael Brown",   "+91 9800000003", "m.brown@email.com",         "Bangalore", "Youth mentoring, Teaching"),
            ("Emily Davis",     "+91 9800000004", "emily.d@email.com",         "Chennai",   "Event planning, Social media"),
            ("Daniel Wilson",   "+91 9800000005", "d.wilson@email.com",        "Kolkata",   "Data analysis, Fundraising"),
            ("Jessica Thompson","+91 9800000006", "jessica.t@email.com",       "Delhi",     "Pet grooming, Photography"),
            ("Ryan Anderson",   "+91 9800000007", "ryan.a@email.com",          "Mumbai",    "First aid, Counseling"),
            ("Olivia Martinez", "+91 9800000008", "olivia.m@email.com",        "Bangalore", "Tutoring, Leadership development"),
            ("Ethan Harris",    "+91 9800000009", "ethan.h@email.com",         "Chennai",   "Graphic design, Marketing"),
            ("Ava Lewis",       "+91 9800000010", "ava.l@email.com",           "Kolkata",   "Nursing, Elderly care"),
            ("Benjamin Wright", "+91 9800000011", "ben.w@email.com",           "Delhi",     "Sports coaching, Team management"),
            ("Mia Turner",      "+91 9800000012", "mia.t@email.com",           "Mumbai",    "Veterinary assistance, Animal rescue"),
            ("Samuel Green",    "+91 9800000013", "sam.g@email.com",           "Bangalore", "Research, Lab assistance"),
            ("Lily Walker",     "+91 9800000014", "lily.w@email.com",          "Chennai",   "Mentoring, Community outreach"),
            ("Noah Turner",     "+91 9800000015", "noah.t@email.com",          "Kolkata",   "Dog walking, Pet adoption"),
            ("Sophia Clark",    "+91 9800000016", "sophia.c@email.com",        "Delhi",     "Nutrition, Health education"),
            ("James Evans",     "+91 9800000017", "james.e@email.com",         "Mumbai",    "Tutoring, Career guidance"),
            ("Mia Hernandez",   "+91 9800000018", "mia.h@email.com",           "Bangalore", "Animal shelter volunteering"),
            ("Ethan Adams",     "+91 9800000019", "ethan.a@email.com",         "Chennai",   "Medical coding, Administrative tasks"),
            ("Harper Lewis",    "+91 9800000020", "harper.l@email.com",        "Kolkata",   "Childcare, Mentoring"),
            ("Oliver Wilson",   "+91 9800000021", "oliver.w@email.com",        "Delhi",     "Environmental conservation, Gardening"),
            ("Amelia Adams",    "+91 9800000022", "amelia.a@email.com",        "Mumbai",    "Counseling, Mental health support"),
            ("Benjamin Cooper", "+91 9800000023", "benco@email.com",           "Bangalore", "Leadership development, Sports coaching"),
            ("Harper Turner",   "+91 9800000024", "harpert@email.com",         "Chennai",   "Social media management, Event coordination"),
            ("Liam Thompson",   "+91 9800000025", "liam.t@email.com",          "Kolkata",   "Veterinary assistance, Animal behavior"),
            ("Emily Martinez",  "+91 9800000026", "emily.m@email.com",         "Delhi",     "Nursing, Medical assistance"),
            ("Ethan Roberts",   "+91 9800000027", "ethan.r@email.com",         "Mumbai",    "Teaching, Youth mentoring"),
            ("Sophia Harris",   "+91 9800000028", "sophia.h@email.com",        "Bangalore", "Photography, Creative design"),
            ("Lucas Davis",     "+91 9800000029", "lucas.d@email.com",         "Chennai",   "First aid, Emergency response"),
            ("Ava Turner",      "+91 9800000030", "ava.t@email.com",           "Kolkata",   "Childcare, Tutoring"),
            ("Noah Walker",     "+91 9800000031", "noah.w@email.com",          "Delhi",     "Environmental advocacy, Conservation"),
            ("Isabella Anderson","+91 9800000032","isabella.a@email.com",      "Mumbai",    "Medical research, Lab technician"),
            ("Ethan Wilson",    "+91 9800000033", "ethanw@email.com",          "Bangalore", "Computer programming, Web development"),
            ("Mia Johnson",     "+91 9800000034", "mia.j@email.com",           "Chennai",   "Animal rescue, Wildlife rehabilitation"),
            ("Benjamin Turner", "+91 9800000035", "bent@email.com",            "Kolkata",   "Nutrition, Diet planning"),
            ("Olivia Hernandez","+91 9800000036", "oliviah@email.com",         "Delhi",     "Mentoring, Career guidance"),
            ("Sophia Evans",    "+91 9800000037", "sophia.e@email.com",        "Mumbai",    "Data analysis, Statistical modeling"),
            ("Noah Lewis",      "+91 9800000038", "noah.l@email.com",          "Bangalore", "Event planning, Volunteer coordination"),
            ("Ava Smith",       "+91 9800000039", "ava.s@email.com",           "Chennai",   "Wildlife conservation, Environmental education"),
            ("James Adams",     "+91 9800000040", "james.a@email.com",         "Kolkata",   "Physical therapy, Rehabilitation"),
            ("Mia Turner2",     "+91 9800000041", "mia.t2@email.com",          "Hyderabad", "Art therapy, Special needs support"),
            ("Benjamin Martinez","+91 9800000042","benm@email.com",            "Hyderabad", "Digital marketing, Content creation"),
            ("Lily Thompson",   "+91 9800000043", "lily.th@email.com",         "Hyderabad", "Clinical research, Data management"),
            ("Ethan Walker",    "+91 9800000044", "ethanwk@email.com",         "Hyderabad", "Counseling, Crisis intervention"),
            ("Olivia Harris",   "+91 9800000045", "oliviaH@email.com",         "Hyderabad", "Gardening, Urban farming"),
            ("Ethan Wilson2",   "+91 9800000046", "ethanw2@email.com",         "Hyderabad", "Public speaking, Advocacy"),
            ("Ava Roberts",     "+91 9800000047", "ava.rob@email.com",         "Hyderabad", "Teaching, English language tutoring"),
            ("Benjamin Thompson","+91 9800000048","benth@email.com",           "Hyderabad", "Veterinary medicine, Animal surgery"),
            ("Mia Davis",       "+91 9800000049", "mia.dav@email.com",         "Hyderabad", "Health education, Community outreach"),
            ("Noah Turner2",    "+91 9800000050", "noah.t2@email.com",         "Hyderabad", "Leadership training, Team building"),
            ("Sophia Adams",    "+91 9800000051", "sophia.ad@email.com",       "Hyderabad", "Graphic design, Visual communication"),
            ("James Cooper",    "+91 9800000052", "james.coop@email.com",      "Hyderabad", "Nursing, Geriatric care"),
            ("Mia Hernandez2",  "+91 9800000053", "mia.her2@email.com",        "Hyderabad", "Research, Data analysis"),
            ("Ethan Walker2",   "+91 9800000054", "ethanwk2@email.com",        "Hyderabad", "Dog training, Animal behavior modification"),
            ("Olivia Thompson", "+91 9800000055", "olivia.th@email.com",       "Hyderabad", "Occupational therapy, Rehabilitation"),
            ("Benjamin Adams",  "+91 9800000056", "ben.ad@email.com",          "Hyderabad", "Mentoring, Youth empowerment"),
            ("Ava Lewis2",      "+91 9800000057", "ava.lew2@email.com",        "Hyderabad", "Web development, Database management"),
            ("Noah Johnson",    "+91 9800000058", "noah.j@email.com",          "Hyderabad", "Psychology, Mental health counseling"),
            ("Sophia Wilson",   "+91 9800000059", "sophia.wil@email.com",      "Hyderabad", "Event coordination, Volunteer management"),
            ("James Roberts",   "+91 9800000060", "james.rob@email.com",       "Hyderabad", "Animal shelter volunteering, Pet adoption support"),
            ("Mia Davis2",      "+91 9800000061", "mia.dav2@email.com",        "Hyderabad", "Social work, Case management"),
            ("Benjamin Turner2","+91 9800000062", "bent2@email.com",           "Hyderabad", "Teaching, Computer literacy"),
            ("Olivia Martinez2","+91 9800000063", "oliviam2@email.com",        "Hyderabad", "Environmental activism, Conservation"),
            ("Ethan Harris2",   "+91 9800000064", "ethanh2@email.com",         "Hyderabad", "Medical research, Data analysis"),
        ]
        for name, phone, email, location, skills in volunteers_data:
            s.add(Volunteer(name=name, phone=phone, email=email, location=location, skills=skills))
        s.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    _seed()
    yield


app = FastAPI(title="AidEthos API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "AidEthos API", "version": "1.0.0"}


# ══════════════════════════════════════════════════════
# NGO
# ══════════════════════════════════════════════════════

@app.post("/ngo/register", response_model=NGOOut, status_code=201, tags=["NGO"])
def ngo_register(data: NGORegister, s: Session = Depends(get_session)):
    if s.exec(select(NGO).where(NGO.email == data.email)).first():
        raise HTTPException(400, "Email already registered.")
    ngo = NGO(org_name=data.org_name, phone=data.phone, email=data.email,
              password_hash=_hash(data.password), location=data.location,
              volunteer_needs=data.volunteer_needs, credibility_score=5.0)
    s.add(ngo); s.commit(); s.refresh(ngo)
    return ngo


@app.post("/ngo/login", response_model=NGOOut, tags=["NGO"])
def ngo_login(data: NGOLogin, s: Session = Depends(get_session)):
    ngo = s.exec(select(NGO).where(NGO.email == data.email)).first()
    if not ngo or ngo.password_hash != _hash(data.password):
        raise HTTPException(401, "Invalid email or password.")
    return ngo


@app.get("/ngo/{ngo_id}", response_model=NGOOut, tags=["NGO"])
def get_ngo(ngo_id: int, s: Session = Depends(get_session)):
    ngo = s.get(NGO, ngo_id)
    if not ngo: raise HTTPException(404, "NGO not found.")
    return ngo


@app.get("/ngo/{ngo_id}/crises", response_model=List[CrisisOut], tags=["NGO"])
def ngo_crises(ngo_id: int, s: Session = Depends(get_session)):
    ngo = s.get(NGO, ngo_id)
    if not ngo: raise HTTPException(404, "NGO not found.")
    crises = s.exec(select(Crisis).where(Crisis.ngo_id == ngo_id).order_by(Crisis.created_at.desc())).all()
    result = []
    for c in crises:
        vols = s.exec(select(Volunteer).where(Volunteer.crisis_id == c.id)).all()
        cred = calculate_credibility(ngo_id, len(crises), len(vols))
        ngo.credibility_score = cred
        d = c.dict()
        d["credibility_score"] = cred
        d["ngo_name"] = c.ngo_name or ngo.org_name
        d["volunteer_count"] = len(vols)
        d["match_score"] = None
        result.append(d)
    s.add(ngo); s.commit()
    return result


@app.get("/ngo/{ngo_id}/volunteers", response_model=List[VolunteerOut], tags=["NGO"])
def ngo_volunteers(ngo_id: int, s: Session = Depends(get_session)):
    crises = s.exec(select(Crisis).where(Crisis.ngo_id == ngo_id)).all()
    if not crises: return []
    ids = [c.id for c in crises]
    vols = s.exec(select(Volunteer).where(Volunteer.crisis_id.in_(ids))).all()
    return [v.dict() | {"match_score": None} for v in vols]


# ══════════════════════════════════════════════════════
# VOLUNTEER
# ══════════════════════════════════════════════════════

@app.post("/volunteer/register", response_model=VolunteerOut, status_code=201, tags=["Volunteer"])
def vol_register(data: VolunteerRegister, s: Session = Depends(get_session)):
    if data.email:
        existing = s.exec(select(Volunteer).where(Volunteer.email == data.email, Volunteer.password_hash != None)).first()
        if existing: raise HTTPException(400, "Email already registered.")
    vol = Volunteer(name=data.name, phone=data.phone, email=data.email,
                    password_hash=_hash(data.password) if data.password else None,
                    location=data.location, skills=data.skills)
    s.add(vol); s.commit(); s.refresh(vol)
    return vol.dict() | {"match_score": None}


@app.post("/volunteer/login", response_model=VolunteerOut, tags=["Volunteer"])
def vol_login(data: VolunteerLogin, s: Session = Depends(get_session)):
    vol = s.exec(select(Volunteer).where(Volunteer.email == data.email)).first()
    if not vol or vol.password_hash != _hash(data.password):
        raise HTTPException(401, "Invalid email or password.")
    return vol.dict() | {"match_score": None}


@app.post("/volunteers", response_model=VolunteerOut, status_code=201, tags=["Volunteer"])
def quick_register(data: VolunteerCreate, s: Session = Depends(get_session)):
    """Quick registration (no password) from homepage."""
    vol = Volunteer(name=data.name, phone=data.phone, email=data.email,
                    location=data.location, skills=data.skills, crisis_id=data.crisis_id)
    s.add(vol); s.commit(); s.refresh(vol)
    if data.crisis_id:
        crisis = s.get(Crisis, data.crisis_id)
        if crisis:
            act = VolunteerActivity(volunteer_id=vol.id, crisis_id=data.crisis_id,
                                    crisis_title=crisis.title, status="Registered")
            s.add(act); s.commit()
    return vol.dict() | {"match_score": None}


@app.get("/volunteers", response_model=List[VolunteerOut], tags=["Volunteer"])
def list_volunteers(s: Session = Depends(get_session)):
    return [v.dict() | {"match_score": None} for v in s.exec(select(Volunteer)).all()]


@app.patch("/volunteer/{vol_id}/skills", response_model=VolunteerOut, tags=["Volunteer"])
def update_skills(vol_id: int, data: SkillsUpdate, s: Session = Depends(get_session)):
    vol = s.get(Volunteer, vol_id)
    if not vol: raise HTTPException(404, "Volunteer not found.")
    vol.skills = data.skills
    s.add(vol); s.commit(); s.refresh(vol)
    return vol.dict() | {"match_score": None}


@app.post("/volunteers/{vol_id}/register-crisis", tags=["Volunteer"])
def register_for_crisis(vol_id: int, data: RegisterCrisis, s: Session = Depends(get_session)):
    vol    = s.get(Volunteer, vol_id)
    crisis = s.get(Crisis, data.crisis_id)
    if not vol:    raise HTTPException(404, "Volunteer not found.")
    if not crisis: raise HTTPException(404, "Crisis not found.")
    existing = s.exec(select(VolunteerActivity)
                      .where(VolunteerActivity.volunteer_id == vol_id)
                      .where(VolunteerActivity.crisis_id == data.crisis_id)).first()
    if not existing:
        act = VolunteerActivity(volunteer_id=vol_id, crisis_id=data.crisis_id,
                                crisis_title=crisis.title, status="Registered")
        s.add(act); s.commit()
        vol.crisis_id = data.crisis_id
        s.add(vol); s.commit()
    return {"status": "registered"}


@app.get("/volunteer/{vol_id}/activity", response_model=List[ActivityOut], tags=["Volunteer"])
def vol_activity(vol_id: int, s: Session = Depends(get_session)):
    acts = s.exec(select(VolunteerActivity)
                  .where(VolunteerActivity.volunteer_id == vol_id)
                  .order_by(VolunteerActivity.created_at.desc())).all()
    return [{"crisis_title": a.crisis_title, "status": a.status,
             "time_ago": _time_ago(a.created_at)} for a in acts]


# ══════════════════════════════════════════════════════
# CRISES
# ══════════════════════════════════════════════════════

@app.post("/crises", response_model=CrisisOut, status_code=201, tags=["Crises"])
def create_crisis(data: CrisisCreate, s: Session = Depends(get_session)):
    ngo = s.get(NGO, data.ngo_id)
    if not ngo: raise HTTPException(404, "NGO not found.")
    c = Crisis(ngo_id=data.ngo_id, ngo_name=ngo.org_name, title=data.title,
               crisis_type=data.crisis_type, description=data.description,
               required_skills=data.required_skills, urgency_level=data.urgency_level,
               location=data.location or "Hyderabad, Telangana",
               deadline=data.deadline,
               contact_phone=data.contact_phone or ngo.phone,
               contact_email=data.contact_email or ngo.email)
    s.add(c); s.commit(); s.refresh(c)
    d = c.dict()
    d["credibility_score"] = ngo.credibility_score
    d["volunteer_count"] = 0
    d["match_score"] = None
    return d


@app.get("/crises", response_model=List[CrisisOut], tags=["Crises"])
def list_crises(s: Session = Depends(get_session)):
    crises = s.exec(select(Crisis).where(Crisis.is_active == True)
                    .order_by(Crisis.urgency_level.desc())).all()
    result = []
    for c in crises:
        ngo  = s.get(NGO, c.ngo_id)
        vols = s.exec(select(Volunteer).where(Volunteer.crisis_id == c.id)).all()
        d = c.dict()
        d["ngo_name"]          = c.ngo_name or (ngo.org_name if ngo else "—")
        d["credibility_score"] = ngo.credibility_score if ngo else 5.0
        d["volunteer_count"]   = len(vols)
        d["match_score"]       = None
        result.append(d)
    return result


@app.get("/crises/{crisis_id}", response_model=CrisisOut, tags=["Crises"])
def get_crisis(crisis_id: int, s: Session = Depends(get_session)):
    c = s.get(Crisis, crisis_id)
    if not c: raise HTTPException(404, "Crisis not found.")
    ngo  = s.get(NGO, c.ngo_id)
    vols = s.exec(select(Volunteer).where(Volunteer.crisis_id == crisis_id)).all()
    d = c.dict()
    d["credibility_score"] = ngo.credibility_score if ngo else 5.0
    d["volunteer_count"]   = len(vols)
    d["match_score"]       = None
    return d


@app.get("/crises/{crisis_id}/volunteers", response_model=List[VolunteerOut], tags=["Crises"])
def crisis_volunteers(crisis_id: int, s: Session = Depends(get_session)):
    c = s.get(Crisis, crisis_id)
    if not c: raise HTTPException(404, "Crisis not found.")
    vols = s.exec(select(Volunteer).where(Volunteer.crisis_id == crisis_id)).all()
    if not vols: return []
    return match_crisis_to_volunteers(c, vols)


# ══════════════════════════════════════════════════════
# AI MATCHING
# ══════════════════════════════════════════════════════

@app.post("/match/volunteer", response_model=List[CrisisOut], tags=["Matching"])
def match_for_volunteer(data: SkillMatchRequest, s: Session = Depends(get_session)):
    crises = s.exec(select(Crisis).where(Crisis.is_active == True)).all()
    if not crises: return []
    matched = match_volunteer_to_crises(data.skills, crises)
    for item in matched:
        ngo  = s.get(NGO, item["ngo_id"])
        vols = s.exec(select(Volunteer).where(Volunteer.crisis_id == item["id"])).all()
        item["credibility_score"] = ngo.credibility_score if ngo else 5.0
        item["volunteer_count"]   = len(vols)
    return matched


@app.get("/match/volunteer/{vol_id}", response_model=List[CrisisOut], tags=["Matching"])
def match_by_vol_id(vol_id: int, s: Session = Depends(get_session)):
    vol = s.get(Volunteer, vol_id)
    if not vol: raise HTTPException(404, "Volunteer not found.")
    crises = s.exec(select(Crisis).where(Crisis.is_active == True)).all()
    if not crises: return []
    matched = match_volunteer_to_crises(vol.skills, crises)
    for item in matched:
        ngo  = s.get(NGO, item["ngo_id"])
        vols = s.exec(select(Volunteer).where(Volunteer.crisis_id == item["id"])).all()
        item["credibility_score"] = ngo.credibility_score if ngo else 5.0
        item["volunteer_count"]   = len(vols)
    return matched


@app.get("/match/crisis/{crisis_id}", response_model=List[VolunteerOut], tags=["Matching"])
def match_for_crisis(crisis_id: int, s: Session = Depends(get_session)):
    c = s.get(Crisis, crisis_id)
    if not c: raise HTTPException(404, "Crisis not found.")
    vols = s.exec(select(Volunteer)).all()
    return match_crisis_to_volunteers(c, vols) if vols else []
