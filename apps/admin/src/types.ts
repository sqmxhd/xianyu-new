export type RuntimeState =
  | "disabled"
  | "deleting"
  | "stopped"
  | "connecting"
  | "online"
  | "reconnecting"
  | "offline"
  | "auth_expired"
  | "risk_blocked"
  | "proxy_failed"
  | "error";

export type RuntimeRecoveryAction =
  | "none"
  | "reconnect"
  | "verify"
  | "relogin"
  | "fix_proxy";

export interface ProxyConfig {
  enabled: boolean;
  scheme: "socks5" | "socks5h";
  host?: string | null;
  port?: number | null;
  username?: string | null;
  password?: string | null;
}

export interface ProxyResource {
  proxy_id: string;
  name: string;
  enabled: boolean;
  scheme: "socks5" | "socks5h";
  host: string;
  port: number;
  username?: string | null;
  has_password: boolean;
  last_test_ok?: boolean | null;
  last_test_message?: string | null;
  last_test_latency_ms?: number | null;
  last_test_at?: string | null;
  exit_ip?: string | null;
  exit_ipv4?: string | null;
  exit_ipv6?: string | null;
  exit_country?: string | null;
  exit_region?: string | null;
  exit_city?: string | null;
  exit_isp?: string | null;
  exit_ipv6_country?: string | null;
  exit_ipv6_continent?: string | null;
  exit_checked_at?: string | null;
  last_platform_status?: number | null;
  created_at: string;
  updated_at: string;
}

export interface ProxyFormValues {
  name: string;
  enabled: boolean;
  scheme: "socks5" | "socks5h";
  host: string;
  port: number;
  username?: string | null;
  password?: string | null;
}

export interface RuntimeStatus {
  account_id: string;
  state: RuntimeState;
  recovery_action: RuntimeRecoveryAction;
  message?: string | null;
  last_error?: string | null;
  last_state_at?: string | null;
  last_online_at?: string | null;
  last_message_at?: string | null;
  message_count: number;
}

export interface AccountConnectionHealth {
  account_id: string;
  account_name: string;
  enabled: boolean;
  network_mode: "direct" | "socks5";
  proxy_id?: string | null;
  proxy_name?: string | null;
  running: boolean;
  online: boolean;
  heartbeat_age_seconds?: number | null;
  server_frame_age_seconds?: number | null;
  last_rpc_latency_ms?: number | null;
  last_rpc_error?: string | null;
  consecutive_rpc_failures: number;
  rpc_healthy: boolean;
  push_queue_depth: number;
  push_queue_dropped: number;
  push_inflight: number;
  active_pushes: string[];
  reconnect_count: number;
  last_disconnect_reason?: string | null;
  sync_queue_depth: number;
  side_effect_queue_depth: number;
  side_effect_queue_capacity: number;
  side_effect_queue_dropped: number;
  message_retry_pending: number;
  processing_errors_total: number;
  last_processing_error?: string | null;
  last_processing_error_at?: string | null;
}

export interface ExecutorHealth {
  name: string;
  max_workers: number;
  max_queue: number;
  capacity: number;
  active: number;
  queued: number;
  submitted: number;
  completed: number;
  failed: number;
  rejected: number;
  average_queue_wait_ms: number;
  average_duration_ms: number;
  last_duration_ms?: number | null;
}

export interface ProcessHealth {
  process_id: number;
  started_at: string;
  uptime_seconds: number;
  thread_count: number;
  event_loop: {
    status: "healthy" | "warning" | "critical";
    current_lag_ms: number;
    max_lag_ms_60s: number;
    p95_lag_ms_60s: number;
    sample_count: number;
    consecutive_warnings: number;
    warning_count: number;
    last_sample_at?: string | null;
  };
  executors: ExecutorHealth[];
  realtime: {
    subscribers: number;
    queued: number;
    capacity_per_subscriber: number;
    published: number;
    resync_required: number;
  };
  worker: {
    online: boolean;
    worker_id?: string | null;
    process_id?: number | null;
    concurrency?: number | null;
    active_tasks: string[];
    queued_tasks: number;
    heartbeat_age_seconds?: number | null;
    error?: string | null;
  };
}

export type CookieHealthState = "missing" | "unchecked" | "valid" | "renewing" | "invalid";

export interface CookieHealth {
  state: CookieHealthState;
  message?: string | null;
  checked_at?: string | null;
  last_renewed_at?: string | null;
  next_renewal_at?: string | null;
  last_failed_at?: string | null;
  verification_source?: string | null;
  failure_source?: string | null;
  error_kind?: string | null;
  manual_action_required: boolean;
}

export interface IMHealth {
  state: RuntimeState;
  available: boolean;
  message?: string | null;
  last_online_at?: string | null;
}

export type IMVerificationState =
  | "required"
  | "starting"
  | "ready"
  | "completing"
  | "completed"
  | "failed"
  | "expired"
  | "cancelled";

export interface IMVerification {
  verification_id: string;
  account_id: string;
  status: IMVerificationState;
  reason_code: string;
  message?: string | null;
  x5_cookie_names: string[];
  triggered_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  expires_at?: string | null;
  browser_available: boolean;
  browser_error?: string | null;
  vnc_available: boolean;
}

export interface IMVerificationTicket {
  ticket: string;
  expires_in: number;
}

