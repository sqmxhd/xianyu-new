import {
  ApiOutlined,
  ArrowLeftOutlined,
  ArrowRightOutlined,
  BellOutlined,
  CloudServerOutlined,
  CheckOutlined,
  CheckCircleFilled,
  CloseOutlined,
  DeleteOutlined,
  DesktopOutlined,
  EditOutlined,
  EnvironmentOutlined,
  EyeInvisibleOutlined,
  EyeOutlined,
  FolderOpenOutlined,
  HistoryOutlined,
  HolderOutlined,
  InfoCircleOutlined,
  LockOutlined,
  LogoutOutlined,
  MenuOutlined,
  MessageOutlined,
  MoreOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  PictureOutlined,
  QuestionCircleOutlined,
  QrcodeOutlined,
  ShopOutlined,
  RobotOutlined,
  RollbackOutlined,
  SendOutlined,
  SaveOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  ShoppingCartOutlined,
  StopOutlined,
  SyncOutlined,
  ThunderboltOutlined,
  UploadOutlined,
  WarningOutlined
} from "@ant-design/icons";
import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent
} from "@dnd-kit/core";
import {
  arrayMove,
  rectSortingStrategy,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  Alert,
  App as AntApp,
  AutoComplete,
  Avatar,
  Button,
  Card,
  Descriptions,
  Drawer,
  Dropdown,
  Empty,
  Form,
  Image,
  Input,
  InputNumber,
  Layout,
  List,
  Menu,
  Modal,
  Popover,
  QRCode,
  Segmented,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tabs,
  Tag,
  Tree,
  TreeSelect,
  Upload,
  Tooltip,
  Typography
} from "antd";
import type { ColumnsType } from "antd/es/table";
import VirtualList from "rc-virtual-list";
import {
  useEffect,
  createContext,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useContext,
  type ChangeEvent,
  type ClipboardEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type HTMLAttributes
} from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import {
  createAccount,
  clearAccountBrowserProfile,
  clearBrowserProfile,
  closeAccountBrowserSession,
  createAccountBrowserVNCTicket,
  createRealtimeWebSocket,
  createSystemUser,
  createAutoReplyRule,
  createDeliveryTemplate,
  createProductDraft,
  createIMVerificationVNCTicket,
  createIMVerificationVNCWebSocketUrl,
  createXianyuQRBrowserVNCTicket,
  createQuickPhrase,
  createPublishAddress,
  createPublishAddressGroup,
  createAndEnqueueProductPublishJob,
  createAndEnqueueProductPublishTask,
  createProxy,
  deleteAccount,
  deleteAutoReplyRule,
  deleteDeliveryTemplate,
  deleteLocalManagedProduct,
  deleteProductDraft,
  deleteProductImage,
  cleanupProductUploadSession,
  deleteQuickPhrase,
  deletePublishAddress,
  deletePublishAddressGroup,
  deleteProxy,
  checkDeliveryPreflight,
  getAIProviderSetting,
  getBrowserRuntimeSetting,
  getDeliveryAutomationSetting,
  getAccount,
  getAccountIMVerification,
  getAccountBrowserSession,
  getCookieRenewalStatus,
  getPublishAddressRegions,
  listBackgroundTasks,
  listBrowserProfiles,
  listAccountRuntimeEvents,
  listActiveAccountBrowserSessions,
  listAccounts,
  listAuditLogs,
  listAutoReplyLogs,
  listAutoReplyRuleIssues,
  listAutoReplyRules,
  listAggregateConversations,
  listCachedMessages,
  getChatwootConfig,
  getWebNotificationConfig,
  getWebNotificationSound,
  getOrder,
  getPlatformBlacklist,
  listConversationOrders,
  listDeliveryRecords,
  listDeliveryTemplates,
  listOrders,
  listOrderManagementAccounts,
  listOrderSyncRuns,
  executeOrderOperation,
  previewOrderOperation,
  syncOrder,
  syncOrders,
  updateOrderSyncSetting,
  syncMessages,
  syncConversationItem,
  listProductDrafts,
  listProductImages,
  listProductLocations,
  listProductRegions,
  listProductPublishTasks,
  retryProductPublishTask,
  listProductManagementAccounts,
  listManagedProducts,
  listProductOperations,
  syncManagedProducts,
  polishManagedProducts,
  offlineManagedProducts,
  deleteManagedProducts,
  updateProductSyncSetting,
  listQuickPhrases,
  listPublishAddresses,
  listPublishAddressGroups,
  listProxies,
  previewOrderDelivery,
  previewAutoReply,
  replacePublishAddressRegions,
  pollXianyuQRLogin,
  startXianyuQRBrowserVerification,
  completeXianyuQRBrowserVerification,
  cancelXianyuQRLogin,
  cancelXianyuQRBrowserVerification,
  sendDeliveryRecord,
  sendOrderDelivery,
  sendImage,
  recallMessage,
  revealAccountCookie,
  sendText,
  saveChatwootConfig,
  saveWebNotificationConfig,
  setManualTakeover,
  setPlatformBlacklist,
  startAccount,
  startAccountBrowserSession,
  detectAccountBrowserFingerprint,
  startAccountIMVerification,
  startCookieRenewal,
  stopBrowserProfile,
  startXianyuQRLogin,
  testChatwootAccountAlerts,
  testChatwootConfig,
  testProxy,
  updateAccount,
  updateAccountAutoReply,
  updateAccountWorkspaceVisibility,
  updateAIProviderSetting,
  reorderAccounts,
  reorderAutoReplyRules,
  updateAutoReplyRule,
  updateDeliveryAutomationSetting,
  updateDeliveryTemplate,
  updateProductDraft,
  updateQuickPhrase,
  updatePublishAddress,
  updatePublishAddressGroup,
  uploadProductImage,
  uploadProductImageArchive,
  uploadWebNotificationSound,
  clearWebNotificationSound,
  getProductImageContent,
  updateProxy,
  completeIMVerification,
  cancelIMVerification,
  ApiRequestError,
  bootstrapAdminUser,
  clearStoredAccessToken,
  enqueueDeliveryRecord,
  enqueueProductPublishTask,
  getAuthSetupStatus,
  getCurrentUser,
  getProcessHealth,
  getStoredAccessToken,
  listSystemUsers,
  listRuntimeHealth,
  loginWithPassword,
  markConversationRead,
  setStoredAccessToken,
  pasteAccountBrowserText,
  touchAccountBrowserSession,
  touchQuickPhrase,
  updateCurrentUserPreferences,
  updateSystemUser,
  uploadStandardBrowser,
  downloadStandardBrowser,
  activateStandardBrowser,
  uploadFingerprintBrowser,
  downloadFingerprintBrowser,
  activateFingerprintBrowser
} from "./api";
import { createClientRequestId } from "./requestId";
import { maskSensitive, privacyLocation } from "./privacy";
import { apiTimeToEpochMs, formatCompactBeijingTime } from "./time";
import { AccountWorkspacePage } from "./components/AccountWorkspacePage";
import { IMVerificationViewer } from "./components/IMVerificationViewer";
import {
  AccountHealthTags,
  CookieHealthTag,
  FailedMessageNotice,
  formatItemPrice,
  IMHealthTag,
  StatusTag,
  SystemMessageNotice,
  conversationTitle as rawConversationTitle,
  formatTime,
  isFailedOutboundMessage,
  messageAuthor,
  runtimeStateLabel,
  renderChatMessageContent
} from "./presentation";
import type {
  Account,
  AccountConnectionHealth,
  AccountBrowserSession,
  AccountBrowserIdentity,
  AccountFormValues,
  AdminUser,
  AIProviderSetting,
  AIProviderSettingFormValues,
  AuditLog,
  AutoReplyLog,
  AutoReplyPreviewRequest,
  AutoReplyPreviewResult,
  AutoReplyRule,
  AutoReplyRuleFormValues,
  AutoReplyRuleIssue,
  BackgroundTask,
  BrowserProfile,
  BrowserFingerprintSnapshot,
  BrowserEngine,
  BrowserRuntimeSetting,
  ChatMessage,
  ChatwootConfig,
  ChatwootConfigFormValues,
  WebNotificationConfig,
  Conversation,
  ConversationAccountSync,
  CookieRenewalStatus,
  DeliveryAutomationFormValues,
  DeliveryPreflightResult,
  DeliveryRecord,
  DeliveryTemplate,
  DeliveryTemplateFormValues,
  IMVerification,
  OrderDeliveryPreview,
  OrderDetail,
  OrderAction,
  OrderScope,
  OrderStatus,
  OrderAccountSummary,
  OrderSyncRun,
  OrderSyncSetting,
  ProductDraft,
  ProductDraftFormValues,
  ProductImageAsset,
  ProductLocation,
  ProductLocationListResult,
  ProductLocationOption,
  ProductRegion,
  ProductRegionCatalog,
  ProductPublishTask,
  ManagedProductItem,
  ProductAccountSummary,
  ProductOperationRun,
  ProductPlatformStatus,
  ProductSyncSetting,
  ProcessHealth,
  QuickPhrase,
  QuickPhraseFormValues,
  PublishAddress,
  PublishAddressGroup,
  PublishAddressGroupFormValues,
  ProxyFormValues,
  ProxyResource,
  RuntimeEvent,
  RuntimeState,
  ClientAccessInfo,
  LoginFormValues,
  SendTextFormValues,
  UserFormValues,
  XianyuOrder,
  QRBrowserVerification,
  XianyuQRStatus
} from "./types";
import type { DataNode } from "antd/es/tree";

const { Header, Content, Sider } = Layout;
const { Text, Title } = Typography;

type ConversationStatusFilter = "all" | "unread";
type PendingImageStatus = "queued" | "sending" | "sent" | "failed";
type AccountWorkspaceVisibilityField =
  | "conversation_visible"
  | "chat_enabled"
  | "order_management_visible"
  | "product_management_visible";
type PendingImage = {
  clientRequestId: string;
  file: File;
  previewUrl: string;
  status: PendingImageStatus;
  error?: string;
};
type AddressImportFormValues = {
  account_id: string;
  location_ids: string[];
};
type ProductManagerStatusFilter = ProductPlatformStatus | "all" | "publishing" | "publish_failed";
type ProductCatalogEntry = {
  key: string;
  kind: "item" | "publish_task";
  title: string;
  price: string;
  coverUrl?: string | null;
  item?: ManagedProductItem;
  task?: ProductPublishTask;
};

type RuleDragContextValue = Pick<
  ReturnType<typeof useSortable>,
  "attributes" | "listeners" | "setActivatorNodeRef"
>;

const RuleDragContext = createContext<RuleDragContextValue | null>(null);

type AccountDragContextValue = Pick<
  ReturnType<typeof useSortable>,
  "attributes" | "listeners" | "setActivatorNodeRef"
>;

const AccountDragContext = createContext<AccountDragContextValue | null>(null);

function SortableAccountRow(
  props: HTMLAttributes<HTMLTableRowElement> & { "data-row-key"?: string }
) {
  const rowKey = String(props["data-row-key"] || "");
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: rowKey, disabled: !rowKey });
  const contextValue = useMemo(
    () => ({ attributes, listeners, setActivatorNodeRef }),
    [attributes, listeners, setActivatorNodeRef]
  );
  return (
    <AccountDragContext.Provider value={contextValue}>
      <tr
        {...props}
        ref={setNodeRef}
        className={`${props.className || ""}${isDragging ? " account-table-row-dragging" : ""}`}
        style={{
          ...props.style,
          transform: CSS.Transform.toString(transform),
          transition,
          position: isDragging ? "relative" : undefined,
          zIndex: isDragging ? 1 : undefined
        }}
      />
    </AccountDragContext.Provider>
  );
}

function AccountDragHandle({ disabled = false }: { disabled?: boolean }) {
  const drag = useContext(AccountDragContext);
  return (
    <Tooltip title={disabled ? "正在保存账户顺序" : "拖动调整账户顺序"}>
      <Button
        ref={disabled ? undefined : drag?.setActivatorNodeRef}
        type="text"
        size="small"
        className="account-drag-handle"
        icon={<HolderOutlined />}
        disabled={disabled}
        aria-label={disabled ? "正在保存账户顺序" : "拖动调整账户顺序"}
        {...(disabled ? {} : drag?.attributes)}
        {...(disabled ? {} : drag?.listeners)}
      />
    </Tooltip>
  );
}

function SortableRuleRow(
  props: HTMLAttributes<HTMLTableRowElement> & { "data-row-key"?: string }
) {
  const rowKey = String(props["data-row-key"] || "");
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: rowKey, disabled: !rowKey });
  const contextValue = useMemo(
    () => ({ attributes, listeners, setActivatorNodeRef }),
    [attributes, listeners, setActivatorNodeRef]
  );
  return (
    <RuleDragContext.Provider value={contextValue}>
      <tr
        {...props}
        ref={setNodeRef}
        className={`${props.className || ""}${isDragging ? " auto-reply-rule-row-dragging" : ""}`}
        style={{
          ...props.style,
          transform: CSS.Transform.toString(transform),
          transition,
          position: isDragging ? "relative" : undefined,
          zIndex: isDragging ? 1 : undefined
        }}
      />
    </RuleDragContext.Provider>
  );
}

function RuleDragHandle({ disabled = false }: { disabled?: boolean }) {
  const drag = useContext(RuleDragContext);
  return (
    <Tooltip title={disabled ? "兜底规则固定在列表末尾" : "拖动调整执行顺序"}>
      <Button
        ref={disabled ? undefined : drag?.setActivatorNodeRef}
        type="text"
        size="small"
        className="auto-reply-rule-drag-handle"
        icon={<HolderOutlined />}
        disabled={disabled}
        aria-label={disabled ? "兜底规则固定在末尾" : "拖动调整规则顺序"}
        {...(disabled ? {} : drag?.attributes)}
        {...(disabled ? {} : drag?.listeners)}
      />
    </Tooltip>
  );
}

type SortableProductImageProps = {
  imageRef: string;
  index: number;
  total: number;
  asset?: ProductImageAsset;
  previewUrl?: string;
  onPreview: (imageRef: string) => void;
  onMove: (imageRef: string, offset: -1 | 1) => void;
  onRemove: (imageRef: string) => void;
};

function SortableProductImage({
  imageRef,
  index,
  total,
  asset,
  previewUrl,
  onPreview,
  onMove,
  onRemove
}: SortableProductImageProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: imageRef });

  return (
    <div
      ref={setNodeRef}
      className={`product-image-item${isDragging ? " is-dragging" : ""}`}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        zIndex: isDragging ? 1 : undefined
      }}
    >
      <div
        className="product-image-preview product-image-drag-target"
        {...attributes}
        {...listeners}
        title="点击预览，拖动调整图片顺序"
        onClick={() => previewUrl && onPreview(imageRef)}
      >
        {previewUrl ? (
          <img src={previewUrl} alt={asset?.original_filename || `商品图片 ${index + 1}`} />
        ) : (
          <Spin size="small" />
        )}
        {index === 0 ? <Tag color="blue">主图</Tag> : null}
        <HolderOutlined className="product-image-drag-indicator" aria-hidden="true" />
      </div>
      <Text ellipsis title={asset?.original_filename}>
        {asset?.original_filename || `图片 ${index + 1}`}
      </Text>
      <Space size={4} className="product-image-actions">
        <Tooltip title="向左移动">
          <Button
            size="small"
            icon={<ArrowLeftOutlined />}
            disabled={index === 0}
            onClick={() => onMove(imageRef, -1)}
          />
        </Tooltip>
        <Tooltip title="向右移动">
          <Button
            size="small"
            icon={<ArrowRightOutlined />}
            disabled={index === total - 1}
            onClick={() => onMove(imageRef, 1)}
          />
        </Tooltip>
        <Tooltip title="移除图片">
          <Button
            danger
            size="small"
            icon={<DeleteOutlined />}
            onClick={() => onRemove(imageRef)}
          />
        </Tooltip>
      </Space>
    </div>
  );
}

const cookieTriggerLabels = {
  manual: "手动执行",
  scheduled: "定时任务",
  auth_recovery: "认证恢复"
} as const;

const cookieSourceLabels: Record<string, string> = {
  manual_update: "手动更新",
  qr_login: "扫码登录",
  runtime_refresh: "IM 令牌刷新",
  manual_renewal: "手动续期",
  scheduled_renewal: "定时续期",
  auth_recovery: "认证恢复",
  cookie_keepalive: "轻量保活",
  account_browser: "VNC 浏览器",
  account_browser_local_validation: "VNC 本地复核",
  legacy: "历史数据"
};

const imVerificationStateMeta: Record<
  IMVerification["status"],
  { label: string; color: string }
> = {
  required: { label: "待处理", color: "orange" },
  starting: { label: "正在启动", color: "processing" },
  ready: { label: "等待验证", color: "blue" },
  completing: { label: "正在恢复", color: "processing" },
  completed: { label: "已完成", color: "green" },
  failed: { label: "失败", color: "red" },
  expired: { label: "已超时", color: "default" },
  cancelled: { label: "已取消", color: "default" }
};

const qrBrowserStateMeta: Record<
  QRBrowserVerification["status"],
  { label: string; color: string }
> = {
  idle: { label: "未启动", color: "default" },
  starting: { label: "正在启动", color: "processing" },
  ready: { label: "等待操作", color: "blue" },
  completing: { label: "正在检查", color: "processing" },
  completed: { label: "已完成", color: "green" },
  failed: { label: "启动失败", color: "red" },
  expired: { label: "已超时", color: "default" },
  cancelled: { label: "已取消", color: "default" }
};

const accountBrowserStateMeta: Record<
  AccountBrowserSession["status"],
  { label: string; color: string }
> = {
  starting: { label: "正在启动", color: "processing" },
  ready: { label: "可以操作", color: "blue" },
  closing: { label: "正在关闭", color: "processing" },
  closed: { label: "已关闭", color: "default" },
  expired: { label: "已超时", color: "default" },
  failed: { label: "启动失败", color: "red" }
};

const accountBrowserCookieSyncMeta: Record<
  AccountBrowserSession["cookie_sync_status"],
  { label: string; color: string }
> = {
  pending: { label: "Cookie 待核对", color: "default" },
  updated_from_browser: { label: "浏览器 Cookie 已更新", color: "green" },
  refreshed_from_browser: { label: "浏览器 Cookie 已验证", color: "green" },
  kept_local: { label: "已保留本地 Cookie", color: "blue" },
  auth_recovery: { label: "正在认证恢复", color: "orange" },
  account_mismatch: { label: "账号不一致", color: "red" },
  unknown: { label: "Cookie 待复核", color: "gold" },
  failed: { label: "Cookie 核对失败", color: "red" }
};

const browserProfileStateMeta: Record<
  BrowserProfile["status"],
  { label: string; color: string }
> = {
  running: { label: "运行中", color: "green" },
  stopped: { label: "已停止", color: "default" },
  busy: { label: "进程占用", color: "orange" },
  orphaned: { label: "未绑定账户", color: "red" },
  temporary: { label: "扫码临时目录", color: "blue" }
};

function browserFingerprintDetectionMeta(
  snapshot?: BrowserFingerprintSnapshot | null,
  status?: AccountBrowserSession["fingerprint_detection_status"] | null
): { label: string; color: string } {
  if (status === "collecting") return { label: "检测中", color: "processing" };
  if (status === "failed") return { label: "检测失败", color: "red" };
  if (!snapshot) return { label: "待检测", color: "default" };
  if (snapshot.stability_status === "changed") return { label: "有变化", color: "orange" };
  if (snapshot.stability_status === "stable") return { label: "稳定", color: "green" };
  return { label: "基线已建立", color: "blue" };
}

function browserFingerprintSecurityMeta(
  snapshot?: BrowserFingerprintSnapshot | null
): { label: string; color: string } {
  if (!snapshot) return { label: "安全待检测", color: "default" };
  if (
    snapshot.schema_version < 3
    && snapshot.risk_status === "warning"
    && snapshot.risk_findings.length > 0
    && snapshot.risk_findings.every((finding) => finding.includes("未配置 STUN 探针"))
  ) {
    return { label: "安全待复检", color: "default" };
  }
  if (snapshot.risk_status === "risk") return { label: "存在风险", color: "red" };
  if (snapshot.risk_status === "warning") return { label: "需要确认", color: "gold" };
  if (snapshot.risk_status === "pass") return { label: "安全通过", color: "green" };
  return { label: "结果未确认", color: "default" };
}

function browserFingerprintRiskSummary(snapshot: BrowserFingerprintSnapshot): string {
  const findings = snapshot.risk_findings.filter(
    (finding) => !finding.includes("未配置 STUN 探针")
  );
  if (findings.length) return findings.join("；");
  if (snapshot.schema_version < 3) return "旧快照未包含浏览器 HTTP 出口，请重新检测";
  return "未发现当前标准检测项风险";
}

function browserWebRTCDetectionSummary(snapshot: BrowserFingerprintSnapshot): string {
  if (snapshot.webrtc_policy === "disabled") {
    return snapshot.webrtc_api_available === false ? "严格阻断已生效" : "严格阻断未完全生效";
  }
  if (snapshot.webrtc_policy === "browser_default") return "浏览器默认，未限制到代理";
  if (snapshot.webrtc_proxy_match === true) return "公网候选与账户代理出口匹配";
  if (snapshot.webrtc_proxy_match === false) return "公网候选与账户代理出口不匹配";
  if (!snapshot.webrtc_public_candidate_detected) return "未发现公网候选地址";
  return "缺少代理出口基线，暂无法比对";
}

function browserEgressDetectionSummary(snapshot: BrowserFingerprintSnapshot): string {
  const browserCount = snapshot.browser_egress_ips?.length ?? 0;
  const proxyCount = snapshot.proxy_expected_ips?.length ?? 0;
  if (snapshot.browser_egress_match === true) {
    return `浏览器已获取 ${browserCount} 个出口 · 代理基线 ${proxyCount} 个 · 匹配`;
  }
  if (snapshot.browser_egress_match === false) {
    return `浏览器已获取 ${browserCount} 个出口 · 代理基线 ${proxyCount} 个 · 不匹配`;
  }
  if (!browserCount && proxyCount) return `浏览器出口探测未返回 · 代理基线 ${proxyCount} 个`;
  if (browserCount && !proxyCount) return `浏览器已获取 ${browserCount} 个出口 · 缺少代理基线`;
  return "浏览器出口与代理基线均未返回";
}

function isActiveAccountBrowser(session?: AccountBrowserSession | null): boolean {
  return Boolean(session && ["starting", "ready", "closing"].includes(session.status));
}

const cookiePhaseLabels: Record<string, string> = {
  idle: "等待执行",
  renewing: "平台续期",
  persisting: "保存凭据",
  runtime: "运行时应用",
  completed: "已完成"
};

const COOKIE_RENEWAL_MANUAL_COOLDOWN_MS = 60 * 60 * 1000;

const AUTO_REPLY_CONTEXT_OPTIONS = [
  { label: "平台编码", value: "platform.code" },
  { label: "平台名称", value: "platform.name" },
  { label: "所属账户 ID", value: "account.id" },
  { label: "所属账户名称", value: "account.name" },
  { label: "消息来源用户 ID", value: "sender.id" },
  { label: "消息来源用户名称", value: "sender.name" },
  { label: "会话 ID", value: "conversation.id" },
  { label: "消息 ID", value: "message.id" },
  { label: "消息类型", value: "message.type" },
  { label: "消息内容", value: "message.text" },
  { label: "消息时间", value: "message.time" },
  { label: "会话图片", value: "message.image_urls" },
  { label: "商品 ID", value: "item.id" },
  { label: "商品名称", value: "item.title" },
  { label: "商品价格", value: "item.price" },
  { label: "商品主图", value: "item.image_url" },
  { label: "商品链接", value: "item.url" },
  { label: "订单 ID", value: "order.id" },
  { label: "订单状态", value: "order.status" },
  { label: "订单金额", value: "order.price" },
  { label: "订单数量", value: "order.quantity" },
  { label: "订单角色", value: "order.trade_role" },
  { label: "系统时间", value: "system.now" }
] as const;

const DEFAULT_AUTO_REPLY_CONTEXT_FIELDS = [
  "account.name",
  "sender.id",
  "sender.name",
  "message.text",
  "message.time",
  "item.id",
  "item.title",
  "item.price",
  "order.id",
  "order.status",
  "order.price",
  "conversation.id"
];

const ACCOUNT_TABLE_COLUMN_WIDTHS = {
  order: 56,
  account: 220,
  proxy: 376,
  cookie: 116,
  toggles: 176,
  recentOnline: 92,
  messageCount: 60,
  remark: 150,
  actions: 112
} as const;

function randomFingerprintSeed(): number {
  const values = new Uint32Array(1);
  globalThis.crypto?.getRandomValues(values);
  return values[0] || Math.floor(Math.random() * 4_294_967_294) + 1;
}

function defaultBrowserIdentity(): AccountBrowserIdentity {
  return {
    browser_engine: "system_chromium",
    fingerprint_seed: null,
    browser_version: null,
    platform: "windows",
    platform_version: "10.0.0",
    brand: "Chrome",
    language: "zh-CN",
    accept_language: "zh-CN,zh;q=0.9,en;q=0.8",
    timezone: "Asia/Shanghai",
    hardware_concurrency: null,
    spoof_canvas: true,
    spoof_webgl: true,
    spoof_audio: true,
    spoof_fonts: true,
    spoof_client_rects: true,
    webrtc_policy: "proxy_only",
    config_revision: 1,
    user_agent: null,
    dingtalk_user_agent: null,
    transport_profile: null,
    fingerprint_snapshot: null
  };
}

function browserIdentityUserAgent(identity: AccountBrowserIdentity, runtimeVersion?: string | null): string {
  const version = String(identity.browser_version || runtimeVersion || "").trim();
  if (!version) return "保存并检测浏览器后生成";
  const platformToken = identity.platform === "linux"
    ? "X11; Linux x86_64"
    : identity.platform === "macos"
      ? `Macintosh; Intel Mac OS X ${String(identity.platform_version || "14.0.0").split(".").join("_")}`
      : "Windows NT 10.0; Win64; x64";
  const base = `Mozilla/5.0 (${platformToken}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${version} Safari/537.36`;
  const suffix = {
    Chrome: "",
    Edge: ` Edg/${version}`,
    Opera: ` OPR/${version}`,
    Vivaldi: ` Vivaldi/${version}`
  }[identity.brand];
  return `${base}${suffix}`;
}

function defaultAcceptLanguage(language?: string | null): string {
  const normalized = String(language || "").trim();
  if (!normalized) return "zh-CN,zh;q=0.9,en;q=0.8";
  const base = normalized.split("-")[0];
  return base.toLowerCase() === "en"
    ? `${normalized},en;q=0.9`
    : `${normalized},${base};q=0.9,en;q=0.8`;
}

function normalizeBrowserIdentityForEditor(identity: AccountBrowserIdentity): AccountBrowserIdentity {
  const major = Number.parseInt(String(identity.browser_version || "0").split(".")[0], 10);
  if (identity.browser_engine !== "fingerprint_chromium" || major >= 144) return identity;
  return {
    ...identity,
    spoof_canvas: true,
    spoof_webgl: true,
    spoof_audio: true,
    spoof_fonts: true,
    spoof_client_rects: true
  };
}

function accountIMAvailable(account?: Account | null): boolean {
  return Boolean(account?.enabled && account.runtime.state === "online");
}

function accountDiagnosticWarnings(health?: AccountConnectionHealth): string[] {
  if (!health || !health.enabled) return [];
  const warnings: string[] = [];
  if (health.consecutive_rpc_failures > 0) {
    warnings.push(`IM RPC 连续失败 ${health.consecutive_rpc_failures} 次`);
  }
  if (health.push_queue_dropped > 0) {
    warnings.push(`IM 推送已丢弃 ${health.push_queue_dropped} 条`);
  }
  if (health.push_queue_depth >= 500) {
    warnings.push(`IM 推送积压 ${health.push_queue_depth} 条`);
  }
  if (health.sync_queue_depth >= 6) {
    warnings.push(`会话同步排队 ${health.sync_queue_depth} 个`);
  }
  if (health.side_effect_queue_dropped > 0) {
    warnings.push(`消息后处理已丢弃 ${health.side_effect_queue_dropped} 条`);
  } else if (health.side_effect_queue_depth >= 100) {
    warnings.push(`消息后处理积压 ${health.side_effect_queue_depth} 条`);
  }
  if (health.message_retry_pending > 0) {
    warnings.push(`消息持久化待重试 ${health.message_retry_pending} 条`);
  }
  if (health.last_processing_error_at) {
    const age = Date.now() - new Date(health.last_processing_error_at).getTime();
    if (Number.isFinite(age) && age >= 0 && age <= 5 * 60 * 1000) {
      warnings.push(health.last_processing_error || "最近发生消息处理错误");
    }
  }
  return warnings;
}

function applyRuntimeHealth(account: Account, runtime: Account["runtime"]): Account {
  let cookieHealth = account.cookie_health;
  if (!account.has_cookie) {
    cookieHealth = {
      state: "missing",
      message: "未配置 Cookie",
      manual_action_required: false
    };
  }
  return {
    ...account,
    runtime,
    cookie_health: cookieHealth,
    im_health: {
      state: runtime.state,
      available: account.enabled && runtime.state === "online",
      message: runtime.message,
      last_online_at: runtime.last_online_at
    }
  };
}

function applyCookieRenewalHealth(
  account: Account,
  renewal: CookieRenewalStatus
): Account {
  let cookieHealth = account.cookie_health;
  const healthMetadata = {
    last_renewed_at: renewal.last_succeeded_at,
    next_renewal_at: renewal.next_attempt_at,
    last_failed_at: renewal.last_failed_at,
    verification_source: renewal.last_verified_source,
    failure_source: renewal.last_error_source,
    error_kind: renewal.last_error_kind,
    manual_action_required: renewal.manual_action_required
  };
  if (["running", "applying"].includes(renewal.state)) {
    cookieHealth = {
      state: "renewing",
      message: renewal.message || "Cookie 正在续期",
      checked_at: renewal.last_verified_at,
      ...healthMetadata
    };
  } else if (renewal.state === "succeeded") {
    cookieHealth = {
      state: "valid",
      message: renewal.message || "Cookie 续期验证成功",
      checked_at: renewal.last_verified_at || renewal.last_succeeded_at,
      ...healthMetadata
    };
  } else if (renewal.state === "failed" && renewal.last_error_kind === "auth_expired") {
    cookieHealth = {
      state: "invalid",
      message: renewal.message || "Cookie 已失效",
      checked_at: renewal.last_failed_at,
      ...healthMetadata
    };
  } else if (renewal.state === "failed" || renewal.state === "conflict") {
    if (!account.has_cookie) {
      cookieHealth = {
        state: "missing",
        message: "未配置 Cookie",
        ...healthMetadata
      };
    } else if (renewal.last_error_kind === "runtime_apply_failed") {
      cookieHealth = {
        state: "valid",
        message: "Cookie 已更新，但 IM 运行时应用失败",
        checked_at: renewal.last_verified_at || renewal.cookie_updated_at,
        ...healthMetadata
      };
    } else if (renewal.last_verified_at || account.cookie_health.checked_at) {
      cookieHealth = {
        state: "valid",
        message:
          renewal.last_error_kind === "suspected_expired"
            ? renewal.message || "Cookie 最近一次验证有效；当前状态正在后台复核"
            : "Cookie 最近一次平台验证有效；本次续期未完成",
        checked_at: renewal.last_verified_at || account.cookie_health.checked_at,
        ...healthMetadata
      };
    } else {
      cookieHealth = {
        state: "unchecked",
        message: "本次续期未完成，Cookie 有效性待验证",
        checked_at: renewal.last_failed_at,
        ...healthMetadata
      };
    }
  } else if (renewal.last_verified_at) {
    cookieHealth = {
      state: "valid",
      message: renewal.message || "最近一次平台 Cookie 验证成功",
      checked_at: renewal.last_verified_at,
      ...healthMetadata
    };
  }
  return {
    ...account,
    cookie_health: cookieHealth,
    cookie_updated_at: renewal.cookie_updated_at,
    cookie_update_source: renewal.cookie_update_source
  };
}

function cookieRenewalIsCoolingDown(status?: CookieRenewalStatus | null) {
  if (!status?.last_succeeded_at) {
    return false;
  }
  const elapsed = Date.now() - apiTimeToEpochMs(status.last_succeeded_at);
  return elapsed >= 0 && elapsed < COOKIE_RENEWAL_MANUAL_COOLDOWN_MS;
}

function proxyIPv4Location(proxy?: ProxyResource): string {
  if (!proxy) return "-";
  const parts = [proxy.exit_country, proxy.exit_region, proxy.exit_city, proxy.exit_isp]
    .filter((value, index, values): value is string => Boolean(value) && values.indexOf(value) === index);
  return parts.join(" · ") || "未解析";
}

function proxyIPv6Location(proxy?: ProxyResource): string {
  if (!proxy) return "-";
  const parts = [proxy.exit_ipv6_country, proxy.exit_ipv6_continent]
    .filter((value, index, values): value is string => Boolean(value) && values.indexOf(value) === index);
  return parts.join(" · ") || "未解析";
}

function proxyHasExitIP(proxy: ProxyResource): boolean {
  return Boolean(proxy.exit_ipv4 || proxy.exit_ipv6);
}

function proxyExitIPIsCurrent(proxy: ProxyResource): boolean {
  return Boolean(
    proxy.last_test_ok === true &&
      proxy.exit_checked_at &&
      proxy.last_test_at &&
      Math.abs(
        apiTimeToEpochMs(proxy.exit_checked_at) -
        apiTimeToEpochMs(proxy.last_test_at)
      ) < 1000
  );
}

function canRecallMessage(chatMessage: ChatMessage): boolean {
  const createdAt = apiTimeToEpochMs(chatMessage.created_at);
  return Boolean(
    chatMessage.direction === "outbound" &&
      chatMessage.send_status === "sent" &&
      chatMessage.message_id &&
      !chatMessage.recalled_at &&
      Number.isFinite(createdAt) &&
      Date.now() - createdAt >= -10_000 &&
      Date.now() - createdAt <= 120_000
  );
}

function productLocationKey(location: ProductLocation): string {
  return [
    location.division_id,
    location.poi_id,
    location.longitude,
    location.latitude
  ].join(":");
}

function buildRegionTree(items: ProductRegion[]): DataNode[] {
  const nodes = new Map<string, DataNode & { children: DataNode[] }>();
  items.forEach((item) => {
    nodes.set(item.region_code, {
      key: item.region_code,
      title: item.name,
      children: []
    });
  });
  const roots: DataNode[] = [];
  items.forEach((item) => {
    const node = nodes.get(item.region_code)!;
    const parent = nodes.get(item.parent_code);
    if (parent) {
      parent.children.push(node);
    } else {
      roots.push(node);
    }
  });
  return roots;
}

function productRegionPath(items: ProductRegion[], code: string): string[] {
  const byCode = new Map(items.map((item) => [item.region_code, item]));
  const path: string[] = [];
  let current = byCode.get(code);
  while (current) {
    path.unshift(current.region_code);
    current = byCode.get(current.parent_code);
  }
  return path.length ? path : [code];
}

function productRegionLocation(region: ProductRegion): ProductLocation {
  return {
    prov: region.prov,
    city: region.city,
    area: region.area,
    division_id: region.region_code,
    longitude: region.longitude,
    latitude: region.latitude,
    poi_id: "",
    poi_name: region.name
  };
}

type ProductLocationTreeNode = {
  value: string;
  title: string;
  displayLabel: string;
  searchText: string;
  selectable?: boolean;
  disabled?: boolean;
  isLeaf?: boolean;
  children?: ProductLocationTreeNode[];
};

function locationPathLabel(parts: string[]): string {
  return parts.filter((part, index) => part && parts.indexOf(part) === index).join(" / ");
}

function buildProductLocationTree(
  regions: ProductRegion[],
  groups: PublishAddressGroup[],
  locations: ProductLocationOption[],
  options: { regionLoading: boolean; preciseLoading: boolean; preciseLoaded: boolean }
): ProductLocationTreeNode[] {
  const regionNodes = new Map<string, ProductLocationTreeNode>();
  regions.forEach((region) => {
    const path = locationPathLabel([region.prov, region.city, region.area || region.name]);
    regionNodes.set(region.region_code, {
      value: `region:${region.region_code}`,
      title: region.name,
      displayLabel: `指定区域 / ${path || region.name}`,
      searchText: `${region.name} ${region.prov} ${region.city} ${region.area}`.toLowerCase(),
      selectable: region.selectable,
      children: []
    });
  });
  const regionRoots: ProductLocationTreeNode[] = [];
  regions.forEach((region) => {
    const node = regionNodes.get(region.region_code)!;
    const parent = regionNodes.get(region.parent_code);
    if (parent) {
      parent.children!.push(node);
    } else {
      regionRoots.push(node);
    }
  });
  regionNodes.forEach((node) => {
    if (!node.children?.length) {
      delete node.children;
      node.isLeaf = true;
    }
  });

  const groupChildren: ProductLocationTreeNode[] = groups
    .filter((group) => group.enabled && group.address_count > 0)
    .map((group) => ({
      value: `group:${group.group_id}`,
      title: `${group.name}（${group.address_count}）`,
      displayLabel: `地址组随机 / ${group.name}`,
      searchText: group.name.toLowerCase(),
      isLeaf: true
    }));
  if (!groupChildren.length) {
    groupChildren.push({
      value: "placeholder:group",
      title: "没有可用地址组",
      displayLabel: "没有可用地址组",
      searchText: "",
      isLeaf: true,
      disabled: true
    });
  }

  let preciseChildren: ProductLocationTreeNode[] | undefined;
  if (locations.length) {
    preciseChildren = locations.map((location) => ({
      value: `precise:${productLocationKey(location)}`,
      title: location.label,
      displayLabel: `精准地址 / ${location.label}`,
      searchText: location.label.toLowerCase(),
      isLeaf: true
    }));
  } else if (options.preciseLoading || options.preciseLoaded) {
    preciseChildren = [{
      value: "placeholder:precise",
      title: options.preciseLoading ? "正在加载精准地址" : "账号未返回可用所在地",
      displayLabel: "精准地址",
      searchText: "",
      isLeaf: true,
      disabled: true
    }];
  }

  const regionChildren = regionRoots.length
    ? regionRoots
    : [{
        value: "placeholder:region",
        title: options.regionLoading ? "正在加载全国行政区域" : "行政区域目录不可用",
        displayLabel: "指定区域",
        searchText: "",
        isLeaf: true,
        disabled: true
      }];

  return [
    {
      value: "mode:account_default",
      title: "账户默认",
      displayLabel: "账户默认",
      searchText: "账户默认",
      isLeaf: true
    },
    {
      value: "mode:group_random",
      title: "地址组随机",
      displayLabel: "地址组随机",
      searchText: "地址组随机",
      selectable: false,
      isLeaf: false,
      children: groupChildren
    },
    {
      value: "mode:region",
      title: "指定区域",
      displayLabel: "指定区域",
      searchText: "指定区域",
      selectable: false,
      isLeaf: false,
      children: regionChildren
    },
    {
      value: "mode:selected",
      title: "精准地址",
      displayLabel: "精准地址",
      searchText: "精准地址",
      selectable: false,
      isLeaf: false,
      children: preciseChildren
    }
  ];
}

function cookieSourceLabel(source?: string | null) {
  return source ? cookieSourceLabels[source] || source : "-";
}

function formatDuration(value?: number | null) {
  if (value === null || value === undefined) {
    return "-";
  }
  return value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(1)} 秒`;
}

function formatCountdown(expiresAt: string, now: number) {
  const remainingSeconds = Math.max(0, Math.ceil((apiTimeToEpochMs(expiresAt) - now) / 1000));
  if (remainingSeconds <= 0) return "即将关闭";
  const hours = Math.floor(remainingSeconds / 3600);
  const minutes = Math.floor((remainingSeconds % 3600) / 60);
  const seconds = remainingSeconds % 60;
  return hours > 0
    ? `${hours}小时${String(minutes).padStart(2, "0")}分${String(seconds).padStart(2, "0")}秒`
    : `${minutes}分${String(seconds).padStart(2, "0")}秒`;
}

function formatSecondsDuration(value: number) {
  const seconds = Math.max(0, Math.round(value));
  if (seconds >= 3600) {
    const hours = seconds / 3600;
    return `${Number.isInteger(hours) ? hours : hours.toFixed(1)} 小时`;
  }
  if (seconds >= 60) {
    const minutes = seconds / 60;
    return `${Number.isInteger(minutes) ? minutes : minutes.toFixed(1)} 分钟`;
  }
  return `${seconds} 秒`;
}

function loginSourceLabel(source?: string | null) {
  const labels: Record<string, string> = {
    remote_addr: "直连",
    cf_connecting_ip: "Cloudflare",
    true_client_ip: "True-Client-IP",
    x_real_ip: "X-Real-IP",
    x_forwarded_for: "X-Forwarded-For"
  };
  return source ? labels[source] || source : "未知";
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) {
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function playDefaultMessageDing(context: AudioContext) {
  const startAt = context.currentTime + 0.01;
  const playTone = (frequency: number, offset: number) => {
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    const toneAt = startAt + offset;
    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(frequency, toneAt);
    gain.gain.setValueAtTime(0.0001, toneAt);
    gain.gain.exponentialRampToValueAtTime(0.22, toneAt + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, toneAt + 0.28);
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start(toneAt);
    oscillator.stop(toneAt + 0.3);
  };
  playTone(880, 0);
  playTone(660, 0.18);
}

function rawRenderItemIdLink(itemId?: string | null, itemUrl?: string | null) {
  if (!itemId) return "-";
  const normalizedUrl = itemUrl?.trim();
  const targetUrl = normalizedUrl && /^https?:\/\//i.test(normalizedUrl)
    ? normalizedUrl
    : `https://www.goofish.com/item?id=${encodeURIComponent(itemId)}`;
  return (
    <Tooltip title="打开闲鱼商品详情">
      <Typography.Link
        className="item-id-text-link"
        href={targetUrl}
        target="_blank"
        rel="noopener noreferrer"
        copyable={{ text: itemId, tooltips: ["复制商品 ID", "已复制"] }}
      >
        {itemId}
      </Typography.Link>
    </Tooltip>
  );
}

function cookieStateLabel(state?: CookieRenewalStatus["state"]) {
  return state === "succeeded"
    ? "成功"
    : state === "running"
      ? "续期中"
      : state === "applying"
        ? "应用中"
        : state === "failed"
          ? "失败"
          : state === "conflict"
            ? "已跳过覆盖"
            : "等待执行";
}

function cookieStateColor(state?: CookieRenewalStatus["state"]) {
  return state === "succeeded"
    ? "green"
    : state === "running" || state === "applying"
      ? "blue"
      : state === "failed"
        ? "red"
        : state === "conflict"
          ? "orange"
          : "default";
}

function conversationIdentity(conversation: Conversation): string {
  return (
    conversation.conversation_key ||
    `${conversation.platform || "xianyu"}:${conversation.account_id}:${conversation.conversation_id}`
  );
}

function platformName(platform?: string | null): string {
  return platform === "xianyu" || !platform ? "闲鱼" : platform;
}

type AccountLabelSource = {
  account_id?: string | null;
  account_name?: string | null;
  display_name?: string | null;
  platform_display_name?: string | null;
};

function rawPlatformAccountName(account?: AccountLabelSource | null): string {
  return account?.platform_display_name?.trim() || "用户名待同步";
}

function rawAccountDisplayName(account?: AccountLabelSource | null): string {
  return (
    account?.platform_display_name?.trim() ||
    account?.display_name?.trim() ||
    account?.account_name?.trim() ||
    account?.account_id ||
    "闲鱼账户"
  );
}

function rawBrowserEngineLabel(
  engine?: BrowserEngine | null,
  systemLabel = "系统 Chromium"
): string {
  return engine === "fingerprint_chromium" ? "Fingerprint Chromium" : systemLabel;
}

function platformTagColor(platform?: string | null): string {
  return platform === "xianyu" || !platform ? "gold" : "purple";
}

const orderStatusMeta: Record<OrderStatus, { label: string; color: string }> = {
  pending_payment: { label: "待付款", color: "gold" },
  waiting_seller_delivery: { label: "待卖家发货", color: "blue" },
  paid_waiting_delivery: { label: "待发货", color: "blue" },
  shipped: { label: "已发货", color: "cyan" },
  completed: { label: "已完成", color: "green" },
  closed: { label: "已关闭", color: "default" },
  refunding: { label: "退款中", color: "orange" },
  refunded: { label: "已退款", color: "red" },
  unknown: { label: "待确认", color: "default" }
};

function renderOrderStatus(status: OrderStatus) {
  const meta = orderStatusMeta[status] || orderStatusMeta.unknown;
  return <Tag color={meta.color}>{meta.label}</Tag>;
}

function renderRefundStatus(status?: string | null) {
  const normalized = String(status || "").trim().toLowerCase();
  const meta: Record<string, { label: string; color: string }> = {
    pending: { label: "退款待处理", color: "orange" },
    processing: { label: "退款处理中", color: "orange" },
    refunding: { label: "退款处理中", color: "orange" },
    requested: { label: "退款待处理", color: "orange" },
    rejected: { label: "退款已拒绝", color: "default" },
    refunded: { label: "退款成功", color: "red" },
    success: { label: "退款成功", color: "red" },
    completed: { label: "退款成功", color: "red" }
  };
  const selected = meta[normalized];
  return selected ? <Tag color={selected.color}>{selected.label}</Tag> : <Tag>无退款</Tag>;
}

function conversationDirection(conversation: Conversation): {
  label: string;
  className: string;
} {
  const direction = conversation.last_activity_direction ?? conversation.last_message_direction;
  if (direction === "outbound") {
    return { label: "我", className: "outbound" };
  }
  if (direction === "inbound") {
    return { label: "客", className: "inbound" };
  }
  return { label: "系统", className: "system" };
}

function mergeConversationRecords(
  items: Conversation[],
  updates: Conversation[]
): Conversation[] {
  const merged = new Map(items.map((item) => [conversationIdentity(item), item]));
  for (const next of updates) {
    const identity = conversationIdentity(next);
    const previous = merged.get(identity);
    const platformUnreadDelta = previous
      ? Math.max(
          0,
          (next.platform_unread_count ?? next.unread_count ?? 0) -
            (previous.platform_unread_count ?? previous.unread_count ?? 0)
        )
      : 0;
    const candidate = {
      ...previous,
      ...next,
      viewer_unread_count:
        next.viewer_unread_count ??
        (previous
          ? (previous.viewer_unread_count ?? previous.platform_unread_count ?? 0) +
            platformUnreadDelta
          : next.platform_unread_count ?? next.unread_count ?? 0)
    };
    merged.set(identity, previous && shallowRecordEqual(previous, candidate) ? previous : candidate);
  }
  const result = [...merged.values()].sort(compareConversations);
  return result.length === items.length && result.every((item, index) => item === items[index])
    ? items
    : result;
}

function shallowRecordEqual<T extends object>(left: T, right: T): boolean {
  const keys = new Set<keyof T>([
    ...(Object.keys(left) as Array<keyof T>),
    ...(Object.keys(right) as Array<keyof T>)
  ]);
  return [...keys].every((key) => Object.is(left[key], right[key]));
}

function conversationUnreadCount(conversation: Conversation): number {
  return conversation.viewer_unread_count ?? conversation.platform_unread_count ?? 0;
}

function parseTimestamp(value?: string | null): number {
  if (!value) {
    return 0;
  }
  const timestamp = apiTimeToEpochMs(value);
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function compareConversations(left: Conversation, right: Conversation): number {
  const activityDifference =
    parseTimestamp(right.last_activity_at ?? right.last_message_at ?? right.updated_at) -
    parseTimestamp(left.last_activity_at ?? left.last_message_at ?? left.updated_at);
  return (
    activityDifference || conversationIdentity(left).localeCompare(conversationIdentity(right))
  );
}

function mergeChatMessageRecords(
  items: ChatMessage[],
  updates: ChatMessage[]
): ChatMessage[] {
  const merged = new Map(
    [...items, ...updates].map((item) => [item.message_pk, item])
  );
  return [...merged.values()].sort(
    (left, right) => {
      const leftTimestamp = left.created_at_ms ?? parseTimestamp(left.created_at);
      const rightTimestamp = right.created_at_ms ?? parseTimestamp(right.created_at);
      return leftTimestamp - rightTimestamp || left.message_pk.localeCompare(right.message_pk);
    }
  );
}

type AdminMenuKey =
  | "dashboard"
  | "users"
  | "accounts"
  | "conversations"
  | "auto-reply"
  | "delivery"
  | "product-management"
  | "products"
  | "events"
  | "tasks"
  | "audit"
  | "settings";

interface UserSubmissionSnapshot {
  targetUser: AdminUser | null;
  values: {
    username: string;
    password: string;
    role: AdminUser["role"];
    enabled: boolean;
  };
  mutationKey: string;
  accessToken: string;
}

type SettingsTabKey =
  | "users"
  | "proxies"
  | "message-services"
  | "browsers"
  | "addresses"
  | "ai"
  | "tasks"
  | "audit";

const settingsTabLabels: Record<SettingsTabKey, string> = {
  users: "用户与登录",
  proxies: "代理管理",
  "message-services": "消息服务",
  browsers: "浏览器运行环境",
  addresses: "地址库",
  ai: "AI 服务",
  tasks: "后台任务",
  audit: "审计日志"
};

function settingsTabFromSearch(
  search: string,
  isAdmin: boolean,
  canMutate: boolean
): SettingsTabKey {
  const requested = new URLSearchParams(search).get("tab");
  if (requested === "users" || requested === "proxies") {
    return requested;
  }
  if (requested === "addresses" && canMutate) {
    return requested;
  }
  if (isAdmin && requested && requested in settingsTabLabels) {
    return requested as SettingsTabKey;
  }
  return "users";
}

const menuTitles: Record<AdminMenuKey, string> = {
  dashboard: "控制台",
  users: "用户管理",
  accounts: "平台账户",
  conversations: "会话消息",
  "auto-reply": "自动回复",
  delivery: "订单管理",
  "product-management": "商品管理",
  products: "商品发布",
  events: "运行事件",
  tasks: "后台任务",
  audit: "审计日志",
  settings: "系统设置"
};

const menuPaths: Record<AdminMenuKey, string> = {
  dashboard: "/dashboard",
  users: "/users",
  accounts: "/accounts",
  conversations: "/conversations",
  "auto-reply": "/auto-reply",
  delivery: "/delivery",
  "product-management": "/product-management",
  products: "/products",
  events: "/events",
  tasks: "/tasks",
  audit: "/audit",
  settings: "/settings"
};

const pathMenus = Object.fromEntries(
  Object.entries(menuPaths).map(([key, path]) => [path, key as AdminMenuKey])
) as Record<string, AdminMenuKey>;

const adminMenus = new Set<AdminMenuKey>(["users", "tasks", "audit"]);
const viewerMenus = new Set<AdminMenuKey>([
  "dashboard",
  "accounts",
  "conversations",
  "settings"
]);

export default function App() {
  const { message, notification } = AntApp.useApp();
  const location = useLocation();
  const navigate = useNavigate();
  const [authenticated, setAuthenticated] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);
  const [setupInitialized, setSetupInitialized] = useState(true);
  const [clientAccess, setClientAccess] = useState<ClientAccessInfo | null>(null);
  const [currentUser, setCurrentUser] = useState<AdminUser | null>(null);
  const [privacySaving, setPrivacySaving] = useState(false);
  const privacyMaskEnabled = Boolean(currentUser?.privacy_mask_enabled);
  const [loginLoading, setLoginLoading] = useState(false);
  const [activeMenu, setActiveMenu] = useState<AdminMenuKey>("dashboard");
  const [navigationOpenKeys, setNavigationOpenKeys] = useState<string[]>([]);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [compactLayout, setCompactLayout] = useState(false);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [pendingUserMutationKeys, setPendingUserMutationKeys] = useState<Set<string>>(
    () => new Set()
  );
  const pendingUserMutationKeysRef = useRef<Set<string>>(new Set());
  const [userDrawerOpen, setUserDrawerOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountReordering, setAccountReordering] = useState(false);
  const [processHealth, setProcessHealth] = useState<ProcessHealth | null>(null);
  const [runtimeHealth, setRuntimeHealth] = useState<AccountConnectionHealth[]>([]);
  const [proxies, setProxies] = useState<ProxyResource[]>([]);
  const [proxyListLoading, setProxyListLoading] = useState(false);
  const [proxySaving, setProxySaving] = useState(false);
  const [testingProxyIds, setTestingProxyIds] = useState<Set<string>>(() => new Set());
  const [queuedProxyIds, setQueuedProxyIds] = useState<Set<string>>(() => new Set());
  const [deletingProxyIds, setDeletingProxyIds] = useState<Set<string>>(() => new Set());
  const [selectedProxyIds, setSelectedProxyIds] = useState<string[]>([]);
  const [proxyBatchProgress, setProxyBatchProgress] = useState<{
    completed: number;
    total: number;
  } | null>(null);
  const [accountTableWidth, setAccountTableWidth] = useState(0);
  const [proxyDrawerOpen, setProxyDrawerOpen] = useState(false);
  const [editingProxy, setEditingProxy] = useState<ProxyResource | null>(null);
  const [chatwootConfig, setChatwootConfig] = useState<ChatwootConfig | null>(null);
  const [chatwootLoading, setChatwootLoading] = useState(false);
  const [chatwootSaving, setChatwootSaving] = useState(false);
  const [chatwootTesting, setChatwootTesting] = useState(false);
  const [chatwootAlertTesting, setChatwootAlertTesting] = useState(false);
  const [webNotificationConfig, setWebNotificationConfig] =
    useState<WebNotificationConfig | null>(null);
  const [webNotificationLoading, setWebNotificationLoading] = useState(false);
  const [webNotificationSaving, setWebNotificationSaving] = useState(false);
  const [webNotificationUploading, setWebNotificationUploading] = useState(false);
  const [webNotificationUnlocked, setWebNotificationUnlocked] = useState(false);
  const [loading, setLoading] = useState(false);
  const [recoveringAccountId, setRecoveringAccountId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<Account | null>(null);
  const [accountEditorTab, setAccountEditorTab] = useState("basic");
  const [editingOriginalCookie, setEditingOriginalCookie] = useState<string | null>(null);
  const [accountCookieLoading, setAccountCookieLoading] = useState(false);
  const [qrLogin, setQrLogin] = useState<XianyuQRStatus | null>(null);
  const [qrLoginValues, setQrLoginValues] = useState<{
    account_id?: string | null;
    remark?: string | null;
    client_request_id?: string | null;
    proxy_id?: string | null;
    browser_identity?: AccountBrowserIdentity | null;
  } | null>(null);
  const [qrModalOpen, setQrModalOpen] = useState(false);
  const [qrLoading, setQrLoading] = useState(false);
  const [qrBrowserVerification, setQrBrowserVerification] =
    useState<QRBrowserVerification | null>(null);
  const [qrBrowserOpen, setQrBrowserOpen] = useState(false);
  const [qrBrowserLoading, setQrBrowserLoading] = useState(false);
  const [qrBrowserSocketUrl, setQrBrowserSocketUrl] = useState("");
  const [qrBrowserConnected, setQrBrowserConnected] = useState(false);
  const [cookieRenewalAccount, setCookieRenewalAccount] = useState<Account | null>(null);
  const [cookieRenewalStatus, setCookieRenewalStatus] = useState<CookieRenewalStatus | null>(null);
  const [cookieRenewalOpen, setCookieRenewalOpen] = useState(false);
  const [cookieRenewalLoading, setCookieRenewalLoading] = useState(false);
  const [imVerificationAccount, setIMVerificationAccount] = useState<Account | null>(null);
  const [imVerification, setIMVerification] = useState<IMVerification | null>(null);
  const [imVerificationOpen, setIMVerificationOpen] = useState(false);
  const [imVerificationLoading, setIMVerificationLoading] = useState(false);
  const [imVerificationSocketUrl, setIMVerificationSocketUrl] = useState("");
  const [imVerificationConnected, setIMVerificationConnected] = useState(false);
  const [accountBrowserAccount, setAccountBrowserAccount] = useState<Account | null>(null);
  const [accountBrowserSession, setAccountBrowserSession] =
    useState<AccountBrowserSession | null>(null);
  const [accountBrowserOpen, setAccountBrowserOpen] = useState(false);
  const [accountBrowserLoading, setAccountBrowserLoading] = useState(false);
  const [accountBrowserSocketUrl, setAccountBrowserSocketUrl] = useState("");
  const [accountBrowserConnected, setAccountBrowserConnected] = useState(false);
  const [accountBrowserError, setAccountBrowserError] = useState("");
  const [accountBrowserClearing, setAccountBrowserClearing] = useState(false);
  const [accountBrowserDetecting, setAccountBrowserDetecting] = useState(false);
  const [accountBrowserPasteText, setAccountBrowserPasteText] = useState("");
  const [accountBrowserPasting, setAccountBrowserPasting] = useState(false);
  const [accountBrowserClock, setAccountBrowserClock] = useState(() => Date.now());
  const accountBrowserActivitySentAtRef = useRef(0);
  const [accountBrowserStatuses, setAccountBrowserStatuses] = useState<
    Record<string, AccountBrowserSession>
  >({});
  const [browserProfileDrawerOpen, setBrowserProfileDrawerOpen] = useState(false);
  const [browserProfiles, setBrowserProfiles] = useState<BrowserProfile[]>([]);
  const [browserProfilesLoading, setBrowserProfilesLoading] = useState(false);
  const [browserProfileStoppingKey, setBrowserProfileStoppingKey] = useState<string | null>(null);
  const [browserProfileClearingKey, setBrowserProfileClearingKey] = useState<string | null>(null);
  const [browserRuntime, setBrowserRuntime] = useState<BrowserRuntimeSetting | null>(null);
  const [browserRuntimeLoading, setBrowserRuntimeLoading] = useState(false);
  const [browserRuntimeAction, setBrowserRuntimeAction] = useState<string | null>(null);
  const browserEnvironmentRows = useMemo<BrowserProfile[]>(() => {
    const accountProfiles = new Map(
      browserProfiles
        .filter((profile) => profile.account_id)
        .map((profile) => [profile.account_id!, profile])
    );
    const accountRows = accounts.map((account) => {
      const profile = accountProfiles.get(account.account_id);
      if (profile) return profile;
      const session = accountBrowserStatuses[account.account_id];
      const browserIdentity = account.browser_identity ?? defaultBrowserIdentity();
      return {
        profile_key: `account:${account.account_id}`,
        directory_name: "尚未创建",
        profile_type: "account" as const,
        account_id: account.account_id,
        account_name: account.display_name,
        account_exists: true,
        size_bytes: 0,
        created_at: account.created_at,
        updated_at: account.updated_at,
        status: isActiveAccountBrowser(session) ? "running" as const : "stopped" as const,
        session_id: session?.session_id,
        session_purpose: "account_browser",
        vnc_available: Boolean(session?.vnc_available),
        current_url: session?.current_url,
        manageable: false,
        browser_engine: browserIdentity.browser_engine,
        config_revision: browserIdentity.config_revision
      };
    });
    const extraRows = browserProfiles.filter(
      (profile) => !profile.account_id || !accounts.some((account) => account.account_id === profile.account_id)
    );
    return [...accountRows, ...extraRows];
  }, [accountBrowserStatuses, accounts, browserProfiles]);
  const [runtimeLogAccount, setRuntimeLogAccount] = useState<Account | null>(null);
  const [runtimeLogOpen, setRuntimeLogOpen] = useState(false);
  const [events, setEvents] = useState<RuntimeEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);
  const runtimeLogRequestRef = useRef(0);
  const [conversationAccount, setConversationAccount] = useState<Account | null>(null);
  const [conversationAccountFilter, setConversationAccountFilter] = useState("all");
  const [conversationStatusFilter, setConversationStatusFilter] =
    useState<ConversationStatusFilter>("all");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationSyncStatuses, setConversationSyncStatuses] = useState<
    ConversationAccountSync[]
  >([]);
  const [conversationsLoading, setConversationsLoading] = useState(false);
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null);
  const [mobileConversationDetailOpen, setMobileConversationDetailOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const selectedConversationRef = useRef<Conversation | null>(null);
  const accountsRef = useRef<Account[]>([]);
  const activeMenuRef = useRef<AdminMenuKey>(activeMenu);
  const compactLayoutRef = useRef(compactLayout);
  const mobileConversationDetailOpenRef = useRef(mobileConversationDetailOpen);
  const conversationRequestRef = useRef(0);
  const messageRequestRef = useRef(0);
  const messageListRef = useRef<HTMLDivElement | null>(null);
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const composerNoticeTimerRef = useRef<number | null>(null);
  const productImageInputRef = useRef<HTMLInputElement | null>(null);
  const productImagePreviewUrlsRef = useRef<Record<string, string>>({});
  const productImageDragDepthRef = useRef(0);
  const productAccountIdRef = useRef<string | null>(null);
  const productManagerAccountIdRef = useRef<string | null>(null);
  const productLocationRequestRef = useRef(0);
  const productManagerRequestRef = useRef(0);
  const orderManagerRequestRef = useRef(0);
  const orderScopeRef = useRef<OrderScope>("bought");
  const conversationListViewportRef = useRef<HTMLDivElement | null>(null);
  const accountTableViewportRef = useRef<HTMLDivElement | null>(null);
  const accountCookieRequestRef = useRef(0);
  const qrClientRequestIdRef = useRef(createClientRequestId("qr-login"));
  const accountBrowserRequestRef = useRef(0);
  const stickMessagesToBottomRef = useRef(true);
  const forceBottomConversationRef = useRef<string | null>(null);
  const historyScrollAnchorRef = useRef<{ height: number; top: number } | null>(null);
  const historyRequestRef = useRef(0);
  const conversationPageWasActiveRef = useRef(false);
  const messageSyncAtRef = useRef(new Map<string, number>());
  const realtimeConnectedRef = useRef(false);
  const realtimeLastEventAtRef = useRef(0);
  const workspaceBootstrappedRef = useRef(false);
  const webNotificationConfigRef = useRef<WebNotificationConfig | null>(null);
  const webNotificationAudioContextRef = useRef<AudioContext | null>(null);
  const webNotificationAudioBytesRef = useRef<ArrayBuffer | null>(null);
  const webNotificationAudioBufferRef = useRef<AudioBuffer | null>(null);
  const webNotificationAudioLoadRef = useRef(0);
  const notifiedMessageIdsRef = useRef(new Map<string, number>());
  const [chatMessagesLoading, setChatMessagesLoading] = useState(false);
  const [olderMessagesLoading, setOlderMessagesLoading] = useState(false);
  const [pendingImages, setPendingImages] = useState<PendingImage[]>([]);
  const [composerNotice, setComposerNotice] = useState<string | null>(null);
  const [quickPhrases, setQuickPhrases] = useState<QuickPhrase[]>([]);
  const [quickPhraseSearch, setQuickPhraseSearch] = useState("");
  const [quickPhrasePopoverOpen, setQuickPhrasePopoverOpen] = useState(false);
  const [quickPhraseManagerOpen, setQuickPhraseManagerOpen] = useState(false);
  const [editingQuickPhrase, setEditingQuickPhrase] = useState<QuickPhrase | null>(null);
  const [quickPhraseSaving, setQuickPhraseSaving] = useState(false);
  const [platformBlacklist, setPlatformBlacklistState] = useState<boolean | null>(null);
  const [platformBlacklistLoading, setPlatformBlacklistLoading] = useState(false);
  const [manualTakeoverUpdating, setManualTakeoverUpdating] = useState(false);
  const [recallingMessagePk, setRecallingMessagePk] = useState<string | null>(null);
  const [messageNextCursor, setMessageNextCursor] = useState<number | null>(null);
  const [messageHasMore, setMessageHasMore] = useState(false);
  const [conversationListHeight, setConversationListHeight] = useState(0);
  const [orders, setOrders] = useState<XianyuOrder[]>([]);
  const [conversationOrders, setConversationOrders] = useState<XianyuOrder[]>([]);
  const [orderScope, setOrderScope] = useState<OrderScope>("bought");
  const [orderAccountFilter, setOrderAccountFilter] = useState("all");
  const [orderStatusFilter, setOrderStatusFilter] = useState("all");
  const [orderKeyword, setOrderKeyword] = useState("");
  const [orderManagerAccounts, setOrderManagerAccounts] = useState<OrderAccountSummary[]>([]);
  const [orderSyncRuns, setOrderSyncRuns] = useState<OrderSyncRun[]>([]);
  const [orderManagerAction, setOrderManagerAction] = useState<string | null>(null);
  const [orderSettingsOpen, setOrderSettingsOpen] = useState(false);
  const [orderHistoryOpen, setOrderHistoryOpen] = useState(false);
  const [orderDrawerOpen, setOrderDrawerOpen] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState<OrderDetail | null>(null);
  const [orderPreview, setOrderPreview] = useState<OrderDeliveryPreview | null>(null);
  const [orderTemplateId, setOrderTemplateId] = useState<string | undefined>();
  const [orderDeliveryContent, setOrderDeliveryContent] = useState("");
  const [orderRateFeedback, setOrderRateFeedback] = useState("不错的买家，期待再次交易");
  const [orderOperationAction, setOrderOperationAction] = useState<OrderAction | null>(null);
  const [orderLoading, setOrderLoading] = useState(false);
  const [autoReplyRules, setAutoReplyRules] = useState<AutoReplyRule[]>([]);
  const [autoReplyLogs, setAutoReplyLogs] = useState<AutoReplyLog[]>([]);
  const [autoReplyRuleIssues, setAutoReplyRuleIssues] = useState<AutoReplyRuleIssue[]>([]);
  const [autoReplyLoading, setAutoReplyLoading] = useState(false);
  const [autoReplyReordering, setAutoReplyReordering] = useState(false);
  const [autoReplyUpdatingRuleId, setAutoReplyUpdatingRuleId] = useState<string | null>(null);
  const [autoReplyPreviewOpen, setAutoReplyPreviewOpen] = useState(false);
  const [autoReplyPreviewLoading, setAutoReplyPreviewLoading] = useState(false);
  const [autoReplyPreviewResult, setAutoReplyPreviewResult] = useState<AutoReplyPreviewResult | null>(null);
  const [editingRule, setEditingRule] = useState<AutoReplyRule | null>(null);
  const [ruleDrawerOpen, setRuleDrawerOpen] = useState(false);
  const [accountAutoReplyUpdatingId, setAccountAutoReplyUpdatingId] = useState<string | null>(null);
  const [accountWorkspaceVisibilityUpdatingKeys, setAccountWorkspaceVisibilityUpdatingKeys] =
    useState<Set<string>>(() => new Set());
  const [aiProvider, setAIProvider] = useState<AIProviderSetting | null>(null);
  const [aiProviderLoading, setAIProviderLoading] = useState(false);
  const [aiProviderSaving, setAIProviderSaving] = useState(false);
  const [deliveryAccount, setDeliveryAccount] = useState<Account | null>(null);
  const [deliveryTemplates, setDeliveryTemplates] = useState<DeliveryTemplate[]>([]);
  const [deliveryRecords, setDeliveryRecords] = useState<DeliveryRecord[]>([]);
  const [deliveryPreflight, setDeliveryPreflight] = useState<DeliveryPreflightResult | null>(null);
  const [deliveryLoading, setDeliveryLoading] = useState(false);
  const [editingDeliveryTemplate, setEditingDeliveryTemplate] = useState<DeliveryTemplate | null>(null);
  const [preparedDelivery, setPreparedDelivery] = useState<DeliveryRecord | null>(null);
  const [productAccount, setProductAccount] = useState<Account | null>(null);
  const [productDrafts, setProductDrafts] = useState<ProductDraft[]>([]);
  const [productImageAssets, setProductImageAssets] = useState<ProductImageAsset[]>([]);
  const [productImagePreviewUrls, setProductImagePreviewUrls] = useState<Record<string, string>>({});
  const [productImageUploading, setProductImageUploading] = useState(false);
  const [productImageDropActive, setProductImageDropActive] = useState(false);
  const [productImagePreviewOpen, setProductImagePreviewOpen] = useState(false);
  const [productImagePreviewIndex, setProductImagePreviewIndex] = useState(0);
  const [productLocations, setProductLocations] = useState<ProductLocationOption[]>([]);
  const [productLocationResult, setProductLocationResult] = useState<ProductLocationListResult | null>(null);
  const [productLocationLoading, setProductLocationLoading] = useState(false);
  const [productRegionCatalog, setProductRegionCatalog] = useState<ProductRegionCatalog | null>(null);
  const [productRegionLoading, setProductRegionLoading] = useState(false);
  const [productTasks, setProductTasks] = useState<ProductPublishTask[]>([]);
  const [productLoading, setProductLoading] = useState(false);
  const [productPublishingDraftId, setProductPublishingDraftId] = useState<string | null>(null);
  const [editingProductDraft, setEditingProductDraft] = useState<ProductDraft | null>(null);
  const [productPublishDrawerOpen, setProductPublishDrawerOpen] = useState(false);
  const [productUploadSessionId, setProductUploadSessionId] = useState<string | null>(null);
  const [productPublishSubmitting, setProductPublishSubmitting] = useState(false);
  const [productShippingOpen, setProductShippingOpen] = useState(false);
  const [productShippingError, setProductShippingError] = useState<string | null>(null);
  const [productRetryingTaskId, setProductRetryingTaskId] = useState<string | null>(null);
  const [productManagerAccounts, setProductManagerAccounts] = useState<ProductAccountSummary[]>([]);
  const [productManagerAccountId, setProductManagerAccountId] = useState<string | null>(null);
  const [managedProducts, setManagedProducts] = useState<ManagedProductItem[]>([]);
  const [productOperationRuns, setProductOperationRuns] = useState<ProductOperationRun[]>([]);
  const [productManagerLoading, setProductManagerLoading] = useState(false);
  const [productManagerAction, setProductManagerAction] = useState<string | null>(null);
  const [productManagerSelection, setProductManagerSelection] = useState<string[]>([]);
  const [productManagerStatus, setProductManagerStatus] = useState<ProductManagerStatusFilter>("all");
  const [productManagerKeyword, setProductManagerKeyword] = useState("");
  const [productManagerSettingsOpen, setProductManagerSettingsOpen] = useState(false);
  const [productManagerHistoryOpen, setProductManagerHistoryOpen] = useState(false);
  const [productAddressGroups, setProductAddressGroups] = useState<PublishAddressGroup[]>([]);
  const [addressGroups, setAddressGroups] = useState<PublishAddressGroup[]>([]);
  const [selectedAddressGroupId, setSelectedAddressGroupId] = useState<string | null>(null);
  const [publishAddresses, setPublishAddresses] = useState<PublishAddress[]>([]);
  const [addressRegionCodes, setAddressRegionCodes] = useState<string[]>([]);
  const [addressRegionSaving, setAddressRegionSaving] = useState(false);
  const [addressLibraryLoading, setAddressLibraryLoading] = useState(false);
  const [addressGroupModalOpen, setAddressGroupModalOpen] = useState(false);
  const [editingAddressGroup, setEditingAddressGroup] = useState<PublishAddressGroup | null>(null);
  const [addressImportModalOpen, setAddressImportModalOpen] = useState(false);
  const [addressImportLocations, setAddressImportLocations] = useState<ProductLocationOption[]>([]);
  const [addressImportLoading, setAddressImportLoading] = useState(false);
  const [backgroundTasks, setBackgroundTasks] = useState<BackgroundTask[]>([]);
  const [backgroundTasksLoading, setBackgroundTasksLoading] = useState(false);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [loginForm] = Form.useForm<LoginFormValues>();
  const [userForm] = Form.useForm<UserFormValues>();
  const [form] = Form.useForm<AccountFormValues>();
  const selectedBrowserEngine = Form.useWatch(
    ["browser_identity", "browser_engine"],
    form
  ) ?? "system_chromium";
  const selectedBrowserIdentity = Form.useWatch("browser_identity", form);
  const [proxyForm] = Form.useForm<ProxyFormValues>();
  const [chatwootForm] = Form.useForm<ChatwootConfigFormValues>();
  const chatwootCallbackUrlValue = Form.useWatch("callback_url", chatwootForm);
  const [sendForm] = Form.useForm<SendTextFormValues>();
  const [quickPhraseForm] = Form.useForm<QuickPhraseFormValues>();
  const [ruleForm] = Form.useForm<AutoReplyRuleFormValues>();
  const [autoReplyPreviewForm] = Form.useForm<AutoReplyPreviewRequest>();
  const [aiProviderForm] = Form.useForm<AIProviderSettingFormValues>();
  const [deliveryTemplateForm] = Form.useForm<DeliveryTemplateFormValues>();
  const [deliveryAutomationForm] = Form.useForm<DeliveryAutomationFormValues>();
  const [orderSyncSettingForm] = Form.useForm<
    Pick<
      OrderSyncSetting,
      "sync_enabled" | "pending_interval_seconds" | "full_interval_minutes" | "jitter_seconds"
    >
  >();
  const [productDraftForm] = Form.useForm<ProductDraftFormValues>();
  const [productSyncSettingForm] = Form.useForm<
    Pick<
      ProductSyncSetting,
      | "sync_enabled"
      | "sync_interval_minutes"
      | "sync_jitter_minutes"
      | "full_sync_interval_hours"
      | "publish_verify_delay_seconds"
      | "auto_polish_enabled"
      | "polish_hour"
      | "polish_jitter_minutes"
    >
  >();
  const [addressGroupForm] = Form.useForm<PublishAddressGroupFormValues>();
  const [addressImportForm] = Form.useForm<AddressImportFormValues>();
  const ruleTriggerType = Form.useWatch("trigger_type", ruleForm) ?? "keyword";
  const ruleActionType = Form.useWatch("action_type", ruleForm) ?? "template";
  const selectedProductImageRefs =
    (Form.useWatch("image_refs", productDraftForm) as string[] | undefined) ?? [];
  const productImageSensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );
  const autoReplyRuleSensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );
  const accountSortSensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );
  const productLocationMode = Form.useWatch("location_mode", productDraftForm) ?? "account_default";
  const productDeliveryChoice =
    Form.useWatch("delivery_choice", productDraftForm) ?? "free_shipping";
  const productPostPrice = Form.useWatch("post_price", productDraftForm) ?? "";
  const productCanSelfPickup = Form.useWatch("can_self_pickup", productDraftForm) ?? false;
  const productRegionPathValue = Form.useWatch("region_path", productDraftForm);
  const productLocationKeyValue = Form.useWatch("location_key", productDraftForm);
  const productLocationGroupId = Form.useWatch("location_group_id", productDraftForm);
  const productRegionsByCode = useMemo(
    () => new Map((productRegionCatalog?.items || []).map((item) => [item.region_code, item])),
    [productRegionCatalog]
  );
  const productRegionTree = useMemo(
    () => buildRegionTree(productRegionCatalog?.items || []),
    [productRegionCatalog]
  );
  const productLocationTreeData = useMemo(() => {
    const tree = buildProductLocationTree(
        productRegionCatalog?.items || [],
        productAddressGroups,
        productLocations,
        {
          regionLoading: productRegionLoading,
          preciseLoading: productLocationLoading,
          preciseLoaded: productLocationResult !== null
        }
      );
    if (!privacyMaskEnabled) return tree;
    const maskNodes = (nodes: ProductLocationTreeNode[]): ProductLocationTreeNode[] =>
      nodes.map(node => {
        const isPrecise = node.value.startsWith("precise:");
        const isGroup = node.value.startsWith("group:");
        return {
          ...node,
          title: isPrecise
            ? "精准地址已隐藏"
            : isGroup
              ? maskSensitive(node.title, true, "name")
              : node.title,
          displayLabel: isPrecise
            ? "精准地址 / 地址已隐藏"
            : isGroup
              ? maskSensitive(node.displayLabel, true, "name")
              : node.displayLabel,
          children: node.children ? maskNodes(node.children) : undefined
        };
      });
    return maskNodes(tree);
  },
    [
      productAddressGroups,
      productLocationLoading,
      productLocationResult,
      productLocations,
      productRegionCatalog,
      productRegionLoading,
      privacyMaskEnabled
    ]
  );
  const productLocationSelection = useMemo(() => {
    if (productLocationMode === "group_random" && productLocationGroupId) {
      return `group:${productLocationGroupId}`;
    }
    if (productLocationMode === "region" && productRegionPathValue?.length) {
      return `region:${productRegionPathValue[productRegionPathValue.length - 1]}`;
    }
    if (productLocationMode === "selected" && productLocationKeyValue) {
      return `precise:${productLocationKeyValue}`;
    }
    return "mode:account_default";
  }, [
    productLocationGroupId,
    productLocationKeyValue,
    productLocationMode,
    productRegionPathValue
  ]);
  const productImagePreviewRefs = useMemo(
    () => selectedProductImageRefs.filter((imageRef) => Boolean(productImagePreviewUrls[imageRef])),
    [productImagePreviewUrls, selectedProductImageRefs]
  );
  const productImagePreviewItems = useMemo(
    () => productImagePreviewRefs.map((imageRef) => productImagePreviewUrls[imageRef]),
    [productImagePreviewRefs, productImagePreviewUrls]
  );
  const productPublishRequestIdsRef = useRef<Record<string, string>>({});
  const isAdmin = currentUser?.role === "admin";
  const canMutate = currentUser?.role === "admin" || currentUser?.role === "operator";
  const accountDisplayName = (account?: AccountLabelSource | null) =>
    maskSensitive(rawAccountDisplayName(account), privacyMaskEnabled, "name");
  const platformAccountName = (account?: AccountLabelSource | null) =>
    maskSensitive(rawPlatformAccountName(account), privacyMaskEnabled, "name");
  const conversationTitle = (conversation: Conversation) =>
    maskSensitive(rawConversationTitle(conversation), privacyMaskEnabled, "name");
  const privateName = (value?: string | null) =>
    maskSensitive(value, privacyMaskEnabled, "name");
  const privateId = (value?: string | null) =>
    maskSensitive(value, privacyMaskEnabled, "identifier");
  const privateContent = (value?: string | null) =>
    maskSensitive(value, privacyMaskEnabled, "content");
  const privateIPv4 = (value?: string | null) =>
    maskSensitive(value, privacyMaskEnabled, "ipv4");
  const privateIPv6 = (value?: string | null) =>
    maskSensitive(value, privacyMaskEnabled, "ipv6");
  const privateIP = (value?: string | null) =>
    value?.includes(":") ? privateIPv6(value) : privateIPv4(value);
  const privateBrowserEngineLabel = (
    engine?: BrowserEngine | null,
    systemLabel?: string
  ) => maskSensitive(rawBrowserEngineLabel(engine, systemLabel), privacyMaskEnabled, "name");
  const renderItemIdLink = (itemId?: string | null, itemUrl?: string | null) =>
    privacyMaskEnabled ? (
      <Tooltip title="隐私模式下已隐藏商品链接">
        <Text className="item-id-text-link">
          {maskSensitive(itemId, true, "identifier")}
        </Text>
      </Tooltip>
    ) : rawRenderItemIdLink(itemId, itemUrl);
  const selectedProductManagerAccount = useMemo(
    () => productManagerAccounts.find((item) => item.account_id === productManagerAccountId) ?? null,
    [productManagerAccountId, productManagerAccounts]
  );
  const selectedOrderManagerAccount = useMemo(
    () => orderManagerAccounts.find((item) => item.account_id === orderAccountFilter) ?? null,
    [orderAccountFilter, orderManagerAccounts]
  );
  const visibleProductCatalog = useMemo(() => {
    const keyword = productManagerKeyword.trim().toLowerCase();
    const knownItemIds = new Set(managedProducts.map((item) => item.item_id));
    const taskEntries: ProductCatalogEntry[] = productTasks
      .filter((task) => !task.item_id || !knownItemIds.has(task.item_id))
      .map((task) => ({
        key: `task:${task.task_id}`,
        kind: "publish_task",
        title: String(task.snapshot.title || "未命名发布任务"),
        price: String(task.snapshot.price || ""),
        task
      }));
    const itemEntries: ProductCatalogEntry[] = managedProducts.map((item) => ({
      key: `item:${item.item_id}`,
      kind: "item",
      title: item.title,
      price: item.price,
      coverUrl: item.cover_url,
      item
    }));
    return [...taskEntries, ...itemEntries].filter((entry) => {
      const matchesKeyword = !keyword || entry.title.toLowerCase().includes(keyword) ||
        entry.item?.item_id.toLowerCase().includes(keyword) || entry.task?.task_id.toLowerCase().includes(keyword);
      if (!matchesKeyword) return false;
      if (productManagerStatus === "all") return true;
      if (entry.kind === "item") return entry.item?.platform_status === productManagerStatus;
      if (productManagerStatus === "publishing") {
        return entry.task?.status === "pending" || entry.task?.status === "running" || entry.task?.status === "success";
      }
      if (productManagerStatus === "publish_failed") {
        return entry.task?.status === "failed" || entry.task?.status === "verification_required";
      }
      return false;
    });
  }, [managedProducts, productManagerKeyword, productManagerStatus, productTasks]);
  const conversationAccounts = useMemo(
    () =>
      accounts.filter(
        (account) =>
          account.enabled &&
          account.conversation_visible &&
          !["disabled", "deleting"].includes(account.runtime.state)
      ),
    [accounts]
  );
  const conversationAccountMap = useMemo(
    () => new Map(conversationAccounts.map((account) => [account.account_id, account])),
    [conversationAccounts]
  );
  const availableConversationAccountIds = useMemo(
    () =>
      new Set(
        conversationAccounts
          .filter((account) => accountIMAvailable(account))
          .map((account) => account.account_id)
      ),
    [conversationAccounts]
  );
  const conversationSyncStatusMap = useMemo(
    () => new Map(conversationSyncStatuses.map((status) => [status.account_id, status])),
    [conversationSyncStatuses]
  );
  const visibleConversations = useMemo(
    () =>
      conversations.filter((conversation) => {
        if (!availableConversationAccountIds.has(conversation.account_id)) {
          return false;
        }
        if (
          conversationAccountFilter !== "all" &&
          conversation.account_id !== conversationAccountFilter
        ) {
          return false;
        }
        return (
          conversationStatusFilter !== "unread" ||
          (conversation.viewer_unread_count ?? conversation.platform_unread_count ?? 0) > 0
        );
      }),
    [
      availableConversationAccountIds,
      conversationAccountFilter,
      conversationStatusFilter,
      conversations
    ]
  );

  function selectMenu(key: AdminMenuKey) {
    setActiveMenu(key);
    setMobileNavOpen(false);
    if (key !== "settings") setNavigationOpenKeys([]);
    navigate(menuPaths[key]);
  }

  function handleNavigationClick(key: string) {
    if (key.startsWith("settings:")) {
      const tab = key.slice("settings:".length) as SettingsTabKey;
      setActiveMenu("settings");
      setNavigationOpenKeys(["settings"]);
      setMobileNavOpen(false);
      navigate(`/settings?tab=${tab}`);
      return;
    }
    selectMenu(key as AdminMenuKey);
  }

  function isUnauthorized(error: unknown): boolean {
    return error instanceof ApiRequestError && error.status === 401;
  }

  async function load(options: { quietUnauthorized?: boolean } = {}): Promise<boolean> {
    setLoading(true);
    try {
      const [nextAccounts, nextProxies, browserSessions] = await Promise.all([
        listAccounts(),
        listProxies(),
        listActiveAccountBrowserSessions()
      ]);
      setAccounts(nextAccounts);
      setProxies(nextProxies);
      setAccountBrowserStatuses(
        Object.fromEntries(browserSessions.map((session) => [session.account_id, session]))
      );
      return true;
    } catch (error) {
      if (!options.quietUnauthorized || !isUnauthorized(error)) {
        message.error(error instanceof Error ? error.message : "加载账户或代理失败");
      }
      return false;
    } finally {
      setLoading(false);
    }
  }

  async function loadRuntimeDiagnostics() {
    try {
      const [process, runtime] = await Promise.all([
        getProcessHealth(),
        listRuntimeHealth()
      ]);
      setProcessHealth(process);
      setRuntimeHealth(runtime);
    } catch {
      // Diagnostics are supplemental and must not block normal account workflows.
    }
  }

  async function loadProxyData(silent = false) {
    if (!silent) {
      setProxyListLoading(true);
    }
    try {
      const [nextAccounts, nextProxies] = await Promise.all([listAccounts(), listProxies()]);
      setAccounts(nextAccounts);
      setProxies(nextProxies);
      const selectableIds = new Set(
        nextProxies.filter((proxy) => proxy.enabled).map((proxy) => proxy.proxy_id)
      );
      setSelectedProxyIds((current) => current.filter((proxyId) => selectableIds.has(proxyId)));
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载代理失败");
    } finally {
      if (!silent) {
        setProxyListLoading(false);
      }
    }
  }

  async function loadUsers() {
    setUsersLoading(true);
    try {
      setUsers(await listSystemUsers());
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载用户失败");
    } finally {
      setUsersLoading(false);
    }
  }

  async function bootstrapAuth() {
    try {
      const setupStatus = await getAuthSetupStatus();
      setSetupInitialized(setupStatus.initialized);
      setClientAccess(setupStatus.client);

      if (!getStoredAccessToken()) {
        setAuthenticated(false);
        return;
      }

      const [ok, user] = await Promise.all([
        load({ quietUnauthorized: true }),
        getCurrentUser()
      ]);
      if (ok) {
        setCurrentUser(user);
        setAuthenticated(true);
      } else {
        clearStoredAccessToken();
        setAuthenticated(false);
      }
    } catch (error) {
      if (isUnauthorized(error)) {
        clearStoredAccessToken();
        setCurrentUser(null);
      }
      setAuthenticated(false);
      message.error(error instanceof Error ? error.message : "检查系统状态失败");
    } finally {
      setAuthChecked(true);
    }
  }

  async function submitLogin() {
    const values = await loginForm.validateFields();
    setLoginLoading(true);
    try {
      const username = values.username?.trim() ?? "";
      const password = values.password ?? "";
      const result = await loginWithPassword({ username, password });
      setStoredAccessToken(result.access_token);
      setCurrentUser(result.user);
      const ok = await load();
      if (!ok) {
        clearStoredAccessToken();
        setAuthenticated(false);
        return;
      }
      setAuthenticated(true);
      message.success("登录成功");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "登录失败");
    } finally {
      setLoginLoading(false);
    }
  }

  async function bootstrapFirstAdmin() {
    const values = await loginForm.validateFields(["username", "password"]);
    const username = values.username?.trim() ?? "";
    const password = values.password ?? "";
    setLoginLoading(true);
    try {
      const result = await bootstrapAdminUser({ username, password });
      setStoredAccessToken(result.access_token);
      setCurrentUser(result.user);
      const ok = await load();
      if (!ok) {
        clearStoredAccessToken();
        setAuthenticated(false);
        return;
      }
      setAuthenticated(true);
      setSetupInitialized(true);
      message.success("首个管理员已初始化");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "初始化管理员失败");
      void getAuthSetupStatus().then((status) => setSetupInitialized(status.initialized)).catch(() => undefined);
    } finally {
      setLoginLoading(false);
    }
  }

  function clearAuthenticatedSession() {
    clearStoredAccessToken();
    setAuthenticated(false);
    setCurrentUser(null);
    setAccounts([]);
    setProcessHealth(null);
    setRuntimeHealth([]);
    loginForm.setFieldsValue({ username: "", password: "" });
  }

  function logout() {
    clearAuthenticatedSession();
    message.success("已退出登录");
  }

  function privacyAllowsSensitiveEditor(): boolean {
    if (!privacyMaskEnabled) return true;
    message.info("隐私模式下不打开包含原始数据的编辑界面，请先关闭隐私去敏");
    return false;
  }

  async function togglePrivacyMask() {
    if (!currentUser || privacySaving) return;
    const enabled = !currentUser.privacy_mask_enabled;
    setPrivacySaving(true);
    try {
      const updated = await updateCurrentUserPreferences({ privacy_mask_enabled: enabled });
      setCurrentUser(updated);
      setUsers(items => items.map(item => item.user_id === updated.user_id ? updated : item));
      if (enabled) {
        setUserDrawerOpen(false);
        setProxyDrawerOpen(false);
        setDrawerOpen(false);
        setRuleDrawerOpen(false);
        setAutoReplyPreviewOpen(false);
        setQuickPhraseManagerOpen(false);
        setProductPublishDrawerOpen(false);
        setProductImagePreviewOpen(false);
        setAddressGroupModalOpen(false);
        setAddressImportModalOpen(false);
      }
      message.success(enabled ? "隐私去敏已开启" : "隐私去敏已关闭");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "隐私设置更新失败");
    } finally {
      setPrivacySaving(false);
    }
  }

  useEffect(() => {
    loginForm.setFieldsValue({ username: "", password: "" });
    void bootstrapAuth();
  }, []);

  useEffect(() => {
    if (!authenticated || !["dashboard", "accounts"].includes(activeMenu)) {
      return;
    }
    const refresh = () => {
      if (document.visibilityState === "visible") {
        void loadRuntimeDiagnostics();
      }
    };
    refresh();
    const timer = window.setInterval(refresh, 7000);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [activeMenu, authenticated]);

  useEffect(() => {
    const media = window.matchMedia("(max-width: 767px)");
    const update = () => setCompactLayout(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useLayoutEffect(() => {
    activeMenuRef.current = activeMenu;
    compactLayoutRef.current = compactLayout;
    mobileConversationDetailOpenRef.current = mobileConversationDetailOpen;
  }, [activeMenu, compactLayout, mobileConversationDetailOpen]);

  useEffect(() => {
    accountsRef.current = accounts;
    const selectableAccountIds = new Set(
      accounts
        .filter(
          (account) =>
            account.enabled &&
            account.conversation_visible &&
            !["disabled", "deleting"].includes(account.runtime.state)
        )
        .map((account) => account.account_id)
    );
    setConversations((items) =>
      items.filter((conversation) => selectableAccountIds.has(conversation.account_id))
    );
    setConversationAccountFilter((current) =>
      current === "all" || selectableAccountIds.has(current) ? current : "all"
    );
    const selected = selectedConversationRef.current;
    const selectedAccount = selected
      ? accounts.find((account) => account.account_id === selected.account_id)
      : null;
    if (
      selected &&
      (!selectedAccount?.conversation_visible || !accountIMAvailable(selectedAccount))
    ) {
      selectedConversationRef.current = null;
      setSelectedConversation(null);
      setConversationAccount(null);
      setChatMessages([]);
      setMobileConversationDetailOpen(false);
      setPendingImages([]);
    } else if (selectedAccount) {
      setConversationAccount(selectedAccount);
    }
  }, [accounts]);

  useLayoutEffect(() => {
    const container = conversationListViewportRef.current;
    if (!container || activeMenu !== "conversations") {
      return;
    }
    const updateHeight = () => {
      const next = Math.floor(container.clientHeight);
      if (next > 0) {
        setConversationListHeight((current) => (current === next ? current : next));
      }
    };
    const animationFrame = window.requestAnimationFrame(updateHeight);
    const observer = new ResizeObserver(updateHeight);
    observer.observe(container);
    window.addEventListener("resize", updateHeight);
    window.visualViewport?.addEventListener("resize", updateHeight);
    return () => {
      window.cancelAnimationFrame(animationFrame);
      observer.disconnect();
      window.removeEventListener("resize", updateHeight);
      window.visualViewport?.removeEventListener("resize", updateHeight);
    };
  }, [activeMenu, authenticated, compactLayout, mobileConversationDetailOpen]);

  useLayoutEffect(() => {
    const container = accountTableViewportRef.current;
    if (!container || activeMenu !== "accounts") {
      return;
    }
    const updateWidth = () => {
      const next = Math.floor(container.clientWidth);
      if (next > 0) {
        setAccountTableWidth((current) => (current === next ? current : next));
      }
    };
    const animationFrame = window.requestAnimationFrame(updateWidth);
    const observer = new ResizeObserver(updateWidth);
    observer.observe(container);
    window.addEventListener("resize", updateWidth);
    return () => {
      window.cancelAnimationFrame(animationFrame);
      observer.disconnect();
      window.removeEventListener("resize", updateWidth);
    };
  }, [activeMenu, authenticated, compactLayout]);

  useEffect(() => {
    if (activeMenu !== "accounts" || !authenticated) {
      return;
    }
    let cancelled = false;
    const drawerAccountId = accountBrowserOpen ? accountBrowserAccount?.account_id : null;
    const refresh = () => {
      void (async () => {
        try {
          const sessions = await listActiveAccountBrowserSessions();
          if (cancelled) return;
          setAccountBrowserStatuses(
            Object.fromEntries(sessions.map((session) => [session.account_id, session]))
          );
          sessions.forEach((session) => {
            if (session.fingerprint_snapshot) {
              updateAccountFingerprintSnapshot(
                session.account_id,
                session.fingerprint_snapshot
              );
            }
          });
          if (drawerAccountId) {
            try {
              const current = await getAccountBrowserSession(drawerAccountId);
              if (!cancelled) {
                setAccountBrowserSession(current);
                updateAccountBrowserStatus(current, drawerAccountId);
              }
            } catch (error) {
              if (
                !cancelled &&
                error instanceof ApiRequestError &&
                error.status === 404
              ) {
                setAccountBrowserSession(null);
              }
            }
          }
        } catch {
          // Keep the last known VNC state until the next poll.
        }
      })();
    };
    refresh();
    const timer = window.setInterval(refresh, 10_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [
    accountBrowserAccount?.account_id,
    accountBrowserOpen,
    activeMenu,
    authenticated
  ]);

  useEffect(() => {
    if (!browserProfileDrawerOpen || !authenticated) {
      return;
    }
    let cancelled = false;
    const refresh = () => {
      void listBrowserProfiles()
        .then((profiles) => {
          if (!cancelled) setBrowserProfiles(profiles);
        })
        .catch(() => {
          // Keep the latest directory snapshot until the next poll.
        });
    };
    const timer = window.setInterval(refresh, 8_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [authenticated, browserProfileDrawerOpen]);

  useEffect(() => {
    if (!accountBrowserOpen || !isActiveAccountBrowser(accountBrowserSession)) return;
    setAccountBrowserClock(Date.now());
    const timer = window.setInterval(() => setAccountBrowserClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [accountBrowserOpen, accountBrowserSession?.session_id, accountBrowserSession?.status]);

  useEffect(() => {
    if (accountBrowserSession?.status === "ready") return;
    setAccountBrowserPasteText("");
    setAccountBrowserPasting(false);
  }, [accountBrowserSession?.session_id, accountBrowserSession?.status]);

  useEffect(() => {
    const nextMenu = pathMenus[location.pathname] ?? "dashboard";
    const denied =
      (Boolean(currentUser) && adminMenus.has(nextMenu) && currentUser?.role !== "admin") ||
      (currentUser?.role === "viewer" && !viewerMenus.has(nextMenu));
    if (denied) {
      setActiveMenu("dashboard");
      setNavigationOpenKeys([]);
      navigate(menuPaths.dashboard, { replace: true });
      return;
    }
    setActiveMenu(nextMenu);
    setNavigationOpenKeys(nextMenu === "settings" ? ["settings"] : []);
  }, [currentUser?.role, location.pathname, navigate]);

  useEffect(() => {
    if (
      activeMenu !== "product-management" ||
      !productManagerAccountId ||
      !productTasks.some((task) => task.status === "pending" || task.status === "running")
    ) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadProductManagementWorkspace(productManagerAccountId, true);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [activeMenu, productManagerAccountId, productTasks]);

  useEffect(() => {
    if (activeMenu !== "product-management" || !authenticated) {
      return;
    }
    void loadProductManagementWorkspace();
  }, [activeMenu, authenticated]);

  useEffect(() => {
    if (activeMenu !== "product-management" || !productManagerAccountId) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadProductManagementWorkspace(productManagerAccountId, true);
    }, 10000);
    return () => window.clearInterval(timer);
  }, [activeMenu, productManagerAccountId]);

  useEffect(() => {
    if (activeMenu !== "delivery" || !authenticated) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadOrderManagement(orderAccountFilter, true);
    }, 10000);
    return () => window.clearInterval(timer);
  }, [activeMenu, authenticated, orderAccountFilter, orderStatusFilter, orderKeyword, orderScope]);

  useEffect(() => {
    selectedConversationRef.current = selectedConversation;
  }, [selectedConversation]);

  useEffect(() => {
    orderScopeRef.current = orderScope;
  }, [orderScope]);

  useEffect(() => {
    return () => {
      Object.values(productImagePreviewUrlsRef.current).forEach((url) => URL.revokeObjectURL(url));
      if (composerNoticeTimerRef.current !== null) {
        window.clearTimeout(composerNoticeTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    setPendingImages((items) => {
      items.forEach((item) => URL.revokeObjectURL(item.previewUrl));
      return [];
    });
    setPlatformBlacklistState(null);
    setComposerNotice(null);
    if (imageInputRef.current) {
      imageInputRef.current.value = "";
    }
  }, [selectedConversation?.account_id, selectedConversation?.conversation_id]);

  useLayoutEffect(() => {
    if (activeMenu !== "conversations") {
      if (conversationPageWasActiveRef.current) {
        historyRequestRef.current += 1;
        historyScrollAnchorRef.current = null;
        setOlderMessagesLoading(false);
      }
      conversationPageWasActiveRef.current = false;
      return;
    }
    const reenteredConversationPage = !conversationPageWasActiveRef.current;
    conversationPageWasActiveRef.current = true;
    const container = messageListRef.current;
    if (!container || !selectedConversation) {
      return;
    }
    if (compactLayout && !mobileConversationDetailOpen) {
      return;
    }
    const selectedIdentity = conversationIdentity(selectedConversation);
    if (reenteredConversationPage) {
      stickMessagesToBottomRef.current = true;
      forceBottomConversationRef.current = selectedIdentity;
      historyScrollAnchorRef.current = null;
    }
    const historyAnchor = historyScrollAnchorRef.current;
    if (historyAnchor) {
      container.scrollTop = historyAnchor.top + (container.scrollHeight - historyAnchor.height);
      historyScrollAnchorRef.current = null;
      return;
    }
    const forceBottom = forceBottomConversationRef.current === selectedIdentity;
    if ((forceBottom && !chatMessagesLoading) || stickMessagesToBottomRef.current) {
      container.scrollTop = container.scrollHeight;
      if (forceBottom) {
        let secondFrame = 0;
        const firstFrame = window.requestAnimationFrame(() => {
          const current = messageListRef.current;
          const selected = selectedConversationRef.current;
          if (
            current &&
            selected &&
            activeMenuRef.current === "conversations" &&
            (!compactLayoutRef.current || mobileConversationDetailOpenRef.current) &&
            conversationIdentity(selected) === selectedIdentity &&
            stickMessagesToBottomRef.current
          ) {
            current.scrollTop = current.scrollHeight;
            secondFrame = window.requestAnimationFrame(() => {
              const latest = messageListRef.current;
              if (latest && stickMessagesToBottomRef.current) {
                latest.scrollTop = latest.scrollHeight;
              }
            });
          }
        });
        if (forceBottom && !chatMessagesLoading) {
          forceBottomConversationRef.current = null;
        }
        return () => {
          window.cancelAnimationFrame(firstFrame);
          if (secondFrame) {
            window.cancelAnimationFrame(secondFrame);
          }
        };
      }
      if (forceBottom && !chatMessagesLoading) {
        forceBottomConversationRef.current = null;
      }
    }
  }, [
    activeMenu,
    chatMessages.length,
    chatMessages[chatMessages.length - 1]?.message_pk,
    chatMessages[chatMessages.length - 1]?.send_status,
    chatMessages[chatMessages.length - 1]?.recalled_at,
    chatMessagesLoading,
    compactLayout,
    mobileConversationDetailOpen,
    selectedConversation?.account_id,
    selectedConversation?.conversation_id
  ]);

  function getWebNotificationAudioContext(): AudioContext | null {
    if (webNotificationAudioContextRef.current) {
      return webNotificationAudioContextRef.current;
    }
    if (typeof window === "undefined" || !window.AudioContext) {
      return null;
    }
    const context = new window.AudioContext();
    webNotificationAudioContextRef.current = context;
    return context;
  }

  async function decodeWebNotificationSound() {
    const context = getWebNotificationAudioContext();
    const bytes = webNotificationAudioBytesRef.current;
    if (!context || !bytes) {
      webNotificationAudioBufferRef.current = null;
      return;
    }
    try {
      webNotificationAudioBufferRef.current = await context.decodeAudioData(bytes.slice(0));
    } catch {
      webNotificationAudioBufferRef.current = null;
    }
  }

  async function applyWebNotificationConfig(config: WebNotificationConfig) {
    webNotificationConfigRef.current = config;
    setWebNotificationConfig(config);
    const loadId = webNotificationAudioLoadRef.current + 1;
    webNotificationAudioLoadRef.current = loadId;
    webNotificationAudioBytesRef.current = null;
    webNotificationAudioBufferRef.current = null;
    if (!config.has_custom_sound || !config.sound_url) {
      return;
    }
    try {
      const blob = await getWebNotificationSound();
      const bytes = await blob.arrayBuffer();
      if (webNotificationAudioLoadRef.current !== loadId) {
        return;
      }
      webNotificationAudioBytesRef.current = bytes;
      await decodeWebNotificationSound();
    } catch {
      // A missing or browser-incompatible custom file falls back to the built-in ding.
    }
  }

  async function loadWebNotificationData(showError = false) {
    setWebNotificationLoading(true);
    try {
      await applyWebNotificationConfig(await getWebNotificationConfig());
    } catch (error) {
      if (showError) {
        message.error(error instanceof Error ? error.message : "加载网页铃声配置失败");
      }
    } finally {
      setWebNotificationLoading(false);
    }
  }

  function playWebNotificationSound(force = false) {
    const config = webNotificationConfigRef.current;
    if (!config || (!force && !config.enabled)) {
      return;
    }
    const context = webNotificationAudioContextRef.current;
    if (!context || context.state !== "running") {
      setWebNotificationUnlocked(false);
      return;
    }
    const buffer = webNotificationAudioBufferRef.current;
    if (config.has_custom_sound && buffer) {
      const source = context.createBufferSource();
      const gain = context.createGain();
      gain.gain.value = 0.9;
      source.buffer = buffer;
      source.connect(gain);
      gain.connect(context.destination);
      source.start();
      return;
    }
    playDefaultMessageDing(context);
  }

  function notifyForInboundMessage(next: ChatMessage) {
    if (
      next.direction !== "inbound" ||
      next.message_type === "system" ||
      next.recalled_at ||
      !webNotificationConfigRef.current?.enabled
    ) {
      return;
    }
    const account = accountsRef.current.find((item) => item.account_id === next.account_id);
    if (account && (!account.enabled || !account.conversation_visible)) {
      return;
    }
    const now = Date.now();
    const notified = notifiedMessageIdsRef.current;
    if (notified.has(next.message_pk)) {
      return;
    }
    notified.set(next.message_pk, now);
    if (notified.size > 500) {
      for (const [messagePk, notifiedAt] of notified) {
        if (now - notifiedAt > 10 * 60 * 1000) {
          notified.delete(messagePk);
        }
      }
    }
    playWebNotificationSound();
  }

  useEffect(() => {
    if (!authenticated) {
      webNotificationConfigRef.current = null;
      setWebNotificationConfig(null);
      return undefined;
    }
    void loadWebNotificationData();
    const unlockAudio = () => {
      const context = getWebNotificationAudioContext();
      if (!context) {
        return;
      }
      void context
        .resume()
        .then(async () => {
          if (
            webNotificationAudioBytesRef.current &&
            !webNotificationAudioBufferRef.current
          ) {
            await decodeWebNotificationSound();
          }
          setWebNotificationUnlocked(context.state === "running");
        })
        .catch(() => setWebNotificationUnlocked(false));
    };
    window.addEventListener("pointerdown", unlockAudio, { capture: true });
    window.addEventListener("keydown", unlockAudio, { capture: true });
    return () => {
      window.removeEventListener("pointerdown", unlockAudio, { capture: true });
      window.removeEventListener("keydown", unlockAudio, { capture: true });
      notifiedMessageIdsRef.current.clear();
      webNotificationAudioBytesRef.current = null;
      webNotificationAudioBufferRef.current = null;
      const context = webNotificationAudioContextRef.current;
      webNotificationAudioContextRef.current = null;
      if (context) {
        void context.close();
      }
    };
  }, [authenticated]);

  useEffect(() => {
    if (!authenticated) {
      return undefined;
    }

    let stopped = false;
    let socket: WebSocket | null = null;
    let reconnectDelay = 1000;
    let reconnectTimer: number | undefined;
    let heartbeatTimer: number | undefined;

    const upsertConversations = (updates: Conversation[]) => {
      const visibleUpdates = updates.filter((update) => {
        const account = accountsRef.current.find(
          (item) => item.account_id === update.account_id
        );
        return Boolean(account?.conversation_visible && accountIMAvailable(account));
      });
      if (!visibleUpdates.length) {
        return;
      }
      setConversations((items) => mergeConversationRecords(items, visibleUpdates));
      const selectedIdentity = selectedConversationRef.current
        ? conversationIdentity(selectedConversationRef.current)
        : null;
      const selectedUpdate = visibleUpdates.find(
        (item) => conversationIdentity(item) === selectedIdentity
      );
      if (selectedUpdate) {
        const mergedSelected = {
          ...selectedConversationRef.current,
          ...selectedUpdate
        } as Conversation;
        if (
          !selectedConversationRef.current ||
          !shallowRecordEqual(selectedConversationRef.current, mergedSelected)
        ) {
          selectedConversationRef.current = mergedSelected;
          setSelectedConversation(mergedSelected);
        }
      }
    };

    const resyncWorkspace = async () => {
      const nextAccounts = await listAccounts();
      if (stopped) {
        return;
      }
      setAccounts(nextAccounts);
      void loadConversationList(false);
      const selected = selectedConversationRef.current;
      if (selected) {
        const messagePage = await listCachedMessages(
          selected.account_id,
          selected.conversation_id,
          100
        );
        if (!stopped) {
          setChatMessages((items) => mergeChatMessageRecords(items, messagePage.items));
          setMessageHasMore(messagePage.has_more);
          setMessageNextCursor(messagePage.next_cursor ?? null);
        }
      }
    };

    const scheduleReconnect = () => {
      if (stopped || reconnectTimer !== undefined) {
        return;
      }
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = undefined;
        void connect();
      }, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, 30000);
    };

    const connect = async () => {
      try {
        socket = await createRealtimeWebSocket();
        if (stopped) {
          socket.close();
          return;
        }
        socket.onopen = () => {
          reconnectDelay = 1000;
          realtimeConnectedRef.current = true;
          const eventAge = Date.now() - realtimeLastEventAtRef.current;
          if (!workspaceBootstrappedRef.current || eventAge > 120000) {
            workspaceBootstrappedRef.current = true;
            void resyncWorkspace().catch(() => undefined);
          }
          heartbeatTimer = window.setInterval(() => {
            if (socket?.readyState === WebSocket.OPEN) {
              socket.send(JSON.stringify({ type: "ping" }));
            }
          }, 25000);
        };
        socket.onmessage = (rawEvent) => {
          realtimeLastEventAtRef.current = Date.now();
          let event: {
            event?: string;
            account_id?: string;
            account_ids?: string[];
            data?: unknown;
          };
          try {
            event = JSON.parse(String(rawEvent.data));
          } catch {
            return;
          }
          if (event.event === "accounts_reordered" && Array.isArray(event.account_ids)) {
            const positions = new Map(
              event.account_ids.map((accountId, index) => [accountId, index])
            );
            setAccounts((items) => {
              const next = [...items]
                .sort((left, right) => {
                  const leftPosition = positions.get(left.account_id);
                  const rightPosition = positions.get(right.account_id);
                  if (leftPosition == null && rightPosition == null) return 0;
                  if (leftPosition == null) return 1;
                  if (rightPosition == null) return -1;
                  return leftPosition - rightPosition;
                })
                .map((account, index) => ({ ...account, sort_order: (index + 1) * 100 }));
              accountsRef.current = next;
              return next;
            });
            return;
          }
          if (event.event === "account_upsert" && event.account_id && event.data) {
            const update = event.data as Account;
            setAccounts((items) => {
              const exists = items.some((item) => item.account_id === update.account_id);
              const next = exists
                ? items.map((item) => item.account_id === update.account_id ? update : item)
                : [...items, update];
              accountsRef.current = next;
              return next;
            });
            setAccountBrowserAccount((current) =>
              current?.account_id === update.account_id ? update : current
            );
            setEditing((current) => {
              if (current?.account_id !== update.account_id) return current;
              const snapshot = update.browser_identity?.fingerprint_snapshot;
              if (snapshot) {
                return {
                  ...current,
                  browser_identity: {
                    ...(current.browser_identity ?? defaultBrowserIdentity()),
                    fingerprint_snapshot: snapshot
                  }
                };
              }
              return current;
            });
            return;
          }
          if (event.event === "account_delete" && event.account_id) {
            setAccounts((items) => {
              const next = items.filter((item) => item.account_id !== event.account_id);
              accountsRef.current = next;
              return next;
            });
            setAccountBrowserStatuses((items) => {
              const next = { ...items };
              delete next[event.account_id!];
              return next;
            });
            return;
          }
          if (event.event === "account_status" && event.account_id && event.data) {
            setAccounts((items) => {
              const next = items.map((item) =>
                item.account_id === event.account_id
                  ? applyRuntimeHealth(item, event.data as Account["runtime"])
                  : item
              );
              accountsRef.current = next;
              return next;
            });
            return;
          }
          if (event.event === "cookie_renewal_status" && event.account_id && event.data) {
            const next = event.data as CookieRenewalStatus;
            setCookieRenewalStatus((current) =>
              current?.account_id === event.account_id ? next : current
            );
            setAccounts((items) => {
              const updated = items.map((item) =>
                item.account_id === event.account_id
                  ? applyCookieRenewalHealth(item, next)
                  : item
              );
              accountsRef.current = updated;
              return updated;
            });
            return;
          }
          if (event.event === "conversation_upsert" && event.data) {
            const next = event.data as Conversation;
            upsertConversations([next]);
            return;
          }
          if (event.event === "product_publish_task_upsert" && event.account_id && event.data) {
            const next = event.data as ProductPublishTask;
            if (event.account_id === productManagerAccountIdRef.current) {
              setProductTasks((items) => [next, ...items.filter((item) => item.task_id !== next.task_id)]);
              if (next.status === "success" || next.status === "verification_required") {
                window.setTimeout(() => {
                  void loadProductManagementWorkspace(event.account_id, true);
                }, 800);
              }
            }
            return;
          }
          if (event.event === "conversation_batch" && Array.isArray(event.data)) {
            const updates = event.data as Conversation[];
            if (updates.length) {
              upsertConversations(updates);
            }
            return;
          }
          if (event.event === "conversation_sync_status" && event.data) {
            const next = event.data as ConversationAccountSync;
            setConversationSyncStatuses((items) => [
              next,
              ...items.filter((item) => item.account_id !== next.account_id)
            ]);
            return;
          }
          if (event.event === "conversation_read" && event.data) {
            upsertConversations([event.data as Conversation]);
            return;
          }
          if (event.event === "message_upsert" && event.data) {
            const next = event.data as ChatMessage;
            notifyForInboundMessage(next);
            const selected = selectedConversationRef.current;
            if (
              selected &&
              next.account_id === selected.account_id &&
              next.conversation_id === selected.conversation_id
            ) {
              setChatMessages((items) => mergeChatMessageRecords(items, [next]));
              const detailVisible =
                !compactLayoutRef.current || mobileConversationDetailOpenRef.current;
              if (
                next.direction === "inbound" &&
                activeMenuRef.current === "conversations" &&
                detailVisible &&
                document.visibilityState === "visible" &&
                document.hasFocus() &&
                stickMessagesToBottomRef.current
              ) {
                void markConversationRead(next.account_id, next.conversation_id)
                  .then((conversation) => upsertConversations([conversation]))
                  .catch(() => undefined);
              }
            }
            return;
          }
          if (event.event === "order_upsert" && event.data) {
            const next = event.data as XianyuOrder;
            const visibleRole = orderScopeRef.current === "bought" ? "buyer" : "seller";
            const visibleSource = orderScopeRef.current === "bought" ? "buyer_bought" : "seller_sold";
            const account = accountsRef.current.find((item) => item.account_id === next.account_id);
            if (
              account?.order_management_visible &&
              next.trade_role === visibleRole &&
              next.data_source === visibleSource
            ) {
              setOrders((items) => [next, ...items.filter((item) => item.order_pk !== next.order_pk)]);
            }
            setConversationOrders((items) =>
              [next, ...items.filter((item) => item.order_pk !== next.order_pk)]
                .filter(
                  (item) =>
                    item.account_id === next.account_id &&
                    item.conversation_id === next.conversation_id
                )
            );
            setSelectedOrder((current) =>
              current?.order_pk === next.order_pk ? { ...current, ...next } : current
            );
            return;
          }
          if (event.event === "resync_required") {
            void resyncWorkspace().catch(() => undefined);
          }
        };
        socket.onclose = () => {
          realtimeConnectedRef.current = false;
          if (heartbeatTimer !== undefined) {
            window.clearInterval(heartbeatTimer);
            heartbeatTimer = undefined;
          }
          scheduleReconnect();
        };
        socket.onerror = () => socket?.close();
      } catch {
        scheduleReconnect();
      }
    };

    const fallbackTimer = window.setInterval(() => {
      void listAccounts().then(setAccounts).catch(() => undefined);
    }, 60000);
    const onVisibility = () => {
      const realtimeStale = Date.now() - realtimeLastEventAtRef.current > 120000;
      if (
        document.visibilityState === "visible" &&
        (!realtimeConnectedRef.current || realtimeStale)
      ) {
        void resyncWorkspace().catch(() => undefined);
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    void connect();

    return () => {
      stopped = true;
      realtimeConnectedRef.current = false;
      socket?.close();
      window.clearInterval(fallbackTimer);
      if (heartbeatTimer !== undefined) {
        window.clearInterval(heartbeatTimer);
      }
      if (reconnectTimer !== undefined) {
        window.clearTimeout(reconnectTimer);
      }
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [authenticated]);

  useEffect(() => {
    if (
      !qrModalOpen ||
      !qrLogin ||
      ["browser_verification", "completed", "expired", "error"].includes(qrLogin.status)
    ) {
      return undefined;
    }
    let cancelled = false;
    let timer: number | undefined;
    let controller: AbortController | undefined;
    const poll = async () => {
      controller = new AbortController();
      try {
        const next = await pollXianyuQRLogin(qrLogin.session_id, controller.signal);
        if (cancelled) {
          return;
        }
        setQrLogin(next);
        if (next.status === "completed") {
          const runtimeText = next.runtime_state ? `，连接状态：${next.runtime_state}` : "";
          message.success(`闲鱼账号凭据已保存${runtimeText}`);
          setQrModalOpen(false);
          setDrawerOpen(false);
          await load();
        }
      } catch (error) {
        if (!cancelled && !(error instanceof DOMException && error.name === "AbortError")) {
          message.error(error instanceof Error ? error.message : "二维码状态查询失败");
        }
      } finally {
        if (!cancelled) {
          timer = window.setTimeout(() => void poll(), 2000);
        }
      }
    };
    void poll();
    return () => {
      cancelled = true;
      controller?.abort();
      if (timer !== undefined) {
        window.clearTimeout(timer);
      }
    };
  }, [qrLogin?.session_id, qrLogin?.status, qrModalOpen]);

  useEffect(() => {
    if (!authenticated) {
      return;
    }
    if (activeMenu === "settings" && isAdmin) {
      const tab = settingsTabFromSearch(location.search, isAdmin, canMutate);
      if (tab === "users") void loadUsers();
      if (tab === "browsers") void loadBrowserRuntime();
      if (tab === "message-services") {
        void loadChatwootData();
        void loadWebNotificationData(true);
      }
      if (tab === "audit") void loadAuditLogs();
      if (tab === "ai") void loadAIProviderData();
      if (tab === "tasks") void loadBackgroundTaskData();
    }
    if (activeMenu === "settings") {
      const tab = settingsTabFromSearch(location.search, isAdmin, canMutate);
      if (tab === "proxies") void loadProxyData();
      if (tab === "addresses" && canMutate) void loadAddressLibrary();
    }
    if (activeMenu === "accounts" && isAdmin) {
      void loadBrowserRuntime(true);
    }
    if (activeMenu === "conversations") {
      void loadConversationList();
      void loadQuickPhraseData();
    }
    if (activeMenu === "auto-reply" && canMutate) {
      setEditingRule(null);
      setRuleDrawerOpen(false);
      void loadAutoReplyData();
    }
    if (activeMenu === "delivery") {
      void loadOrderManagement();
    }
  }, [activeMenu, authenticated, isAdmin, canMutate, location.search]);

  useEffect(() => {
    if (
      !authenticated ||
      activeMenu !== "settings" ||
      settingsTabFromSearch(location.search, isAdmin, canMutate) !== "tasks" ||
      !isAdmin
    ) return;
    const timer = window.setInterval(() => void loadBackgroundTaskData(true), 8_000);
    return () => window.clearInterval(timer);
  }, [activeMenu, authenticated, isAdmin, canMutate, location.search]);

  useEffect(() => {
    if (!runtimeLogOpen || !runtimeLogAccount) return;
    const timer = window.setInterval(
      () => void loadEventsFor(runtimeLogAccount.account_id, true),
      5_000
    );
    return () => window.clearInterval(timer);
  }, [runtimeLogAccount?.account_id, runtimeLogOpen]);

  function openCreateDrawer() {
    if (!privacyAllowsSensitiveEditor()) return;
    accountCookieRequestRef.current += 1;
    qrClientRequestIdRef.current = createClientRequestId("qr-login");
    setEditing(null);
    setAccountEditorTab("basic");
    setEditingOriginalCookie(null);
    setAccountCookieLoading(false);
    form.setFieldsValue({
      remark: "",
      cookie: "",
      enabled: true,
      proxy_id: null,
      browser_identity: {
        ...defaultBrowserIdentity(),
        browser_version: browserRuntime?.active_standard_version || null
      }
    });
    void loadBrowserRuntime(true);
    setDrawerOpen(true);
  }

  function openEditDrawer(account: Account, tab = "basic") {
    if (!privacyAllowsSensitiveEditor()) return;
    const requestId = ++accountCookieRequestRef.current;
    setEditing(account);
    setAccountEditorTab(tab);
    setEditingOriginalCookie(null);
    form.setFieldsValue({
      remark: account.remark || "",
      cookie: "",
      enabled: account.enabled,
      proxy_id: account.proxy_id ?? null,
      browser_identity: normalizeBrowserIdentityForEditor(account.browser_identity)
    });
    void loadBrowserRuntime(true);
    setDrawerOpen(true);
    void getAccount(account.account_id)
      .then((latest) => {
        if (requestId !== accountCookieRequestRef.current) return;
        setAccounts((items) => {
          const next = items.map((item) =>
            item.account_id === latest.account_id ? latest : item
          );
          accountsRef.current = next;
          return next;
        });
        setEditing((current) =>
          current?.account_id === latest.account_id ? latest : current
        );
        setAccountBrowserAccount((current) =>
          current?.account_id === latest.account_id ? latest : current
        );
      })
      .catch(() => {
        // The account-list snapshot remains usable if this supplemental refresh fails.
      });
    setAccountCookieLoading(true);
    void revealAccountCookie(account.account_id)
      .then((result) => {
        if (requestId !== accountCookieRequestRef.current) return;
        setEditingOriginalCookie(result.cookie);
        form.setFieldValue("cookie", result.cookie);
      })
      .catch((error) => {
        if (requestId !== accountCookieRequestRef.current) return;
        message.error(error instanceof Error ? error.message : "读取原 Cookie 失败");
      })
      .finally(() => {
        if (requestId === accountCookieRequestRef.current) {
          setAccountCookieLoading(false);
        }
      });
  }

  async function submitForm() {
    const values = await form.validateFields();
    const payload: AccountFormValues = {
      ...values,
      remark: values.remark?.trim() || null,
      proxy_id: values.proxy_id || null
    };

    setSubmitting(true);
    try {
      if (editing) {
        const updatePayload: Partial<AccountFormValues> = { ...payload };
        delete updatePayload.enabled;
        if (!payload.cookie || payload.cookie === editingOriginalCookie) {
          delete updatePayload.cookie;
        }
        await updateAccount(editing.account_id, updatePayload);
        message.success("账户已更新");
      } else {
        await createAccount(payload);
        message.success("账户已创建");
      }
      setDrawerOpen(false);
      await load();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function beginQRLogin() {
    const values = form.getFieldsValue();
    await beginQRLoginWithAccount({
      account_id: editing?.account_id,
      remark: editing?.remark || values.remark?.trim() || null,
      client_request_id: editing ? null : qrClientRequestIdRef.current,
      proxy_id: values.proxy_id || null,
      browser_identity: values.browser_identity
    });
  }

  async function beginQRLoginWithAccount(values: {
    account_id?: string | null;
    remark?: string | null;
    client_request_id?: string | null;
    proxy_id?: string | null;
    browser_identity?: AccountBrowserIdentity | null;
  }) {
    setQrLoginValues(values);
    setQrLoading(true);
    try {
      const result = await startXianyuQRLogin(values);
      setQrLogin(result);
      setQrBrowserVerification(null);
      setQrBrowserSocketUrl("");
      setQrBrowserConnected(false);
      setQrModalOpen(true);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "生成二维码失败");
    } finally {
      setQrLoading(false);
    }
  }

  function closeQRLoginModal() {
    const current = qrLogin;
    setQrModalOpen(false);
    if (current && !["completed", "expired"].includes(current.status)) {
      void cancelXianyuQRLogin(current.session_id).catch(() => undefined);
    }
  }

  async function beginAccountQRLogin(account: Account) {
    setRecoveringAccountId(account.account_id);
    try {
      await beginQRLoginWithAccount({
        account_id: account.account_id,
        remark: account.remark || null,
        proxy_id: account.proxy_id ?? null,
        browser_identity: account.browser_identity
      });
    } finally {
      setRecoveringAccountId(null);
    }
  }

  async function connectQRBrowserViewer(sessionId: string) {
    setQrBrowserLoading(true);
    try {
      const result = await createXianyuQRBrowserVNCTicket(sessionId);
      setQrBrowserConnected(false);
      setQrBrowserSocketUrl(createIMVerificationVNCWebSocketUrl(result.ticket));
    } catch (error) {
      message.error(error instanceof Error ? error.message : "远程登录画面连接失败");
    } finally {
      setQrBrowserLoading(false);
    }
  }

  async function runQRBrowserVerificationStart() {
    if (!qrLogin) {
      return;
    }
    setQrBrowserLoading(true);
    setQrBrowserSocketUrl("");
    try {
      const current = await startXianyuQRBrowserVerification(qrLogin.session_id);
      setQrBrowserVerification(current);
      setQrLogin((login) =>
        login ? { ...login, status: "browser_verification", error: null } : login
      );
      setQrModalOpen(false);
      setQrBrowserOpen(true);
      if (current.status === "ready" && current.vnc_available) {
        await connectQRBrowserViewer(qrLogin.session_id);
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "远程登录验证启动失败");
    } finally {
      setQrBrowserLoading(false);
    }
  }

  async function runQRBrowserVerificationComplete() {
    if (!qrLogin) {
      return;
    }
    setQrBrowserLoading(true);
    try {
      const current = await completeXianyuQRBrowserVerification(qrLogin.session_id);
      setQrLogin(current);
      setQrBrowserSocketUrl("");
      setQrBrowserOpen(false);
      setDrawerOpen(false);
      message.success("闲鱼登录凭据已验证并保存");
      await load();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "登录凭据检查失败，请继续完成验证");
      setQrBrowserVerification((current) =>
        current ? { ...current, status: "ready", message: error instanceof Error ? error.message : "登录凭据尚未完成" } : current
      );
    } finally {
      setQrBrowserLoading(false);
    }
  }

  async function runQRBrowserVerificationCancel() {
    if (!qrLogin) {
      return;
    }
    setQrBrowserLoading(true);
    try {
      const current = await cancelXianyuQRBrowserVerification(qrLogin.session_id);
      setQrBrowserVerification(current);
      setQrBrowserSocketUrl("");
      setQrBrowserOpen(false);
      setQrLogin((login) => login ? { ...login, status: "error", error: current.message } : login);
      setQrModalOpen(true);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "取消远程登录失败");
    } finally {
      setQrBrowserLoading(false);
    }
  }

  async function runReconnect(account: Account) {
    setRecoveringAccountId(account.account_id);
    try {
      await startAccount(account.account_id);
      message.success("恢复连接请求已发送");
      await load();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "恢复连接失败");
    } finally {
      setRecoveringAccountId(null);
    }
  }

  async function applyAccountEnabled(account: Account, enabled: boolean) {
    try {
      await updateAccount(account.account_id, { enabled });
      message.success(enabled ? "账户已启用" : "账户已停用");
      await load();
    } catch (error) {
      message.error(error instanceof Error ? error.message : enabled ? "启用账户失败" : "停用账户失败");
    }
  }

  function runToggleAccountEnabled(account: Account) {
    if (!account.enabled) {
      void applyAccountEnabled(account, true);
      return;
    }
    Modal.confirm({
      title: "停用账户",
      content: `确认停用「${accountDisplayName(account)}」？账户连接会断开，并停止接收新消息。`,
      okText: "停用",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: () => applyAccountEnabled(account, false)
    });
  }

  async function showCookieRenewalStatus(account: Account) {
    setCookieRenewalAccount(account);
    setCookieRenewalOpen(true);
    setCookieRenewalLoading(true);
    try {
      setCookieRenewalStatus(await getCookieRenewalStatus(account.account_id));
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载续期状态失败");
    } finally {
      setCookieRenewalLoading(false);
    }
  }

  async function runCookieRenewal(account: Account) {
    setCookieRenewalAccount(account);
    setCookieRenewalOpen(true);
    setCookieRenewalLoading(true);
    try {
      const status = await startCookieRenewal(account.account_id);
      setCookieRenewalStatus(status);
      message.info(status.state === "running" ? "Cookie 续期已开始" : status.message || "续期请求已提交");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "启动 Cookie 续期失败");
    } finally {
      setCookieRenewalLoading(false);
    }
  }

  async function connectAccountBrowserViewer(
    session: AccountBrowserSession,
    requestId = accountBrowserRequestRef.current
  ) {
    setAccountBrowserLoading(true);
    try {
      const result = await createAccountBrowserVNCTicket(session.session_id);
      if (requestId !== accountBrowserRequestRef.current) return;
      setAccountBrowserConnected(false);
      setAccountBrowserSocketUrl(createIMVerificationVNCWebSocketUrl(result.ticket));
    } catch (error) {
      if (requestId === accountBrowserRequestRef.current) {
        message.error(error instanceof Error ? error.message : "VNC 浏览器画面连接失败");
      }
    } finally {
      if (requestId === accountBrowserRequestRef.current) {
        setAccountBrowserLoading(false);
      }
    }
  }

  function updateAccountFingerprintSnapshot(
    accountId: string,
    snapshot: BrowserFingerprintSnapshot
  ) {
    setAccounts((items) => {
      const next = items.map((item) =>
        item.account_id === accountId
          ? {
              ...item,
              browser_identity: {
                ...(item.browser_identity ?? defaultBrowserIdentity()),
                fingerprint_snapshot: snapshot
              }
            }
          : item
      );
      accountsRef.current = next;
      return next;
    });
    setAccountBrowserAccount((current) =>
      current?.account_id === accountId
        ? {
            ...current,
            browser_identity: {
              ...(current.browser_identity ?? defaultBrowserIdentity()),
              fingerprint_snapshot: snapshot
            }
          }
        : current
    );
    setEditing((current) =>
      current?.account_id === accountId
        ? {
            ...current,
            browser_identity: {
              ...(current.browser_identity ?? defaultBrowserIdentity()),
              fingerprint_snapshot: snapshot
            }
          }
        : current
    );
  }

  function updateAccountBrowserStatus(session: AccountBrowserSession | null, accountId: string) {
    if (session?.fingerprint_snapshot) {
      updateAccountFingerprintSnapshot(accountId, session.fingerprint_snapshot);
    }
    setAccountBrowserStatuses((items) => {
      const next = { ...items };
      if (isActiveAccountBrowser(session)) {
        next[accountId] = session!;
      } else {
        delete next[accountId];
      }
      return next;
    });
  }

  async function openAccountBrowser(account: Account) {
    const requestId = ++accountBrowserRequestRef.current;
    setAccountBrowserAccount(account);
    setAccountBrowserSession(accountBrowserStatuses[account.account_id] ?? null);
    setAccountBrowserError("");
    setAccountBrowserSocketUrl("");
    setAccountBrowserConnected(false);
    setAccountBrowserPasteText("");
    setAccountBrowserPasting(false);
    accountBrowserActivitySentAtRef.current = 0;
    setAccountBrowserOpen(true);
    setAccountBrowserLoading(true);
    try {
      const current = await getAccountBrowserSession(account.account_id);
      if (requestId !== accountBrowserRequestRef.current) return;
      setAccountBrowserSession(current);
      updateAccountBrowserStatus(current, account.account_id);
      if (current.status === "ready" && current.vnc_available) {
        await connectAccountBrowserViewer(current, requestId);
      }
    } catch (error) {
      if (requestId !== accountBrowserRequestRef.current) return;
      if (error instanceof ApiRequestError && error.status === 404) {
        setAccountBrowserSession(null);
        updateAccountBrowserStatus(null, account.account_id);
      } else {
        const detail = error instanceof Error ? error.message : "平台账户浏览器状态读取失败";
        setAccountBrowserError(detail);
        message.error(detail);
      }
    } finally {
      if (requestId === accountBrowserRequestRef.current) {
        setAccountBrowserLoading(false);
      }
    }
  }

  async function beginAccountBrowserSession() {
    const account = accountBrowserAccount;
    if (!account) return;
    const requestId = ++accountBrowserRequestRef.current;
    setAccountBrowserLoading(true);
    setAccountBrowserError("");
    setAccountBrowserSocketUrl("");
    setAccountBrowserConnected(false);
    try {
      const current = await startAccountBrowserSession(account.account_id);
      updateAccountBrowserStatus(current, account.account_id);
      if (requestId !== accountBrowserRequestRef.current) return;
      setAccountBrowserSession(current);
      if (current.status === "ready" && current.vnc_available) {
        await connectAccountBrowserViewer(current, requestId);
      }
    } catch (error) {
      if (requestId !== accountBrowserRequestRef.current) return;
      const detail = error instanceof Error ? error.message : "平台账户浏览器启动失败";
      setAccountBrowserError(detail);
      message.error(detail);
    } finally {
      if (requestId === accountBrowserRequestRef.current) {
        setAccountBrowserLoading(false);
      }
    }
  }

  async function finishAccountBrowserSession() {
    const session = accountBrowserSession;
    if (!session) return;
    const requestId = ++accountBrowserRequestRef.current;
    setAccountBrowserLoading(true);
    setAccountBrowserSocketUrl("");
    setAccountBrowserConnected(false);
    try {
      const current = await closeAccountBrowserSession(session.session_id);
      updateAccountBrowserStatus(null, session.account_id);
      if (requestId !== accountBrowserRequestRef.current) return;
      setAccountBrowserSession(current);
      if (
        ["auth_recovery", "account_mismatch", "unknown", "failed"].includes(
          current.cookie_sync_status
        )
      ) {
        message.warning(current.message || "平台账户浏览器已关闭，Cookie 状态需要复核");
      } else {
        message.success(current.message || "平台账户浏览器已关闭");
      }
    } catch (error) {
      if (requestId === accountBrowserRequestRef.current) {
        message.error(error instanceof Error ? error.message : "平台账户浏览器关闭失败");
      }
    } finally {
      if (requestId === accountBrowserRequestRef.current) {
        setAccountBrowserLoading(false);
      }
    }
  }

  async function runAccountBrowserFingerprintDetection(
    targetSession: AccountBrowserSession | null = accountBrowserSession
  ) {
    const session = targetSession;
    if (!session || session.status !== "ready") return;
    setAccountBrowserDetecting(true);
    const collecting = {
      ...session,
      fingerprint_detection_status: "collecting" as const,
      fingerprint_detection_error: null
    };
    updateAccountBrowserStatus(collecting, session.account_id);
    setAccountBrowserSession((current) =>
      current?.session_id === session.session_id ? collecting : current
    );
    try {
      const current = await detectAccountBrowserFingerprint(session.session_id);
      setAccountBrowserSession((selected) =>
        selected?.session_id === session.session_id ? current : selected
      );
      updateAccountBrowserStatus(current, current.account_id);
      message.success("浏览器指纹检测已完成");
    } catch (error) {
      const detail = error instanceof Error ? error.message : "浏览器指纹检测失败";
      const failed = {
        ...session,
        fingerprint_detection_status: "failed" as const,
        fingerprint_detection_error: detail
      };
      updateAccountBrowserStatus(failed, session.account_id);
      setAccountBrowserSession((current) =>
        current?.session_id === session.session_id ? {
          ...current,
          fingerprint_detection_status: "failed",
          fingerprint_detection_error: detail
        } : current
      );
      message.error(detail);
    } finally {
      setAccountBrowserDetecting(false);
    }
  }

  async function pasteTextIntoAccountBrowser() {
    const session = accountBrowserSession;
    const text = accountBrowserPasteText;
    if (!session || session.status !== "ready" || !text.trim()) return;
    setAccountBrowserPasting(true);
    try {
      const current = await pasteAccountBrowserText(session.session_id, text);
      setAccountBrowserSession((selected) =>
        selected?.session_id === current.session_id ? current : selected
      );
      updateAccountBrowserStatus(current, current.account_id);
      setAccountBrowserPasteText("");
      setAccountBrowserClock(Date.now());
      message.success("文本已粘贴到当前网页焦点");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "文本粘贴失败");
    } finally {
      setAccountBrowserPasting(false);
    }
  }

  function reportAccountBrowserActivity() {
    const session = accountBrowserSession;
    if (!session || session.status !== "ready") return;
    const now = Date.now();
    if (now - accountBrowserActivitySentAtRef.current < 15_000) return;
    accountBrowserActivitySentAtRef.current = now;
    void touchAccountBrowserSession(session.session_id)
      .then((current) => {
        setAccountBrowserSession((selected) =>
          selected?.session_id === current.session_id ? current : selected
        );
        updateAccountBrowserStatus(current, current.account_id);
        setAccountBrowserClock(Date.now());
      })
      .catch(() => {
        accountBrowserActivitySentAtRef.current = 0;
      });
  }

  function closeAccountBrowserDrawer() {
    ++accountBrowserRequestRef.current;
    setAccountBrowserOpen(false);
    setAccountBrowserSocketUrl("");
    setAccountBrowserConnected(false);
    setAccountBrowserLoading(false);
    setAccountBrowserPasteText("");
    setAccountBrowserPasting(false);
    accountBrowserActivitySentAtRef.current = 0;
  }

  function confirmClearAccountBrowserProfile() {
    const account = accountBrowserAccount;
    if (!account || isActiveAccountBrowser(accountBrowserSession)) return;
    Modal.confirm({
      title: "清理 VNC 浏览器数据",
      content:
        "将删除该账户浏览器 Profile，包括缓存、浏览器 Cookie、LocalStorage 和登录状态。数据库中的账户 Cookie 不受影响，下次开启会重新注入。",
      okText: "确认清理",
      okButtonProps: { danger: true },
      cancelText: "取消",
      async onOk() {
        setAccountBrowserClearing(true);
        try {
          const result = await clearAccountBrowserProfile(account.account_id);
          message.success(privacyMaskEnabled ? "浏览器目录已清理" : result.message);
          if (browserProfileDrawerOpen) {
            await loadBrowserProfileData(true);
          }
        } catch (error) {
          message.error(error instanceof Error ? error.message : "VNC 浏览器数据清理失败");
          throw error;
        } finally {
          setAccountBrowserClearing(false);
        }
      }
    });
  }

  async function loadBrowserRuntime(silent = false) {
    if (!silent) setBrowserRuntimeLoading(true);
    try {
      setBrowserRuntime(await getBrowserRuntimeSetting());
    } catch (error) {
      if (!silent) {
        message.error(error instanceof Error ? error.message : "浏览器运行环境读取失败");
      }
    } finally {
      if (!silent) setBrowserRuntimeLoading(false);
    }
  }

  async function installStandardBrowserFromFile(file: File) {
    setBrowserRuntimeAction("standard:upload");
    try {
      const installed = await uploadStandardBrowser(file);
      message.success(`标准 Chrome ${installed.version} 已安装`);
      await loadBrowserRuntime(true);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "标准 Chrome 压缩包安装失败");
    } finally {
      setBrowserRuntimeAction(null);
    }
  }

  async function downloadLatestStandardBrowser() {
    setBrowserRuntimeAction("standard:download");
    try {
      const installed = await downloadStandardBrowser();
      message.success(`标准 Chrome ${installed.version} 已下载并安装`);
      await loadBrowserRuntime(true);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "标准 Chrome 下载失败");
    } finally {
      setBrowserRuntimeAction(null);
    }
  }

  async function activateStandardBrowserVersion(version: string | null) {
    const action = `standard:activate:${version || "system"}`;
    setBrowserRuntimeAction(action);
    try {
      const runtime = await activateStandardBrowser(version);
      setBrowserRuntime(runtime);
      message.success(
        version ? `已将 ${version} 设为默认标准 Chrome` : "已将系统 Chromium 设为默认"
      );
    } catch (error) {
      message.error(error instanceof Error ? error.message : "标准 Chrome 默认版本更新失败");
    } finally {
      setBrowserRuntimeAction(null);
    }
  }

  async function installFingerprintBrowserFromFile(file: File) {
    setBrowserRuntimeAction("upload");
    try {
      const installed = await uploadFingerprintBrowser(file);
      message.success(`Fingerprint Chromium ${installed.version} 已安装`);
      await loadBrowserRuntime(true);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "浏览器压缩包安装失败");
    } finally {
      setBrowserRuntimeAction(null);
    }
  }

  async function downloadLatestFingerprintBrowser() {
    setBrowserRuntimeAction("download");
    try {
      const installed = await downloadFingerprintBrowser();
      message.success(`Fingerprint Chromium ${installed.version} 已下载并安装`);
      await loadBrowserRuntime(true);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "浏览器一键下载失败");
    } finally {
      setBrowserRuntimeAction(null);
    }
  }

  async function activateFingerprintBrowserVersion(version: string) {
    setBrowserRuntimeAction(`activate:${version}`);
    try {
      await activateFingerprintBrowser(version);
      message.success(`已将 ${version} 设为默认 Fingerprint Chromium`);
      await loadBrowserRuntime(true);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "浏览器版本启用失败");
    } finally {
      setBrowserRuntimeAction(null);
    }
  }

  async function loadBrowserProfileData(silent = false) {
    if (!silent) setBrowserProfilesLoading(true);
    try {
      const profiles = await listBrowserProfiles();
      setBrowserProfiles(profiles);
    } catch (error) {
      if (!silent) {
        message.error(error instanceof Error ? error.message : "浏览器目录读取失败");
      }
    } finally {
      if (!silent) setBrowserProfilesLoading(false);
    }
  }

  function openBrowserProfileDrawer() {
    setBrowserProfileDrawerOpen(true);
    void Promise.all([loadBrowserProfileData(), loadBrowserRuntime(true)]);
  }

  async function stopManagedBrowserProfile(profile: BrowserProfile) {
    setBrowserProfileStoppingKey(profile.profile_key);
    try {
      const result = await stopBrowserProfile(profile.profile_key);
      message.success(privacyMaskEnabled ? "浏览器目录操作完成" : result.message);
      const [profiles, sessions] = await Promise.all([
        listBrowserProfiles(),
        listActiveAccountBrowserSessions()
      ]);
      setBrowserProfiles(profiles);
      setAccountBrowserStatuses(
        Object.fromEntries(sessions.map((session) => [session.account_id, session]))
      );
      if (profile.account_id === accountBrowserAccount?.account_id) {
        setAccountBrowserSocketUrl("");
        setAccountBrowserConnected(false);
        setAccountBrowserSession((current) =>
          current
            ? {
                ...current,
                status: "closed",
                message: "浏览器会话已由目录管理停止",
                vnc_available: false,
                cdp_available: false
              }
            : current
        );
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "浏览器会话停止失败");
    } finally {
      setBrowserProfileStoppingKey(null);
    }
  }

  function confirmClearManagedBrowserProfile(profile: BrowserProfile) {
    Modal.confirm({
      title: "清理浏览器数据目录",
      content: profile.account_exists
        ? `将删除“${accountDisplayName(accounts.find(account => account.account_id === profile.account_id))}”的浏览器缓存与浏览器登录态。数据库 Cookie 不受影响。`
        : `该目录未绑定现有账户，确认删除“${privateId(profile.directory_name)}”及其中的浏览器数据？`,
      okText: "确认清理",
      okButtonProps: { danger: true },
      cancelText: "取消",
      async onOk() {
        setBrowserProfileClearingKey(profile.profile_key);
        try {
          const result = await clearBrowserProfile(profile.profile_key);
          message.success(privacyMaskEnabled ? "验证操作已完成" : result.message);
          await loadBrowserProfileData(true);
        } catch (error) {
          message.error(error instanceof Error ? error.message : "浏览器目录清理失败");
          throw error;
        } finally {
          setBrowserProfileClearingKey(null);
        }
      }
    });
  }

  async function connectIMVerificationViewer(verification: IMVerification) {
    setIMVerificationLoading(true);
    try {
      const result = await createIMVerificationVNCTicket(verification.verification_id);
      setIMVerificationConnected(false);
      setIMVerificationSocketUrl(createIMVerificationVNCWebSocketUrl(result.ticket));
    } catch (error) {
      message.error(error instanceof Error ? error.message : "远程验证画面连接失败");
    } finally {
      setIMVerificationLoading(false);
    }
  }

  async function showIMVerification(account: Account) {
    setRecoveringAccountId(account.account_id);
    setIMVerificationAccount(account);
    setIMVerification(null);
    setIMVerificationSocketUrl("");
    setIMVerificationConnected(false);
    setIMVerificationOpen(true);
    setIMVerificationLoading(true);
    try {
      let current = await getAccountIMVerification(account.account_id);
      if (
        ["required", "starting", "failed", "expired", "cancelled"].includes(current.status) ||
        (current.status === "ready" && !current.vnc_available)
      ) {
        current = await startAccountIMVerification(account.account_id);
      }
      setIMVerification(current);
      if (current.status === "ready" && current.vnc_available) {
        await connectIMVerificationViewer(current);
      } else if (current.status === "completed") {
        message.success(current.message || "闲鱼 IM 已恢复在线");
        setIMVerificationOpen(false);
        await load();
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "安全验证启动失败");
      try {
        setIMVerification(await getAccountIMVerification(account.account_id));
      } catch {
        // Keep the drawer open with the platform error already shown above.
      }
    } finally {
      setIMVerificationLoading(false);
      setRecoveringAccountId(null);
    }
  }

  async function runIMVerificationStart() {
    if (!imVerificationAccount) {
      return;
    }
    setIMVerificationLoading(true);
    setIMVerificationSocketUrl("");
    try {
      const current = await startAccountIMVerification(imVerificationAccount.account_id);
      setIMVerification(current);
      if (current.status === "ready" && current.vnc_available) {
        await connectIMVerificationViewer(current);
      } else if (current.status === "completed") {
        message.success(current.message || "闲鱼 IM 已恢复在线");
        await load();
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "重新启动安全验证失败");
      try {
        setIMVerification(await getAccountIMVerification(imVerificationAccount.account_id));
      } catch {
        // Keep the last visible state.
      }
    } finally {
      setIMVerificationLoading(false);
    }
  }

  async function runIMVerificationComplete() {
    if (!imVerification) {
      return;
    }
    setIMVerificationLoading(true);
    try {
      const current = await completeIMVerification(imVerification.verification_id);
      setIMVerification(current);
      setIMVerificationSocketUrl("");
      if (current.status === "completed") {
        message.success(current.message || "闲鱼 IM 已恢复在线");
        setIMVerificationOpen(false);
      } else {
        message.warning(current.message || "平台仍要求安全验证，请重新开始");
      }
      await load();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "验证结果提交失败");
      if (imVerificationAccount) {
        try {
          setIMVerification(await getAccountIMVerification(imVerificationAccount.account_id));
        } catch {
          // Keep the last visible state.
        }
      }
    } finally {
      setIMVerificationLoading(false);
    }
  }

  async function runIMVerificationCancel() {
    if (!imVerification) {
      setIMVerificationOpen(false);
      return;
    }
    setIMVerificationLoading(true);
    try {
      setIMVerification(await cancelIMVerification(imVerification.verification_id));
      setIMVerificationSocketUrl("");
      setIMVerificationOpen(false);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "取消安全验证失败");
    } finally {
      setIMVerificationLoading(false);
    }
  }

  function openCreateProxyDrawer() {
    if (!privacyAllowsSensitiveEditor()) return;
    setEditingProxy(null);
    proxyForm.resetFields();
    proxyForm.setFieldsValue({
      name: "",
      enabled: true,
      scheme: "socks5h",
      host: "",
      username: "",
      password: ""
    });
    setProxyDrawerOpen(true);
  }

  function openEditProxyDrawer(proxy: ProxyResource) {
    if (!privacyAllowsSensitiveEditor()) return;
    setEditingProxy(proxy);
    proxyForm.setFieldsValue({
      name: proxy.name,
      enabled: proxy.enabled,
      scheme: proxy.scheme,
      host: proxy.host,
      port: proxy.port,
      username: proxy.username || "",
      password: ""
    });
    setProxyDrawerOpen(true);
  }

  async function submitProxyForm() {
    const values = await proxyForm.validateFields();
    const normalizedValues: ProxyFormValues = {
      ...values,
      name: values.name.trim(),
      host: values.host.trim(),
      username: values.username?.trim() || null,
      password: values.password?.trim() || null
    };
    setProxySaving(true);
    try {
      if (editingProxy) {
        const payload: Partial<ProxyFormValues> = {};
        if (normalizedValues.name !== editingProxy.name) payload.name = normalizedValues.name;
        if (normalizedValues.enabled !== editingProxy.enabled) payload.enabled = normalizedValues.enabled;
        if (normalizedValues.scheme !== editingProxy.scheme) payload.scheme = normalizedValues.scheme;
        if (normalizedValues.host !== editingProxy.host) payload.host = normalizedValues.host;
        if (normalizedValues.port !== editingProxy.port) payload.port = normalizedValues.port;
        if (normalizedValues.username !== (editingProxy.username || null)) {
          payload.username = normalizedValues.username;
        }
        if (normalizedValues.password) payload.password = normalizedValues.password;
        if (!Object.keys(payload).length) {
          setProxyDrawerOpen(false);
          message.info("代理配置未变化");
          return;
        }
        await updateProxy(editingProxy.proxy_id, payload);
        message.success("代理已更新");
      } else {
        await createProxy(normalizedValues);
        message.success("代理已创建");
      }
      setProxyDrawerOpen(false);
      await loadProxyData(true);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存代理失败");
    } finally {
      setProxySaving(false);
    }
  }

  async function runProxyResourceTest(
    proxy: ProxyResource,
    options: { notify?: boolean; refresh?: boolean } = {}
  ): Promise<"success" | "failed" | "skipped"> {
    if (testingProxyIds.has(proxy.proxy_id)) {
      return "skipped";
    }
    const notify = options.notify !== false;
    const refresh = options.refresh !== false;
    setTestingProxyIds((current) => new Set(current).add(proxy.proxy_id));
    try {
      const result = await testProxy(proxy.proxy_id);
      if (notify && result.ok) {
        message.success(
          privacyMaskEnabled
            ? `代理检测通过${result.latency_ms != null ? `，${result.latency_ms}ms` : ""}`
            : `${result.message}${result.latency_ms != null ? `，${result.latency_ms}ms` : ""}`
        );
      } else if (notify) {
        message.error(privacyMaskEnabled ? "代理检测失败，详情已隐藏" : result.message);
      }
      if (refresh) {
        await loadProxyData(true);
      }
      return result.ok ? "success" : "failed";
    } catch (error) {
      if (notify) {
        message.error(error instanceof Error ? error.message : "代理测试失败");
      }
      return "failed";
    } finally {
      setTestingProxyIds((current) => {
        const next = new Set(current);
        next.delete(proxy.proxy_id);
        return next;
      });
    }
  }

  async function runProxyBatchTest() {
    if (proxyBatchProgress) {
      return;
    }
    const selected = new Set(selectedProxyIds);
    const requested = selected.size
      ? proxies.filter((proxy) => selected.has(proxy.proxy_id))
      : proxies.filter((proxy) => proxy.enabled);
    const targets = requested.filter(
      (proxy) =>
        proxy.enabled &&
        !testingProxyIds.has(proxy.proxy_id) &&
        !deletingProxyIds.has(proxy.proxy_id)
    );
    const initiallySkipped = requested.length - targets.length;
    if (!targets.length) {
      message.info(requested.length ? "所选代理正在检测或暂不可用" : "没有可检测的代理节点");
      return;
    }

    setQueuedProxyIds(new Set(targets.map((proxy) => proxy.proxy_id)));
    setProxyBatchProgress({ completed: 0, total: targets.length });
    const outcomes: Array<"success" | "failed" | "skipped"> = [];
    let cursor = 0;
    const worker = async () => {
      while (cursor < targets.length) {
        const target = targets[cursor];
        cursor += 1;
        setQueuedProxyIds((current) => {
          const next = new Set(current);
          next.delete(target.proxy_id);
          return next;
        });
        outcomes.push(
          await runProxyResourceTest(target, { notify: false, refresh: false })
        );
        setProxyBatchProgress((current) =>
          current ? { ...current, completed: current.completed + 1 } : current
        );
      }
    };

    try {
      await Promise.all(
        Array.from({ length: Math.min(3, targets.length) }, () => worker())
      );
      await loadProxyData(true);
      const successCount = outcomes.filter((outcome) => outcome === "success").length;
      const failedCount = outcomes.filter((outcome) => outcome === "failed").length;
      const skippedCount =
        initiallySkipped + outcomes.filter((outcome) => outcome === "skipped").length;
      const summary = `检测完成：成功 ${successCount}，失败 ${failedCount}，跳过 ${skippedCount}`;
      if (failedCount) {
        message.warning(summary);
      } else {
        message.success(summary);
      }
    } finally {
      setQueuedProxyIds(new Set());
      setProxyBatchProgress(null);
    }
  }

  async function removeProxy(proxy: ProxyResource) {
    Modal.confirm({
      title: "删除代理",
      content: `确认删除「${privateName(proxy.name)}」？`,
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      async onOk() {
        setDeletingProxyIds((current) => new Set(current).add(proxy.proxy_id));
        try {
          await deleteProxy(proxy.proxy_id);
          await loadProxyData(true);
        } finally {
          setDeletingProxyIds((current) => {
            const next = new Set(current);
            next.delete(proxy.proxy_id);
            return next;
          });
        }
      }
    });
  }

  async function runToggleAccountAutoReply(account: Account, enabled: boolean) {
    setAccountAutoReplyUpdatingId(account.account_id);
    try {
      const result = await updateAccountAutoReply(account.account_id, enabled);
      setAccounts((items) =>
        items.map((item) =>
          item.account_id === account.account_id
            ? { ...item, auto_reply_enabled: result.enabled }
            : item
        )
      );
      message.success(result.enabled ? "已开启智能回复" : "已关闭智能回复");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "更新智能回复开关失败");
    } finally {
      setAccountAutoReplyUpdatingId(null);
    }
  }

  async function runToggleAccountWorkspaceVisibility(
    account: Account,
    field: AccountWorkspaceVisibilityField,
    visible: boolean,
    workspaceLabel: string
  ) {
    const key = `${account.account_id}:${field}`;
    setAccountWorkspaceVisibilityUpdatingKeys((current) => new Set(current).add(key));
    try {
      const result = await updateAccountWorkspaceVisibility(account.account_id, {
        [field]: visible
      });
      setAccounts((items) => {
        const next = items.map((item) => item.account_id === result.account_id ? result : item);
        accountsRef.current = next;
        return next;
      });
      message.success(
        field === "chat_enabled"
          ? visible
            ? "已开启该账户的 Chatwoot 消息同步"
            : "已关闭该账户的 Chatwoot 消息同步，历史映射保留"
          : visible
            ? `已在${workspaceLabel}显示该账户`
            : `已从${workspaceLabel}隐藏，账户连接与自动回复不受影响`
      );
    } catch (error) {
      message.error(error instanceof Error ? error.message : `更新${workspaceLabel}显示设置失败`);
    } finally {
      setAccountWorkspaceVisibilityUpdatingKeys((current) => {
        const next = new Set(current);
        next.delete(key);
        return next;
      });
    }
  }

  async function loadEventsFor(accountId: string, quiet = false) {
    const requestId = ++runtimeLogRequestRef.current;
    if (!quiet) setEventsLoading(true);
    try {
      const nextEvents = await listAccountRuntimeEvents(accountId, 200);
      if (requestId === runtimeLogRequestRef.current) {
        setEvents(nextEvents);
      }
    } catch (error) {
      if (!quiet && requestId === runtimeLogRequestRef.current) {
        message.error(error instanceof Error ? error.message : "加载运行日志失败");
      }
    } finally {
      if (!quiet && requestId === runtimeLogRequestRef.current) {
        setEventsLoading(false);
      }
    }
  }

  function openRuntimeLogDrawer(account: Account) {
    runtimeLogRequestRef.current += 1;
    setEvents([]);
    setRuntimeLogAccount(account);
    setRuntimeLogOpen(true);
    void loadEventsFor(account.account_id);
  }

  async function loadConversationList(showInitialLoading = conversations.length === 0) {
    const requestId = ++conversationRequestRef.current;
    if (showInitialLoading) {
      setConversationsLoading(true);
    }
    try {
      let cursor: number | string | null = null;
      const snapshot: Conversation[] = [];
      let syncStatuses: ConversationAccountSync[] = [];
      do {
        const page = await listAggregateConversations({
          status: "all",
          limit: 200,
          cursor
        });
        if (requestId !== conversationRequestRef.current) {
          return;
        }
        snapshot.push(...page.items);
        if (page.account_statuses.length) {
          syncStatuses = page.account_statuses;
        }
        cursor = page.has_more ? page.next_cursor ?? null : null;
        if (cursor != null) {
          await new Promise((resolve) => window.setTimeout(resolve, 0));
        }
      } while (cursor != null);
      setConversationSyncStatuses(syncStatuses);
      setConversations((current) => {
        const snapshotByIdentity = new Map(
          snapshot.map((item) => [conversationIdentity(item), item])
        );
        const concurrentUpdates = current.filter((item) => {
          const snapshotItem = snapshotByIdentity.get(conversationIdentity(item));
          return (
            !snapshotItem ||
            apiTimeToEpochMs(item.updated_at) > apiTimeToEpochMs(snapshotItem.updated_at)
          );
        });
        return mergeConversationRecords(snapshot, concurrentUpdates);
      });
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载会话失败");
    } finally {
      if (requestId === conversationRequestRef.current) {
        setConversationsLoading(false);
      }
    }
  }

  function clearConversationWorkspace() {
    messageRequestRef.current += 1;
    historyRequestRef.current += 1;
    selectedConversationRef.current = null;
    mobileConversationDetailOpenRef.current = false;
    stickMessagesToBottomRef.current = true;
    forceBottomConversationRef.current = null;
    historyScrollAnchorRef.current = null;

    setSelectedConversation(null);
    setMobileConversationDetailOpen(false);
    setConversationAccount(null);
    setChatMessages([]);
    setChatMessagesLoading(false);
    setOlderMessagesLoading(false);
    setMessageHasMore(false);
    setMessageNextCursor(null);
    setConversationOrders([]);
    setDeliveryTemplates([]);
    setOrderDrawerOpen(false);
    setSelectedOrder(null);
    setOrderPreview(null);
    setOrderTemplateId(undefined);
    setOrderDeliveryContent("");
    setOrderLoading(false);
    setPlatformBlacklistState(null);
    setPlatformBlacklistLoading(false);
    setRecallingMessagePk(null);
    setQuickPhrasePopoverOpen(false);
    setQuickPhraseSearch("");
    if (composerNoticeTimerRef.current !== null) {
      window.clearTimeout(composerNoticeTimerRef.current);
      composerNoticeTimerRef.current = null;
    }
    setComposerNotice(null);
    sendForm.setFieldValue("text", "");
    clearPendingImages();
  }

  function changeConversationAccountFilter(accountId: string) {
    if (accountId !== conversationAccountFilter) {
      clearConversationWorkspace();
    }
    setConversationAccountFilter(accountId);
  }

  function changeConversationStatusFilter(status: ConversationStatusFilter) {
    clearConversationWorkspace();
    setConversationStatusFilter(status);
  }

  async function openConversation(conversation: Conversation) {
    const account = accounts.find((item) => item.account_id === conversation.account_id);
    if (!account?.conversation_visible || !accountIMAvailable(account)) {
      message.error("会话所属账户 IM 未在线，暂时无法查看会话");
      return;
    }
    const identity = conversationIdentity(conversation);
    const previousIdentity = selectedConversationRef.current
      ? conversationIdentity(selectedConversationRef.current)
      : null;
    historyRequestRef.current += 1;
    stickMessagesToBottomRef.current = true;
    forceBottomConversationRef.current = identity;
    historyScrollAnchorRef.current = null;
    setOlderMessagesLoading(false);
    setConversationAccount(account);
    selectedConversationRef.current = conversation;
    setSelectedConversation(conversation);
    setMobileConversationDetailOpen(true);
    sendForm.setFieldValue("text", "");
    if (previousIdentity !== identity) {
      setChatMessages([]);
      setMessageHasMore(false);
      setMessageNextCursor(null);
      setConversationOrders([]);
      setDeliveryTemplates([]);
    }
    const accountId = conversation.account_id;
    const conversationId = conversation.conversation_id;
    const requestId = ++messageRequestRef.current;
    setChatMessagesLoading(true);
    void loadConversationOrders(accountId, conversationId, identity);
    void loadPlatformBlacklistState(accountId, conversationId, identity);
    const itemSyncKey = `item:${identity}`;
    if (
      conversation.item_id &&
      Date.now() - (messageSyncAtRef.current.get(itemSyncKey) ?? 0) > 1800000
    ) {
      messageSyncAtRef.current.set(itemSyncKey, Date.now());
      void syncConversationItem(accountId, conversationId)
        .then((updated) => {
          setConversations((items) => mergeConversationRecords(items, [updated]));
          if (
            selectedConversationRef.current &&
            conversationIdentity(selectedConversationRef.current) === identity
          ) {
            const merged = { ...selectedConversationRef.current, ...updated };
            selectedConversationRef.current = merged;
            setSelectedConversation(merged);
          }
        })
        .catch(() => undefined);
    }
    try {
      const nextMessages = await listCachedMessages(accountId, conversationId, 100);
      if (
        requestId === messageRequestRef.current &&
        selectedConversationRef.current &&
        conversationIdentity(selectedConversationRef.current) === identity
      ) {
        setChatMessages((items) => mergeChatMessageRecords(items, nextMessages.items));
        setMessageHasMore(nextMessages.has_more);
        setMessageNextCursor(nextMessages.next_cursor ?? null);
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载会话消息失败");
    } finally {
      if (requestId === messageRequestRef.current) {
        setChatMessagesLoading(false);
      }
    }

    try {
      const readConversation = await markConversationRead(accountId, conversationId);
      setConversations((items) => mergeConversationRecords(items, [readConversation]));
      if (
        requestId === messageRequestRef.current &&
        selectedConversationRef.current &&
        conversationIdentity(selectedConversationRef.current) === identity
      ) {
        const selectedRead = { ...conversation, ...readConversation };
        selectedConversationRef.current = selectedRead;
        setSelectedConversation(selectedRead);
      }
    } catch (error) {
      message.warning(error instanceof Error ? error.message : "标记会话已查看失败");
    }
    const lastMessageSyncAt = messageSyncAtRef.current.get(identity) ?? 0;
    if (
      selectedConversationRef.current &&
      conversationIdentity(selectedConversationRef.current) === identity &&
      Date.now() - lastMessageSyncAt > 120000
    ) {
      messageSyncAtRef.current.set(identity, Date.now());
      void refreshMessagesFor(accountId, conversationId, false);
    }
  }

  async function loadConversationOrders(
    accountId: string,
    conversationId: string,
    identity: string
  ) {
    setOrderLoading(true);
    try {
      const [nextOrders, templates] = await Promise.all([
        listConversationOrders(accountId, conversationId, 100),
        listDeliveryTemplates(accountId)
      ]);
      if (
        selectedConversationRef.current &&
        conversationIdentity(selectedConversationRef.current) === identity
      ) {
        setConversationOrders(nextOrders);
        setDeliveryTemplates(templates);
      }
    } catch (error) {
      if (
        selectedConversationRef.current &&
        conversationIdentity(selectedConversationRef.current) === identity
      ) {
        message.error(error instanceof Error ? error.message : "加载会话订单失败");
      }
    } finally {
      if (
        selectedConversationRef.current &&
        conversationIdentity(selectedConversationRef.current) === identity
      ) {
        setOrderLoading(false);
      }
    }
  }

  async function refreshMessagesFor(
    accountId: string,
    conversationId: string,
    showLoading = true
  ) {
    const requestId = ++messageRequestRef.current;
    if (showLoading) {
      setChatMessagesLoading(true);
    }
    try {
      const page = await syncMessages(accountId, conversationId, 100);
      if (
        requestId !== messageRequestRef.current ||
        selectedConversationRef.current?.account_id !== accountId ||
        selectedConversationRef.current?.conversation_id !== conversationId
      ) {
        return;
      }
      setChatMessages((items) => mergeChatMessageRecords(items, page.items));
      setMessageHasMore(page.has_more);
      setMessageNextCursor(page.next_cursor ?? null);
      if (showLoading && page.stale && page.error) {
        message.warning(
          privacyMaskEnabled
            ? "刷新失败，已保留本地缓存；错误详情已隐藏"
            : `刷新失败，已保留本地缓存：${page.error}`
        );
      }
    } catch (error) {
      if (showLoading) {
        message.error(error instanceof Error ? error.message : "刷新消息失败");
      }
    } finally {
      if (showLoading && requestId === messageRequestRef.current) {
        setChatMessagesLoading(false);
      }
    }
  }

  async function reloadSelectedConversation() {
    if (!conversationAccount || !selectedConversation) {
      return;
    }
    const identity = conversationIdentity(selectedConversation);
    stickMessagesToBottomRef.current = true;
    forceBottomConversationRef.current = identity;
    const [nextMessages, nextOrders] = await Promise.all([
      syncMessages(conversationAccount.account_id, selectedConversation.conversation_id, 100),
      listConversationOrders(conversationAccount.account_id, selectedConversation.conversation_id, 100)
    ]);
    if (
      selectedConversationRef.current &&
      conversationIdentity(selectedConversationRef.current) === identity
    ) {
      setChatMessages((items) => mergeChatMessageRecords(items, nextMessages.items));
      setMessageHasMore(nextMessages.has_more);
      setMessageNextCursor(nextMessages.next_cursor ?? null);
      setConversationOrders(nextOrders);
    }
  }

  function handleMessageScroll() {
    const container = messageListRef.current;
    if (!container) {
      return;
    }
    const distanceToBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    stickMessagesToBottomRef.current = distanceToBottom <= 80;
  }

  function handleMessageContentLoad() {
    if (
      activeMenuRef.current !== "conversations" ||
      !stickMessagesToBottomRef.current ||
      (compactLayoutRef.current && !mobileConversationDetailOpenRef.current)
    ) {
      return;
    }
    window.requestAnimationFrame(() => {
      const container = messageListRef.current;
      if (container && stickMessagesToBottomRef.current) {
        container.scrollTop = container.scrollHeight;
      }
    });
  }

  async function loadOlderMessages() {
    if (
      !conversationAccount ||
      !selectedConversation ||
      !messageHasMore ||
      messageNextCursor == null ||
      olderMessagesLoading
    ) {
      return;
    }
    const identity = conversationIdentity(selectedConversation);
    const requestId = ++historyRequestRef.current;
    stickMessagesToBottomRef.current = false;
    setOlderMessagesLoading(true);
    try {
      const page = await syncMessages(
        conversationAccount.account_id,
        selectedConversation.conversation_id,
        100,
        messageNextCursor
      );
      if (
        requestId !== historyRequestRef.current ||
        activeMenuRef.current !== "conversations" ||
        !selectedConversationRef.current ||
        conversationIdentity(selectedConversationRef.current) !== identity
      ) {
        return;
      }
      const container = messageListRef.current;
      if (container) {
        historyScrollAnchorRef.current = {
          height: container.scrollHeight,
          top: container.scrollTop
        };
      }
      setChatMessages((items) => mergeChatMessageRecords(page.items, items));
      setMessageHasMore(page.has_more);
      setMessageNextCursor(page.next_cursor ?? null);
    } catch (error) {
      if (requestId === historyRequestRef.current) {
        message.error(error instanceof Error ? error.message : "加载更早消息失败");
      }
    } finally {
      if (requestId === historyRequestRef.current) {
        setOlderMessagesLoading(false);
      }
    }
  }

  function clearPendingImages() {
    setPendingImages((items) => {
      items.forEach((item) => URL.revokeObjectURL(item.previewUrl));
      return [];
    });
    if (imageInputRef.current) {
      imageInputRef.current.value = "";
    }
  }

  function showComposerNotice(notice: string) {
    setComposerNotice(notice);
    if (composerNoticeTimerRef.current !== null) {
      window.clearTimeout(composerNoticeTimerRef.current);
    }
    composerNoticeTimerRef.current = window.setTimeout(() => {
      setComposerNotice(null);
      composerNoticeTimerRef.current = null;
    }, 4000);
  }

  function removePendingImage(clientRequestId: string) {
    setPendingImages((items) => {
      const removed = items.find((item) => item.clientRequestId === clientRequestId);
      if (removed) URL.revokeObjectURL(removed.previewUrl);
      return items.filter((item) => item.clientRequestId !== clientRequestId);
    });
  }

  function selectPendingImages(files: File[]) {
    const supportedTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
    const validFiles = files.filter((file) => {
      if (!supportedTypes.has(file.type)) {
        showComposerNotice(`${file.name}：仅支持 JPEG、PNG、WebP 图片`);
        return false;
      }
      if (file.size === 0) {
        showComposerNotice(`${file.name}：图片文件为空`);
        return false;
      }
      if (file.size > 10 * 1024 * 1024) {
        showComposerNotice(`${file.name}：图片大小不能超过 10 MB`);
        return false;
      }
      return true;
    });
    setPendingImages((items) => {
      const remaining = Math.max(0, 9 - items.length);
      if (validFiles.length > remaining) showComposerNotice("每次最多发送 9 张图片");
      return [
        ...items,
        ...validFiles.slice(0, remaining).map((file) => ({
          clientRequestId: createClientRequestId("message-image"),
          file,
          previewUrl: URL.createObjectURL(file),
          status: "queued" as const
        }))
      ];
    });
  }

  function handleImageSelected(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.currentTarget.files || []);
    event.currentTarget.value = "";
    if (files.length) selectPendingImages(files);
  }

  function handleComposerPaste(event: ClipboardEvent<HTMLTextAreaElement>) {
    const imageItems = Array.from(event.clipboardData.items).filter(
      (candidate) => candidate.kind === "file" && candidate.type.startsWith("image/")
    );
    if (!imageItems.length) return;
    const files = imageItems.flatMap((item) => {
      const file = item.getAsFile();
      if (!file) return [];
      const extension = file.type === "image/jpeg" ? "jpg" : file.type.split("/")[1] || "png";
      return [
        new File([file], `clipboard-${Date.now()}.${extension}`, {
          type: file.type,
          lastModified: Date.now()
        })
      ];
    });
    selectPendingImages(files);
  }

  function canSendFromConversationAccount(accountId: string): boolean {
    const account = accountsRef.current.find((item) => item.account_id === accountId);
    if (!account?.enabled || account.runtime.state !== "online") {
      message.warning("账户已离线，恢复连接后可发送消息");
      return false;
    }
    return true;
  }

  async function submitImages(): Promise<boolean> {
    if (!conversationAccount || !selectedConversation || !pendingImages.length) return false;
    if (!canSendFromConversationAccount(conversationAccount.account_id)) return false;
    const queue = pendingImages.filter((item) => item.status !== "sent");
    if (!queue.length) return true;
    setSending(true);
    stickMessagesToBottomRef.current = true;
    let sentCount = 0;
    let failedCount = 0;
    try {
      for (const pending of queue) {
        setPendingImages((items) =>
          items.map((item) =>
            item.clientRequestId === pending.clientRequestId
              ? { ...item, status: "sending", error: undefined }
              : item
          )
        );
        try {
          const result = await sendImage(
            conversationAccount.account_id,
            selectedConversation.conversation_id,
            pending.file,
            pending.clientRequestId
          );
          if (result.message) {
            setChatMessages((items) =>
              mergeChatMessageRecords(items, [result.message as ChatMessage])
            );
          }
          const status = result.success ? "sent" : "failed";
          sentCount += result.success ? 1 : 0;
          failedCount += result.success ? 0 : 1;
          setPendingImages((items) =>
            items.map((item) =>
              item.clientRequestId === pending.clientRequestId
                ? { ...item, status, error: result.error || undefined }
                : item
            )
          );
        } catch (error) {
          failedCount += 1;
          setPendingImages((items) =>
            items.map((item) =>
              item.clientRequestId === pending.clientRequestId
                ? {
                    ...item,
                    status: "failed",
                    error: error instanceof Error ? error.message : "图片发送失败"
                  }
                : item
            )
          );
        }
      }
      if (failedCount) showComposerNotice(`${failedCount} 张图片发送失败，已保留可重试`);
      setPendingImages((items) => {
        items.filter((item) => item.status === "sent").forEach((item) => {
          URL.revokeObjectURL(item.previewUrl);
        });
        return items.filter((item) => item.status !== "sent");
      });
      return failedCount === 0;
    } finally {
      setSending(false);
    }
  }

  async function submitText(text?: string): Promise<boolean> {
    if (!conversationAccount || !selectedConversation) {
      return false;
    }
    if (!canSendFromConversationAccount(conversationAccount.account_id)) {
      return false;
    }
    const receiverUserId = selectedConversation.peer_user_id?.trim();
    if (!receiverUserId) {
      message.error("当前会话缺少接收方用户 ID，无法发送消息");
      return false;
    }
    const content = (text ?? sendForm.getFieldValue("text") ?? "").trim();
    if (!content) return true;
    setSending(true);
    try {
      const result = await sendText(
        conversationAccount.account_id,
        selectedConversation.conversation_id,
        { text: content, receiver_user_id: receiverUserId }
      );
      if (result.message) {
        setChatMessages((items) => mergeChatMessageRecords(items, [result.message as ChatMessage]));
      }
      if (result.success) {
        message.success("消息已发送");
        sendForm.setFieldValue("text", "");
        return true;
      } else {
        showComposerNotice(result.error || "消息发送失败");
        return false;
      }
    } catch (error) {
      showComposerNotice(error instanceof Error ? error.message : "消息发送失败");
      return false;
    } finally {
      setSending(false);
    }
  }

  async function submitComposer() {
    const text = String(sendForm.getFieldValue("text") || "").trim();
    if (!pendingImages.length && !text) {
      showComposerNotice("请输入消息或选择图片");
      return;
    }
    if (pendingImages.length) {
      const imagesSent = await submitImages();
      if (!imagesSent) {
        if (text) showComposerNotice("图片未全部发送，文字已保留未发送");
        return;
      }
    }
    if (text) await submitText(text);
  }

  function handleComposerKeyDown(event: ReactKeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.nativeEvent.isComposing) {
      return;
    }

    if (event.ctrlKey || event.altKey) {
      event.preventDefault();
      const textarea = event.currentTarget;
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const nextValue = `${textarea.value.slice(0, start)}\n${textarea.value.slice(end)}`;
      const nextCaret = start + 1;
      sendForm.setFieldValue("text", nextValue);
      window.requestAnimationFrame(() => {
        textarea.focus();
        textarea.setSelectionRange(nextCaret, nextCaret);
      });
      return;
    }

    if (event.shiftKey) return;

    event.preventDefault();
    if (!sending) {
      void submitComposer();
    }
  }

  async function loadQuickPhraseData() {
    try {
      setQuickPhrases(await listQuickPhrases());
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载快捷短语失败");
    }
  }

  function startCreateQuickPhrase() {
    if (!privacyAllowsSensitiveEditor()) return;
    setQuickPhrasePopoverOpen(false);
    setEditingQuickPhrase(null);
    quickPhraseForm.setFieldsValue({
      title: "",
      content: "",
      group_name: "默认",
      sort_order: 0
    });
    setQuickPhraseManagerOpen(true);
  }

  function startEditQuickPhrase(phrase: QuickPhrase) {
    if (!privacyAllowsSensitiveEditor()) return;
    setEditingQuickPhrase(phrase);
    quickPhraseForm.setFieldsValue({
      title: phrase.title,
      content: phrase.content,
      group_name: phrase.group_name,
      sort_order: phrase.sort_order
    });
    setQuickPhraseManagerOpen(true);
  }

  async function saveQuickPhrase() {
    const values = await quickPhraseForm.validateFields();
    setQuickPhraseSaving(true);
    try {
      if (editingQuickPhrase) {
        await updateQuickPhrase(editingQuickPhrase.phrase_id, values);
        message.success("快捷短语已更新");
      } else {
        await createQuickPhrase(values);
        message.success("快捷短语已添加");
      }
      setEditingQuickPhrase(null);
      quickPhraseForm.resetFields();
      await loadQuickPhraseData();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存快捷短语失败");
    } finally {
      setQuickPhraseSaving(false);
    }
  }

  function confirmDeleteQuickPhrase(phrase: QuickPhrase) {
    Modal.confirm({
      title: "删除快捷短语",
      content: `确定删除“${privateName(phrase.title)}”吗？`,
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      async onOk() {
        await deleteQuickPhrase(phrase.phrase_id);
        if (editingQuickPhrase?.phrase_id === phrase.phrase_id) {
          setEditingQuickPhrase(null);
          quickPhraseForm.resetFields();
        }
        await loadQuickPhraseData();
      }
    });
  }

  async function applyQuickPhrase(phrase: QuickPhrase) {
    setQuickPhrasePopoverOpen(false);
    sendForm.setFieldValue("text", phrase.content);
    try {
      const updated = await touchQuickPhrase(phrase.phrase_id);
      setQuickPhrases((items) =>
        items.map((item) => (item.phrase_id === updated.phrase_id ? updated : item))
      );
    } catch {
      // Filling the composer remains useful even if recent-use tracking fails.
    }
  }

  async function loadPlatformBlacklistState(
    accountId: string,
    conversationId: string,
    identity: string
  ) {
    setPlatformBlacklistLoading(true);
    try {
      const result = await getPlatformBlacklist(accountId, conversationId);
      if (!result.success) throw new Error(result.error || "查询平台黑名单失败");
      if (
        selectedConversationRef.current &&
        conversationIdentity(selectedConversationRef.current) === identity
      ) {
        setPlatformBlacklistState(Boolean(result.blocked));
      }
    } catch (error) {
      if (
        selectedConversationRef.current &&
        conversationIdentity(selectedConversationRef.current) === identity
      ) {
        setPlatformBlacklistState(null);
        message.warning(error instanceof Error ? error.message : "查询平台黑名单失败");
      }
    } finally {
      if (
        selectedConversationRef.current &&
        conversationIdentity(selectedConversationRef.current) === identity
      ) {
        setPlatformBlacklistLoading(false);
      }
    }
  }

  function confirmPlatformBlacklistChange() {
    if (!conversationAccount || !selectedConversation || platformBlacklist == null) return;
    const blocked = !platformBlacklist;
    const identity = conversationIdentity(selectedConversation);
    Modal.confirm({
      title: blocked ? "加入闲鱼官方黑名单" : "解除闲鱼官方黑名单",
      content: blocked
        ? "加入后将由闲鱼平台屏蔽该会话。此操作不同于自动回复黑名单，确定继续吗？"
        : "确定从闲鱼官方黑名单中解除该会话吗？",
      okText: blocked ? "确认拉黑" : "确认解除",
      okButtonProps: blocked ? { danger: true } : undefined,
      cancelText: "取消",
      async onOk() {
        setPlatformBlacklistLoading(true);
        try {
          const result = await setPlatformBlacklist(
            conversationAccount.account_id,
            selectedConversation.conversation_id,
            blocked
          );
          if (!result.success) throw new Error(result.error || "平台黑名单操作失败");
          if (
            selectedConversationRef.current &&
            conversationIdentity(selectedConversationRef.current) === identity
          ) {
            setPlatformBlacklistState(Boolean(result.blocked));
          }
          message.success(blocked ? "已加入闲鱼官方黑名单" : "已解除闲鱼官方黑名单");
        } catch (error) {
          message.error(error instanceof Error ? error.message : "平台黑名单操作失败");
          throw error;
        } finally {
          setPlatformBlacklistLoading(false);
        }
      }
    });
  }

  async function runRecallMessage(chatMessage: ChatMessage) {
    if (!conversationAccount || !selectedConversation || !canRecallMessage(chatMessage)) return;
    setRecallingMessagePk(chatMessage.message_pk);
    try {
      const result = await recallMessage(
        conversationAccount.account_id,
        selectedConversation.conversation_id,
        chatMessage.message_pk
      );
      if (!result.success) throw new Error(result.error || "撤回失败");
      if (result.message) {
        setChatMessages((items) => mergeChatMessageRecords(items, [result.message as ChatMessage]));
      }
      message.success("消息已撤回");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "撤回失败");
    } finally {
      setRecallingMessagePk(null);
    }
  }

  async function loadAutoReplyData() {
    setAutoReplyLoading(true);
    try {
      const [rules, logs, issues] = await Promise.all([
        listAutoReplyRules(),
        listAutoReplyLogs(100),
        listAutoReplyRuleIssues()
      ]);
      setAutoReplyRules(rules);
      setAutoReplyLogs(logs);
      setAutoReplyRuleIssues(issues);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载自动回复配置失败");
    } finally {
      setAutoReplyLoading(false);
    }
  }

  async function loadAIProviderData() {
    setAIProviderLoading(true);
    try {
      const result = await getAIProviderSetting();
      setAIProvider(result);
      aiProviderForm.setFieldsValue({
        ai_base_url: result.base_url || "",
        ai_model: result.model || "",
        ai_api_key: ""
      });
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载 AI 服务配置失败");
    } finally {
      setAIProviderLoading(false);
    }
  }

  async function loadChatwootData() {
    setChatwootLoading(true);
    try {
      const result = await getChatwootConfig();
      setChatwootConfig(result);
      chatwootForm.setFieldsValue({
        enabled: result.enabled,
        account_alerts_enabled: result.account_alerts_enabled,
        offline_alert_delay_seconds: result.offline_alert_delay_seconds,
        base_url: result.base_url,
        inbox_identifier: result.inbox_identifier,
        callback_url: result.callback_url,
        webhook_secret: result.webhook_secret,
        client_hmac_token: result.client_hmac_token || "",
        clear_client_hmac_token: false,
        chatwoot_account_id: result.chatwoot_account_id ?? null,
        api_access_token: result.api_access_token || "",
        clear_api_access_token: false
      });
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载 Chatwoot 配置失败");
    } finally {
      setChatwootLoading(false);
    }
  }

  async function setWebNotificationEnabled(enabled: boolean) {
    setWebNotificationSaving(true);
    try {
      await applyWebNotificationConfig(await saveWebNotificationConfig(enabled));
      message.success(enabled ? "网页客户消息铃声已启用" : "网页客户消息铃声已关闭");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存网页铃声配置失败");
    } finally {
      setWebNotificationSaving(false);
    }
  }

  async function handleWebNotificationSoundUpload(file: File) {
    setWebNotificationUploading(true);
    try {
      const saved = await uploadWebNotificationSound(file);
      await applyWebNotificationConfig(saved);
      message.success("网页消息铃声已更新");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "上传网页消息铃声失败");
    } finally {
      setWebNotificationUploading(false);
    }
  }

  async function previewWebNotificationSound() {
    const context = getWebNotificationAudioContext();
    if (!context) {
      message.warning("当前浏览器不支持网页音频提醒");
      return;
    }
    try {
      await context.resume();
      if (
        webNotificationAudioBytesRef.current &&
        !webNotificationAudioBufferRef.current
      ) {
        await decodeWebNotificationSound();
      }
      setWebNotificationUnlocked(context.state === "running");
      playWebNotificationSound(true);
    } catch {
      message.warning("浏览器尚未允许播放声音，请先点击页面后再试听");
    }
  }

  function confirmClearWebNotificationSound() {
    Modal.confirm({
      title: "恢复默认叮咚铃声",
      content: "已上传的自定义铃声会被删除，网页端将改用内置的叮咚提示音。",
      okText: "恢复默认",
      cancelText: "取消",
      async onOk() {
        setWebNotificationUploading(true);
        try {
          await applyWebNotificationConfig(await clearWebNotificationSound());
          message.success("已恢复默认叮咚铃声");
        } catch (error) {
          message.error(error instanceof Error ? error.message : "恢复默认铃声失败");
          throw error;
        } finally {
          setWebNotificationUploading(false);
        }
      }
    });
  }

  async function saveChatwootConfiguration() {
    const values = await chatwootForm.validateFields();
    setChatwootSaving(true);
    try {
      const saved = await saveChatwootConfig({
        ...values,
        webhook_secret: values.webhook_secret || undefined,
        client_hmac_token: values.client_hmac_token || undefined,
        api_access_token: values.api_access_token || undefined
      });
      setChatwootConfig(saved);
      chatwootForm.setFieldsValue({
        enabled: saved.enabled,
        account_alerts_enabled: saved.account_alerts_enabled,
        offline_alert_delay_seconds: saved.offline_alert_delay_seconds,
        base_url: saved.base_url,
        inbox_identifier: saved.inbox_identifier,
        callback_url: saved.callback_url,
        webhook_secret: saved.webhook_secret,
        client_hmac_token: saved.client_hmac_token || "",
        clear_client_hmac_token: false,
        chatwoot_account_id: saved.chatwoot_account_id ?? null,
        api_access_token: saved.api_access_token || "",
        clear_api_access_token: false
      });
      message.success("Chatwoot 配置已保存");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存 Chatwoot 配置失败");
    } finally {
      setChatwootSaving(false);
    }
  }

  async function runChatwootTest() {
    setChatwootTesting(true);
    try {
      const result = await testChatwootConfig();
      message.success(result.message);
      await loadChatwootData();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "Chatwoot 连接测试失败");
      await loadChatwootData();
    } finally {
      setChatwootTesting(false);
    }
  }

  async function runChatwootAccountAlertTest() {
    setChatwootAlertTesting(true);
    try {
      const result = await testChatwootAccountAlerts();
      message.success(result.message);
      await loadChatwootData();
    } catch (error) {
      message.error(
        error instanceof Error ? error.message : "Chatwoot 账户提醒测试失败"
      );
      await loadChatwootData();
    } finally {
      setChatwootAlertTesting(false);
    }
  }

  async function saveAIProviderSetting() {
    const values = await aiProviderForm.validateFields();
    setAIProviderSaving(true);
    try {
      const result = await updateAIProviderSetting({
        ai_base_url: values.ai_base_url || null,
        ai_model: values.ai_model || null,
        ai_api_key: values.ai_api_key || null
      });
      setAIProvider(result);
      aiProviderForm.setFieldValue("ai_api_key", "");
      message.success("AI 服务配置已保存");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存 AI 服务配置失败");
    } finally {
      setAIProviderSaving(false);
    }
  }

  function clearAIProviderKey() {
    Modal.confirm({
      title: "删除已保存的 API Key",
      content: "删除后，所有 AI 回复规则会因缺少凭据而停止执行。",
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      async onOk() {
        const result = await updateAIProviderSetting({ clear_api_key: true });
        setAIProvider(result);
        aiProviderForm.setFieldValue("ai_api_key", "");
        message.success("API Key 已删除");
      }
    });
  }

  async function updateManualTakeoverMode(
    mode: "auto" | "temporary" | "permanent"
  ) {
    if (!conversationAccount || !selectedConversation) {
      return;
    }
    const apply = async () => {
      setManualTakeoverUpdating(true);
      try {
        const result = await setManualTakeover(
          conversationAccount.account_id,
          selectedConversation.conversation_id,
          mode,
          30
        );
        const updated = {
          ...selectedConversation,
          manual_takeover_mode: result.mode,
          manual_takeover_until: result.until || null
        };
        selectedConversationRef.current = updated;
        setSelectedConversation(updated);
        setConversations((items) =>
          items.map((item) =>
            conversationIdentity(item) === conversationIdentity(updated) ? updated : item
          )
        );
        message.success(
          result.mode === "auto"
            ? "已恢复自动回复"
            : result.mode === "permanent"
              ? "已永久接管当前会话"
              : "已人工接管 30 分钟"
        );
      } catch (error) {
        message.error(error instanceof Error ? error.message : "更新人工接管失败");
      } finally {
        setManualTakeoverUpdating(false);
      }
    };
    if (mode === "permanent") {
      Modal.confirm({
        title: "永久接管当前会话？",
        content: "永久接管后，此会话不会进入自动回复链路，直到手动恢复自动回复。",
        okText: "永久接管",
        okButtonProps: { danger: true },
        cancelText: "取消",
        onOk: apply
      });
      return;
    }
    await apply();
  }

  function startCreateRule() {
    if (!privacyAllowsSensitiveEditor()) return;
    setEditingRule(null);
    ruleForm.setFieldsValue({
      enabled: true,
      group_name: "",
      keyword: "",
      trigger_type: "keyword",
      match_mode: "contains",
      case_sensitive: false,
      account_ids: [],
      platform: "xianyu",
      message_type: "text",
      sender_user_id: "",
      conversation_id: "",
      item_id: "",
      cooldown_seconds: 0,
      action_type: "template",
      reply_text: "",
      continue_matching: false,
      context_message_count: 10,
      context_fields: DEFAULT_AUTO_REPLY_CONTEXT_FIELDS,
      ai_system_prompt: "",
      ai_temperature: 0.4
    });
    setRuleDrawerOpen(true);
  }

  function startEditRule(rule: AutoReplyRule) {
    if (!privacyAllowsSensitiveEditor()) return;
    setEditingRule(rule);
    ruleForm.setFieldsValue({
      enabled: rule.enabled,
      group_name: rule.group_name || "",
      keyword: rule.keyword,
      trigger_type: rule.trigger_type,
      match_mode: rule.match_mode,
      case_sensitive: rule.case_sensitive,
      account_ids: rule.account_ids,
      platform: rule.platform || "xianyu",
      message_type: rule.message_type || "text",
      sender_user_id: rule.sender_user_id || "",
      conversation_id: rule.conversation_id || "",
      item_id: rule.item_id || "",
      cooldown_seconds: rule.cooldown_seconds,
      action_type: rule.action_type,
      reply_text: rule.reply_text,
      continue_matching: rule.continue_matching,
      context_message_count: rule.context_message_count,
      context_fields: rule.context_fields,
      ai_system_prompt: rule.ai_system_prompt,
      ai_temperature: rule.ai_temperature
    });
    setRuleDrawerOpen(true);
  }

  async function submitRule() {
    const values = await ruleForm.validateFields();
    setAutoReplyLoading(true);
    try {
      if (editingRule) {
        await updateAutoReplyRule(editingRule.rule_id, values);
        message.success("规则已更新");
      } else {
        await createAutoReplyRule(values);
        message.success("规则已创建");
      }
      setEditingRule(null);
      setRuleDrawerOpen(false);
      ruleForm.resetFields();
      await loadAutoReplyData();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存规则失败");
    } finally {
      setAutoReplyLoading(false);
    }
  }

  async function removeRule(rule: AutoReplyRule) {
    Modal.confirm({
      title: "删除自动回复规则",
      content: `确认删除规则「${rule.group_name || rule.keyword || "未命中兜底"}」？`,
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      async onOk() {
        await deleteAutoReplyRule(rule.rule_id);
        message.success("规则已删除");
        await loadAutoReplyData();
      }
    });
  }

  async function reorderAutoReplyRuleRows(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id || autoReplyReordering) return;
    const currentIndex = autoReplyRules.findIndex((rule) => rule.rule_id === active.id);
    const targetIndex = autoReplyRules.findIndex((rule) => rule.rule_id === over.id);
    if (currentIndex < 0 || targetIndex < 0) return;
    const previous = autoReplyRules;
    const moved = arrayMove(previous, currentIndex, targetIndex);
    const next = [
      ...moved.filter((rule) => rule.trigger_type !== "fallback"),
      ...moved.filter((rule) => rule.trigger_type === "fallback")
    ];
    setAutoReplyRules(next);
    setAutoReplyReordering(true);
    try {
      const reordered = await reorderAutoReplyRules(next.map((rule) => rule.rule_id));
      setAutoReplyRules(reordered);
      setAutoReplyRuleIssues(await listAutoReplyRuleIssues());
      message.success("策略执行顺序已更新");
    } catch (error) {
      setAutoReplyRules(previous);
      message.error(error instanceof Error ? error.message : "更新策略顺序失败");
    } finally {
      setAutoReplyReordering(false);
    }
  }

  async function toggleAutoReplyRuleEnabled(rule: AutoReplyRule, enabled: boolean) {
    setAutoReplyUpdatingRuleId(rule.rule_id);
    try {
      const updated = await updateAutoReplyRule(rule.rule_id, { enabled });
      setAutoReplyRules((items) =>
        items.map((item) => item.rule_id === updated.rule_id ? updated : item)
      );
      setAutoReplyRuleIssues(await listAutoReplyRuleIssues());
      message.success(enabled ? "策略已启用" : "策略已关闭");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "更新策略状态失败");
    } finally {
      setAutoReplyUpdatingRuleId(null);
    }
  }

  function openAutoReplyPreview() {
    if (!privacyAllowsSensitiveEditor()) return;
    const currentAccountId = autoReplyPreviewForm.getFieldValue("account_id");
    autoReplyPreviewForm.setFieldsValue({
      account_id: currentAccountId || accounts[0]?.account_id,
      content: autoReplyPreviewForm.getFieldValue("content") || "请问商品还在吗",
      message_type: autoReplyPreviewForm.getFieldValue("message_type") || "text"
    });
    setAutoReplyPreviewResult(null);
    setAutoReplyPreviewOpen(true);
  }

  async function runAutoReplyPreview() {
    const values = await autoReplyPreviewForm.validateFields();
    setAutoReplyPreviewLoading(true);
    try {
      setAutoReplyPreviewResult(await previewAutoReply(values));
    } catch (error) {
      message.error(error instanceof Error ? error.message : "策略模拟失败");
    } finally {
      setAutoReplyPreviewLoading(false);
    }
  }

  async function loadDeliveryData(accountId: string) {
    setDeliveryLoading(true);
    try {
      const [templates, records, automation] = await Promise.all([
        listDeliveryTemplates(accountId),
        listDeliveryRecords(accountId, 100),
        getDeliveryAutomationSetting(accountId)
      ]);
      setDeliveryTemplates(templates);
      setDeliveryRecords(records);
      deliveryAutomationForm.setFieldsValue({
        enabled: automation.enabled,
        mode: automation.mode,
        require_order_card: automation.require_order_card,
        duplicate_guard_enabled: automation.duplicate_guard_enabled,
        order_status_allowlist_text: automation.order_status_allowlist.join("\n")
      });
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载发货数据失败");
    } finally {
      setDeliveryLoading(false);
    }
  }

  async function loadOrderData(
    accountId = orderAccountFilter,
    status = orderStatusFilter,
    keyword = orderKeyword,
    silent = false,
    scope = orderScope
  ) {
    if (!silent) setOrderLoading(true);
    try {
      setOrders(
        await listOrders({
          accountId: accountId === "all" ? null : accountId,
          status: status === "all" ? null : status,
          tradeRole: scope === "bought" ? "buyer" : "seller",
          confirmedOnly: true,
          managementVisibleOnly: true,
          keyword,
          limit: 500
        })
      );
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载订单失败");
    } finally {
      if (!silent) setOrderLoading(false);
    }
  }

  async function loadOrderManagement(
    accountId = orderAccountFilter,
    silent = false,
    scope = orderScope
  ) {
    const requestId = ++orderManagerRequestRef.current;
    if (!silent) setOrderLoading(true);
    try {
      const summaries = await listOrderManagementAccounts(scope);
      const effectiveAccountId =
        accountId === "all" || summaries.some((item) => item.account_id === accountId)
          ? accountId
          : "all";
      const [nextOrders, runs] = await Promise.all([
        listOrders({
          accountId: effectiveAccountId === "all" ? null : effectiveAccountId,
          status: orderStatusFilter === "all" ? null : orderStatusFilter,
          tradeRole: scope === "bought" ? "buyer" : "seller",
          confirmedOnly: true,
          managementVisibleOnly: true,
          keyword: orderKeyword,
          limit: 500
        }),
        effectiveAccountId === "all"
          ? Promise.resolve([] as OrderSyncRun[])
          : listOrderSyncRuns(effectiveAccountId, scope, 30)
      ]);
      if (requestId !== orderManagerRequestRef.current) return;
      setOrderManagerAccounts(summaries);
      setOrderAccountFilter(effectiveAccountId);
      setOrders(nextOrders);
      setOrderSyncRuns(runs);
    } catch (error) {
      if (!silent) message.error(error instanceof Error ? error.message : "加载订单管理失败");
    } finally {
      if (!silent && requestId === orderManagerRequestRef.current) setOrderLoading(false);
    }
  }

  async function selectOrderManagerAccount(accountId: string) {
    setOrderAccountFilter(accountId);
    setOrderHistoryOpen(false);
    if (accountId === "all") {
      setDeliveryAccount(null);
      setDeliveryTemplates([]);
      setDeliveryRecords([]);
      await loadOrderManagement("all");
      return;
    }
    const account = accounts.find((item) => item.account_id === accountId);
    await Promise.all([
      loadOrderManagement(accountId),
      account ? loadDeliveryWorkspace(account) : Promise.resolve()
    ]);
  }

  async function selectOrderScope(scope: OrderScope) {
    if (scope === orderScope) return;
    orderScopeRef.current = scope;
    setOrderScope(scope);
    setOrderStatusFilter("all");
    setOrderHistoryOpen(false);
    setOrderSettingsOpen(false);
    setSelectedOrder(null);
    await loadOrderManagement(orderAccountFilter, false, scope);
  }

  async function runOrderSync(
    accountId: string,
    mode: "full" | "pending" = "full",
    scope = orderScope
  ) {
    if (orderManagerAction) return;
    const action = `sync:${accountId}`;
    setOrderManagerAction(action);
    try {
      await syncOrders(accountId, scope, mode);
      message.success(
        scope === "bought"
          ? "已提交买入订单同步"
          : mode === "full" ? "已提交已售订单全量同步" : "已提交待发货订单同步"
      );
      if (accountId === orderAccountFilter) {
        await loadOrderManagement(accountId, true);
      } else {
        setOrderManagerAccounts(await listOrderManagementAccounts(scope));
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "提交订单同步失败");
    } finally {
      setOrderManagerAction(null);
    }
  }

  function openOrderSettings() {
    if (!selectedOrderManagerAccount) return;
    const setting = selectedOrderManagerAccount.setting;
    orderSyncSettingForm.setFieldsValue({
      sync_enabled: setting.sync_enabled,
      pending_interval_seconds: setting.pending_interval_seconds,
      full_interval_minutes: setting.full_interval_minutes,
      jitter_seconds: setting.jitter_seconds
    });
    setOrderSettingsOpen(true);
  }

  async function saveOrderSettings() {
    if (!selectedOrderManagerAccount) return;
    const values = await orderSyncSettingForm.validateFields();
    setOrderManagerAction("settings");
    try {
      await updateOrderSyncSetting(selectedOrderManagerAccount.account_id, orderScope, values);
      setOrderSettingsOpen(false);
      message.success("订单同步设置已保存");
      await loadOrderManagement(selectedOrderManagerAccount.account_id, true);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存订单同步设置失败");
    } finally {
      setOrderManagerAction(null);
    }
  }

  async function openOrderDetails(order: XianyuOrder) {
    setOrderDrawerOpen(true);
    setOrderLoading(true);
    setOrderPreview(null);
    setOrderTemplateId(undefined);
    setOrderDeliveryContent("");
    try {
      const [detail, templates] = await Promise.all([
        getOrder(order.order_pk),
        order.trade_role === "seller" ? listDeliveryTemplates(order.account_id) : Promise.resolve([])
      ]);
      setSelectedOrder(detail);
      setDeliveryTemplates(templates);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载订单详情失败");
    } finally {
      setOrderLoading(false);
    }
  }

  async function refreshSelectedOrder() {
    if (!selectedOrder) return;
    const orderPk = selectedOrder.order_pk;
    setOrderLoading(true);
    try {
      const detail = await syncOrder(orderPk);
      setSelectedOrder(detail);
      message.success("订单详情已从平台刷新");
      await loadOrderManagement(orderAccountFilter, true, orderScope);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "刷新订单详情失败");
    } finally {
      setOrderLoading(false);
    }
  }

  async function confirmOrderOperation(action: OrderAction) {
    if (!selectedOrder) return;
    const orderPk = selectedOrder.order_pk;
    const availability = selectedOrder.available_actions.find((item) => item.action === action);
    setOrderOperationAction(action);
    try {
      const preview = await previewOrderOperation(orderPk, action);
      if (!preview.eligible) {
        message.warning(preview.reasons.join("；") || availability?.reason || "当前不可执行该操作");
        const refreshed = await getOrder(orderPk);
        setSelectedOrder(refreshed);
        return;
      }
      const idempotencyKey = createClientRequestId(`order-${action}`);
      const isRate = action === "rate_buyer";
      const isOfflineShipping = action === "offline_shipping";
      const isRefuseRefund = action === "refuse_refund";
      const isDanger = action === "close_order" || isRefuseRefund;
      let trackingNo = "";
      let carrierCode = "";
      let refundReasonId = "";
      const basePrompt = isDanger
        ? action === "close_order"
          ? "关闭后交易将无法继续，请确认平台订单状态和退款情况。提交前系统会再次读取平台详情。"
          : "拒绝后平台将进入退款协商流程。提交前系统会再次读取退款详情和拒绝原因。"
        : `提交前系统会再次读取平台详情并校验是否可${preview.action.label}，请确认继续。`;
      const content = isOfflineShipping ? (
        <Space direction="vertical" size={12} className="content-stack">
          {preview.order.refund_status === "pending" || preview.order.refund_status === "processing" ? (
            <Alert
              type="warning"
              showIcon
              message="该订单同时存在退款申请"
              description="履约与退款为独立状态；仅在你确认仍需发货时继续。"
            />
          ) : null}
          <Text type="secondary">请填写平台使用的快递公司编码和快递单号。</Text>
          <Input
            placeholder="快递公司编码（cpCode）"
            onChange={(event) => { carrierCode = event.target.value.trim(); }}
          />
          <Input
            placeholder="快递单号"
            onChange={(event) => { trackingNo = event.target.value.trim(); }}
          />
        </Space>
      ) : isRefuseRefund ? (
        <Space direction="vertical" size={12} className="content-stack">
          <Text type="secondary">拒绝原因来自闲鱼当前退款单，提交前会再次校验。</Text>
          <Select
            className="content-stack"
            placeholder="请选择拒绝退款原因"
            options={preview.order.refund_refuse_options.map((item) => ({
              value: item.id,
              label: `${item.name}${item.proof_required ? "（需举证）" : ""}`,
              disabled: Boolean(item.proof_required)
            }))}
            onChange={(value) => { refundReasonId = value; }}
          />
          {preview.order.refund_refuse_options.some((item) => item.proof_required) ? (
            <Text type="warning">需要上传凭证或填写退款物流的原因，请前往闲鱼页面处理。</Text>
          ) : null}
        </Space>
      ) : basePrompt;
      Modal.confirm({
        title: `确认${preview.action.label}`,
        content,
        okText: preview.action.label,
        okButtonProps: { danger: isDanger },
        cancelText: "取消",
        async onOk() {
          if (isOfflineShipping && (!carrierCode || !trackingNo)) {
            message.warning("请填写快递公司编码和快递单号");
            throw new Error("missing shipping fields");
          }
          if (isRefuseRefund && !refundReasonId) {
            message.warning("请选择拒绝退款原因");
            throw new Error("missing refund reason");
          }
          setOrderOperationAction(action);
          try {
            const result = await executeOrderOperation(orderPk, {
              action,
              idempotency_key: idempotencyKey,
              feedback: isRate ? orderRateFeedback.trim() || "不错的买家，期待再次交易" : null,
              close_reason: action === "close_order" ? "其他原因" : null,
              tracking_no: isOfflineShipping ? trackingNo : null,
              carrier_code: isOfflineShipping ? carrierCode : null,
              refund_reason_id: isRefuseRefund ? refundReasonId : null
            });
            setSelectedOrder(result.order);
            await loadOrderManagement(orderAccountFilter, true, orderScope);
            if (result.operation.status === "succeeded") {
              message.success(result.operation.message || `${preview.action.label}成功`);
            } else if (result.operation.status === "uncertain") {
              message.warning("平台结果暂时无法确认，请先刷新订单状态，不要重复提交");
            } else {
              message.error(result.operation.error || `${preview.action.label}失败`);
            }
          } catch (error) {
            message.error(error instanceof Error ? error.message : `${preview.action.label}失败`);
            throw error;
          } finally {
            setOrderOperationAction(null);
          }
        }
      });
    } catch (error) {
      message.error(error instanceof Error ? error.message : "订单操作预检失败");
    } finally {
      setOrderOperationAction(null);
    }
  }

  async function openConversationOrderDrawer() {
    if (!selectedConversation) return;
    setOrderDrawerOpen(true);
    setOrderLoading(true);
    try {
      const nextOrders = await listConversationOrders(
        selectedConversation.account_id,
        selectedConversation.conversation_id,
        100
      );
      setConversationOrders(nextOrders);
      if (nextOrders.length > 0) {
        await openOrderDetails(nextOrders[0]);
      } else {
        setSelectedOrder(null);
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载会话订单失败");
    } finally {
      setOrderLoading(false);
    }
  }

  async function createOrderDeliveryPreview() {
    if (!selectedOrder) return;
    setOrderLoading(true);
    try {
      const preview = await previewOrderDelivery(selectedOrder.order_pk, {
        template_id: orderTemplateId,
        content: orderDeliveryContent || null
      });
      setOrderPreview(preview);
      setOrderDeliveryContent(preview.content);
      if (!preview.eligible) {
        message.warning(preview.reasons.join("；"));
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "生成发送预览失败");
    } finally {
      setOrderLoading(false);
    }
  }

  async function confirmOrderDelivery() {
    if (!selectedOrder) return;
    setOrderLoading(true);
    try {
      const preview = await previewOrderDelivery(selectedOrder.order_pk, {
        template_id: orderTemplateId,
        content: orderDeliveryContent || null
      });
      setOrderPreview(preview);
      setOrderDeliveryContent(preview.content);
      if (!preview.eligible) {
        message.warning(preview.reasons.join("；"));
        return;
      }
      Modal.confirm({
        title: "确认发送发货内容",
        content: "内容将通过当前闲鱼会话发送给买家。此操作不会代替闲鱼平台的物流发货确认。",
        okText: "确认发送",
        cancelText: "取消",
        async onOk() {
          const result = await sendOrderDelivery(selectedOrder.order_pk, {
            template_id: orderTemplateId,
            content: preview.content
          });
          if (!result.success) throw new Error(result.error || "发送失败");
          message.success("发货内容已发送");
          setSelectedOrder(await getOrder(selectedOrder.order_pk));
          await Promise.all([loadOrderData(), reloadSelectedConversation()]);
        }
      });
    } catch (error) {
      message.error(error instanceof Error ? error.message : "发送发货内容失败");
    } finally {
      setOrderLoading(false);
    }
  }

  async function loadDeliveryWorkspace(account: Account) {
    setDeliveryAccount(account);
    setEditingDeliveryTemplate(null);
    setPreparedDelivery(null);
    setDeliveryPreflight(null);
    deliveryTemplateForm.resetFields();
    deliveryAutomationForm.resetFields();
    await loadDeliveryData(account.account_id);
  }

  async function selectDeliveryAccount(account: Account) {
    await loadDeliveryWorkspace(account);
  }

  async function saveDeliveryAutomationSetting() {
    if (!deliveryAccount) {
      return;
    }
    const values = await deliveryAutomationForm.validateFields();
    setDeliveryLoading(true);
    try {
      await updateDeliveryAutomationSetting(deliveryAccount.account_id, values);
      message.success("自动发货配置已保存");
      await loadDeliveryData(deliveryAccount.account_id);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存自动发货配置失败");
    } finally {
      setDeliveryLoading(false);
    }
  }

  function startCreateDeliveryTemplate() {
    if (!privacyAllowsSensitiveEditor()) return;
    setEditingDeliveryTemplate(null);
    deliveryTemplateForm.setFieldsValue({
      name: "",
      enabled: true,
      content: "您好，您购买的资料如下：\\n\\n{item_id}\\n\\n请及时保存。",
      priority: 100
    });
  }

  function startEditDeliveryTemplate(template: DeliveryTemplate) {
    if (!privacyAllowsSensitiveEditor()) return;
    setEditingDeliveryTemplate(template);
    deliveryTemplateForm.setFieldsValue({
      name: template.name,
      enabled: template.enabled,
      content: template.content,
      priority: template.priority
    });
  }

  async function submitDeliveryTemplate() {
    if (!deliveryAccount) {
      return;
    }
    const values = await deliveryTemplateForm.validateFields();
    setDeliveryLoading(true);
    try {
      if (editingDeliveryTemplate) {
        await updateDeliveryTemplate(deliveryAccount.account_id, editingDeliveryTemplate.template_id, values);
        message.success("发货模板已更新");
      } else {
        await createDeliveryTemplate(deliveryAccount.account_id, values);
        message.success("发货模板已创建");
      }
      setEditingDeliveryTemplate(null);
      deliveryTemplateForm.resetFields();
      await loadDeliveryData(deliveryAccount.account_id);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存发货模板失败");
    } finally {
      setDeliveryLoading(false);
    }
  }

  async function removeDeliveryTemplate(template: DeliveryTemplate) {
    if (!deliveryAccount) {
      return;
    }
    Modal.confirm({
      title: "删除发货模板",
      content: `确认删除模板「${privateName(template.name)}」？`,
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      async onOk() {
        await deleteDeliveryTemplate(deliveryAccount.account_id, template.template_id);
        message.success("发货模板已删除");
        await loadDeliveryData(deliveryAccount.account_id);
      }
    });
  }

  async function sendPreparedDelivery(record?: DeliveryRecord | null) {
    const target = record || preparedDelivery;
    if (!target) {
      return;
    }
    setDeliveryLoading(true);
    try {
      const result = await sendDeliveryRecord(target.account_id, target.record_id);
      setPreparedDelivery(result.record);
      if (result.success) {
        message.success("发货内容已发送");
      } else {
        message.error(
          privacyMaskEnabled && result.error
            ? "发货失败，错误详情已隐藏"
            : result.error || "发货内容发送失败"
        );
      }
      if (deliveryAccount) {
        await loadDeliveryData(deliveryAccount.account_id);
      }
      await reloadSelectedConversation();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "发货内容发送失败");
    } finally {
      setDeliveryLoading(false);
    }
  }

  async function enqueuePreparedDelivery(record: DeliveryRecord) {
    setDeliveryLoading(true);
    try {
      await enqueueDeliveryRecord(record.account_id, record.record_id);
      message.success("发货任务已入队");
      if (deliveryAccount) {
        await loadDeliveryData(deliveryAccount.account_id);
      }
      await loadBackgroundTaskData();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "发货任务入队失败");
    } finally {
      setDeliveryLoading(false);
    }
  }

  async function runDeliveryPreflight(record: DeliveryRecord) {
    setDeliveryLoading(true);
    try {
      const result = await checkDeliveryPreflight(record.account_id, record.record_id);
      setDeliveryPreflight(result);
      if (result.eligible) {
        message.success("预检通过");
      } else {
        message.warning(result.reasons.join("；") || "预检未通过");
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "自动发货预检失败");
    } finally {
      setDeliveryLoading(false);
    }
  }

  async function loadProductRegionCatalog() {
    if (productRegionCatalog) {
      return productRegionCatalog;
    }
    setProductRegionLoading(true);
    try {
      const catalog = await listProductRegions();
      setProductRegionCatalog(catalog);
      return catalog;
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载全国区域目录失败");
      return null;
    } finally {
      setProductRegionLoading(false);
    }
  }

  async function loadAddressLibrary(preferredGroupId?: string | null) {
    setAddressLibraryLoading(true);
    try {
      void loadProductRegionCatalog();
      const groups = await listPublishAddressGroups();
      setAddressGroups(groups);
      const groupId =
        (preferredGroupId && groups.some((item) => item.group_id === preferredGroupId)
          ? preferredGroupId
          : selectedAddressGroupId && groups.some((item) => item.group_id === selectedAddressGroupId)
            ? selectedAddressGroupId
            : groups[0]?.group_id) || null;
      setSelectedAddressGroupId(groupId);
      if (groupId) {
        const [addresses, regions] = await Promise.all([
          listPublishAddresses(groupId),
          getPublishAddressRegions(groupId)
        ]);
        setPublishAddresses(addresses);
        setAddressRegionCodes(regions.region_codes);
      } else {
        setPublishAddresses([]);
        setAddressRegionCodes([]);
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载地址库失败");
    } finally {
      setAddressLibraryLoading(false);
    }
  }

  async function selectAddressGroup(groupId: string) {
    setSelectedAddressGroupId(groupId);
    setAddressLibraryLoading(true);
    try {
      const [addresses, regions] = await Promise.all([
        listPublishAddresses(groupId),
        getPublishAddressRegions(groupId)
      ]);
      setPublishAddresses(addresses);
      setAddressRegionCodes(regions.region_codes);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载分组地址失败");
    } finally {
      setAddressLibraryLoading(false);
    }
  }

  async function saveAddressRegions() {
    if (!selectedAddressGroupId) {
      return;
    }
    setAddressRegionSaving(true);
    try {
      const result = await replacePublishAddressRegions(
        selectedAddressGroupId,
        addressRegionCodes
      );
      setAddressRegionCodes(result.region_codes);
      await loadAddressLibrary(selectedAddressGroupId);
      message.success(`已保存 ${result.address_count} 个可发布区域`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存区域地址失败");
    } finally {
      setAddressRegionSaving(false);
    }
  }

  function openAddressGroupModal(group?: PublishAddressGroup) {
    if (!privacyAllowsSensitiveEditor()) return;
    setEditingAddressGroup(group || null);
    addressGroupForm.setFieldsValue({
      name: group?.name || "",
      enabled: group?.enabled ?? true,
      avoid_recent_count: group?.avoid_recent_count ?? 3,
      account_ids: group?.account_ids || []
    });
    setAddressGroupModalOpen(true);
  }

  async function saveAddressGroup() {
    const values = await addressGroupForm.validateFields();
    setAddressLibraryLoading(true);
    try {
      const group = editingAddressGroup
        ? await updatePublishAddressGroup(editingAddressGroup.group_id, values)
        : await createPublishAddressGroup(values);
      setAddressGroupModalOpen(false);
      await loadAddressLibrary(group.group_id);
      message.success(editingAddressGroup ? "地址分组已更新" : "地址分组已创建");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存地址分组失败");
    } finally {
      setAddressLibraryLoading(false);
    }
  }

  async function removeAddressGroup(group: PublishAddressGroup) {
    Modal.confirm({
      title: `删除地址分组“${privateName(group.name)}”？`,
      content: "引用此分组的草稿将恢复为账户默认所在地。",
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        await deletePublishAddressGroup(group.group_id);
        await loadAddressLibrary(null);
      }
    });
  }

  async function loadAddressImportLocations(accountId: string, refresh = false) {
    setAddressImportLoading(true);
    try {
      const result = await listProductLocations(accountId, refresh);
      setAddressImportLocations(result.items);
      if (result.warning) {
        message.warning(result.warning);
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "同步平台地址失败");
      setAddressImportLocations([]);
    } finally {
      setAddressImportLoading(false);
    }
  }

  function openAddressImportModal() {
    if (!privacyAllowsSensitiveEditor()) return;
    const accountId = accounts[0]?.account_id;
    addressImportForm.setFieldsValue({ account_id: accountId, location_ids: [] });
    setAddressImportLocations([]);
    setAddressImportModalOpen(true);
    if (accountId) {
      void loadAddressImportLocations(accountId);
    }
  }

  async function importPublishAddresses() {
    if (!selectedAddressGroupId) {
      return;
    }
    const values = await addressImportForm.validateFields();
    setAddressImportLoading(true);
    try {
      await Promise.all(
        values.location_ids.map((locationId) =>
          createPublishAddress(selectedAddressGroupId, values.account_id, locationId)
        )
      );
      setAddressImportModalOpen(false);
      await loadAddressLibrary(selectedAddressGroupId);
      message.success(`已加入 ${values.location_ids.length} 个地址`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "添加地址失败");
    } finally {
      setAddressImportLoading(false);
    }
  }

  async function togglePublishAddress(address: PublishAddress, enabled: boolean) {
    if (!selectedAddressGroupId) {
      return;
    }
    try {
      const updated = await updatePublishAddress(
        selectedAddressGroupId,
        address.address_id,
        enabled
      );
      setPublishAddresses((items) =>
        items.map((item) => item.address_id === updated.address_id ? updated : item)
      );
    } catch (error) {
      message.error(error instanceof Error ? error.message : "更新地址失败");
    }
  }

  async function removePublishAddress(address: PublishAddress) {
    if (!selectedAddressGroupId) {
      return;
    }
    await deletePublishAddress(selectedAddressGroupId, address.address_id);
    await loadAddressLibrary(selectedAddressGroupId);
  }

  function clearProductImagePreviews() {
    Object.values(productImagePreviewUrlsRef.current).forEach((url) => URL.revokeObjectURL(url));
    productImagePreviewUrlsRef.current = {};
    setProductImagePreviewUrls({});
  }

  function setProductImagePreview(imageRef: string, url: string) {
    const previous = productImagePreviewUrlsRef.current[imageRef];
    if (previous && previous !== url) {
      URL.revokeObjectURL(previous);
    }
    const next = { ...productImagePreviewUrlsRef.current, [imageRef]: url };
    productImagePreviewUrlsRef.current = next;
    setProductImagePreviewUrls(next);
  }

  async function ensureProductImagePreviews(accountId: string, imageRefs: string[]) {
    await Promise.all(
      imageRefs.map(async (imageRef) => {
        if (!imageRef.startsWith("asset:") || productImagePreviewUrlsRef.current[imageRef]) {
          return;
        }
        const assetId = imageRef.slice("asset:".length);
        try {
          const content = await getProductImageContent(accountId, assetId);
          setProductImagePreview(imageRef, URL.createObjectURL(content));
        } catch (error) {
          message.error(error instanceof Error ? error.message : "加载商品图片预览失败");
        }
      })
    );
  }

  async function loadProductData(accountId: string, silent = false) {
    if (!silent) {
      setProductLoading(true);
    }
    try {
      const [tasks, images] = await Promise.all([
        listProductPublishTasks(accountId, 100),
        listProductImages(accountId, 200)
      ]);
      setProductDrafts([]);
      setProductTasks(tasks);
      setProductImageAssets(images);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载商品发布数据失败");
    } finally {
      if (!silent) {
        setProductLoading(false);
      }
    }
  }

  async function loadProductWorkspace(account: Account) {
    if (productAccount?.account_id !== account.account_id) {
      clearProductImagePreviews();
    }
    productAccountIdRef.current = account.account_id;
    productLocationRequestRef.current += 1;
    setProductAccount(account);
    setProductLocations([]);
    setProductLocationResult(null);
    setProductLocationLoading(false);
    setProductImagePreviewOpen(false);
    setProductImageDropActive(false);
    productImageDragDepthRef.current = 0;
    setProductShippingOpen(false);
    setProductShippingError(null);
    setProductAddressGroups([]);
    setEditingProductDraft(null);
    productDraftForm.resetFields();
    const [, groups] = await Promise.all([
      loadProductData(account.account_id),
      listPublishAddressGroups(account.account_id),
      loadProductRegionCatalog()
    ]);
    setProductAddressGroups(groups);
  }

  async function loadProductLocationOptions(accountId: string, refresh = false) {
    const requestId = ++productLocationRequestRef.current;
    setProductLocationLoading(true);
    try {
      const result = await listProductLocations(accountId, refresh);
      if (productAccountIdRef.current !== accountId || productLocationRequestRef.current !== requestId) {
        return;
      }
      setProductLocationResult(result);
      setProductLocations((existing) => {
        const merged = [
          ...existing.filter((option) => option.source === "saved_snapshot"),
          ...result.items
        ];
        const seen = new Set<string>();
        return merged.filter((option) => {
          const key = productLocationKey(option);
          if (seen.has(key)) {
            return false;
          }
          seen.add(key);
          return true;
        });
      });
      if (result.warning) {
        message.warning(result.warning);
      }
    } catch (error) {
      if (productAccountIdRef.current === accountId && productLocationRequestRef.current === requestId) {
        message.warning(error instanceof Error ? error.message : "加载宝贝所在地失败");
      }
    } finally {
      if (productAccountIdRef.current === accountId && productLocationRequestRef.current === requestId) {
        setProductLocationLoading(false);
      }
    }
  }

  async function selectProductAccount(account: Account) {
    await loadProductWorkspace(account);
  }

  function startCreateProductDraft() {
    if (!privacyAllowsSensitiveEditor()) return;
    setEditingProductDraft(null);
    productDraftForm.setFieldsValue({
      title: "",
      description: "",
      price: "",
      original_price: "",
      stock: 1,
      category_id: "",
      category_hint: "",
      image_refs: [],
      images_text: "",
      delivery_choice: "free_shipping",
      post_price: "",
      can_self_pickup: false,
      location_mode: "account_default",
      location: null,
      region_path: undefined,
      location_key: null,
      location_group_id: null,
      status: "draft"
    });
    setProductShippingError(null);
  }

  function startEditProductDraft(draft: ProductDraft) {
    if (!privacyAllowsSensitiveEditor()) return;
    const assetRefs = draft.images.filter((value) => value.startsWith("asset:"));
    setEditingProductDraft(draft);
    const locationKey = draft.location ? productLocationKey(draft.location) : null;
    if (
      draft.location &&
      !productLocations.some((option) => productLocationKey(option) === locationKey)
    ) {
      setProductLocations((options) => [
        {
          ...draft.location!,
          location_id: `saved-${draft.draft_id}`,
          label: [draft.location!.prov, draft.location!.city, draft.location!.area, draft.location!.poi_name]
            .filter(Boolean)
            .join(" "),
          source: "saved_snapshot"
        },
        ...options
      ]);
    }
    productDraftForm.setFieldsValue({
      title: draft.title,
      description: draft.description,
      price: draft.price,
      original_price: draft.original_price || "",
      stock: draft.stock,
      category_id: draft.category_id || "",
      category_hint: draft.category_hint || "",
      image_refs: assetRefs,
      images_text: draft.images.filter((value) => !value.startsWith("asset:")).join("\n"),
      delivery_choice: draft.delivery_choice,
      post_price: draft.post_price || "",
      can_self_pickup: draft.can_self_pickup,
      location_mode: draft.location_mode,
      location: draft.location || null,
      region_path:
        draft.location_mode === "region" && draft.location
          ? productRegionPath(productRegionCatalog?.items || [], draft.location.division_id)
          : undefined,
      location_key: locationKey,
      location_group_id: draft.location_group_id || null,
      status: draft.status
    });
    if (draft.location_mode === "selected" && productAccount) {
      void loadProductLocationOptions(productAccount.account_id);
    } else if (draft.location_mode === "region") {
      void loadProductRegionCatalog();
    }
    void ensureProductImagePreviews(draft.account_id, assetRefs);
    setProductShippingError(null);
  }

  function selectProductDeliveryChoice(choice: ProductDraft["delivery_choice"]) {
    productDraftForm.setFieldValue("delivery_choice", choice);
    if (choice !== "fixed") {
      productDraftForm.setFieldValue("post_price", null);
      setProductShippingError(null);
    }
    if (choice === "pickup_only") {
      productDraftForm.setFieldValue("can_self_pickup", false);
    }
    if (choice !== "fixed") {
      setProductShippingOpen(false);
    }
  }

  function confirmFixedProductDelivery() {
    const amount = Number(String(productDraftForm.getFieldValue("post_price") || "").trim());
    if (!Number.isFinite(amount) || amount <= 0) {
      setProductShippingError("请输入大于 0 的固定运费");
      return;
    }
    productDraftForm.setFieldValue("delivery_choice", "fixed");
    setProductShippingError(null);
    setProductShippingOpen(false);
  }

  function resetProductLocationSelection() {
    productDraftForm.setFieldsValue({
      location_mode: "account_default",
      location: null,
      region_path: undefined,
      location_key: null,
      location_group_id: null
    });
  }

  function selectProductLocation(value?: string) {
    if (!value || value === "mode:account_default") {
      resetProductLocationSelection();
      return;
    }
    if (value.startsWith("group:")) {
      productDraftForm.setFieldsValue({
        location_mode: "group_random",
        location: null,
        region_path: undefined,
        location_key: null,
        location_group_id: value.slice("group:".length)
      });
      return;
    }
    if (value.startsWith("region:")) {
      const regionCode = value.slice("region:".length);
      productDraftForm.setFieldsValue({
        location_mode: "region",
        location: null,
        region_path: productRegionPath(productRegionCatalog?.items || [], regionCode),
        location_key: null,
        location_group_id: null
      });
      return;
    }
    if (value.startsWith("precise:")) {
      productDraftForm.setFieldsValue({
        location_mode: "selected",
        location: null,
        region_path: undefined,
        location_key: value.slice("precise:".length),
        location_group_id: null
      });
    }
  }

  function openProductImagePreview(imageRef: string) {
    if (!privacyAllowsSensitiveEditor()) return;
    const index = productImagePreviewRefs.indexOf(imageRef);
    if (index < 0) return;
    setProductImagePreviewIndex(index);
    setProductImagePreviewOpen(true);
  }

  async function uploadProductImages(files: FileList | File[] | null) {
    const fileItems = files ? Array.from(files) : [];
    if (!productAccount || !fileItems.length) {
      return;
    }
    if (productImageUploading) {
      message.warning("图片正在导入，请稍候");
      return;
    }
    const supportedImageTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
    const supportedImageSuffixes = [".jpg", ".jpeg", ".png", ".webp"];
    const archiveTypes = new Set(["application/zip", "application/x-zip-compressed"]);
    const isArchive = (file: File) =>
      archiveTypes.has(file.type) || file.name.toLowerCase().endsWith(".zip");
    const isSupportedImage = (file: File) =>
      supportedImageTypes.has(file.type) ||
      supportedImageSuffixes.some((suffix) => file.name.toLowerCase().endsWith(suffix));
    const supportedFiles = fileItems.filter((file) => {
      if (file.size <= 0) return false;
      if (isArchive(file)) return file.size <= 50 * 1024 * 1024;
      return isSupportedImage(file) && file.size <= 10 * 1024 * 1024;
    });
    const rejectedCount = fileItems.length - supportedFiles.length;
    if (rejectedCount) {
      message.warning(
        `${rejectedCount} 个文件不符合图片格式、图片 10 MB 或 ZIP 50 MB 限制`
      );
    }
    if (!supportedFiles.length) {
      return;
    }
    const externalCount = (productDraftForm.getFieldValue("images_text") || "")
      .split("\n")
      .filter((value: string) => value.trim()).length;
    const currentRefs = productDraftForm.getFieldValue("image_refs") || [];
    const remaining = 9 - externalCount - currentRefs.length;
    if (remaining <= 0) {
      message.warning("商品图片最多 9 张");
      return;
    }
    setProductImageUploading(true);
    const uploaded: ProductImageAsset[] = [];
    let slotsRemaining = remaining;
    let ignoredNonImageCount = 0;
    let rejectedArchiveImageCount = 0;
    let skippedLimitCount = 0;
    let unprocessedFileCount = 0;
    let importedArchive = false;
    try {
      for (let index = 0; index < supportedFiles.length; index += 1) {
        const file = supportedFiles[index];
        if (slotsRemaining <= 0) {
          unprocessedFileCount = supportedFiles.length - index;
          break;
        }
        if (isArchive(file)) {
          importedArchive = true;
          const result = await uploadProductImageArchive(
            productAccount.account_id,
            file,
            slotsRemaining,
            productUploadSessionId || undefined
          );
          uploaded.push(...result.assets);
          slotsRemaining -= result.assets.length;
          ignoredNonImageCount += result.ignored_non_image_count;
          rejectedArchiveImageCount += result.rejected_images.length;
          skippedLimitCount += result.skipped_limit_count;
          await ensureProductImagePreviews(
            productAccount.account_id,
            result.assets.map((asset) => asset.image_ref)
          );
        } else {
          const asset = await uploadProductImage(
            productAccount.account_id,
            file,
            productUploadSessionId || undefined
          );
          uploaded.push(asset);
          slotsRemaining -= 1;
          setProductImagePreview(asset.image_ref, URL.createObjectURL(file));
        }
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "商品图片导入失败");
    } finally {
      if (uploaded.length) {
        setProductImageAssets((items) => [
          ...uploaded,
          ...items.filter((item) => !uploaded.some((asset) => asset.asset_id === item.asset_id))
        ]);
        productDraftForm.setFieldValue("image_refs", [
          ...currentRefs,
          ...uploaded.map((asset) => asset.image_ref)
        ]);
        message.success(
          importedArchive
            ? `已导入 ${uploaded.length} 张商品图片`
            : `已上传 ${uploaded.length} 张商品图片`
        );
      }
      if (ignoredNonImageCount) {
        message.info(`已忽略压缩包内 ${ignoredNonImageCount} 个非图片文件`);
      }
      if (rejectedArchiveImageCount) {
        message.warning(`压缩包内 ${rejectedArchiveImageCount} 张无效图片已跳过`);
      }
      if (skippedLimitCount || unprocessedFileCount) {
        message.warning("达到 9 张上限，其余图片或文件未处理");
      }
      setProductImageUploading(false);
      if (productImageInputRef.current) {
        productImageInputRef.current.value = "";
      }
    }
  }

  function moveProductImage(imageRef: string, offset: -1 | 1) {
    const index = selectedProductImageRefs.indexOf(imageRef);
    const target = index + offset;
    if (index < 0 || target < 0 || target >= selectedProductImageRefs.length) {
      return;
    }
    productDraftForm.setFieldValue("image_refs", arrayMove(selectedProductImageRefs, index, target));
  }

  function handleProductImageDragEnd({ active, over }: DragEndEvent) {
    if (!over || active.id === over.id) {
      return;
    }
    const currentIndex = selectedProductImageRefs.indexOf(String(active.id));
    const targetIndex = selectedProductImageRefs.indexOf(String(over.id));
    if (currentIndex < 0 || targetIndex < 0) {
      return;
    }
    productDraftForm.setFieldValue(
      "image_refs",
      arrayMove(selectedProductImageRefs, currentIndex, targetIndex)
    );
  }

  async function deleteUnusedProductImage(imageRef: string, quiet = false) {
    if (!productAccount || !imageRef.startsWith("asset:")) {
      return;
    }
    const assetId = imageRef.slice("asset:".length);
    try {
      await deleteProductImage(productAccount.account_id, assetId);
      setProductImageAssets((items) => items.filter((item) => item.asset_id !== assetId));
      const previewUrl = productImagePreviewUrlsRef.current[imageRef];
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
        const next = { ...productImagePreviewUrlsRef.current };
        delete next[imageRef];
        productImagePreviewUrlsRef.current = next;
        setProductImagePreviewUrls(next);
      }
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 409) {
        return;
      }
      if (!quiet) {
        message.warning(error instanceof Error ? error.message : "清理商品图片失败");
      }
    }
  }

  function removeProductImageFromDraft(imageRef: string) {
    if (productImagePreviewRefs.includes(imageRef)) {
      setProductImagePreviewOpen(false);
    }
    productDraftForm.setFieldValue(
      "image_refs",
      selectedProductImageRefs.filter((value) => value !== imageRef)
    );
    void deleteUnusedProductImage(imageRef);
  }

  async function submitProductDraft() {
    if (!productAccount || !productUploadSessionId || productPublishSubmitting) {
      return;
    }
    const values = await productDraftForm.validateFields();
    const selectedRegionCode = values.region_path?.[values.region_path.length - 1];
    const selectedRegion =
      values.location_mode === "region" && selectedRegionCode
        ? productRegionsByCode.get(selectedRegionCode) ?? null
        : null;
    const selectedLocation =
      values.location_mode === "selected"
        ? productLocations.find((option) => productLocationKey(option) === values.location_key) ?? null
        : null;
    if (values.location_mode === "selected" && !selectedLocation) {
      message.error("请选择一个有效的精准地址");
      return;
    }
    if (values.location_mode === "region" && (!selectedRegion || !selectedRegion.selectable)) {
      message.error("请选择一个具体的可发布区域");
      return;
    }
    const draftValues: ProductDraftFormValues = {
      ...values,
      location: selectedRegion
        ? productRegionLocation(selectedRegion)
        : selectedLocation
        ? {
            prov: selectedLocation.prov,
            city: selectedLocation.city,
            area: selectedLocation.area,
            division_id: selectedLocation.division_id,
            longitude: selectedLocation.longitude,
            latitude: selectedLocation.latitude,
            poi_id: selectedLocation.poi_id,
            poi_name: selectedLocation.poi_name
          }
        : null
    };
    const totalImageCount = values.image_refs?.length || 0;
    if (totalImageCount < 1 || totalImageCount > 9) {
      message.error("商品图片数量必须为 1 到 9 张");
      return;
    }
    const requestKey = `${productAccount.account_id}:${productUploadSessionId}`;
    const idempotencyKey = productPublishRequestIdsRef.current[requestKey] || createClientRequestId("publish");
    productPublishRequestIdsRef.current[requestKey] = idempotencyKey;
    setProductPublishSubmitting(true);
    try {
      const result = await createAndEnqueueProductPublishJob(
        productAccount.account_id,
        { ...draftValues, images_text: "", status: "ready" },
        productUploadSessionId,
        idempotencyKey
      );
      delete productPublishRequestIdsRef.current[requestKey];
      setProductTasks((items) => [
        result.publish_task,
        ...items.filter((item) => item.task_id !== result.publish_task.task_id)
      ]);
      try {
        await cleanupProductUploadSession(productAccount.account_id, productUploadSessionId);
      } catch {
        // Submitted assets are retained by the task; the sweeper handles unused leftovers.
      }
      setProductPublishDrawerOpen(false);
      setProductImagePreviewOpen(false);
      setProductShippingOpen(false);
      setProductUploadSessionId(null);
      productDraftForm.resetFields();
      clearProductImagePreviews();
      message.success("商品发布任务已提交");
      await loadProductManagementWorkspace(productAccount.account_id, true);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "创建商品发布任务失败");
    } finally {
      setProductPublishSubmitting(false);
    }
  }

  async function openProductPublishDrawer() {
    if (!privacyAllowsSensitiveEditor()) return;
    if (!productManagerAccountId) return;
    const account = accounts.find((item) => item.account_id === productManagerAccountId);
    if (!account) {
      message.error("未找到当前平台账户");
      return;
    }
    const uploadSessionId = createClientRequestId("product-upload");
    setProductUploadSessionId(uploadSessionId);
    setProductPublishDrawerOpen(true);
    await loadProductWorkspace(account);
    startCreateProductDraft();
  }

  async function closeProductPublishDrawer() {
    if (productPublishSubmitting || productImagePreviewOpen) return;
    const accountId = productAccount?.account_id;
    const uploadSessionId = productUploadSessionId;
    setProductPublishDrawerOpen(false);
    setProductImagePreviewOpen(false);
    setProductImageDropActive(false);
    productImageDragDepthRef.current = 0;
    setProductShippingOpen(false);
    setProductShippingError(null);
    setProductUploadSessionId(null);
    productDraftForm.resetFields();
    clearProductImagePreviews();
    if (accountId && uploadSessionId) {
      try {
        await cleanupProductUploadSession(accountId, uploadSessionId);
      } catch {
        // The server-side expiry sweeper removes abandoned staged assets.
      }
    }
  }

  async function retryFailedProductPublish(task: ProductPublishTask) {
    if (!productManagerAccountId || productRetryingTaskId) return;
    setProductRetryingTaskId(task.task_id);
    try {
      const result = await retryProductPublishTask(
        productManagerAccountId,
        task.task_id,
        createClientRequestId("publish-retry")
      );
      setProductTasks((items) => [
        result.publish_task,
        ...items.filter((item) => item.task_id !== result.publish_task.task_id)
      ]);
      message.success("重新发布任务已提交");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "重新发布失败");
    } finally {
      setProductRetryingTaskId(null);
    }
  }

  async function removeProductDraft(draft: ProductDraft) {
    if (!productAccount) {
      return;
    }
    Modal.confirm({
      title: "删除商品草稿",
      content: `确认删除「${privateName(draft.title)}」？`,
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      async onOk() {
        await deleteProductDraft(productAccount.account_id, draft.draft_id);
        await Promise.all(
          draft.images
            .filter((imageRef) => imageRef.startsWith("asset:"))
            .map((imageRef) => deleteUnusedProductImage(imageRef, true))
        );
        message.success("商品草稿已删除");
        await loadProductData(productAccount.account_id);
      }
    });
  }

  async function createPublishTask(draft: ProductDraft, mode: ProductPublishTask["mode"] = "platform_api") {
    if (!productAccount) {
      return;
    }
    if (productPublishingDraftId) {
      return;
    }
    const requestKey = `${productAccount.account_id}:${draft.draft_id}`;
    const idempotencyKey =
      productPublishRequestIdsRef.current[requestKey] || createClientRequestId("publish");
    productPublishRequestIdsRef.current[requestKey] = idempotencyKey;
    setProductPublishingDraftId(draft.draft_id);
    try {
      await createAndEnqueueProductPublishTask(
        productAccount.account_id,
        draft.draft_id,
        mode,
        idempotencyKey
      );
      delete productPublishRequestIdsRef.current[requestKey];
      message.success("商品发布任务已入队");
      await loadProductData(productAccount.account_id, true);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "创建发布任务失败");
    } finally {
      setProductPublishingDraftId(null);
    }
  }

  async function enqueuePublishTask(task: ProductPublishTask) {
    if (!productAccount) {
      return;
    }
    setProductLoading(true);
    try {
      await enqueueProductPublishTask(productAccount.account_id, task.task_id);
      message.success("商品发布任务已入队");
      await loadProductData(productAccount.account_id);
      await loadBackgroundTaskData();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "商品发布任务入队失败");
    } finally {
      setProductLoading(false);
    }
  }

  async function loadProductManagementWorkspace(
    preferredAccountId?: string | null,
    silent = false
  ) {
    const requestId = ++productManagerRequestRef.current;
    if (!silent) setProductManagerLoading(true);
    try {
      const summaries = await listProductManagementAccounts();
      const accountId =
        (preferredAccountId && summaries.some((item) => item.account_id === preferredAccountId)
          ? preferredAccountId
          : productManagerAccountId &&
              summaries.some((item) => item.account_id === productManagerAccountId)
            ? productManagerAccountId
            : summaries[0]?.account_id) || null;
      if (requestId !== productManagerRequestRef.current) return;
      setProductManagerAccounts(summaries);
      setProductManagerAccountId(accountId);
      productManagerAccountIdRef.current = accountId;
      if (!accountId) {
        setManagedProducts([]);
        setProductOperationRuns([]);
        setProductTasks([]);
        return;
      }
      const [items, runs, publishTasks] = await Promise.all([
        listManagedProducts(accountId, { limit: 500 }),
        listProductOperations(accountId, 30),
        listProductPublishTasks(accountId, 100)
      ]);
      if (requestId !== productManagerRequestRef.current) return;
      setManagedProducts(items);
      setProductOperationRuns(runs);
      setProductTasks(publishTasks);
      setProductManagerSelection((current) =>
        current.filter((itemId) => items.some((item) => item.item_id === itemId))
      );
    } catch (error) {
      if (!silent) {
        message.error(error instanceof Error ? error.message : "加载商品管理数据失败");
      }
    } finally {
      if (!silent && requestId === productManagerRequestRef.current) {
        setProductManagerLoading(false);
      }
    }
  }

  async function selectProductManagerAccount(accountId: string) {
    setProductManagerSelection([]);
    setProductManagerAccountId(accountId);
    productManagerAccountIdRef.current = accountId;
    await loadProductManagementWorkspace(accountId);
  }

  async function runProductManagerSync(accountId: string) {
    const actionKey = `sync:${accountId}`;
    if (productManagerAction) return;
    setProductManagerAction(actionKey);
    try {
      const result = await syncManagedProducts(accountId, true);
      message.success(result.run.status === "pending" ? "商品全量同步任务已入队" : "商品同步任务正在执行");
      if (accountId === productManagerAccountId) {
        setProductOperationRuns((items) => [
          result.run,
          ...items.filter((item) => item.run_id !== result.run.run_id)
        ]);
      }
      await loadProductManagementWorkspace(accountId, true);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "商品同步任务入队失败");
    } finally {
      setProductManagerAction(null);
    }
  }

  async function runManagedProductAction(
    operation: "polish" | "offline" | "delete",
    itemIds: string[]
  ) {
    if (!productManagerAccountId || !itemIds.length || productManagerAction) return;
    setProductManagerAction(operation);
    try {
      const result =
        operation === "polish"
          ? await polishManagedProducts(productManagerAccountId, itemIds)
          : operation === "offline"
            ? await offlineManagedProducts(productManagerAccountId, itemIds)
            : await deleteManagedProducts(productManagerAccountId, itemIds);
      const label = operation === "polish" ? "擦亮" : operation === "offline" ? "下架" : "永久删除";
      message.success(`${label}任务已入队`);
      setProductManagerSelection([]);
      setProductOperationRuns((items) => [
        result.run,
        ...items.filter((item) => item.run_id !== result.run.run_id)
      ]);
      await loadProductManagementWorkspace(productManagerAccountId, true);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "商品操作任务入队失败");
    } finally {
      setProductManagerAction(null);
    }
  }

  function confirmDeleteManagedProducts(itemIds: string[]) {
    const selectedItems = managedProducts.filter((item) => itemIds.includes(item.item_id));
    Modal.confirm({
      title: `永久删除 ${itemIds.length} 个商品？`,
      content: (
        <Space direction="vertical" size={4}>
          <Text type="danger">此操作会删除闲鱼平台商品，无法在本系统恢复。</Text>
          <Text type="secondary" ellipsis>
            {selectedItems.map((item) => privateName(item.title) || privateId(item.item_id)).join("、")}
          </Text>
        </Space>
      ),
      okText: "永久删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: () => runManagedProductAction("delete", itemIds)
    });
  }

  async function runDeleteLocalManagedProduct(item: ManagedProductItem) {
    if (!productManagerAccountId || productManagerAction) return;
    const actionKey = `local-delete:${item.item_id}`;
    setProductManagerAction(actionKey);
    try {
      await deleteLocalManagedProduct(productManagerAccountId, item.item_id);
      setManagedProducts((items) => items.filter((entry) => entry.item_id !== item.item_id));
      setProductTasks((tasks) => tasks.filter((task) => task.item_id !== item.item_id));
      setProductManagerSelection((items) => items.filter((itemId) => itemId !== item.item_id));
      message.success("本地商品数据已删除，平台操作记录仍保留");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "删除本地商品数据失败");
    } finally {
      setProductManagerAction(null);
    }
  }

  function confirmDeleteLocalManagedProduct(item: ManagedProductItem) {
    Modal.confirm({
      title: "删除本地商品数据？",
      content: (
        <Space direction="vertical" size={4}>
          <Text>仅删除本系统商品列表数据，不会再次操作闲鱼平台。</Text>
          <Text type="secondary">平台操作、订单、会话和审计记录仍会保留。</Text>
          <Text type="secondary" ellipsis>{privateName(item.title) || privateId(item.item_id)}</Text>
        </Space>
      ),
      okText: "删除本地数据",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: () => runDeleteLocalManagedProduct(item)
    });
  }

  function openProductManagerSettings() {
    if (!selectedProductManagerAccount) return;
    const setting = selectedProductManagerAccount.setting;
    productSyncSettingForm.setFieldsValue({
      sync_enabled: setting.sync_enabled,
      sync_interval_minutes: setting.sync_interval_minutes,
      sync_jitter_minutes: setting.sync_jitter_minutes,
      full_sync_interval_hours: setting.full_sync_interval_hours,
      publish_verify_delay_seconds: setting.publish_verify_delay_seconds,
      auto_polish_enabled: setting.auto_polish_enabled,
      polish_hour: setting.polish_hour,
      polish_jitter_minutes: setting.polish_jitter_minutes
    });
    setProductManagerSettingsOpen(true);
  }

  async function saveProductManagerSettings() {
    if (!productManagerAccountId) return;
    const values = await productSyncSettingForm.validateFields();
    setProductManagerAction("settings");
    try {
      await updateProductSyncSetting(productManagerAccountId, values);
      setProductManagerSettingsOpen(false);
      message.success("商品同步与擦亮设置已保存");
      await loadProductManagementWorkspace(productManagerAccountId, true);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存商品管理设置失败");
    } finally {
      setProductManagerAction(null);
    }
  }

  async function loadBackgroundTaskData(quiet = false) {
    if (!quiet) setBackgroundTasksLoading(true);
    try {
      setBackgroundTasks(await listBackgroundTasks(200));
    } catch (error) {
      if (!quiet) {
        message.error(error instanceof Error ? error.message : "加载后台任务失败");
      }
    } finally {
      if (!quiet) setBackgroundTasksLoading(false);
    }
  }

  async function loadAuditLogs() {
    setAuditLoading(true);
    try {
      setAuditLogs(await listAuditLogs(200));
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载审计日志失败");
    } finally {
      setAuditLoading(false);
    }
  }

  function openCreateUserDrawer() {
    if (!privacyAllowsSensitiveEditor()) return;
    setEditingUser(null);
    userForm.setFieldsValue({
      username: "",
      password: "",
      role: "operator",
      enabled: true
    });
    setUserDrawerOpen(true);
  }

  function openEditUserDrawer(user: AdminUser) {
    if (!privacyAllowsSensitiveEditor()) return;
    setEditingUser(user);
    userForm.setFieldsValue({
      username: user.username,
      password: "",
      role: user.role,
      enabled: user.enabled
    });
    setUserDrawerOpen(true);
  }

  function setUserMutationPending(mutationKey: string, pending: boolean) {
    const next = new Set(pendingUserMutationKeysRef.current);
    if (pending) {
      next.add(mutationKey);
    } else {
      next.delete(mutationKey);
    }
    pendingUserMutationKeysRef.current = next;
    setPendingUserMutationKeys(next);
  }

  function mergeSavedUser(savedUser: AdminUser) {
    setUsers((items) => {
      const existingIndex = items.findIndex((item) => item.user_id === savedUser.user_id);
      if (existingIndex >= 0) {
        return items.map((item) => item.user_id === savedUser.user_id ? savedUser : item);
      }
      return [...items, savedUser].sort(
        (left, right) => parseTimestamp(left.created_at) - parseTimestamp(right.created_at)
      );
    });
  }

  function restoreUserSubmission(snapshot: UserSubmissionSnapshot, notificationKey: string) {
    notification.destroy(notificationKey);
    if (!privacyAllowsSensitiveEditor()) return;
    setEditingUser(snapshot.targetUser);
    userForm.setFieldsValue(snapshot.values);
    setUserDrawerOpen(true);
  }

  async function persistUserSubmission(snapshot: UserSubmissionSnapshot) {
    try {
      const savedUser = snapshot.targetUser
        ? await updateSystemUser(snapshot.targetUser.user_id, {
            role: snapshot.values.role,
            enabled: snapshot.values.enabled,
            ...(snapshot.values.password ? { password: snapshot.values.password } : {})
          })
        : await createSystemUser(snapshot.values);

      mergeSavedUser(savedUser);
      const currentSessionStillActive = getStoredAccessToken() === snapshot.accessToken;
      if (snapshot.targetUser?.user_id === currentUser?.user_id && currentSessionStillActive) {
        if (savedUser.enabled) {
          setCurrentUser(savedUser);
        } else {
          clearAuthenticatedSession();
          message.warning("当前用户已停用，已退出登录");
          return;
        }
      }
      message.success(snapshot.targetUser ? "用户已更新" : "用户已创建");
    } catch (error) {
      const notificationKey = `user-save-error:${snapshot.mutationKey}`;
      notification.error({
        key: notificationKey,
        message: snapshot.targetUser ? "更新用户失败" : "新增用户失败",
        description: error instanceof Error ? error.message : "保存用户失败",
        duration: 0,
        actions: (
          <Button
            size="small"
            onClick={() => restoreUserSubmission(snapshot, notificationKey)}
          >
            重新编辑
          </Button>
        )
      });
    } finally {
      setUserMutationPending(snapshot.mutationKey, false);
    }
  }

  async function submitUserForm() {
    let values: UserFormValues;
    try {
      values = await userForm.validateFields();
    } catch {
      return;
    }
    const password = values.password?.trim() ?? "";
    if (!editingUser && !password) {
      userForm.setFields([{ name: "password", errors: ["请输入密码"] }]);
      return;
    }

    const targetUser = editingUser;
    const username = values.username.trim();
    const mutationKey = targetUser
      ? `user:${targetUser.user_id}`
      : `username:${username.toLocaleLowerCase()}`;
    if (pendingUserMutationKeysRef.current.has(mutationKey)) {
      message.info("该用户正在后台保存，请勿重复提交");
      return;
    }

    const snapshot: UserSubmissionSnapshot = {
      targetUser,
      values: {
        username,
        password,
        role: values.role,
        enabled: values.enabled
      },
      mutationKey,
      accessToken: getStoredAccessToken()
    };
    setUserMutationPending(mutationKey, true);
    setUserDrawerOpen(false);
    setEditingUser(null);
    void persistUserSubmission(snapshot);
  }

  async function runDelete(account: Account) {
    Modal.confirm({
      title: "删除账户",
      content: `确认删除「${accountDisplayName(account)}」？运行中的连接会先停止。`,
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      async onOk() {
        const task = await deleteAccount(account.account_id);
        setDrawerOpen(false);
        setEditing(null);
        setAccounts((items) =>
          items.map((item) =>
            item.account_id === account.account_id
              ? {
                  ...item,
                  runtime: {
                    ...item.runtime,
                    state: "deleting",
                    recovery_action: "none",
                    message: `删除任务 ${task.task_id.slice(0, 8)} 已提交`
                  }
                }
              : item
          )
        );
        message.success("账户删除任务已提交");
      }
    });
  }

  async function reorderAccountRows(event: DragEndEvent) {
    const { active, over } = event;
    if (!canMutate || !over || active.id === over.id || accountReordering) return;
    const currentIndex = accounts.findIndex((account) => account.account_id === active.id);
    const targetIndex = accounts.findIndex((account) => account.account_id === over.id);
    if (currentIndex < 0 || targetIndex < 0) return;
    const previous = accounts;
    const next = arrayMove(previous, currentIndex, targetIndex).map((account, index) => ({
      ...account,
      sort_order: (index + 1) * 100
    }));
    setAccounts(next);
    accountsRef.current = next;
    setAccountReordering(true);
    try {
      const reordered = await reorderAccounts(next.map((account) => account.account_id));
      setAccounts(reordered);
      accountsRef.current = reordered;
      message.success("账户顺序已更新");
    } catch (error) {
      setAccounts(previous);
      accountsRef.current = previous;
      message.error(error instanceof Error ? error.message : "更新账户顺序失败");
    } finally {
      setAccountReordering(false);
    }
  }

  const accountTableHasMeasured = accountTableWidth > 0;
  const runtimeHealthByAccount = useMemo(
    () => new Map(runtimeHealth.map((item) => [item.account_id, item])),
    [runtimeHealth]
  );
  const showAccountProxy =
    !compactLayout && (!accountTableHasMeasured || accountTableWidth >= 720);
  const showAccountToggles = true;
  const showAccountActivity =
    !compactLayout && (!accountTableHasMeasured || accountTableWidth >= 1080);
  const showAccountDetails =
    !compactLayout && (!accountTableHasMeasured || accountTableWidth >= 1300);
  const accountColumnWidth = compactLayout
    ? 180
    : accountTableWidth >= 1300
      ? ACCOUNT_TABLE_COLUMN_WIDTHS.account
      : 200;
  const accountActionColumnWidth = canMutate ? ACCOUNT_TABLE_COLUMN_WIDTHS.actions : 60;
  const accountTableMinWidth =
    (canMutate ? ACCOUNT_TABLE_COLUMN_WIDTHS.order : 0) +
    accountColumnWidth +
    accountActionColumnWidth +
    (showAccountDetails ? ACCOUNT_TABLE_COLUMN_WIDTHS.cookie : 0) +
    (showAccountProxy ? ACCOUNT_TABLE_COLUMN_WIDTHS.proxy : 0) +
    (showAccountToggles ? ACCOUNT_TABLE_COLUMN_WIDTHS.toggles : 0) +
    (showAccountActivity
      ? ACCOUNT_TABLE_COLUMN_WIDTHS.recentOnline +
        ACCOUNT_TABLE_COLUMN_WIDTHS.messageCount +
        ACCOUNT_TABLE_COLUMN_WIDTHS.remark
      : 0);

  const columns = useMemo<ColumnsType<Account>>(
    () => [
      {
        title: "顺序",
        width: ACCOUNT_TABLE_COLUMN_WIDTHS.order,
        align: "center",
        hidden: !canMutate,
        render: (_, _account, index) => (
          <Space size={2}>
            <AccountDragHandle disabled={accountReordering} />
            <Text type="secondary">{index + 1}</Text>
          </Space>
        )
      },
      {
        title: "账户",
        dataIndex: "display_name",
        width: showAccountProxy ? accountColumnWidth : undefined,
        minWidth: ACCOUNT_TABLE_COLUMN_WIDTHS.account,
        render: (_, account) => {
          const browserSession = accountBrowserStatuses[account.account_id];
          const diagnosticWarnings = accountDiagnosticWarnings(
            runtimeHealthByAccount.get(account.account_id)
          );
          const avatarFallback = (
            account.platform_display_name ||
            account.platform ||
            "闲"
          ).trim().slice(0, 1);
          return (
            <div className="account-primary-cell">
              <Avatar
                className="account-list-avatar"
                size={compactLayout ? 40 : 48}
                src={!privacyMaskEnabled ? account.platform_avatar_url || undefined : undefined}
              >
                {privacyMaskEnabled ? <LockOutlined /> : avatarFallback}
              </Avatar>
              <Space className="account-primary-content" direction="vertical" size={0}>
                <div className="account-name-heading">
                  {isActiveAccountBrowser(browserSession) ? (
                    <Tag className="account-vnc-tag" color={browserSession.status === "ready" ? "green" : "processing"}>
                      VNC
                    </Tag>
                  ) : null}
                  <Text strong ellipsis={{ tooltip: platformAccountName(account) }}>
                    {platformAccountName(account)}
                  </Text>
                  {diagnosticWarnings.length ? (
                    <Tooltip title={diagnosticWarnings.join("；")}>
                      <WarningOutlined className="account-diagnostic-warning" />
                    </Tooltip>
                  ) : null}
                </div>
                <div className="account-meta-row">
                  <Tooltip title={`内部账户 ID：${privateId(account.account_id)}`}>
                    <Text className="account-id" type="secondary" ellipsis>
                      {account.platform_user_id
                        ? `平台 ID ${privateId(account.platform_user_id)}`
                        : privateId(account.account_id)}
                    </Text>
                  </Tooltip>
                  {!showAccountActivity && account.remark ? (
                    <Tooltip title={privateName(account.remark)}>
                      <Text className="account-inline-remark" type="secondary" ellipsis>
                        · {privateName(account.remark)}
                      </Text>
                    </Tooltip>
                  ) : null}
                </div>
                <div className="account-login-status">
                  <AccountHealthTags
                    account={account}
                    privacyMaskEnabled={privacyMaskEnabled}
                    direction="horizontal"
                  />
                </div>
              </Space>
            </div>
          );
        }
      },
      {
        title: "环境",
        width: ACCOUNT_TABLE_COLUMN_WIDTHS.proxy,
        className: "account-proxy-column",
        hidden: !showAccountProxy,
        render: (_, account) => {
          const browserSession = accountBrowserStatuses[account.account_id];
          const candidateSnapshot = browserSession?.fingerprint_snapshot
            ?? account.browser_identity.fingerprint_snapshot;
          const snapshotMatchesIdentity = Boolean(
            candidateSnapshot
            && candidateSnapshot.config_revision === account.browser_identity.config_revision
            && candidateSnapshot.browser_engine === account.browser_identity.browser_engine
            && candidateSnapshot.browser_version === (account.browser_identity.browser_version || candidateSnapshot.browser_version)
          );
          const currentSnapshot = snapshotMatchesIdentity ? candidateSnapshot : null;
          const detectionStatus = browserSession?.fingerprint_detection_status;
          const fingerprintMeta = candidateSnapshot
            && !snapshotMatchesIdentity
            && detectionStatus !== "collecting"
            && detectionStatus !== "failed"
              ? { label: "待重新检测", color: "default" }
              : browserFingerprintDetectionMeta(currentSnapshot, detectionStatus);
          const securityMeta = browserFingerprintSecurityMeta(currentSnapshot);
          const browserLabel = privateBrowserEngineLabel(
            account.browser_identity.browser_engine,
            "系统 Chrome"
          );
          const browserDetectionLine = (
            <div className="account-environment-status">
              <Tag color={account.browser_identity.browser_engine === "fingerprint_chromium" ? "purple" : "blue"}>
                {browserLabel}
              </Tag>
              <Tag color={fingerprintMeta.color}>指纹{fingerprintMeta.label}</Tag>
              {currentSnapshot && detectionStatus !== "collecting" && detectionStatus !== "failed" ? (
                <Tag color={securityMeta.color}>{securityMeta.label}</Tag>
              ) : null}
            </div>
          );
          if (account.network_mode === "direct") {
            return (
              <Space direction="vertical" size={1} style={{ width: "100%" }}>
                <div className="account-proxy-heading">
                  <Tag>本地直连</Tag>
                  <Text className="account-proxy-name" strong>不经过账户代理</Text>
                </div>
                <Text type="secondary">IPv4 地址：本地网络出口</Text>
                {browserDetectionLine}
              </Space>
            );
          }
          const proxy = proxies.find((item) => item.proxy_id === account.proxy_id);
          const endpoint = `${account.proxy.scheme}://${privateId(account.proxy.host || "-")}:${account.proxy.port || "-"}`;
          const proxyName = privateName(proxy?.name || account.proxy_name || "已绑定代理");
          const ipv4Address = proxy?.exit_ipv4 || null;
          const ipv4Location = ipv4Address
            ? privacyLocation(
                privacyMaskEnabled,
                proxy?.exit_country,
                proxy?.exit_region,
                proxy?.exit_city,
                proxy?.exit_isp
              ) || (privacyMaskEnabled ? "位置未解析" : proxyIPv4Location(proxy))
            : null;
          const ipv4Summary = `IPv4 地址：${ipv4Address ? privateIPv4(ipv4Address) : "未检测"}${
            ipv4Location ? ` · ${ipv4Location}` : ""
          }`;

          return (
            <Space direction="vertical" size={1} style={{ width: "100%" }}>
              <div className="account-proxy-heading">
                {proxy?.last_test_ok == null ? (
                  <Tag>未检测</Tag>
                ) : proxy.last_test_ok ? (
                  <Tag color="green">可用</Tag>
                ) : (
                  <Tag color="red">检测失败</Tag>
                )}
                <Tooltip title={<Space direction="vertical" size={0}><span>{proxyName}</span><span>{endpoint}</span><span>{ipv4Summary}</span></Space>}>
                  <Text className="account-proxy-name" strong ellipsis>
                    {proxyName}
                  </Text>
                </Tooltip>
              </div>
              <Text type="secondary" ellipsis={{ tooltip: ipv4Summary }}>
                {ipv4Summary}
              </Text>
              {browserDetectionLine}
            </Space>
          );
        }
      },
      {
        title: "Cookie",
        dataIndex: "has_cookie",
        width: ACCOUNT_TABLE_COLUMN_WIDTHS.cookie,
        hidden: !showAccountDetails,
        render: (_hasCookie: boolean, account) => (
          <Space className="account-compact-cell" direction="vertical" size={0}>
            {account.cookie_health.verification_source ? (
              <Text type="secondary" ellipsis={{ tooltip: cookieSourceLabel(account.cookie_health.verification_source) }}>
                {cookieSourceLabel(account.cookie_health.verification_source)}
              </Text>
            ) : null}
            {account.cookie_health.checked_at ? (
              <Tooltip title={`最近验证：${formatTime(account.cookie_health.checked_at)}`}>
                <Text className="account-compact-time" type="secondary">
                  验 {formatCompactBeijingTime(account.cookie_health.checked_at)}
                </Text>
              </Tooltip>
            ) : null}
            {account.cookie_health.next_renewal_at ? (
              <Tooltip title={`下次续期：${formatTime(account.cookie_health.next_renewal_at)}`}>
                <Text className="account-compact-time" type="secondary">
                  续 {formatCompactBeijingTime(account.cookie_health.next_renewal_at)}
                </Text>
              </Tooltip>
            ) : null}
            {!account.cookie_health.verification_source && !account.cookie_health.checked_at ? (
              <Text type="secondary">-</Text>
            ) : null}
          </Space>
        )
      },
      {
        title: "开关",
        width: ACCOUNT_TABLE_COLUMN_WIDTHS.toggles,
        align: "center",
        hidden: !showAccountToggles,
        render: (_, account) => {
          const conversationKey = `${account.account_id}:conversation_visible`;
          const chatKey = `${account.account_id}:chat_enabled`;
          const orderKey = `${account.account_id}:order_management_visible`;
          const productKey = `${account.account_id}:product_management_visible`;
          return (
            <div className="account-feature-switches">
              <Tooltip title="仅控制会话消息页面展示，不影响 IM 连接、Cookie 或自动回复">
                <Switch
                  size="small"
                  disabled={!canMutate || accountWorkspaceVisibilityUpdatingKeys.has(conversationKey)}
                  loading={accountWorkspaceVisibilityUpdatingKeys.has(conversationKey)}
                  checked={account.conversation_visible}
                  checkedChildren="会话"
                  unCheckedChildren="会话"
                  onChange={(checked) =>
                    void runToggleAccountWorkspaceVisibility(account, "conversation_visible", checked, "会话消息")
                  }
                />
              </Tooltip>
              <Tooltip title="控制该账户是否接入平台级 Chatwoot；关闭后停止双向消息与状态同步，历史映射保留">
                <Switch
                  className="account-chat-switch"
                  size="small"
                  disabled={!canMutate || accountWorkspaceVisibilityUpdatingKeys.has(chatKey)}
                  loading={accountWorkspaceVisibilityUpdatingKeys.has(chatKey)}
                  checked={account.chat_enabled}
                  checkedChildren="Chat"
                  unCheckedChildren="Chat"
                  onChange={(checked) =>
                    void runToggleAccountWorkspaceVisibility(account, "chat_enabled", checked, "Chat")
                  }
                />
              </Tooltip>
              <Switch
                size="small"
                disabled={!canMutate || accountAutoReplyUpdatingId === account.account_id}
                loading={accountAutoReplyUpdatingId === account.account_id}
                checked={account.auto_reply_enabled}
                checkedChildren="回复"
                unCheckedChildren="回复"
                onChange={(checked) => void runToggleAccountAutoReply(account, checked)}
              />
              <Tooltip title="仅控制商品管理页面展示，不影响账户连接或同步设置">
                <Switch
                  size="small"
                  disabled={!canMutate || accountWorkspaceVisibilityUpdatingKeys.has(productKey)}
                  loading={accountWorkspaceVisibilityUpdatingKeys.has(productKey)}
                  checked={account.product_management_visible}
                  checkedChildren="商品"
                  unCheckedChildren="商品"
                  onChange={(checked) =>
                    void runToggleAccountWorkspaceVisibility(account, "product_management_visible", checked, "商品管理")
                  }
                />
              </Tooltip>
              <Tooltip title="仅控制订单管理页面展示，不影响账户连接或同步设置">
                <Switch
                  size="small"
                  disabled={!canMutate || accountWorkspaceVisibilityUpdatingKeys.has(orderKey)}
                  loading={accountWorkspaceVisibilityUpdatingKeys.has(orderKey)}
                  checked={account.order_management_visible}
                  checkedChildren="订单"
                  unCheckedChildren="订单"
                  onChange={(checked) =>
                    void runToggleAccountWorkspaceVisibility(account, "order_management_visible", checked, "订单管理")
                  }
                />
              </Tooltip>
            </div>
          );
        }
      },
      {
        title: "最近在线",
        dataIndex: ["runtime", "last_online_at"],
        width: ACCOUNT_TABLE_COLUMN_WIDTHS.recentOnline,
        hidden: !showAccountDetails,
        render: (value?: string | null) => {
          const fullTime = formatTime(value);
          return (
            <Tooltip title={fullTime}>
              <Text className="account-compact-time">{formatCompactBeijingTime(value)}</Text>
            </Tooltip>
          );
        }
      },
      {
        title: "消息数",
        dataIndex: ["runtime", "message_count"],
        width: ACCOUNT_TABLE_COLUMN_WIDTHS.messageCount,
        align: "right",
        hidden: !showAccountActivity,
        render: (value: number) => <span className="account-message-count">{value}</span>
      },
      {
        title: "备注",
        dataIndex: "remark",
        minWidth: ACCOUNT_TABLE_COLUMN_WIDTHS.remark,
        hidden: !showAccountActivity,
        render: (value?: string | null) => value ? (
          <Tooltip title={privateName(value)}>
            <span className="account-remark-text">{privateName(value)}</span>
          </Tooltip>
        ) : <Text type="secondary">未设置</Text>
      },
      {
        title: "操作",
        fixed: compactLayout ? undefined : "right",
        width: accountActionColumnWidth,
        render: (_, account) => (
          <Space className="account-actions">
            {canMutate ? (
              <>
                {account.cookie_health.manual_action_required ? (
                  <Tooltip title="Cookie 已失效，重新扫码">
                    <Button
                      size="small"
                      type="primary"
                      danger
                      icon={<QrcodeOutlined />}
                      loading={recoveringAccountId === account.account_id || qrLoading}
                      aria-label="重新扫码登录闲鱼账户"
                      onClick={() => void beginAccountQRLogin(account)}
                    />
                  </Tooltip>
                ) : account.runtime.recovery_action === "verify" ? (
                  <Tooltip title="安全验证">
                    <Button
                      size="small"
                      type="primary"
                      icon={<SafetyCertificateOutlined />}
                      loading={recoveringAccountId === account.account_id}
                      aria-label="人工安全验证"
                      onClick={() => void showIMVerification(account)}
                    />
                  </Tooltip>
                ) : account.runtime.recovery_action === "reconnect" ? (
                  <Tooltip title="恢复连接">
                    <Button
                      size="small"
                      icon={<SyncOutlined />}
                      loading={recoveringAccountId === account.account_id}
                      aria-label="恢复账户连接"
                      onClick={() => void runReconnect(account)}
                    />
                  </Tooltip>
                ) : account.runtime.recovery_action === "relogin" ? (
                  <Tooltip title="重新登录">
                    <Button
                      size="small"
                      icon={<QrcodeOutlined />}
                      loading={recoveringAccountId === account.account_id || qrLoading}
                      aria-label="重新登录闲鱼账户"
                      onClick={() => void beginAccountQRLogin(account)}
                    />
                  </Tooltip>
                ) : account.runtime.recovery_action === "fix_proxy" ? (
                  <Tooltip title="处理代理">
                    <Button
                      size="small"
                      icon={<ApiOutlined />}
                      aria-label="处理账户代理"
                      onClick={() => openEditDrawer(account)}
                    />
                  </Tooltip>
                ) : null}
                <Tooltip title="编辑账户">
                  <Button
                    size="small"
                    icon={<EditOutlined />}
                    aria-label="编辑账户"
                    onClick={() => openEditDrawer(account)}
                  />
                </Tooltip>
              </>
            ) : null}
            <Dropdown
              trigger={["click"]}
              menu={{
                items: [
                  ...(canMutate
                    ? [
                        {
                          key: "account-browser",
                          icon: <DesktopOutlined />,
                          label: isActiveAccountBrowser(accountBrowserStatuses[account.account_id])
                            ? "进入 VNC"
                            : "VNC 会话"
                        }
                      ]
                    : []),
                  { key: "runtime-logs", icon: <HistoryOutlined />, label: "运行日志" },
                  { key: "cookie-renewal", icon: <HistoryOutlined />, label: "Cookie" },
                  ...(canMutate
                    ? [
                        { type: "divider" as const },
                        account.enabled
                          ? { key: "disable", icon: <StopOutlined />, label: "停用账户" }
                          : { key: "enable", icon: <PlayCircleOutlined />, label: "启用账户" },
                        { type: "divider" as const },
                        { key: "delete", icon: <DeleteOutlined />, label: "删除账户", danger: true }
                      ]
                    : [])
                ],
                onClick: ({ key }) => {
                  if (key === "account-browser") {
                    void openAccountBrowser(account);
                  } else if (key === "runtime-logs") {
                    openRuntimeLogDrawer(account);
                  } else if (key === "cookie-renewal") {
                    void showCookieRenewalStatus(account);
                  } else if (key === "enable" || key === "disable") {
                    runToggleAccountEnabled(account);
                  } else if (key === "delete") {
                    void runDelete(account);
                  }
                }
              }}
            >
              <Tooltip title="更多操作">
                <Button size="small" icon={<MoreOutlined />} aria-label="更多操作" />
              </Tooltip>
            </Dropdown>
          </Space>
        )
      }
    ],
    [
      accountActionColumnWidth,
      accountColumnWidth,
      accountBrowserStatuses,
      accountReordering,
      canMutate,
      accountAutoReplyUpdatingId,
      accountWorkspaceVisibilityUpdatingKeys,
      compactLayout,
      proxies,
      qrLoading,
      recoveringAccountId,
      privacyMaskEnabled,
      runtimeHealthByAccount,
      showAccountActivity,
      showAccountDetails,
      showAccountProxy,
      showAccountToggles
    ]
  );

  function renderDashboardPage() {
    const executorActive =
      processHealth?.executors.reduce((total, item) => total + item.active, 0) ?? 0;
    const executorQueued =
      processHealth?.executors.reduce((total, item) => total + item.queued, 0) ?? 0;
    const executorRejected =
      processHealth?.executors.reduce((total, item) => total + item.rejected, 0) ?? 0;
    const processWarning = Boolean(
      processHealth &&
        (processHealth.event_loop.status !== "healthy" ||
          !processHealth.worker.online ||
          executorRejected > 0)
    );
    return (
      <Space direction="vertical" size={16} className="content-stack">
        <Card>
          <Descriptions column={{ xs: 2, sm: 3, lg: 6 }} size="small">
            <Descriptions.Item label="账户数">{accounts.length}</Descriptions.Item>
            <Descriptions.Item label="在线">
              {accounts.filter((item) => item.runtime.state === "online").length}
            </Descriptions.Item>
            <Descriptions.Item label="代理账户">
              {accounts.filter((item) => item.proxy.enabled).length}
            </Descriptions.Item>
            <Descriptions.Item label="错误">
              {
                accounts.filter((item) =>
                  ["error", "auth_expired", "proxy_failed"].includes(item.runtime.state)
                ).length
              }
            </Descriptions.Item>
            <Descriptions.Item label="Chat 开启">
              {accounts.filter((item) => item.chat_enabled).length}
            </Descriptions.Item>
            <Descriptions.Item label="智能回复">
              {accounts.filter((item) => item.auto_reply_enabled).length}
            </Descriptions.Item>
          </Descriptions>
        </Card>
        <Card title="系统运行状态">
          <Space direction="vertical" size={12} className="content-stack">
            {processWarning ? (
              <Alert
                showIcon
                type="warning"
                message="运行状态存在异常"
                description={
                  !processHealth?.worker.online
                    ? processHealth?.worker.error || "后台任务 Worker 未上报心跳"
                    : processHealth?.event_loop.status !== "healthy"
                      ? `事件循环 P95 延迟 ${processHealth?.event_loop.p95_lag_ms_60s ?? 0} ms`
                      : `线程池累计拒绝 ${executorRejected} 个任务`
                }
              />
            ) : null}
            <Descriptions column={{ xs: 2, sm: 3, lg: 6 }} size="small">
              <Descriptions.Item label="API 进程">{processHealth?.process_id ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="事件循环">
                <Tag
                  color={
                    processHealth?.event_loop.status === "critical"
                      ? "red"
                      : processHealth?.event_loop.status === "warning"
                        ? "orange"
                        : "green"
                  }
                >
                  {processHealth
                    ? `${processHealth.event_loop.p95_lag_ms_60s} ms`
                    : "等待采样"}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Worker">
                <Tag color={processHealth?.worker.online ? "green" : "red"}>
                  {processHealth?.worker.online ? "在线" : "离线"}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="系统线程">{processHealth?.thread_count ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="阻塞任务">{executorActive}</Descriptions.Item>
              <Descriptions.Item label="线程池排队">{executorQueued}</Descriptions.Item>
            </Descriptions>
            <Table
              rowKey="name"
              size="small"
              pagination={false}
              dataSource={processHealth?.executors ?? []}
              scroll={{ x: 720 }}
              columns={[
                { title: "执行器", dataIndex: "name", width: 120 },
                { title: "线程", dataIndex: "max_workers", width: 80 },
                { title: "运行", dataIndex: "active", width: 80 },
                { title: "排队", dataIndex: "queued", width: 80 },
                { title: "拒绝", dataIndex: "rejected", width: 80 },
                {
                  title: "平均排队",
                  dataIndex: "average_queue_wait_ms",
                  width: 120,
                  render: (value: number) => `${value} ms`
                },
                {
                  title: "平均耗时",
                  dataIndex: "average_duration_ms",
                  width: 120,
                  render: (value: number) => `${value} ms`
                }
              ]}
            />
          </Space>
        </Card>
      </Space>
    );
  }

  function renderUsersPage() {
    const visibleUsers = isAdmin ? users : currentUser ? [currentUser] : [];
    return (
      <Card
        title="用户管理"
        extra={
          isAdmin ? (
            <Space>
              {pendingUserMutationKeys.size > 0 ? (
                <Tag icon={<SyncOutlined spin />} color="processing">
                  {pendingUserMutationKeys.size} 项后台保存中
                </Tag>
              ) : null}
              <Button type="primary" icon={<PlusOutlined />} onClick={openCreateUserDrawer}>
                新增用户
              </Button>
            </Space>
          ) : null
        }
      >
        <Table
          rowKey="user_id"
          loading={usersLoading}
          dataSource={visibleUsers}
          pagination={{ pageSize: 10 }}
          scroll={{ x: 1000 }}
          columns={[
            {
              title: "用户名",
              dataIndex: "username",
              render: (value: string, user: AdminUser) => (
                <Space direction="vertical" size={0}>
                  <Space size={6} wrap>
                    <Text strong>{privateName(value)}</Text>
                    {currentUser?.user_id === user.user_id ? <Tag color="blue">当前会话</Tag> : null}
                  </Space>
                  <Text type="secondary" copyable={privacyMaskEnabled ? false : undefined}>
                    {privateId(user.user_id)}
                  </Text>
                </Space>
              )
            },
            {
              title: "角色",
              dataIndex: "role",
              width: 120,
              render: (role: AdminUser["role"]) => {
                const color = role === "admin" ? "red" : role === "operator" ? "blue" : "default";
                return <Tag color={color}>{role}</Tag>;
              }
            },
            {
              title: "状态",
              dataIndex: "enabled",
              width: 100,
              render: (enabled: boolean) => (enabled ? <Tag color="green">启用</Tag> : <Tag color="red">禁用</Tag>)
            },
            {
              title: "登录信息",
              width: 260,
              render: (_, user: AdminUser) => {
                const current = currentUser?.user_id === user.user_id;
                const ip = current ? clientAccess?.ip || user.last_login_ip : user.last_login_ip;
                const source = current
                  ? clientAccess?.source || user.last_login_source
                  : user.last_login_source;
                const details = current && clientAccess ? (
                  <Descriptions size="small" column={1}>
                    <Descriptions.Item label="remote_addr">{privateIP(clientAccess.remote_addr) || "-"}</Descriptions.Item>
                    <Descriptions.Item label="CF-Connecting-IP">{privateIP(clientAccess.cf_connecting_ip) || "-"}</Descriptions.Item>
                    <Descriptions.Item label="True-Client-IP">{privateIP(clientAccess.true_client_ip) || "-"}</Descriptions.Item>
                    <Descriptions.Item label="X-Real-IP">{privateIP(clientAccess.x_real_ip) || "-"}</Descriptions.Item>
                    <Descriptions.Item label="X-Forwarded-For">{privateIP(clientAccess.x_forwarded_for) || "-"}</Descriptions.Item>
                  </Descriptions>
                ) : null;
                return (
                  <Space direction="vertical" size={2}>
                    <Text>{formatTime(user.last_login_at)}</Text>
                    <Space size={4} wrap>
                      <Tag>{ip ? privateIP(ip) : "IP 未记录"}</Tag>
                      <Tag color={current ? "blue" : "default"}>{loginSourceLabel(source)}</Tag>
                      {details ? (
                        <Popover title="当前访问链路" content={details} trigger="click">
                          <Button type="link" size="small">详情</Button>
                        </Popover>
                      ) : null}
                    </Space>
                  </Space>
                );
              }
            },
            {
              title: "创建时间",
              dataIndex: "created_at",
              width: 170,
              render: (value: string) => formatTime(value)
            },
            {
              title: "操作",
              width: 120,
              hidden: !isAdmin,
              render: (_, user: AdminUser) => (
                <Button
                  size="small"
                  icon={<EditOutlined />}
                  loading={pendingUserMutationKeys.has(`user:${user.user_id}`)}
                  onClick={() => openEditUserDrawer(user)}
                >
                  编辑
                </Button>
              )
            }
          ]}
        />
      </Card>
    );
  }

  function renderAccountBasicForm() {
    return (
      <>
        <Form.Item
          name="remark"
          label="备注"
          extra="可选，仅用于系统内识别，不会替代平台自动获取的用户名。"
        >
          <Input.TextArea rows={3} maxLength={500} showCount placeholder="例如：主号、售后号或负责人信息" />
        </Form.Item>
        <Form.Item
          name="cookie"
          label="闲鱼 Cookie"
          extra={
            editing
              ? accountCookieLoading
                ? "正在读取原 Cookie…"
                : editingOriginalCookie !== null
                  ? "已加载原 Cookie；内容未修改时不会重复应用。"
                  : "未读取到原 Cookie，可粘贴新 Cookie 进行替换。"
              : "真实启动连接需要完整 Cookie。"
          }
        >
          <Input.TextArea
            rows={5}
            disabled={(Boolean(editing) && accountCookieLoading) || privacyMaskEnabled}
            placeholder={privacyMaskEnabled ? "隐私模式下 Cookie 已隐藏" : accountCookieLoading ? "正在读取原 Cookie…" : "粘贴完整 Cookie"}
          />
        </Form.Item>
        {!editing ? (
          <Form.Item name="enabled" label="启用账户" valuePropName="checked">
            <Switch />
          </Form.Item>
        ) : null}
        <Form.Item name="proxy_id" label="SOCKS5 代理" extra="单账户单代理；浏览器、HTTP 与 WSS 共用此出口。">
          <Select
            allowClear
            placeholder="不选择则直连"
            options={proxies.filter((proxy) => proxy.enabled).map((proxy) => {
              const assignedAccount = accounts.find((account) => account.proxy_id === proxy.proxy_id);
              const assignedToOther = Boolean(assignedAccount && assignedAccount.account_id !== editing?.account_id);
              const assignmentLabel = assignedToOther
                ? ` · 已绑定 ${accountDisplayName(assignedAccount)}`
                : assignedAccount ? " · 当前账户" : "";
              return {
                label: `${privateName(proxy.name)} · ${privateId(proxy.host)}:${proxy.port}${assignmentLabel}`,
                value: proxy.proxy_id,
                disabled: assignedToOther
              };
            })}
          />
        </Form.Item>
      </>
    );
  }

  function renderAccountBrowserIdentityForm() {
    const installedVersions = browserRuntime?.fingerprint_browsers.filter((item) => item.valid) ?? [];
    const identity = selectedBrowserIdentity ?? defaultBrowserIdentity();
    const activeEditorSession = editing ? accountBrowserStatuses[editing.account_id] : undefined;
    const listedEditorAccount = editing
      ? accounts.find((account) => account.account_id === editing.account_id)
      : undefined;
    const snapshot = activeEditorSession?.fingerprint_snapshot
      ?? editing?.browser_identity.fingerprint_snapshot
      ?? listedEditorAccount?.browser_identity.fingerprint_snapshot
      ?? null;
    const runtimeVersion = selectedBrowserEngine === "system_chromium"
      ? identity.browser_version || browserRuntime?.system_browser.version
      : identity.browser_version;
    const systemKernelVersion = selectedBrowserEngine === "system_chromium"
      ? runtimeVersion
      : browserRuntime?.active_standard_version || browserRuntime?.system_browser.version;
    const fingerprintKernelVersion = selectedBrowserEngine === "fingerprint_chromium"
      ? identity.browser_version
      : browserRuntime?.active_fingerprint_version;
    const selectedBrowserMajor = Number.parseInt(String(identity.browser_version || "0").split(".")[0], 10);
    const moduleControlsSupported = selectedBrowserEngine === "fingerprint_chromium" && selectedBrowserMajor >= 144;
    const fingerprintModules = [
      { field: "spoof_canvas" as const, label: "Canvas" },
      { field: "spoof_webgl" as const, label: "WebGL / GPU" },
      { field: "spoof_audio" as const, label: "Audio" },
      { field: "spoof_fonts" as const, label: "字体" },
      { field: "spoof_client_rects" as const, label: "ClientRects" }
    ];
    const usesRealFingerprintValue = fingerprintModules.some(({ field }) => identity[field] === false);
    const fingerprintModuleSummary = selectedBrowserEngine === "fingerprint_chromium"
      ? fingerprintModules.map(({ field, label }) => `${label}：${identity[field] === false ? "真实值" : "Seed"}`).join(" · ")
      : "系统 Chrome 使用运行环境值，不应用 Seed 模块";
    const configRevision = editing?.browser_identity.config_revision ?? identity.config_revision ?? 1;
    const acceptLanguagePrimary = String(identity.accept_language || "")
      .split(",", 1)[0]
      .split(";", 1)[0]
      .trim()
      .toLowerCase();
    const languageHeaderMismatch = Boolean(
      identity.language
      && acceptLanguagePrimary
      && identity.language.toLowerCase() !== acceptLanguagePrimary
    );
    const snapshotMatchesConfig = Boolean(
      snapshot
      && snapshot.config_revision === configRevision
      && snapshot.browser_engine === selectedBrowserEngine
      && snapshot.target_platform === identity.platform
      && snapshot.brand === identity.brand
      && snapshot.language === identity.language
      && snapshot.accept_language === identity.accept_language
      && snapshot.timezone === identity.timezone
      && snapshot.webrtc_policy === identity.webrtc_policy
      && snapshot.spoof_canvas === identity.spoof_canvas
      && snapshot.spoof_webgl === identity.spoof_webgl
      && snapshot.spoof_audio === identity.spoof_audio
      && snapshot.spoof_fonts === identity.spoof_fonts
      && snapshot.spoof_client_rects === identity.spoof_client_rects
      && (!runtimeVersion || snapshot.browser_version === runtimeVersion)
    );
    const previewUserAgent = browserIdentityUserAgent(identity, runtimeVersion);
    const observedSnapshotMeta = browserFingerprintDetectionMeta(snapshot);
    const snapshotStatus = accountBrowserDetecting
      || activeEditorSession?.fingerprint_detection_status === "collecting"
      ? { color: "processing", text: "检测中" }
      : activeEditorSession?.fingerprint_detection_status === "failed"
        ? { color: "error", text: "检测失败" }
        : !snapshotMatchesConfig
          ? { color: "default", text: snapshot ? "配置已变化，待重新检测" : "待首次启动检测" }
          : { color: observedSnapshotMeta.color, text: observedSnapshotMeta.label };
    const snapshotSecurityMeta = browserFingerprintSecurityMeta(
      snapshotMatchesConfig ? snapshot : null
    );
    return (
      <Space direction="vertical" size={8} className="content-stack account-browser-identity">
        <Form.Item
            className="account-browser-inline-form-item account-browser-kernel-field"
            name={["browser_identity", "browser_engine"]}
            label={
              <Space size={6}>
                <span>内核</span>
                <Tag className="account-browser-identity-tag" color="blue">热配置</Tag>
                <Tooltip
                  title={
                    selectedBrowserEngine === "fingerprint_chromium"
                      ? "本配置按账户隔离；平台与指纹模块由 Fingerprint Chromium 内核统一生成，修改后会清理旧浏览器目录。"
                      : "本配置按账户隔离；系统 Chrome 会同步 UA、UA-CH、语言和时区，修改后会清理旧浏览器目录。"
                  }
                >
                  <InfoCircleOutlined className="account-browser-identity-help" aria-label="查看浏览器热配置说明" />
                </Tooltip>
                <Tag
                  className="account-browser-identity-tag"
                  color={selectedBrowserEngine === "fingerprint_chromium" ? "purple" : "blue"}
                >
                  {selectedBrowserEngine === "fingerprint_chromium" ? "内核级" : "兼容模拟"}
                </Tag>
              </Space>
            }
            rules={[{ required: true }]}
          >
            <Select
            onChange={(engine) => {
              if (engine === "fingerprint_chromium") {
                const identity = form.getFieldValue("browser_identity") ?? defaultBrowserIdentity();
                const retainedVersion = installedVersions.some((item) => item.version === identity.browser_version)
                  ? identity.browser_version
                  : null;
                const targetVersion = retainedVersion || browserRuntime?.active_fingerprint_version || installedVersions[0]?.version || null;
                const targetMajor = Number.parseInt(String(targetVersion || "0").split(".")[0], 10);
                form.setFieldValue("browser_identity", {
                  ...identity,
                  browser_engine: engine,
                  fingerprint_seed: identity.fingerprint_seed || randomFingerprintSeed(),
                  browser_version: targetVersion,
                  ...(targetMajor < 144 ? {
                    spoof_canvas: true,
                    spoof_webgl: true,
                    spoof_audio: true,
                    spoof_fonts: true,
                    spoof_client_rects: true
                  } : {})
                });
              } else {
                const identity = form.getFieldValue("browser_identity") ?? defaultBrowserIdentity();
                form.setFieldValue("browser_identity", {
                  ...identity,
                  browser_engine: engine,
                  fingerprint_seed: null,
                  browser_version: browserRuntime?.active_standard_version || null
                });
              }
            }}
            options={[
              {
                value: "system_chromium",
                label: `系统 Chrome${systemKernelVersion ? ` · ${systemKernelVersion}` : " · 未安装"}`
              },
              {
                value: "fingerprint_chromium",
                label: `Fingerprint Chromium${fingerprintKernelVersion ? ` · ${fingerprintKernelVersion}` : " · 未安装"}`,
                disabled: installedVersions.length === 0
              }
            ]}
            />
        </Form.Item>
        {selectedBrowserEngine === "system_chromium"
          && !identity.browser_version
          && browserRuntime?.system_browser.available === false ? (
          <Alert
            className="account-browser-identity-alert"
            type="warning"
            showIcon
            message={browserRuntime.system_browser.validation_message || "未检测到系统 Chromium"}
          />
        ) : null}
        <div className={`account-browser-field-grid account-browser-platform-grid${selectedBrowserEngine === "fingerprint_chromium" ? "" : " two-columns"}`}>
          <Form.Item className="account-browser-compact-field" name={["browser_identity", "platform"]} label="平台" rules={[{ required: true }]}>
            <Select options={[
              { label: "Windows", value: "windows" },
              { label: "Linux", value: "linux" },
              { label: "macOS", value: "macos" }
            ]} />
          </Form.Item>
          <Form.Item className="account-browser-compact-field" name={["browser_identity", "platform_version"]} label="版本" rules={[{ required: true }]}>
            <Input placeholder="10.0.0" />
          </Form.Item>
          {selectedBrowserEngine === "fingerprint_chromium" ? (
            <Form.Item
              className="account-browser-compact-field"
              name={["browser_identity", "hardware_concurrency"]}
              label="CPU"
            >
              <Select
                allowClear
                placeholder="Seed 自动"
                options={[4, 8, 12, 16].map((value) => ({ label: `${value} 线程`, value }))}
              />
            </Form.Item>
          ) : null}
        </div>
        {selectedBrowserEngine === "fingerprint_chromium" ? (
          <>
            <Form.Item label="稳定指纹编号（Seed）" required extra="同一浏览器版本、平台和配置下持续复用；重新生成会改变账户指纹。">
              <Space.Compact block>
                <Form.Item
                  name={["browser_identity", "fingerprint_seed"]}
                  noStyle
                  rules={[{ required: true, message: "请生成稳定指纹 Seed" }]}
                >
                  <InputNumber className="full-width" min={1} max={4_294_967_295} precision={0} />
                </Form.Item>
                <Button
                  icon={<ThunderboltOutlined />}
                  onClick={() => {
                    const generate = () => form.setFieldValue(["browser_identity", "fingerprint_seed"], randomFingerprintSeed());
                    if (!editing) {
                      generate();
                      return;
                    }
                    Modal.confirm({
                      title: "重新生成稳定指纹？",
                      content: "保存后会清理该账户旧浏览器 Profile，Canvas、WebGL、Audio、字体等指纹都会变化。",
                      okText: "重新生成",
                      cancelText: "取消",
                      onOk: generate
                    });
                  }}
                >
                  重新生成
                </Button>
              </Space.Compact>
            </Form.Item>
            <div className="fingerprint-module-section">
              <div className="fingerprint-module-heading">
                <Typography.Text strong>指纹模块</Typography.Text>
                <Typography.Text type="secondary">开启使用 Seed 生成，关闭使用底层真实值</Typography.Text>
              </div>
              <div className="fingerprint-module-grid">
                {fingerprintModules.map(({ field, label }) => (
                  <div key={field} className="fingerprint-module-item">
                    <span>{label}</span>
                    <Form.Item name={["browser_identity", field]} valuePropName="checked" noStyle>
                      <Switch
                        size="small"
                        disabled={!moduleControlsSupported}
                        checkedChildren="Seed"
                        unCheckedChildren="真实"
                      />
                    </Form.Item>
                  </div>
                ))}
              </div>
              <Typography.Text type="secondary" className="fingerprint-module-note">
                {moduleControlsSupported
                  ? "关闭不是禁用浏览器功能，而是停止该模块的指纹改写。"
                  : "当前版本低于 Chrome 144，不支持按模块关闭指纹改写。"}
              </Typography.Text>
            </div>
            {usesRealFingerprintValue ? (
              <Alert
                className="account-browser-identity-alert"
                type="warning"
                showIcon
                message="部分模块正在使用真实值；多个账户共用相同运行环境时可能产生关联特征。"
              />
            ) : null}
          </>
        ) : null}
        <div className="account-browser-identity-subheading">
          <Typography.Text strong>浏览器身份参数</Typography.Text>
        </div>
        <div className="account-browser-field-grid account-browser-locale-grid">
          <Form.Item name={["browser_identity", "brand"]} label="浏览器品牌" rules={[{ required: true }]}>
            <Select options={[
              { label: "Chrome", value: "Chrome" },
              { label: "Edge", value: "Edge" },
              { label: "Opera", value: "Opera" },
              { label: "Vivaldi", value: "Vivaldi" }
            ]} />
          </Form.Item>
          <Form.Item
            name={["browser_identity", "language"]}
            label="浏览器语言"
            rules={[
              { required: true, message: "请输入浏览器语言" },
              { pattern: /^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$/, message: "请输入有效语言代码，例如 zh-CN" }
            ]}
          >
            <AutoComplete
              placeholder="例如 zh-CN"
              options={["zh-CN", "zh-TW", "en-US", "ja-JP", "ko-KR"].map((value) => ({ value }))}
            />
          </Form.Item>
          <Form.Item name={["browser_identity", "timezone"]} label="时区" rules={[{ required: true }]}>
            <Select showSearch options={[
              { label: "Asia/Shanghai", value: "Asia/Shanghai" },
              { label: "Asia/Hong_Kong", value: "Asia/Hong_Kong" },
              { label: "Asia/Taipei", value: "Asia/Taipei" },
              { label: "Asia/Singapore", value: "Asia/Singapore" },
              { label: "America/Los_Angeles", value: "America/Los_Angeles" },
              { label: "America/New_York", value: "America/New_York" },
              { label: "America/Chicago", value: "America/Chicago" },
              { label: "America/Denver", value: "America/Denver" }
            ]} />
          </Form.Item>
        </div>
        <Form.Item
          label="请求语言（Accept-Language）"
          extra="浏览器、HTTP 与 WSS 统一使用；可手动修改，或根据浏览器语言重新生成。"
          required
        >
          <Space.Compact block>
            <Form.Item
              name={["browser_identity", "accept_language"]}
              noStyle
              rules={[{ required: true, message: "请输入 Accept-Language" }]}
            >
              <Input placeholder="zh-CN,zh;q=0.9,en;q=0.8" />
            </Form.Item>
            <Button
              onClick={() => form.setFieldValue(
                ["browser_identity", "accept_language"],
                defaultAcceptLanguage(form.getFieldValue(["browser_identity", "language"]))
              )}
            >
              跟随语言
            </Button>
          </Space.Compact>
        </Form.Item>
        {languageHeaderMismatch ? (
          <Alert
            className="account-browser-identity-alert"
            type="warning"
            showIcon
            message="浏览器语言与 Accept-Language 首选语言不一致；可以保留，也可以点击“跟随语言”重新生成。"
          />
        ) : null}
        <Form.Item
          className="account-browser-inline-form-item account-browser-webrtc-field"
          name={["browser_identity", "webrtc_policy"]}
          label={
            <Space size={5}>
              <span>WebRTC</span>
              <Tooltip title="仅代理模式保留 WebRTC；严格阻断会影响音视频和部分实时功能。">
                <InfoCircleOutlined className="account-browser-identity-help" aria-label="查看 WebRTC 策略说明" />
              </Tooltip>
            </Space>
          }
        >
          <Select options={[
            { label: "仅允许代理链路（推荐）", value: "proxy_only" },
            { label: "严格阻断（WebRTC 不可用）", value: "disabled" },
            { label: "浏览器默认（有泄漏风险）", value: "browser_default" }
          ]} />
        </Form.Item>
        <Form.Item name={["browser_identity", "browser_version"]} hidden>
          <Input />
        </Form.Item>
        <Descriptions title="统一身份预览" size="small" column={1} bordered>
          <Descriptions.Item label="实现级别">
            {selectedBrowserEngine === "fingerprint_chromium" ? "内核级伪装" : "系统 Chrome 兼容模拟"}
          </Descriptions.Item>
          <Descriptions.Item label="品牌 / 语言">{identity.brand} · {identity.language} · {identity.accept_language}</Descriptions.Item>
          <Descriptions.Item label="指纹模块">{fingerprintModuleSummary}</Descriptions.Item>
          <Descriptions.Item label="UA"><Typography.Text copyable>{previewUserAgent}</Typography.Text></Descriptions.Item>
          <Descriptions.Item label="HTTP / WSS">UA、目标平台、语言、Cookie 与账户代理统一读取本配置</Descriptions.Item>
          <Descriptions.Item label="身份修订">v{configRevision}</Descriptions.Item>
        </Descriptions>
        <Descriptions
          title="实际检测摘要"
          extra={activeEditorSession?.status === "ready" ? (
            <Button
              size="small"
              icon={<SyncOutlined spin={accountBrowserDetecting} />}
              loading={accountBrowserDetecting}
              onClick={() => void runAccountBrowserFingerprintDetection(activeEditorSession)}
            >
              {accountBrowserDetecting ? "检测中" : "重新检测"}
            </Button>
          ) : null}
          size="small"
          column={1}
          bordered
        >
          <Descriptions.Item label="检测状态">
            <Space size={8} wrap>
              <Tag color={snapshotStatus.color}>指纹：{snapshotStatus.text}</Tag>
              <Tag color={snapshotSecurityMeta.color}>安全：{snapshotSecurityMeta.label}</Tag>
              {activeEditorSession?.fingerprint_detection_error ? (
                <Text type="danger">{activeEditorSession.fingerprint_detection_error}</Text>
              ) : !snapshot ? (
                <Text type="secondary">开启账户 VNC 后自动检测，也可在会话就绪时手动检测</Text>
              ) : null}
            </Space>
          </Descriptions.Item>
          {snapshot ? (
            <>
              <Descriptions.Item label="检测时间">{new Date(snapshot.observed_at).toLocaleString()}</Descriptions.Item>
              <Descriptions.Item label="品牌 / UA-CH">{snapshot.brand} · {snapshot.ua_ch_brands.join("、") || "未返回"}</Descriptions.Item>
              <Descriptions.Item label="平台">目标 {snapshot.target_platform} · navigator {snapshot.observed_platform || "未返回"} · UA-CH {snapshot.ua_ch_platform || "未返回"}</Descriptions.Item>
              <Descriptions.Item label="语言 / 时区">{snapshot.language || "-"} · {snapshot.languages.join("、") || snapshot.accept_language || "-"} · {snapshot.timezone || "-"}</Descriptions.Item>
              <Descriptions.Item label="CPU / 内存">{snapshot.hardware_concurrency ?? "-"} 线程 · {snapshot.device_memory != null ? `${snapshot.device_memory} GB` : "未公开内存值"}</Descriptions.Item>
              <Descriptions.Item label="Canvas / ClientRects">{snapshot.canvas_hash || "-"} · {snapshot.client_rects_hash || "-"}</Descriptions.Item>
              <Descriptions.Item label="WebGL / GPU">{snapshot.webgl_vendor || "-"} · {snapshot.webgl_renderer || "-"} · {snapshot.webgl_hash || "-"}</Descriptions.Item>
              <Descriptions.Item label="Audio / 字体">{snapshot.audio_hash || "-"} · {snapshot.fonts_hash || "-"}{snapshot.detected_fonts.length ? ` · ${snapshot.detected_fonts.join("、")}` : ""}</Descriptions.Item>
              <Descriptions.Item label="模块模式">
                Canvas {snapshot.spoof_canvas ? "Seed" : "真实"} · WebGL/GPU {snapshot.spoof_webgl ? "Seed" : "真实"} · Audio {snapshot.spoof_audio ? "Seed" : "真实"} · 字体 {snapshot.spoof_fonts ? "Seed" : "真实"} · ClientRects {snapshot.spoof_client_rects ? "Seed" : "真实"}
              </Descriptions.Item>
              <Descriptions.Item label="WebRTC">
                {snapshot.webrtc_policy === "proxy_only" ? "仅允许代理链路" : snapshot.webrtc_policy === "disabled" ? "严格阻断" : "浏览器默认"}
                {` · API ${snapshot.webrtc_api_available === false ? "不可用" : "可用"} · 候选类型 ${snapshot.webrtc_candidate_types.join("、") || "无"}`}
                {` · ${browserWebRTCDetectionSummary(snapshot)}`}
                {` · STUN 增强${snapshot.webrtc_probe_configured ? "已启用" : "未启用"}`}
              </Descriptions.Item>
              <Descriptions.Item label="浏览器出口">
                {browserEgressDetectionSummary(snapshot)}
              </Descriptions.Item>
              <Descriptions.Item label="自动化 / CDP">
                {snapshot.automation_protection_level === "fingerprint_kernel" ? "内核级自动化兼容" : "系统 Chrome 基础兼容"}
                {` · webdriver ${snapshot.navigator_webdriver === true ? "暴露" : snapshot.navigator_webdriver === false ? "未暴露" : "未返回"}`}
                {` · CDP 探针 ${snapshot.cdp_stack_probe_detected === true ? "命中" : snapshot.cdp_stack_probe_detected === false ? "未命中" : "未返回"}`}
              </Descriptions.Item>
              <Descriptions.Item label="检测结论">
                {browserFingerprintRiskSummary(snapshot)}
              </Descriptions.Item>
              {snapshot.changed_fields.length ? (
                <Descriptions.Item label="变化字段">{snapshot.changed_fields.join("、")}</Descriptions.Item>
              ) : null}
            </>
          ) : (
            <Descriptions.Item label="状态">开启账户浏览器会话后，将自动采集本项目标准检测摘要。</Descriptions.Item>
          )}
        </Descriptions>
      </Space>
    );
  }

  function renderAccountsPage() {
    return (
      <Card>
        <div className="account-page-toolbar">
          <Space>
            {canMutate ? (
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreateDrawer}>
              新增账户
            </Button>
            ) : null}
            <Button icon={<FolderOpenOutlined />} onClick={openBrowserProfileDrawer}>
              浏览器环境管理
            </Button>
          </Space>
        </div>
        <div ref={accountTableViewportRef} className="account-table-viewport">
          <DndContext
            sensors={accountSortSensors}
            collisionDetection={closestCenter}
            onDragEnd={(event) => void reorderAccountRows(event)}
          >
            <SortableContext
              items={accounts.map((account) => account.account_id)}
              strategy={verticalListSortingStrategy}
            >
              <Table
                components={{ body: { row: SortableAccountRow } }}
                className="account-table"
                rowKey="account_id"
                size="small"
                tableLayout="auto"
                loading={loading || accountReordering}
                columns={columns}
                dataSource={accounts}
                scroll={{ x: accountTableMinWidth }}
                pagination={false}
              />
            </SortableContext>
          </DndContext>
        </div>
      </Card>
    );
  }

  function renderSocksProxyPage() {
    const enabledProxies = proxies.filter((proxy) => proxy.enabled);
    const assignedAccountCount = accounts.filter((account) => account.proxy_id).length;
    const proxyFailedAccounts = accounts.filter((account) => account.runtime.state === "proxy_failed");

    return (
      <Card
        className="proxy-list-card"
        title={
          <div className="proxy-list-heading">
            <span className="proxy-list-title">代理节点</span>
            <Space size={[4, 4]} wrap className="proxy-summary-tags">
              <Tag>共 {proxies.length}</Tag>
              <Tag color="green">启用 {enabledProxies.length}</Tag>
              <Tag color="blue">已绑定 {assignedAccountCount}</Tag>
              <Tag color={proxyFailedAccounts.length ? "red" : "default"}>
                异常账户 {proxyFailedAccounts.length}
              </Tag>
            </Space>
          </div>
        }
        extra={
          <Space wrap className="proxy-list-actions">
            {canMutate ? (
              <>
                <Button
                  icon={<ApiOutlined />}
                  loading={Boolean(proxyBatchProgress)}
                  disabled={!proxies.some((proxy) => proxy.enabled)}
                  onClick={() => void runProxyBatchTest()}
                >
                  {proxyBatchProgress
                    ? `检测中 ${proxyBatchProgress.completed}/${proxyBatchProgress.total}`
                    : selectedProxyIds.length
                      ? `选中项测试（${selectedProxyIds.length}）`
                      : "一键测试"}
                </Button>
                <Button type="primary" icon={<PlusOutlined />} onClick={openCreateProxyDrawer}>
                  新增代理
                </Button>
              </>
            ) : null}
            <Tooltip title="刷新代理列表">
              <Button
                icon={<SyncOutlined spin={proxyListLoading} />}
                aria-label="刷新代理列表"
                disabled={proxyListLoading}
                onClick={() => void loadProxyData()}
              />
            </Tooltip>
          </Space>
        }
      >
        <Table
            rowKey="proxy_id"
            loading={proxyListLoading}
            dataSource={proxies}
            scroll={{ x: 1306 }}
            pagination={{ pageSize: 10 }}
            rowSelection={canMutate ? {
              columnWidth: 48,
              fixed: !compactLayout,
              selectedRowKeys: selectedProxyIds,
              onSelect: (proxy, selected) => {
                setSelectedProxyIds((current) =>
                  selected
                    ? [...new Set([...current, proxy.proxy_id])]
                    : current.filter((proxyId) => proxyId !== proxy.proxy_id)
                );
              },
              onSelectAll: (selected) => {
                setSelectedProxyIds(
                  selected
                    ? proxies
                        .filter(
                          (proxy) => proxy.enabled && !deletingProxyIds.has(proxy.proxy_id)
                        )
                        .map((proxy) => proxy.proxy_id)
                    : []
                );
              },
              getCheckboxProps: (proxy) => ({
                disabled: !proxy.enabled || deletingProxyIds.has(proxy.proxy_id)
              }),
              selections: [
                {
                  key: "all-testable",
                  text: "选择全部可检测节点",
                  onSelect: () => setSelectedProxyIds(
                    proxies
                      .filter(
                        (proxy) => proxy.enabled && !deletingProxyIds.has(proxy.proxy_id)
                      )
                      .map((proxy) => proxy.proxy_id)
                  )
                },
                {
                  key: "untested",
                  text: "选择未检测节点",
                  onSelect: () => setSelectedProxyIds(
                    proxies
                      .filter(
                        (proxy) =>
                          proxy.enabled &&
                          proxy.last_test_ok == null &&
                          !deletingProxyIds.has(proxy.proxy_id)
                      )
                      .map((proxy) => proxy.proxy_id)
                  )
                },
                {
                  key: "clear",
                  text: "清空选择",
                  onSelect: () => setSelectedProxyIds([])
                }
              ]
            } : undefined}
            columns={[
              {
                title: "名称",
                dataIndex: "name",
                fixed: compactLayout ? undefined : "left",
                width: 260,
                render: (name: string, proxy: ProxyResource) => {
                  const assignedAccount = accounts.find(
                    (account) => account.proxy_id === proxy.proxy_id
                  );
                  return (
                    <div className="proxy-name-cell">
                      <div className="proxy-name-row">
                        <Tag color={proxy.enabled ? "green" : "default"}>
                          {proxy.enabled ? "启用" : "停用"}
                        </Tag>
                        <Text strong ellipsis={{ tooltip: privateName(name) }} className="proxy-name-value">
                          {privateName(name)}
                        </Text>
                      </div>
                      <div className="proxy-name-row">
                        {assignedAccount ? (
                          <>
                            <StatusTag state={assignedAccount.runtime.state} />
                            <Text
                              ellipsis={{ tooltip: accountDisplayName(assignedAccount) }}
                              className="proxy-account-value"
                            >
                              {accountDisplayName(assignedAccount)}
                            </Text>
                          </>
                        ) : (
                          <>
                            <Tag>未绑定</Tag>
                            <Text type="secondary" className="proxy-account-value">
                              暂无绑定账户
                            </Text>
                          </>
                        )}
                      </div>
                    </div>
                  );
                }
              },
              {
                title: "配置",
                className: "proxy-config-column",
                width: 240,
                render: (_, proxy: ProxyResource) => {
                  const proxyAddress = `${proxy.scheme}://${privateId(proxy.host)}:${proxy.port}`;
                  const needsAuthentication = Boolean(proxy.username || proxy.has_password);
                  const isTesting = testingProxyIds.has(proxy.proxy_id);
                  const isQueued = queuedProxyIds.has(proxy.proxy_id);
                  const exitIsCurrent = proxyExitIPIsCurrent(proxy);
                  const outletWarning = proxy.last_test_ok === true && !exitIsCurrent;
                  const testMetadata = [
                    proxy.last_platform_status != null
                      ? `HTTP ${proxy.last_platform_status}`
                      : null,
                    proxy.last_test_latency_ms != null
                      ? `${proxy.last_test_latency_ms}ms`
                      : null
                  ].filter((value): value is string => Boolean(value));

                  let testTag = <Tag>未检测</Tag>;
                  let testText = "点击雷电图标检测";
                  let testTextType: "secondary" | "danger" | "warning" = "secondary";
                  if (isTesting) {
                    testTag = <Tag color="processing" icon={<SyncOutlined spin />}>检测中</Tag>;
                    testText = "检测连通性与 IP";
                  } else if (isQueued) {
                    testTag = <Tag color="blue">等待中</Tag>;
                    testText = "等待进入检测队列";
                  } else if (proxy.last_test_ok === false) {
                    testTag = <Tag color="red">失败</Tag>;
                    testText = [
                      ...testMetadata,
                      privacyMaskEnabled
                        ? "检测详情已隐藏"
                        : proxy.last_test_message || "检测失败"
                    ].join(" · ");
                    testTextType = "danger";
                  } else if (outletWarning) {
                    testTag = <Tag color="gold">可用</Tag>;
                    testText = "IP 未更新";
                    testTextType = "warning";
                  } else if (proxy.last_test_ok === true) {
                    testTag = <Tag color="green">可用</Tag>;
                    testText = testMetadata.join(" · ") || "检测通过";
                  }

                  return (
                    <div className="proxy-config-cell">
                      <div className="proxy-config-address-row">
                        <Text className="proxy-config-address">{proxyAddress}</Text>
                        {needsAuthentication ? (
                          <Tooltip title="该代理需要账号密码认证">
                            <LockOutlined className="proxy-auth-icon" aria-label="需要认证" />
                          </Tooltip>
                        ) : null}
                      </div>
                      <div className="proxy-config-status-row">
                        {testTag}
                        <Text
                          type={testTextType}
                          ellipsis={{ tooltip: testText }}
                          className="proxy-config-status-text"
                        >
                          {testText}
                        </Text>
                      </div>
                    </div>
                  );
                }
              },
              {
                title: "IP 信息",
                className: "proxy-ip-column",
                width: 430,
                render: (_, proxy: ProxyResource) => {
                  const hasExit = proxyHasExitIP(proxy);
                  const ipv4Location = privacyLocation(
                    privacyMaskEnabled,
                    proxy.exit_country,
                    proxy.exit_region,
                    proxy.exit_city,
                    proxy.exit_isp
                  ) || (privacyMaskEnabled ? "位置未解析" : proxyIPv4Location(proxy));
                  const ipv6Location = privacyLocation(
                    privacyMaskEnabled,
                    proxy.exit_ipv6_country,
                    proxy.exit_region,
                    proxy.exit_city,
                    proxy.exit_ipv6_continent
                  ) || (privacyMaskEnabled ? "位置未解析" : proxyIPv6Location(proxy));
                  return (
                    <div className="proxy-ip-cell">
                      {proxy.exit_ipv4 ? (
                        <div className="proxy-ip-row">
                          <Text type="secondary" className="proxy-ip-label">IPv4</Text>
                          <div className="proxy-ip-detail">
                            <Text className="proxy-ip-value">
                              {privateIPv4(proxy.exit_ipv4)}
                            </Text>
                            {ipv4Location !== "未解析" ? (
                              <Text
                                type="secondary"
                                className="proxy-ip-location"
                              >
                                {ipv4Location}
                              </Text>
                            ) : null}
                          </div>
                        </div>
                      ) : null}
                      {proxy.exit_ipv6 ? (
                        <div className="proxy-ip-row">
                          <Text type="secondary" className="proxy-ip-label">IPv6</Text>
                          <div className="proxy-ip-detail">
                            <Text className="proxy-ip-value">
                              {privateIPv6(proxy.exit_ipv6)}
                            </Text>
                            {ipv6Location !== "未解析" ? (
                              <Text
                                type="secondary"
                                className="proxy-ip-location"
                              >
                                {ipv6Location}
                              </Text>
                            ) : null}
                          </div>
                        </div>
                      ) : null}
                      {!hasExit ? <Text type="secondary">未获取 IP</Text> : null}
                    </div>
                  );
                }
              },
              {
                title: "检测时间",
                width: 200,
                render: (_, proxy: ProxyResource) => {
                  const exitIsCurrent = proxyExitIPIsCurrent(proxy);
                  return (
                    <Space direction="vertical" size={2} className="proxy-test-time-cell">
                      {proxy.last_test_at ? (
                        <Text type="secondary">{formatTime(proxy.last_test_at)}</Text>
                      ) : (
                        <Text type="secondary">未检测</Text>
                      )}
                      {!exitIsCurrent && proxy.exit_checked_at ? (
                        <Text type="secondary">IP {formatTime(proxy.exit_checked_at)}</Text>
                      ) : null}
                    </Space>
                  );
                }
              },
              {
                title: "操作",
                fixed: compactLayout ? undefined : "right",
                align: "center",
                width: 128,
                render: (_, proxy: ProxyResource) => canMutate ? (() => {
                  const isTesting = testingProxyIds.has(proxy.proxy_id);
                  const isQueued = queuedProxyIds.has(proxy.proxy_id);
                  const isDeleting = deletingProxyIds.has(proxy.proxy_id);
                  return (
                    <Space size={4} wrap={false} className="proxy-action-cell">
                      <Tooltip title="编辑代理">
                        <Button
                          size="small"
                          icon={<EditOutlined />}
                          aria-label="编辑代理"
                          disabled={isTesting || isQueued || isDeleting}
                          onClick={() => openEditProxyDrawer(proxy)}
                        />
                      </Tooltip>
                      <Tooltip title={isTesting ? "检测中" : isQueued ? "等待检测" : "测试代理"}>
                        <Button
                          size="small"
                          icon={<ThunderboltOutlined />}
                          aria-label={isTesting ? "检测中" : isQueued ? "等待检测" : "测试代理"}
                          loading={isTesting}
                          disabled={isQueued || isDeleting}
                          onClick={() => void runProxyResourceTest(proxy)}
                        />
                      </Tooltip>
                      <Tooltip title="删除代理">
                        <Button
                          danger
                          size="small"
                          icon={<DeleteOutlined />}
                          aria-label="删除代理"
                          loading={isDeleting}
                          disabled={isTesting || isQueued}
                          onClick={() => void removeProxy(proxy)}
                        />
                      </Tooltip>
                    </Space>
                  );
                })() : null
              }
            ]}
          />
      </Card>
    );
  }

  function renderOrderDrawer() {
    return (
      <Drawer
        title="订单详情"
        width={compactLayout ? "100%" : 720}
        open={orderDrawerOpen}
        onClose={() => setOrderDrawerOpen(false)}
      >
        <Spin spinning={orderLoading}>
          <div className="order-drawer-detail">
            {selectedOrder ? (
              <Space direction="vertical" size={16} className="content-stack">
                <div className="order-detail-heading">
                  <div className="order-detail-product">
                    {selectedOrder.image_url && !privacyMaskEnabled ? (
                      <img src={selectedOrder.image_url} alt="" />
                    ) : (
                      <div className="managed-product-cover-empty"><PictureOutlined /></div>
                    )}
                    <div>
                      <Title level={5}>{privateName(selectedOrder.title) || "闲鱼订单"}</Title>
                      <Space size={6} wrap>
                        <Text type="secondary">履约</Text>
                        {renderOrderStatus(selectedOrder.status)}
                        <Text type="secondary">退款</Text>
                        {renderRefundStatus(selectedOrder.refund_status)}
                        {selectedOrder.data_source === "seller_sold" ? <Tag color="green">已售订单</Tag> : null}
                        {selectedOrder.data_source === "buyer_bought" ? <Tag color="blue">买入订单</Tag> : null}
                        {selectedOrder.sync_state === "confirmed" ? <Tag color="success">平台已确认</Tag> : null}
                        {selectedOrder.headinfo_confirmed_at ? <Tag color="cyan">会话订单已确认</Tag> : null}
                        {selectedOrder.sync_state === "provisional" ? <Tag color="warning">会话推断</Tag> : null}
                        {selectedOrder.sync_state === "stale" ? <Tag color="orange">详情待刷新</Tag> : null}
                        {selectedOrder.sync_state === "error" ? <Tag color="error">同步异常</Tag> : null}
                        {selectedOrder.is_bargain ? <Tag color="purple">砍价订单</Tag> : null}
                      </Space>
                    </div>
                  </div>
                  <Button
                    icon={<SyncOutlined />}
                    loading={orderLoading}
                    onClick={() => void refreshSelectedOrder()}
                  >
                    刷新平台详情
                  </Button>
                </div>
                <Descriptions size="small" column={compactLayout ? 1 : 2} bordered>
                  <Descriptions.Item label="闲鱼账户">
                    {accountDisplayName(accounts.find(account => account.account_id === selectedOrder.account_id))}
                  </Descriptions.Item>
                  <Descriptions.Item label="平台状态">
                    {selectedOrder.platform_status || selectedOrder.status_text || "-"}
                  </Descriptions.Item>
                  <Descriptions.Item label="履约状态">
                    {renderOrderStatus(selectedOrder.status)}
                  </Descriptions.Item>
                  <Descriptions.Item label="退款状态">
                    <Space size={6} wrap>
                      {renderRefundStatus(selectedOrder.refund_status)}
                      {selectedOrder.refund_id ? (
                        <Text type="secondary" copyable={privacyMaskEnabled ? false : undefined}>
                          {privateId(selectedOrder.refund_id)}
                        </Text>
                      ) : null}
                    </Space>
                  </Descriptions.Item>
                  <Descriptions.Item label="平台订单号" span={2}>
                    {selectedOrder.platform_order_id ? (
                      <Text copyable={privacyMaskEnabled ? false : undefined}>
                        {privateId(selectedOrder.platform_order_id)}
                      </Text>
                    ) : "-"}
                  </Descriptions.Item>
                  <Descriptions.Item label="商品 ID">
                    {selectedOrder.item_id ? (
                      <Text copyable={privacyMaskEnabled ? false : undefined}>
                        {privateId(selectedOrder.item_id)}
                      </Text>
                    ) : "-"}
                  </Descriptions.Item>
                  <Descriptions.Item label="数量">{selectedOrder.quantity || 1}</Descriptions.Item>
                  <Descriptions.Item label={selectedOrder.trade_role === "buyer" ? "卖家" : "买家"}>
                    {selectedOrder.trade_role === "buyer"
                      ? privateName(selectedOrder.peer_name) || "-"
                      : privateName(selectedOrder.buyer_name || selectedOrder.peer_name) || "-"}
                  </Descriptions.Item>
                  <Descriptions.Item label={selectedOrder.trade_role === "buyer" ? "卖家 ID" : "买家 ID"}>
                    {selectedOrder.trade_role === "buyer"
                      ? privateId(selectedOrder.peer_user_id) || "-"
                      : privateId(selectedOrder.buyer_user_id || selectedOrder.peer_user_id) || "-"}
                  </Descriptions.Item>
                  <Descriptions.Item label="订单金额">{selectedOrder.price || "-"}</Descriptions.Item>
                  <Descriptions.Item label="下单时间">
                    {formatTime(selectedOrder.platform_created_at || selectedOrder.created_at)}
                  </Descriptions.Item>
                  <Descriptions.Item label="详情同步时间">
                    {selectedOrder.last_detail_synced_at ? formatTime(selectedOrder.last_detail_synced_at) : "尚未同步详情"}
                  </Descriptions.Item>
                  <Descriptions.Item label="会话确认时间">
                    {selectedOrder.headinfo_confirmed_at ? formatTime(selectedOrder.headinfo_confirmed_at) : "-"}
                  </Descriptions.Item>
                  <Descriptions.Item label="物流方式">{selectedOrder.logistics_type || "-"}</Descriptions.Item>
                  {selectedOrder.tracking_no ? (
                    <Descriptions.Item label="物流单号" span={2}>
                      <Text copyable={privacyMaskEnabled ? false : undefined}>{privateId(selectedOrder.tracking_no)}</Text>
                    </Descriptions.Item>
                  ) : null}
                  {selectedOrder.trade_role === "seller" ? (
                    <>
                      <Descriptions.Item label="收件人">{privateName(selectedOrder.receiver_name) || "-"}</Descriptions.Item>
                      <Descriptions.Item label="联系电话">
                        {maskSensitive(selectedOrder.receiver_phone, privacyMaskEnabled, "phone") || "-"}
                      </Descriptions.Item>
                      <Descriptions.Item label="收货地址" span={2}>
                        {maskSensitive(selectedOrder.receiver_address, privacyMaskEnabled, "address") || "-"}
                      </Descriptions.Item>
                    </>
                  ) : null}
                </Descriptions>

                {canMutate && selectedOrder.trade_role === "seller" ? (
                  <div className="order-platform-actions">
                    <Space align="center" wrap>
                      <Text strong>平台订单操作</Text>
                      <Text type="secondary">每次提交前都会重新读取平台状态</Text>
                    </Space>
                    {!selectedOrder.platform_confirmed ? (
                      <Alert
                        type="warning"
                        showIcon
                        message="该订单尚未由平台订单列表确认，暂不允许执行平台写操作"
                      />
                    ) : null}
                    {selectedOrder.refund_status === "pending" ||
                    selectedOrder.refund_status === "processing" ||
                    selectedOrder.refund_status === "refunding" ? (
                      <Alert
                        type="warning"
                        showIcon
                        message="平台显示该订单有待处理的退款申请"
                        description="履约与退款分别校验；只要闲鱼仍返回可用发货方式，订单仍可发货。"
                      />
                    ) : null}
                    <Space wrap>
                      {selectedOrder.available_actions.map((item) => (
                        <Tooltip key={item.action} title={item.enabled ? "" : item.reason}>
                          <span>
                            <Button
                              danger={item.danger}
                              disabled={
                                !item.enabled ||
                                Boolean(orderOperationAction)
                              }
                              loading={orderOperationAction === item.action}
                              onClick={() => void confirmOrderOperation(item.action)}
                            >
                              {item.label}
                            </Button>
                          </span>
                        </Tooltip>
                      ))}
                    </Space>
                    {selectedOrder.available_actions.some((item) => item.action === "rate_buyer" && item.enabled) ? (
                      <Input.TextArea
                        rows={2}
                        maxLength={500}
                        showCount
                        value={orderRateFeedback}
                        placeholder="填写给买家的评价内容"
                        onChange={(event) => setOrderRateFeedback(event.target.value)}
                      />
                    ) : null}
                    {selectedOrder.sync_error ? (
                      <Alert type="error" showIcon message="最近同步失败" description={selectedOrder.sync_error} />
                    ) : null}
                  </div>
                ) : null}

                {selectedOrder.operations.length > 0 ? (
                  <div className="order-operation-history">
                    <Text strong>平台操作记录</Text>
                    <List
                      size="small"
                      dataSource={selectedOrder.operations}
                      renderItem={(operation) => {
                        const actionLabel = selectedOrder.available_actions.find(
                          (item) => item.action === operation.action
                        )?.label || operation.action;
                        const statusMeta = {
                          processing: { label: "处理中", color: "processing" },
                          succeeded: { label: "成功", color: "success" },
                          failed: { label: "失败", color: "error" },
                          uncertain: { label: "结果待确认", color: "warning" }
                        }[operation.status];
                        return (
                          <List.Item>
                            <Space direction="vertical" size={2} className="content-stack">
                              <Space wrap>
                                <Text>{actionLabel}</Text>
                                <Tag color={statusMeta.color}>{statusMeta.label}</Tag>
                                {operation.platform_code ? <Text type="secondary">{operation.platform_code}</Text> : null}
                              </Space>
                              {operation.message || operation.error ? (
                                <Text type={operation.error ? "danger" : "secondary"}>
                                  {operation.message || operation.error}
                                </Text>
                              ) : null}
                              <Text type="secondary">
                                {operation.requested_by ? `${operation.requested_by} · ` : ""}
                                {formatTime(operation.finished_at || operation.created_at)}
                              </Text>
                            </Space>
                          </List.Item>
                        );
                      }}
                    />
                  </div>
                ) : null}

                <div className="order-events">
                  <Text strong>订单动态</Text>
                  <List
                    size="small"
                    dataSource={selectedOrder.events}
                    locale={{ emptyText: "暂无订单动态" }}
                    renderItem={(event) => (
                      <List.Item>
                        <Space direction="vertical" size={1}>
                          <Space>{renderOrderStatus(event.status)}<Text>{event.status_text || "订单状态更新"}</Text></Space>
                          <Text type="secondary">{formatTime(event.created_at)}</Text>
                        </Space>
                      </List.Item>
                    )}
                  />
                </div>

                {canMutate && selectedOrder.trade_role === "seller" && selectedOrder.data_source === "seller_sold" ? (
                  <div className="order-delivery-section">
                    <Text strong>人工交付</Text>
                    <Alert
                      type="info"
                      showIcon
                      message="交付内容通过该订单关联的闲鱼会话发送，不会修改平台物流状态"
                    />
                    <Select
                      allowClear
                      value={orderTemplateId}
                      placeholder="选择交付模板"
                      onChange={(value) => {
                        setOrderTemplateId(value);
                        setOrderDeliveryContent("");
                        setOrderPreview(null);
                      }}
                      options={deliveryTemplates
                        .filter((template) => template.enabled)
                        .map((template) => ({ label: template.name, value: template.template_id }))}
                    />
                    <Input.TextArea
                      rows={5}
                      value={orderDeliveryContent}
                      placeholder="选择模板后生成预览，或直接填写要发送给买家的内容"
                      onChange={(event) => {
                        setOrderDeliveryContent(event.target.value);
                        setOrderPreview(null);
                      }}
                    />
                    {orderPreview ? (
                      <Alert
                        type={orderPreview.eligible ? "success" : "warning"}
                        showIcon
                        message={orderPreview.eligible ? "发送条件已确认" : "当前不可发送"}
                        description={orderPreview.reasons.join("；") || "请确认内容后发送"}
                      />
                    ) : null}
                    <Space>
                      <Button loading={orderLoading} onClick={() => void createOrderDeliveryPreview()}>
                        生成预览
                      </Button>
                      <Button
                        type="primary"
                        icon={<SendOutlined />}
                        loading={orderLoading}
                        onClick={() => void confirmOrderDelivery()}
                      >
                        确认发送
                      </Button>
                    </Space>
                  </div>
                ) : null}
              </Space>
            ) : (
              <Empty description="暂无订单详情" />
            )}
          </div>
        </Spin>
      </Drawer>
    );
  }

  function renderConversationWorkspace() {
    const selectedAccount = selectedConversation
      ? conversationAccountMap.get(selectedConversation.account_id) ?? conversationAccount
      : null;
    const selectedAccountOffline = Boolean(selectedAccount && !accountIMAvailable(selectedAccount));
    const filteredSyncStatus =
      conversationAccountFilter === "all"
        ? null
        : conversationSyncStatusMap.get(conversationAccountFilter) ?? null;
    const failedConversationAccounts = conversationAccounts.filter(
      (account) =>
        accountIMAvailable(account) &&
        conversationSyncStatusMap.get(account.account_id)?.state === "error"
    );
    const filteredAccount = conversationAccountFilter === "all"
      ? null
      : conversationAccountMap.get(conversationAccountFilter) ?? null;
    const onlineConversationAccountCount = conversationAccounts.filter(accountIMAvailable).length;
    const abnormalConversationAccountCount =
      conversationAccounts.length - onlineConversationAccountCount;
    const unreadConversationCount = visibleConversations.filter(
      (conversation) => conversationUnreadCount(conversation) > 0
    ).length;
    const conversationEmptyDescription = filteredAccount && !accountIMAvailable(filteredAccount)
      ? `${accountDisplayName(filteredAccount)} 的 IM 当前${runtimeStateLabel(filteredAccount.runtime.state)}，会话已隐藏`
      : conversationAccountFilter === "all" && onlineConversationAccountCount === 0
        ? "当前没有 IM 在线账户，会话已隐藏"
        : filteredSyncStatus?.state === "error"
      ? `${accountDisplayName(conversationAccountMap.get(filteredSyncStatus.account_id))}会话同步失败：${
          privacyMaskEnabled && filteredSyncStatus.last_error
            ? "错误详情已隐藏"
            : filteredSyncStatus.last_error || "IM 请求没有响应"
        }`
      : filteredSyncStatus?.state === "syncing" || filteredSyncStatus?.state === "pending"
        ? "正在从闲鱼同步会话"
        : filteredSyncStatus?.state === "offline"
          ? "当前账户 IM 已离线，会话已隐藏"
          : "暂无会话。收到消息或完成平台同步后会出现在这里。";
    const manualTakeoverMode: "auto" | "temporary" | "permanent" =
      selectedConversation?.manual_takeover_mode === "permanent"
        ? "permanent"
        : selectedConversation?.manual_takeover_until &&
            apiTimeToEpochMs(selectedConversation.manual_takeover_until) > Date.now()
          ? "temporary"
          : "auto";
    const quickPhraseNeedle = quickPhraseSearch.trim().toLowerCase();
    const visibleQuickPhrases = quickPhrases.filter((phrase) =>
      !quickPhraseNeedle ||
      phrase.title.toLowerCase().includes(quickPhraseNeedle) ||
      phrase.content.toLowerCase().includes(quickPhraseNeedle) ||
      phrase.group_name.toLowerCase().includes(quickPhraseNeedle)
    );

    return (
      <div
        className={`conversation-shell${
          compactLayout && mobileConversationDetailOpen ? " mobile-chat-active" : ""
        }`}
      >
        <div className="conversation-account-rail" role="group" aria-label="会话账户筛选">
          <Tooltip
            title={`全部账户：IM 在线 ${onlineConversationAccountCount}，异常 ${abnormalConversationAccountCount}`}
          >
            <button
              type="button"
              className={`conversation-account-avatar-button${conversationAccountFilter === "all" ? " selected" : ""}`}
              aria-label="显示全部账户会话"
              aria-pressed={conversationAccountFilter === "all"}
              onClick={() => changeConversationAccountFilter("all")}
            >
              <span className="conversation-account-avatar-shell">
                <Avatar size={42} icon={<RobotOutlined />} />
                {conversationAccountFilter === "all" ? (
                  <CheckCircleFilled className="conversation-account-selected" />
                ) : null}
              </span>
            </button>
          </Tooltip>
          {conversationAccounts.map((account) => {
            const selected = conversationAccountFilter === account.account_id;
            const cookieNormal =
              (account.cookie_health.state === "valid" ||
                account.cookie_health.state === "renewing") &&
              !account.cookie_health.manual_action_required;
            const imNormal = accountIMAvailable(account);
            const avatarFallback = (
              account.platform_display_name || account.remark || account.platform
            ).slice(0, 1);
            return (
              <Tooltip
                key={account.account_id}
                title={
                  <Space direction="vertical" size={1}>
                    <span>平台：{platformName(account.platform)}</span>
                    <span>账户：{platformAccountName(account)}</span>
                    <span>备注：{account.remark ? privateName(account.remark) : "未设置"}</span>
                    <span>
                      Cookie：{account.cookie_health.message || account.cookie_health.state}
                    </span>
                    <span>
                      IM：{account.runtime.message || runtimeStateLabel(account.runtime.state)}
                    </span>
                  </Space>
                }
              >
                <button
                  type="button"
                  className={`conversation-account-avatar-button${selected ? " selected" : ""}`}
                  aria-label={`筛选账户 ${accountDisplayName(account)}`}
                  aria-pressed={selected}
                  onClick={() => changeConversationAccountFilter(account.account_id)}
                >
                  <span className="conversation-account-avatar-shell">
                    <Avatar
                      size={42}
                      src={!privacyMaskEnabled ? account.platform_avatar_url || undefined : undefined}
                    >
                      {privacyMaskEnabled ? <LockOutlined /> : avatarFallback}
                    </Avatar>
                    <Tooltip title={cookieNormal ? "Cookie 正常" : "Cookie 异常"}>
                      <span
                        className={`conversation-account-health-dot cookie ${cookieNormal ? "normal" : "abnormal"}`}
                      />
                    </Tooltip>
                    <Tooltip title={imNormal ? "IM 正常" : "IM 异常"}>
                      <span
                        className={`conversation-account-health-dot im ${imNormal ? "normal" : "abnormal"}`}
                      />
                    </Tooltip>
                    {selected ? (
                      <CheckCircleFilled className="conversation-account-selected" />
                    ) : null}
                  </span>
                </button>
              </Tooltip>
            );
          })}
        </div>
        <div className="conversation-list">
          <div className="conversation-list-toolbar">
            <Segmented
              className="conversation-status-segmented"
              block
              size="small"
              value={conversationStatusFilter}
              onClick={clearConversationWorkspace}
              options={[
                {
                  label: (
                    <span className="conversation-filter-option">
                      <MessageOutlined />
                      <span>全部</span>
                    </span>
                  ),
                  value: "all"
                },
                {
                  label: (
                    <span className="conversation-filter-option">
                      <BellOutlined />
                      <span>未查看</span>
                      {unreadConversationCount > 0 ? (
                        <span
                          className="conversation-filter-count"
                          aria-label={`${unreadConversationCount} 个未查看会话`}
                        >
                          {unreadConversationCount > 99 ? "99+" : unreadConversationCount}
                        </span>
                      ) : null}
                    </span>
                  ),
                  value: "unread"
                }
              ]}
              onChange={(value) =>
                changeConversationStatusFilter(value as ConversationStatusFilter)
              }
            />
            {failedConversationAccounts.length ? (
              <Alert
                className="conversation-sync-alert"
                type="warning"
                showIcon
                message={`${failedConversationAccounts.map(accountDisplayName).join("、")} 会话同步失败`}
              />
            ) : null}
          </div>
          <div ref={conversationListViewportRef} className="conversation-list-body">
            <Spin spinning={conversationsLoading}>
            {visibleConversations.length === 0 && !conversationsLoading ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={conversationEmptyDescription}
              />
            ) : conversationListHeight > 0 ? (
              <VirtualList
                className="conversation-virtual-list"
                data={visibleConversations}
                height={conversationListHeight}
                itemHeight={82}
                itemKey={conversationIdentity}
              >
                {(item) => {
                  const direction = conversationDirection(item);
                  const sourceAccount = conversationAccountMap.get(item.account_id);
                  const accountName = platformAccountName(sourceAccount);
                  const customerName = conversationTitle(item);
                  const unreadCount = conversationUnreadCount(item);
                  const isSelected = Boolean(
                    selectedConversation &&
                    conversationIdentity(selectedConversation) === conversationIdentity(item)
                  );
                  return (
                    <List.Item
                      className={isSelected ? "conversation-item active" : "conversation-item"}
                      role="button"
                      tabIndex={0}
                      aria-current={isSelected ? "true" : undefined}
                      onClick={() => void openConversation(item)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          void openConversation(item);
                        }
                      }}
                    >
                      <div className="conversation-item-layout">
                        <span className="conversation-customer-avatar-shell">
                          <Avatar
                            className="conversation-customer-avatar"
                            size={40}
                            src={!privacyMaskEnabled ? item.peer_avatar_url || undefined : undefined}
                          >
                            {privacyMaskEnabled ? <LockOutlined /> : customerName.slice(0, 1)}
                          </Avatar>
                          {unreadCount > 0 ? (
                            <span
                              className="conversation-unread-badge"
                              aria-label={`${unreadCount} 条未查看消息`}
                            >
                              {unreadCount > 99 ? "99+" : unreadCount}
                            </span>
                          ) : null}
                        </span>
                        <div className="conversation-item-content">
                          <div className="conversation-item-header">
                            <Tooltip title={`客户：${customerName}`}>
                              <Text className="conversation-customer-name" strong ellipsis>
                                {customerName}
                              </Text>
                            </Tooltip>
                          </div>
                          <div className="conversation-item-account">
                            {conversationAccountFilter === "all" ? (
                              <>
                                <Tag
                                  className="conversation-platform-tag"
                                  color={platformTagColor(item.platform)}
                                >
                                  {platformName(item.platform)}
                                </Tag>
                                <Tooltip title={`账户：${accountName}`}>
                                  <Text className="conversation-store-name" type="secondary" ellipsis>
                                    {accountName}
                                  </Text>
                                </Tooltip>
                              </>
                            ) : (
                              <Text className="conversation-store-name" type="secondary" ellipsis>
                                {formatCompactBeijingTime(
                                  item.last_activity_at || item.last_message_at
                                )}
                              </Text>
                            )}
                          </div>
                          <div className="conversation-preview">
                            <span className={`conversation-direction ${direction.className}`}>
                              {direction.label}
                            </span>
                            <Text type="secondary" ellipsis>
                              {privacyMaskEnabled
                                ? "消息内容已隐藏"
                                : item.last_activity_content ||
                                  item.last_message_content ||
                                  "暂无消息内容"}
                            </Text>
                          </div>
                        </div>
                        <div className="conversation-item-product" aria-label="会话商品图片">
                          <ShopOutlined />
                          {item.item_image_url && !privacyMaskEnabled ? (
                            <img
                              src={item.item_image_url}
                              alt={item.item_title || "会话商品"}
                              loading="lazy"
                              onError={(event) => {
                                event.currentTarget.style.display = "none";
                              }}
                            />
                          ) : null}
                        </div>
                      </div>
                    </List.Item>
                  );
                }}
              </VirtualList>
            ) : null}
            </Spin>
          </div>
        </div>

        <div className="chat-panel">
          {selectedConversation ? (
            <>
              <div className="mobile-conversation-header">
                <Button
                  type="text"
                  icon={<ArrowLeftOutlined />}
                  aria-label="返回会话列表"
                  onClick={() => setMobileConversationDetailOpen(false)}
                />
                <Text strong ellipsis>{conversationTitle(selectedConversation)}</Text>
              </div>
              <div className="chat-meta-inline">
                <div className="chat-meta-item">
                  <Text type="secondary">账户</Text>
                  <Tag color="gold">{platformName(selectedConversation.platform)}</Tag>
                  <Text strong ellipsis>
                    {platformAccountName(selectedAccount)}
                  </Text>
                  {selectedAccountOffline && conversationAccount ? (
                    <Tooltip title={`账户状态：${runtimeStateLabel(conversationAccount.runtime.state)}`}>
                      <Tag color="error">已离线</Tag>
                    </Tooltip>
                  ) : null}
                </div>
                <div className="chat-meta-item">
                  <Text type="secondary">客户</Text>
                  <Tooltip title={`接收方 ID：${privateId(selectedConversation.peer_user_id) || "未知"}`}>
                    <Tag color="cyan">{conversationTitle(selectedConversation)}</Tag>
                  </Tooltip>
                </div>
                <div className="chat-meta-item">
                  <Text type="secondary">会话 ID</Text>
                  <Text copyable={privacyMaskEnabled ? false : undefined}>
                    {privateId(selectedConversation.conversation_id)}
                  </Text>
                </div>
                <div className="chat-meta-item">
                  <Text type="secondary">消息数</Text>
                  <Text>{selectedConversation.message_count}</Text>
                </div>
              </div>
              <div className="chat-actions">
                {canMutate ? (
                  <Tooltip
                    title={
                      manualTakeoverMode === "temporary" && selectedConversation.manual_takeover_until
                        ? `接管截止：${formatTime(selectedConversation.manual_takeover_until)}`
                        : conversationAccount?.auto_reply_enabled
                          ? "当前会话允许进入自动回复链路"
                          : "当前账户 AI 回复开关未开启"
                    }
                  >
                    <Select
                      className="conversation-reply-mode"
                      size="small"
                      value={manualTakeoverMode}
                      loading={manualTakeoverUpdating}
                      disabled={manualTakeoverUpdating}
                      onChange={(value) => void updateManualTakeoverMode(value)}
                      options={[
                        {
                          value: "auto",
                          label: conversationAccount?.auto_reply_enabled
                            ? "自动回复"
                            : "自动回复（AI 未启用）"
                        },
                        { value: "temporary", label: "人工接管 30 分钟" },
                        { value: "permanent", label: "永久接管此聊天" }
                      ]}
                    />
                  </Tooltip>
                ) : (
                  <Tag color={manualTakeoverMode === "auto" ? "green" : "orange"}>
                    {manualTakeoverMode === "permanent"
                      ? "永久人工接管"
                      : manualTakeoverMode === "temporary"
                        ? "人工接管中"
                        : "自动回复"}
                  </Tag>
                )}
                <Button
                  size="small"
                  icon={<ShoppingCartOutlined />}
                  onClick={() => void openConversationOrderDrawer()}
                >
                  会话订单{conversationOrders.length ? ` (${conversationOrders.length})` : ""}
                </Button>
                <Tooltip
                  title={
                    platformBlacklist == null
                      ? "平台拉黑状态暂不可用"
                      : platformBlacklist
                        ? "已加入闲鱼平台黑名单"
                        : "未加入闲鱼平台黑名单"
                  }
                >
                  <span className="platform-blacklist-control">
                    <Text type={platformBlacklist == null ? "secondary" : undefined}>平台拉黑</Text>
                    <Switch
                      size="small"
                      checked={Boolean(platformBlacklist)}
                      loading={platformBlacklistLoading}
                      disabled={!canMutate || platformBlacklist == null}
                      onChange={confirmPlatformBlacklistChange}
                    />
                  </span>
                </Tooltip>
              </div>
              {selectedConversation.item_id ? (
                <div
                  className={`conversation-product-context${
                    selectedAccount?.remark ? " has-account-remark" : ""
                  }`}
                >
                  <div className="conversation-product-placeholder">
                    <ShopOutlined />
                    {selectedConversation.item_image_url && !privacyMaskEnabled ? (
                      <img
                        src={selectedConversation.item_image_url}
                        alt=""
                        onError={(event) => {
                          event.currentTarget.style.display = "none";
                        }}
                      />
                    ) : null}
                  </div>
                  <div className="conversation-product-details">
                    <Text
                      strong
                      ellipsis
                      title={privateName(selectedConversation.item_title) || undefined}
                    >
                      {privateName(selectedConversation.item_title) || "当前咨询商品"}
                    </Text>
                    <Space size={8} wrap>
                      {selectedConversation.item_price ? (
                        <Text className="conversation-product-price">
                          {formatItemPrice(selectedConversation.item_price)}
                        </Text>
                      ) : null}
                      {renderItemIdLink(
                        selectedConversation.item_id,
                        selectedConversation.item_url
                      )}
                    </Space>
                  </div>
                  {selectedAccount?.remark ? (
                    <Tooltip title={privateName(selectedAccount.remark)}>
                      <div className="conversation-account-remark">
                        <Text type="secondary">备注</Text>
                        <span className="conversation-account-remark-text">
                          {privateName(selectedAccount.remark)}
                        </span>
                      </div>
                    </Tooltip>
                  ) : null}
                </div>
              ) : selectedAccount?.remark ? (
                <Tooltip title={privateName(selectedAccount.remark)}>
                  <div className="conversation-account-remark standalone">
                    <Text type="secondary">备注</Text>
                    <span className="conversation-account-remark-text">
                      {privateName(selectedAccount.remark)}
                    </span>
                  </div>
                </Tooltip>
              ) : null}

              <div
                ref={messageListRef}
                className="message-list"
                onScroll={handleMessageScroll}
                onLoadCapture={handleMessageContentLoad}
              >
                {messageHasMore ? (
                  <Button
                    block
                    type="text"
                    icon={<HistoryOutlined />}
                    loading={olderMessagesLoading}
                    onClick={() => void loadOlderMessages()}
                  >
                    加载更早消息
                  </Button>
                ) : null}
                {chatMessagesLoading && chatMessages.length === 0 ? (
                  <Text type="secondary">消息加载中...</Text>
                ) : chatMessages.length === 0 ? (
                  <Empty description="暂无消息" />
                ) : (
                  chatMessages.map((chatMessage) =>
                    privacyMaskEnabled &&
                    (isFailedOutboundMessage(chatMessage) || chatMessage.message_type === "system") ? (
                      <div key={chatMessage.message_pk} className="message-row system-event">
                        <Text type="secondary">系统消息内容已隐藏</Text>
                      </div>
                    ) : isFailedOutboundMessage(chatMessage) ? (
                      <div key={chatMessage.message_pk} className="message-row system-event">
                        <FailedMessageNotice chatMessage={chatMessage} />
                      </div>
                    ) : chatMessage.message_type === "system" ? (
                      <div key={chatMessage.message_pk} className="message-row system-event">
                        <SystemMessageNotice chatMessage={chatMessage} />
                      </div>
                    ) : (
                      <div
                        key={chatMessage.message_pk}
                        className={`message-row ${chatMessage.direction}`}
                      >
                        {chatMessage.direction === "inbound" ? (
                          <Tooltip title={conversationTitle(selectedConversation)}>
                            <Avatar
                              className="message-avatar customer"
                              size={34}
                              src={!privacyMaskEnabled ? selectedConversation.peer_avatar_url || undefined : undefined}
                            >
                              {privacyMaskEnabled
                                ? <LockOutlined />
                                : conversationTitle(selectedConversation).slice(0, 1)}
                            </Avatar>
                          </Tooltip>
                        ) : null}
                        <div className="message-bubble">
                          <div className="message-meta">
                            <Text type="secondary">
                              {messageAuthor(chatMessage, selectedConversation, privacyMaskEnabled)}
                            </Text>
                            <Space size={4}>
                              <Text type="secondary">{formatTime(chatMessage.created_at)}</Text>
                              {canMutate && canRecallMessage(chatMessage) ? (
                                <Tooltip title="撤回消息">
                                  <Button
                                    type="text"
                                    size="small"
                                    icon={<RollbackOutlined />}
                                    loading={recallingMessagePk === chatMessage.message_pk}
                                    aria-label="撤回消息"
                                    onClick={() => void runRecallMessage(chatMessage)}
                                  />
                                </Tooltip>
                              ) : null}
                            </Space>
                          </div>
                          {renderChatMessageContent(chatMessage, privacyMaskEnabled)}
                          {chatMessage.recalled_at ? (
                            <div className="message-recall-state">
                              <Tag>已撤回</Tag>
                            </div>
                          ) : null}
                        </div>
                        {chatMessage.direction === "outbound" ? (
                          <Tooltip
                            title={
                              privateName(
                                conversationAccount?.platform_display_name ||
                                conversationAccount?.remark ||
                                conversationAccount?.display_name ||
                                "我"
                              )
                            }
                          >
                            <Avatar
                              className="message-avatar account"
                              size={34}
                              src={!privacyMaskEnabled ? conversationAccount?.platform_avatar_url || undefined : undefined}
                            >
                              {privacyMaskEnabled ? <LockOutlined /> : (
                                conversationAccount?.platform_display_name ||
                                conversationAccount?.remark ||
                                conversationAccount?.display_name ||
                                "我"
                              ).slice(0, 1)}
                            </Avatar>
                          </Tooltip>
                        ) : null}
                      </div>
                    )
                  )
                )}
              </div>

              {selectedAccountOffline ? (
                <Alert
                  type="warning"
                  showIcon
                  message="账户已离线，恢复连接后可发送消息"
                />
              ) : null}
              <Form form={sendForm} layout="vertical" className="send-form">
                <input
                  ref={imageInputRef}
                  className="image-file-input"
                  type="file"
                  hidden
                  multiple
                  accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
                  onChange={handleImageSelected}
                />
                <div className="message-composer">
                  {pendingImages.length ? (
                  <div className="pending-images" aria-label="待发送图片">
                    {pendingImages.map((pendingImage) => (
                      <Tooltip
                        key={pendingImage.clientRequestId}
                        title={pendingImage.error || privateName(pendingImage.file.name)}
                      >
                      <div
                        className={`pending-image pending-image-${pendingImage.status}`}
                      >
                        {privacyMaskEnabled ? (
                          <span className="pending-image-private"><EyeInvisibleOutlined /></span>
                        ) : (
                          <img src={pendingImage.previewUrl} alt="待发送图片" />
                        )}
                          <Button
                            className="pending-image-remove"
                            type="text"
                            size="small"
                            icon={<CloseOutlined />}
                            disabled={sending}
                            aria-label="移除待发送图片"
                            onClick={() => removePendingImage(pendingImage.clientRequestId)}
                          />
                      </div>
                      </Tooltip>
                    ))}
                  </div>
                ) : null}
                <Form.Item
                  name="text"
                  noStyle
                >
                  <Input.TextArea
                    className={`message-composer-input${privacyMaskEnabled ? " privacy-sensitive-textarea" : ""}`}
                    rows={3}
                    disabled={selectedAccountOffline}
                    placeholder="输入消息，可粘贴图片"
                    onPaste={handleComposerPaste}
                    onKeyDown={handleComposerKeyDown}
                  />
                </Form.Item>
                <div className="message-composer-toolbar">
                  <Space size={8}>
                    <Tooltip title="选择图片">
                      <Button
                        icon={<PictureOutlined />}
                        disabled={selectedAccountOffline || sending || !selectedConversation.peer_user_id || pendingImages.length >= 9}
                        aria-label="选择图片"
                        onClick={() => imageInputRef.current?.click()}
                      />
                    </Tooltip>
                    <Popover
                      open={quickPhrasePopoverOpen}
                      onOpenChange={setQuickPhrasePopoverOpen}
                      placement="topLeft"
                      trigger="click"
                      content={
                        <div className="quick-phrase-popover">
                          <Input.Search
                            allowClear
                            size="small"
                            value={quickPhraseSearch}
                            placeholder="搜索快捷短语"
                            onChange={(event) => setQuickPhraseSearch(event.target.value)}
                          />
                          <List
                            size="small"
                            dataSource={visibleQuickPhrases.slice(0, 20)}
                            locale={{ emptyText: "暂无快捷短语" }}
                            renderItem={(phrase) => (
                              <List.Item
                                className="quick-phrase-option"
                                role="button"
                                tabIndex={0}
                                onClick={() => void applyQuickPhrase(phrase)}
                                onKeyDown={(event) => {
                                  if (event.key === "Enter" || event.key === " ") {
                                    event.preventDefault();
                                    void applyQuickPhrase(phrase);
                                  }
                                }}
                              >
                                <List.Item.Meta
                                  title={
                                    <Space size={6}>
                                      <Text strong>{privateName(phrase.title)}</Text>
                                      <Tag>{privateName(phrase.group_name)}</Tag>
                                    </Space>
                                  }
                                  description={<Text ellipsis>{privateContent(phrase.content)}</Text>}
                                />
                              </List.Item>
                            )}
                          />
                          {canMutate ? (
                            <Button block type="text" icon={<EditOutlined />} onClick={startCreateQuickPhrase}>
                              管理快捷短语
                            </Button>
                          ) : null}
                        </div>
                      }
                    >
                      <Tooltip title="快捷短语">
                        <Button icon={<MessageOutlined />} aria-label="快捷短语" />
                      </Tooltip>
                    </Popover>
                  </Space>
                  {pendingImages.length ? (
                    <Tooltip title="清空图片">
                      <Button
                        type="text"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        disabled={sending}
                        aria-label="清空待发送图片"
                        onClick={clearPendingImages}
                      />
                    </Tooltip>
                  ) : null}
                  <div className="composer-toolbar-end">
                    {composerNotice ? (
                      <Text className="composer-notice" type="danger" aria-live="polite">
                        {composerNotice}
                      </Text>
                    ) : (
                      <Text className="composer-shortcut-hint" type="secondary">
                        Enter 发送 · Ctrl/Alt + Enter 换行
                      </Text>
                    )}
                    <Button
                      type="primary"
                      icon={<SendOutlined />}
                      loading={sending}
                      disabled={selectedAccountOffline || !selectedConversation.peer_user_id}
                      onClick={() => void submitComposer()}
                    >
                      发送
                    </Button>
                  </div>
                </div>
                </div>
              </Form>

            </>
          ) : (
            <Empty description="请选择左侧会话" />
          )}
        </div>
      </div>
    );
  }

  function renderQuickPhraseManager() {
    const needle = quickPhraseSearch.trim().toLowerCase();
    const items = quickPhrases.filter((phrase) =>
      !needle ||
      phrase.title.toLowerCase().includes(needle) ||
      phrase.content.toLowerCase().includes(needle) ||
      phrase.group_name.toLowerCase().includes(needle)
    );
    return (
      <Drawer
        title="快捷短语"
        width={compactLayout ? "100%" : 720}
        open={quickPhraseManagerOpen}
        onClose={() => setQuickPhraseManagerOpen(false)}
        extra={
          <Button icon={<PlusOutlined />} onClick={startCreateQuickPhrase}>
            新建
          </Button>
        }
      >
        <Form
          form={quickPhraseForm}
          layout="vertical"
          className="quick-phrase-form"
          initialValues={{ group_name: "默认", sort_order: 0 }}
        >
          <Form.Item
            name="title"
            label="标题"
            rules={[{ required: true, message: "请输入短语标题" }]}
          >
            <Input maxLength={80} />
          </Form.Item>
          <Form.Item
            name="group_name"
            label="分组"
            rules={[{ required: true, message: "请输入分组名称" }]}
          >
            <Input maxLength={80} />
          </Form.Item>
          <Form.Item name="sort_order" label="排序">
            <InputNumber className="full-width" min={-100000} max={100000} />
          </Form.Item>
          <Form.Item
            name="content"
            label="内容"
            className="quick-phrase-content-field"
            rules={[{ required: true, message: "请输入短语内容" }]}
          >
            <Input.TextArea rows={4} maxLength={2000} showCount />
          </Form.Item>
          <div className="quick-phrase-form-actions">
            {editingQuickPhrase ? (
              <Button
                onClick={() => {
                  setEditingQuickPhrase(null);
                  quickPhraseForm.setFieldsValue({
                    title: "",
                    content: "",
                    group_name: "默认",
                    sort_order: 0
                  });
                }}
              >
                取消编辑
              </Button>
            ) : null}
            <Button
              type="primary"
              icon={<SaveOutlined />}
              loading={quickPhraseSaving}
              onClick={() => void saveQuickPhrase()}
            >
              {editingQuickPhrase ? "保存修改" : "添加短语"}
            </Button>
          </div>
        </Form>
        <Input.Search
          allowClear
          value={quickPhraseSearch}
          placeholder="搜索标题、内容或分组"
          className="quick-phrase-manager-search"
          onChange={(event) => setQuickPhraseSearch(event.target.value)}
        />
        <List
          className="quick-phrase-manager-list"
          dataSource={items}
          locale={{ emptyText: "暂无快捷短语" }}
          renderItem={(phrase) => (
            <List.Item
              actions={[
                <Tooltip title="编辑" key="edit">
                  <Button
                    type="text"
                    icon={<EditOutlined />}
                    aria-label="编辑快捷短语"
                    onClick={() => startEditQuickPhrase(phrase)}
                  />
                </Tooltip>,
                <Tooltip title="删除" key="delete">
                  <Button
                    danger
                    type="text"
                    icon={<DeleteOutlined />}
                    aria-label="删除快捷短语"
                    onClick={() => confirmDeleteQuickPhrase(phrase)}
                  />
                </Tooltip>
              ]}
            >
              <List.Item.Meta
                title={
                  <Space size={6} wrap>
                    <Text strong>{privateName(phrase.title)}</Text>
                    <Tag>{privateName(phrase.group_name)}</Tag>
                    <Text type="secondary">排序 {phrase.sort_order}</Text>
                  </Space>
                }
                description={
                  <Space direction="vertical" size={2} className="quick-phrase-manager-description">
                    <Text>{privateContent(phrase.content)}</Text>
                    {phrase.last_used_at ? (
                      <Text type="secondary">最近使用：{formatTime(phrase.last_used_at)}</Text>
                    ) : null}
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      </Drawer>
    );
  }

  function renderConversationsPage() {
    return (
      <div className="conversation-page">
        {renderConversationWorkspace()}
        {renderOrderDrawer()}
        {renderQuickPhraseManager()}
      </div>
    );
  }

  function renderAutoReplyWorkspace() {
    return (
      <Space direction="vertical" size={16} className="content-stack">
        <Drawer
          title={editingRule ? `编辑规则：${editingRule.keyword}` : "新增规则"}
          width={compactLayout ? "100%" : 720}
          open={ruleDrawerOpen}
          onClose={() => {
            setRuleDrawerOpen(false);
            setEditingRule(null);
            ruleForm.resetFields();
          }}
        >
          <Form
            form={ruleForm}
            layout="vertical"
            initialValues={{
              enabled: true,
              group_name: "",
              keyword: "",
              trigger_type: "keyword",
              match_mode: "contains",
              case_sensitive: false,
              account_ids: [],
              platform: "xianyu",
              message_type: "text",
              sender_user_id: "",
              conversation_id: "",
              item_id: "",
              cooldown_seconds: 0,
              action_type: "template",
              reply_text: "",
              continue_matching: false,
              context_message_count: 10,
              context_fields: DEFAULT_AUTO_REPLY_CONTEXT_FIELDS,
              ai_system_prompt: "",
              ai_temperature: 0.4
            }}
          >
            <div className="auto-reply-rule-grid">
              <Form.Item name="enabled" label="启用规则" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Form.Item name="group_name" label="策略名称">
                <Input placeholder="例如：售前询价" />
              </Form.Item>
              <Form.Item name="trigger_type" label="触发方式">
                <Select
                  options={[
                    { label: "关键词命中", value: "keyword" },
                    { label: "全部消息", value: "always" },
                    { label: "其他规则未命中", value: "fallback" }
                  ]}
                />
              </Form.Item>
              {ruleTriggerType === "keyword" ? (
                <>
                  <Form.Item
                    name="keyword"
                    label="关键词"
                    rules={[{ required: true, message: "请输入关键词" }]}
                  >
                    <Input placeholder="例如：还在吗" />
                  </Form.Item>
                  <Form.Item name="match_mode" label="匹配方式">
                    <Select
                      options={[
                        { label: "包含关键词", value: "contains" },
                        { label: "完全等于", value: "exact" }
                      ]}
                    />
                  </Form.Item>
                  <Form.Item name="case_sensitive" label="大小写敏感" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </>
              ) : null}
              <Form.Item name="account_ids" label="适用账户">
                <Select
                  mode="multiple"
                  allowClear
                  placeholder="留空表示全部账户"
                  options={accounts.map((account) => ({
                    label: accountDisplayName(account),
                    value: account.account_id
                  }))}
                />
              </Form.Item>
              <Form.Item name="message_type" label="消息类型">
                <Select
                  allowClear
                  options={[
                    { label: "文本", value: "text" },
                    { label: "图片", value: "image" },
                    { label: "卡片", value: "card" },
                    { label: "系统消息", value: "system" }
                  ]}
                />
              </Form.Item>
              <Form.Item name="sender_user_id" label="限定发送方">
                <Input placeholder="可选：闲鱼用户 ID" />
              </Form.Item>
              <Form.Item name="conversation_id" label="限定会话">
                <Input placeholder="可选：conversation_id" />
              </Form.Item>
              <Form.Item name="item_id" label="限定商品">
                <Input placeholder="可选：item_id" />
              </Form.Item>
              <Form.Item name="cooldown_seconds" label="规则冷却秒数">
                <InputNumber className="full-width" min={0} max={86400} />
              </Form.Item>
              <Form.Item name="action_type" label="命中动作">
                <Select
                  options={[
                    { label: "模板回复", value: "template" },
                    { label: "AI 回复", value: "ai" },
                    { label: "跳过回复", value: "skip" }
                  ]}
                />
              </Form.Item>
              {ruleActionType === "template" ? (
                <>
                  <Form.Item
                    className="auto-reply-rule-wide"
                    name="reply_text"
                    label="模板回复内容"
                    rules={[{ required: true, message: "请输入模板回复内容" }]}
                  >
                    <Input.TextArea rows={4} placeholder="可插入 {{ sender.name }}、{{ item.title }} 等变量" />
                  </Form.Item>
                  <Form.Item name="continue_matching" label="继续匹配" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </>
              ) : null}
              {ruleActionType === "ai" ? (
                <>
                  <Form.Item name="context_message_count" label="上下文消息数">
                    <InputNumber className="full-width" min={1} max={50} />
                  </Form.Item>
                  <Form.Item name="ai_temperature" label="AI 随机度">
                    <InputNumber className="full-width" min={0} max={2} step={0.1} />
                  </Form.Item>
                  <Form.Item
                    className="auto-reply-rule-wide"
                    name="context_fields"
                    label="传入参数"
                  >
                    <Select
                      mode="multiple"
                      allowClear
                      optionFilterProp="label"
                      options={[...AUTO_REPLY_CONTEXT_OPTIONS]}
                    />
                  </Form.Item>
                  <Form.Item
                    className="auto-reply-rule-wide"
                    name="ai_system_prompt"
                    label="系统提示词"
                  >
                    <Input.TextArea rows={5} placeholder="定义客服身份、回复边界和表达方式" />
                  </Form.Item>
                </>
              ) : null}
            </div>
            <Space>
              <Button type="primary" loading={autoReplyLoading} onClick={() => void submitRule()}>
                {editingRule ? "保存规则" : "创建规则"}
              </Button>
              <Button onClick={() => setRuleDrawerOpen(false)}>取消</Button>
            </Space>
          </Form>
        </Drawer>

        <Drawer
          title="测试策略"
          width={compactLayout ? "100%" : 640}
          open={autoReplyPreviewOpen}
          onClose={() => setAutoReplyPreviewOpen(false)}
        >
          <Form
            form={autoReplyPreviewForm}
            layout="vertical"
            initialValues={{ message_type: "text", content: "请问商品还在吗" }}
          >
            <div className="auto-reply-rule-grid">
              <Form.Item
                name="account_id"
                label="平台账户"
                rules={[{ required: true, message: "请选择平台账户" }]}
              >
                <Select
                  options={accounts.map((account) => ({
                    label: accountDisplayName(account),
                    value: account.account_id
                  }))}
                />
              </Form.Item>
              <Form.Item name="message_type" label="消息类型">
                <Select
                  options={[
                    { label: "文本", value: "text" },
                    { label: "图片", value: "image" },
                    { label: "卡片", value: "card" },
                    { label: "系统消息", value: "system" },
                    { label: "未知类型", value: "unknown" }
                  ]}
                />
              </Form.Item>
              <Form.Item className="auto-reply-rule-wide" name="content" label="消息内容">
                <Input.TextArea rows={4} />
              </Form.Item>
              <Form.Item name="sender_user_id" label="发送方用户 ID">
                <Input allowClear />
              </Form.Item>
              <Form.Item name="conversation_id" label="会话 ID">
                <Input allowClear />
              </Form.Item>
              <Form.Item name="item_id" label="商品 ID">
                <Input allowClear />
              </Form.Item>
            </div>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              loading={autoReplyPreviewLoading}
              onClick={() => void runAutoReplyPreview()}
            >
              运行测试
            </Button>
          </Form>

          {autoReplyPreviewResult ? (
            <div className="auto-reply-preview-result">
              <Alert
                showIcon
                type={autoReplyPreviewResult.executable ? "success" : "warning"}
                message={autoReplyPreviewResult.reason}
                description={
                  autoReplyPreviewResult.action_type
                    ? `动作：${autoReplyPreviewResult.action_type === "ai" ? "AI 回复" : autoReplyPreviewResult.action_type === "skip" ? "跳过回复" : "模板回复"}`
                    : "未选择执行动作"
                }
              />
              <List
                size="small"
                header={<Text strong>系统闸门</Text>}
                dataSource={autoReplyPreviewResult.gates}
                renderItem={(gate) => (
                  <List.Item>
                    <Space>
                      <Tag color={gate.passed ? "green" : "red"}>{gate.passed ? "通过" : "阻止"}</Tag>
                      <Text>{gate.message}</Text>
                    </Space>
                  </List.Item>
                )}
              />
              <List
                size="small"
                header={<Text strong>匹配轨迹</Text>}
                dataSource={autoReplyPreviewResult.traces}
                locale={{ emptyText: "暂无规则" }}
                renderItem={(trace) => (
                  <List.Item>
                    <Space wrap>
                      <Tag color={trace.selected ? "blue" : trace.matched ? "green" : "default"}>
                        {trace.selected ? "执行" : trace.matched ? "命中" : "跳过"}
                      </Tag>
                      <Text strong={trace.selected}>{privateName(trace.name)}</Text>
                      <Text type="secondary">
                        {privacyMaskEnabled ? "匹配详情已隐藏" : trace.message}
                      </Text>
                    </Space>
                  </List.Item>
                )}
              />
              {autoReplyPreviewResult.reply_preview ? (
                <div className="auto-reply-preview-output">
                  <Text strong>回复预览</Text>
                  <pre>{privacyMaskEnabled ? "回复内容已隐藏" : autoReplyPreviewResult.reply_preview}</pre>
                </div>
              ) : null}
              {Object.keys(autoReplyPreviewResult.ai_context).length ? (
                <div className="auto-reply-preview-output">
                  <Text strong>AI 传入参数</Text>
                  <pre>{privacyMaskEnabled ? "AI 传入参数已隐藏" : JSON.stringify(autoReplyPreviewResult.ai_context, null, 2)}</pre>
                </div>
              ) : null}
            </div>
          ) : null}
        </Drawer>

        <Card
          size="small"
          title="策略顺序"
          extra={(
            <Space>
              <Button icon={<PlayCircleOutlined />} onClick={openAutoReplyPreview}>
                测试策略
              </Button>
              <Button type="primary" icon={<PlusOutlined />} onClick={startCreateRule}>
                新增策略
              </Button>
            </Space>
          )}
        >
          {autoReplyRuleIssues.map((issue) => (
            <Alert
              key={`${issue.code}:${issue.rule_ids.join(",")}`}
              className="auto-reply-rule-issue"
              showIcon
              type={issue.severity === "error" ? "error" : "warning"}
              message={issue.message}
            />
          ))}
          <DndContext
            sensors={autoReplyRuleSensors}
            collisionDetection={closestCenter}
            onDragEnd={(event) => void reorderAutoReplyRuleRows(event)}
          >
            <SortableContext
              items={autoReplyRules.map((rule) => rule.rule_id)}
              strategy={verticalListSortingStrategy}
            >
              <Table<AutoReplyRule>
                components={{ body: { row: SortableRuleRow } }}
                rowKey="rule_id"
                size="small"
                loading={autoReplyLoading || autoReplyReordering}
                dataSource={autoReplyRules}
                pagination={false}
                columns={[
                  {
                    title: "顺序",
                    width: 76,
                    render: (_, rule, index) => (
                      <Space size={2}>
                        <RuleDragHandle disabled={rule.trigger_type === "fallback"} />
                        <Text type="secondary">{index + 1}</Text>
                      </Space>
                    )
                  },
                  {
                    title: "状态",
                    dataIndex: "enabled",
                    width: 72,
                    render: (enabled: boolean, rule) => (
                      <Switch
                        size="small"
                        checked={enabled}
                        loading={autoReplyUpdatingRuleId === rule.rule_id}
                        aria-label={enabled ? "关闭策略" : "启用策略"}
                        onChange={(checked) => void toggleAutoReplyRuleEnabled(rule, checked)}
                      />
                    )
                  },
                  {
                    title: "策略名称",
                    dataIndex: "group_name",
                    width: 140,
                    ellipsis: true,
                    render: (value: string | null | undefined, rule) =>
                      privateName(value || rule.keyword) || (rule.trigger_type === "fallback" ? "兜底规则" : "全部消息")
                  },
                  {
                    title: "当",
                    width: 210,
                    ellipsis: true,
                    render: (_, rule) =>
                      rule.trigger_type === "keyword"
                        ? `消息${rule.match_mode === "exact" ? "等于" : "包含"}“${privateName(rule.keyword)}”`
                        : rule.trigger_type === "fallback"
                          ? "其他策略均未命中"
                          : "收到任意消息"
                  },
                  {
                    title: "范围",
                    width: 210,
                    render: (_, rule) => (
                      <Space size={[4, 4]} wrap>
                        <Tag>{rule.account_ids.length ? `${rule.account_ids.length} 个账户` : "全部账户"}</Tag>
                        {rule.message_type ? <Tag>{rule.message_type}</Tag> : null}
                        {rule.item_id ? <Tag>指定商品</Tag> : null}
                        {rule.conversation_id ? <Tag>指定会话</Tag> : null}
                      </Space>
                    )
                  },
                  {
                    title: "则",
                    dataIndex: "action_type",
                    width: 100,
                    render: (value: AutoReplyRule["action_type"]) => (
                      <Tag color={value === "ai" ? "blue" : value === "skip" ? "default" : "green"}>
                        {value === "ai" ? "AI 回复" : value === "skip" ? "跳过" : "模板回复"}
                      </Tag>
                    )
                  },
                  {
                    title: "内容",
                    ellipsis: true,
                    render: (_, rule) =>
                      rule.action_type === "ai"
                        ? privateContent(rule.ai_system_prompt) || "使用默认提示词"
                        : rule.action_type === "skip"
                          ? "不发送回复"
                          : privateContent(rule.reply_text) || "-"
                  },
                  {
                    title: "操作",
                    width: 96,
                    fixed: "right",
                    render: (_, rule) => (
                      <Space size={2}>
                        <Tooltip title="编辑">
                          <Button
                            type="text"
                            size="small"
                            icon={<EditOutlined />}
                            aria-label="编辑策略"
                            onClick={() => startEditRule(rule)}
                          />
                        </Tooltip>
                        <Tooltip title="删除">
                          <Button
                            danger
                            type="text"
                            size="small"
                            icon={<DeleteOutlined />}
                            aria-label="删除策略"
                            onClick={() => void removeRule(rule)}
                          />
                        </Tooltip>
                      </Space>
                    )
                  }
                ]}
                scroll={{ x: 1120 }}
              />
            </SortableContext>
          </DndContext>
        </Card>

        <Card size="small" title="命中日志">
          <Table
            rowKey="log_id"
            size="small"
            loading={autoReplyLoading}
            dataSource={autoReplyLogs}
            pagination={{ pageSize: 5 }}
            columns={[
              {
                title: "时间",
                dataIndex: "created_at",
                width: 170,
                render: (value: string) => formatTime(value)
              },
              {
                title: "结果",
                dataIndex: "success",
                width: 80,
                render: (success: boolean) =>
                  success ? <Tag color="green">成功</Tag> : <Tag color="red">失败</Tag>
              },
              { title: "会话", dataIndex: "conversation_id", width: 150, render: (value?: string | null) => privateId(value) || "-" },
              { title: "关键词", dataIndex: "matched_keyword", width: 130, render: (value?: string | null) => privateName(value) || "-" },
              { title: "回复", dataIndex: "reply_text", ellipsis: true, render: (value?: string | null) => privateContent(value) || "-" },
              {
                title: "错误",
                dataIndex: "error",
                ellipsis: true,
                render: (value?: string | null) =>
                  privacyMaskEnabled && value ? "错误详情已隐藏" : value || "-"
              }
            ]}
          />
        </Card>
      </Space>
    );
  }

  function renderAutoReplyPage() {
    return (
      <div className="auto-reply-page">
        <div className="workspace-page-header">
          <div>
            <Title level={4}>自动回复</Title>
            <Text type="secondary">规则按当前系统用户维护，账户开关在平台账户中独立控制</Text>
          </div>
        </div>
        {renderAutoReplyWorkspace()}
      </div>
    );
  }

  function renderEventsWorkspace() {
    return (
      <Table
        rowKey="event_id"
        size="small"
        loading={eventsLoading}
        dataSource={events}
        pagination={{ pageSize: 20 }}
        scroll={{ x: 680 }}
        locale={{ emptyText: "暂无运行日志" }}
        columns={[
          {
            title: "时间",
            dataIndex: "created_at",
            width: 180,
            render: (value: string) => formatTime(value)
          },
          {
            title: "级别",
            dataIndex: "level",
            width: 90,
            render: (level: RuntimeEvent["level"]) => {
              const color = level === "error" ? "red" : level === "warning" ? "orange" : "blue";
              return <Tag color={color}>{level}</Tag>;
            }
          },
          {
            title: "状态",
            dataIndex: "state",
            width: 110,
            render: (state: RuntimeState) => <StatusTag state={state} />
          },
          {
            title: "消息",
            dataIndex: "message",
            render: (value?: string | null) =>
              privacyMaskEnabled && value ? "运行详情已隐藏" : value || "-"
          }
        ]}
      />
    );
  }

  function renderDeliveryWorkspace() {
    return (
      <Space direction="vertical" size={16} className="content-stack">
        <Card size="small" title="订单发送配置">
          <Form
            form={deliveryAutomationForm}
            layout="vertical"
            initialValues={{
              enabled: false,
              mode: "manual_only",
              require_order_card: true,
              duplicate_guard_enabled: true,
              order_status_allowlist_text: "WAIT_SELLER_SEND_GOODS\n待发货\n待卖家发货"
            }}
          >
            <div className="delivery-automation-grid">
              <Form.Item name="enabled" label="启用自动发送" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Form.Item name="mode" label="模式">
                <Select
                  options={[
                    { label: "人工确认", value: "manual_only" },
                    { label: "自动发送文本", value: "ws_text" },
                    { label: "平台物流发货（未接入）", value: "platform_api" }
                  ]}
                />
              </Form.Item>
              <Form.Item name="require_order_card" label="必须关联卡片" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Form.Item name="duplicate_guard_enabled" label="防重复" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Form.Item name="order_status_allowlist_text" label="订单状态白名单">
                <Input.TextArea rows={3} placeholder="一行一个，例如 WAIT_SELLER_SEND_GOODS、待发货" />
              </Form.Item>
            </div>
            <Space>
              <Button type="primary" loading={deliveryLoading} onClick={() => void saveDeliveryAutomationSetting()}>
                保存发送配置
              </Button>
              <Text type="secondary">当前发送动作仅通过闲鱼会话发送内容，不会变更平台物流状态。</Text>
            </Space>
          </Form>
        </Card>

        {deliveryPreflight ? (
          <Alert
            type={deliveryPreflight.eligible ? "success" : "warning"}
            showIcon
            message={deliveryPreflight.eligible ? "自动发货预检通过" : "自动发货预检未通过"}
            description={
              deliveryPreflight.reasons.length > 0
                ? deliveryPreflight.reasons.join("；")
                : `模式：${deliveryPreflight.mode}`
            }
          />
        ) : null}

        <Card
          size="small"
          title={editingDeliveryTemplate ? `编辑模板：${privateName(editingDeliveryTemplate.name)}` : "发货模板"}
          extra={<Button onClick={startCreateDeliveryTemplate}>新建模板</Button>}
        >
          <Form
            form={deliveryTemplateForm}
            layout="vertical"
            initialValues={{
              enabled: true,
              priority: 100,
              content: "您好，您购买的资料如下：\n\n{item_id}\n\n请及时保存。"
            }}
          >
            <div className="delivery-template-grid">
              <Form.Item
                name="name"
                label="模板名称"
                rules={[{ required: true, message: "请输入模板名称" }]}
              >
                <Input placeholder="例如：虚拟资料发货" />
              </Form.Item>
              <Form.Item name="enabled" label="启用" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Form.Item name="priority" label="优先级">
                <InputNumber className="full-width" min={0} max={100000} />
              </Form.Item>
              <Form.Item
                name="content"
                label="发货内容"
                rules={[{ required: true, message: "请输入发货内容" }]}
              >
                <Input.TextArea
                  rows={4}
                  placeholder="支持 {receiver_user_id}、{conversation_id}、{item_id}、{peer_name}"
                />
              </Form.Item>
            </div>
            <Space>
              <Button type="primary" loading={deliveryLoading} onClick={() => void submitDeliveryTemplate()}>
                {editingDeliveryTemplate ? "保存模板" : "创建模板"}
              </Button>
              {editingDeliveryTemplate ? <Button onClick={startCreateDeliveryTemplate}>取消编辑</Button> : null}
            </Space>
          </Form>
        </Card>

        <Card size="small" title="模板列表">
          <Table
            rowKey="template_id"
            size="small"
            loading={deliveryLoading}
            dataSource={deliveryTemplates}
            pagination={{ pageSize: 5 }}
            columns={[
              {
                title: "状态",
                dataIndex: "enabled",
                width: 80,
                render: (enabled: boolean) =>
                  enabled ? <Tag color="green">启用</Tag> : <Tag color="default">关闭</Tag>
              },
              { title: "名称", dataIndex: "name", width: 180, render: (value?: string | null) => privateName(value) || "-" },
              { title: "优先级", dataIndex: "priority", width: 90 },
              { title: "内容", dataIndex: "content", ellipsis: true, render: (value?: string | null) => privateContent(value) || "-" },
              {
                title: "操作",
                width: 150,
                render: (_, template) => (
                  <Space>
                    <Button size="small" onClick={() => startEditDeliveryTemplate(template)}>
                      编辑
                    </Button>
                    <Button danger size="small" onClick={() => void removeDeliveryTemplate(template)}>
                      删除
                    </Button>
                  </Space>
                )
              }
            ]}
          />
        </Card>

        <Card size="small" title="发货记录">
          <Table
            rowKey="record_id"
            size="small"
            loading={deliveryLoading}
            dataSource={deliveryRecords}
            pagination={{ pageSize: 8 }}
            columns={[
              {
                title: "时间",
                dataIndex: "created_at",
                width: 170,
                render: (value: string) => formatTime(value)
              },
              {
                title: "状态",
                dataIndex: "status",
                width: 90,
                render: (status: DeliveryRecord["status"]) => {
                  const statusMeta: Record<DeliveryRecord["status"], { color: string; label: string }> = {
                    pending: { color: "blue", label: "待发送" },
                    sending: { color: "processing", label: "发送中" },
                    sent: { color: "green", label: "已发送" },
                    failed: { color: "red", label: "发送失败" },
                    uncertain: { color: "orange", label: "结果待核验" },
                    cancelled: { color: "default", label: "已取消" }
                  };
                  const meta = statusMeta[status];
                  return <Tag color={meta.color}>{meta.label}</Tag>;
                }
              },
              { title: "会话", dataIndex: "conversation_id", width: 150, render: (value?: string | null) => privateId(value) || "-" },
              { title: "接收方", dataIndex: "receiver_user_id", width: 150, render: (value?: string | null) => privateId(value) || "-" },
              {
                title: "订单",
                dataIndex: "order_id",
                width: 150,
                render: (value?: string | null) => value ? (
                  <Text copyable={privacyMaskEnabled ? false : undefined}>{privateId(value)}</Text>
                ) : "-"
              },
              {
                title: "商品",
                dataIndex: "item_id",
                width: 140,
                render: (value?: string | null) => value ? (
                  <Text copyable={privacyMaskEnabled ? false : undefined}>{privateId(value)}</Text>
                ) : "-"
              },
              { title: "内容", dataIndex: "content", ellipsis: true, render: (value?: string | null) => privateContent(value) || "-" },
              { title: "错误", dataIndex: "send_error", ellipsis: true, render: (value?: string | null) => privacyMaskEnabled && value ? "错误详情已隐藏" : value || "-" },
              {
                title: "操作",
                width: 210,
                render: (_, record) =>
                  record.status === "pending" || record.status === "failed" ? (
                    <Space>
                      <Button size="small" onClick={() => void runDeliveryPreflight(record)}>
                        预检
                      </Button>
                      <Button size="small" onClick={() => void sendPreparedDelivery(record)}>
                        发送
                      </Button>
                      <Button size="small" onClick={() => void enqueuePreparedDelivery(record)}>
                        入队
                      </Button>
                    </Space>
                  ) : null
              }
            ]}
          />
        </Card>
      </Space>
    );
  }

  function renderDeliveryPage() {
    const isBought = orderScope === "bought";
    const scopeLabel = isBought ? "买入" : "已售";
    const latestRun = orderSyncRuns[0];
    const allOrderCount = orderManagerAccounts.reduce((total, account) => total + account.total_count, 0);
    const runStatusMeta: Record<OrderSyncRun["status"], { label: string; color: string }> = {
      pending: { label: "排队中", color: "blue" },
      running: { label: "同步中", color: "processing" },
      success: { label: "成功", color: "green" },
      failed: { label: "失败", color: "red" },
      cancelled: { label: "已取消", color: "default" }
    };
    return (
      <>
        <div className="order-management-shell">
          <aside className="order-account-pane">
            <div className="order-account-pane-heading">
              <Text strong>闲鱼账户</Text>
              <Text type="secondary">{orderManagerAccounts.length}</Text>
            </div>
            <div className="order-account-list">
              <div
                role="button"
                tabIndex={0}
                className={`order-account-row${orderAccountFilter === "all" ? " active" : ""}`}
                onClick={() => void selectOrderManagerAccount("all")}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    void selectOrderManagerAccount("all");
                  }
                }}
              >
                <span className="order-account-main">
                  <Text strong>全部账户</Text>
                  <Text type="secondary">{scopeLabel} {allOrderCount}</Text>
                </span>
              </div>
              {orderManagerAccounts.map((account) => (
                <div
                  role="button"
                  tabIndex={0}
                  key={account.account_id}
                  className={`order-account-row${account.account_id === orderAccountFilter ? " active" : ""}`}
                  onClick={() => void selectOrderManagerAccount(account.account_id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      void selectOrderManagerAccount(account.account_id);
                    }
                  }}
                >
                  <span className="order-account-main">
                    <Text strong ellipsis title={accountDisplayName(account)}>{accountDisplayName(account)}</Text>
                    <span className="order-account-meta">
                      <StatusTag state={account.runtime_state} />
                      <Text type="secondary">{scopeLabel} {account.total_count}</Text>
                      {account.pending_count > 0 ? (
                        <Tag color="blue">{isBought ? "待卖家发" : "待发"} {account.pending_count}</Tag>
                      ) : null}
                    </span>
                  </span>
                  <Tooltip title={isBought ? "同步平台买入订单" : "同步平台已售订单"}>
                    <Button
                      type="text"
                      size="small"
                      icon={<SyncOutlined spin={orderManagerAction === `sync:${account.account_id}`} />}
                      disabled={Boolean(orderManagerAction) || !account.enabled}
                      aria-label={`同步 ${accountDisplayName(account)} 的${isBought ? "买入" : "已售"}订单`}
                      onClick={(event) => {
                        event.stopPropagation();
                        void runOrderSync(account.account_id);
                      }}
                    />
                  </Tooltip>
                </div>
              ))}
              {!orderManagerAccounts.length && !orderLoading ? (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无闲鱼账户" />
              ) : null}
            </div>
          </aside>

          <section className="order-catalog-pane">
            <div className="order-catalog-heading">
              <div className="order-catalog-title">
                <Space size={10} wrap>
                  <Segmented
                    size="small"
                    value={orderScope}
                    options={[
                      { label: "我买到的", value: "bought" },
                      { label: "我卖出的", value: "sold" }
                    ]}
                    onChange={(value) => void selectOrderScope(value as OrderScope)}
                  />
                  <Text strong>{selectedOrderManagerAccount ? accountDisplayName(selectedOrderManagerAccount) : "全部账户"}</Text>
                </Space>
                <Text type="secondary">
                  {selectedOrderManagerAccount?.setting.last_sync_at
                    ? `上次同步 ${formatTime(selectedOrderManagerAccount.setting.last_sync_at)}`
                    : selectedOrderManagerAccount
                      ? `尚未同步平台${isBought ? "买入" : "已售"}订单`
                      : `共 ${orders.length} 笔${isBought ? "买入" : "已售"}订单`}
                </Text>
              </div>
              {selectedOrderManagerAccount ? (
                <Space size={8}>
                  <Button type="text" icon={<HistoryOutlined />} onClick={() => setOrderHistoryOpen(true)}>
                    {latestRun ? runStatusMeta[latestRun.status].label : "同步记录"}
                  </Button>
                  <Tooltip title="同步与交付设置">
                    <Button icon={<SettingOutlined />} aria-label="订单同步与交付设置" onClick={openOrderSettings} />
                  </Tooltip>
                </Space>
              ) : null}
            </div>

            {selectedOrderManagerAccount?.setting.last_sync_status === "failed" ? (
              <Alert
                type="error"
                showIcon
                message="最近一次订单同步失败"
                description={selectedOrderManagerAccount.setting.last_sync_error || "未返回具体错误"}
              />
            ) : null}

            <div className="order-catalog-toolbar">
              <Input.Search
                allowClear
                value={orderKeyword}
                className="order-catalog-search"
                placeholder={`搜索商品、订单号或${isBought ? "卖家" : "买家"}`}
                onChange={(event) => {
                  const value = event.target.value;
                  setOrderKeyword(value);
                  if (!value) void loadOrderData(orderAccountFilter, orderStatusFilter, "");
                }}
                onSearch={(value) => void loadOrderData(orderAccountFilter, orderStatusFilter, value)}
              />
              <Select
                value={orderStatusFilter}
                className="order-catalog-status"
                options={[
                  { label: "全部状态", value: "all" },
                  { label: "待付款", value: "pending_payment" },
                  ...(isBought
                    ? [{ label: "待卖家发货", value: "waiting_seller_delivery" }]
                    : [{ label: "待发货", value: "paid_waiting_delivery" }]),
                  { label: isBought ? "待收货" : "已发货", value: "shipped" },
                  { label: "已完成", value: "completed" },
                  { label: "退款中", value: "refunding" },
                  { label: "已退款", value: "refunded" },
                  { label: "已关闭", value: "closed" }
                ]}
                onChange={(value) => {
                  setOrderStatusFilter(value);
                  void loadOrderData(orderAccountFilter, value, orderKeyword);
                }}
              />
            </div>

            <div className="order-catalog-table">
              <Table<XianyuOrder>
                rowKey="order_pk"
                size="small"
                loading={orderLoading}
                dataSource={orders}
                pagination={{ pageSize: 30, showSizeChanger: false }}
                scroll={{ x: 1080 }}
                locale={{ emptyText: `暂无已同步的${isBought ? "买入" : "卖家已售"}订单` }}
                columns={[
                  {
                    title: "商品",
                    dataIndex: "title",
                    width: 330,
                    render: (_, order) => (
                      <div className="managed-product-cell">
                        {order.image_url && !privacyMaskEnabled ? (
                          <img src={order.image_url} alt="" loading="lazy" />
                        ) : (
                          <div className="managed-product-cover-empty"><PictureOutlined /></div>
                        )}
                        <div className="managed-product-copy">
                          <Text ellipsis title={privateName(order.title) || "闲鱼订单"}>
                            {privateName(order.title) || "闲鱼订单"}
                          </Text>
                          <Text type="secondary">{privateId(order.item_id) || "无商品 ID"}</Text>
                        </div>
                      </div>
                    )
                  },
                  ...(orderAccountFilter === "all" ? [{
                    title: "账户",
                    dataIndex: "account_name" as const,
                    width: 130,
                    render: (_value: string | null, order: XianyuOrder) =>
                      accountDisplayName(accounts.find(account => account.account_id === order.account_id))
                  }] : []),
                  { title: "状态", dataIndex: "status", width: 100, render: renderOrderStatus },
                  {
                    title: isBought ? "卖家" : "买家",
                    dataIndex: isBought ? "peer_name" : "buyer_name",
                    width: 130,
                    ellipsis: true,
                    render: (value: string | null, order) =>
                      privateName(value || order.peer_name) ||
                      privateId(isBought ? order.peer_user_id : order.buyer_user_id) ||
                      "-"
                  },
                  {
                    title: "金额 / 数量",
                    dataIndex: "price",
                    width: 120,
                    render: (value: string | null, order) => `${value || "-"} × ${order.quantity || 1}`
                  },
                  {
                    title: "订单号",
                    dataIndex: "platform_order_id",
                    width: 190,
                    render: (value?: string | null) => value ? (
                      <Text copyable={privacyMaskEnabled ? false : undefined}>{privateId(value)}</Text>
                    ) : "-"
                  },
                  {
                    title: "订单时间",
                    dataIndex: "platform_created_at",
                    width: 170,
                    render: (_: string | null, order) => formatTime(
                      order.platform_paid_at || order.platform_created_at || order.last_event_at || order.created_at
                    )
                  },
                  {
                    title: "操作",
                    fixed: "right",
                    width: 72,
                    render: (_, order) => (
                      <Tooltip title="查看订单">
                        <Button type="text" icon={<ShoppingCartOutlined />} aria-label="查看订单" onClick={() => void openOrderDetails(order)} />
                      </Tooltip>
                    )
                  }
                ]}
              />
            </div>
          </section>
        </div>

        <Drawer
          title={`${selectedOrderManagerAccount ? accountDisplayName(selectedOrderManagerAccount) : "账户"} · ${isBought ? "买入" : "已售"}订单设置`}
          width={compactLayout ? "100%" : 960}
          open={orderSettingsOpen}
          onClose={() => setOrderSettingsOpen(false)}
        >
          <Tabs
            items={[
              {
                key: "sync",
                label: "订单同步",
                children: (
                  <Form form={orderSyncSettingForm} layout="vertical" className="order-setting-form">
                    <Form.Item name="sync_enabled" label="定时同步" valuePropName="checked">
                      <Switch />
                    </Form.Item>
                    {!isBought ? (
                      <Form.Item name="pending_interval_seconds" label="待发货同步间隔（秒）">
                        <InputNumber className="full-width" min={60} max={3600} />
                      </Form.Item>
                    ) : null}
                    <Form.Item name="full_interval_minutes" label="全量同步间隔（分钟）">
                      <InputNumber className="full-width" min={10} max={1440} />
                    </Form.Item>
                    <Form.Item name="jitter_seconds" label="随机延迟（秒）">
                      <InputNumber className="full-width" min={0} max={600} />
                    </Form.Item>
                    <Space>
                      <Button type="primary" loading={orderManagerAction === "settings"} onClick={() => void saveOrderSettings()}>
                        保存同步设置
                      </Button>
                      {!isBought ? (
                        <Button
                          icon={<SyncOutlined />}
                          disabled={Boolean(orderManagerAction) || !selectedOrderManagerAccount}
                          onClick={() => selectedOrderManagerAccount && void runOrderSync(selectedOrderManagerAccount.account_id, "pending")}
                        >
                          同步待发货
                        </Button>
                      ) : null}
                    </Space>
                  </Form>
                )
              },
              ...(!isBought ? [{
                key: "delivery",
                label: "交付配置",
                children: deliveryAccount ? renderDeliveryWorkspace() : <Empty description="请选择具体账户" />
              }] : [])
            ]}
          />
        </Drawer>

        <Drawer
          title={`${selectedOrderManagerAccount ? accountDisplayName(selectedOrderManagerAccount) : "账户"} · 同步记录`}
          width={compactLayout ? "100%" : 820}
          open={orderHistoryOpen}
          onClose={() => setOrderHistoryOpen(false)}
        >
          <Table<OrderSyncRun>
            rowKey="run_id"
            size="small"
            dataSource={orderSyncRuns}
            pagination={{ pageSize: 15, showSizeChanger: false }}
            locale={{ emptyText: "暂无同步记录" }}
            columns={[
              { title: "提交时间", dataIndex: "created_at", width: 170, render: formatTime },
              { title: "范围", dataIndex: "mode", width: 90, render: (mode) => mode === "full" ? "全部" : "待发货" },
              { title: "来源", dataIndex: "trigger", width: 90, render: (trigger) => trigger === "scheduled" ? "定时" : "手动" },
              {
                title: "状态",
                dataIndex: "status",
                width: 90,
                render: (status: OrderSyncRun["status"]) => <Tag color={runStatusMeta[status].color}>{runStatusMeta[status].label}</Tag>
              },
              { title: "订单数", dataIndex: "total_count", width: 80 },
              { title: "新增", dataIndex: "inserted_count", width: 70 },
              { title: "更新", dataIndex: "updated_count", width: 70 },
              { title: "错误", dataIndex: "error", ellipsis: true }
            ]}
          />
        </Drawer>
        {renderOrderDrawer()}
      </>
    );
  }

  function renderProductManagementPage() {
    const statusMeta: Record<ProductPlatformStatus, { label: string; color: string }> = {
      selling: { label: "在售", color: "green" },
      offline: { label: "已下架", color: "default" },
      deleted: { label: "已删除", color: "red" },
      not_selling: { label: "未在售", color: "orange" },
      unknown: { label: "待确认", color: "blue" }
    };
    const operationLabels: Record<ProductOperationRun["operation"], string> = {
      sync: "同步",
      polish: "擦亮",
      offline: "下架",
      delete: "永久删除"
    };
    const runStatusMeta: Record<ProductOperationRun["status"], { label: string; color: string }> = {
      pending: { label: "排队中", color: "blue" },
      running: { label: "执行中", color: "processing" },
      success: { label: "成功", color: "green" },
      partial_success: { label: "部分成功", color: "orange" },
      failed: { label: "失败", color: "red" },
      verification_required: { label: "待核验", color: "volcano" }
    };
    const publishStatusMeta: Record<ProductPublishTask["status"], { label: string; color: string }> = {
      pending: { label: "排队中", color: "blue" },
      running: { label: "发布中", color: "processing" },
      success: { label: "等待同步", color: "cyan" },
      verification_required: { label: "待核验", color: "orange" },
      failed: { label: "发布失败", color: "red" },
      cancelled: { label: "已取消", color: "default" }
    };
    const publishPhaseLabels: Record<string, string> = {
      pending: "等待执行",
      starting: "发布预检",
      resolving_location: "解析所在地",
      resolving_category: "识别类目",
      publishing: "提交平台",
      verifying: "核验商品",
      completed: "等待同步",
      verification_required: "等待核验",
      failed: "执行失败"
    };
    const latestRun = productOperationRuns[0];
    const selectedSellingIds = productManagerSelection.filter(
      (itemId) => managedProducts.find((item) => item.item_id === itemId)?.platform_status === "selling"
    );

    return (
      <div className="product-management-shell">
        <aside className="product-account-pane">
          <div className="product-account-pane-heading">
            <Text strong>闲鱼账户</Text>
            <Text type="secondary">{productManagerAccounts.length}</Text>
          </div>
          <div className="product-account-list">
            {productManagerAccounts.map((account) => (
              <div
                role="button"
                tabIndex={0}
                key={account.account_id}
                className={`product-account-row${account.account_id === productManagerAccountId ? " active" : ""}`}
                onClick={() => void selectProductManagerAccount(account.account_id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    void selectProductManagerAccount(account.account_id);
                  }
                }}
              >
                <span className="product-account-main">
                  <Text strong ellipsis title={accountDisplayName(account)}>{accountDisplayName(account)}</Text>
                  <span className="product-account-meta">
                    <StatusTag state={account.runtime_state} />
                    <Text type="secondary">在售 {account.selling_count}</Text>
                  </span>
                </span>
                <Tooltip title="同步平台商品">
                  <Button
                    type="text"
                    size="small"
                    icon={<SyncOutlined spin={productManagerAction === `sync:${account.account_id}`} />}
                    disabled={Boolean(productManagerAction) || !account.enabled}
                    aria-label={`同步 ${accountDisplayName(account)} 的平台商品`}
                    onClick={(event) => {
                      event.stopPropagation();
                      void runProductManagerSync(account.account_id);
                    }}
                  />
                </Tooltip>
              </div>
            ))}
            {!productManagerAccounts.length && !productManagerLoading ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无闲鱼账户" />
            ) : null}
          </div>
        </aside>

        <section className="product-catalog-pane">
          {selectedProductManagerAccount ? (
            <>
              <div className="product-catalog-heading">
                <div className="product-catalog-title">
                  <Text strong>{accountDisplayName(selectedProductManagerAccount)}</Text>
                  <Text type="secondary">
                    {selectedProductManagerAccount.setting.last_sync_at
                      ? `上次同步 ${formatTime(selectedProductManagerAccount.setting.last_sync_at)}`
                      : "尚未同步"}
                  </Text>
                </div>
                <Space size={8}>
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    disabled={!selectedProductManagerAccount.enabled}
                    onClick={() => void openProductPublishDrawer()}
                  >
                    发布商品
                  </Button>
                  {latestRun ? (
                    <Button type="text" onClick={() => setProductManagerHistoryOpen(true)}>
                      {operationLabels[latestRun.operation]}
                      <Tag color={runStatusMeta[latestRun.status].color} className="product-run-tag">
                        {runStatusMeta[latestRun.status].label}
                      </Tag>
                    </Button>
                  ) : (
                    <Button type="text" onClick={() => setProductManagerHistoryOpen(true)}>任务记录</Button>
                  )}
                  <Tooltip title="同步与自动擦亮设置">
                    <Button
                      icon={<SettingOutlined />}
                      aria-label="商品同步与自动擦亮设置"
                      onClick={openProductManagerSettings}
                    />
                  </Tooltip>
                </Space>
              </div>

              {selectedProductManagerAccount.setting.last_sync_status === "failed" ? (
                <Alert
                  type="error"
                  showIcon
                  message="最近一次商品同步失败"
                  description={selectedProductManagerAccount.setting.last_sync_error || "未返回具体错误"}
                />
              ) : latestRun?.status === "verification_required" ? (
                <Alert
                  type="warning"
                  showIcon
                  message="最近一次商品操作需要核验"
                  description={latestRun.error || "请先同步平台商品状态，确认结果后再继续操作。"}
                />
              ) : null}

              <div className="product-catalog-toolbar">
                <Space wrap size={8}>
                  <Input.Search
                    allowClear
                    value={productManagerKeyword}
                    className="product-catalog-search"
                    placeholder="搜索标题或商品 ID"
                    onChange={(event) => setProductManagerKeyword(event.target.value)}
                  />
                  <Select
                    value={productManagerStatus}
                    className="product-catalog-status"
                    options={[
                      { label: "全部", value: "all" },
                      { label: "发布中", value: "publishing" },
                      { label: "发布异常", value: "publish_failed" },
                      { label: "在售", value: "selling" },
                      { label: "已下架", value: "offline" },
                      { label: "未在售", value: "not_selling" },
                      { label: "已删除", value: "deleted" },
                      { label: "待确认", value: "unknown" }
                    ]}
                    onChange={(value) => setProductManagerStatus(value as ProductManagerStatusFilter)}
                  />
                </Space>
                <Space wrap size={8}>
                  <Button
                    icon={<SyncOutlined />}
                    loading={productManagerAction === "polish"}
                    disabled={!selectedSellingIds.length || Boolean(productManagerAction)}
                    onClick={() => void runManagedProductAction("polish", selectedSellingIds)}
                  >
                    擦亮选中
                  </Button>
                  <Button
                    icon={<StopOutlined />}
                    loading={productManagerAction === "offline"}
                    disabled={!selectedSellingIds.length || Boolean(productManagerAction)}
                    onClick={() => void runManagedProductAction("offline", selectedSellingIds)}
                  >
                    下架选中
                  </Button>
                  <Button
                    danger
                    icon={<DeleteOutlined />}
                    loading={productManagerAction === "delete"}
                    disabled={!productManagerSelection.length || Boolean(productManagerAction)}
                    onClick={() => confirmDeleteManagedProducts(productManagerSelection)}
                  >
                    永久删除
                  </Button>
                </Space>
              </div>

              <div className="product-catalog-table">
                <Table<ProductCatalogEntry>
                  rowKey="key"
                  size="small"
                  loading={productManagerLoading}
                  dataSource={visibleProductCatalog}
                  pagination={{ pageSize: 30, showSizeChanger: false }}
                  scroll={{ x: 1010 }}
                  rowSelection={{
                    selectedRowKeys: productManagerSelection.map((itemId) => `item:${itemId}`),
                    onChange: (keys) => setProductManagerSelection(
                      keys.map(String).filter((key) => key.startsWith("item:")).map((key) => key.slice(5))
                    ),
                    getCheckboxProps: (entry) => ({
                      disabled: entry.kind === "publish_task" || entry.item?.platform_status === "deleted"
                    })
                  }}
                  locale={{ emptyText: "暂无商品或发布任务" }}
                  columns={[
                    {
                      title: "商品",
                      dataIndex: "title",
                      width: 300,
                      render: (_, entry) => (
                        <div className="managed-product-cell">
                          {entry.coverUrl && !privacyMaskEnabled ? (
                            <img src={entry.coverUrl} alt="" loading="lazy" />
                          ) : (
                            <div className="managed-product-cover-empty"><PictureOutlined /></div>
                          )}
                          <div className="managed-product-copy">
                            <Space size={6}>
                              {entry.kind === "publish_task" ? <Tag>发布任务</Tag> : null}
                              <Text ellipsis title={privateName(entry.title)}>
                                {privateName(entry.title) || "未命名商品"}
                              </Text>
                            </Space>
                            {entry.item ? (
                              renderItemIdLink(entry.item.item_id, entry.item.detail_url)
                            ) : (
                              <Text type="secondary">第 {entry.task?.attempt_no || 1} 次 · {formatTime(entry.task?.created_at)}</Text>
                            )}
                          </div>
                        </div>
                      )
                    },
                    { title: "价格", dataIndex: "price", width: 90, render: (value) => value || "-" },
                    {
                      title: "状态",
                      width: 180,
                      render: (_, entry) => {
                        if (entry.task) {
                          const meta = publishStatusMeta[entry.task.status];
                          const phase = entry.task.phase.startsWith("uploading_image:")
                            ? `上传图片 ${entry.task.phase.split(":")[1]}`
                            : publishPhaseLabels[entry.task.phase] || entry.task.phase;
                          return <Space size={4}><Tag color={meta.color}>{meta.label}</Tag><Text type="secondary">{phase}</Text></Space>;
                        }
                        const item = entry.item!;
                        const meta = statusMeta[item.platform_status];
                        return (
                          <Space size={[4, 4]} wrap>
                            <Tag color={meta.color}>{meta.label}</Tag>
                            {item.want_text ? (
                              <Tooltip title={`平台最近同步数据 · ${formatTime(item.last_synced_at)}`}>
                                <Tag>{item.want_text}</Tag>
                              </Tooltip>
                            ) : null}
                            {item.sync_state === "pending_confirmation" ? (
                              <Tooltip title="需下一次全量同步确认"><QuestionCircleOutlined /></Tooltip>
                            ) : null}
                          </Space>
                        );
                      }
                    },
                    {
                      title: "发布时间",
                      width: 145,
                      render: (_, entry) => {
                        const value = entry.task
                          ? (["success", "verification_required"].includes(entry.task.status) && entry.task.item_id
                            ? entry.task.finished_at
                            : null)
                          : entry.item?.published_at;
                        if (!value) return <Text type="secondary">未知</Text>;
                        const source = entry.task || entry.item?.published_at_source === "publish_task"
                          ? "系统发布记录"
                          : entry.item?.published_at_source === "platform"
                            ? "平台时间"
                            : "时间来源未知";
                        return <Tooltip title={source}>{formatTime(value)}</Tooltip>;
                      }
                    },
                    {
                      title: "结果",
                      width: 150,
                      ellipsis: true,
                      render: (_, entry) => entry.task ? (
                        entry.task.item_url && !privacyMaskEnabled ? (
                          <a href={entry.task.item_url} target="_blank" rel="noreferrer">
                            {entry.task.item_id || "查看商品"}
                          </a>
                        ) : entry.task.item_id ? (
                          <Text>{privateId(entry.task.item_id)}</Text>
                        ) : (
                          <Text type={entry.task.error ? "danger" : "secondary"}>
                            {privacyMaskEnabled && entry.task.error ? "错误详情已隐藏" : entry.task.error || "-"}
                          </Text>
                        )
                      ) : entry.item?.last_polished_at ? `擦亮 ${formatTime(entry.item.last_polished_at)}` : "-"
                    },
                    {
                      title: "操作",
                      fixed: "right",
                      width: 112,
                      render: (_, entry) => {
                        if (entry.task) {
                          const task = entry.task;
                          return (
                            <Dropdown
                              trigger={["click"]}
                              menu={{
                                items: [
                                  {
                                    key: "retry",
                                    icon: <SendOutlined />,
                                    label: "重新发布",
                                    disabled: task.status !== "failed" || !task.retryable
                                  },
                                  {
                                    key: "sync",
                                    icon: <SyncOutlined />,
                                    label: "手动核检",
                                    disabled: !["success", "verification_required"].includes(task.status)
                                  },
                                  { key: "details", icon: <InfoCircleOutlined />, label: "执行详情" }
                                ],
                                onClick: ({ key }) => {
                                  if (key === "retry") void retryFailedProductPublish(task);
                                  if (key === "sync" && productManagerAccountId) void runProductManagerSync(productManagerAccountId);
                                  if (key === "details") {
                                    Modal.info({
                                      title: "发布任务详情",
                                      width: 680,
                                      content: (
                                        <Space direction="vertical" size={8} className="content-stack">
                                          <Text copyable={privacyMaskEnabled ? false : undefined}>
                                            任务 ID：{privateId(task.task_id)}
                                          </Text>
                                          <Text>阶段：{publishPhaseLabels[task.phase] || task.phase}</Text>
                                          <Text>尝试次数：{task.attempt_no}</Text>
                                          {task.failure_kind ? <Text>错误类型：{task.failure_kind}</Text> : null}
                                          {task.error ? (
                                            <Alert
                                              type="error"
                                              showIcon
                                              message={privacyMaskEnabled ? "错误详情已隐藏" : task.error}
                                            />
                                          ) : null}
                                        </Space>
                                      )
                                    });
                                  }
                                }
                              }}
                            >
                              <Tooltip title="更多操作">
                                <Button
                                  type="text"
                                  icon={<MoreOutlined />}
                                  loading={productRetryingTaskId === task.task_id}
                                  aria-label="发布任务更多操作"
                                />
                              </Tooltip>
                            </Dropdown>
                          );
                        }
                        const item = entry.item!;
                        return (
                          <Space size={4}>
                            <Tooltip title="擦亮">
                              <Button
                                type="text"
                                icon={<SyncOutlined />}
                                disabled={item.platform_status !== "selling" || Boolean(productManagerAction)}
                                aria-label="擦亮商品"
                                onClick={() => void runManagedProductAction("polish", [item.item_id])}
                              />
                            </Tooltip>
                            <Tooltip title="下架">
                              <Button
                                type="text"
                                icon={<StopOutlined />}
                                disabled={item.platform_status !== "selling" || Boolean(productManagerAction)}
                                aria-label="下架商品"
                                onClick={() => void runManagedProductAction("offline", [item.item_id])}
                              />
                            </Tooltip>
                            <Dropdown
                              trigger={["click"]}
                              menu={{
                                items: item.platform_status === "deleted"
                                  ? item.sync_state === "current"
                                    ? [{
                                        key: "delete-local",
                                        danger: true,
                                        icon: <DeleteOutlined />,
                                        label: "删除本地数据"
                                      }]
                                    : [{
                                        key: "verify",
                                        icon: <SyncOutlined />,
                                        label: "手动核检"
                                      }]
                                  : [{
                                      key: "delete",
                                      danger: true,
                                      icon: <DeleteOutlined />,
                                      label: "永久删除"
                                    }],
                                onClick: ({ key }) => {
                                  if (key === "delete") confirmDeleteManagedProducts([item.item_id]);
                                  if (key === "delete-local") confirmDeleteLocalManagedProduct(item);
                                  if (key === "verify" && productManagerAccountId) {
                                    void runProductManagerSync(productManagerAccountId);
                                  }
                                }
                              }}
                            >
                              <Tooltip title="更多操作">
                                <Button
                                  type="text"
                                  icon={<MoreOutlined />}
                                  loading={productManagerAction === `local-delete:${item.item_id}`}
                                  disabled={Boolean(productManagerAction)}
                                  aria-label="更多操作"
                                />
                              </Tooltip>
                            </Dropdown>
                          </Space>
                        );
                      }
                    }
                  ]}
                />
              </div>
            </>
          ) : (
            <div className="product-catalog-empty">
              {productManagerLoading ? <Spin /> : <Empty description="请选择闲鱼账户" />}
            </div>
          )}
        </section>

        <Drawer
          className="product-publish-drawer"
          title={`${selectedProductManagerAccount ? accountDisplayName(selectedProductManagerAccount) : "账户"} · 发布商品`}
          width={compactLayout ? "100%" : 820}
          open={productPublishDrawerOpen}
          maskClosable={!productPublishSubmitting && !productImagePreviewOpen}
          keyboard={!productPublishSubmitting && !productImagePreviewOpen}
          closable={!productPublishSubmitting && !productImagePreviewOpen}
          onClose={() => void closeProductPublishDrawer()}
        >
          {productLoading ? (
            <div className="product-catalog-empty"><Spin /></div>
          ) : productAccount ? renderProductWorkspace() : <Empty description="未加载平台账户" />}
        </Drawer>

        <Modal
          title={`${selectedProductManagerAccount ? accountDisplayName(selectedProductManagerAccount) : "账户"} · 商品任务设置`}
          open={productManagerSettingsOpen}
          confirmLoading={productManagerAction === "settings"}
          okText="保存"
          cancelText="取消"
          onOk={() => void saveProductManagerSettings()}
          onCancel={() => setProductManagerSettingsOpen(false)}
        >
          <Form form={productSyncSettingForm} layout="vertical" className="product-setting-form">
            <Form.Item name="sync_enabled" label="定时同步" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="sync_interval_minutes" label="增量同步间隔（分钟）">
              <InputNumber className="full-width" min={5} max={1440} />
            </Form.Item>
            <Form.Item name="sync_jitter_minutes" label="同步随机延迟（分钟）">
              <InputNumber className="full-width" min={0} max={120} />
            </Form.Item>
            <Form.Item name="full_sync_interval_hours" label="全量同步间隔（小时）">
              <InputNumber className="full-width" min={1} max={168} />
            </Form.Item>
            <Form.Item
              name="publish_verify_delay_seconds"
              label="发布后核检延迟（秒）"
              tooltip="发布完成后等待平台列表更新，再自动核检一次；不会循环核检。"
            >
              <InputNumber className="full-width" min={10} max={300} />
            </Form.Item>
            <Form.Item name="auto_polish_enabled" label="自动擦亮" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="polish_hour" label="每日执行时段（北京时间）">
              <InputNumber className="full-width" min={0} max={23} addonAfter="时" />
            </Form.Item>
            <Form.Item name="polish_jitter_minutes" label="擦亮随机延迟（分钟）">
              <InputNumber className="full-width" min={0} max={180} />
            </Form.Item>
          </Form>
        </Modal>

        <Drawer
          title={`${selectedProductManagerAccount ? accountDisplayName(selectedProductManagerAccount) : "账户"} · 商品任务记录`}
          width={compactLayout ? "100%" : 760}
          open={productManagerHistoryOpen}
          onClose={() => setProductManagerHistoryOpen(false)}
        >
          <Table<ProductOperationRun>
            rowKey="run_id"
            size="small"
            dataSource={productOperationRuns}
            pagination={{ pageSize: 15, showSizeChanger: false }}
            expandable={{
              expandedRowRender: (run) => run.error ? (
                <Text type="danger">{privacyMaskEnabled ? "错误详情已隐藏" : run.error}</Text>
              ) : (
                <Text type="secondary">成功 {run.success_count}，失败 {run.failed_count}，跳过 {run.skipped_count}</Text>
              )
            }}
            columns={[
              { title: "任务", dataIndex: "operation", width: 100, render: (value) => operationLabels[value as ProductOperationRun["operation"]] },
              { title: "状态", dataIndex: "status", width: 110, render: (value: ProductOperationRun["status"]) => <Tag color={runStatusMeta[value].color}>{runStatusMeta[value].label}</Tag> },
              { title: "触发", dataIndex: "trigger", width: 90, render: (value) => value === "manual" ? "手动" : value === "scheduled" ? "定时" : "发布后" },
              { title: "数量", dataIndex: "total_count", width: 80 },
              { title: "时间", dataIndex: "created_at", width: 180, render: formatTime }
            ]}
          />
        </Drawer>
      </div>
    );
  }

  function renderProductWorkspace() {
    const taskStatusLabels: Record<ProductPublishTask["status"], string> = {
      pending: "排队中",
      running: "发布中",
      success: "发布成功",
      verification_required: "待人工核验",
      failed: "发布失败",
      cancelled: "已取消"
    };
    const phaseLabels: Record<string, string> = {
      pending: "等待执行",
      starting: "准备发布",
      resolving_category: "识别类目",
      resolving_location: "读取地址",
      publishing: "提交发布",
      verifying: "核验商品",
      completed: "已完成",
      verification_required: "等待核验",
      failed: "执行失败"
    };
    return (
      <Space direction="vertical" size={16} className="content-stack">
        <Card
          size="small"
          title={(
            <Space size={6}>
              <span>商品信息</span>
              <Tooltip
                title="提交后由后台任务使用当前账户绑定代理执行，状态会在商品列表持续更新。结果未知或需要核验时，不会自动重复发布。"
              >
                <QuestionCircleOutlined
                  className="product-publish-help"
                  tabIndex={0}
                  aria-label="发布任务说明"
                />
              </Tooltip>
            </Space>
          )}
        >
          <Form
            form={productDraftForm}
            layout="vertical"
            initialValues={{
              stock: 1,
              image_refs: [],
              images_text: "",
              delivery_choice: "free_shipping",
              can_self_pickup: false,
              location_mode: "account_default",
              region_path: null,
              location_key: null,
              location_group_id: null,
              status: "draft"
            }}
          >
            <div className="product-draft-grid">
              <Form.Item
                name="title"
                className="product-wide-field"
                label="商品标题"
                rules={[{ required: true, message: "请输入商品标题" }]}
              >
                <Input placeholder="商品标题" />
              </Form.Item>
              <Form.Item
                name="description"
                className="product-wide-field"
                label="商品描述"
                rules={[{ required: true, message: "请输入商品描述" }]}
              >
                <Input.TextArea
                  autoSize={{ minRows: 3, maxRows: 10 }}
                  placeholder="填写商品成色、规格、瑕疵和交易说明"
                />
              </Form.Item>
              <div className="product-form-row product-price-row">
                <Form.Item name="price" label="价格" rules={[{ required: true, message: "请输入价格" }]}> 
                  <Input prefix="¥" inputMode="decimal" placeholder="19.90" />
                </Form.Item>
                <Form.Item name="original_price" label="原价">
                  <Input prefix="¥" inputMode="decimal" placeholder="可选" />
                </Form.Item>
                <Form.Item name="stock" label="库存">
                  <InputNumber className="full-width" min={1} max={100000} />
                </Form.Item>
                <Form.Item name="category_hint" label="类目提示">
                  <Input placeholder="例如 手机配件" />
                </Form.Item>
              </div>
              <div className="product-form-row product-shipping-row">
                <Form.Item name="delivery_choice" label="运费方式">
                  <Select
                    open={productShippingOpen}
                    onOpenChange={(open) => {
                      setProductShippingOpen(open);
                      if (!open) setProductShippingError(null);
                    }}
                    options={[
                      { label: "包邮", value: "free_shipping" },
                      {
                        label: productDeliveryChoice === "fixed" && productPostPrice
                          ? `固定运费 ¥${productPostPrice}`
                          : "固定运费",
                        value: "fixed"
                      },
                      { label: "仅自提", value: "pickup_only" },
                      { label: "按距离计费", value: "distance" }
                    ]}
                    onChange={(value: ProductDraft["delivery_choice"]) => {
                      if (value === "fixed") {
                        setProductShippingOpen(true);
                        return;
                      }
                      selectProductDeliveryChoice(value);
                    }}
                    popupRender={() => (
                      <div
                        className="product-shipping-menu"
                        onMouseDown={(event) => event.stopPropagation()}
                      >
                        <button
                          type="button"
                          className={`product-shipping-option${productDeliveryChoice === "free_shipping" ? " is-selected" : ""}`}
                          onClick={() => selectProductDeliveryChoice("free_shipping")}
                        >
                          <span>包邮</span>
                          {productDeliveryChoice === "free_shipping" ? <CheckOutlined /> : null}
                        </button>
                        <div className={`product-shipping-fixed${productDeliveryChoice === "fixed" ? " is-selected" : ""}`}>
                          <span className="product-shipping-fixed-label">固定运费</span>
                          <Space.Compact className="product-shipping-fixed-input">
                            <Input
                              prefix="¥"
                              inputMode="decimal"
                              value={productPostPrice || ""}
                              status={productShippingError ? "error" : undefined}
                              placeholder="输入运费"
                              onChange={(event) => {
                                productDraftForm.setFieldValue("post_price", event.target.value);
                                setProductShippingError(null);
                              }}
                              onPressEnter={confirmFixedProductDelivery}
                            />
                            <Tooltip title="确认固定运费">
                              <Button
                                type="primary"
                                icon={<CheckOutlined />}
                                aria-label="确认固定运费"
                                onClick={confirmFixedProductDelivery}
                              />
                            </Tooltip>
                          </Space.Compact>
                          {productShippingError ? (
                            <Text type="danger" className="product-shipping-error">
                              {productShippingError}
                            </Text>
                          ) : null}
                        </div>
                        <button
                          type="button"
                          className={`product-shipping-option${productDeliveryChoice === "pickup_only" ? " is-selected" : ""}`}
                          onClick={() => selectProductDeliveryChoice("pickup_only")}
                        >
                          <span>仅自提</span>
                          {productDeliveryChoice === "pickup_only" ? <CheckOutlined /> : null}
                        </button>
                        <button
                          type="button"
                          className={`product-shipping-option${productDeliveryChoice === "distance" ? " is-selected" : ""}`}
                          onClick={() => selectProductDeliveryChoice("distance")}
                        >
                          <span>按距离计费</span>
                          {productDeliveryChoice === "distance" ? <CheckOutlined /> : null}
                        </button>
                        <div className="product-shipping-pickup">
                          <div>
                            <Text>支持自提</Text>
                            {productDeliveryChoice === "pickup_only" ? (
                              <Text type="secondary">仅自提模式已包含</Text>
                            ) : null}
                          </div>
                          <Switch
                            size="small"
                            checked={productDeliveryChoice === "pickup_only" ? false : productCanSelfPickup}
                            disabled={productDeliveryChoice === "pickup_only"}
                            onChange={(checked) => productDraftForm.setFieldValue("can_self_pickup", checked)}
                          />
                        </div>
                      </div>
                    )}
                  />
                </Form.Item>
              </div>
              <Form.Item className="product-wide-field" label="宝贝所在地">
                <TreeSelect<string, ProductLocationTreeNode>
                  className="full-width"
                  value={productLocationSelection}
                  treeData={productLocationTreeData}
                  treeNodeLabelProp="displayLabel"
                  treeLine
                  treeExpandAction="click"
                  showSearch
                  allowClear
                  popupMatchSelectWidth={compactLayout ? true : 520}
                  placeholder="账户默认，可搜索全国行政区域"
                  suffixIcon={productRegionLoading || productLocationLoading ? <Spin size="small" /> : <EnvironmentOutlined />}
                  filterTreeNode={(input, node) => {
                    if (!input) return true;
                    return String(node.value).startsWith("region:") &&
                      node.searchText.includes(input.trim().toLowerCase());
                  }}
                  loadData={async (node) => {
                    if (
                      String(node.value) === "mode:selected" &&
                      productAccount &&
                      !productLocationLoading &&
                      !productLocations.length
                    ) {
                      await loadProductLocationOptions(productAccount.account_id);
                    }
                  }}
                  onClear={resetProductLocationSelection}
                  onChange={(value) => selectProductLocation(value)}
                  notFoundContent="没有匹配的全国行政区域"
                />
              </Form.Item>
              <Form.Item name="post_price" hidden><Input /></Form.Item>
              <Form.Item name="can_self_pickup" hidden valuePropName="checked"><Switch /></Form.Item>
              <Form.Item name="location_mode" hidden><Input /></Form.Item>
              <Form.Item name="region_path" hidden><Input /></Form.Item>
              <Form.Item name="location_key" hidden><Input /></Form.Item>
              <Form.Item name="location_group_id" hidden><Input /></Form.Item>
              <Form.Item name="image_refs" hidden>
                <Input />
              </Form.Item>
              <Form.Item
                className="product-wide-field"
                label={`商品图片（${selectedProductImageRefs.length}/9）`}
                required
              >
                <input
                  ref={productImageInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,.zip,application/zip"
                  multiple
                  hidden
                  onChange={(event) => void uploadProductImages(event.target.files)}
                />
                <div
                  className={`product-image-dropzone${productImageDropActive ? " is-drag-over" : ""}`}
                  onDragEnter={(event) => {
                    event.preventDefault();
                    productImageDragDepthRef.current += 1;
                    setProductImageDropActive(true);
                  }}
                  onDragOver={(event) => {
                    event.preventDefault();
                    event.dataTransfer.dropEffect = "copy";
                    setProductImageDropActive(true);
                  }}
                  onDragLeave={() => {
                    productImageDragDepthRef.current = Math.max(0, productImageDragDepthRef.current - 1);
                    if (productImageDragDepthRef.current === 0) {
                      setProductImageDropActive(false);
                    }
                  }}
                  onDrop={(event) => {
                    event.preventDefault();
                    productImageDragDepthRef.current = 0;
                    setProductImageDropActive(false);
                    void uploadProductImages(event.dataTransfer.files);
                  }}
                >
                {productImageDropActive ? (
                  <div className="product-image-drop-overlay">
                    <PictureOutlined />
                    <Text strong>释放以导入图片或 ZIP</Text>
                  </div>
                ) : null}
                <Space direction="vertical" size={12} className="content-stack">
                  <Space wrap>
                    <Button
                      icon={<PictureOutlined />}
                      loading={productImageUploading}
                      disabled={!productAccount || selectedProductImageRefs.length >= 9}
                      onClick={() => productImageInputRef.current?.click()}
                    >
                      选择图片或 ZIP
                    </Button>
                    <Text type="secondary">
                      支持 JPEG、PNG、WebP，或不超过 50 MB 的 ZIP；最多 9 张图片
                    </Text>
                  </Space>
                  {selectedProductImageRefs.length ? (
                    <DndContext
                      sensors={productImageSensors}
                      collisionDetection={closestCenter}
                      onDragEnd={handleProductImageDragEnd}
                    >
                      <SortableContext
                        items={selectedProductImageRefs}
                        strategy={rectSortingStrategy}
                      >
                        <div className="product-image-grid">
                          {selectedProductImageRefs.map((imageRef, index) => (
                            <SortableProductImage
                              key={imageRef}
                              imageRef={imageRef}
                              index={index}
                              total={selectedProductImageRefs.length}
                              asset={productImageAssets.find((item) => item.image_ref === imageRef)}
                              previewUrl={productImagePreviewUrls[imageRef]}
                              onPreview={openProductImagePreview}
                              onMove={moveProductImage}
                              onRemove={removeProductImageFromDraft}
                            />
                          ))}
                        </div>
                      </SortableContext>
                    </DndContext>
                  ) : (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未选择本地图片" />
                  )}
                </Space>
                </div>
                <Image.PreviewGroup
                  items={productImagePreviewItems}
                  preview={{
                    visible: productImagePreviewOpen,
                    current: productImagePreviewIndex,
                    zIndex: 1400,
                    minScale: 0.5,
                    maxScale: 6,
                    scaleStep: 0.25,
                    movable: true,
                    getContainer: () => document.body,
                    onVisibleChange: (visible) => setProductImagePreviewOpen(visible),
                    onChange: (current) => setProductImagePreviewIndex(current)
                  }}
                />
              </Form.Item>
              <Form.Item name="images_text" hidden><Input /></Form.Item>
            </div>
            <div className="product-publish-actions">
              <Text type="secondary">提交后可关闭页面，任务会继续执行。</Text>
              <Button
                type="primary"
                icon={<SendOutlined />}
                loading={productPublishSubmitting}
                disabled={productImageUploading}
                onClick={() => void submitProductDraft()}
              >
                发布商品
              </Button>
            </div>
          </Form>
        </Card>

        {false ? <>
        <Card size="small" title="草稿列表">
          <Table
            rowKey="draft_id"
            size="small"
            loading={productLoading}
            dataSource={productDrafts}
            scroll={{ x: 980 }}
            pagination={{ pageSize: 6 }}
            columns={[
              { title: "标题", dataIndex: "title", width: 220, ellipsis: true },
              { title: "价格", dataIndex: "price", width: 100 },
              { title: "库存", dataIndex: "stock", width: 80 },
              {
                title: "所在地",
                width: 180,
                ellipsis: true,
                render: (_, draft) =>
                  ["region", "selected"].includes(draft.location_mode) && draft.location
                    ? [draft.location.city, draft.location.area, draft.location.poi_name].filter(Boolean).join(" ")
                    : draft.location_mode === "group_random"
                      ? `随机：${productAddressGroups.find((group) => group.group_id === draft.location_group_id)?.name || "地址分组"}`
                    : "账户默认"
              },
              {
                title: "状态",
                dataIndex: "status",
                width: 90,
                render: (status: ProductDraft["status"]) => {
                  const color = status === "ready" ? "blue" : status === "archived" ? "default" : "green";
                  return <Tag color={color}>{status}</Tag>;
                }
              },
              {
                title: "更新",
                dataIndex: "updated_at",
                width: 170,
                render: (value: string) => formatTime(value)
              },
              {
                title: "操作",
                width: 210,
                render: (_, draft) => (
                  <Space wrap>
                    <Tooltip title="编辑草稿">
                      <Button size="small" icon={<EditOutlined />} onClick={() => startEditProductDraft(draft)} />
                    </Tooltip>
                    <Button
                      type="primary"
                      size="small"
                      icon={<SendOutlined />}
                      loading={productPublishingDraftId === draft.draft_id}
                      disabled={Boolean(productPublishingDraftId) || productLoading || draft.status === "archived"}
                      onClick={() => void createPublishTask(draft)}
                    >
                      发布
                    </Button>
                    <Tooltip title="删除草稿">
                      <Button danger size="small" icon={<DeleteOutlined />} onClick={() => void removeProductDraft(draft)} />
                    </Tooltip>
                  </Space>
                )
              }
            ]}
          />
        </Card>

        <Card size="small" title="发布任务">
          <Table
            rowKey="task_id"
            size="small"
            loading={productLoading}
            dataSource={productTasks}
            scroll={{ x: 1000 }}
            pagination={{ pageSize: 6 }}
            columns={[
              {
                title: "时间",
                dataIndex: "created_at",
                width: 170,
                render: (value: string) => formatTime(value)
              },
              {
                title: "商品",
                dataIndex: "draft_id",
                width: 180,
                render: (draftId: string) => productDrafts.find((draft) => draft.draft_id === draftId)?.title || draftId
              },
              {
                title: "阶段",
                dataIndex: "phase",
                width: 110,
                render: (phase: string) => phase.startsWith("uploading_image:") ? `上传图片 ${phase.split(":")[1]}` : (phaseLabels[phase] || phase)
              },
              {
                title: "状态",
                dataIndex: "status",
                width: 90,
                render: (status: ProductPublishTask["status"]) => {
                  const color = status === "success" ? "green" : status === "failed" ? "red" : status === "verification_required" ? "orange" : "blue";
                  return <Tag color={color}>{taskStatusLabels[status]}</Tag>;
                }
              },
              {
                title: "商品 ID",
                dataIndex: "item_id",
                width: 150,
                render: (itemId: string | null, task: ProductPublishTask) => task.item_url ? <a href={task.item_url} target="_blank" rel="noreferrer">{itemId || "查看商品"}</a> : (itemId || "-")
              },
              { title: "错误", dataIndex: "error", ellipsis: true },
              {
                title: "操作",
                width: 100,
                render: (_, task) => {
                  const draft = productDrafts.find((item) => item.draft_id === task.draft_id);
                  if (task.status === "pending") {
                    return (
                      <Button size="small" onClick={() => void enqueuePublishTask(task)}>
                        重新入队
                      </Button>
                    );
                  }
                  return task.status === "failed" && draft ? (
                    <Button
                      size="small"
                      loading={productPublishingDraftId === draft.draft_id}
                      disabled={Boolean(productPublishingDraftId)}
                      onClick={() => void createPublishTask(draft)}
                    >
                      新建重试
                    </Button>
                  ) : null;
                }
              }
            ]}
          />
        </Card>
        </> : null}
      </Space>
    );
  }

  function renderProductsPage() {
    return (
      <AccountWorkspacePage
        accounts={accounts}
        selectedAccount={productAccount}
        title="商品发布"
        emptyDescription="请选择一个账户进入商品发布页"
        refreshText="刷新商品数据"
        loading={productLoading}
        onSelect={(account) => {
          void selectProductAccount(account);
        }}
        onRefresh={() => {
          if (productAccount) {
            void Promise.all([
              loadProductData(productAccount.account_id),
              productLocations.length || productLocationMode === "selected"
                ? loadProductLocationOptions(productAccount.account_id, true)
                : Promise.resolve()
            ]);
          }
        }}
      >
        {renderProductWorkspace()}
      </AccountWorkspacePage>
    );
  }

  function renderAddressLibraryPage() {
    const selectedGroup = addressGroups.find(
      (group) => group.group_id === selectedAddressGroupId
    );
    const preciseAddresses = publishAddresses.filter(
      (address) => address.source !== "administrative_region"
    );
    const selectedRegionLeafCount = addressRegionCodes.filter(
      (code) => productRegionsByCode.get(code)?.selectable
    ).length;
    return (
      <Space direction="vertical" size={16} className="content-stack">
        <div className="page-toolbar">
          <Space wrap>
            <Select
              className="address-group-select"
              placeholder="选择地址分组"
              value={selectedAddressGroupId || undefined}
              loading={addressLibraryLoading}
              options={addressGroups.map((group) => ({
                label: `${privateName(group.name)}（${group.address_count}）`,
                value: group.group_id
              }))}
              onChange={(value) => void selectAddressGroup(value)}
            />
            <Button icon={<PlusOutlined />} type="primary" onClick={() => openAddressGroupModal()}>
              新建分组
            </Button>
            <Tooltip title="编辑分组">
              <Button
                icon={<EditOutlined />}
                disabled={!selectedGroup}
                onClick={() => selectedGroup && openAddressGroupModal(selectedGroup)}
              />
            </Tooltip>
            <Tooltip title="删除分组">
              <Button
                danger
                icon={<DeleteOutlined />}
                disabled={!selectedGroup}
                onClick={() => selectedGroup && void removeAddressGroup(selectedGroup)}
              />
            </Tooltip>
          </Space>
          <Button
            icon={<PlusOutlined />}
            disabled={!selectedGroup}
            onClick={openAddressImportModal}
          >
            添加精准地址
          </Button>
        </div>

        {selectedGroup ? (
          <Descriptions size="small" bordered column={{ xs: 1, sm: 2, lg: 4 }}>
            <Descriptions.Item label="分组">{privateName(selectedGroup.name)}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={selectedGroup.enabled ? "green" : "default"}>
                {selectedGroup.enabled ? "启用" : "停用"}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="避免最近重复">
              {selectedGroup.avoid_recent_count} 次
            </Descriptions.Item>
            <Descriptions.Item label="绑定账户">
              {selectedGroup.account_ids.length
                ? selectedGroup.account_ids
                    .map((accountId) => accountDisplayName(accounts.find(item => item.account_id === accountId)))
                    .join("、")
                : "未绑定"}
            </Descriptions.Item>
          </Descriptions>
        ) : null}

        <section className="address-region-section">
          <div className="address-region-heading">
            <div>
              <Text strong>随机区域</Text>
              <Text type="secondary">
                {selectedGroup
                  ? `已选 ${selectedRegionLeafCount} 个可发布区域`
                  : "请先创建地址分组"}
              </Text>
            </div>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              loading={addressRegionSaving}
              disabled={!selectedGroup || productRegionLoading}
              onClick={() => void saveAddressRegions()}
            >
              保存区域
            </Button>
          </div>
          {selectedGroup ? (
            <Spin spinning={productRegionLoading}>
              <div className="address-region-tree">
                <Tree
                  checkable
                  selectable={false}
                  height={420}
                  treeData={productRegionTree}
                  checkedKeys={addressRegionCodes}
                  onCheck={(checked) => {
                    const keys = Array.isArray(checked) ? checked : checked.checked;
                    setAddressRegionCodes(keys.map(String));
                  }}
                />
              </div>
            </Spin>
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无地址分组" />
          )}
        </section>

        <div className="address-table-heading">
          <Text strong>精准地址</Text>
          <Text type="secondary">{preciseAddresses.length} 个</Text>
        </div>

        <Table
          rowKey="address_id"
          size="small"
          loading={addressLibraryLoading}
          dataSource={preciseAddresses}
          scroll={{ x: 1050 }}
          pagination={{ pageSize: 12 }}
          locale={{ emptyText: selectedGroup ? "分组内尚无精准地址" : "请先创建地址分组" }}
          columns={[
            {
              title: "精准地址",
              dataIndex: "label",
              width: 300,
              ellipsis: true,
              render: (value: string) =>
                maskSensitive(value, privacyMaskEnabled, "address") || "-"
            },
            {
              title: "来源账户",
              dataIndex: "source_account_id",
              width: 150,
              render: (accountId: string | null) =>
                accountDisplayName(accounts.find((account) => account.account_id === accountId)) || privateId(accountId) || "-"
            },
            {
              title: "区域编码",
              dataIndex: "division_id",
              width: 110,
              render: (value?: string | null) => privateId(value) || "-"
            },
            { title: "使用次数", dataIndex: "use_count", width: 90 },
            {
              title: "上次使用",
              dataIndex: "last_used_at",
              width: 170,
              render: (value: string | null) => value ? formatTime(value) : "-"
            },
            {
              title: "启用",
              dataIndex: "enabled",
              width: 80,
              render: (enabled: boolean, address: PublishAddress) => (
                <Switch
                  size="small"
                  checked={enabled}
                  onChange={(checked) => void togglePublishAddress(address, checked)}
                />
              )
            },
            {
              title: "操作",
              width: 80,
              render: (_, address: PublishAddress) => (
                <Tooltip title="移出分组">
                  <Button
                    danger
                    size="small"
                    icon={<DeleteOutlined />}
                    onClick={() => Modal.confirm({
                      title: "移出此地址？",
                      okText: "移出",
                      okButtonProps: { danger: true },
                      cancelText: "取消",
                      onOk: () => removePublishAddress(address)
                    })}
                  />
                </Tooltip>
              )
            }
          ]}
        />

        <Modal
          title={editingAddressGroup ? "编辑地址分组" : "新建地址分组"}
          open={addressGroupModalOpen}
          confirmLoading={addressLibraryLoading}
          onOk={() => void saveAddressGroup()}
          onCancel={() => setAddressGroupModalOpen(false)}
          okText="保存"
          cancelText="取消"
        >
          <Form form={addressGroupForm} layout="vertical">
            <Form.Item name="name" label="分组名称" rules={[{ required: true, message: "请输入分组名称" }]}>
              <Input placeholder="例如 华东随机地址" />
            </Form.Item>
            <Form.Item
              name="account_ids"
              label="绑定发布账户"
              rules={[{ required: true, message: "请选择至少一个账户" }]}
            >
              <Select
                mode="multiple"
                optionFilterProp="label"
                options={accounts.map((account) => ({
                  label: accountDisplayName(account),
                  value: account.account_id
                }))}
              />
            </Form.Item>
            <Form.Item name="avoid_recent_count" label="避免最近重复次数">
              <InputNumber className="full-width" min={0} max={100} />
            </Form.Item>
            <Form.Item name="enabled" label="启用分组" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Form>
        </Modal>

        <Modal
          title="添加账号精准地址"
          open={addressImportModalOpen}
          width={680}
          confirmLoading={addressImportLoading}
          onOk={() => void importPublishAddresses()}
          onCancel={() => setAddressImportModalOpen(false)}
          okText="加入分组"
          cancelText="取消"
        >
          <Form form={addressImportForm} layout="vertical">
            <Form.Item name="account_id" label="地址来源账户" rules={[{ required: true }]}>
              <Select
                options={accounts.map((account) => ({
                  label: accountDisplayName(account),
                  value: account.account_id
                }))}
                onChange={(accountId) => {
                  addressImportForm.setFieldValue("location_ids", []);
                  void loadAddressImportLocations(accountId);
                }}
              />
            </Form.Item>
            <Form.Item
              name="location_ids"
              label="账号精准地址"
              rules={[{ required: true, message: "请选择至少一个精准地址" }]}
            >
              <Select
                mode="multiple"
                showSearch
                optionFilterProp="label"
                loading={addressImportLoading}
                placeholder="选择常用地址、默认所在地或附近地址"
                options={addressImportLocations.map((location) => ({
                  label: maskSensitive(location.label, privacyMaskEnabled, "address"),
                  value: location.location_id
                }))}
                notFoundContent={addressImportLoading ? <Spin size="small" /> : "暂无平台地址"}
              />
            </Form.Item>
            <Button
              icon={<SyncOutlined />}
              loading={addressImportLoading}
              disabled={!addressImportForm.getFieldValue("account_id")}
              onClick={() => {
                const accountId = addressImportForm.getFieldValue("account_id");
                if (accountId) {
                  void loadAddressImportLocations(accountId, true);
                }
              }}
            >
              刷新平台地址
            </Button>
          </Form>
        </Modal>
      </Space>
    );
  }

  function renderTasksPage() {
    return (
      <Card
        size="small"
        title="后台任务"
        extra={
          <Tooltip title="刷新后台任务">
            <Button
              type="text"
              icon={<SyncOutlined spin={backgroundTasksLoading} />}
              aria-label="刷新后台任务"
              onClick={() => void loadBackgroundTaskData()}
            />
          </Tooltip>
        }
      >
          <Table
            rowKey="task_id"
            size="small"
            loading={backgroundTasksLoading}
            dataSource={backgroundTasks}
            pagination={{ pageSize: 10 }}
            columns={[
              {
                title: "时间",
                dataIndex: "created_at",
                width: 170,
                render: (value: string) => formatTime(value)
              },
              {
                title: "账户",
                dataIndex: "account_id",
                width: 160,
                render: (accountId?: string | null) =>
                  accountId
                    ? accountDisplayName(accounts.find((account) => account.account_id === accountId))
                    : "系统"
              },
              { title: "类型", dataIndex: "task_type", width: 160 },
              {
                title: "状态",
                dataIndex: "status",
                width: 90,
                render: (status: BackgroundTask["status"]) => {
                  const color = status === "success" ? "green" : status === "failed" ? "red" : "blue";
                  const label = {
                    pending: "等待中",
                    running: "执行中",
                    success: "成功",
                    failed: "失败",
                    cancelled: "已取消"
                  }[status];
                  return <Tag color={color}>{label}</Tag>;
                }
              },
              { title: "尝试", dataIndex: "attempt_count", width: 70, align: "right" },
              {
                title: "开始时间",
                dataIndex: "started_at",
                width: 170,
                render: (value?: string | null) => formatTime(value)
              },
              {
                title: "耗时",
                width: 100,
                render: (_, task: BackgroundTask) => {
                  if (!task.started_at) return "-";
                  const end = task.finished_at ? apiTimeToEpochMs(task.finished_at) : Date.now();
                  return formatDuration(Math.max(0, end - apiTimeToEpochMs(task.started_at)));
                }
              },
              { title: "错误", dataIndex: "error", ellipsis: true }
            ]}
            scroll={{ x: 1200 }}
          />
      </Card>
    );
  }

  function renderAuditPage() {
    return (
      <Card
        title="审计日志"
        extra={<Button onClick={() => void loadAuditLogs()}>刷新</Button>}
      >
        <Table
          rowKey="audit_id"
          size="small"
          loading={auditLoading}
          dataSource={auditLogs}
          pagination={{ pageSize: 15 }}
          columns={[
            {
              title: "时间",
              dataIndex: "created_at",
              width: 170,
              render: (value: string) => formatTime(value)
            },
            { title: "动作", dataIndex: "action", width: 90 },
            { title: "操作者", dataIndex: "actor", width: 120, render: (value?: string | null) => privateName(value) || "-" },
            { title: "客户端 IP", dataIndex: "client_ip", width: 140, render: (value?: string | null) => privateIP(value) || "-" },
            { title: "目标", dataIndex: "target", ellipsis: true, render: (value?: string | null) => privacyMaskEnabled && value ? "目标已隐藏" : value || "-" },
            {
              title: "结果",
              dataIndex: "success",
              width: 90,
              render: (success: boolean) =>
                success ? <Tag color="green">成功</Tag> : <Tag color="red">失败</Tag>
            },
            { title: "状态码", dataIndex: "status_code", width: 90 },
            { title: "错误", dataIndex: "error", ellipsis: true, render: (value?: string | null) => privacyMaskEnabled && value ? "错误详情已隐藏" : value || "-" }
          ]}
        />
      </Card>
    );
  }

  function renderMessageServicesPage() {
    const chatwootStatusColor =
      chatwootConfig?.status === "error"
        ? "red"
        : chatwootConfig?.status === "degraded"
          ? "orange"
          : chatwootConfig?.status === "online" || chatwootConfig?.status === "ready"
            ? "blue"
            : "default";
    return (
      <Space direction="vertical" size={16} className="content-stack message-services-page">
        <Card
          title={
            <Space size={8} wrap>
              <span>Chatwoot</span>
              <Tag color="blue">平台级</Tag>
              {chatwootConfig ? (
                <>
                  <Tag color={chatwootConfig.enabled ? "green" : "default"}>
                    {chatwootConfig.enabled ? "已启用" : "已停用"}
                  </Tag>
                  <Tag color={chatwootStatusColor}>{chatwootConfig.status}</Tag>
                </>
              ) : (
                <Tag color="orange">尚未配置</Tag>
              )}
            </Space>
          }
          loading={chatwootLoading}
          extra={
            <Button
              icon={<SyncOutlined />}
              onClick={() => {
                void loadChatwootData();
                void loadWebNotificationData(true);
              }}
            >
              刷新
            </Button>
          }
        >
          <Form
            form={chatwootForm}
            layout="vertical"
            className="chatwoot-config-form"
            initialValues={{
              enabled: false,
              account_alerts_enabled: true,
              offline_alert_delay_seconds: 120,
              clear_client_hmac_token: false,
              clear_api_access_token: false
            }}
          >
            <div className="message-service-section">
              <div className="message-service-section-heading">
                <Text strong>功能与提醒</Text>
                <Text type="secondary">控制 Chatwoot 主链路和账户异常提醒</Text>
              </div>
              <div className="message-service-toggle-grid">
                <div className="message-service-toggle-item">
                  <div>
                    <Text strong>启用 Chatwoot</Text>
                    <Text type="secondary">闲鱼消息与 Chatwoot 双向同步</Text>
                  </div>
                  <Form.Item name="enabled" valuePropName="checked" noStyle>
                    <Switch checkedChildren="启用" unCheckedChildren="停用" />
                  </Form.Item>
                </div>
                <div className="message-service-toggle-item">
                  <div>
                    <Text strong>账户状态提醒</Text>
                    <Text type="secondary">Cookie 失效、IM 掉线与恢复推送到 Chatwoot</Text>
                  </div>
                  <Form.Item name="account_alerts_enabled" valuePropName="checked" noStyle>
                    <Switch checkedChildren="启用" unCheckedChildren="停用" />
                  </Form.Item>
                </div>
              </div>
              <div className="chatwoot-config-grid message-service-fields">
                <Form.Item
                  name="offline_alert_delay_seconds"
                  label="IM 掉线提醒延迟"
                  extra="过滤短时网络抖动；Cookie 确认失效不受此延迟影响"
                  rules={[{ required: true, message: "请输入掉线提醒延迟" }]}
                >
                  <InputNumber
                    min={30}
                    max={3600}
                    precision={0}
                    addonAfter="秒"
                    style={{ width: "100%" }}
                  />
                </Form.Item>
                <Form.Item label="当前链路">
                  <Space size={6} wrap className="chatwoot-config-status">
                    <Tag color={chatwootConfig?.has_webhook_secret ? "green" : "red"}>
                      Webhook {chatwootConfig?.has_webhook_secret ? "已配置" : "未配置"}
                    </Tag>
                    <Tag color={chatwootConfig?.full_outbound_sync_enabled ? "green" : "orange"}>
                      {chatwootConfig?.full_outbound_sync_enabled ? "完整双向同步" : "基础链路"}
                    </Tag>
                    <Tag color={chatwootConfig?.account_grouping_enabled ? "green" : "orange"}>
                      {chatwootConfig?.account_grouping_enabled
                        ? `${chatwootConfig?.managed_inbox_count ?? 0} 个账号 Inbox`
                        : "账号分组待凭据"}
                    </Tag>
                  </Space>
                </Form.Item>
              </div>
            </div>

            <div className="message-service-section">
              <div className="message-service-section-heading">
                <Text strong>连接参数</Text>
                <Text type="secondary">Chatwoot 地址、收件箱和回调入口</Text>
              </div>
              <div className="chatwoot-config-grid message-service-fields">
                <Form.Item
                  name="base_url"
                  label="Chatwoot 地址"
                  rules={[{ required: true, message: "请输入 Chatwoot 地址" }]}
                >
                  <Input placeholder="https://192.168.201.2" />
                </Form.Item>
                <Form.Item name="chatwoot_account_id" label="Chatwoot 平台账户 ID">
                  <InputNumber min={1} precision={0} style={{ width: "100%" }} />
                </Form.Item>
                <Form.Item
                  name="inbox_identifier"
                  label="收件箱标识符"
                  rules={[{ required: true, message: "请输入 API Inbox 标识符" }]}
                >
                  <Input />
                </Form.Item>
                <Form.Item label="账户范围">
                  <div className="message-service-readonly">
                    <Text>
                      {accounts.filter((account) => account.chat_enabled).length} 个账户开启 Chat
                    </Text>
                    <Text type="secondary">
                      {chatwootConfig?.managed_inbox_count ?? 0} 个托管 Inbox
                    </Text>
                  </div>
                </Form.Item>
                <Form.Item
                  name="callback_url"
                  label="Webhook 地址"
                  className="chatwoot-config-span-2"
                  extra="在 Chatwoot API Inbox 中填写此回调地址"
                  rules={[
                    { required: true, message: "请输入 Webhook 地址" },
                    { type: "url", message: "请输入完整的 http:// 或 https:// 地址" }
                  ]}
                >
                  <Input
                    placeholder="https://192.168.2.3/api/integrations/chatwoot/webhook"
                    suffix={
                      chatwootCallbackUrlValue ? (
                        <Text copyable={{ text: chatwootCallbackUrlValue }} />
                      ) : null
                    }
                  />
                </Form.Item>
              </div>
            </div>

            <div className="message-service-section">
              <div className="message-service-section-heading">
                <Text strong>安全凭据</Text>
                <Text type="secondary">凭据在服务端加密存储，留空不会覆盖已有值</Text>
              </div>
              <div className="chatwoot-config-grid message-service-fields">
                <Form.Item
                  name="webhook_secret"
                  label="Webhook 秘密"
                  rules={[
                    {
                      validator: (_, value) =>
                        value
                          ? Promise.resolve()
                          : Promise.reject(new Error("请输入 Webhook 秘密"))
                    }
                  ]}
                >
                  <Input.Password autoComplete="new-password" />
                </Form.Item>
                <div className="message-service-credential">
                  <Form.Item
                    name="client_hmac_token"
                    label="客户端身份 HMAC Token"
                    extra="仅在 Chatwoot API Inbox 启用身份验证时填写"
                  >
                    <Input.Password autoComplete="new-password" />
                  </Form.Item>
                  {chatwootConfig?.has_client_hmac_token ? (
                    <div className="message-service-clear-control">
                      <Text type="secondary">保存时清除现有 HMAC Token</Text>
                      <Form.Item
                        name="clear_client_hmac_token"
                        valuePropName="checked"
                        noStyle
                      >
                        <Switch size="small" />
                      </Form.Item>
                    </div>
                  ) : null}
                </div>
                <div className="message-service-credential chatwoot-config-span-2">
                  <Form.Item
                    name="api_access_token"
                    label="专用服务账号令牌"
                    extra="账号标签、手机端账号分组、在线状态及自动创建账号 Inbox 必填"
                  >
                    <Input.Password autoComplete="new-password" />
                  </Form.Item>
                  {chatwootConfig?.has_api_access_token ? (
                    <div className="message-service-clear-control">
                      <Text type="secondary">保存时清除现有服务账号令牌</Text>
                      <Form.Item
                        name="clear_api_access_token"
                        valuePropName="checked"
                        noStyle
                      >
                        <Switch size="small" />
                      </Form.Item>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>

            <div className="message-service-section message-service-runtime">
              <div className="message-service-section-heading">
                <Text strong>运行记录</Text>
                <Text type="secondary">用于快速判断双向链路是否持续活跃</Text>
              </div>
              <div className="message-service-runtime-grid">
                <div>
                  <Text type="secondary">最近推送</Text>
                  <Text>{formatTime(chatwootConfig?.last_push_at)}</Text>
                </div>
                <div>
                  <Text type="secondary">最近回调</Text>
                  <Text>{formatTime(chatwootConfig?.last_webhook_at)}</Text>
                </div>
                <div>
                  <Text type="secondary">配置更新时间</Text>
                  <Text>{formatTime(chatwootConfig?.updated_at)}</Text>
                </div>
              </div>
            </div>

            <div className="chatwoot-config-actions">
              <Button
                type="primary"
                icon={<SaveOutlined />}
                loading={chatwootSaving}
                onClick={() => void saveChatwootConfiguration()}
              >
                保存配置
              </Button>
              <Button
                loading={chatwootTesting}
                disabled={!chatwootConfig}
                onClick={() => void runChatwootTest()}
              >
                测试连接
              </Button>
              <Button
                loading={chatwootAlertTesting}
                disabled={
                  !chatwootConfig?.enabled ||
                  !chatwootConfig?.account_alerts_enabled
                }
                onClick={() => void runChatwootAccountAlertTest()}
              >
                测试账户提醒
              </Button>
            </div>
          </Form>
        </Card>
        {chatwootConfig?.last_error ? (
          <Alert
            type="error"
            showIcon
            message="最近一次同步失败"
            description={chatwootConfig.last_error}
          />
        ) : null}
        <Card
          title={
            <Space size={8} wrap>
              <span>网页客户消息铃声</span>
              <Tag color="purple">仅本项目网页端</Tag>
              <Tag color={webNotificationConfig?.enabled ? "green" : "default"}>
                {webNotificationConfig?.enabled ? "已启用" : "已关闭"}
              </Tag>
            </Space>
          }
          loading={webNotificationLoading}
        >
          <div className="web-notification-settings">
            <Alert
              type="info"
              showIcon
              message="Chatwoot 使用它自己的通知设置"
              description="这里的铃声只在本项目网页收到新的客户入站消息时播放，不会修改或重复接管 Chatwoot 的手机端和网页端通知。"
            />
            <div className="message-service-toggle-item web-notification-toggle">
              <div>
                <Text strong>客户消息叮咚提醒</Text>
                <Text type="secondary">
                  只提醒实时新消息；历史同步、自己发送和系统消息不会播放
                </Text>
              </div>
              <Switch
                checked={Boolean(webNotificationConfig?.enabled)}
                loading={webNotificationSaving}
                checkedChildren="启用"
                unCheckedChildren="关闭"
                onChange={(checked) => void setWebNotificationEnabled(checked)}
              />
            </div>
            <div className="web-notification-sound-row">
              <div className="web-notification-sound-info">
                <Space size={8} wrap>
                  <Text strong>当前铃声</Text>
                  <Tag color={webNotificationConfig?.has_custom_sound ? "blue" : "default"}>
                    {webNotificationConfig?.has_custom_sound ? "自定义" : "内置叮咚"}
                  </Tag>
                  <Tag color={webNotificationUnlocked ? "green" : "orange"}>
                    {webNotificationUnlocked ? "浏览器已允许播放" : "点击页面后可播放"}
                  </Tag>
                </Space>
                <Text type="secondary">
                  {webNotificationConfig?.has_custom_sound
                    ? `${webNotificationConfig.sound_filename || "自定义铃声"} · ${
                        webNotificationConfig.sound_size_bytes != null
                          ? formatBytes(webNotificationConfig.sound_size_bytes)
                          : "未知大小"
                      }`
                    : "使用项目内置的双音“叮咚”提示，不依赖外部音频文件"}
                </Text>
                {webNotificationConfig?.updated_at ? (
                  <Text type="secondary">
                    最近更新：{formatTime(webNotificationConfig.updated_at)}
                  </Text>
                ) : null}
              </div>
              <Space size={8} wrap className="web-notification-actions">
                <Button
                  icon={<PlayCircleOutlined />}
                  disabled={!webNotificationConfig}
                  onClick={() => void previewWebNotificationSound()}
                >
                  试听
                </Button>
                <Upload
                  accept=".mp3,.wav,.ogg,.m4a,audio/mpeg,audio/wav,audio/ogg,audio/mp4"
                  showUploadList={false}
                  disabled={webNotificationUploading}
                  beforeUpload={(file) => {
                    void handleWebNotificationSoundUpload(file);
                    return false;
                  }}
                >
                  <Button
                    icon={<UploadOutlined />}
                    loading={webNotificationUploading}
                  >
                    {webNotificationConfig?.has_custom_sound ? "更换铃声" : "上传铃声"}
                  </Button>
                </Upload>
                {webNotificationConfig?.has_custom_sound ? (
                  <Button
                    disabled={webNotificationUploading}
                    onClick={confirmClearWebNotificationSound}
                  >
                    恢复默认
                  </Button>
                ) : null}
              </Space>
            </div>
            <Text type="secondary">
              支持 MP3、WAV、OGG、M4A，最大 5 MB。浏览器为防止网页自动发声，登录后至少需要点击页面一次。
            </Text>
          </div>
        </Card>
      </Space>
    );
  }

  function renderAIProviderPage() {
    return (
      <Card
        title="AI 服务"
        loading={aiProviderLoading}
        extra={
          aiProvider?.has_api_key
            ? <Tag color="green">凭据已配置</Tag>
            : <Tag color="orange">缺少凭据</Tag>
        }
      >
        <Form
          form={aiProviderForm}
          layout="vertical"
          className="ai-provider-form"
          initialValues={{ ai_base_url: "", ai_model: "", ai_api_key: "" }}
        >
          <Form.Item
            name="ai_base_url"
            label="API 地址"
            rules={[{ required: true, message: "请输入 API 地址" }]}
          >
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          <Form.Item
            name="ai_model"
            label="模型"
            rules={[{ required: true, message: "请输入模型名称" }]}
          >
            <Input placeholder="例如 gpt-4.1-mini" />
          </Form.Item>
          <Form.Item
            name="ai_api_key"
            label="API Key"
            extra={aiProvider?.has_api_key ? "已保存，留空不会覆盖现有密钥" : undefined}
            rules={[
              {
                validator: (_, value) =>
                  aiProvider?.has_api_key || value
                    ? Promise.resolve()
                    : Promise.reject(new Error("请输入 API Key"))
              }
            ]}
          >
            <Input.Password autoComplete="new-password" placeholder="sk-..." />
          </Form.Item>
          <Space>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              loading={aiProviderSaving}
              onClick={() => void saveAIProviderSetting()}
            >
              保存
            </Button>
            {aiProvider?.has_api_key ? (
              <Button danger icon={<DeleteOutlined />} onClick={clearAIProviderKey}>
                删除 API Key
              </Button>
            ) : null}
          </Space>
        </Form>
      </Card>
    );
  }

  function renderBrowserRuntimePage() {
    const runtime = browserRuntime;
    const activeVncSessionCount = runtime?.active_vnc_session_count
      || runtime?.active_vnc_account_ids?.length
      || 1;
    const transportBoundaryDetails = runtime
      ? `${runtime.transport_warning} 当前：HTTP=${runtime.http_transport}，WSS=${runtime.wss_transport}。高风险网页操作应走账户 VNC/CDP 浏览器链路。`
      : "当前浏览器页面由 Chromium 自身产生网络指纹；后台协议链路不宣称与 Chromium TLS 完全一致。";
    return (
      <Space direction="vertical" size={12} className="content-stack browser-runtime-page">
        <div className="browser-runtime-summary" role="note" aria-label="浏览器运行环境说明">
          <div className="browser-runtime-summary-item">
            <Tag className="browser-runtime-tag" color="blue">冷配置</Tag>
            <Text type="secondary" className="browser-runtime-summary-text">浏览器二进制统一管理</Text>
            <Tooltip title="上传、下载和默认版本在这里统一管理；账户使用哪个内核、固定 Seed 和指纹参数在“平台账户 → 编辑 → 浏览器与指纹”中配置。">
              <InfoCircleOutlined className="browser-runtime-summary-help" aria-label="查看冷配置说明" />
            </Tooltip>
          </div>
          {runtime?.active_vnc_account_id ? (
            <div className="browser-runtime-summary-item browser-runtime-summary-item-warning">
              <Tag className="browser-runtime-tag" color="gold">VNC 运行中 {activeVncSessionCount}</Tag>
              <Text type="secondary" className="browser-runtime-summary-text">切换默认版本前请先停止全部运行环境</Text>
            </div>
          ) : null}
        </div>
        <Card
          title="标准 Chrome / Chromium"
          loading={browserRuntimeLoading && !runtime}
          extra={
            <Space wrap>
              <Upload
                accept=".zip"
                showUploadList={false}
                beforeUpload={(file) => {
                  void installStandardBrowserFromFile(file);
                  return false;
                }}
                disabled={Boolean(browserRuntimeAction)}
              >
                <Button
                  icon={<UploadOutlined />}
                  loading={browserRuntimeAction === "standard:upload"}
                >
                  上传压缩包
                </Button>
              </Upload>
              <Button
                type="primary"
                icon={<CloudServerOutlined />}
                loading={browserRuntimeAction === "standard:download"}
                disabled={Boolean(browserRuntimeAction) && browserRuntimeAction !== "standard:download"}
                onClick={() => void downloadLatestStandardBrowser()}
              >
                一键下载最新版
              </Button>
              <Tooltip title="刷新运行环境">
                <Button
                  type="text"
                  aria-label="刷新浏览器运行环境"
                  icon={<SyncOutlined spin={browserRuntimeLoading} />}
                  onClick={() => void loadBrowserRuntime()}
                />
              </Tooltip>
            </Space>
          }
        >
          <Space direction="vertical" size={12} className="content-stack">
            <Text type="secondary">
              系统内置 Chromium 保持只读；托管版本仅接受 Google Chrome for Testing Linux x86_64 ZIP。官方项目：{" "}
              <a href={runtime?.official_standard_project_url} target="_blank" rel="noreferrer">Chrome for Testing</a>
            </Text>
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="当前默认">
                {runtime?.active_standard_version ? (
                  <Tag color="blue">托管 · {runtime.active_standard_version}</Tag>
                ) : (
                  <Tag color="green">系统内置</Tag>
                )}
              </Descriptions.Item>
              <Descriptions.Item label="系统状态">
                <Tag color={runtime?.system_browser.available ? "green" : "red"}>
                  {runtime?.system_browser.available ? "可用" : "不可用"}
                </Tag>
                {runtime?.system_browser.validation_message || ""}
              </Descriptions.Item>
              <Descriptions.Item label="系统版本">{runtime?.system_browser.version || "-"}</Descriptions.Item>
              <Descriptions.Item label="系统路径">{runtime?.system_browser.executable_path || "-"}</Descriptions.Item>
              <Descriptions.Item label="托管目录">{runtime?.standard_root_directory || "-"}</Descriptions.Item>
              <Descriptions.Item label="账户 VNC 会话">
                无操作 {formatSecondsDuration(runtime?.vnc_idle_timeout_seconds || 1800)}自动关闭 · 最长 {formatSecondsDuration(runtime?.vnc_max_session_seconds || 28800)}
              </Descriptions.Item>
              <Descriptions.Item label="系统操作">
                <Button
                  size="small"
                  disabled={!runtime?.active_standard_version || Boolean(runtime?.active_vnc_account_id)}
                  loading={browserRuntimeAction === "standard:activate:system"}
                  onClick={() => void activateStandardBrowserVersion(null)}
                >
                  {runtime?.active_standard_version ? "设为默认" : "使用中"}
                </Button>
              </Descriptions.Item>
            </Descriptions>
            <Table
              rowKey="version"
              size="small"
              pagination={false}
              loading={browserRuntimeLoading}
              dataSource={runtime?.standard_browsers ?? []}
              locale={{ emptyText: "尚未安装托管标准 Chrome" }}
              columns={[
                {
                  title: "版本",
                  dataIndex: "version",
                  render: (value, item) => <Space><Text strong>{value}</Text>{item.active ? <Tag color="green">默认</Tag> : null}</Space>
                },
                { title: "来源", dataIndex: "source", width: 90 },
                { title: "大小", dataIndex: "size_bytes", width: 110, render: (value) => formatBytes(value) },
                {
                  title: "校验",
                  width: 120,
                  render: (_, item) => <Tooltip title={item.validation_message}><Tag color={item.valid ? "green" : "red"}>{item.valid ? "通过" : "失败"}</Tag></Tooltip>
                },
                {
                  title: "操作",
                  width: 100,
                  render: (_, item) => (
                    <Button
                      size="small"
                      type={item.active ? "default" : "primary"}
                      disabled={item.active || !item.valid || Boolean(runtime?.active_vnc_account_id)}
                      loading={browserRuntimeAction === `standard:activate:${item.version}`}
                      onClick={() => void activateStandardBrowserVersion(item.version)}
                    >
                      {item.active ? "使用中" : "设为默认"}
                    </Button>
                  )
                }
              ]}
            />
          </Space>
        </Card>
        <Card
          title="Fingerprint Chromium"
          extra={
            <Space wrap>
              <Upload
                accept=".zip,.tar.xz,.txz"
                showUploadList={false}
                beforeUpload={(file) => {
                  void installFingerprintBrowserFromFile(file);
                  return false;
                }}
                disabled={Boolean(browserRuntimeAction)}
              >
                <Button icon={<UploadOutlined />} loading={browserRuntimeAction === "upload"}>
                  上传压缩包
                </Button>
              </Upload>
              <Button
                type="primary"
                icon={<CloudServerOutlined />}
                loading={browserRuntimeAction === "download"}
                disabled={Boolean(browserRuntimeAction) && browserRuntimeAction !== "download"}
                onClick={() => void downloadLatestFingerprintBrowser()}
              >
                一键下载最新版
              </Button>
            </Space>
          }
        >
          <Space direction="vertical" size={12} className="content-stack">
            <Text type="secondary">
              仅接受官方项目 Linux 压缩包，服务端会校验归档路径、可执行文件、版本与 SHA256。上游项目：{" "}
              <a href={runtime?.official_project_url} target="_blank" rel="noreferrer">fingerprint-chromium</a>
            </Text>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="本地目录">{runtime?.root_directory || "-"}</Descriptions.Item>
              <Descriptions.Item label="默认版本">{runtime?.active_fingerprint_version || "未设置"}</Descriptions.Item>
            </Descriptions>
            <Table
              rowKey="version"
              size="small"
              pagination={false}
              loading={browserRuntimeLoading}
              dataSource={runtime?.fingerprint_browsers ?? []}
              locale={{ emptyText: "尚未安装 Fingerprint Chromium" }}
              columns={[
                {
                  title: "版本",
                  dataIndex: "version",
                  render: (value, item) => <Space><Text strong>{value}</Text>{item.active ? <Tag color="green">默认</Tag> : null}</Space>
                },
                { title: "来源", dataIndex: "source", width: 90 },
                { title: "大小", dataIndex: "size_bytes", width: 110, render: (value) => formatBytes(value) },
                {
                  title: "校验",
                  width: 120,
                  render: (_, item) => <Tooltip title={item.validation_message}><Tag color={item.valid ? "green" : "red"}>{item.valid ? "通过" : "失败"}</Tag></Tooltip>
                },
                {
                  title: "操作",
                  width: 100,
                  render: (_, item) => (
                    <Button
                      size="small"
                      type={item.active ? "default" : "primary"}
                      disabled={item.active || !item.valid || Boolean(runtime?.active_vnc_account_id)}
                      loading={browserRuntimeAction === `activate:${item.version}`}
                      onClick={() => void activateFingerprintBrowserVersion(item.version)}
                    >
                      {item.active ? "使用中" : "设为默认"}
                    </Button>
                  )
                }
              ]}
            />
          </Space>
        </Card>
        <div className="browser-runtime-boundary" role="note" aria-label="网络指纹边界说明">
          <WarningOutlined className="browser-runtime-boundary-icon" aria-hidden="true" />
          <Tag className="browser-runtime-tag" color="gold">网络指纹边界</Tag>
          <Text type="secondary" className="browser-runtime-boundary-text">
            {runtime
              ? `HTTP：${runtime.http_transport} · WSS：${runtime.wss_transport}`
              : "HTTP / WSS 传输信息读取中"}
          </Text>
          <Tooltip title={transportBoundaryDetails}>
            <InfoCircleOutlined className="browser-runtime-summary-help" aria-label="查看 TLS、JA3 和 HTTP2 边界说明" />
          </Tooltip>
        </div>
      </Space>
    );
  }

  function renderSettingsPage() {
    const activeTab = settingsTabFromSearch(location.search, isAdmin, canMutate);
    if (activeTab === "proxies") return renderSocksProxyPage();
    if (activeTab === "browsers") return renderBrowserRuntimePage();
    if (activeTab === "addresses") return renderAddressLibraryPage();
    if (activeTab === "ai") return renderAIProviderPage();
    if (activeTab === "message-services") return renderMessageServicesPage();
    if (activeTab === "tasks") return renderTasksPage();
    if (activeTab === "audit") return renderAuditPage();
    return renderUsersPage();
  }

  const activeSettingsTab = settingsTabFromSearch(location.search, isAdmin, canMutate);
  const settingsNavigationChildren = [
    { key: "settings:users", label: settingsTabLabels.users },
    { key: "settings:proxies", label: settingsTabLabels.proxies },
    ...(canMutate
      ? [{ key: "settings:addresses", label: settingsTabLabels.addresses }]
      : []),
    ...(isAdmin
      ? [
          { key: "settings:ai", label: settingsTabLabels.ai },
          { key: "settings:message-services", label: settingsTabLabels["message-services"] },
          { key: "settings:browsers", label: settingsTabLabels.browsers },
          { key: "settings:tasks", label: settingsTabLabels.tasks },
          { key: "settings:audit", label: settingsTabLabels.audit }
        ]
      : [])
  ];
  const navigationItems = [
    { key: "dashboard", icon: <CloudServerOutlined />, label: "控制台" },
    { key: "accounts", icon: <ApiOutlined />, label: "平台账户" },
    { key: "conversations", icon: <MessageOutlined />, label: "会话消息" },
    { key: "auto-reply", icon: <RobotOutlined />, label: "自动回复" },
    { key: "delivery", icon: <ShoppingCartOutlined />, label: "订单管理" },
    { key: "product-management", icon: <ShopOutlined />, label: "商品管理" },
    {
      key: "settings",
      icon: <LockOutlined />,
      label: "系统设置",
      children: settingsNavigationChildren
    }
  ].filter((item) => {
    const key = item.key as AdminMenuKey;
    if (adminMenus.has(key) && !isAdmin) {
      return false;
    }
    return currentUser?.role !== "viewer" || viewerMenus.has(key);
  });

  if (!authChecked) {
    return (
      <Layout className="login-layout">
        <Card className="login-card" loading>
          正在检查登录状态...
        </Card>
      </Layout>
    );
  }

  if (!authenticated) {
    return (
      <Layout className="login-layout">
        <Card className="login-card">
          <Space direction="vertical" size={20} className="content-stack">
            <Space direction="vertical" size={4}>
              <Space>
                <CloudServerOutlined className="login-brand-icon" />
                <Title level={3} className="login-title">
                  多平台管理
                </Title>
              </Space>
              <Text type="secondary">
                {setupInitialized ? "请输入管理员用户名和密码登录。" : "系统尚未初始化，请创建首个管理员。"}
              </Text>
              {clientAccess ? (
                <Text type="secondary">
                  当前访问 IP：{clientAccess.ip || "-"}（来源：{clientAccess.source}）
                </Text>
              ) : null}
            </Space>
            <Form form={loginForm} layout="vertical" onFinish={() => void (setupInitialized ? submitLogin() : bootstrapFirstAdmin())}>
              <Form.Item name="username" label="用户名" rules={[{ required: true, message: "请输入用户名" }]}>
                <Input placeholder="管理员用户名" />
              </Form.Item>
              <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }]}>
                <Input.Password prefix={<LockOutlined />} placeholder="管理员密码" />
              </Form.Item>
              <Space direction="vertical" className="content-stack">
                {setupInitialized ? (
                  <Button type="primary" htmlType="submit" loading={loginLoading} block>
                    登录
                  </Button>
                ) : (
                  <Button type="primary" htmlType="submit" loading={loginLoading} block>
                    初始化首个管理员
                  </Button>
                )}
              </Space>
            </Form>
          </Space>
        </Card>
      </Layout>
    );
  }

  return (
    <Layout className={`admin-layout${privacyMaskEnabled ? " privacy-mode" : ""}`}>
      <Sider width={232} className="admin-sider">
        <div className="sider-brand">
          <CloudServerOutlined className="brand-icon" />
          <span>多平台管理</span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[
            activeMenu === "settings" ? `settings:${activeSettingsTab}` : activeMenu
          ]}
          openKeys={navigationOpenKeys}
          onOpenChange={(keys) => setNavigationOpenKeys(keys.includes("settings") ? ["settings"] : [])}
          onClick={({ key }) => handleNavigationClick(key)}
          items={navigationItems}
        />
      </Sider>
      <Drawer
        className="mobile-navigation"
        placement="left"
        width={232}
        open={mobileNavOpen}
        onClose={() => setMobileNavOpen(false)}
        title="多平台管理"
        styles={{ body: { padding: 0, background: "#141414" } }}
      >
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[
            activeMenu === "settings" ? `settings:${activeSettingsTab}` : activeMenu
          ]}
          openKeys={navigationOpenKeys}
          onOpenChange={(keys) => setNavigationOpenKeys(keys.includes("settings") ? ["settings"] : [])}
          onClick={({ key }) => handleNavigationClick(key)}
          items={navigationItems}
        />
      </Drawer>
      <Layout className={activeMenu === "conversations" ? "conversation-main-layout" : undefined}>
        <Header className="admin-header">
          <Space className="header-title">
            <Button
              className="mobile-menu-button"
              type="text"
              icon={<MenuOutlined />}
              aria-label="打开导航"
              onClick={() => setMobileNavOpen(true)}
            />
            <Title level={4} className="brand-title">
              {activeMenu === "settings"
                ? settingsTabLabels[activeSettingsTab]
                : menuTitles[activeMenu]}
            </Title>
          </Space>
          <Space className="header-account-actions" size={8}>
            <Tooltip title={privacyMaskEnabled ? "关闭隐私去敏" : "开启隐私去敏"}>
              <Button
                type={privacyMaskEnabled ? "primary" : "text"}
                className="privacy-toggle"
                icon={privacyMaskEnabled ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                loading={privacySaving}
                aria-label={privacyMaskEnabled ? "关闭隐私去敏" : "开启隐私去敏"}
                aria-pressed={privacyMaskEnabled}
                onClick={() => void togglePrivacyMask()}
              />
            </Tooltip>
            <Tooltip title={`角色：${currentUser?.role || "-"}`}>
              <span className="current-user">
                {maskSensitive(currentUser?.username, privacyMaskEnabled, "name")}
              </span>
            </Tooltip>
            <Button icon={<LogoutOutlined />} onClick={logout} aria-label="退出登录" />
          </Space>
        </Header>
        <Content
          className={`admin-content${
            activeMenu === "conversations" ? " conversation-content" : ""
          }`}
        >
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={renderDashboardPage()} />
            <Route path="/users" element={<Navigate to="/settings?tab=users" replace />} />
            <Route path="/accounts" element={renderAccountsPage()} />
            <Route path="/conversations" element={renderConversationsPage()} />
            <Route path="/auto-reply" element={canMutate ? renderAutoReplyPage() : <Navigate to="/dashboard" replace />} />
            <Route path="/delivery" element={canMutate ? renderDeliveryPage() : <Navigate to="/dashboard" replace />} />
            <Route path="/product-management" element={canMutate ? renderProductManagementPage() : <Navigate to="/dashboard" replace />} />
            <Route path="/products" element={<Navigate to="/product-management" replace />} />
            <Route path="/events" element={<Navigate to="/accounts" replace />} />
            <Route path="/tasks" element={<Navigate to="/settings?tab=tasks" replace />} />
            <Route path="/audit" element={<Navigate to="/settings?tab=audit" replace />} />
            <Route path="/settings" element={renderSettingsPage()} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Content>
      </Layout>

      <Drawer
        title={editingUser ? "编辑用户" : "新增用户"}
        width={480}
        open={userDrawerOpen}
        onClose={() => setUserDrawerOpen(false)}
        extra={
          <Space>
            <Button onClick={() => setUserDrawerOpen(false)}>取消</Button>
            <Button type="primary" onClick={() => void submitUserForm()}>
              保存
            </Button>
          </Space>
        }
      >
        <Form form={userForm} layout="vertical" requiredMark="optional">
          <Form.Item
            name="username"
            label="用户名"
            rules={[{ required: true, message: "请输入用户名" }]}
          >
            <Input disabled={Boolean(editingUser)} placeholder="例如：admin / operator01" />
          </Form.Item>
          <Form.Item
            name="password"
            label={editingUser ? "新密码" : "密码"}
            extra={editingUser ? "留空表示不修改密码。" : "至少 8 位。"}
            rules={editingUser ? [] : [{ required: true, message: "请输入密码" }]}
          >
            <Input.Password placeholder={editingUser ? "不修改则留空" : "至少 8 位"} />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true, message: "请选择角色" }]}>
            <Select
              options={[
                { label: "admin", value: "admin" },
                { label: "operator", value: "operator" },
                { label: "viewer", value: "viewer" }
              ]}
            />
          </Form.Item>
          <Form.Item name="enabled" label="启用用户" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Drawer>

      <Drawer
        title={runtimeLogAccount ? `${accountDisplayName(runtimeLogAccount)} · 运行日志` : "运行日志"}
        width={compactLayout ? "100%" : 760}
        open={runtimeLogOpen}
        destroyOnClose
        onClose={() => {
          runtimeLogRequestRef.current += 1;
          setRuntimeLogOpen(false);
          setRuntimeLogAccount(null);
          setEvents([]);
          setEventsLoading(false);
        }}
        extra={
          <Tooltip title="刷新运行日志">
            <Button
              type="text"
              icon={<SyncOutlined spin={eventsLoading} />}
              aria-label="刷新运行日志"
              disabled={!runtimeLogAccount}
              onClick={() => {
                if (runtimeLogAccount) void loadEventsFor(runtimeLogAccount.account_id);
              }}
            />
          </Tooltip>
        }
      >
        {renderEventsWorkspace()}
      </Drawer>

      <Drawer
        title={editingProxy ? "编辑代理" : "新增代理"}
        width={480}
        open={proxyDrawerOpen}
        onClose={() => setProxyDrawerOpen(false)}
        extra={
          <Space>
            <Button onClick={() => setProxyDrawerOpen(false)}>取消</Button>
            <Button type="primary" loading={proxySaving} onClick={() => void submitProxyForm()}>保存</Button>
          </Space>
        }
      >
        <Form form={proxyForm} layout="vertical" requiredMark="optional">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: "请输入代理名称" }]}>
            <Input placeholder="例如：香港节点 01" />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item
            name="scheme"
            label={
              <Space size={4}>
                <span>协议</span>
                <Tooltip title="socks5h 由代理服务器解析域名，可减少 DNS 泄漏，推荐使用；socks5 由本机解析域名。">
                  <QuestionCircleOutlined aria-label="查看代理协议说明" />
                </Tooltip>
              </Space>
            }
            rules={[{ required: true }]}
          >
            <Select options={[{ label: "socks5h", value: "socks5h" }, { label: "socks5", value: "socks5" }]} />
          </Form.Item>
          <Form.Item name="host" label="Host" rules={[{ required: true, message: "请输入 Host" }]}>
            <Input placeholder="127.0.0.1" />
          </Form.Item>
          <Form.Item name="port" label="端口" rules={[{ required: true, message: "请输入端口" }]}>
            <InputNumber className="full-width" min={1} max={65535} placeholder="1080" />
          </Form.Item>
          <Form.Item name="username" label="用户名">
            <Input autoComplete="off" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            extra={editingProxy && editingProxy.has_password ? "留空保留现有密码。" : undefined}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Drawer>

      <Drawer
        title={editing ? "编辑账户" : "新增账户"}
        width={520}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        extra={
          <Space>
            <Button loading={qrLoading} onClick={() => void beginQRLogin()}>
              扫码登录
            </Button>
            <Button onClick={() => setDrawerOpen(false)}>取消</Button>
            <Button type="primary" loading={submitting} onClick={() => void submitForm()}>
              保存
            </Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical">
          <Tabs
            className="account-editor-tabs"
            activeKey={accountEditorTab}
            onChange={setAccountEditorTab}
            items={[
              { key: "basic", label: "账户与网络", children: renderAccountBasicForm() },
              { key: "browser", label: "浏览器与指纹", children: renderAccountBrowserIdentityForm() }
            ]}
          />
        </Form>
      </Drawer>

      <Drawer
        className="browser-environment-drawer"
        title={
          <Space size={8}>
            <FolderOpenOutlined />
            <span>浏览器环境管理</span>
            <Tag color={Object.keys(accountBrowserStatuses).length ? "processing" : "default"}>
              运行 {Object.keys(accountBrowserStatuses).length}/{browserRuntime?.max_vnc_session_count || 3}
            </Tag>
          </Space>
        }
        width="min(880px, calc(100vw - 24px))"
        open={browserProfileDrawerOpen}
        onClose={() => setBrowserProfileDrawerOpen(false)}
        extra={
          <Tooltip title="刷新目录状态">
            <Button
              type="text"
              icon={<SyncOutlined spin={browserProfilesLoading} />}
              aria-label="刷新浏览器目录状态"
              onClick={() => void loadBrowserProfileData()}
            />
          </Tooltip>
        }
      >
        <Table<BrowserProfile>
          rowKey="profile_key"
          size="small"
          loading={browserProfilesLoading}
          dataSource={browserEnvironmentRows}
          pagination={false}
          tableLayout="fixed"
          locale={{ emptyText: "暂无浏览器环境" }}
          columns={[
            {
              title: "账户",
              render: (_, profile) => (
                <Space direction="vertical" size={0} className="browser-profile-account">
                  <Text
                    strong
                    ellipsis={{
                      tooltip: profile.account_id
                        ? accountDisplayName(accounts.find(account => account.account_id === profile.account_id))
                        : privateName(profile.account_name) || undefined
                    }}
                  >
                    {profile.account_id
                      ? accountDisplayName(accounts.find(account => account.account_id === profile.account_id))
                      : privateName(profile.account_name) ||
                        (profile.profile_type === "qr" ? "扫码登录临时目录" : "未绑定账户")}
                  </Text>
                  <Text type="secondary" ellipsis={{ tooltip: privateId(profile.account_id) || undefined }}>
                    {privateId(profile.account_id) || "-"}
                  </Text>
                </Space>
              )
            },
            {
              title: "环境 / 目录",
              render: (_, profile) => (
                <Space direction="vertical" size={0} className="browser-profile-directory">
                  <Text>
                    {privateBrowserEngineLabel(profile.browser_engine)}
                  </Text>
                  <Text type="secondary" ellipsis={{ tooltip: privateId(profile.directory_name) }}>
                    {privateId(profile.directory_name)} · {formatBytes(profile.size_bytes)}
                    {profile.config_revision ? ` · 配置 v${profile.config_revision}` : ""}
                  </Text>
                </Space>
              )
            },
            {
              title: "状态",
              width: 90,
              render: (_, profile) => (
                <Tag color={browserProfileStateMeta[profile.status].color}>
                  {browserProfileStateMeta[profile.status].label}
                </Tag>
              )
            },
            {
              title: "最近更新",
              dataIndex: "updated_at",
              width: 150,
              render: (value: string) => formatTime(value)
            },
            {
              title: "操作",
              width: 120,
              render: (_, profile) => {
                if (!canMutate) return <Text type="secondary">只读</Text>;
                const running = profile.status === "running" || profile.status === "busy";
                const account = accounts.find((item) => item.account_id === profile.account_id);
                return (
                  <Space size={2}>
                    {account ? (
                      <Tooltip title={running ? "进入已打开的 VNC 环境" : "打开 VNC 会话面板，确认后启动"}>
                        <Button
                          type="text"
                          icon={running ? <DesktopOutlined /> : <PlayCircleOutlined />}
                          aria-label={`${running ? "进入" : "启动"} ${accountDisplayName(account)}`}
                          disabled={Boolean(browserProfileClearingKey)}
                          onClick={() => void openAccountBrowser(account)}
                        />
                      </Tooltip>
                    ) : null}
                    <Tooltip title={running ? "停止该目录的浏览器会话" : "当前未运行"}>
                      <span>
                        <Button
                          type="text"
                          danger
                          icon={<StopOutlined />}
                          aria-label={`停止 ${privateId(profile.directory_name)}`}
                          loading={browserProfileStoppingKey === profile.profile_key}
                          disabled={!running || Boolean(browserProfileClearingKey)}
                          onClick={() => void stopManagedBrowserProfile(profile)}
                        />
                      </span>
                    </Tooltip>
                    <Tooltip title={running ? "请先停止会话" : "清理浏览器数据目录"}>
                      <span>
                        <Button
                          type="text"
                          danger
                          icon={<DeleteOutlined />}
                          aria-label={`清理 ${privateId(profile.directory_name)}`}
                          loading={browserProfileClearingKey === profile.profile_key}
                          disabled={
                            running ||
                            !profile.manageable ||
                            Boolean(browserProfileStoppingKey)
                          }
                          onClick={() => confirmClearManagedBrowserProfile(profile)}
                        />
                      </span>
                    </Tooltip>
                  </Space>
                );
              }
            }
          ]}
        />
      </Drawer>

      <Drawer
        className="im-verification-drawer"
        title={
          <Space size={8}>
            <DesktopOutlined />
            <span>{accountDisplayName(accountBrowserAccount)} · VNC 浏览器</span>
          </Space>
        }
        width="100vw"
        open={accountBrowserOpen}
        destroyOnClose
        onClose={closeAccountBrowserDrawer}
        extra={
          <Space wrap>
            {accountBrowserSession?.status === "ready" && !accountBrowserSocketUrl ? (
              <Button
                icon={<SyncOutlined />}
                loading={accountBrowserLoading}
                onClick={() => void connectAccountBrowserViewer(accountBrowserSession)}
              >
                连接画面
              </Button>
            ) : null}
            {isActiveAccountBrowser(accountBrowserSession) ? (
              <Button
                danger
                loading={accountBrowserLoading}
                disabled={accountBrowserSession?.status !== "ready"}
                onClick={() => void finishAccountBrowserSession()}
              >
                结束会话
              </Button>
            ) : (
              <Button
                type="primary"
                loading={accountBrowserLoading}
                disabled={
                  !accountBrowserAccount ||
                  accountBrowserClearing ||
                  Object.keys(accountBrowserStatuses).length >=
                    (browserRuntime?.max_vnc_session_count || 3)
                }
                onClick={() => void beginAccountBrowserSession()}
              >
                {Object.keys(accountBrowserStatuses).length >=
                (browserRuntime?.max_vnc_session_count || 3)
                  ? "并发已满"
                  : "开启会话"}
                </Button>
              )}
            <Tooltip
              title={
                isActiveAccountBrowser(accountBrowserSession)
                  ? "请先结束会话，再清理浏览器数据"
                  : "删除该账户的 VNC 浏览器 Profile"
              }
            >
              <span>
                <Button
                  danger
                  icon={<DeleteOutlined />}
                  loading={accountBrowserClearing}
                  disabled={
                    !accountBrowserAccount ||
                    accountBrowserLoading ||
                    isActiveAccountBrowser(accountBrowserSession)
                  }
                  onClick={confirmClearAccountBrowserProfile}
                >
                  清理浏览器数据
                </Button>
              </span>
            </Tooltip>
          </Space>
        }
      >
        <>
          <div className="im-verification-content">
            {accountBrowserSession ? (
              <div className="im-verification-status">
                <Space size={8} wrap>
                  <Tag color={accountBrowserStateMeta[accountBrowserSession.status].color}>
                    {accountBrowserStateMeta[accountBrowserSession.status].label}
                  </Tag>
                  <Tag color={accountBrowserSession.proxy_enabled ? "green" : "default"}>
                    {accountBrowserSession.proxy_enabled ? "账户代理已应用" : "直连"}
                  </Tag>
                  <Tag color={accountBrowserSession.cdp_available ? "green" : "default"}>
                    {accountBrowserSession.cdp_available ? "本机 CDP 已开启" : "CDP 未开启"}
                  </Tag>
                  {accountBrowserSession.cookie_sync_status &&
                  accountBrowserSession.cookie_sync_status !== "pending" ? (
                    <Tag color={accountBrowserCookieSyncMeta[accountBrowserSession.cookie_sync_status].color}>
                      {accountBrowserCookieSyncMeta[accountBrowserSession.cookie_sync_status].label}
                    </Tag>
                  ) : null}
                  <Tag color={browserFingerprintDetectionMeta(
                    accountBrowserSession.fingerprint_snapshot
                      ?? accountBrowserAccount?.browser_identity?.fingerprint_snapshot,
                    accountBrowserSession.fingerprint_detection_status
                  ).color}>
                    指纹：{browserFingerprintDetectionMeta(
                      accountBrowserSession.fingerprint_snapshot
                        ?? accountBrowserAccount?.browser_identity?.fingerprint_snapshot,
                      accountBrowserSession.fingerprint_detection_status
                    ).label}
                  </Tag>
                  <Tag color={browserFingerprintSecurityMeta(
                    accountBrowserSession.fingerprint_snapshot
                      ?? accountBrowserAccount?.browser_identity?.fingerprint_snapshot
                  ).color}>
                    安全：{browserFingerprintSecurityMeta(
                      accountBrowserSession.fingerprint_snapshot
                        ?? accountBrowserAccount?.browser_identity?.fingerprint_snapshot
                    ).label}
                  </Tag>
                  {accountBrowserSession.idle_expires_at ? (
                    <Text type="secondary">
                      无操作剩余 {formatCountdown(accountBrowserSession.idle_expires_at, accountBrowserClock)}
                    </Text>
                  ) : null}
                  {accountBrowserSession.max_expires_at ? (
                    <Text type="secondary">最长至 {formatTime(accountBrowserSession.max_expires_at)}</Text>
                  ) : null}
                </Space>
                <div className="account-browser-status-side">
                  {accountBrowserSession.status === "ready" ? (
                    <div className="account-browser-paste-box">
                      <Input.TextArea
                        value={accountBrowserPasteText}
                        onChange={(event) => setAccountBrowserPasteText(event.target.value)}
                        placeholder="先点击 VNC 网页输入框，再粘贴文本"
                        autoSize={{ minRows: 1, maxRows: 3 }}
                        allowClear
                        maxLength={20_000}
                        aria-label="粘贴到 VNC 的文本"
                      />
                      <Button
                        type="primary"
                        loading={accountBrowserPasting}
                        disabled={!accountBrowserConnected || !accountBrowserPasteText.trim()}
                        onClick={() => void pasteTextIntoAccountBrowser()}
                      >
                        确认
                      </Button>
                    </div>
                  ) : null}
                  <Space direction="vertical" size={0} className="account-browser-status-message">
                    {accountBrowserSession.message ? (
                      <Text>{privacyMaskEnabled ? "浏览器状态详情已隐藏" : accountBrowserSession.message}</Text>
                    ) : null}
                    {accountBrowserSession.current_url ? (
                      <Text type="secondary" ellipsis={{ tooltip: privacyMaskEnabled ? "链接已隐藏" : accountBrowserSession.current_url }}>
                        {maskSensitive(accountBrowserSession.current_url, privacyMaskEnabled, "url")}
                      </Text>
                    ) : null}
                  </Space>
                </div>
              </div>
            ) : null}

            {!accountBrowserSession && !accountBrowserLoading && !accountBrowserError ? (
              <div className="im-verification-status im-verification-status-compact">
                <Space size={4}>
                  <Tag>未开启</Tag>
                  <Tooltip title="开启会话时会重新注入该账户数据库中的最新 Cookie，并应用账户代理。">
                    <QuestionCircleOutlined
                      className="im-verification-help"
                      aria-label="查看 VNC 会话说明"
                    />
                  </Tooltip>
                </Space>
              </div>
            ) : null}

            {!isActiveAccountBrowser(accountBrowserSession) &&
            Object.keys(accountBrowserStatuses).length >=
              (browserRuntime?.max_vnc_session_count || 3) ? (
              <Alert
                type="warning"
                showIcon
                message={`账户 VNC 并发数已达到上限 ${browserRuntime?.max_vnc_session_count || 3}，请先结束一个会话`}
              />
            ) : null}

            {accountBrowserError ? (
              <Alert type="error" showIcon message={privacyMaskEnabled ? "浏览器错误详情已隐藏" : accountBrowserError} />
            ) : null}
            {accountBrowserSession && !accountBrowserSession.browser_available ? (
              <Alert
                type="warning"
                showIcon
                message={privacyMaskEnabled && accountBrowserSession.browser_error ? "浏览器错误详情已隐藏" : accountBrowserSession.browser_error || "平台账户浏览器当前不可用"}
              />
            ) : null}
            {accountBrowserSession?.fingerprint_detection_status === "failed" ? (
              <Alert
                type="warning"
                showIcon
                message="标准指纹检测失败"
                description={accountBrowserSession.fingerprint_detection_error || "检测脚本未返回有效结果，可在编辑账户的“浏览器与指纹”页重新检测"}
              />
            ) : null}

            <div className="account-browser-visual">
              {accountBrowserSocketUrl ? (
                <div className="im-verification-desktop">
                  {privacyMaskEnabled ? (
                    <div className="im-verification-placeholder privacy-vnc-placeholder">
                      <EyeInvisibleOutlined />
                      <Text type="secondary">隐私模式下远程画面已隐藏</Text>
                    </div>
                  ) : (
                    <IMVerificationViewer
                      websocketUrl={accountBrowserSocketUrl}
                      onConnected={() => {
                        setAccountBrowserConnected(true);
                        reportAccountBrowserActivity();
                      }}
                      onActivity={reportAccountBrowserActivity}
                      onDisconnected={(clean) => {
                        setAccountBrowserConnected(false);
                        if (!clean && accountBrowserOpen) {
                          setAccountBrowserSocketUrl("");
                        }
                      }}
                    />
                  )}
                  <Tag
                    className="im-verification-connection"
                    color={accountBrowserConnected ? "green" : "processing"}
                  >
                    {accountBrowserConnected ? "画面已连接" : "正在连接"}
                  </Tag>
                </div>
              ) : (
                <div className="im-verification-placeholder">
                  {accountBrowserLoading ? <Spin /> : <DesktopOutlined />}
                </div>
              )}
            </div>
          </div>
        </>
      </Drawer>

      <Drawer
        className="im-verification-drawer"
        title={
          <Space size={8}>
            <SafetyCertificateOutlined />
            <span>{accountDisplayName(imVerificationAccount)} · 安全验证</span>
          </Space>
        }
        width="100vw"
        open={imVerificationOpen}
        destroyOnClose
        onClose={() => {
          setIMVerificationOpen(false);
          setIMVerificationSocketUrl("");
          setIMVerificationConnected(false);
        }}
        extra={
          <Space wrap>
            {imVerification?.status === "ready" && !imVerificationSocketUrl ? (
              <Button
                icon={<SyncOutlined />}
                loading={imVerificationLoading}
                onClick={() => void connectIMVerificationViewer(imVerification)}
              >
                连接画面
              </Button>
            ) : null}
            {imVerification?.status === "ready" ? (
              <Button
                type="primary"
                loading={imVerificationLoading}
                onClick={() => void runIMVerificationComplete()}
              >
                已完成，恢复 IM
              </Button>
            ) : null}
            {imVerification && ["required", "failed", "expired", "cancelled"].includes(imVerification.status) ? (
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                loading={imVerificationLoading}
                disabled={!imVerification.browser_available}
                onClick={() => void runIMVerificationStart()}
              >
                重新验证
              </Button>
            ) : null}
            {imVerification && ["starting", "ready"].includes(imVerification.status) ? (
              <Button
                danger
                disabled={imVerificationLoading}
                onClick={() => void runIMVerificationCancel()}
              >
                取消
              </Button>
            ) : null}
          </Space>
        }
      >
        <Spin spinning={imVerificationLoading && !imVerification}>
          <div className="im-verification-content">
            {imVerification ? (
              <div className="im-verification-status">
                <Space size={8} wrap>
                  <Tag color={imVerificationStateMeta[imVerification.status].color}>
                    {imVerificationStateMeta[imVerification.status].label}
                  </Tag>
                  <Text type="secondary">{imVerification.reason_code}</Text>
                  {imVerification.expires_at ? (
                    <Text type="secondary">截止 {formatTime(imVerification.expires_at)}</Text>
                  ) : null}
                </Space>
                {imVerification.message ? <Text>{privacyMaskEnabled ? "验证详情已隐藏" : imVerification.message}</Text> : null}
              </div>
            ) : null}

            {imVerification && !imVerification.browser_available ? (
              <Alert
                type="warning"
                showIcon
                message={privacyMaskEnabled && imVerification.browser_error ? "浏览器错误详情已隐藏" : imVerification.browser_error || "人工验证浏览器当前不可用"}
              />
            ) : null}

            {imVerificationSocketUrl ? (
              <div className="im-verification-desktop">
                {privacyMaskEnabled ? (
                  <div className="im-verification-placeholder privacy-vnc-placeholder">
                    <EyeInvisibleOutlined />
                    <Text type="secondary">隐私模式下远程画面已隐藏</Text>
                  </div>
                ) : (
                  <IMVerificationViewer
                    websocketUrl={imVerificationSocketUrl}
                    onConnected={() => setIMVerificationConnected(true)}
                    onDisconnected={(clean) => {
                      setIMVerificationConnected(false);
                      if (!clean && imVerificationOpen) {
                        setIMVerificationSocketUrl("");
                      }
                    }}
                  />
                )}
                <Tag className="im-verification-connection" color={imVerificationConnected ? "green" : "processing"}>
                  {imVerificationConnected ? "画面已连接" : "正在连接"}
                </Tag>
              </div>
            ) : (
              <div className="im-verification-placeholder">
                {imVerificationLoading ? (
                  <Spin />
                ) : (
                  <SafetyCertificateOutlined />
                )}
              </div>
            )}
          </div>
        </Spin>
      </Drawer>

      <Drawer
        className="im-verification-drawer"
        title={
          <Space size={8}>
            <QrcodeOutlined />
            <span>
              {compactLayout
                ? "远程登录验证"
                : `${accountDisplayName(
                    accounts.find((account) => account.account_id === qrLogin?.account_id) || editing
                  )} · 远程登录验证`}
            </span>
          </Space>
        }
        width="100vw"
        open={qrBrowserOpen}
        destroyOnClose
        onClose={() => {
          setQrBrowserOpen(false);
          setQrBrowserSocketUrl("");
          setQrBrowserConnected(false);
          if (qrLogin && qrLogin.status !== "completed") {
            setQrModalOpen(true);
          }
        }}
        extra={
          <Space wrap>
            {qrLogin && qrBrowserVerification?.status === "ready" && !qrBrowserSocketUrl ? (
              <Button
                icon={<SyncOutlined />}
                loading={qrBrowserLoading}
                onClick={() => void connectQRBrowserViewer(qrLogin.session_id)}
              >
                连接画面
              </Button>
            ) : null}
            {qrBrowserVerification?.status === "ready" ? (
              <Button
                type="primary"
                loading={qrBrowserLoading}
                onClick={() => void runQRBrowserVerificationComplete()}
              >
                已完成，检查并保存登录
              </Button>
            ) : null}
            {qrBrowserVerification && ["failed", "expired", "cancelled"].includes(qrBrowserVerification.status) ? (
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                loading={qrBrowserLoading}
                disabled={!qrBrowserVerification.browser_available}
                onClick={() => void runQRBrowserVerificationStart()}
              >
                重新打开
              </Button>
            ) : null}
            {qrBrowserVerification && ["starting", "ready"].includes(qrBrowserVerification.status) ? (
              <Button
                danger
                disabled={qrBrowserLoading}
                onClick={() => void runQRBrowserVerificationCancel()}
              >
                取消
              </Button>
            ) : null}
          </Space>
        }
      >
        <Spin spinning={qrBrowserLoading && !qrBrowserVerification}>
          <div className="im-verification-content">
            {qrBrowserVerification ? (
              <div className="im-verification-status">
                <Space size={8} wrap>
                  <Tag color={qrBrowserStateMeta[qrBrowserVerification.status].color}>
                    {qrBrowserStateMeta[qrBrowserVerification.status].label}
                  </Tag>
                  {qrBrowserVerification.expires_at ? (
                    <Text type="secondary">截止 {formatTime(qrBrowserVerification.expires_at)}</Text>
                  ) : null}
                </Space>
                {qrBrowserVerification.message ? <Text>{privacyMaskEnabled ? "验证详情已隐藏" : qrBrowserVerification.message}</Text> : null}
              </div>
            ) : null}

            {qrBrowserVerification && !qrBrowserVerification.browser_available ? (
              <Alert
                type="warning"
                showIcon
                message={privacyMaskEnabled && qrBrowserVerification.browser_error ? "浏览器错误详情已隐藏" : qrBrowserVerification.browser_error || "远程登录浏览器当前不可用"}
              />
            ) : null}

            {qrBrowserSocketUrl ? (
              <div className="im-verification-desktop">
                {privacyMaskEnabled ? (
                  <div className="im-verification-placeholder privacy-vnc-placeholder">
                    <EyeInvisibleOutlined />
                    <Text type="secondary">隐私模式下远程画面已隐藏</Text>
                  </div>
                ) : (
                  <IMVerificationViewer
                    websocketUrl={qrBrowserSocketUrl}
                    onConnected={() => setQrBrowserConnected(true)}
                    onDisconnected={(clean) => {
                      setQrBrowserConnected(false);
                      if (!clean && qrBrowserOpen) {
                        setQrBrowserSocketUrl("");
                      }
                    }}
                  />
                )}
                <Tag className="im-verification-connection" color={qrBrowserConnected ? "green" : "processing"}>
                  {qrBrowserConnected ? "画面已连接" : "正在连接"}
                </Tag>
              </div>
            ) : (
              <div className="im-verification-placeholder">
                {qrBrowserLoading ? <Spin /> : <QrcodeOutlined />}
              </div>
            )}
          </div>
        </Spin>
      </Drawer>

      <Modal
        className="cookie-renewal-modal"
        title={cookieRenewalAccount ? `Cookie 续期管理 · ${accountDisplayName(cookieRenewalAccount)}` : "Cookie 续期管理"}
        open={cookieRenewalOpen}
        onCancel={() => setCookieRenewalOpen(false)}
        footer={
          <Space>
            {canMutate && cookieRenewalAccount ? (
              <Button
                icon={<SyncOutlined />}
                disabled={cookieRenewalIsCoolingDown(cookieRenewalStatus)}
                loading={
                  cookieRenewalLoading ||
                  ["running", "applying"].includes(cookieRenewalStatus?.state || "")
                }
                onClick={() => void runCookieRenewal(cookieRenewalAccount)}
              >
                {cookieRenewalIsCoolingDown(cookieRenewalStatus) ? "一小时内无需重复续期" : "立即续期"}
              </Button>
            ) : null}
            <Button onClick={() => setCookieRenewalOpen(false)}>关闭</Button>
          </Space>
        }
      >
        <Descriptions column={1} size="small" bordered>
          <Descriptions.Item label="状态">
            <Tag color={cookieStateColor(cookieRenewalStatus?.state)}>
              {cookieStateLabel(cookieRenewalStatus?.state)}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="当前阶段">
            {cookiePhaseLabels[cookieRenewalStatus?.phase || "idle"]}
          </Descriptions.Item>
          <Descriptions.Item label="触发来源">
            {cookieRenewalStatus?.trigger
              ? cookieTriggerLabels[cookieRenewalStatus.trigger]
              : "-"}
          </Descriptions.Item>
          <Descriptions.Item label="结果">
            {privacyMaskEnabled && cookieRenewalStatus?.message ? "续期详情已隐藏" : cookieRenewalStatus?.message || "-"}
          </Descriptions.Item>
          <Descriptions.Item label="本次开始">
            {formatTime(cookieRenewalStatus?.last_started_at)}
          </Descriptions.Item>
          <Descriptions.Item label="本次完成">
            {formatTime(cookieRenewalStatus?.last_finished_at)}
          </Descriptions.Item>
          <Descriptions.Item label="最近平台验证">
            {formatTime(cookieRenewalStatus?.last_verified_at)}
          </Descriptions.Item>
          <Descriptions.Item label="验证来源">
            {cookieSourceLabel(cookieRenewalStatus?.last_verified_source)}
          </Descriptions.Item>
          <Descriptions.Item label="Cookie 更新时间">
            {formatTime(cookieRenewalStatus?.cookie_updated_at)}
          </Descriptions.Item>
          <Descriptions.Item label="Cookie 更新来源">
            {cookieSourceLabel(cookieRenewalStatus?.cookie_update_source)}
          </Descriptions.Item>
          <Descriptions.Item label="运行时应用">
            {cookieRenewalStatus?.runtime_applied === true ? (
              <Tag color="green">已应用</Tag>
            ) : cookieRenewalStatus?.runtime_applied === false ? (
              <Tag color="red">应用失败</Tag>
            ) : (
              <Text type="secondary">历史未记录</Text>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="下次尝试">{formatTime(cookieRenewalStatus?.next_attempt_at)}</Descriptions.Item>
          <Descriptions.Item label="人工处理">
            {cookieRenewalStatus?.manual_action_required ? (
              <Tag color="red">等待重新扫码</Tag>
            ) : (
              <Tag color="green">无需处理</Tag>
            )}
          </Descriptions.Item>
          {cookieRenewalStatus?.last_error_kind ? (
            <Descriptions.Item label="错误类型">
              {cookieRenewalStatus.last_error_kind}
            </Descriptions.Item>
          ) : null}
          {cookieRenewalStatus?.last_error_source ? (
            <Descriptions.Item label="失败来源">
              {cookieRenewalStatus.last_error_source}
            </Descriptions.Item>
          ) : null}
          <Descriptions.Item label="更新字段">
            {!privacyMaskEnabled && cookieRenewalStatus?.updated_cookie_names.length
              ? cookieRenewalStatus.updated_cookie_names.join("、")
              : "-"}
          </Descriptions.Item>
        </Descriptions>
        <div className="cookie-renewal-history">
          <Text strong>最近执行</Text>
          <Text type="secondary">
            时间统一按北京时间（Asia/Shanghai）显示
          </Text>
          <List
            size="small"
            locale={{ emptyText: "暂无执行记录" }}
            dataSource={cookieRenewalStatus?.recent_attempts || []}
            renderItem={(attempt) => (
              <List.Item>
                <Space direction="vertical" size={2} className="cookie-renewal-attempt">
                  <Space size={6} wrap>
                    <Tag color={cookieStateColor(attempt.state)}>
                      {cookieStateLabel(attempt.state)}
                    </Tag>
                    <Text>{cookieTriggerLabels[attempt.trigger]}</Text>
                    <Text type="secondary">{cookiePhaseLabels[attempt.phase]}</Text>
                  </Space>
                  <Text type="secondary">
                    {formatTime(attempt.started_at)} → {formatTime(attempt.finished_at)} · {formatDuration(attempt.duration_ms)}
                  </Text>
                  <Text>{privacyMaskEnabled && attempt.message ? "执行详情已隐藏" : attempt.message || "-"}</Text>
                  {attempt.error_kind ? (
                    <Text type="danger">错误类型：{attempt.error_kind}</Text>
                  ) : null}
                </Space>
              </List.Item>
            )}
          />
        </div>
      </Modal>

      <Modal
        title="闲鱼扫码登录"
        open={qrModalOpen}
        onCancel={closeQRLoginModal}
        footer={
          <Space wrap>
            {qrLogin && !["initializing", "completed", "finalizing"].includes(qrLogin.status) ? (
              <Button
                type={qrLogin.status === "verification_required" || qrLogin.status === "error" ? "primary" : "default"}
                icon={<CloudServerOutlined />}
                loading={qrBrowserLoading}
                onClick={() => void runQRBrowserVerificationStart()}
              >
                远程浏览器验证
              </Button>
            ) : null}
            {qrLogin?.status === "expired" || qrLogin?.status === "error" ? (
              <Button
                loading={qrLoading}
                onClick={() => void (qrLoginValues ? beginQRLoginWithAccount(qrLoginValues) : beginQRLogin())}
              >
                重新生成
              </Button>
            ) : null}
            <Button onClick={closeQRLoginModal}>关闭</Button>
          </Space>
        }
      >
        <Space direction="vertical" align="center" size={16} className="qr-login-content">
          {privacyMaskEnabled && (qrLogin?.code_content || qrLogin?.face_code_content) ? (
            <div className="qr-privacy-placeholder">
              <EyeInvisibleOutlined />
              <Text type="secondary">隐私模式下二维码已隐藏</Text>
            </div>
          ) : qrLogin?.code_content ? (
            <QRCode
              value={qrLogin.code_content}
              size={240}
              status={qrLogin.status === "expired" ? "expired" : qrLogin.status === "scanned" ? "scanned" : "active"}
            />
          ) : null}
          {!privacyMaskEnabled && qrLogin?.status === "verification_required" && qrLogin.face_code_content ? (
            <>
              <QRCode value={qrLogin.face_code_content} size={240} status="active" />
              <Text strong>需要人脸验证</Text>
              <Text type="secondary">请使用闲鱼 App 扫描二维码并完成人脸验证</Text>
            </>
          ) : null}
          <Tag
            color={
              qrLogin?.status === "scanned"
                ? "blue"
                : qrLogin?.status === "verification_required"
                  ? "orange"
                : qrLogin?.status === "browser_verification"
                  ? "blue"
                : qrLogin?.status === "finalizing"
                  ? "gold"
                  : qrLogin?.status === "completed"
                    ? "green"
                    : qrLogin?.status === "error"
                      ? "red"
                      : "default"
            }
          >
            {qrLogin?.status === "scanned"
              ? "已扫码，等待手机确认"
              : qrLogin?.status === "initializing"
                ? "正在生成登录二维码"
              : qrLogin?.status === "verification_required"
                ? "等待完成人脸验证"
              : qrLogin?.status === "browser_verification"
                ? "远程浏览器验证中"
              : qrLogin?.status === "finalizing"
                ? "正在验证并保存登录凭据"
                : qrLogin?.status === "completed"
                  ? "登录凭据已保存"
                  : qrLogin?.status === "expired"
                    ? "二维码已过期"
                    : qrLogin?.status === "error"
                      ? "登录失败"
                      : "等待扫码"}
          </Tag>
          {qrLogin?.error ? <Text type="danger">{privacyMaskEnabled ? "登录错误详情已隐藏" : qrLogin.error}</Text> : null}
        </Space>
      </Modal>

    </Layout>
  );
}
