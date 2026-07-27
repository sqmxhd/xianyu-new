"""Internal adapter boundary for the Xianyu messaging core.

The code in this package is owned by this project. XianYuApis is vendored under
``third_party/XianYuApis`` and updated through ordinary parent-repository
changes, while business integration code remains here.
"""

from .models import (
    AccountConfig,
    ChatMediaAttachment,
    ChatMessageEvent,
    ConversationPage,
    ConversationSummary,
    ConnectionState,
    Direction,
    MessageType,
    MessagePage,
    ProxyConfig,
    SendMessageResult,
    InteractiveVerification,
)
from .identity import ClientIdentity
from .ports import XianyuCoreClient
from .proxy import build_socks_proxy_url
from .client import XianyuCoreRuntime
from .product_models import (
    ManagedProduct,
    ProductActionItemResult,
    ProductBatchActionResult,
    ProductListResult,
    ProductOperationError,
    ProductPublishError,
    ProductImageData,
    ProductPublishRequest,
    ProductPublishResult,
    PublishedImage,
)
from .product_operations import MtopProductOperations
from .product_publisher import MtopProductPublisher
from .order_models import (
    BuyerOrder,
    BuyerOrderListResult,
    OrderActionError,
    OrderActionResult,
    OrderDetailSnapshot,
    OrderSyncError,
    SellerOrder,
    SellerOrderListResult,
)
from .order_actions import MtopOrderActions
from .buyer_order_operations import MtopBuyerOrderOperations
from .order_operations import MtopOrderOperations

__all__ = [
    "AccountConfig",
    "ClientIdentity",
    "ChatMediaAttachment",
    "ChatMessageEvent",
    "ConversationPage",
    "ConversationSummary",
    "ConnectionState",
    "Direction",
    "MessageType",
    "MessagePage",
    "ProxyConfig",
    "SendMessageResult",
    "InteractiveVerification",
    "XianyuCoreClient",
    "XianyuCoreRuntime",
    "build_socks_proxy_url",
    "MtopProductPublisher",
    "MtopProductOperations",
    "ManagedProduct",
    "ProductActionItemResult",
    "ProductBatchActionResult",
    "ProductListResult",
    "ProductOperationError",
    "ProductPublishError",
    "ProductImageData",
    "ProductPublishRequest",
    "ProductPublishResult",
    "PublishedImage",
    "MtopOrderOperations",
    "MtopOrderActions",
    "MtopBuyerOrderOperations",
    "BuyerOrder",
    "BuyerOrderListResult",
    "OrderActionError",
    "OrderActionResult",
    "OrderDetailSnapshot",
    "OrderSyncError",
    "SellerOrder",
    "SellerOrderListResult",
]
