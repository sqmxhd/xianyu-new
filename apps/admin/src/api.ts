import type {
  Account,
  AccountAutoReplyStatus,
  AccountConnectionHealth,
  AccountBrowserSession,
  AccountCookie,
  AccountFormValues,
  AdminUser,
  AuthSetupStatus,
  AuthToken,
  AuditLog,
  AutoReplyLog,
  AutoReplyPreviewRequest,
  AutoReplyPreviewResult,
  AutoReplyRule,
  AutoReplyRuleFormValues,
  AutoReplyRuleIssue,
  AIProviderSetting,
  AIProviderSettingFormValues,
  BackgroundTask,
  BrowserProfile,
  BrowserProfileAction,
  BrowserProfileCleanup,
  BrowserRuntimeSetting,
  BrowserBinary,
  ChatMessage,
  ChatwootConfig,
  ChatwootConfigFormValues,
  ChatwootTestResult,
  Conversation,
  ConversationPage,
  CookieRenewalStatus,
  DeliveryAutomationFormValues,
  DeliveryAutomationSetting,
  DeliveryPrepareValues,
  DeliveryPreflightResult,
  DeliveryRecord,
  DeliverySendResult,
  DeliveryTemplate,
  DeliveryTemplateFormValues,
  IMVerification,
  IMVerificationTicket,
  MessageCard,
  MessagePage,
  ManualTakeoverStatus,
  OrderDeliveryPreview,
  OrderDetail,
  OrderAction,
  OrderAccountSummary,
  OrderOperationExecuteResult,
  OrderOperationPreview,
  OrderSyncEnqueueResult,
  OrderSyncRun,
  OrderSyncSetting,
  ProductDraft,
  ProductDraftFormValues,
  ProductImageArchiveUploadResult,
  ProductImageAsset,
  ProductLocationListResult,
  ProductLocalCleanupResult,
  ManagedProductItem,
  ProductAccountSummary,
  ProductOperationEnqueueResult,
  ProductOperationRun,
  ProductPlatformStatus,
  ProductSyncSetting,
  ProductRegionCatalog,
  PublishAddress,
  PublishAddressGroup,
  PublishAddressGroupFormValues,
  PublishAddressRegionSelection,
  ProductPublishEnqueueResult,
  ProductPublishTask,
  ProcessHealth,
  PlatformBlacklistState,
  ProxyFormValues,
  ProxyResource,
  ProxyTestResult,
  QuickPhrase,
  QuickPhraseFormValues,
  RecallMessageResult,
  RuntimeEvent,
  RuntimeStatus,
  SendImageResult,
  LoginFormValues,
  SendTextPayload,
  SendTextResult,
  UserFormValues,
  XianyuOrder,
  QRBrowserVerification,
  XianyuQRStatus
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiRequestError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    const message =
      typeof detail === "string"
        ? detail
        : detail && typeof detail === "object" && "message" in detail
          ? String(detail.message)
          : JSON.stringify(detail);
    const errorId =
      detail && typeof detail === "object" && "error_id" in detail
        ? String(detail.error_id)
        : "";
    super(errorId ? `${message}（错误编号：${errorId}）` : message);
    this.name = "ApiRequestError";
    this.status = status;
    this.detail = detail;
  }
}

export function getStoredAccessToken(): string {
  return typeof window !== "undefined" ? window.localStorage.getItem("xianyu_access_token") ?? "" : "";
}

export function setStoredAccessToken(token: string): void {
  if (typeof window !== "undefined") {
    window.localStorage.setItem("xianyu_access_token", token);
  }
}

export function clearStoredAccessToken(): void {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem("xianyu_access_token");
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const accessToken = getStoredAccessToken();
  const isFormData = init?.body instanceof FormData;
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(!isFormData ? { "Content-Type": "application/json" } : {}),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // Keep HTTP status text.
    }
    throw new ApiRequestError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

async function requestBlob(path: string): Promise<Blob> {
  const accessToken = getStoredAccessToken();
  const response = await fetch(`${API_BASE}${path}`, {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {}
  });
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // Keep HTTP status text.
    }
    throw new ApiRequestError(response.status, detail);
  }
  return response.blob();
}

export function listAccounts(): Promise<Account[]> {
  return request<Account[]>("/api/accounts");
}

export function getChatwootConfig(): Promise<ChatwootConfig> {
  return request<ChatwootConfig>("/api/settings/message-services/chatwoot");
}

export function saveChatwootConfig(
  values: ChatwootConfigFormValues
): Promise<ChatwootConfig> {
  return request<ChatwootConfig>("/api/settings/message-services/chatwoot", {
    method: "PUT",
    body: JSON.stringify(values)
  });
}

export function testChatwootConfig(): Promise<ChatwootTestResult> {
  return request<ChatwootTestResult>("/api/settings/message-services/chatwoot/test", {
    method: "POST"
  });
}

export function testChatwootAccountAlerts(): Promise<ChatwootTestResult> {
  return request<ChatwootTestResult>(
    "/api/settings/message-services/chatwoot/account-alert-test",
    { method: "POST" }
  );
}

export function reorderAccounts(accountIds: string[]): Promise<Account[]> {
  return request<Account[]>("/api/accounts/order", {
    method: "PUT",
    body: JSON.stringify({ account_ids: accountIds })
  });
}

export function getAccount(accountId: string): Promise<Account> {
  return request<Account>(`/api/accounts/${accountId}`);
}

export function listRuntimeHealth(): Promise<AccountConnectionHealth[]> {
  return request<AccountConnectionHealth[]>("/api/runtime-health");
}

export function getProcessHealth(): Promise<ProcessHealth> {
  return request<ProcessHealth>("/api/process-health");
}

export function getCookieRenewalStatus(accountId: string): Promise<CookieRenewalStatus> {
  return request<CookieRenewalStatus>(`/api/accounts/${accountId}/cookie-renewal`);
}

export function startCookieRenewal(accountId: string): Promise<CookieRenewalStatus> {
  return request<CookieRenewalStatus>(`/api/accounts/${accountId}/cookie-renewal`, {
    method: "POST"
  });
}

