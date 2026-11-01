from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.project import ProjectStatus


class _ProjectFields(BaseModel):
    @field_validator("name", "description", "research_question", mode="before", check_fields=False)
    @classmethod
    def _strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ProjectCreate(_ProjectFields):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    research_question: str | None = Field(default=None, max_length=2000)
    status: ProjectStatus = ProjectStatus.ACTIVE


class ProjectUpdate(_ProjectFields):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    research_question: str | None = Field(default=None, max_length=2000)
    status: ProjectStatus | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    research_question: str | None
    status: ProjectStatus
    document_count: int = 0
    report_count: int = 0
    created_at: datetime
    updated_at: datetime
