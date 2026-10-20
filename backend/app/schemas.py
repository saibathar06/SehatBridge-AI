from datetime import date as Date, time
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Credentials(Strict):
    email: str = Field(min_length=5, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    password: str = Field(min_length=12, max_length=128)
    recaptcha_token: str | None = Field(default=None, max_length=4096)


class Destination(Strict):
    email: str = Field(min_length=5, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    purpose: Literal['verify', 'reset'] = 'verify'
    recaptcha_token: str | None = Field(default=None, max_length=4096)


class OTPInput(Destination):
    code: str = Field(pattern=r'^\d{6}$')
    new_password: str | None = Field(default=None, min_length=12, max_length=128)


class RefreshInput(Strict):
    refresh_token: str = Field(min_length=20, max_length=200)


class ProfileInput(Strict):
    name: str = Field(default='', max_length=100)
    language: Literal['en', 'hi'] = 'en'
    timezone: str = 'Asia/Kolkata'
    chat_history: bool = False

    @field_validator('timezone')
    @classmethod
    def timezone_valid(cls, value):
        try:
            ZoneInfo(value)
        except Exception:
            raise ValueError('Unknown IANA timezone')
        return value


class Source(Strict):
    page: int = Field(ge=1)
    excerpt: str = Field(max_length=1500)


class ExtractedMedicine(Strict):
    name: str | None = Field(default=None, max_length=200)
    brand_generic: str | None = None
    strength: str | None = None
    dose: str | None = None
    dose_unit: str | None = None
    route: str | None = None
    frequency: str | None = None
    scheduled_times: list[str] = Field(default_factory=list, max_length=12)
    duration: str | None = None
    start_date: Date | None = None
    end_date: Date | None = None
    food_instructions: str | None = None
    special_instructions: str | None = None
    source: Source
    confidence: Literal['high', 'medium', 'low'] = 'low'
    clarification_required: bool = True
    review_flags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator('scheduled_times')
    @classmethod
    def valid_times(cls, values):
        for v in values:
            if len(v) != 5:
                raise ValueError('Use HH:MM times')
            time.fromisoformat(v)
        return list(dict.fromkeys(values))


class FollowUpInput(Strict):
    name: str = Field(max_length=200)
    date: Date | None = None
    time_window: str | None = None
    explicitly_documented: bool = True
    source: Source
    review_flags: list[str] = Field(default_factory=list)


class InstructionInput(Strict):
    text: str = Field(max_length=3000)
    kind: Literal['diet', 'care']
    direct_instruction: bool = True
    source: Source


class Extraction(Strict):
    document_type: Literal['prescription', 'discharge', 'laboratory', 'other']
    document_date: Date | None = None
    institution: str | None = None
    clinician: str | None = None
    clinical_context: str | None = None
    summary: str = Field(max_length=6000)
    medicines: list[ExtractedMedicine] = Field(default_factory=list, max_length=100)
    follow_ups: list[FollowUpInput] = Field(default_factory=list, max_length=100)
    tests: list[FollowUpInput] = Field(default_factory=list, max_length=100)
    instructions: list[InstructionInput] = Field(default_factory=list, max_length=100)
    review_flags: list[str] = Field(default_factory=list, max_length=100)

    def validate_sources(self, pages):
        for item in [*self.medicines, *self.follow_ups, *self.tests, *self.instructions]:
            if item.source.page > pages or not item.source.excerpt.strip():
                raise ValueError('Invalid or empty source reference')
        for medicine in self.medicines:
            missing = [key for key in ('name', 'dose', 'dose_unit', 'frequency') if not getattr(medicine, key)]
            if missing or medicine.confidence != 'high':
                medicine.clarification_required = True
                medicine.review_flags = list(set(medicine.review_flags + ['Verify missing/uncertain fields: ' + ', '.join(missing)]))
        return self


class ReviewInput(Strict):
    revision: int = Field(ge=1)
    extraction: Extraction


class ScheduleInput(Strict):
    medicine_index: int = Field(ge=0)
    times: list[str] = Field(min_length=1, max_length=12)
    timezone: str
    start_date: Date
    end_date: Date
    timing_confirmed: bool
    clinician_verified: bool = False
    clarification_note: str = Field(default='', max_length=1000)

    @model_validator(mode='after')
    def validate_schedule(self):
        ProfileInput(timezone=self.timezone)
        ExtractedMedicine.valid_times(self.times)
        if self.end_date < self.start_date or (self.end_date - self.start_date).days > 366:
            raise ValueError('Schedule dates must cover at most 366 days')
        if not self.timing_confirmed:
            raise ValueError('Patient timing confirmation required')
        return self


class ConfirmInput(Strict):
    revision: int = Field(ge=1)
    confirmed: bool
    schedules: list[ScheduleInput] = Field(default_factory=list, max_length=100)


class DoseInput(Strict):
    status: Literal['taken', 'skipped', 'missed', 'upcoming']
    idempotency_key: str = Field(min_length=16, max_length=64)
    expected_status: Literal['taken', 'skipped', 'missed', 'upcoming']


class PreferencesInput(Strict):
    enabled: bool = False
    remote_enabled: bool = False
    quiet_start: str | None = None
    quiet_end: str | None = None

    @model_validator(mode='after')
    def quiet(self):
        if bool(self.quiet_start) != bool(self.quiet_end):
            raise ValueError('Set both quiet hours or neither')
        if self.quiet_start:
            ExtractedMedicine.valid_times([self.quiet_start, self.quiet_end])
            if self.quiet_start == self.quiet_end:
                raise ValueError('Quiet hours start and end must differ')
        return self


class DeviceInput(Strict):
    token: str = Field(min_length=20, max_length=4096)
    device_name: str = Field(max_length=100)


class ChatInput(Strict):
    question: str = Field(min_length=1, max_length=2000)
    language: Literal['hi', 'en'] = 'en'
    document_id: str | None = None


class BookingInput(Strict):
    slot_id: str


class OrderLine(Strict):
    inventory_id: str
    quantity: int = Field(ge=1, le=10)


class OrderInput(Strict):
    items: list[OrderLine] = Field(min_length=1, max_length=20)


class PasswordInput(Strict):
    old_password: str = Field(max_length=128)
    new_password: str = Field(min_length=12, max_length=128)