export type AccountBrowserSessionState =
  | "starting"
  | "ready"
  | "closing"
  | "closed"
  | "expired"
  | "failed";

export interface AccountBrowserSession {
  session_id: string;
  account_id: string;
  status: AccountBrowserSessionState;
  message?: string | null;
  current_url?: string | null;
  proxy_enabled: boolean;
  browser_available: boolean;
  browser_error?: string | null;
  vnc_available: boolean;
  cdp_available: boolean;
  cookie_sync_status:
    | "pending"
    | "updated_from_browser"
    | "refreshed_from_browser"
    | "kept_local"
    | "auth_recovery"
    | "account_mismatch"
    | "unknown"
    | "failed";
  browser_cookie_status: "not_checked" | "valid" | "invalid" | "unknown";
  local_cookie_status: "not_checked" | "valid" | "invalid" | "unknown";
  fingerprint_snapshot?: BrowserFingerprintSnapshot | null;
  fingerprint_detection_status: "pending" | "collecting" | "ready" | "failed";
  fingerprint_detection_error?: string | null;
  started_at?: string | null;
  last_activity_at?: string | null;
  idle_expires_at?: string | null;
  max_expires_at?: string | null;
  expires_at?: string | null;
}

export interface BrowserProfileCleanup {
  account_id: string;
  deleted: boolean;
  message: string;
}

export type BrowserProfileStatus =
  | "running"
  | "stopped"
  | "busy"
  | "orphaned"
  | "temporary";

export interface BrowserProfile {
  profile_key: string;
  directory_name: string;
  profile_type: "account" | "qr" | "orphan";
  account_id?: string | null;
  account_name?: string | null;
  account_exists: boolean;
  size_bytes: number;
  created_at: string;
  updated_at: string;
  status: BrowserProfileStatus;
  session_id?: string | null;
  session_purpose?: string | null;
  vnc_available: boolean;
  current_url?: string | null;
  manageable: boolean;
  browser_engine?: BrowserEngine | null;
  config_revision?: number | null;
}

export type BrowserEngine = "system_chromium" | "fingerprint_chromium";
export type BrowserBrand = "Chrome" | "Edge" | "Opera" | "Vivaldi";
export type WebRTCPolicy = "proxy_only" | "disabled" | "browser_default";

export interface BrowserFingerprintSnapshot {
  schema_version: number;
  browser_engine: BrowserEngine;
  browser_version: string;
  target_platform: "windows" | "linux" | "macos";
  brand: BrowserBrand;
  observed_platform?: string | null;
  user_agent: string;
  ua_ch_platform?: string | null;
  ua_ch_brands: string[];
  language?: string | null;
  languages: string[];
  accept_language: string;
  timezone?: string | null;
  hardware_concurrency?: number | null;
  device_memory?: number | null;
  canvas_hash?: string | null;
  webgl_vendor?: string | null;
  webgl_renderer?: string | null;
  webgl_hash?: string | null;
  audio_hash?: string | null;
  fonts_hash?: string | null;
  detected_fonts: string[];
  client_rects_hash?: string | null;
  spoof_canvas: boolean;
  spoof_webgl: boolean;
  spoof_audio: boolean;
  spoof_fonts: boolean;
  spoof_client_rects: boolean;
  webrtc_policy: WebRTCPolicy;
  webrtc_candidate_types: string[];
  webrtc_api_available?: boolean | null;
  webrtc_blocked: boolean;
  webrtc_gathering_state?: string | null;
  webrtc_private_candidate_detected: boolean;
  webrtc_public_candidate_detected: boolean;
  webrtc_proxy_match?: boolean | null;
  webrtc_probe_configured: boolean;
  browser_egress_ips: string[];
  proxy_expected_ips: string[];
  browser_egress_match?: boolean | null;
  browser_egress_probe_source?: string | null;
  navigator_webdriver?: boolean | null;
  automation_window_markers: string[];
  has_window_chrome?: boolean | null;
  plugins_count?: number | null;
  notification_permission?: string | null;
  iframe_webdriver?: boolean | null;
  worker_webdriver?: boolean | null;
  cdp_stack_probe_detected?: boolean | null;
  automation_protection_level: "fingerprint_kernel" | "system_compatibility";
  risk_status: "pass" | "warning" | "risk" | "inconclusive";
  risk_findings: string[];
  config_revision: number;
  stability_status: "baseline" | "stable" | "changed";
  changed_fields: string[];
  observed_at: string;
}

export interface AccountBrowserIdentity {
  browser_engine: BrowserEngine;
  fingerprint_seed?: number | null;
  browser_version?: string | null;
  platform: "windows" | "linux" | "macos";
  platform_version: string;
  brand: BrowserBrand;
  language: string;
  accept_language: string;
  timezone: string;
  hardware_concurrency?: 4 | 8 | 12 | 16 | null;
  spoof_canvas: boolean;
  spoof_webgl: boolean;
  spoof_audio: boolean;
  spoof_fonts: boolean;
  spoof_client_rects: boolean;
  webrtc_policy: WebRTCPolicy;
  config_revision: number;
  user_agent?: string | null;
  dingtalk_user_agent?: string | null;
  transport_profile?: string | null;
  fingerprint_snapshot?: BrowserFingerprintSnapshot | null;
}

