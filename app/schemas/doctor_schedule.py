from datetime import date, time
from uuid import UUID

from pydantic import Field

from app.schemas.common import ORMModel


class WeeklyHoursEntry(ORMModel):
    day_of_week: int = Field(ge=0, le=6, description="0=lunes .. 6=domingo")
    start_time: time
    end_time: time


class WeeklyHoursRead(WeeklyHoursEntry):
    id: UUID


class WeeklyHoursSetRequest(ORMModel):
    entries: list[WeeklyHoursEntry] = Field(default_factory=list, max_length=21)


class DoctorAbsenceCreate(ORMModel):
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=500)


class DoctorAbsenceRead(DoctorAbsenceCreate):
    id: UUID
