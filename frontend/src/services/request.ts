export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
// 只有显式配置为 "false" 才走真实接口，避免本地缺省 env 时页面挂掉
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false";
export const TOKEN_KEY = "law_auth_token";

interface RequestOptions {
  // UniApp 原生类型里没列 PATCH，这里放宽一下供重命名等接口使用
  method?: UniApp.RequestOptions["method"] | "PATCH";
  query?: Record<string, string | number | undefined>;
  data?: UniApp.RequestOptions["data"];
  header?: Record<string, string>;
  timeout?: number;
  // 登录页、协议页这类本身允许未登录访问的接口设为 true，避免 401 死循环跳登录
  skipAuthRedirect?: boolean;
}

export class ApiError extends Error {
  status: number;
  code: string;
  requestId?: string;

  constructor(
    status: number,
    code: string,
    message: string,
    requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

// 并发请求同时 401 时只跳一次登录页，防止页面栈反复 reLaunch
let redirectingAuth = false;

export function getStoredToken(): string {
  try {
    return (uni.getStorageSync(TOKEN_KEY) as string) || "";
  } catch {
    return "";
  }
}

export function clearStoredToken() {
  try {
    uni.removeStorageSync(TOKEN_KEY);
  } catch {
    // 隐私模式或受限容器下清存储可能抛错，直接忽略即可
  }
}

export function redirectToLogin() {
  clearStoredToken();
  if (redirectingAuth) return;
  redirectingAuth = true;
  uni.reLaunch({
    url: "/pages/auth/login",
    complete: () => {
      setTimeout(() => {
        redirectingAuth = false;
      }, 300);
    },
  });
}

// 后端校验 client_*_id 只允许 [a-zA-Z0-9_-] 且最长 64 位
export function createClientId(prefix = "cli"): string {
  const rand = Math.random().toString(36).slice(2, 10);
  return `${prefix}-${Date.now()}-${rand}`.slice(0, 64);
}

// 兼容后端 { error: { code, message }, request_id } 格式，兜底返回 HTTP 状态文案
export function parseApiError(statusCode: number, data: unknown): ApiError {
  if (data && typeof data === "object") {
    const record = data as {
      error?: { code?: string; message?: string };
      request_id?: string;
    };
    if (record.error?.message) {
      return new ApiError(
        statusCode,
        record.error.code || "http_error",
        record.error.message,
        record.request_id,
      );
    }
  }
  return new ApiError(statusCode, "http_error", `请求失败（${statusCode}）`);
}

function buildUrl(path: string, query?: RequestOptions["query"]) {
  const url = `${API_BASE_URL}${path}`;
  if (!query) return url;

  const search = Object.entries(query)
    .filter(([, value]) => value !== undefined && value !== "")
    .map(
      ([key, value]) =>
        `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`,
    )
    .join("&");

  return search ? `${url}?${search}` : url;
}

/** 基础请求封装（基于 uni.request，自动带 Token 并处理 401 回跳） */
export function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  // 请求前：补默认请求头和 Bearer Token
  const token = getStoredToken();
  const header: Record<string, string> = {
    "Content-Type": "application/json",
    ...options.header,
  };
  if (token && !header.Authorization) {
    header.Authorization = `Bearer ${token}`;
  }

  return new Promise((resolve, reject) => {
    uni.request({
      url: buildUrl(path, options.query),
      method: (options.method ?? "GET") as UniApp.RequestOptions["method"],
      data: options.data,
      header,
      timeout: options.timeout ?? 15000,
      success: (response) => {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data as T);
          return;
        }
        // 非 2xx 统一转成 ApiError；401 时清掉失效凭证并回登录页
        const error = parseApiError(response.statusCode, response.data);
        if (response.statusCode === 401 && !options.skipAuthRedirect) {
          redirectToLogin();
        }
        reject(error);
      },
      fail: (error) => {
        reject(new Error(error.errMsg || "网络异常，请稍后重试"));
      },
    });
  });
}
