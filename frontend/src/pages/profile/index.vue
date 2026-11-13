<script setup lang="ts">
import { onShow } from "@dcloudio/uni-app";
import { computed, ref } from "vue";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import PageNav from "@/components/PageNav.vue";
import { useAuthStore } from "@/stores/auth";
import type { UserProfile } from "@/types/user";

interface ProfileRow {
  icon: string;
  label: string;
  value: string;
}

const auth = useAuthStore();
const profile = ref<UserProfile | null>(null);
const logoutVisible = ref(false);

function loadProfile() {
  auth
    .loadProfile()
    .then((data) => {
      profile.value = data;
    })
    .catch(() => {
      profile.value = { ...auth.profile };
    });
}

onShow(loadProfile);
loadProfile();

const rows = computed<ProfileRow[]>(() => {
  const data = profile.value;
  if (!data) return [];

  if (data.role_type === "legal") {
    return [
      { icon: "profile-briefcase.png", label: "角色：", value: data.legal_role },
      { icon: "profile-building.png", label: "单位名称：", value: data.organization_name },
    ];
  }

  if (data.role_type === "individual") {
    return [
      { icon: "profile-user.png", label: "姓名：", value: data.display_name },
      { icon: "profile-briefcase.png", label: "用户类型：", value: "个人用户" },
    ];
  }

  return [
    { icon: "profile-briefcase.png", label: "担任职位：", value: data.position },
    { icon: "profile-building.png", label: "企业名称：", value: data.company_name },
    { icon: "profile-box.png", label: "所在行业：", value: data.industry },
  ];
});

function confirmLogout() {
  logoutVisible.value = false;
  auth.logout();
}
</script>

<template>
  <view class="page-shell profile-page">
    <PageNav title="个人中心" />

    <view v-if="profile" class="profile-scroll">
      <image class="profile-avatar" :src="profile.avatar_url" mode="aspectFill" />
      <text class="profile-name">{{ profile.display_name }}</text>
      <view class="profile-role">{{ profile.role_label }}</view>

      <view class="profile-card">
        <view v-for="row in rows" :key="row.label" class="profile-row">
          <view class="pic">
            <image class="pic-icon" :src="`/static/images/icons/${row.icon}`" />
          </view>
          <text class="pl">{{ row.label }}</text>
          <text class="pv">{{ row.value || "—" }}</text>
        </view>
      </view>
    </view>

    <view class="profile-footer">
      <view class="profile-logout" @click="logoutVisible = true">退出当前账号</view>
    </view>

    <ConfirmDialog
      :visible="logoutVisible"
      title="确定退出当前账号？"
      @cancel="logoutVisible = false"
      @confirm="confirmLogout"
    />
  </view>
</template>

<style lang="scss" scoped>
.profile-page {
  background: #fff;
}

.profile-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  scrollbar-width: none;
}

.profile-scroll::-webkit-scrollbar {
  display: none;
}

.profile-avatar {
  flex: none;
  width: 105px;
  height: 105px;
  margin-top: 34px;
  border-radius: 50%;
  object-position: center 35%;
  box-shadow: 0 6px 20px rgba(30, 60, 120, 0.12);
}

.profile-name {
  margin: 16px 0 8px;
  font-size: 20px;
  font-weight: 700;
  color: #2f2f2f;
}

.profile-role {
  display: flex;
  align-items: center;
  padding: 3px 12px;
  border-radius: 9px;
  background: #f1f5ff;
  color: #215cff;
  font-size: 12px;
}

.profile-card {
  width: 100%;
  margin-top: 28px;
  padding: 8px 16px;
  border-radius: 12px;
  background: #f7f8fa;
}

.profile-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 0;
  font-size: 15px;
  color: #555;
}

.profile-row + .profile-row {
  border-top: 1px solid #f0f1f4;
}

.pic {
  flex: none;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e7edff;
}

.pic-icon {
  width: 16px;
  height: 16px;
}

.pl {
  flex: none;
}

.pv {
  color: #333;
}

.profile-footer {
  flex: none;
  padding: 0 18px calc(14px + env(safe-area-inset-bottom));
}

/* #ifdef H5 */
.profile-footer {
  padding-bottom: 14px;
}
/* #endif */

.profile-logout {
  height: 48px;
  margin-bottom: 14px;
  border-radius: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f6f7f9;
  color: #8d93a1;
  font-size: 15px;
}
</style>
