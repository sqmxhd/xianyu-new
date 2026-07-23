import { InfoCircleOutlined, WarningOutlined } from "@ant-design/icons";
import { Space, Tag, Tooltip, Typography } from "antd";

import { formatBeijingTime } from "./time";
import { maskSensitive } from "./privacy";
import type { Account, ChatMessage, Conversation, MessageCard, RuntimeState } from "./types";

const stateText: Record<RuntimeState, string> = {
  disabled: "已禁用",
  deleting: "删除中",
  stopped: "已停止",
  connecting: "连接中",
  online: "在线",
  reconnecting: "重连中",
  offline: "离线",
  auth_expired: "认证失效",
  risk_blocked: "安全验证",
  proxy_failed: "代理失败",
  error: "错误"
};

const stateColor: Record<RuntimeState, string> = {
  disabled: "default",
  deleting: "processing",
  stopped: "default",
  connecting: "processing",
  online: "success",
  reconnecting: "warning",
  offline: "default",
  auth_expired: "error",
  risk_blocked: "volcano",
  proxy_failed: "error",
  error: "error"
};

const deliveryOrderStatusAllowlist = [
  "wait_seller_send_goods",
  "wait_seller_send",
  "waiting_seller_send",
  "待发货",
  "待卖家发货",
  "等待卖家发货"
];

const peerNameNoticeTitles = new Set([
  "你有一条新消息",
  "你有新的消息",
  "您有一条新消息",
  "发来一条新消息",
  "闲鱼新消息",
  "闲鱼消息",
  "交易消息",
  "系统消息",
  "快给ta一个评价吧~",
  "我完成了评价",
  "卖家人不错?送ta闲鱼小红花",
  "可以送ta闲鱼小红花吗~",
  "买家已拍下,待付款",
  "等待您发货",
  "等待你发货",
  "我发起了退款申请",
  "我将「退货退款」修改为「退款」",
  "闲鱼游戏交易安全提醒"
]);

function validPeerName(value?: string | null, peerUserId?: string | null) {
  const name = value?.trim();
  if (!name) {
    return undefined;
  }
  const comparable = name.normalize("NFKC").toLocaleLowerCase();
  if (
    peerNameNoticeTitles.has(comparable) ||
    comparable === peerUserId?.trim().toLocaleLowerCase()
  ) {
    return undefined;
  }
  return name;
}

export function StatusTag({ state }: { state: RuntimeState }) {
  return <Tag color={stateColor[state]}>{stateText[state]}</Tag>;
}

const cookieHealthMeta: Record<
  Account["cookie_health"]["state"],
  { label: string; color: string }
> = {
  missing: { label: "缺失", color: "error" },
  unchecked: { label: "待验证", color: "default" },
  valid: { label: "有效", color: "success" },
  renewing: { label: "续期中", color: "processing" },
  invalid: { label: "失效", color: "error" }
};

export function CookieHealthTag({
  account,
  privacyMaskEnabled = false
}: {
  account: Account;
  privacyMaskEnabled?: boolean;
}) {
  const meta = cookieHealthMeta[account.cookie_health.state];
  const tag = <Tag color={meta.color}>Cookie {meta.label}</Tag>;
  return account.cookie_health.message || account.cookie_health.checked_at ? (
    <Tooltip
      title={
        <Space direction="vertical" size={0}>
          <span>
            {privacyMaskEnabled && account.cookie_health.message
              ? "Cookie 检测详情已隐藏"
              : account.cookie_health.message || `Cookie ${meta.label}`}
          </span>
          {account.cookie_health.checked_at ? (
            <span>最近验证：{formatBeijingTime(account.cookie_health.checked_at)}</span>
          ) : null}
          {account.cookie_health.next_renewal_at ? (
            <span>下次续期：{formatBeijingTime(account.cookie_health.next_renewal_at)}</span>
          ) : null}
          {account.cookie_health.failure_source ? (
            <span>失败来源：{account.cookie_health.failure_source}</span>
          ) : null}
        </Space>
      }
    >
      <span className="account-health-tag">{tag}</span>
    </Tooltip>
  ) : tag;
}

export function IMHealthTag({
  account,
  privacyMaskEnabled = false
}: {
  account: Account;
  privacyMaskEnabled?: boolean;
}) {
  const tag = (
    <Tag color={stateColor[account.runtime.state]}>
      IM {stateText[account.runtime.state]}
    </Tag>
  );
  return account.runtime.message ? (
    <Tooltip title={privacyMaskEnabled ? "IM 状态详情已隐藏" : account.runtime.message}>
      <span className="account-health-tag">{tag}</span>
    </Tooltip>
  ) : tag;
}