export interface BrowserBinary {
  version: string;
  executable_path: string;
  source: "upload" | "download" | "bundled" | "unknown";
  sha256?: string | null;
  size_bytes: number;
  installed_at?: string | null;
  active: boolean;
  valid: boolean;
  validation_message?: string | null;
}

export interface SystemBrowser {
  executable_path?: string | null;
  version?: string | null;
  available: boolean;
  validation_message?: string | null;
}

export interface BrowserRuntimeSetting {
  root_directory: string;
  standard_root_directory: string;
  system_browser: SystemBrowser;
  standard_browsers: BrowserBinary[];
  active_standard_version?: string | null;
  fingerprint_browsers: BrowserBinary[];
  active_fingerprint_version?: string | null;
  official_project_url: string;
  official_standard_project_url: string;
  active_vnc_account_id?: string | null;
  active_vnc_account_ids: string[];
  active_vnc_session_count: number;
  max_vnc_session_count: number;
  vnc_idle_timeout_seconds: number;
  vnc_max_session_seconds: number;
  http_transport: "requests";
  wss_transport: "websockets";
  tls_fingerprint_mode: "native_client";
  transport_alignment: string[];
  transport_warning: string;
}

export interface BrowserProfileAction {
  profile_key: string;
  stopped: boolean;
  deleted: boolean;
  message: string;
}

export interface RuntimeEvent {
  event_id: string;
  account_id: string;
  level: "info" | "warning" | "error";
  state: RuntimeState;
  message?: string | null;
  created_at: string;
}

export interface Conversation {
  account_id: string;
  account_name?: string | null;
  account_display_name?: string | null;
  account_remark?: string | null;
  platform: string;
  conversation_key?: string | null;
  conversation_id: string;
  peer_user_id?: string | null;
  peer_name?: string | null;
  peer_avatar_url?: string | null;
  item_id?: string | null;
  item_title?: string | null;
  item_price?: string | null;
  item_image_url?: string | null;
  item_url?: string | null;
  item_context_source?: string | null;
  item_context_at?: string | null;
  last_message_content?: string | null;
  last_message_type: "text" | "image" | "audio" | "card" | "system" | "unknown";
  last_message_direction?: "inbound" | "outbound" | null;
  last_message_at?: string | null;
  last_activity_at?: string | null;
  last_activity_content?: string | null;
  last_activity_type?: "text" | "image" | "audio" | "card" | "system" | "unknown" | null;
  last_activity_direction?: "inbound" | "outbound" | null;
  message_count: number;
  unread_count: number;
  platform_unread_count: number;
  viewer_unread_count?: number | null;
  needs_reply: boolean;
  last_inbound_at?: string | null;
  last_outbound_at?: string | null;
  manual_takeover_until?: string | null;
  manual_takeover_mode?: "auto" | "temporary" | "permanent";
  created_at: string;
  updated_at: string;
}

export type ConversationSyncState =
  | "pending"
  | "syncing"
  | "healthy"
  | "empty"
  | "error"
  | "offline";

export interface ConversationAccountSync {
  account_id: string;
  state: ConversationSyncState;
  conversation_count: number;
  rpc_healthy: boolean;
  last_attempt_at?: string | null;
  last_success_at?: string | null;
  last_error_at?: string | null;
  last_error?: string | null;
  consecutive_failures: number;
}

export interface ChatMessage {
  message_pk: string;
  account_id: string;
  conversation_id: string;
  message_id?: string | null;
  client_request_id?: string | null;
  direction: "inbound" | "outbound";
  message_type: "text" | "image" | "audio" | "card" | "system" | "unknown";
  content: string;
  peer_user_id?: string | null;
  peer_name?: string | null;
  item_id?: string | null;
  send_success?: boolean | null;
  send_status?: "uploading" | "sending" | "sent" | "failed" | null;
  send_error?: string | null;
  recalled_at?: string | null;
  attachments: MessageAttachment[];
  cards?: MessageCard[];
  raw_payload?: unknown;
  created_at_ms?: number | null;
  received_at_ms?: number | null;
  created_at: string;
  received_at?: string | null;
}

export interface MessageAttachment {
  attachment_id: string;
  attachment_type: "image" | "audio";
  remote_url?: string | null;
  mime_type?: string | null;
  width?: number | null;
  height?: number | null;
  size_bytes?: number | null;
  sha256?: string | null;
  status: "uploading" | "sending" | "sent" | "failed";
  error?: string | null;
}

export interface ConversationPage {
  items: Conversation[];
  has_more: boolean;
  next_cursor?: number | string | null;
  source: "live" | "cache";
  connection_state: RuntimeState;
  stale: boolean;
  error?: string | null;
  account_statuses: ConversationAccountSync[];
}

export interface MessagePage {
  items: ChatMessage[];
  has_more: boolean;
  next_cursor?: number | null;
  source: "live" | "cache";
  connection_state: RuntimeState;
  stale: boolean;
  error?: string | null;
}

export interface MessageCard {
  card_id: string;
  account_id: string;
  conversation_id: string;
  message_pk: string;
  card_type: "product" | "order";
  item_id?: string | null;
  order_id?: string | null;
  title?: string | null;
  price?: string | null;
  status?: string | null;
  image_url?: string | null;
  url?: string | null;
  raw_summary?: unknown;
  created_at: string;
}

