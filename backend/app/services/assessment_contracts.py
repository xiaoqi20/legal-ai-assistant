from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AssessmentOutput(BaseModel):
  model_config = ConfigDict(extra="forbid", strict=True)


class AssessmentIssue(AssessmentOutput):
  title: str = Field(min_length=1, max_length=200)
  query: str = Field(min_length=1, max_length=1000, pattern=r"\S")


class AssessmentPlan(AssessmentOutput):
  issues: list[AssessmentIssue] = Field(min_length=1, max_length=5)


class EvidenceCoverage(AssessmentOutput):
  queries: list[str] = Field(max_length=3)
  gaps: list[str] = Field(max_length=10)


class AssessmentFact(AssessmentOutput):
  statement: str = Field(min_length=1, max_length=1000)
  origin: Literal["user_statement", "material", "inference"]
  citation_ranks: list[int] = Field(max_length=10)


class IssueFinding(AssessmentOutput):
  title: str = Field(min_length=1, max_length=200)
  assessment: str = Field(min_length=1, max_length=2000)
  supporting_ranks: list[int] = Field(max_length=10)
  opposing_ranks: list[int] = Field(max_length=10)
  gaps: list[str] = Field(max_length=10)


class AssessmentReport(AssessmentOutput):
  outcome: Literal["assessed", "insufficient_material"]
  summary: str = Field(min_length=1, max_length=3000)
  facts: list[AssessmentFact] = Field(max_length=20)
  issues: list[IssueFinding] = Field(min_length=1, max_length=5)
  recommendations: list[str] = Field(max_length=10)
  legal_questions_to_verify: list[str] = Field(max_length=10)
  limitations: list[str] = Field(min_length=1, max_length=10)
