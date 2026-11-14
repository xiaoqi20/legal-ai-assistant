from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Input(BaseModel):
  model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Consent(Input):
  agreed: Literal[True]
  document_ids: list[int] = Field(default_factory=list, max_length=10)


class DevLogin(Consent):
  identity: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")


class WechatLogin(Consent):
  login_code: str = Field(min_length=1, max_length=256)
  phone_code: str = Field(min_length=1, max_length=256)


class SMSCode(Consent):
  phone: str = Field(pattern=r"^1[3-9]\d{9}$")


class SMSLogin(SMSCode):
  code: str = Field(pattern=r"^\d{6}$")


class Profile(Input):
  role_type: Literal["individual", "enterprise", "legal"]
  real_name: str = Field(min_length=1, max_length=50)
  company_name: str | None = Field(None, max_length=200)
  position: str | None = Field(None, max_length=100)
  industry: str | None = Field(None, max_length=100)
  organization_name: str | None = Field(None, max_length=200)
  legal_role: str | None = Field(None, max_length=50)

  @model_validator(mode="after")
  def required_fields(self):
    fields = {"enterprise": ["company_name", "position", "industry"],
              "legal": ["organization_name", "legal_role"]}.get(self.role_type, [])
    if any(not getattr(self, name) for name in fields):
      raise ValueError("请填写当前角色的全部必填信息")
    return self


class ConversationCreate(Input):
  case_id: int | None = Field(None, gt=0)
  title: str = Field("未命名对话", min_length=1, max_length=200)


class Rename(Input):
  title: str = Field(min_length=1, max_length=200)


class DeleteConversations(Input):
  ids: list[int] = Field(min_length=1, max_length=100)


class MessageCreate(Input):
  content: str = Field(min_length=1, max_length=4000)
  client_message_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


class Feedback(Input):
  rating: Literal["like", "dislike"]
  comment: str | None = Field(None, max_length=1000)


class UploadCreate(Input):
  case_id: int = Field(gt=0)
  filename: str = Field(min_length=1, max_length=255)
  size_bytes: int = Field(gt=0)
  mime_type: Literal[
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
  ]
  sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
  category: Literal["case_procedure", "court_record", "communication", "other"] = "other"

  @field_validator("filename")
  @classmethod
  def safe_name(cls, value):
    if "/" in value or "\\" in value or any(ord(c) < 32 for c in value):
      raise ValueError("文件名不能包含路径或控制字符")
    return value


class OcrPageReview(Input):
  corrected_text: str = Field(min_length=1, max_length=500000)


class Retrieval(Input):
  query: str = Field(min_length=1, max_length=4000)


class CaseCreate(Input):
  title: str = Field("未命名案件（待完善）", min_length=1, max_length=200)
  case_type: Literal["civil", "criminal", "administrative", "other"] = "other"
  procedure: Literal["first_instance", "second_instance", "retrial", "enforcement", "arbitration", "other"] = "other"
  summary: str | None = Field(None, max_length=2000)
  claim: str | None = Field(None, max_length=2000)
  handling_identity: Literal["self", "agent"] | None = None
  party_role_label: str | None = Field(None, max_length=80)
  our_parties: list[str] = Field(default_factory=list, max_length=5)
  opponent_parties: list[str] = Field(default_factory=list, max_length=5)

  @field_validator("title", mode="before")
  @classmethod
  def default_title(cls, value):
    if isinstance(value, str):
      return value.strip() or "未命名案件（待完善）"
    return value

  @field_validator("summary", "claim", "party_role_label")
  @classmethod
  def empty_optional_text(cls, value):
    return value or None

  @field_validator("our_parties", "opponent_parties")
  @classmethod
  def valid_party_names(cls, values):
    names = [name.strip() for name in values]
    if any(not name or len(name) > 200 for name in names):
      raise ValueError("当事人名称不能为空且不能超过 200 字")
    return names


class AnalysisCreate(Input):
  analysis_type: Literal["case_summary", "timeline", "judicial_reasoning", "dispute_focus", "evidence_chain", "evidence_list", "win_rate", "material_review", "complaint_draft", "evidence_catalog"]
  client_request_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
  material_id: int | None = Field(None, gt=0)

  @model_validator(mode="after")
  def material_target(self):
    if (self.analysis_type == "material_review") != (self.material_id is not None):
      raise ValueError("材料辅助分析须指定材料，其他分析不能指定材料")
    return self


class MaterialInput(Input):
  title: str = Field(min_length=1, max_length=200)
  category: Literal["written", "electronic", "photo_video", "audio", "physical"]
  purpose: str = Field(min_length=1, max_length=3000)
  description: str = Field("", max_length=5000)
  source: str = Field("", max_length=100)
  occurred_on: date | None = None
  requirement_id: int | None = Field(None, gt=0)
  file_ids: list[int] = Field(default_factory=list, max_length=20)

  @field_validator("file_ids")
  @classmethod
  def unique_files(cls, ids):
    if len(ids) != len(set(ids)) or any(i <= 0 for i in ids):
      raise ValueError("附件编号无效或重复")
    return ids


class MaterialUpdate(MaterialInput):
  revision: int = Field(gt=0)


class MaterialAction(Input):
  revision: int = Field(gt=0)
  action: Literal["submit", "withdraw", "approve", "reject"]
  comment: str = Field("", max_length=3000)

  @model_validator(mode="after")
  def rejection_reason(self):
    if self.action == "reject" and not self.comment:
      raise ValueError("退回须填写原因")
    return self


class DraftSave(Input):
  expected_revision: int = Field(ge=0)
  title: str = Field(min_length=1, max_length=200)
  body: str = Field(min_length=1, max_length=30000)
