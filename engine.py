"""
价格行为学交易筛查引擎
独立于UI的纯逻辑层，供CLI和Web共同调用
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(Enum):
    RED = "red"
    ORANGE = "orange"
    YELLOW = "yellow"
    GREEN = "green"
    INFO = "info"

    @property
    def icon(self):
        icons = {"red": "🔴", "orange": "🟠", "yellow": "🟡", "green": "🟢", "info": "ℹ️"}
        return icons.get(self.value, "")


class MarketPhase(Enum):
    BREAKOUT = "breakout"
    TIGHT_CHANNEL = "tight_channel"
    BROAD_CHANNEL = "broad_channel"
    TRADING_RANGE = "trading_range"

    @property
    def label(self):
        labels = {
            "breakout": "突破 (Breakout)",
            "tight_channel": "窄通道 (Tight Channel)",
            "broad_channel": "宽通道 (Broad Channel)",
            "trading_range": "震荡区间 (Trading Range)",
        }
        return labels.get(self.value, "")


class Direction(Enum):
    LONG = "long"
    SHORT = "short"

    @property
    def label(self):
        return "做多" if self.value == "long" else "做空"


class TradeAlignment(Enum):
    WITH_TREND = "with_trend"
    AGAINST_TREND = "against_trend"

    @property
    def label(self):
        return "顺势" if self.value == "with_trend" else "逆势"


class EntryCount(Enum):
    FIRST = "first"
    SECOND = "second"
    THIRD = "third"
    FOURTH_PLUS = "fourth_plus"

    @property
    def label(self):
        labels = {"first": "H1/L1 第一次", "second": "H2/L2 第二次", "third": "H3/L3 第三次", "fourth_plus": "H4/L4+ 第四次+"}
        return labels.get(self.value, "")


class OrderType(Enum):
    STOP = "stop"
    LIMIT = "limit"
    MARKET = "market"

    @property
    def label(self):
        labels = {"stop": "Stop Order (突破单)", "limit": "Limit Order (限价单)", "market": "Market Order (市价单)"}
        return labels.get(self.value, "")


@dataclass
class Finding:
    severity: Severity
    message: str
    score_impact: int

    def to_dict(self):
        return {
            "severity": self.severity.value,
            "icon": self.severity.icon,
            "message": self.message,
            "score_impact": self.score_impact,
        }


@dataclass
class TradeInfo:
    symbol: str = ""
    direction: Optional[Direction] = None
    current_price: float = 0.0
    ema20_position: str = ""  # above / below / near
    market_phase: Optional[MarketPhase] = None
    alignment: Optional[TradeAlignment] = None
    entry_count: Optional[EntryCount] = None
    order_type: Optional[OrderType] = None
    has_stop_loss: bool = False
    stop_loss_type: str = ""
    stop_order_type: str = ""
    risk_pct: float = 0.0
    rr_ratio: float = 0.0
    has_target: bool = False
    target_basis: str = ""
    has_partial_tp: bool = False
    signal_k_score: int = 0
    wedge_overlap: str = ""
    is_second_entry: bool = False
    skunk_stop: bool = False
    range_position: str = ""
    gap_exists: bool = False
    multi_timeframe: bool = False
    third_push: bool = False
    has_third_push_plan: bool = False
    has_failure_plan: bool = False
    signal_type: str = ""


class ScreeningEngine:
    def __init__(self):
        self.trade = TradeInfo()
        self.findings: list[Finding] = []
        self.fatal_errors: list[str] = []
        self.score = 50

    def run_full_screening(self, data: dict) -> dict:
        """接收前端提交的表单数据，运行完整筛查，返回结果字典"""
        self._parse_input(data)
        self._screen_context()
        self._screen_direction()
        self._screen_entry()
        self._screen_risk()
        self._screen_target()
        return self._build_result()

    def _parse_input(self, data: dict):
        t = self.trade
        t.symbol = data.get("symbol", "").strip() or "未指定"
        t.current_price = float(data.get("current_price", 0) or 0)

        # Direction
        d = data.get("direction")
        if d:
            t.direction = Direction.LONG if d == "long" else Direction.SHORT

        # EMA20
        t.ema20_position = data.get("ema20_position", "near")

        # Market phase
        mp = data.get("market_phase")
        if mp:
            t.market_phase = MarketPhase(mp)

        # Alignment
        al = data.get("alignment")
        if al:
            t.alignment = TradeAlignment(al)

        # Entry count
        ec = data.get("entry_count")
        if ec:
            t.entry_count = EntryCount(ec)

        # Order type
        ot = data.get("order_type")
        if ot:
            t.order_type = OrderType(ot)

        t.has_stop_loss = data.get("has_stop_loss") == "true"
        t.stop_loss_type = data.get("stop_loss_type", "")
        t.stop_order_type = data.get("stop_order_type", "")
        t.risk_pct = float(data.get("risk_pct", 1) or 1)
        t.rr_ratio = float(data.get("rr_ratio", 1) or 1)

        t.has_target = data.get("has_target") == "true"
        t.target_basis = data.get("target_basis", "")
        t.has_partial_tp = data.get("has_partial_tp") == "true"

        t.gap_exists = data.get("gap_exists") == "true"
        t.range_position = data.get("range_position", "")
        t.wedge_overlap = data.get("wedge_overlap", "")
        t.third_push = data.get("third_push") == "true"
        t.has_third_push_plan = data.get("has_third_push_plan") == "true"
        t.has_failure_plan = data.get("has_failure_plan") == "true"
        t.skunk_stop = data.get("skunk_stop") == "true"

        # Signal K quality
        t.signal_k_score = int(data.get("signal_k_score", 50) or 50)
        t.signal_type = data.get("signal_type", "")

        # Derive is_second_entry
        t.is_second_entry = (t.entry_count == EntryCount.SECOND)

    # ── 筛查逻辑 ────────────────────────────────────

    def _screen_context(self):
        t = self.trade

        # 均线缺口
        if t.gap_exists and t.market_phase in (MarketPhase.BREAKOUT, MarketPhase.TIGHT_CHANNEL):
            self.findings.append(Finding(Severity.GREEN, "均线缺口存在 → 趋势极强信号", 5))

        # 第三段+
        if t.third_push:
            self.findings.append(Finding(Severity.YELLOW,
                "第三段及以上行情 → 随时可能转震荡或反转，注意减仓", -5))

        # 宽通道
        if t.market_phase == MarketPhase.BROAD_CHANNEL:
            self.findings.append(Finding(Severity.ORANGE,
                "宽通道 = 带倾斜角度的震荡区间，75%概率被反向突破，必须快速止盈", -5))

        # 震荡区间中轴
        if t.market_phase == MarketPhase.TRADING_RANGE and t.range_position == "middle":
            self.findings.append(Finding(Severity.YELLOW,
                "区间中轴位置 → 盈亏比最差，不建议在此开仓", -5))

    def _screen_direction(self):
        t = self.trade

        if t.alignment == TradeAlignment.WITH_TREND:
            self.findings.append(Finding(Severity.GREEN,
                "顺势交易 — 方向与市场背景一致", 10))
            if t.market_phase in (MarketPhase.BREAKOUT, MarketPhase.TIGHT_CHANNEL):
                self.findings.append(Finding(Severity.GREEN,
                    "强趋势顺势 — Always In 模式，胜率最高", 5))

        elif t.alignment == TradeAlignment.AGAINST_TREND:
            if t.market_phase in (MarketPhase.BREAKOUT, MarketPhase.TIGHT_CHANNEL):
                self.fatal_errors.append(
                    "🔴 致命：在窄通道/突破中逆势交易！\n"
                    "→ 第一次反转80%概率失败\n"
                    "→ 强趋势中逆势是极高风险行为\n"
                    "→ 建议：放弃这笔交易，或等待二次入场确认"
                )
                self.findings.append(Finding(Severity.RED,
                    "窄通道/突破中逆势 — 80%反转失败", -30))

            elif t.market_phase == MarketPhase.TRADING_RANGE:
                if t.range_position == "upper" and t.direction == Direction.LONG:
                    self.fatal_errors.append(
                        "🔴 致命：震荡区间上沿追涨（第二段陷阱）！\n"
                        "→ 80%突破会失败，不加仓不开仓"
                    )
                    self.findings.append(Finding(Severity.RED,
                        "震荡区间上沿追涨 — 第二段陷阱", -25))
                elif t.range_position == "lower" and t.direction == Direction.SHORT:
                    self.fatal_errors.append(
                        "🔴 致命：震荡区间下沿追空（第二段陷阱）！\n"
                        "→ 80%突破会失败，不加仓不开仓"
                    )
                    self.findings.append(Finding(Severity.RED,
                        "震荡区间下沿追空 — 第二段陷阱", -25))
                else:
                    self.findings.append(Finding(Severity.YELLOW,
                        "震荡区间逆势操作 — 需要更强的确认信号", -5))
            else:
                self.findings.append(Finding(Severity.ORANGE,
                    "逆势交易 — 需要更强的确认信号，建议等待二次入场", -10))

    def _screen_entry(self):
        t = self.trade

        # 信号类型
        if t.signal_type == "intuition":
            self.findings.append(Finding(Severity.RED,
                "纯直觉入场 — 没有客观信号依据！极易亏损", -15))

        # 信号K评分
        if t.signal_k_score >= 80:
            self.findings.append(Finding(Severity.GREEN, "信号K质量优秀 (≥80分)", 8))
        elif t.signal_k_score >= 60:
            self.findings.append(Finding(Severity.GREEN, "信号K质量良好 (60-79分)", 3))
        elif t.signal_k_score >= 40:
            self.findings.append(Finding(Severity.YELLOW, "信号K质量一般 (40-59分)", -3))
        else:
            self.findings.append(Finding(Severity.ORANGE, "信号K质量较差 (<40分)", -8))

        # 数K线
        if t.entry_count == EntryCount.SECOND:
            self.findings.append(Finding(Severity.GREEN,
                "H2/L2入场 — 黄金入场点，胜率最高！", 15))
        elif t.entry_count == EntryCount.THIRD:
            self.findings.append(Finding(Severity.GREEN,
                "H3/L3入场 — 楔形回调，好楔形胜率可达75%", 10))
        elif t.entry_count == EntryCount.FIRST:
            self.findings.append(Finding(Severity.YELLOW,
                "H1/L1入场 — 第一次入场80%可能失败，胜率较低", -10))
        elif t.entry_count == EntryCount.FOURTH_PLUS:
            self.findings.append(Finding(Severity.ORANGE,
                "H4/L4+ — 趋势极弱，可能已转震荡区间", -12))

        # 二次入场
        if t.is_second_entry:
            self.findings.append(Finding(Severity.GREEN,
                "二次入场 (Second Entry) — 高阶高胜率武器", 15))
        elif t.alignment == TradeAlignment.AGAINST_TREND and t.entry_count == EntryCount.FIRST:
            self.findings.append(Finding(Severity.ORANGE,
                "逆势 + 第一次入场 — 强烈建议等待二次入场", -8))

        # 楔形
        if t.wedge_overlap == "low":
            self.fatal_errors.append(
                "🔴 致命：坏楔形 — 无重叠的三推不是楔形，是窄通道！\n"
                "→ 反转胜率仅20%\n"
                "→ 在窄通道中逆势摸顶/抄底是严重错误"
            )
            self.findings.append(Finding(Severity.RED,
                "坏楔形(窄通道式) — 反转胜率仅20%", -25))
        elif t.wedge_overlap == "high":
            self.findings.append(Finding(Severity.GREEN,
                "好楔形(高重叠) — 反转胜率可达75%", 10))

        # 订单类型
        if t.market_phase == MarketPhase.TRADING_RANGE:
            if t.order_type == OrderType.STOP:
                self.fatal_errors.append(
                    "🔴 致命：震荡区间使用Stop Order追突破！\n"
                    "→ 80%突破会失败\n"
                    "→ 震荡区间应使用Limit Order高抛低吸"
                )
                self.findings.append(Finding(Severity.RED,
                    "震荡区间用Stop Order — 80%突破失败", -20))
            elif t.order_type == OrderType.LIMIT:
                self.findings.append(Finding(Severity.GREEN,
                    "震荡区间用Limit Order — 正确的订单类型", 10))

        if t.order_type == OrderType.MARKET:
            if t.market_phase in (MarketPhase.BREAKOUT, MarketPhase.TIGHT_CHANNEL):
                self.findings.append(Finding(Severity.GREEN,
                    "Always In行情用市价单 — 可以接受", 3))
            else:
                self.findings.append(Finding(Severity.YELLOW,
                    "非强趋势行情用市价单 — 建议改用Stop Order过滤信号", -5))

        if t.alignment == TradeAlignment.WITH_TREND and t.order_type == OrderType.STOP:
            self.findings.append(Finding(Severity.GREEN,
                "顺势 + Stop Order — 正确的入场方式", 10))

    def _screen_risk(self):
        t = self.trade

        # 止损检查
        if not t.has_stop_loss:
            self.fatal_errors.append(
                "🔴🔴 致命：没有保护性止损！\n"
                "→ 开仓后第一件事是设止损\n"
                "→ 不允许无止损交易\n"
                "→ 黑天鹅事件会毁掉你的账户"
            )
            self.findings.append(Finding(Severity.RED, "无止损交易！", -30))
        elif t.stop_loss_type == "mental":
            self.fatal_errors.append(
                "🔴 致命：心理止损等于没有止损！\n"
                "→ 你不会执行的，统计数据证明\n"
                "→ 必须在券商系统里挂好止损单"
            )
            self.findings.append(Finding(Severity.RED, "心理止损 = 没有止损", -25))
        else:
            self.findings.append(Finding(Severity.GREEN, "止损已设定在系统中", 5))

        # 止损订单类型
        if t.has_stop_loss and t.stop_order_type == "stop_limit":
            self.fatal_errors.append(
                "🔴 致命：Stop Limit止损可能滑过不成交！\n"
                "→ 极端行情(闪崩/跳空)时限价单无法执行\n"
                "→ 只用Stop Market，确保止损100%触发"
            )
            self.findings.append(Finding(Severity.RED, "Stop Limit止损 — 可能失效", -20))

        # 臭止损
        if t.skunk_stop:
            self.fatal_errors.append(
                "🔴 致命：臭止损 (Skunk Stop)！\n"
                "→ 别人（机构）在这个区域买入/卖出\n"
                "→ 你在最差的位置割肉\n"
                "→ 正确做法：要么提前敏锐离场，要么坚定依赖初始止损"
            )
            self.findings.append(Finding(Severity.RED, "臭止损 — 在最差位置割肉", -20))

        # 单笔风险
        if t.risk_pct <= 1:
            self.findings.append(Finding(Severity.GREEN, "单笔风险≤1% — 完美风控", 5))
        elif t.risk_pct <= 2:
            self.findings.append(Finding(Severity.GREEN, "单笔风险1-2% — 合理", 2))
        elif t.risk_pct <= 5:
            self.findings.append(Finding(Severity.YELLOW, "单笔风险2-5% — 偏高", -5))
        else:
            self.fatal_errors.append(
                "🔴 致命：单笔风险>5%！\n"
                "→ 即使好信号也不值得冒这么大风险\n"
                "→ 连续几次亏损会严重损害账户"
            )
            self.findings.append(Finding(Severity.RED, "单笔风险>5%", -20))

    def _screen_target(self):
        t = self.trade

        # 目标位
        if not t.has_target:
            self.findings.append(Finding(Severity.YELLOW,
                "没有明确目标位 — 容易拿不住或贪心", -8))
        else:
            tb = t.target_basis
            if tb and tb not in ("7", "other"):
                self.findings.append(Finding(Severity.GREEN, "目标位有客观测算依据", 5))
                if tb == "6":
                    self.findings.append(Finding(Severity.GREEN,
                        "基于Actual Risk — 最精确的动态目标位", 3))
            else:
                self.findings.append(Finding(Severity.YELLOW,
                    "目标位缺乏客观依据 — '感觉'不是策略", -5))

        # 盈亏比
        if t.rr_ratio >= 2.0:
            self.findings.append(Finding(Severity.GREEN,
                "盈亏比≥2:1 — 满足40%胜率+2R稳定盈利条件", 10))
        elif t.rr_ratio >= 1.0:
            self.findings.append(Finding(Severity.YELLOW,
                "盈亏比1:1~2:1 — 需要更高胜率才能盈利", -5))
        else:
            self.findings.append(Finding(Severity.RED,
                "盈亏比<1:1 — 即使赢了也不划算", -15))

        # 分批止盈
        if t.has_partial_tp:
            self.findings.append(Finding(Severity.GREEN,
                "分批止盈 (Smart Trade) — 锁定胜率的最佳策略", 5))
        else:
            self.findings.append(Finding(Severity.YELLOW,
                "没有分批止盈 — 建议至少在1R处止盈一半锁定胜率", -5))

        # 第三推
        if t.third_push:
            if t.has_third_push_plan:
                self.findings.append(Finding(Severity.GREEN,
                    "第三推后减仓 — 正确！大概率反转或震荡", 3))
            else:
                self.findings.append(Finding(Severity.YELLOW,
                    "第三推后全仓持有 — 建议至少减仓一部分", -5))

        # 失败预案
        if not t.has_failure_plan:
            self.findings.append(Finding(Severity.YELLOW,
                "没有失败预案 — 每个形态都有25%+失败概率，必须有离场计划", -5))

    # ── 结果生成 ─────────────────────────────────────

    def _build_result(self) -> dict:
        total_impact = sum(f.score_impact for f in self.findings)
        self.score = max(0, min(100, 50 + total_impact))

        if self.score >= 85:
            grade = "excellent"
            grade_label = "✅✅ 优质交易"
            advice = "满足大部分高胜率条件，可以执行。建议用OCO订单 Set and Forget (沃尔玛交易法)。"
        elif self.score >= 70:
            grade = "good"
            grade_label = "✅ 合格交易"
            advice = "核心条件满足，有一些瑕疵需注意。执行时格外关注瑕疵项，必要时缩小仓位。"
        elif self.score >= 50:
            grade = "questionable"
            grade_label = "⚠️ 存疑交易"
            advice = "多个条件不理想，建议缩小仓位(正常仓位1/3)或等待更好的入场点。"
        else:
            grade = "bad"
            grade_label = "🔴 不建议交易"
            advice = "违反铁律或核心条件缺失，强烈建议放弃这笔交易。市场永远在，不缺机会，缺的是本金。"

        tag = self._get_trade_tag()

        # 数学期望
        if self.trade.rr_ratio >= 2.0:
            expectation = "盈亏比≥2:1 + 胜率40%+ → 正期望系统 ✓\n例: 40%赚2R + 60%亏1R = +0.2R/笔"
        elif self.trade.rr_ratio >= 1.0:
            expectation = "盈亏比1:1~2:1 → 需要胜率>50%才能盈利"
        else:
            expectation = "盈亏比<1:1 → 即使胜率较高也很难长期盈利 ✗"

        # 沃尔玛提醒
        walmart = (self.score >= 70 and self.trade.has_stop_loss
                   and self.trade.has_target and self.trade.stop_loss_type == "system")

        return {
            "symbol": self.trade.symbol,
            "direction": self.trade.direction.label if self.trade.direction else "",
            "tag": tag,
            "score": self.score,
            "grade": grade,
            "grade_label": grade_label,
            "advice": advice,
            "expectation": expectation,
            "walmart": walmart,
            "fatal_errors": self.fatal_errors,
            "findings_green": [f.to_dict() for f in self.findings if f.severity == Severity.GREEN],
            "findings_yellow": [f.to_dict() for f in self.findings if f.severity in (Severity.YELLOW, Severity.ORANGE)],
            "findings_red": [f.to_dict() for f in self.findings if f.severity == Severity.RED],
        }

    def _get_trade_tag(self) -> str:
        if self.fatal_errors:
            return "🚫 违反铁律 — 不应执行"

        tags = []
        t = self.trade
        if t.alignment == TradeAlignment.WITH_TREND:
            if t.market_phase in (MarketPhase.BREAKOUT, MarketPhase.TIGHT_CHANNEL):
                tags.append("顺势强趋势")
            elif t.market_phase == MarketPhase.BROAD_CHANNEL:
                tags.append("顺势弱趋势")
            else:
                tags.append("震荡区间顺势")
        else:
            if t.market_phase == MarketPhase.TRADING_RANGE:
                tags.append("震荡区间逆势反转")
            else:
                tags.append("逆势反转")

        if t.entry_count == EntryCount.SECOND:
            tags.append("H2/L2")
        elif t.entry_count == EntryCount.THIRD:
            tags.append("H3/L3楔形")
        elif t.entry_count == EntryCount.FIRST:
            tags.append("H1/L1(风险)")

        if t.order_type:
            tags.append(t.order_type.label.split("(")[0].strip())

        return " + ".join(tags) if tags else "未分类"
