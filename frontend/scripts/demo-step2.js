// 第二阶段：等待文档解析 -> AI 案情梳理 -> 案件流式问答 -> 小诺助手推荐问 -> 历史记录与个人中心
async (page) => {
  const STEP_MS = 1100;
  const SHORT_MS = 600;
  const pause = (ms = STEP_MS) => page.waitForTimeout(ms);
  const vis = (s) => page.locator(`${s} >> visible=true`);

  async function clickText(text, exact = false, timeout = 8000) {
    const target = page.getByText(text, { exact }).filter({ visible: true }).first();
    await target.waitFor({ state: "visible", timeout });
    await target.scrollIntoViewIfNeeded().catch(() => {});
    await pause(250);
    await target.click();
    await pause(STEP_MS);
  }

  async function goBack() {
    await vis(".nav-back").last().click();
    await pause(STEP_MS);
  }

  async function waitStreamFinish(timeout = 30000) {
    await vis(".stop-btn").waitFor({ state: "hidden", timeout }).catch(() => {});
    await vis(".answer-actions").last().waitFor({ state: "visible", timeout: 8000 }).catch(() => {});
    await pause(STEP_MS);
  }

  // 等待刚上传的文档完成解析并展示在列表中
  await page.getByText("sample-contract.txt", { exact: true }).filter({ visible: true }).first().waitFor({ state: "visible", timeout: 25000 }).catch(() => {});
  await pause(STEP_MS);
  await goBack();

  // 6. AI 案情梳理：未生成则触发生成，已生成则直接切换展示 Tab
  await clickText("AI案情梳理", true);
  await page.getByText("案情梳理", { exact: true }).filter({ visible: true }).first().waitFor({ state: "visible", timeout: 8000 });
  await pause(SHORT_MS);
  const genBtn = page.getByText("生成 AI 分析", { exact: true }).filter({ visible: true });
  if (await genBtn.isVisible().catch(() => false)) {
    await genBtn.click();
    await page.getByText("当事人", { exact: true }).filter({ visible: true }).first().waitFor({ state: "visible", timeout: 30000 }).catch(() => {});
    await pause(STEP_MS);
  }
  await clickText("法律分析", true);
  await clickText("定争分析", true);
  await goBack();

  // 7. 案件详情底部直接提问 -> 案件 AI 流式问答 -> 点赞后返回首页
  const qInput = vis("input.uni-input-input").last();
  await qInput.click();
  await pause(250);
  await qInput.fill("请简要梳理本案合同付款与交房约定");
  await pause(SHORT_MS);
  await vis(".send").last().click();
  await page.getByText("AI问答", { exact: true }).filter({ visible: true }).waitFor({ state: "visible", timeout: 8000 });
  await waitStreamFinish();
  const likeBtn = vis(".answer-actions .action").nth(2);
  if (await likeBtn.isVisible().catch(() => false)) {
    await likeBtn.click();
    await pause(SHORT_MS);
  }
  await goBack();
  await goBack();

  // 8. 切换到首页“助手”Tab -> 点击第一条推荐问发起流式对话
  await clickText("助手", true);
  await page.getByText("推荐问", { exact: true }).filter({ visible: true }).waitFor({ state: "visible", timeout: 8000 });
  await pause(SHORT_MS);
  await vis(".rec-item").first().click();
  await waitStreamFinish();

  // 9. 打开左侧抽屉 -> 历史记录 -> 返回 -> 个人中心
  await vis(".menu").first().click();
  await pause(SHORT_MS);
  await clickText("历史记录", true);
  await page.getByText("历史对话", { exact: true }).filter({ visible: true }).waitFor({ state: "visible", timeout: 8000 });
  await pause(STEP_MS);
  await goBack();

  await vis(".menu").first().click();
  await pause(SHORT_MS);
  await clickText("个人中心", true);
  await page.getByText("退出当前账号", { exact: true }).filter({ visible: true }).waitFor({ state: "visible", timeout: 8000 });
  await pause(1500);

  return { ok: true, currentUrl: page.url() };
}
