export type UserRoleType = "individual" | "enterprise" | "legal";

export interface UserProfile {
  display_name: string;
  avatar_url: string;
  phone: string;
  role_type: UserRoleType;
  role_label: string;
  real_name: string;
  company_name: string;
  position: string;
  industry: string;
  organization_name: string;
  legal_role: string;
}