export function listProxies(): Promise<ProxyResource[]> {
  return request<ProxyResource[]>("/api/proxies");
}

export function createProxy(values: ProxyFormValues): Promise<ProxyResource> {
  return request<ProxyResource>("/api/proxies", {
    method: "POST",
    body: JSON.stringify(values)
  });
}

export function updateProxy(proxyId: string, values: Partial<ProxyFormValues>): Promise<ProxyResource> {
  return request<ProxyResource>(`/api/proxies/${proxyId}`, {
    method: "PUT",
    body: JSON.stringify(values)
  });
}

export function deleteProxy(proxyId: string): Promise<void> {
  return request<void>(`/api/proxies/${proxyId}`, { method: "DELETE" });
}

export function testProxy(proxyId: string): Promise<ProxyTestResult> {
  return request<ProxyTestResult>(`/api/proxies/${proxyId}/test`, { method: "POST" });
}

export function getAuthSetupStatus(): Promise<AuthSetupStatus> {
  return request<AuthSetupStatus>("/api/auth/setup-status");
}

export function getCurrentUser(): Promise<AdminUser> {
  return request<AdminUser>("/api/auth/me");
}

export function updateCurrentUserPreferences(values: {
  privacy_mask_enabled: boolean;
}): Promise<AdminUser> {
  return request<AdminUser>("/api/auth/preferences", {
    method: "PATCH",
    body: JSON.stringify(values)
  });
}

export function loginWithPassword(values: Required<Pick<LoginFormValues, "username" | "password">>): Promise<AuthToken> {
  return request<AuthToken>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(values)
  });
}

export function bootstrapAdminUser(
  values: Required<Pick<LoginFormValues, "username" | "password">>
): Promise<AuthToken> {
  return request<AuthToken>("/api/auth/bootstrap", {
    method: "POST",
    body: JSON.stringify(values)
  });
}

export function startXianyuQRLogin(values: {
  account_id?: string | null;
  remark?: string | null;
  client_request_id?: string | null;
  proxy_id?: string | null;
  browser_identity?: AccountFormValues["browser_identity"] | null;
}): Promise<XianyuQRStatus> {
  return request<XianyuQRStatus>("/api/xianyu-login/qr", {
    method: "POST",
    body: JSON.stringify(values)
  });
}

export function pollXianyuQRLogin(sessionId: string, signal?: AbortSignal): Promise<XianyuQRStatus> {
  return request<XianyuQRStatus>(`/api/xianyu-login/qr/${sessionId}/poll`, { method: "POST", signal });
}

export function cancelXianyuQRLogin(sessionId: string): Promise<void> {
  return request<void>(`/api/xianyu-login/qr/${sessionId}`, { method: "DELETE" });
}

export function startXianyuQRBrowserVerification(
  sessionId: string
): Promise<QRBrowserVerification> {
  return request<QRBrowserVerification>(
    `/api/xianyu-login/qr/${sessionId}/browser-verification/start`,
    { method: "POST" }
  );
}

export function completeXianyuQRBrowserVerification(
  sessionId: string
): Promise<XianyuQRStatus> {
  return request<XianyuQRStatus>(
    `/api/xianyu-login/qr/${sessionId}/browser-verification/complete`,
    { method: "POST" }
  );
}

export function cancelXianyuQRBrowserVerification(
  sessionId: string
): Promise<QRBrowserVerification> {
  return request<QRBrowserVerification>(
    `/api/xianyu-login/qr/${sessionId}/browser-verification/cancel`,
    { method: "POST" }
  );
}

export function createXianyuQRBrowserVNCTicket(
  sessionId: string
): Promise<IMVerificationTicket> {
  return request<IMVerificationTicket>(
    `/api/xianyu-login/qr/${sessionId}/browser-verification/vnc-ticket`,
    { method: "POST" }
  );
}

export function listSystemUsers(): Promise<AdminUser[]> {
  return request<AdminUser[]>("/api/users");
}

export function createSystemUser(values: Required<Pick<UserFormValues, "username" | "password" | "role" | "enabled">>): Promise<AdminUser> {
  return request<AdminUser>("/api/users", {
    method: "POST",
    body: JSON.stringify(values)
  });
}

export function updateSystemUser(userId: string, values: Partial<Pick<UserFormValues, "password" | "role" | "enabled">>): Promise<AdminUser> {
  return request<AdminUser>(`/api/users/${userId}`, {
    method: "PUT",
    body: JSON.stringify(values)
  });
}

export function createAccount(values: AccountFormValues): Promise<Account> {
  return request<Account>("/api/accounts", {
    method: "POST",
    body: JSON.stringify(values)
  });
}

export function updateAccount(accountId: string, values: Partial<AccountFormValues>): Promise<Account> {
  return request<Account>(`/api/accounts/${accountId}`, {
    method: "PUT",
    body: JSON.stringify(values)
  });
}

export function updateAccountWorkspaceVisibility(
  accountId: string,
  values: Partial<
    Pick<
      Account,
      | "conversation_visible"
      | "chat_enabled"
      | "order_management_visible"
      | "product_management_visible"
    >
  >
): Promise<Account> {
  return request<Account>(`/api/accounts/${accountId}/workspace-visibility`, {
    method: "PUT",
    body: JSON.stringify(values)
  });
}

export function revealAccountCookie(accountId: string): Promise<AccountCookie> {
  return request<AccountCookie>(`/api/accounts/${accountId}/cookie/reveal`, {
    method: "POST"
  });
}

export function getAccountBrowserSession(accountId: string): Promise<AccountBrowserSession> {
  return request<AccountBrowserSession>(`/api/accounts/${accountId}/browser-session`);
}

export function listActiveAccountBrowserSessions(): Promise<AccountBrowserSession[]> {
  return request<AccountBrowserSession[]>("/api/browser-sessions");
}

export function startAccountBrowserSession(accountId: string): Promise<AccountBrowserSession> {
  return request<AccountBrowserSession>(`/api/accounts/${accountId}/browser-session`, {
    method: "POST"
  });
}