export function AccountHealthTags({
  account,
  privacyMaskEnabled = false,
  direction = "vertical"
}: {
  account: Account;
  privacyMaskEnabled?: boolean;
  direction?: "vertical" | "horizontal";
}) {
  return (
    <Space className="account-health-tags" direction={direction} size={2}>
      <CookieHealthTag account={account} privacyMaskEnabled={privacyMaskEnabled} />
      <IMHealthTag account={account} privacyMaskEnabled={privacyMaskEnabled} />
    </Space>
  );
}

export function runtimeStateLabel(state: RuntimeState) {
  return stateText[state];
}

export function formatTime(value?: string | null) {
  return formatBeijingTime(value);
}

export function conversationTitle(conversation: Conversation) {
  return (
    validPeerName(conversation.peer_name, conversation.peer_user_id) ||
    conversation.peer_user_id ||
    conversation.conversation_id
  );
}

export function messageAuthor(
  message: ChatMessage,
  conversation?: Conversation | null,
  privacyMaskEnabled = false
) {
  if (message.direction === "outbound") {
    return "我";
  }
  const conversationName =
    (!message.peer_user_id || message.peer_user_id === conversation?.peer_user_id) &&
    validPeerName(conversation?.peer_name, conversation?.peer_user_id);
  const author = (
    validPeerName(message.peer_name, message.peer_user_id) ||
    conversationName ||
    message.peer_user_id ||
    "对方"
  );
  return maskSensitive(author, privacyMaskEnabled, "name");
}

export function isDeliverableMessageCard(card: MessageCard) {
  if (card.card_type !== "order") {
    return true;
  }
  const status = (card.status || "").trim().toLowerCase();
  return deliveryOrderStatusAllowlist.some((item) => status.includes(item));
}

export function messageCardLabel(card: MessageCard) {
  const type = card.card_type === "order" ? "订单" : "商品";
  const id = card.order_id || card.item_id || card.card_id;
  const title = card.title || "未命名卡片";
  const status = card.status ? ` / ${card.status}` : "";
  return `${type}｜${title}｜${id}${status}`;
}

export function formatItemPrice(value?: string | null) {
  const price = value?.trim();
  if (!price) {
    return "";
  }
  return /^[¥￥]/.test(price) ? price : `¥${price}`;
}

function extractImageUrl(value: unknown): string | null {
  if (!value) {
    return null;
  }
  if (typeof value === "string") {
    return /^https?:\/\//i.test(value) ? value : null;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      const found = extractImageUrl(item);
      if (found) {
        return found;
      }
    }
    return null;
  }
  if (typeof value === "object") {
    const objectValue = value as Record<string, unknown>;
    for (const key of ["imageUrl", "picUrl", "pictureUrl", "coverUrl", "url", "image"]) {
      const found = extractImageUrl(objectValue[key]);
      if (found) {
        return found;
      }
    }
    for (const nested of Object.values(objectValue)) {
      const found = extractImageUrl(nested);
      if (found) {
        return found;
      }
    }
  }
  return null;
}

export function renderChatMessageContent(chatMessage: ChatMessage, privacyMaskEnabled = false) {
  if (privacyMaskEnabled) {
    const label = chatMessage.message_type === "image" ? "消息图片已隐藏" : "消息内容已隐藏";
    return <div className="message-content privacy-message-placeholder">{label}</div>;
  }
  const productCard = chatMessage.cards?.find((card) => card.card_type === "product");
  if (productCard) {
    const content = (
      <>
        {productCard.image_url ? (
          <img src={productCard.image_url} alt={productCard.title || "商品"} />
        ) : null}
        <span className="message-product-card-details">
          <Typography.Text strong ellipsis title={productCard.title || undefined}>
            {productCard.title || "商品分享"}
          </Typography.Text>
          {productCard.price ? (
            <Typography.Text className="message-product-card-price">
              {formatItemPrice(productCard.price)}
            </Typography.Text>
          ) : null}
          <Typography.Text type="secondary" ellipsis>
            {productCard.item_id || "商品卡片"}
          </Typography.Text>
        </span>
      </>
    );
    return productCard.url ? (
      <a
        className="message-product-card"
        href={productCard.url}
        target="_blank"
        rel="noreferrer"
      >
        {content}
      </a>
    ) : (
      <div className="message-product-card">{content}</div>
    );
  }
  const imageUrl =
    chatMessage.message_type === "image"
      ? extractImageUrl(chatMessage.raw_payload) || extractImageUrl(chatMessage.content)
      : null;
  if (imageUrl) {
    return (
      <a href={imageUrl} target="_blank" rel="noreferrer">
        <img className="message-image" src={imageUrl} alt="消息图片" />
      </a>
    );
  }
  if (chatMessage.message_type === "image" && chatMessage.send_status === "uploading") {
    return <div className="message-content">图片上传中...</div>;
  }
  if (chatMessage.message_type === "image" && chatMessage.send_status === "sending") {
    return <div className="message-content">图片发送中...</div>;
  }
  if (chatMessage.message_type === "image" && chatMessage.send_status === "failed") {
    return <div className="message-content">图片发送失败</div>;
  }
  return <div className="message-content">{chatMessage.content || "[非文本消息]"}</div>;
}

