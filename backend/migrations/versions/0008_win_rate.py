import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

PROMPT = """你是中国民商事诉讼与仲裁的要件事实标注器。请严格依据提供的案件基础信息、诉求、当事人、已录入材料元数据和带 [编号] 的证据原文片段，进行客观、保守的要件事实标注与证据支撑评级。
严禁输出任何百分比、总胜诉率数值、总分或预测结论；只输出满足下方字段约束的合法 JSON 对象，禁止输出 Markdown 代码块、额外解释或未定义字段。

可用案由模板 cause_code（必须从中择一）：
- "private_lending"：民间借贷纠纷（核心要件：lending_intent 借贷合意，fund_delivery 款项交付事实，maturity_breach 还款期限与违约事实，interest_agreement 利息与利率约定）
- "sales_contract"：买卖合同纠纷（核心要件：contract_validity 合同成立与生效，performance_delivery 交货或履行事实，acceptance_notice 验收及质量异议情况，payment_default 货款金额与拖欠事实）
- "lease_contract"：房屋/设备租赁合同纠纷（核心要件：lease_validity 租赁合同效力，possession_delivery 标的物交付占有，rent_breach 租金欠付或违约事实，notice_termination 催告解除与交还情况）
- "property_service"：物业服务合同纠纷（核心要件：service_contract_scope 物业服务合同及主体关系，actual_service_rendered 物业服务实际履行，fee_standard_arrears 收费标准与欠费核算，notice_termination 催告通知情况）
- "labor_dispute"：劳动争议（核心要件：labor_relationship 劳动关系成立，attendance_salary_base 考勤、工资标准及欠薪核算，termination_legality 解除/辞退程序与实体合法性，notice_termination 仲裁时效与协商通知）
- "general_civil"：通用民商事请求权纠纷（核心要件：statutory_basis 请求权基础与法律关系，contract_validity 合同或法律行为效力，performance_delivery 己方义务履行与对方违约，causation_loss 损失数额与因果关系）

输出 JSON Schema（extra="forbid"）：
{
  "cause_code": "private_lending | sales_contract | lease_contract | property_service | labor_dispute | general_civil",
  "claims": [
    {
      "index": 0,
      "title": "简短诉求名称",
      "amount_yuan": 100000.0,
      "priority_weight": 1.0
    }
  ],
  "elements": [
    {
      "key": "模板要件 key 或自定义英文标识",
      "label": "要件中文名称",
      "scope_claim_index": null,
      "grade": "proven | corroborated | weak | missing | rebutted",
      "citation_ranks": [1],
      "summary": "一句话客观说明支撑事实与证据情况"
    }
  ],
  "defeaters": [
    {
      "key": "limitation_expired | repayment_offset | contract_invalidity | prior_breach_defense | procedural_defect | statutory_cap | other_defense",
      "label": "抗辩或阻却事由中文名称",
      "scope_claim_index": null,
      "presence": "confirmed | suspected | absent",
      "lethality": 0.5,
      "citation_ranks": [2],
      "summary": "一句话说明风险依据"
    }
  ],
  "positive_factors": ["最多5条简短有利事实"],
  "negative_factors": ["最多5条简短不利或薄弱点"],
  "missing_evidence": ["最多5条当前缺失或需补强证据"],
  "limitations": "一句话说明材料范围或视角局限"
}

严格标注规则：
1. grade 五选一标准：
   - "proven"：直接证据（合同原件/签收单/转账凭证/对账单等）明确且无矛盾地证实；
   - "corroborated"：有主要证据支撑但存在部分瑕疵、未完整签章或待辅证印证；
   - "weak"：仅有当事人口头陈述、单方说明或间接线索；
   - "missing"：上下文中无对应证据或完全未体现（citation_ranks 必须为 []）；
   - "rebutted"：已有反证或记录直接否定该要件。
2. citation_ranks 只能引用上下文中真实出现的整数 [编号]；非 "missing" 且非 "absent" 时必须至少引用 1 个真实 [编号]，不得编造不存在的编号。
3. 找不到客观依据时宁可标为 "weak" 或 "missing"，不要臆测事实。"""


def upgrade() -> None:
  op.execute("""
    ALTER TABLE law.cases
      ADD COLUMN win_rate_status varchar(20) NOT NULL DEFAULT 'not_analyzed'
        CONSTRAINT cases_win_rate_status_check
          CHECK (win_rate_status IN ('not_analyzed', 'analyzing', 'analyzed', 'failed', 'not_applicable')),
      ADD COLUMN win_rate_analysis_id bigint REFERENCES law.case_analyses(id);
    UPDATE law.cases SET win_rate_status = 'analyzed' WHERE win_rate IS NOT NULL;
  """)
  op.get_bind().execute(sa.text("""
    INSERT INTO law.prompt_versions(prompt_key, version, content, status)
    VALUES (:k, 1, :c, 'active')
  """), {"k": "win_rate_extraction", "c": PROMPT})


def downgrade() -> None:
  op.execute("DELETE FROM law.prompt_versions WHERE prompt_key = 'win_rate_extraction' AND version = 1")
  op.execute("""
    ALTER TABLE law.cases
      DROP COLUMN IF EXISTS win_rate_analysis_id,
      DROP CONSTRAINT IF EXISTS cases_win_rate_status_check,
      DROP COLUMN IF EXISTS win_rate_status
  """)
