<script setup lang="ts">
import { onLaunch } from "@dcloudio/uni-app";

onLaunch(() => {});
</script>

<style lang="scss">
page {
  height: 100%;
  background: #f7f7f9;
  color: #333;
  font-family: "PingFang SC", "PingFangSC", -apple-system, BlinkMacSystemFont,
    "Helvetica Neue", "Microsoft YaHei", sans-serif;
  font-size: 28rpx;
  -webkit-font-smoothing: antialiased;
}

view,
text,
input,
scroll-view,
image {
  box-sizing: border-box;
}

.page-shell {
  position: relative;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background:
    radial-gradient(
      110% 45% at 100% 0%,
      rgba(112, 186, 255, 0.6) 0%,
      rgba(112, 186, 255, 0) 58%
    ),
    radial-gradient(
      90% 35% at 35% 10%,
      rgba(231, 214, 255, 0.45) 0%,
      rgba(231, 214, 255, 0) 70%
    ),
    linear-gradient(180deg, #fbfcff 0%, #f7f8ff 30%, #ffffff 55%);
}

.page-scroll {
  flex: 1;
  height: 0;
}

.surface-card {
  background: #fff;
  border-radius: 24rpx;
  box-shadow: 0 4rpx 16rpx rgba(35, 70, 120, 0.06);
}

/* #ifdef H5 */
page {
  background: #eef1f6;
}

.page-shell {
  max-width: 430px;
  margin: 0 auto;
  box-shadow: 0 0 40px rgba(35, 70, 120, 0.12);
}
/* #endif */
</style>
