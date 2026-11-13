// 第一阶段：启动引导 -> 一键登录与协议确认 -> 案件搜索/详情 -> 证据清单 -> 案件文档管理并打开文件选择器
async (page) => {
  const BASE_URL = "http://localhost:5173";
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

  // 1. 清空旧登录态并刷新，从启动页自然过渡到登录页
  await page.goto(BASE_URL);
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await pause(2200);

  // 2. 点击一键登录 -> 弹出协议确认弹窗 -> 同意登录进入首页
  await clickText("本机号码一键登录", true);
  await clickText("同意", true);
  await page.getByText("Hi～我是小诺！", { exact: true }).filter({ visible: true }).waitFor({ state: "visible", timeout: 10000 });
  await pause(STEP_MS);

  // 3. 首页搜索演示案件并进入详情
  const searchInput = vis("input.uni-input-input").first();
  await searchInput.click();
  await pause(250);
  await searchInput.fill("房屋买卖");
  await pause(SHORT_MS);
  await clickText("搜索", true);
  await clickText("【合成演示】房屋买卖合同纠纷案", false, 10000);

  // 4. 案件详情 -> 证据资料清单 -> 返回
  await page.getByText("案件详情", { exact: true }).filter({ visible: true }).waitFor({ state: "visible", timeout: 8000 });
  await pause(STEP_MS);
  await clickText("AI证据链分析", true);
  await page.getByText("证据资料清单", { exact: true }).filter({ visible: true }).first().waitFor({ state: "visible", timeout: 8000 });
  await pause(STEP_MS);
  await vis(".nav-back").last().click();
  await pause(STEP_MS);

  // 5. 进入案件文档管理并点击“上传文档”，交由外部 playwright-cli upload 注入测试文件
  await clickText("案件文档归类", true);
  await page.getByText("案件文档管理", { exact: true }).filter({ visible: true }).waitFor({ state: "visible", timeout: 8000 });
  await pause(SHORT_MS);
  await vis(".upload-btn").click();
  await pause(SHORT_MS);
}