export function createAccountBrowserVNCTicket(
  sessionId: string
): Promise<IMVerificationTicket> {
  return request<IMVerificationTicket>(
    `/api/browser-sessions/${sessionId}/vnc-ticket`,
    { method: "POST" }
  );
}

export function closeAccountBrowserSession(sessionId: string): Promise<AccountBrowserSession> {
  return request<AccountBrowserSession>(`/api/browser-sessions/${sessionId}/close`, {
    method: "POST"
  });
}

export function detectAccountBrowserFingerprint(
  sessionId: string
): Promise<AccountBrowserSession> {
  return request<AccountBrowserSession>(
    `/api/browser-sessions/${sessionId}/fingerprint-detect`,
    { method: "POST" }
  );
}

export function touchAccountBrowserSession(
  sessionId: string
): Promise<AccountBrowserSession> {
  return request<AccountBrowserSession>(
    `/api/browser-sessions/${sessionId}/activity`,
    { method: "POST" }
  );
}

export function pasteAccountBrowserText(
  sessionId: string,
  text: string
): Promise<AccountBrowserSession> {
  return request<AccountBrowserSession>(
    `/api/browser-sessions/${sessionId}/paste-text`,
    {
      method: "POST",
      body: JSON.stringify({ text })
    }
  );
}

export function clearAccountBrowserProfile(accountId: string): Promise<BrowserProfileCleanup> {
  return request<BrowserProfileCleanup>(`/api/accounts/${accountId}/browser-profile`, {
    method: "DELETE"
  });
}

export function listBrowserProfiles(): Promise<BrowserProfile[]> {
  return request<BrowserProfile[]>("/api/browser-profiles");
}

export function getBrowserRuntimeSetting(): Promise<BrowserRuntimeSetting> {
  return request<BrowserRuntimeSetting>("/api/settings/browser-runtime");
}

export function uploadStandardBrowser(file: File): Promise<BrowserBinary> {
  const body = new FormData();
  body.append("file", file);
  return request<BrowserBinary>("/api/settings/browser-runtime/standard/upload", {
    method: "POST",
    body
  });
}

export function downloadStandardBrowser(): Promise<BrowserBinary> {
  return request<BrowserBinary>("/api/settings/browser-runtime/standard/download", {
    method: "POST"
  });
}

export function activateStandardBrowser(version: string | null): Promise<BrowserRuntimeSetting> {
  return request<BrowserRuntimeSetting>("/api/settings/browser-runtime/standard/active", {
    method: "PUT",
    body: JSON.stringify({ version })
  });
}

export function uploadFingerprintBrowser(file: File): Promise<BrowserBinary> {
  const body = new FormData();
  body.append("file", file);
  return request<BrowserBinary>("/api/settings/browser-runtime/fingerprint/upload", {
    method: "POST",
    body
  });
}

export function downloadFingerprintBrowser(): Promise<BrowserBinary> {
  return request<BrowserBinary>("/api/settings/browser-runtime/fingerprint/download", {
    method: "POST"
  });
}

export function activateFingerprintBrowser(version: string): Promise<BrowserBinary> {
  return request<BrowserBinary>("/api/settings/browser-runtime/fingerprint/active", {
    method: "PUT",
    body: JSON.stringify({ version })
  });
}

export function stopBrowserProfile(profileKey: string): Promise<BrowserProfileAction> {
  return request<BrowserProfileAction>(
    `/api/browser-profiles/${encodeURIComponent(profileKey)}/stop`,
    { method: "POST" }
  );
}

export function clearBrowserProfile(profileKey: string): Promise<BrowserProfileAction> {
  return request<BrowserProfileAction>(
    `/api/browser-profiles/${encodeURIComponent(profileKey)}`,
    { method: "DELETE" }
  );
}

export function deleteAccount(accountId: string): Promise<BackgroundTask> {
  return request<BackgroundTask>(`/api/accounts/${accountId}`, {
    method: "DELETE"
  });
}

export function startAccount(accountId: string): Promise<Account> {
  return request<Account>(`/api/accounts/${accountId}/start`, {
    method: "POST"
  });
}

export function getAccountIMVerification(accountId: string): Promise<IMVerification> {
  return request<IMVerification>(`/api/accounts/${accountId}/im-verification`);
}

export function startAccountIMVerification(accountId: string): Promise<IMVerification> {
  return request<IMVerification>(`/api/accounts/${accountId}/im-verification/start`, {
    method: "POST"
  });
}

export function completeIMVerification(verificationId: string): Promise<IMVerification> {
  return request<IMVerification>(`/api/im-verifications/${verificationId}/complete`, {
    method: "POST"
  });
}

export function cancelIMVerification(verificationId: string): Promise<IMVerification> {
  return request<IMVerification>(`/api/im-verifications/${verificationId}/cancel`, {
    method: "POST"
  });
}

export function createIMVerificationVNCTicket(
  verificationId: string
): Promise<IMVerificationTicket> {
  return request<IMVerificationTicket>(
    `/api/im-verifications/${verificationId}/vnc-ticket`,
    { method: "POST" }
  );
}

