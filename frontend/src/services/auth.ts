import { request } from "./request";

export interface LegalDocument {
  id: number;
  doc_type: string;
  version: string;
  title: string;
  content: string;
  effective_at: string;
  published_at: string | null;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
  user_id: number;
  needs_onboarding: boolean;
}

export interface SmsCodeResponse {
  mock: boolean;
  code: string;
  retry_after_seconds: number;
  message: string;
}

export function fetchAgreements(): Promise<LegalDocument[]> {
  return request<LegalDocument[]>("/agreements", { skipAuthRedirect: true });
}

export function devLogin(
  identity: string,
  documentIds: number[],
): Promise<AuthTokenResponse> {
  return request<AuthTokenResponse>("/auth/dev-login", {
    method: "POST",
    data: {
      identity,
      agreed: true,
      document_ids: documentIds,
    },
    skipAuthRedirect: true,
  });
}

export function sendSmsCode(
  phone: string,
  documentIds: number[],
): Promise<SmsCodeResponse> {
  return request<SmsCodeResponse>("/auth/sms/code", {
    method: "POST",
    data: {
      phone,
      agreed: true,
      document_ids: documentIds,
    },
    skipAuthRedirect: true,
  });
}

export function smsLogin(
  phone: string,
  code: string,
  documentIds: number[],
): Promise<AuthTokenResponse> {
  return request<AuthTokenResponse>("/auth/sms/login", {
    method: "POST",
    data: {
      phone,
      code,
      agreed: true,
      document_ids: documentIds,
    },
    skipAuthRedirect: true,
  });
}

export function wechatLogin(
  loginCode: string,
  phoneCode: string,
  documentIds: number[],
): Promise<AuthTokenResponse> {
  return request<AuthTokenResponse>("/auth/wechat", {
    method: "POST",
    data: {
      login_code: loginCode,
      phone_code: phoneCode,
      agreed: true,
      document_ids: documentIds,
    },
    skipAuthRedirect: true,
  });
}

export function logoutSession(): Promise<void> {
  return request<void>("/auth/logout", {
    method: "POST",
    skipAuthRedirect: true,
  });
}
