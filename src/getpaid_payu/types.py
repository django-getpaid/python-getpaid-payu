from datetime import datetime
from enum import StrEnum
from enum import auto
from enum import unique
from typing import Any
from typing import Literal
from typing import TypedDict


class AutoName(StrEnum):
    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name.strip("_")


@unique
class PayMethodValue(AutoName):
    # Card-based payment methods
    c = auto()  #: card
    jp = auto()  #: ApplePay
    ap = auto()  #: GooglePay (AndroidPay)
    ma = auto()  #: Masterpass
    vc = auto()  #: Visa Checkout
    # Installments + Pay Later
    ai = auto()  #: Installments (PLN only)
    dp = auto()  #: Pay Later (PLN only)
    dpcz = auto()  #: Pay Later with Twisto (CZK only)
    # Polish pay-by-link online transfers (PLN)
    blik = auto()  #: BLIK
    m = auto()  #: mTransfer - mBank
    mtex = auto()  #: mTransfer mobilny - mBank
    w = auto()  #: Przelew24 - Santander
    o = auto()  #: Pekao24Przelew - Bank Pekao
    i = auto()  #: Płacę z Inteligo
    p = auto()  #: Płać z iPKO
    pkex = auto()  #: PayU Express Bank Pekao
    g = auto()  #: Płać z ING
    gbx = auto()  #: Płacę z GetIn Bank
    gbex = auto()  #: GetIn Bank PayU Express
    nlx = auto()  #: Płacę z Noble Bank
    nlex = auto()  #: Noble Bank PayU Express
    ib = auto()  #: Paylink Idea - IdeaBank
    l = auto()  #: Credit Agricole  # noqa: E741
    as_ = (
        auto()
    )  #: Płacę z T-mobile Usługi Bankowe dostarczane przez Alior Bank
    exas = auto()  #: PayU Express T-mobile Usługi Bankowe
    ab = auto()  #: Płacę z Alior Bankiem
    exab = auto()  #: PayU Express z Alior Bankiem
    ps = auto()  #: Płacę z Bankiem Nowym BFG S.A. (d. PBS)
    wm = auto()  #: Przelew z Millennium
    wc = auto()  #: Przelew z Citi Handlowego
    bo = auto()  #: Płać z BOŚ
    bnx = auto()  #: BNP Paribas
    bnex = auto()  #: BNP Paribas PayU Express
    bs = auto()  #: Banki Spółdzielcze
    nstb = auto()  #: Nest bank
    sgb = auto()  #: SGB-Bank
    plsb = auto()  #: Plus Bank
    b = auto()  #: Wire transfer (Przelew bankowy)
    # Czech pay-by-link online transfers (CZK)
    cs = auto()  #: Česká spořitelna
    mp = auto()  #: mBank
    kb = auto()  #: Komerční banka
    rf = auto()  #: Raiffeisenbank
    pg = auto()  #: Moneta Money Bank
    pv = auto()  #: Sberbank
    pf = auto()  #: Fio banka
    era = auto()  #: Poštovní spořitelna / Era
    cb = auto()  #: ČSOB
    uc = auto()  #: UniCredit
    bt = auto()  #: Bank transfer
    pt = auto()  #: Postal transfer
    # Slovak pay-by-link online transfers (EUR)
    posta = auto()  #: Poštová banka, a. s.
    sporo = auto()  #: Slovenská sporiteľňa, a. s.
    tatra = auto()  #: Tatra banka, a. s.
    uni = auto()  #: UniCredit Bank
    viamo = auto()  #: Viamo
    vub = auto()  #: Všeobecná úverová banka, a. s.
    # International payment methods
    gp = auto()  #: GiroPay
    pid = auto()  #: iDEAL
    it = auto()  #: InstantTransfer
    pscd = auto()  #: PaySafeCard
    sp = auto()  #: SafetyPay
    sb = auto()  #: Sofort Banking
    trp = auto()  #: TrustPay
    # Only for testing purposes
    t = auto()  #: test payment


class PayTypeValue(AutoName):
    PBL = auto()
    CARD_TOKEN = auto()
    INSTALLMENTS = auto()


class SpecData(TypedDict):
    name: str
    value: Any


