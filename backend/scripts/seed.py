"""Explicit opt-in synthetic case seed for a previously logged-in development identity."""
import argparse
import asyncio

from sqlalchemy import insert, select

from app.config import get_settings
from app.db import Database


async def main(identity):
  settings = get_settings()
  if settings.env == "production":
    raise RuntimeError("生产环境禁止写入演示数据")
  database = Database(settings)
  await database.connect()
  t = database.t
  try:
    async with database.sessions.begin() as db:
      user_id = (await db.execute(select(t.user_identities.c.user_id).where(
        t.user_identities.c.provider == "wechat_mini", t.user_identities.c.provider_uid == f"dev:{identity}",
      ))).scalar_one_or_none()
      if user_id is None:
        raise RuntimeError("请先通过 dev-login 创建指定测试身份")
      title = "【合成演示】房屋买卖合同纠纷案"
      exists = (await db.execute(select(t.cases.c.id).where(t.cases.c.owner_user_id == user_id,
        t.cases.c.title == title))).scalar_one_or_none()
      if exists:
        print(f"已存在合成案件 case_id={exists}")
        return
      case_id = (await db.execute(insert(t.cases).values(owner_user_id=user_id, title=title).returning(t.cases.c.id))).scalar_one()
      await db.execute(insert(t.evidence_requirements).values(case_id=case_id,
        title="房屋买卖合同", category="written", source="manual", purpose="证明合成交易约定",
        collection_channel="当事人自行保管的合同原件", collection_method="上传清晰完整的合同文本",
        precautions="仅用于合成数据演示"))
      await db.execute(insert(t.audit_logs).values(user_id=user_id, action="development.seed", resource_type="case", resource_id=case_id))
      print(f"已创建合成案件 case_id={case_id}；未预设分析结果或胜诉率。请上传合成文档。")
  finally:
    await database.close()


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--identity", required=True)
  asyncio.run(main(parser.parse_args().identity))
