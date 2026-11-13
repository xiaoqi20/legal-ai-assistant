import { USE_MOCK, request } from "./request";

const MOCK_RECOMMENDATIONS = [
  "请帮我写一份关于民事诉讼的起诉书",
  "关于民事诉讼的答辩状",
  "别人欠我钱逾期未还怎么办",
  "怎么样快速收集案件证据",
];

export function fetchRecommendations(): Promise<string[]> {
  if (USE_MOCK) {
    return new Promise((resolve) => {
      setTimeout(() => resolve([...MOCK_RECOMMENDATIONS]), 120);
    });
  }
  return request<string[]>("/assistant/recommendations");
}