export function isFailedOutboundMessage(chatMessage: ChatMessage) {
  return (
    chatMessage.direction === "outbound" &&
    (chatMessage.send_success === false || chatMessage.send_status === "failed")
  );
}

function failedMessageTitle(chatMessage: ChatMessage) {
  if (chatMessage.message_type === "image") {
    return "图片未发送成功";
  }
  if (chatMessage.message_type === "text") {
    return "文本未发送成功";
  }
  if (chatMessage.message_type === "card") {
    return "卡片未发送成功";
  }
  return "消息未发送成功";
}

function friendlySendError(error?: string | null) {
  const normalized = error?.trim();
  if (!normalized) {
    return "闲鱼未确认本次发送";
  }
  const comparable = normalized.toLocaleLowerCase();
  if (
    comparable.includes("account runtime is not running") ||
    comparable.includes("account session is not running") ||
    comparable.includes("im current") ||
    comparable.includes("not online")
  ) {
    return "闲鱼账户当前未连接";
  }
  if (
    comparable.includes("ssl") ||
    comparable.includes("eof") ||
    comparable.includes("connection") ||
    comparable.includes("max retries") ||
    comparable.includes("network")
  ) {
    return "网络连接异常，消息未能提交到闲鱼";
  }
  if (comparable.includes("timeout") || comparable.includes("timed out")) {
    return "请求超时，暂未确认闲鱼是否收到";
  }
  if (comparable.includes("receiver") || comparable.includes("接收方")) {
    return "当前会话缺少有效的接收方信息";
  }
  if (
    comparable.includes("denied") ||
    comparable.includes("reject") ||
    comparable.includes("forbidden") ||
    comparable.includes("403")
  ) {
    return "闲鱼拒绝了本次发送";
  }
  return "闲鱼未确认本次发送";
}

export function FailedMessageNotice({ chatMessage }: { chatMessage: ChatMessage }) {
  const technicalError = chatMessage.send_error?.trim();
  return (
    <div className="message-system-notice" role="status">
      <WarningOutlined className="message-system-icon" />
      <div className="message-system-content">
        <Typography.Text strong>{failedMessageTitle(chatMessage)}</Typography.Text>
        <Typography.Text type="secondary">{friendlySendError(technicalError)}</Typography.Text>
        {chatMessage.message_type === "text" && chatMessage.content ? (
          <Typography.Text
            className="message-system-preview"
            ellipsis={{ tooltip: chatMessage.content }}
          >
            未发送内容：{chatMessage.content}
          </Typography.Text>
        ) : null}
        {technicalError ? (
          <details className="message-system-details">
            <summary>查看错误详情</summary>
            <Typography.Text type="secondary">{technicalError}</Typography.Text>
          </details>
        ) : null}
      </div>
      <Typography.Text type="secondary" className="message-system-time">
        {formatTime(chatMessage.created_at)}
      </Typography.Text>
    </div>
  );
}

export function SystemMessageNotice({ chatMessage }: { chatMessage: ChatMessage }) {
  return (
    <div className="message-system-notice platform-notice" role="status">
      <InfoCircleOutlined className="message-system-icon" />
      <Typography.Text className="message-system-content">
        {chatMessage.content || "平台通知"}
      </Typography.Text>
      <Typography.Text type="secondary" className="message-system-time">
        {formatTime(chatMessage.created_at)}
      </Typography.Text>
    </div>
  );
}
