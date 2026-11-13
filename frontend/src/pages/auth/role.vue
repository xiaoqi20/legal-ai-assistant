<script setup lang="ts">
import { computed, ref } from "vue";
import { getNavMetrics } from "@/platform/wechat/nav";
import { useAuthStore } from "@/stores/auth";
import type { UserRoleType } from "@/types/user";

const auth = useAuthStore();
const metrics = getNavMetrics();

const roleTabs: { type: UserRoleType; label: string }[] = [
  { type: "individual", label: "个人用户" },
  { type: "enterprise", label: "企业用户" },
  { type: "legal", label: "法律专业用户" },
];

const industryOptions = [
  "租赁和商务服务业",
  "互联网/信息技术",
  "金融业",
  "制造业",
  "建筑业",
  "其他",
];

const legalRoleOptions = [
  "律师",
  "法务",
  "法官/检察官",
  "法律教师",
  "其他法律从业者",
];

const roleType = ref<UserRoleType>("individual");
const realName = ref(auth.profile.real_name || "");
const companyName = ref(auth.profile.company_name || "");
const position = ref(auth.profile.position || "");
const industry = ref(auth.profile.industry || "");
const organizationName = ref(auth.profile.organization_name || "");
const legalRole = ref(auth.profile.legal_role || "");
const submitting = ref(false);

const namePlaceholder = computed(() =>
  roleType.value === "individual" ? "请输入姓名" : "请输入您的姓名",
);

function pickOption(
  itemList: string[],
  onSelect: (value: string) => void,
) {
  uni.showActionSheet({
    itemList,
    success: ({ tapIndex }) => {
      const value = itemList[tapIndex];
      if (value) onSelect(value);
    },
  });
}

function openIndustryPicker() {
  pickOption(industryOptions, (value) => {
    industry.value = value;
  });
}

function openLegalRolePicker() {
  pickOption(legalRoleOptions, (value) => {
    legalRole.value = value;
  });
}

async function submitRole() {
  if (submitting.value) return;
  if (!realName.value.trim()) {
    uni.showToast({ title: "请输入姓名", icon: "none" });
    return;
  }
  if (roleType.value === "enterprise") {
    if (!companyName.value.trim() || !position.value.trim() || !industry.value.trim()) {
      uni.showToast({ title: "请完善企业名称、职位和行业", icon: "none" });
      return;
    }
  } else if (roleType.value === "legal") {
    if (!organizationName.value.trim() || !legalRole.value.trim()) {
      uni.showToast({ title: "请完善单位名称和法律角色", icon: "none" });
      return;
    }
  }

  submitting.value = true;
  try {
    await auth.saveRoleProfile({
      role_type: roleType.value,
      real_name: realName.value,
      company_name: companyName.value,
      position: position.value,
      industry: industry.value,
      organization_name: organizationName.value,
      legal_role: legalRole.value,
    });
    uni.reLaunch({ url: "/pages/index/index" });
  } catch (error) {
    const msg = error instanceof Error ? error.message : "保存信息失败";
    uni.showToast({ title: msg, icon: "none" });
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <view
    class="page-shell role-page"
    :style="{ paddingTop: `${metrics.statusBarHeight}px` }"
  >
    <scroll-view scroll-y class="page-scroll role-scroll" :show-scrollbar="false">
      <view class="role-inner">
        <text class="role-title">请选择您的角色</text>

        <view class="role-pills">
          <view
            v-for="tab in roleTabs"
            :key="tab.type"
            class="role-pill"
            :class="{ 'role-pill--on': roleType === tab.type }"
            @click="roleType = tab.type"
          >
            {{ tab.label }}
          </view>
        </view>

        <text class="role-form-label">基本信息：</text>

        <view class="role-fields">
          <view class="field">
            <input
              v-model="realName"
              class="field-input"
              type="text"
              :placeholder="namePlaceholder"
              placeholder-style="color:#C3C6CC"
            />
          </view>

          <template v-if="roleType === 'enterprise'">
            <view class="field">
              <input
                v-model="companyName"
                class="field-input"
                type="text"
                placeholder="请输入企业名称"
                placeholder-style="color:#C3C6CC"
              />
            </view>
            <view class="field">
              <input
                v-model="position"
                class="field-input"
                type="text"
                placeholder="请输入担任职位"
                placeholder-style="color:#C3C6CC"
              />
            </view>
            <view class="field field--select" @click="openIndustryPicker">
              <text class="select-text" :class="{ 'select-text--on': industry }">
                {{ industry || "请选择所在的行业" }}
              </text>
              <text class="chevron">⌄</text>
            </view>
          </template>

          <template v-else-if="roleType === 'legal'">
            <view class="field">
              <input
                v-model="organizationName"
                class="field-input"
                type="text"
                placeholder="请输入单位名称"
                placeholder-style="color:#C3C6CC"
              />
            </view>
            <view class="field field--select" @click="openLegalRolePicker">
              <text class="select-text" :class="{ 'select-text--on': legalRole }">
                {{ legalRole || "请选择角色" }}
              </text>
              <text class="chevron">⌄</text>
            </view>
          </template>
        </view>
      </view>
    </scroll-view>

    <view class="role-submit">
      <view class="btn-start" @click="submitRole">
        {{ submitting ? "保存中..." : "开始使用" }}
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.role-page {
  background: #f7f7f9;
}

.role-scroll {
  flex: 1;
  height: 0;
}

.role-inner {
  padding: 0 44rpx 40rpx;
}

.role-title {
  display: block;
  margin-top: 140rpx;
  font-size: 52rpx;
  font-weight: 700;
  color: #262626;
}

.role-pills {
  display: flex;
  flex-wrap: nowrap;
  gap: 20rpx;
  margin-top: 48rpx;
}

.role-pill {
  height: 76rpx;
  padding: 0 28rpx;
  border: 2rpx solid #d9d9d9;
  border-radius: 40rpx;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26rpx;
  color: #666;
  white-space: nowrap;
}

.role-pill--on {
  border-color: transparent;
  background: #dde7ff;
  color: $brand;
}

.role-form-label {
  display: block;
  margin: 36rpx 0 20rpx;
  font-size: 30rpx;
  color: #333;
}

.role-fields {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.field {
  height: 96rpx;
  padding: 0 40rpx;
  border-radius: 48rpx;
  background: #fff;
  display: flex;
  align-items: center;
  gap: 20rpx;
}

.field-input {
  flex: 1;
  min-width: 0;
  height: 100%;
  font-size: 30rpx;
  color: #333;
}

.field--select {
  justify-content: space-between;
}

.select-text {
  font-size: 30rpx;
  color: #c3c6cc;
}

.select-text--on {
  color: #333;
}

.chevron {
  font-size: 32rpx;
  line-height: 1;
  color: #b3b8c2;
  transform: translateY(-4rpx);
}

.role-submit {
  flex: none;
  padding: 28rpx 44rpx calc(84rpx + env(safe-area-inset-bottom));
  background: linear-gradient(180deg, rgba(247, 247, 249, 0), #f7f7f9 38%);
}

.btn-start {
  height: 96rpx;
  border-radius: 52rpx;
  background: $brand;
  color: #fff;
  font-size: 32rpx;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 12rpx 32rpx rgba(33, 92, 255, 0.22);
}
</style>
