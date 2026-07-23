import type { ThemeConfig } from "antd";

export const adminTheme: ThemeConfig = {
  token: {
    colorPrimary: "#262626",
    colorPrimaryHover: "#141414",
    colorPrimaryActive: "#000000",
    colorLink: "#262626",
    colorLinkHover: "#000000",
    colorLinkActive: "#595959",
    colorText: "#1f1f1f",
    colorTextSecondary: "#595959",
    colorBorder: "#d9d9d9",
    colorBgLayout: "#f5f5f5",
    controlItemBgHover: "#e8e8e8",
    controlItemBgActive: "#d9d9d9",
    controlItemBgActiveHover: "#d0d0d0",
    controlOutline: "rgb(38 38 38 / 20%)"
  },
  components: {
    Button: {
      defaultHoverBg: "#f5f5f5",
      defaultHoverColor: "#141414",
      defaultHoverBorderColor: "#595959",
      defaultActiveBg: "#e8e8e8",
      defaultActiveColor: "#000000",
      defaultActiveBorderColor: "#262626",
      primaryShadow: "none"
    },
    Layout: {
      bodyBg: "#f5f5f5",
      headerBg: "#ffffff",
      siderBg: "#141414",
      triggerBg: "#262626"
    },
    Menu: {
      darkItemBg: "#141414",
      darkSubMenuItemBg: "#141414",
      darkPopupBg: "#141414",
      darkItemHoverBg: "#303030",
      darkItemSelectedBg: "#434343",
      darkItemSelectedColor: "#ffffff",
      darkItemHoverColor: "#ffffff"
    },
    Table: {
      headerBg: "#f5f5f5",
      headerSortActiveBg: "#e8e8e8",
      headerSortHoverBg: "#dedede",
      bodySortBg: "#fafafa",
      rowHoverBg: "#e8e8e8",
      rowSelectedBg: "#d9d9d9",
      rowSelectedHoverBg: "#d0d0d0",
      borderColor: "#d9d9d9"
    },
    Select: {
      optionActiveBg: "#e8e8e8",
      optionSelectedBg: "#d9d9d9",
      optionSelectedColor: "#1f1f1f"
    },
    Tree: {
      nodeHoverBg: "#e8e8e8",
      nodeHoverColor: "#1f1f1f",
      nodeSelectedBg: "#d9d9d9",
      nodeSelectedColor: "#1f1f1f",
      directoryNodeSelectedBg: "#595959",
      directoryNodeSelectedColor: "#ffffff"
    },
    Segmented: {
      trackBg: "#e8e8e8",
      itemHoverBg: "#d9d9d9",
      itemHoverColor: "#1f1f1f",
      itemActiveBg: "#d0d0d0",
      itemSelectedBg: "#ffffff",
      itemSelectedColor: "#1f1f1f"
    },
    Tabs: {
      inkBarColor: "#262626",
      itemActiveColor: "#000000",
      itemHoverColor: "#141414",
      itemSelectedColor: "#1f1f1f"
    }
  }
};