class Currency(AutoName):
    BGN = auto()
    CHF = auto()
    CZK = auto()
    DKK = auto()
    EUR = auto()
    GBP = auto()
    HRK = auto()
    HUF = auto()
    NOK = auto()
    PLN = auto()
    RON = auto()
    RUB = auto()
    SEK = auto()
    UAH = auto()
    USD = auto()


class Language(AutoName):
    pl = auto()
    en = auto()
    cs = auto()
    bg = auto()
    da = auto()
    de = auto()
    el = auto()
    es = auto()
    et = auto()
    fi = auto()
    fr = auto()
    hr = auto()
    hu = auto()
    it = auto()
    lt = auto()
    lv = auto()
    pt = auto()
    ro = auto()
    ru = auto()
    sk = auto()
    sl = auto()
    sr = auto()
    sv = auto()
    tr = auto()
    uk = auto()


class PayMethodData(TypedDict):
    type: PayTypeValue
    value: PayMethodValue
    authorizationCode: str | int | None
    specificData: list[SpecData] | None


class PayMethods(TypedDict):
    payMethod: PayMethodData


class DeliveryData(TypedDict):
    street: str | None
    postalBox: str | None
    postalCode: str | None
    city: str | None
    state: str | None
    countryCode: str | None
    name: str | None
    recipientName: str | None
    recipientEmail: str | None
    recipientPhone: str | None


class BuyerData(TypedDict):
    customerIp: str | None
    extCustomerId: str | int | None
    email: str
    phone: str | None
    firstName: str | None
    lastName: str | None
    nin: str | None
    language: Language | None
    delivery: DeliveryData | None


class ProductData(TypedDict):
    name: str
    unitPrice: str | int
    quantity: str | int
    virtual: bool | None
    listingDate: str | datetime | None


class RefundStatus(AutoName):
    PENDING = auto()
    FINALIZED = auto()
    CANCELED = auto()


class ResponseStatus(AutoName):
    SUCCESS = auto()
    WARNING_CONTINUE_REDIRECT = auto()
    WARNING_CONTINUE_3DS = auto()
    WARNING_CONTINUE_CVV = auto()


class OrderStatus(AutoName):
    NEW = auto()
    PENDING = auto()
    CANCELED = auto()
    COMPLETED = auto()
    WAITING_FOR_CONFIRMATION = auto()


class OrderStatusObj(TypedDict):
    statusCode: ResponseStatus
    statusDesc: str | None


class OrderData(TypedDict):
    extOrderId: str | int
    notifyUrl: str | None
    customerIp: str
    merchantPosId: str | int
    description: str
    validityTime: str | int
    currencyCode: str
    totalAmount: str | int
    buyer: BuyerData
    products: list[ProductData]
    payMethods: PayMethods | None
    status: OrderStatus


class ReceivedOrderData(OrderData):
    orderId: str | int
    orderCreateDate: str | datetime


class OrderNotification(TypedDict):
    order: ReceivedOrderData
    localReceiptDateTime: str | datetime | None
    properties: list[SpecData] | None


class RefundInfo(TypedDict):  # request
    refundId: str | int
    amount: str | int | None
    extRefundId: str | int | None
    bankDescription: str | None
    type: Literal["REFUND_PAYMENT_STANDARD"] | None


class RefundRequest(TypedDict):
    orderId: str | int
    refund: RefundInfo


class RefundRecord(TypedDict):  # response
    refundId: str | int
    extRefundId: str | int | None
    amount: str | int
    currencyCode: Currency
    description: str
    creationDateTime: str | datetime
    status: RefundStatus
    statusDateTime: str | datetime


class RefundResponse(TypedDict):
    orderId: str | int
    refund: RefundRecord
    status: OrderStatusObj


class BaseResponse(TypedDict):
    orderId: str | int
    extOrderId: str | int


class CancellationResponse(BaseResponse):
    status: Literal[ResponseStatus.SUCCESS]


class PaymentResponse(BaseResponse):
    status: OrderStatusObj
    redirectUri: str


class ChargeRequest(TypedDict):
    orderId: str | int
    orderStatus: Literal[OrderStatus.COMPLETED]


class ChargeResponse(TypedDict):
    status: OrderStatusObj


class RetrieveOrderInfoResponse(TypedDict):
    orders: list[OrderData]
    status: OrderStatusObj