export function createIMVerificationVNCWebSocketUrl(ticket: string): string {
  const url = new URL(
    `${API_BASE}/api/im-verifications/vnc/${encodeURIComponent(ticket)}`,
    window.location.href
  );
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

export function startAllAccounts(): Promise<Account[]> {
  return request<Account[]>("/api/accounts/start-all", {
    method: "POST"
  });
}

export function stopAccount(accountId: string): Promise<RuntimeStatus> {
  return request<RuntimeStatus>(`/api/accounts/${accountId}/stop`, {
    method: "POST"
  });
}

export function stopAllAccounts(): Promise<RuntimeStatus[]> {
  return request<RuntimeStatus[]>("/api/accounts/stop-all", {
    method: "POST"
  });
}

export function listAccountRuntimeEvents(accountId: string, limit = 100): Promise<RuntimeEvent[]> {
  return request<RuntimeEvent[]>(`/api/accounts/${accountId}/runtime-events?limit=${limit}`);
}

export function listConversations(accountId: string, limit = 100): Promise<Conversation[]> {
  return request<Conversation[]>(`/api/accounts/${accountId}/conversations?limit=${limit}`);
}

export function listCachedConversations(
  accountId: string,
  limit = 20
): Promise<ConversationPage> {
  return request<ConversationPage>(`/api/accounts/${accountId}/im/conversations?limit=${limit}`);
}

export function listAggregateConversations(options: {
  accountId?: string | null;
  status?: "all" | "unread";
  limit?: number;
  cursor?: number | string | null;
} = {}): Promise<ConversationPage> {
  const params = new URLSearchParams({
    limit: String(options.limit ?? 100),
    status: options.status ?? "all"
  });
  if (options.accountId) {
    params.set("account_id", options.accountId);
  }
  if (options.cursor != null) {
    params.set("cursor", String(options.cursor));
  }
  return request<ConversationPage>(`/api/im/conversations?${params}`);
}

export function markConversationRead(
  accountId: string,
  conversationId: string
): Promise<Conversation> {
  return request<Conversation>(
    `/api/im/conversations/${accountId}/${encodeURIComponent(conversationId)}/read`,
    { method: "POST" }
  );
}

export function syncConversations(
  accountId: string,
  limit = 20,
  cursor?: number | null
): Promise<ConversationPage> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor != null) {
    params.set("cursor", String(cursor));
  }
  return request<ConversationPage>(`/api/accounts/${accountId}/im/conversations/sync?${params}`, {
    method: "POST"
  });
}

export function listMessages(
  accountId: string,
  conversationId: string,
  limit = 100
): Promise<ChatMessage[]> {
  return request<ChatMessage[]>(
    `/api/accounts/${accountId}/conversations/${encodeURIComponent(conversationId)}/messages?limit=${limit}`
  );
}

export function listCachedMessages(
  accountId: string,
  conversationId: string,
  limit = 20
): Promise<MessagePage> {
  return request<MessagePage>(
    `/api/accounts/${accountId}/im/conversations/${encodeURIComponent(conversationId)}/messages?limit=${limit}`
  );
}

export function syncMessages(
  accountId: string,
  conversationId: string,
  limit = 20,
  cursor?: number | null
): Promise<MessagePage> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor != null) {
    params.set("cursor", String(cursor));
  }
  return request<MessagePage>(
    `/api/accounts/${accountId}/im/conversations/${encodeURIComponent(conversationId)}/messages/sync?${params}`,
    { method: "POST" }
  );
}