export interface SendTextFormValues {
  text: string;
}

export interface SendTextPayload extends SendTextFormValues {
  receiver_user_id: string;
}

export interface SendTextResult {
  success: boolean;
  account_id: string;
  conversation_id: string;
  message_id?: string | null;
  error?: string | null;
  message?: ChatMessage | null;
}

export interface SendImageResult extends SendTextResult {
  client_request_id: string;
}

export interface RecallMessageResult {
  success: boolean;
  account_id: string;
  conversation_id: string;
  message_pk: string;
  error?: string | null;
  message?: ChatMessage | null;
}

export interface PlatformBlacklistState {
  success: boolean;
  account_id: string;
  conversation_id: string;
  blocked?: boolean | null;
  error?: string | null;
}

export interface QuickPhrase {
  phrase_id: string;
  title: string;
  content: string;
  group_name: string;
  sort_order: number;
  last_used_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface QuickPhraseFormValues {
  title: string;
  content: string;
  group_name: string;
  sort_order: number;
}

export interface AdminUser {
  user_id: string;
  username: string;
  role: "admin" | "operator" | "viewer";
  enabled: boolean;
  privacy_mask_enabled: boolean;
  created_at: string;
  updated_at: string;
  last_login_at?: string | null;
  last_login_ip?: string | null;
  last_login_source?: string | null;
}

export interface UserFormValues {
  username: string;
  password?: string;
  role: AdminUser["role"];
  enabled: boolean;
}

export interface ClientAccessInfo {
  ip?: string | null;
  source: string;
  remote_addr?: string | null;
  cf_connecting_ip?: string | null;
  true_client_ip?: string | null;
  x_real_ip?: string | null;
  x_forwarded_for?: string | null;
}

export interface AuthToken {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: AdminUser;
}

export interface AuthSetupStatus {
  initialized: boolean;
  client: ClientAccessInfo;
}

export interface XianyuQRStatus {
  session_id: string;
  status: "initializing" | "pending" | "scanned" | "verification_required" | "browser_verification" | "finalizing" | "completed" | "expired" | "error";
  code_content?: string | null;
  face_code_content?: string | null;
  challenge_type: "none" | "face" | "slider" | "interactive" | "unknown";
  expires_in: number;
  account_id?: string | null;
  runtime_state?: RuntimeState | null;
  error?: string | null;
}

export type QRBrowserVerificationState =
  | "idle"
  | "starting"
  | "ready"
  | "completing"
  | "completed"
  | "failed"
  | "expired"
  | "cancelled";

export interface QRBrowserVerification {
  session_id: string;
  status: QRBrowserVerificationState;
  message?: string | null;
  expires_at?: string | null;
  browser_available: boolean;
  browser_error?: string | null;
  vnc_available: boolean;
}

export interface LoginFormValues {
  username?: string;
  password?: string;
}

export interface AccountAutoReplyStatus {
  account_id: string;
  enabled: boolean;
}

export interface AIProviderSetting {
  base_url?: string | null;
  model?: string | null;
  has_api_key: boolean;
  created_at: string;
  updated_at: string;
}

export interface AIProviderSettingFormValues {
  ai_base_url?: string | null;
  ai_api_key?: string | null;
  ai_model?: string | null;
}

export interface ManualTakeoverStatus {
  account_id: string;
  conversation_id: string;
  active: boolean;
  mode: "auto" | "temporary" | "permanent";
  until?: string | null;
}

export interface AutoReplyRule {
  rule_id: string;
  account_id?: string | null;
  user_id?: string | null;
  account_ids: string[];
  platform?: string | null;
  enabled: boolean;
  group_name?: string | null;
  keyword: string;
  trigger_type: "keyword" | "always" | "fallback";
  match_mode: "contains" | "exact";
  case_sensitive: boolean;
  message_type?: string | null;
  sender_user_id?: string | null;
  conversation_id?: string | null;
  item_id?: string | null;
  cooldown_seconds: number;
  action_type: "template" | "ai" | "skip";
  reply_text: string;
  priority: number;
  continue_matching: boolean;
  context_message_count: number;
  context_fields: string[];
  ai_system_prompt: string;
  ai_temperature: number;
  created_at: string;
  updated_at: string;
}

export interface AutoReplyRuleFormValues {
  enabled: boolean;
  group_name?: string | null;
  keyword: string;
  trigger_type: "keyword" | "always" | "fallback";
  match_mode: "contains" | "exact";
  case_sensitive: boolean;
  account_ids: string[];
  platform?: string | null;
  message_type?: string | null;
  sender_user_id?: string | null;
  conversation_id?: string | null;
  item_id?: string | null;
  cooldown_seconds: number;
  action_type: "template" | "ai" | "skip";
  reply_text: string;
  continue_matching: boolean;
  context_message_count: number;
  context_fields: string[];
  ai_system_prompt: string;
  ai_temperature: number;
}

export interface AutoReplyRuleIssue {
  severity: "warning" | "error";
  code: string;
  message: string;
  rule_ids: string[];
}

export interface AutoReplyPreviewRequest {
  account_id: string;
  content: string;
  message_type: "text" | "image" | "audio" | "card" | "system" | "unknown";
  sender_user_id?: string | null;
  conversation_id?: string | null;
  item_id?: string | null;
}

export interface AutoReplyPreviewGate {
  key: string;
  passed: boolean;
  message: string;
}

export interface AutoReplyPreviewRuleTrace {
  rule_id: string;
  name: string;
  matched: boolean;
  selected: boolean;
  message: string;
}

export interface AutoReplyPreviewResult {
  account_id: string;
  executable: boolean;
  should_reply: boolean;
  reason: string;
  action_type?: "template" | "ai" | "skip" | null;
  matched_rule_ids: string[];
  reply_preview?: string | null;
  ai_context: Record<string, unknown>;
  gates: AutoReplyPreviewGate[];
  traces: AutoReplyPreviewRuleTrace[];
}

export interface AutoReplyLog {
  log_id: string;
  user_id?: string | null;
  account_id: string;
  conversation_id: string;
  inbound_message_pk?: string | null;
  outbound_message_pk?: string | null;
  rule_id?: string | null;
  matched_keyword?: string | null;
  reply_text: string;
  success: boolean;
  error?: string | null;
  created_at: string;
}

export interface DeliveryTemplate {
  template_id: string;
  account_id: string;
  name: string;
  enabled: boolean;
  content: string;
  priority: number;
  created_at: string;
  updated_at: string;
}

export interface DeliveryTemplateFormValues {
  name: string;
  enabled: boolean;
  content: string;
  priority: number;
}

export interface DeliveryPrepareValues {
  receiver_user_id: string;
  template_id?: string | null;
  content?: string | null;
  card_id?: string | null;
  source_message_pk?: string | null;
  item_id?: string | null;
  order_id?: string | null;
  peer_name?: string | null;
}

export interface DeliveryRecord {
  record_id: string;
  order_pk?: string | null;
  account_id: string;
  conversation_id: string;
  receiver_user_id: string;
  template_id?: string | null;
  card_id?: string | null;
  source_message_pk?: string | null;
  send_message_pk?: string | null;
  item_id?: string | null;
  order_id?: string | null;
  content: string;
  status: "pending" | "sending" | "sent" | "failed" | "uncertain" | "cancelled";
  send_error?: string | null;
  created_at: string;
  updated_at: string;
  sent_at?: string | null;
}

export type OrderStatus =
  | "pending_payment"
  | "waiting_seller_delivery"
  | "paid_waiting_delivery"
  | "shipped"
  | "completed"
  | "closed"
  | "refunding"
  | "refunded"
  | "unknown";

export type OrderScope = "bought" | "sold";

export type OrderSyncState = "provisional" | "confirmed" | "stale" | "error";

export type OrderAction =
  | "confirm_shipping"
  | "offline_shipping"
  | "free_shipping"
  | "close_order"
  | "rate_buyer"
  | "refuse_refund";

export type OrderOperationStatus = "processing" | "succeeded" | "failed" | "uncertain";

export interface OrderActionAvailability {
  action: OrderAction;
  enabled: boolean;
  reason: string;
  label: string;
  danger: boolean;
}

export interface XianyuOrder {
  order_pk: string;
  account_id: string;
  account_name?: string | null;
  platform: string;
  platform_order_id?: string | null;
  trade_role: "seller" | "buyer" | "unknown";
  data_source?: string | null;
  first_seen_source?: string | null;
  platform_confirmed: boolean;
  sync_state: OrderSyncState;
  conversation_id: string;
  peer_user_id?: string | null;
  peer_name?: string | null;
  buyer_user_id?: string | null;
  buyer_name?: string | null;
  receiver_name?: string | null;
  receiver_phone?: string | null;
  receiver_address?: string | null;
  item_id?: string | null;
  title?: string | null;
  price?: string | null;
  quantity?: number | null;
  image_url?: string | null;
  status: OrderStatus;
  status_text?: string | null;
  platform_status?: string | null;
  platform_created_at?: string | null;
  platform_paid_at?: string | null;
  platform_completed_at?: string | null;
  is_bargain: boolean;
  seller_rate_status?: string | null;
  refund_status?: string | null;
  refund_id?: string | null;
  platform_refund_actions: string[];
  refund_refuse_options: Array<{
    id: string;
    name: string;
    proof_required?: boolean;
    proof_type?: string;
    has_negotiation?: boolean;
  }>;
  logistics_type?: string | null;
  carrier_code?: string | null;
  tracking_no?: string | null;
  platform_shipping_methods: string[];
  platform_shipping_context: Record<string, unknown>;
  source_message_pk?: string | null;
  last_event_at?: string | null;
  last_synced_at?: string | null;
  last_detail_synced_at?: string | null;
  headinfo_confirmed_at?: string | null;
  platform_capabilities: string[];
  platform_action_links: Record<string, string>;
  sync_error?: string | null;
  available_actions: OrderActionAvailability[];
  raw_summary?: unknown;
  created_at: string;
  updated_at: string;
}

export interface OrderEvent {
  event_pk: string;
  order_pk?: string | null;
  account_id: string;
  conversation_id: string;
  message_pk: string;
  platform_order_id?: string | null;
  item_id?: string | null;
  event_type: string;
  status: OrderStatus;
  status_text?: string | null;
  raw_summary?: unknown;
  created_at: string;
}

export interface OrderDetail extends XianyuOrder {
  events: OrderEvent[];
  delivery_records: DeliveryRecord[];
  operations: OrderOperation[];
}

export interface OrderOperation {
  operation_id: string;
  order_pk: string;
  account_id: string;
  platform_order_id: string;
  action: OrderAction;
  status: OrderOperationStatus;
  idempotency_key: string;
  requested_by?: string | null;
  pre_status?: string | null;
  post_status?: string | null;
  message?: string | null;
  error?: string | null;
  platform_code?: string | null;
  request_summary?: unknown;
  response_summary?: unknown;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface OrderOperationPreview {
  eligible: boolean;
  reasons: string[];
  action: OrderActionAvailability;
  order: XianyuOrder;
}

export interface OrderOperationExecuteResult {
  operation: OrderOperation;
  order: OrderDetail;
}

export interface OrderSyncSetting {
  account_id: string;
  scope: OrderScope;
  sync_enabled: boolean;
  pending_interval_seconds: number;
  full_interval_minutes: number;
  jitter_seconds: number;
  last_sync_at?: string | null;
  last_pending_sync_at?: string | null;
  last_full_sync_at?: string | null;
  last_sync_status?: string | null;
  last_sync_error?: string | null;
  next_pending_sync_at?: string | null;
  next_full_sync_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface OrderAccountSummary {
  account_id: string;
  account_name: string;
  scope: OrderScope;
  enabled: boolean;
  runtime_state: RuntimeState;
  total_count: number;
  active_count: number;
  pending_count: number;
  refunding_count: number;
  setting: OrderSyncSetting;
}

export interface OrderSyncRun {
  run_id: string;
  account_id: string;
  scope: OrderScope;
  mode: "full" | "pending";
  trigger: "manual" | "scheduled" | string;
  status: "pending" | "running" | "success" | "failed" | "cancelled";
  total_count: number;
  inserted_count: number;
  updated_count: number;
  skipped_count: number;
  error?: string | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface OrderSyncEnqueueResult {
  run: OrderSyncRun;
  background_task: BackgroundTask;
}

export interface OrderDeliveryPreview {
  eligible: boolean;
  reasons: string[];
  order: XianyuOrder;
  template_id?: string | null;
  content: string;
}

export interface DeliverySendResult {
  success: boolean;
  record: DeliveryRecord;
  message?: ChatMessage | null;
  error?: string | null;
}

export interface DeliveryAutomationSetting {
  account_id: string;
  enabled: boolean;
  mode: "manual_only" | "ws_text" | "platform_api";
  require_order_card: boolean;
  duplicate_guard_enabled: boolean;
  order_status_allowlist: string[];
  created_at: string;
  updated_at: string;
}

export interface DeliveryAutomationFormValues {
  enabled: boolean;
  mode: "manual_only" | "ws_text" | "platform_api";
  require_order_card: boolean;
  duplicate_guard_enabled: boolean;
  order_status_allowlist_text: string;
}

export interface DeliveryPreflightResult {
  eligible: boolean;
  account_id: string;
  record_id: string;
  mode: DeliveryAutomationSetting["mode"];
  reasons: string[];
  record: DeliveryRecord;
}

export interface ProductDraft {
  draft_id: string;
  account_id: string;
  title: string;
  description: string;
  price: string;
  original_price?: string | null;
  stock: number;
  category_id?: string | null;
  category_hint?: string | null;
  images: string[];
  delivery_choice: "free_shipping" | "distance" | "fixed" | "pickup_only";
  post_price?: string | null;
  can_self_pickup: boolean;
  location_mode: "account_default" | "region" | "selected" | "group_random";
  location?: ProductLocation | null;
  location_group_id?: string | null;
  status: "draft" | "ready" | "archived";
  created_at: string;
  updated_at: string;
}

export interface ProductDraftFormValues {
  title: string;
  description: string;
  price: string;
  original_price?: string | null;
  stock: number;
  category_id?: string | null;
  category_hint?: string | null;
  image_refs: string[];
  images_text: string;
  delivery_choice: ProductDraft["delivery_choice"];
  post_price?: string | null;
  can_self_pickup: boolean;
  location_mode: ProductDraft["location_mode"];
  location?: ProductLocation | null;
  region_path?: string[] | null;
  location_key?: string | null;
  location_group_id?: string | null;
  status: "draft" | "ready" | "archived";
}

export interface ProductLocation {
  prov: string;
  city: string;
  area: string;
  division_id: string;
  longitude: number;
  latitude: number;
  poi_id: string;
  poi_name: string;
}

export interface ProductLocationOption extends ProductLocation {
  location_id: string;
  label: string;
  source: "platform_common" | "platform_nearby" | "platform_selected" | string;
}

export interface ProductLocationListResult {
  items: ProductLocationOption[];
  data_source: "live" | "cache" | "stale";
  fetched_at: string;
  warning?: string | null;
}

export interface ProductRegion {
  region_code: string;
  parent_code: string;
  name: string;
  level: "province" | "city" | "district";
  longitude: number;
  latitude: number;
  selectable: boolean;
  prov: string;
  city: string;
  area: string;
}

export interface ProductRegionCatalog {
  source: string;
  version: string;
  items: ProductRegion[];
}

export interface PublishAddressRegionSelection {
  region_codes: string[];
  address_count: number;
}

export interface PublishAddressGroup {
  group_id: string;
  name: string;
  enabled: boolean;
  avoid_recent_count: number;
  account_ids: string[];
  address_count: number;
  created_at: string;
  updated_at: string;
}

export interface PublishAddressGroupFormValues {
  name: string;
  enabled: boolean;
  avoid_recent_count: number;
  account_ids: string[];
}

export interface PublishAddress extends ProductLocation {
  address_id: string;
  group_id: string;
  source_account_id?: string | null;
  platform_location_id?: string | null;
  region_code?: string | null;
  label: string;
  source: string;
  enabled: boolean;
  use_count: number;
  last_used_at?: string | null;
  last_verified_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProductImageAsset {
  asset_id: string;
  account_id: string;
  image_ref: string;
  original_filename: string;
  mime_type: string;
  width: number;
  height: number;
  size_bytes: number;
  sha256: string;
  upload_session_id?: string | null;
  state: "staged" | "retained" | "deleting" | string;
  expires_at?: string | null;
  last_referenced_at?: string | null;
  created_at: string;
}

export interface ProductImageArchiveRejected {
  filename: string;
  reason: string;
}

export interface ProductImageArchiveUploadResult {
  assets: ProductImageAsset[];
  ignored_non_image_count: number;
  rejected_images: ProductImageArchiveRejected[];
  skipped_limit_count: number;
}

export interface ProductPublishTask {
  task_id: string;
  account_id: string;
  draft_id?: string | null;
  mode: "manual_export" | "platform_api" | "browser_automation";
  status: "pending" | "running" | "success" | "verification_required" | "failed" | "cancelled";
  phase: string;
  unique_code: string;
  idempotency_key: string;
  snapshot: Record<string, unknown>;
  item_id?: string | null;
  item_url?: string | null;
  failure_kind?: string | null;
  error?: string | null;
  raw_result?: Record<string, unknown> | null;
  retry_of_task_id?: string | null;
  attempt_no: number;
  retryable: boolean;
  result_certainty?: "confirmed_success" | "confirmed_failed" | "published_unconfirmed" | "result_unknown" | string | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface ProductPublishEnqueueResult {
  publish_task: ProductPublishTask;
  background_task: BackgroundTask;
}

export type ProductPlatformStatus =
  | "selling"
  | "offline"
  | "deleted"
  | "not_selling"
  | "unknown";

export interface ManagedProductItem {
  account_id: string;
  item_id: string;
  title: string;
  price: string;
  category_id?: string | null;
  cover_url?: string | null;
  detail_url?: string | null;
  platform_item_status?: string | null;
  want_count?: number | null;
  want_text?: string | null;
  platform_status: ProductPlatformStatus;
  sync_state: string;
  missing_sync_count: number;
  last_seen_at?: string | null;
  last_synced_at?: string | null;
  last_polished_on?: string | null;
  last_polished_at?: string | null;
  published_at?: string | null;
  published_at_source: "platform" | "publish_task" | "unknown";
  created_at: string;
  updated_at: string;
}

export interface ProductLocalCleanupResult {
  account_id: string;
  item_id: string;
  deleted: boolean;
  hidden_publish_task_count: number;
}

export interface ProductSyncSetting {
  account_id: string;
  sync_enabled: boolean;
  sync_interval_minutes: number;
  sync_jitter_minutes: number;
  full_sync_interval_hours: number;
  publish_verify_delay_seconds: number;
  auto_polish_enabled: boolean;
  polish_hour: number;
  polish_jitter_minutes: number;
  last_sync_at?: string | null;
  last_full_sync_at?: string | null;
  last_sync_status?: string | null;
  last_sync_error?: string | null;
  next_sync_at?: string | null;
  last_polish_at?: string | null;
  next_polish_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProductAccountSummary {
  account_id: string;
  account_name: string;
  enabled: boolean;
  runtime_state: RuntimeState;
  selling_count: number;
  offline_count: number;
  unknown_count: number;
  setting: ProductSyncSetting;
}

export type ProductOperation = "sync" | "polish" | "offline" | "delete";
export type ProductOperationStatus =
  | "pending"
  | "running"
  | "success"
  | "partial_success"
  | "failed"
  | "verification_required";

export interface ProductOperationItem {
  result_id: string;
  run_id: string;
  item_id: string;
  status: string;
  message?: string | null;
  platform_code?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProductOperationRun {
  run_id: string;
  account_id: string;
  operation: ProductOperation;
  trigger: "manual" | "scheduled" | "publish";
  status: ProductOperationStatus;
  full_sync: boolean;
  requested_item_ids: string[];
  total_count: number;
  success_count: number;
  failed_count: number;
  skipped_count: number;
  error?: string | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  items: ProductOperationItem[];
}

export interface ProductOperationEnqueueResult {
  run: ProductOperationRun;
  background_task: BackgroundTask;
}

export interface BackgroundTask {
  task_id: string;
  account_id?: string | null;
  task_type: string;
  dedupe_key?: string | null;
  status: "pending" | "running" | "success" | "failed" | "cancelled";
  payload?: unknown;
  result?: unknown;
  error?: string | null;
  worker_id?: string | null;
  lease_expires_at?: string | null;
  run_after?: string | null;
  attempt_count: number;
  created_at: string;
  updated_at: string;
  queued_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface AuditLog {
  audit_id: string;
  actor: string;
  action: string;
  target: string;
  success: boolean;
  status_code?: number | null;
  error?: string | null;
  client_ip?: string | null;
  created_at: string;
}

export interface Account {
  account_id: string;
  remark?: string | null;
  display_name: string;
  platform: string;
  platform_user_id?: string | null;
  platform_display_name?: string | null;
  platform_avatar_url?: string | null;
  platform_identity_source?: string | null;
  platform_identity_checked_at?: string | null;
  sort_order: number;
  enabled: boolean;
  conversation_visible: boolean;
  chat_enabled: boolean;
  order_management_visible: boolean;
  product_management_visible: boolean;
  auto_reply_enabled: boolean;
  automation_owner_user_id?: string | null;
  has_cookie: boolean;
  network_mode: "direct" | "socks5";
  proxy_id?: string | null;
  proxy_name?: string | null;
  proxy: ProxyConfig;
  browser_identity: AccountBrowserIdentity;
  runtime: RuntimeStatus;
  cookie_health: CookieHealth;
  im_health: IMHealth;
  cookie_updated_at?: string | null;
  cookie_update_source?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AccountFormValues {
  remark?: string | null;
  cookie?: string;
  enabled: boolean;
  proxy_id?: string | null;
  proxy?: ProxyConfig;
  browser_identity: AccountBrowserIdentity;
}

export interface AccountCookie {
  account_id: string;
  cookie: string;
  cookie_updated_at?: string | null;
}

export interface CookieRenewalAttempt {
  attempt_id: string;
  trigger: "manual" | "scheduled" | "auth_recovery";
  state: "running" | "applying" | "succeeded" | "failed" | "conflict";
  phase: "renewing" | "persisting" | "runtime" | "completed";
  message?: string | null;
  error_kind?: string | null;
  updated_cookie_names: string[];
  runtime_applied?: boolean | null;
  started_at: string;
  finished_at?: string | null;
  next_attempt_at?: string | null;
  duration_ms?: number | null;
}

export interface CookieRenewalStatus {
  account_id: string;
  state: "idle" | "running" | "applying" | "succeeded" | "failed" | "conflict";
  phase: "idle" | "renewing" | "persisting" | "runtime" | "completed";
  trigger?: "manual" | "scheduled" | "auth_recovery" | null;
  active_attempt_id?: string | null;
  message?: string | null;
  updated_cookie_names: string[];
  attempt_count: number;
  last_started_at?: string | null;
  last_succeeded_at?: string | null;
  last_verified_at?: string | null;
  last_verified_source?: string | null;
  last_failed_at?: string | null;
  last_finished_at?: string | null;
  last_error_kind?: string | null;
  last_error_source?: string | null;
  manual_action_required: boolean;
  runtime_applied?: boolean | null;
  next_attempt_at?: string | null;
  cookie_updated_at?: string | null;
  cookie_update_source?: string | null;
  recent_attempts: CookieRenewalAttempt[];
  updated_at?: string | null;
}

export interface ProxyTestResult {
  ok: boolean;
  proxy_url?: string | null;
  message: string;
  latency_ms?: number | null;
  exit_ip?: string | null;
  exit_ipv4?: string | null;
  exit_ipv6?: string | null;
  exit_country?: string | null;
  exit_region?: string | null;
  exit_city?: string | null;
  exit_isp?: string | null;
  exit_ipv6_country?: string | null;
  exit_ipv6_continent?: string | null;
  platform_status_code?: number | null;
}

export interface ChatwootConfig {
  config_id: string;
  enabled: boolean;
  account_alerts_enabled: boolean;
  offline_alert_delay_seconds: number;
  base_url: string;
  inbox_identifier: string;
  chatwoot_inbox_id?: number | null;
  webhook_secret: string;
  client_hmac_token?: string | null;
  api_access_token?: string | null;
  chatwoot_account_id?: number | null;
  has_webhook_secret: boolean;
  has_client_hmac_token: boolean;
  has_api_access_token: boolean;
  full_outbound_sync_enabled: boolean;
  account_grouping_enabled: boolean;
  managed_inbox_count: number;
  callback_path: string;
  callback_url: string;
  status: string;
  last_error?: string | null;
  last_webhook_at?: string | null;
  last_push_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatwootConfigFormValues {
  enabled: boolean;
  account_alerts_enabled: boolean;
  offline_alert_delay_seconds: number;
  base_url: string;
  inbox_identifier: string;
  callback_url: string;
  webhook_secret?: string;
  client_hmac_token?: string;
  clear_client_hmac_token?: boolean;
  chatwoot_account_id?: number | null;
  api_access_token?: string;
  clear_api_access_token?: boolean;
}

export interface ChatwootTestResult {
  success: boolean;
  message: string;
  status_code?: number | null;
}

export interface WebNotificationConfig {
  config_id: string;
  enabled: boolean;
  has_custom_sound: boolean;
  sound_filename?: string | null;
  sound_mime_type?: string | null;
  sound_size_bytes?: number | null;
  sound_sha256?: string | null;
  sound_url?: string | null;
  created_at: string;
  updated_at: string;
}
