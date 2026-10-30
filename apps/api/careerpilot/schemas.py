import json
import re
from datetime import date
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DENIED_ORG=bytes([104,105,101,114,111]).decode()
Status=Literal['confirmed','unverified','excluded']
def safe_url(value):
    try:
        p=urlsplit(value)
        return bool(p.scheme in {'https','http'} and p.hostname and not p.username and not p.password)
    except ValueError:return False

class Input(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    @model_validator(mode='after')
    def excluded(self):
        if re.search(r'\b'+DENIED_ORG+r'\b',json.dumps(self.model_dump(exclude={'data','app_id','app_key'})),re.I):raise ValueError('This record contains an explicitly excluded organisation.')
        return self
class CandidateInput(Input):
    name:str=Field(min_length=1,max_length=160)
    headline:str=Field(default='',max_length=240)
    summary:str=Field(default='',max_length=10000)
    status:Status='unverified'
    allowed_on_resume:bool=True
    note:str=Field(default='',max_length=10000)
class FactInput(Input):
    title:str=Field(min_length=1,max_length=240)
    organization:str=Field(default='',max_length=240)
    details:str=Field(default='',max_length=10000)
    start_date:str=Field(default='',max_length=10)
    end_date:str=Field(default='',max_length=10)
    status:Status='unverified'
    allowed_on_resume:bool=True
    learning:bool=False
    note:str=Field(default='',max_length=10000)
    @field_validator('start_date','end_date')
    @classmethod
    def dates(cls,v):
        if v:
            if not re.fullmatch(r'\d{4}-\d{2}(-\d{2})?',v):raise ValueError('Use YYYY-MM or YYYY-MM-DD')
            date.fromisoformat(v+'-01' if len(v)==7 else v)
        return v
    @model_validator(mode='after')
    def ordered(self):
        if self.start_date and self.end_date and self.end_date[:7]<self.start_date[:7]:raise ValueError('End date precedes start date')
        return self
class Country(Input):
    country:str=Field(min_length=2,max_length=80)
    regions:str=Field(default='',max_length=500)
    enabled:bool=True
    authorization:Literal['unknown','pending','needs sponsorship','authorised']='unknown'
    authorization_note:str=Field(default='',max_length=2000)
    min_salary:float|None=Field(default=None,ge=0,le=100000000)
    currency:str=Field(default='CAD',pattern='^[A-Z]{3}$')
    template:str=Field(default='',max_length=80)
class PreferencesInput(Input):
    countries:list[Country]=Field(min_length=1,max_length=30)
    target_titles:list[str]=Field(default_factory=list,max_length=100)
    interests:list[str]=Field(default_factory=lambda:['civil engineering','GIS','infrastructure analytics'],max_length=50)
    excluded_employers:list[str]=Field(default_factory=lambda:['First Quantum Minerals'],max_length=100)
    excluded_terms:list[str]=Field(default_factory=lambda:['MEP','facade','façade','finishes'],max_length=100)
    comparison_currency:str=Field(default='CAD',pattern='^[A-Z]{3}$')
    exchange_rates:dict[str,float]=Field(default_factory=dict,max_length=30)
    exchange_rate_date:str=Field(default='',max_length=10)
    earliest_start:str='2027-01-01'
    employment_type:Literal['Full-time','Any']='Full-time'
    early_career_only:bool=True
    languages_on_resume:bool=False
    canadian_location:bool=False
    @model_validator(mode='after')
    def lists(self):
        if len({c.country.casefold() for c in self.countries})!=len(self.countries):raise ValueError('Countries must be unique')
        if any(not x.strip() or len(x)>240 for x in self.target_titles+self.interests+self.excluded_employers+self.excluded_terms):raise ValueError('Search terms must be 1–240 characters')
        if any(not re.fullmatch('[A-Z]{3}',k) or not 0<v<=100000 for k,v in self.exchange_rates.items()):raise ValueError('Enter positive currency rates')
        for v in [self.exchange_rate_date,self.earliest_start]:
            if v:date.fromisoformat(v)
        return self
class JobInput(Input):
    title:str=Field(min_length=2,max_length=240)
    employer:str=Field(min_length=2,max_length=240)
    country:str=Field(default='',max_length=80)
    location:str=Field(default='',max_length=240)
    url:str=Field(default='',max_length=2048)
    description:str=Field(default='',max_length=50000)
    source:str=Field(default='Manual capture',max_length=100)
    salary:str=Field(default='Not published',max_length=240)
    salary_min:float|None=Field(default=None,ge=0,le=1000000000)
    salary_max:float|None=Field(default=None,ge=0,le=1000000000)
    salary_currency:str=Field(default='',pattern='^([A-Z]{3})?$')
    salary_period:Literal['','year','month','hour']=''
    closing_date:str=Field(default='',max_length=80)
    @model_validator(mode='after')
    def source_required(self):
        if self.url and not safe_url(self.url):raise ValueError('Use an HTTP/HTTPS source URL without credentials')
        if not self.url and not self.description:raise ValueError('Paste the description or original URL')
        if self.salary_min is not None and self.salary_max is not None and self.salary_max<self.salary_min:raise ValueError('Maximum pay is below minimum pay')
        return self
class StageInput(Input):
    stage:str=Field(max_length=30)
    version:int=Field(ge=1)
    approval:bool=False
    evidence:str=Field(default='',max_length=10000)
class NoteInput(Input):
    body:str=Field(min_length=1,max_length=10000)
    kind:Literal['note','employer_response']='note'
class SearchInput(Input):
    title:str=Field(min_length=2,max_length=160)
    country:str=Field(min_length=2,max_length=80)
    region:str=Field(default='',max_length=160)
    source:Literal['feeds','remotive','adzuna','usajobs']='feeds'
class FeedInput(Input):
    employer:str=Field(min_length=2,max_length=240)
    provider:Literal['smartrecruiters','greenhouse','lever','ashby']
    slug:str=Field(pattern='^[A-Za-z0-9_-]{1,160}$')
class SavedInput(Input):
    name:str=Field(min_length=2,max_length=160)
    titles:list[str]=Field(min_length=1,max_length=40)
    countries:list[str]=Field(min_length=1,max_length=15)
    sources:list[Literal['feeds','remotive','adzuna','usajobs']]=Field(min_length=1,max_length=4)
    @model_validator(mode='after')
    def terms(self):
        if any(len(x)>160 or not x.strip() for x in self.titles+self.countries):raise ValueError('Invalid search term')
        return self
class Contact(Input):
    name:str=Field(min_length=2,max_length=160)
    salutation:str=Field(default='',max_length=160)
    role:str=Field(default='',max_length=240)
    email:str=Field(default='',max_length=240)
    source_url:str=Field(max_length=2048)
    verified:bool=False
    @model_validator(mode='after')
    def publication(self):
        if not safe_url(self.source_url):raise ValueError('A published employer/directory source URL is required')
        if self.salutation and not re.fullmatch(r'(Mr\.|Ms\.) [\w ’\'-]{2,100}',self.salutation):raise ValueError('Use Mr. Surname or Ms. Surname when known')
        return self
class EmployerInput(Input):
    name:str=Field(min_length=2,max_length=240)
    website:str=Field(default='',max_length=2048)
    careers_page:str=Field(default='',max_length=2048)
    sector:str=Field(default='',max_length=240)
    size:str=Field(default='',max_length=120)
    countries:list[str]=Field(default_factory=list,max_length=30)
    contacts:list[Contact]=Field(default_factory=list,max_length=20)
    public_feed:str=Field(default='',max_length=240)
    research_notes:str=Field(default='',max_length=10000)
    @field_validator('website','careers_page')
    @classmethod
    def urls(cls,v):
        if v and not safe_url(v):raise ValueError('Use a valid HTTP/HTTPS URL')
        return v