export async function createRealtimeWebSocket(): Promise<WebSocket> {
  const result = await request<{ ticket: string; expires_in: number }>("/api/realtime-ticket", {
    method: "POST"
  });
  const url = new URL("/api/realtime", API_BASE || window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.searchParams.set("ticket", result.ticket);
  return new WebSocket(url);
}

export function listMessageCards(accountId: string, limit = 100): Promise<MessageCard[]> {
  return request<MessageCard[]>(`/api/accounts/${accountId}/message-cards?limit=${limit}`);
}

export function listConversationCards(
  accountId: string,
  conversationId: string,
  limit = 100
): Promise<MessageCard[]> {
  return request<MessageCard[]>(
    `/api/accounts/${accountId}/conversations/${encodeURIComponent(conversationId)}/cards?limit=${limit}`
  );
}

export function syncConversationItem(
  accountId: string,
  conversationId: string
): Promise<Conversation> {
  return request<Conversation>(
    `/api/accounts/${accountId}/conversations/${encodeURIComponent(conversationId)}/item/sync`,
    { method: "POST" }
  );
}

export function listOrders(filters: {
  accountId?: string | null;
  conversationId?: string | null;
  status?: string | null;
  tradeRole?: "seller" | "buyer" | "unknown" | "all";
  confirmedOnly?: boolean;
  managementVisibleOnly?: boolean;
  keyword?: string | null;
  limit?: number;
} = {}): Promise<XianyuOrder[]> {
  const params = new URLSearchParams({ limit: String(filters.limit ?? 100) });
  if (filters.accountId) params.set("account_id", filters.accountId);
  if (filters.conversationId) params.set("conversation_id", filters.conversationId);
  if (filters.status && filters.status !== "all") params.set("status", filters.status);
  params.set("trade_role", filters.tradeRole ?? "seller");
  params.set("confirmed_only", String(filters.confirmedOnly ?? true));
  if (filters.managementVisibleOnly) params.set("management_visible_only", "true");
  if (filters.keyword?.trim()) params.set("keyword", filters.keyword.trim());
  return request<XianyuOrder[]>(`/api/orders?${params}`);
}

export function listOrderManagementAccounts(
  scope: "bought" | "sold" = "bought"
): Promise<OrderAccountSummary[]> {
  return request<OrderAccountSummary[]>(`/api/order-management/accounts?scope=${scope}`);
}

export function listOrderSyncRuns(
  accountId: string,
  scope: "bought" | "sold" = "bought",
  limit = 30
): Promise<OrderSyncRun[]> {
  return request<OrderSyncRun[]>(
    `/api/accounts/${accountId}/order-management/sync-runs?scope=${scope}&limit=${limit}`
  );
}

export function updateOrderSyncSetting(
  accountId: string,
  scope: "bought" | "sold",
  values: Pick<
    OrderSyncSetting,
    "sync_enabled" | "pending_interval_seconds" | "full_interval_minutes" | "jitter_seconds"
  >
): Promise<OrderSyncSetting> {
  return request<OrderSyncSetting>(
    `/api/accounts/${accountId}/order-management/settings?scope=${scope}`,
    { method: "PUT", body: JSON.stringify(values) }
  );
}

export function syncOrders(
  accountId: string,
  scope: "bought" | "sold",
  mode: "full" | "pending" = "full"
): Promise<OrderSyncEnqueueResult> {
  return request<OrderSyncEnqueueResult>(
    `/api/accounts/${accountId}/order-management/sync`,
    { method: "POST", body: JSON.stringify({ scope, mode }) }
  );
}

export function listConversationOrders(
  accountId: string,
  conversationId: string,
  limit = 100
): Promise<XianyuOrder[]> {
  return request<XianyuOrder[]>(
    `/api/accounts/${accountId}/conversations/${encodeURIComponent(conversationId)}/orders?limit=${limit}`
  );
}

export function getOrder(orderPk: string): Promise<OrderDetail> {
  return request<OrderDetail>(`/api/orders/${orderPk}`);
}

export function syncOrder(orderPk: string): Promise<OrderDetail> {
  return request<OrderDetail>(`/api/orders/${orderPk}/sync`, { method: "POST" });
}

export function previewOrderOperation(
  orderPk: string,
  action: OrderAction
): Promise<OrderOperationPreview> {
  return request<OrderOperationPreview>(`/api/orders/${orderPk}/operations/preview`, {
    method: "POST",
    body: JSON.stringify({ action })
  });
}

export function executeOrderOperation(
  orderPk: string,
  values: {
    action: OrderAction;
    idempotency_key: string;
    feedback?: string | null;
    close_reason?: string | null;
    tracking_no?: string | null;
    carrier_code?: string | null;
    carrier_brand_code?: string | null;
    sender_address_id?: string | null;
    refund_reason_id?: string | null;
    refund_proof?: Record<string, unknown> | null;
    refund_logistic_info?: Record<string, unknown> | null;
    refund_negotiation_apply?: Record<string, unknown> | null;
  }
): Promise<OrderOperationExecuteResult> {
  return request<OrderOperationExecuteResult>(`/api/orders/${orderPk}/operations`, {
    method: "POST",
    body: JSON.stringify(values)
  });
}

export function previewOrderDelivery(
  orderPk: string,
  values: { template_id?: string | null; content?: string | null }
): Promise<OrderDeliveryPreview> {
  return request<OrderDeliveryPreview>(`/api/orders/${orderPk}/delivery/preview`, {
    method: "POST",
    body: JSON.stringify(values)
  });
}

export function sendOrderDelivery(
  orderPk: string,
  values: { template_id?: string | null; content?: string | null }
): Promise<DeliverySendResult> {
  return request<DeliverySendResult>(`/api/orders/${orderPk}/delivery/send`, {
    method: "POST",
    body: JSON.stringify(values)
  });
}

export function sendText(
  accountId: string,
  conversationId: string,
  values: SendTextPayload
): Promise<SendTextResult> {
  return request<SendTextResult>(
    `/api/accounts/${accountId}/conversations/${encodeURIComponent(conversationId)}/send-text`,
    {
      method: "POST",
      body: JSON.stringify(values)
    }
  );
}

export function sendImage(
  accountId: string,
  conversationId: string,
  file: File,
  clientRequestId: string
): Promise<SendImageResult> {
  const body = new FormData();
  body.append("client_request_id", clientRequestId);
  body.append("image", file, file.name);
  return request<SendImageResult>(
    `/api/accounts/${accountId}/conversations/${encodeURIComponent(conversationId)}/send-image`,
    {
      method: "POST",
      body
    }
  );
}

export function recallMessage(
  accountId: string,
  conversationId: string,
  messagePk: string
): Promise<RecallMessageResult> {
  return request<RecallMessageResult>(
    `/api/accounts/${accountId}/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messagePk)}/recall`,
    { method: "POST" }
  );
}

export function getPlatformBlacklist(
  accountId: string,
  conversationId: string
): Promise<PlatformBlacklistState> {
  return request<PlatformBlacklistState>(
    `/api/accounts/${accountId}/conversations/${encodeURIComponent(conversationId)}/platform-blacklist`
  );
}

export function setPlatformBlacklist(
  accountId: string,
  conversationId: string,
  blocked: boolean
): Promise<PlatformBlacklistState> {
  return request<PlatformBlacklistState>(
    `/api/accounts/${accountId}/conversations/${encodeURIComponent(conversationId)}/platform-blacklist`,
    { method: "PUT", body: JSON.stringify({ blocked }) }
  );
}

export function listQuickPhrases(): Promise<QuickPhrase[]> {
  return request<QuickPhrase[]>("/api/quick-phrases");
}

export function createQuickPhrase(values: QuickPhraseFormValues): Promise<QuickPhrase> {
  return request<QuickPhrase>("/api/quick-phrases", {
    method: "POST",
    body: JSON.stringify(values)
  });
}

export function updateQuickPhrase(
  phraseId: string,
  values: QuickPhraseFormValues
): Promise<QuickPhrase> {
  return request<QuickPhrase>(`/api/quick-phrases/${phraseId}`, {
    method: "PUT",
    body: JSON.stringify(values)
  });
}

export function deleteQuickPhrase(phraseId: string): Promise<void> {
  return request<void>(`/api/quick-phrases/${phraseId}`, { method: "DELETE" });
}

export function touchQuickPhrase(phraseId: string): Promise<QuickPhrase> {
  return request<QuickPhrase>(`/api/quick-phrases/${phraseId}/used`, { method: "POST" });
}

export function setManualTakeover(
  accountId: string,
  conversationId: string,
  mode: "auto" | "temporary" | "permanent",
  minutes = 30
): Promise<ManualTakeoverStatus> {
  return request<ManualTakeoverStatus>(
    `/api/accounts/${accountId}/conversations/${encodeURIComponent(conversationId)}/manual-takeover`,
    { method: "POST", body: JSON.stringify({ mode, minutes }) }
  );
}

export function listBackgroundTasks(limit = 100): Promise<BackgroundTask[]> {
  return request<BackgroundTask[]>(`/api/tasks?limit=${limit}`);
}

export function listAuditLogs(limit = 100): Promise<AuditLog[]> {
  return request<AuditLog[]>(`/api/audit-logs?limit=${limit}`);
}

export function updateAccountAutoReply(
  accountId: string,
  enabled: boolean
): Promise<AccountAutoReplyStatus> {
  return request<AccountAutoReplyStatus>(`/api/accounts/${accountId}/auto-reply-enabled`, {
    method: "PUT",
    body: JSON.stringify({ enabled })
  });
}

export function getAIProviderSetting(): Promise<AIProviderSetting> {
  return request<AIProviderSetting>("/api/settings/ai-provider");
}

export function updateAIProviderSetting(
  values: Partial<AIProviderSettingFormValues> & { clear_api_key?: boolean }
): Promise<AIProviderSetting> {
  return request<AIProviderSetting>("/api/settings/ai-provider", {
    method: "PUT",
    body: JSON.stringify({
      ...values,
      base_url: values.ai_base_url,
      model: values.ai_model,
      api_key: values.ai_api_key,
      ai_base_url: undefined,
      ai_model: undefined,
      ai_api_key: undefined
    })
  });
}

export function listAutoReplyRules(): Promise<AutoReplyRule[]> {
  return request<AutoReplyRule[]>("/api/me/auto-reply/rules");
}

export function createAutoReplyRule(
  values: AutoReplyRuleFormValues
): Promise<AutoReplyRule> {
  return request<AutoReplyRule>("/api/me/auto-reply/rules", {
    method: "POST",
    body: JSON.stringify(values)
  });
}

export function reorderAutoReplyRules(ruleIds: string[]): Promise<AutoReplyRule[]> {
  return request<AutoReplyRule[]>("/api/me/auto-reply/rules/order", {
    method: "PUT",
    body: JSON.stringify({ rule_ids: ruleIds })
  });
}

export function listAutoReplyRuleIssues(): Promise<AutoReplyRuleIssue[]> {
  return request<AutoReplyRuleIssue[]>("/api/me/auto-reply/rules/issues");
}

export function previewAutoReply(
  values: AutoReplyPreviewRequest
): Promise<AutoReplyPreviewResult> {
  return request<AutoReplyPreviewResult>("/api/me/auto-reply/preview", {
    method: "POST",
    body: JSON.stringify(values)
  });
}

export function updateAutoReplyRule(
  ruleId: string,
  values: Partial<AutoReplyRuleFormValues>
): Promise<AutoReplyRule> {
  return request<AutoReplyRule>(`/api/me/auto-reply/rules/${ruleId}`, {
    method: "PUT",
    body: JSON.stringify(values)
  });
}

export function deleteAutoReplyRule(ruleId: string): Promise<void> {
  return request<void>(`/api/me/auto-reply/rules/${ruleId}`, {
    method: "DELETE"
  });
}

export function listAutoReplyLogs(limit = 100): Promise<AutoReplyLog[]> {
  return request<AutoReplyLog[]>(`/api/me/auto-reply/logs?limit=${limit}`);
}

export function listDeliveryTemplates(accountId: string): Promise<DeliveryTemplate[]> {
  return request<DeliveryTemplate[]>(`/api/accounts/${accountId}/delivery/templates`);
}

export function createDeliveryTemplate(
  accountId: string,
  values: DeliveryTemplateFormValues
): Promise<DeliveryTemplate> {
  return request<DeliveryTemplate>(`/api/accounts/${accountId}/delivery/templates`, {
    method: "POST",
    body: JSON.stringify(values)
  });
}

export function updateDeliveryTemplate(
  accountId: string,
  templateId: string,
  values: Partial<DeliveryTemplateFormValues>
): Promise<DeliveryTemplate> {
  return request<DeliveryTemplate>(`/api/accounts/${accountId}/delivery/templates/${templateId}`, {
    method: "PUT",
    body: JSON.stringify(values)
  });
}

export function deleteDeliveryTemplate(accountId: string, templateId: string): Promise<void> {
  return request<void>(`/api/accounts/${accountId}/delivery/templates/${templateId}`, {
    method: "DELETE"
  });
}

export function listDeliveryRecords(accountId: string, limit = 100): Promise<DeliveryRecord[]> {
  return request<DeliveryRecord[]>(`/api/accounts/${accountId}/delivery/records?limit=${limit}`);
}

export function getDeliveryAutomationSetting(accountId: string): Promise<DeliveryAutomationSetting> {
  return request<DeliveryAutomationSetting>(`/api/accounts/${accountId}/delivery/automation`);
}

export function updateDeliveryAutomationSetting(
  accountId: string,
  values: DeliveryAutomationFormValues
): Promise<DeliveryAutomationSetting> {
  return request<DeliveryAutomationSetting>(`/api/accounts/${accountId}/delivery/automation`, {
    method: "PUT",
    body: JSON.stringify({
      enabled: values.enabled,
      mode: values.mode,
      require_order_card: values.require_order_card,
      duplicate_guard_enabled: values.duplicate_guard_enabled,
      order_status_allowlist: values.order_status_allowlist_text
        .split(/[,\n]/)
        .map((item) => item.trim())
        .filter(Boolean)
    })
  });
}

export function checkDeliveryPreflight(
  accountId: string,
  recordId: string
): Promise<DeliveryPreflightResult> {
  return request<DeliveryPreflightResult>(
    `/api/accounts/${accountId}/delivery/records/${recordId}/preflight`,
    {
      method: "POST"
    }
  );
}

export function prepareDeliveryRecord(
  accountId: string,
  conversationId: string,
  values: DeliveryPrepareValues
): Promise<DeliveryRecord> {
  return request<DeliveryRecord>(
    `/api/accounts/${accountId}/conversations/${encodeURIComponent(conversationId)}/delivery/prepare`,
    {
      method: "POST",
      body: JSON.stringify(values)
    }
  );
}

export function sendDeliveryRecord(accountId: string, recordId: string): Promise<DeliverySendResult> {
  return request<DeliverySendResult>(`/api/accounts/${accountId}/delivery/records/${recordId}/send`, {
    method: "POST"
  });
}

export function enqueueDeliveryRecord(accountId: string, recordId: string): Promise<BackgroundTask> {
  return request<BackgroundTask>(`/api/accounts/${accountId}/delivery/records/${recordId}/enqueue`, {
    method: "POST"
  });
}

function productDraftBody(values: ProductDraftFormValues) {
  const externalImages = (values.images_text ?? "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
  return {
    title: values.title,
    description: values.description ?? "",
    price: values.price,
    original_price: values.original_price || null,
    stock: values.stock,
    category_id: values.category_id || null,
    category_hint: values.category_hint || null,
    images: [...(values.image_refs ?? []), ...externalImages],
    delivery_choice: values.delivery_choice,
    post_price: values.post_price || null,
    can_self_pickup: values.can_self_pickup,
    location_mode: values.location_mode,
    location: ["region", "selected"].includes(values.location_mode) ? values.location ?? null : null,
    location_group_id: values.location_mode === "group_random" ? values.location_group_id ?? null : null,
    status: values.status
  };
}

export function listProductImages(accountId: string, limit = 200): Promise<ProductImageAsset[]> {
  return request<ProductImageAsset[]>(`/api/accounts/${accountId}/products/images?limit=${limit}`);
}

export function uploadProductImage(
  accountId: string,
  file: File,
  uploadSessionId?: string
): Promise<ProductImageAsset> {
  const body = new FormData();
  body.append("image", file);
  if (uploadSessionId) body.append("upload_session_id", uploadSessionId);
  return request<ProductImageAsset>(`/api/accounts/${accountId}/products/images`, {
    method: "POST",
    body
  });
}

export function uploadProductImageArchive(
  accountId: string,
  archive: File,
  limit: number,
  uploadSessionId?: string
): Promise<ProductImageArchiveUploadResult> {
  const body = new FormData();
  body.append("archive", archive);
  body.append("limit", String(limit));
  if (uploadSessionId) body.append("upload_session_id", uploadSessionId);
  return request<ProductImageArchiveUploadResult>(
    `/api/accounts/${accountId}/products/images/archive`,
    { method: "POST", body }
  );
}

export function cleanupProductUploadSession(accountId: string, uploadSessionId: string): Promise<void> {
  return request<void>(
    `/api/accounts/${accountId}/products/upload-sessions/${encodeURIComponent(uploadSessionId)}`,
    { method: "DELETE" }
  );
}

export function getProductImageContent(accountId: string, assetId: string): Promise<Blob> {
  return requestBlob(`/api/accounts/${accountId}/products/images/${assetId}/content`);
}

export function getMessageAudio(
  accountId: string,
  conversationId: string,
  messagePk: string
): Promise<Blob> {
  return requestBlob(
    `/api/accounts/${encodeURIComponent(accountId)}/conversations/` +
      `${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messagePk)}/audio`
  );
}

export function deleteProductImage(accountId: string, assetId: string): Promise<void> {
  return request<void>(`/api/accounts/${accountId}/products/images/${assetId}`, {
    method: "DELETE"
  });
}

export function listProductDrafts(accountId: string, limit = 100): Promise<ProductDraft[]> {
  return request<ProductDraft[]>(`/api/accounts/${accountId}/products/drafts?limit=${limit}`);
}

export function listProductLocations(
  accountId: string,
  refresh = false
): Promise<ProductLocationListResult> {
  const query = refresh ? "?refresh=true" : "";
  return request<ProductLocationListResult>(`/api/accounts/${accountId}/products/locations${query}`);
}

export function listProductRegions(): Promise<ProductRegionCatalog> {
  return request<ProductRegionCatalog>("/api/product-regions");
}

export function listPublishAddressGroups(accountId?: string): Promise<PublishAddressGroup[]> {
  const query = accountId ? `?account_id=${encodeURIComponent(accountId)}` : "";
  return request<PublishAddressGroup[]>(`/api/product-address-groups${query}`);
}

export function createPublishAddressGroup(
  values: PublishAddressGroupFormValues
): Promise<PublishAddressGroup> {
  return request<PublishAddressGroup>("/api/product-address-groups", {
    method: "POST",
    body: JSON.stringify(values)
  });
}

export function updatePublishAddressGroup(
  groupId: string,
  values: PublishAddressGroupFormValues
): Promise<PublishAddressGroup> {
  return request<PublishAddressGroup>(`/api/product-address-groups/${groupId}`, {
    method: "PUT",
    body: JSON.stringify(values)
  });
}

export function deletePublishAddressGroup(groupId: string): Promise<void> {
  return request<void>(`/api/product-address-groups/${groupId}`, { method: "DELETE" });
}

export function listPublishAddresses(groupId: string): Promise<PublishAddress[]> {
  return request<PublishAddress[]>(`/api/product-address-groups/${groupId}/addresses`);
}

export function getPublishAddressRegions(
  groupId: string
): Promise<PublishAddressRegionSelection> {
  return request<PublishAddressRegionSelection>(
    `/api/product-address-groups/${groupId}/regions`
  );
}

export function replacePublishAddressRegions(
  groupId: string,
  regionCodes: string[]
): Promise<PublishAddressRegionSelection> {
  return request<PublishAddressRegionSelection>(
    `/api/product-address-groups/${groupId}/regions`,
    { method: "PUT", body: JSON.stringify({ region_codes: regionCodes }) }
  );
}

export function createPublishAddress(
  groupId: string,
  sourceAccountId: string,
  locationId: string
): Promise<PublishAddress> {
  return request<PublishAddress>(`/api/product-address-groups/${groupId}/addresses`, {
    method: "POST",
    body: JSON.stringify({ source_account_id: sourceAccountId, location_id: locationId })
  });
}

export function updatePublishAddress(
  groupId: string,
  addressId: string,
  enabled: boolean
): Promise<PublishAddress> {
  return request<PublishAddress>(
    `/api/product-address-groups/${groupId}/addresses/${addressId}`,
    { method: "PUT", body: JSON.stringify({ enabled }) }
  );
}

export function deletePublishAddress(groupId: string, addressId: string): Promise<void> {
  return request<void>(`/api/product-address-groups/${groupId}/addresses/${addressId}`, {
    method: "DELETE"
  });
}

export function createProductDraft(
  accountId: string,
  values: ProductDraftFormValues
): Promise<ProductDraft> {
  return request<ProductDraft>(`/api/accounts/${accountId}/products/drafts`, {
    method: "POST",
    body: JSON.stringify(productDraftBody(values))
  });
}

export function updateProductDraft(
  accountId: string,
  draftId: string,
  values: ProductDraftFormValues
): Promise<ProductDraft> {
  return request<ProductDraft>(`/api/accounts/${accountId}/products/drafts/${draftId}`, {
    method: "PUT",
    body: JSON.stringify(productDraftBody(values))
  });
}

export function deleteProductDraft(accountId: string, draftId: string): Promise<void> {
  return request<void>(`/api/accounts/${accountId}/products/drafts/${draftId}`, {
    method: "DELETE"
  });
}

export function listProductPublishTasks(accountId: string, limit = 100): Promise<ProductPublishTask[]> {
  return request<ProductPublishTask[]>(`/api/accounts/${accountId}/products/publish-tasks?limit=${limit}`);
}

export function createProductPublishTask(
  accountId: string,
  draftId: string,
  mode: ProductPublishTask["mode"] = "platform_api",
  idempotencyKey?: string
): Promise<ProductPublishTask> {
  return request<ProductPublishTask>(`/api/accounts/${accountId}/products/publish-tasks`, {
    method: "POST",
    body: JSON.stringify({ draft_id: draftId, mode, idempotency_key: idempotencyKey })
  });
}

export function createAndEnqueueProductPublishTask(
  accountId: string,
  draftId: string,
  mode: ProductPublishTask["mode"] = "platform_api",
  idempotencyKey?: string
): Promise<ProductPublishEnqueueResult> {
  return request<ProductPublishEnqueueResult>(
    `/api/accounts/${accountId}/products/publish-tasks:enqueue`,
    {
      method: "POST",
      body: JSON.stringify({ draft_id: draftId, mode, idempotency_key: idempotencyKey })
    }
  );
}

export function createAndEnqueueProductPublishJob(
  accountId: string,
  values: ProductDraftFormValues,
  uploadSessionId: string,
  idempotencyKey: string
): Promise<ProductPublishEnqueueResult> {
  const body = productDraftBody(values);
  return request<ProductPublishEnqueueResult>(
    `/api/accounts/${accountId}/product-management/publish-jobs`,
    {
      method: "POST",
      body: JSON.stringify({
        ...body,
        status: undefined,
        upload_session_id: uploadSessionId,
        idempotency_key: idempotencyKey,
        mode: "platform_api"
      })
    }
  );
}

export function retryProductPublishTask(
  accountId: string,
  taskId: string,
  idempotencyKey: string
): Promise<ProductPublishEnqueueResult> {
  return request<ProductPublishEnqueueResult>(
    `/api/accounts/${accountId}/products/publish-tasks/${taskId}/retry`,
    { method: "POST", body: JSON.stringify({ idempotency_key: idempotencyKey }) }
  );
}

export function enqueueProductPublishTask(accountId: string, taskId: string): Promise<BackgroundTask> {
  return request<BackgroundTask>(`/api/accounts/${accountId}/products/publish-tasks/${taskId}/enqueue`, {
    method: "POST"
  });
}

export function listProductManagementAccounts(): Promise<ProductAccountSummary[]> {
  return request<ProductAccountSummary[]>("/api/product-management/accounts");
}

export function listManagedProducts(
  accountId: string,
  options: { status?: ProductPlatformStatus | "all"; keyword?: string; limit?: number } = {}
): Promise<ManagedProductItem[]> {
  const query = new URLSearchParams();
  query.set("status", options.status ?? "all");
  query.set("limit", String(options.limit ?? 500));
  if (options.keyword?.trim()) query.set("keyword", options.keyword.trim());
  return request<ManagedProductItem[]>(
    `/api/accounts/${accountId}/product-management/items?${query.toString()}`
  );
}

export function deleteLocalManagedProduct(
  accountId: string,
  itemId: string
): Promise<ProductLocalCleanupResult> {
  return request<ProductLocalCleanupResult>(
    `/api/accounts/${accountId}/product-management/items/${encodeURIComponent(itemId)}/local`,
    { method: "DELETE" }
  );
}

export function listProductOperations(
  accountId: string,
  limit = 30
): Promise<ProductOperationRun[]> {
  return request<ProductOperationRun[]>(
    `/api/accounts/${accountId}/product-management/operations?limit=${limit}`
  );
}

export function updateProductSyncSetting(
  accountId: string,
  values: Partial<
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
  >
): Promise<ProductSyncSetting> {
  return request<ProductSyncSetting>(
    `/api/accounts/${accountId}/product-management/settings`,
    { method: "PUT", body: JSON.stringify(values) }
  );
}

export function syncManagedProducts(
  accountId: string,
  full = true
): Promise<ProductOperationEnqueueResult> {
  return request<ProductOperationEnqueueResult>(
    `/api/accounts/${accountId}/product-management/sync`,
    { method: "POST", body: JSON.stringify({ full }) }
  );
}

function enqueueManagedProductOperation(
  accountId: string,
  operation: "polish" | "offline" | "delete",
  itemIds: string[]
): Promise<ProductOperationEnqueueResult> {
  return request<ProductOperationEnqueueResult>(
    `/api/accounts/${accountId}/product-management/${operation}`,
    { method: "POST", body: JSON.stringify({ item_ids: itemIds }) }
  );
}

export function polishManagedProducts(
  accountId: string,
  itemIds: string[]
): Promise<ProductOperationEnqueueResult> {
  return enqueueManagedProductOperation(accountId, "polish", itemIds);
}

export function offlineManagedProducts(
  accountId: string,
  itemIds: string[]
): Promise<ProductOperationEnqueueResult> {
  return enqueueManagedProductOperation(accountId, "offline", itemIds);
}

export function deleteManagedProducts(
  accountId: string,
  itemIds: string[]
): Promise<ProductOperationEnqueueResult> {
  return enqueueManagedProductOperation(accountId, "delete", itemIds);
}
