from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Employee(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, pattern=r"^[a-zA-Z0-9_\-]+$")
    name: str = Field(min_length=1)
    role: str = Field(min_length=1, description='e.g. "Security", "Frontend UI"')
    skills: list[str] = Field(default_factory=list)
    max_load: int = Field(default=15, ge=1)

    @field_validator("skills")
    @classmethod
    def normalise_skills(cls, v: list[str]) -> list[str]:
        return sorted({s.strip().lower() for s in v if s.strip()})


class TeamStructure(BaseModel):
    members: list[Employee] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self) -> "TeamStructure":
        ids = [m.id for m in self.members]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate member ids: {sorted(dupes)}")
        if "unassigned" in ids:
            raise ValueError("'unassigned' is a reserved member id")
        return self
