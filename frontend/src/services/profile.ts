import { request, USE_MOCK } from "@/services/request";
import { useAuthStore } from "@/stores/auth";
import type { UserProfile, UserRoleType } from "@/types/user";

export interface ProfileUpdatePayload {
  role_type: UserRoleType;
  real_name: string;
  company_name?: string;
  position?: string;
  industry?: string;
  organization_name?: string;
  legal_role?: string;
}

const ROLE_LABELS: Record<UserRoleType, string> = {
  individual: "个人",
  enterprise: "企业",
  legal: "法律专业",
};

function normalizeProfile(raw: Partial<UserProfile>): UserProfile {
  const roleType = raw.role_type ?? "individual";
  return {
    display_name: raw.display_name || raw.real_name || "用户",
    avatar_url: raw.avatar_url || "/static/images/avatar.jpg",
    phone: raw.phone || "",
    role_type: roleType,
    role_label: raw.role_label || ROLE_LABELS[roleType],
    real_name: raw.real_name || "",
    company_name: raw.company_name || "",
    position: raw.position || "",
    industry: raw.industry || "",
    organization_name: raw.organization_name || "",
    legal_role: raw.legal_role || "",
  };
}

export async function fetchProfile(): Promise<UserProfile> {
  const auth = useAuthStore();
  if (USE_MOCK) {
    return { ...auth.profile };
  }
  const data = await request<Partial<UserProfile>>("/profile");
  return normalizeProfile(data);
}

export async function updateProfile(
  payload: ProfileUpdatePayload,
): Promise<UserProfile> {
  const auth = useAuthStore();
  if (USE_MOCK) {
    return auth.applyLocalProfile(payload);
  }
  const body: ProfileUpdatePayload = {
    role_type: payload.role_type,
    real_name: payload.real_name.trim(),
  };
  if (payload.role_type === "enterprise") {
    body.company_name = payload.company_name?.trim() || "";
    body.position = payload.position?.trim() || "";
    body.industry = payload.industry?.trim() || "";
  } else if (payload.role_type === "legal") {
    body.organization_name = payload.organization_name?.trim() || "";
    body.legal_role = payload.legal_role?.trim() || "";
  }

  const data = await request<Partial<UserProfile>>("/profile", {
    method: "PUT",
    data: body,
  });
  return normalizeProfile(data);
}
