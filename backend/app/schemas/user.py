from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    mobile: str | None = Field(default=None, max_length=20)
    roles: list[str] = Field(default_factory=list)
    # فاز ۷۴: انتساب کاربر به سازمان برای ایزولاسیون دادهٔ سازمانی
    organization_id: str | None = Field(default=None, max_length=64)
    # فاز ۸۷: عمر توکن بر حسب ساعت (None/0 = دائمی) + شمارهٔ سریال اختیاری
    token_hours: int | None = Field(default=None, ge=0, le=720)
    serial_number: str | None = Field(default=None, max_length=50)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    mobile: str | None = Field(default=None, max_length=20)
    status: str | None = Field(default=None, max_length=30)
    # فاز ۷۴: تغییر سازمان کاربر (None = بدون تغییر؛ "" = حذف انتساب)
    organization_id: str | None = Field(default=None, max_length=64)
    # فاز ۸۷: عمر توکن (None = بدون تغییر؛ ۰ = دائمی؛ ۱..۷۲۰ = ساعت)
    token_hours: int | None = Field(default=None, ge=0, le=720)
    # فاز ۸۷: شمارهٔ سریال (None = بدون تغییر؛ "" = حذف)
    serial_number: str | None = Field(default=None, max_length=50)


class RolesUpdate(BaseModel):
    roles: list[str]


class ActivationTokenOut(BaseModel):
    token: str
    expires_at: datetime


class ResetPasswordRequest(BaseModel):
    """فاز ۵۲ - بازنشانی رمز توسط مدیر سامانه."""

    new_password: str = Field(min_length=8, max_length=128)
    must_change_password: bool = True
