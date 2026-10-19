import uuid
from datetime import date

from pydantic import BaseModel, Field


class CounselorCreate(BaseModel):
    counselor_code: str = Field(min_length=1, max_length=50)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    national_id: str | None = Field(default=None, max_length=20)
    professional_title: str | None = Field(default=None, max_length=200)
    degree: str | None = Field(default=None, max_length=100)
    specialty: str | None = Field(default=None, max_length=100)
    license_number: str | None = Field(default=None, max_length=100)
    license_expiry_date: date | None = None
    work_mobile: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    service_location_id: uuid.UUID | None = None
    capacity: int | None = Field(default=None, gt=0)
    create_account: bool = False
    username: str | None = Field(default=None, max_length=100)


class CounselorUpdate(BaseModel):
    professional_title: str | None = Field(default=None, max_length=200)
    degree: str | None = Field(default=None, max_length=100)
    specialty: str | None = Field(default=None, max_length=100)
    license_number: str | None = Field(default=None, max_length=100)
    license_expiry_date: date | None = None
    work_mobile: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    service_location_id: uuid.UUID | None = None
    capacity: int | None = Field(default=None, gt=0)
    status: str | None = Field(default=None, max_length=30)


class ApplicantCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    external_id: str | None = Field(default=None, max_length=100)
    employee_code: str | None = Field(default=None, max_length=50)
    national_id: str | None = Field(default=None, max_length=20)
    birth_date: date | None = None
    gender: str | None = Field(default=None, max_length=20)
    marital_status: str | None = Field(default=None, max_length=50)
    education: str | None = Field(default=None, max_length=100)
    occupation: str | None = Field(default=None, max_length=100)
    mobile: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=20)
    unit_id: uuid.UUID | None = None
    organization_id: uuid.UUID | None = None  # فاز ۳۳ - B21: سازمان کارفرما
    service_location_id: uuid.UUID | None = None
    city: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    referral_source: str | None = Field(default=None, max_length=200)
    referral_description: str | None = Field(default=None, max_length=1000)
    create_account: bool = False
    username: str | None = Field(default=None, max_length=100)


class ApplicantUpdate(BaseModel):
    birth_date: date | None = None
    gender: str | None = Field(default=None, max_length=20)
    marital_status: str | None = Field(default=None, max_length=50)
    education: str | None = Field(default=None, max_length=100)
    occupation: str | None = Field(default=None, max_length=100)
    mobile: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=20)
    unit_id: uuid.UUID | None = None
    organization_id: uuid.UUID | None = None  # فاز ۳۳ - B21: سازمان کارفرما
    service_location_id: uuid.UUID | None = None
    city: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    referral_source: str | None = Field(default=None, max_length=200)
    referral_description: str | None = Field(default=None, max_length=1000)
    status: str | None = Field(default=None, max_length=30)
