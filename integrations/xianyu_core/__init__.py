"""Internal adapter boundary for the Xianyu messaging core.

The code in this package is owned by this project. Upstream protocol code
under ``third_party/XianYuApis`` should stay unmodified so it can be refreshed
from GitHub without merge conflicts.
"""

from .models import (
    AccountConfig,
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
