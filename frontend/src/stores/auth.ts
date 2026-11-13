import { defineStore } from "pinia";
import { computed, ref } from "vue";
import {
  fetchAgreements,
  logoutSession,
  type AuthTokenResponse,
  type LegalDocument,
} from "@/services/auth";
import {
  fetchProfile,
  updateProfile,
  type ProfileUpdatePayload,
} from "@/services/profile";
import {
  ApiError,
  TOKEN_KEY,
  USE_MOCK,
  clearStoredToken,
  getStoredToken,
} from "@/services/request";
import type { UserProfile, UserRoleType } from "@/types/user";

const PROFILE_KEY = "law_user_profile";

const DEFAULT_PROFILE: UserProfile = {
  display_name: "cherry芝",
  avatar_url: "/static/images/avatar.jpg",
  phone: "135****8890",
  role_type: "enterprise",
  role_label: "企业",
  real_name: "宋芝",
  company_name: "安徽鼎安集团有限公司",
  position: "律师",
  industry: "租赁和商务服务业",
  organization_name: "",
  legal_role: "",
};

const EMPTY_PROFILE: UserProfile = {
  display_name: "未登录用户",
  avatar_url: "/static/images/avatar.jpg",
  phone: "",
  role_type: "individual",
  role_label: "个人",
  real_name: "",
  company_name: "",
  position: "",
  industry: "",
  organization_name: "",
  legal_role: "",
};

const ROLE_LABELS: Record<UserRoleType, string> = {
  individual: "个人",
  enterprise: "企业",
  legal: "法律专业",
};

function readStorage<T>(key: string, fallback: T): T {
  try {
    const raw = uni.getStorageSync(key);
    return raw ? (raw as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeStorage(key: string, value: unknown) {
  try {
    uni.setStorageSync(key, value);
  } catch {
    // ignore storage failures in restricted environments
  }
}

function removeStorage(key: string) {
  try {
    uni.removeStorageSync(key);
  } catch {
    // ignore storage failures
  }
}

function maskPhone(phone: string) {
  const digits = phone.trim();
  if (/^1\d{10}$/.test(digits)) {
    return `${digits.slice(0, 3)}****${digits.slice(7)}`;
  }
  return digits || DEFAULT_PROFILE.phone;
}

export type RoleOnboardingPayload = ProfileUpdatePayload;

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string>(getStoredToken());
  const agreed = ref(false);
  const profile = ref<UserProfile>(
    readStorage<UserProfile>(
      PROFILE_KEY,
      USE_MOCK ? { ...DEFAULT_PROFILE } : { ...EMPTY_PROFILE },
    ),
  );
  const agreements = ref<LegalDocument[]>([]);

  const isLoggedIn = computed(() => Boolean(token.value));

  function toggleAgreed() {
    agreed.value = !agreed.value;
  }

  function setAgreed(value: boolean) {
    agreed.value = value;
  }

  function applyLocalProfile(payload: ProfileUpdatePayload): UserProfile {
    const name = payload.real_name.trim();
    const roleType = payload.role_type;
    const next: UserProfile = {
      ...profile.value,
      role_type: roleType,
      role_label: ROLE_LABELS[roleType],
      real_name: name || profile.value.real_name,
      display_name: name || profile.value.display_name,
      company_name:
        roleType === "enterprise"
          ? payload.company_name?.trim() || "安徽鼎安集团有限公司"
          : "",
      position:
        roleType === "enterprise"
          ? payload.position?.trim() || "律师"
          : "",
      industry:
        roleType === "enterprise"
          ? payload.industry?.trim() || "租赁和商务服务业"
          : "",
      organization_name:
        roleType === "legal"
          ? payload.organization_name?.trim() || "安徽英诺欣律师事务所"
          : "",
      legal_role:
        roleType === "legal"
          ? payload.legal_role?.trim() || "律师"
          : "",
    };
    profile.value = next;
    writeStorage(PROFILE_KEY, next);
    return next;
  }

  // ponytail: simulated login persisted locally when VITE_USE_MOCK=true.
  function loginMock(phone?: string) {
    token.value = "mock-auth-token";
    writeStorage(TOKEN_KEY, token.value);
    if (phone) {
      profile.value = {
        ...profile.value,
        phone: maskPhone(phone),
      };
      writeStorage(PROFILE_KEY, profile.value);
    }
  }

  async function ensureAgreements(forceRefresh = false): Promise<LegalDocument[]> {
    if (USE_MOCK) return agreements.value;
    if (!forceRefresh && agreements.value.length > 0) {
      return agreements.value;
    }
    const docs = await fetchAgreements();
    agreements.value = docs;
    return docs;
  }

  async function ensureAgreementIds(forceRefresh = false): Promise<number[]> {
    const docs = await ensureAgreements(forceRefresh);
    return docs.map((doc) => doc.id);
  }

  async function withAgreementIds<T>(
    runner: (documentIds: number[]) => Promise<T>,
  ): Promise<T> {
    const ids = await ensureAgreementIds();
    try {
      return await runner(ids);
    } catch (error) {
      if (
        error instanceof ApiError &&
        error.status === 409 &&
        error.code === "agreement_version_changed"
      ) {
        const refreshedIds = await ensureAgreementIds(true);
        return runner(refreshedIds);
      }
      throw error;
    }
  }

  async function loadProfile(): Promise<UserProfile> {
    if (USE_MOCK) return profile.value;
    const loaded = await fetchProfile();
    profile.value = loaded;
    writeStorage(PROFILE_KEY, loaded);
    return loaded;
  }

  async function applyAuthToken(res: AuthTokenResponse): Promise<boolean> {
    token.value = res.access_token;
    writeStorage(TOKEN_KEY, res.access_token);
    if (!res.needs_onboarding) {
      await loadProfile().catch(() => undefined);
    }
    return res.needs_onboarding;
  }

  async function saveRoleProfile(
    payload: RoleOnboardingPayload,
  ): Promise<UserProfile> {
    if (USE_MOCK) {
      return applyLocalProfile(payload);
    }
    const updated = await updateProfile(payload);
    profile.value = updated;
    writeStorage(PROFILE_KEY, updated);
    return updated;
  }

  async function logout() {
    if (!USE_MOCK && token.value) {
      await logoutSession().catch(() => undefined);
    }
    token.value = "";
    agreed.value = false;
    clearStoredToken();
    removeStorage(PROFILE_KEY);
    profile.value = USE_MOCK ? { ...DEFAULT_PROFILE } : { ...EMPTY_PROFILE };
    uni.reLaunch({ url: "/pages/auth/login" });
  }

  return {
    token,
    agreed,
    profile,
    agreements,
    isLoggedIn,
    toggleAgreed,
    setAgreed,
    applyLocalProfile,
    loginMock,
    ensureAgreements,
    ensureAgreementIds,
    withAgreementIds,
    loadProfile,
    applyAuthToken,
    saveRoleProfile,
    logout,
  };
});
