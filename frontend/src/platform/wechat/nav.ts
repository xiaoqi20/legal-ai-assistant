export interface NavMetrics {
  statusBarHeight: number;
  navBarHeight: number;
  capsuleInset: number;
}

export function getNavMetrics(): NavMetrics {
  const info = uni.getSystemInfoSync();
  let statusBarHeight = info.statusBarHeight ?? 0;
  let navBarHeight = 44;
  let capsuleInset = 0;

  // #ifdef H5
  if (!statusBarHeight) statusBarHeight = 10;
  // #endif

  // #ifdef MP-WEIXIN
  const capsule = uni.getMenuButtonBoundingClientRect();
  if (capsule && capsule.height > 0) {
    navBarHeight = (capsule.top - statusBarHeight) * 2 + capsule.height;
    capsuleInset = (info.windowWidth ?? 375) - capsule.left + 8;
  }
  // #endif

  return { statusBarHeight, navBarHeight, capsuleInset };
}
