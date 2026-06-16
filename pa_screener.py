#!/usr/bin/env python3
"""
价格行为学交易前筛查系统
Price Action Pre-Trade Screening System

基于 Al Brooks 价格行为学课程，在交易者下单前
通过交互式问答筛查交易决策的合理性。
"""

import sys
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# Windows 控制台 UTF-8 支持
if sys.platform == "win32":
    os.system("")  # 启用 ANSI 转义序列
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ═══════════════════════════════════════════════════════
#  数据结构定义
# ═══════════════════════════════════════════════════════

class Severity(Enum):
    RED = "🔴"      # 致命错误，强烈阻止
    ORANGE = "🟠"   # 高度警惕
    YELLOW = "🟡"   # 需要注意
    GREEN = "🟢"    # 良好条件
    INFO = "ℹ️"     # 信息提示


class MarketPhase(Enum):
    BREAKOUT = "突破 (Breakout)"
    TIGHT_CHANNEL = "窄通道 (Tight Channel)"
    BROAD_CHANNEL = "宽通道 (Broad Channel)"
    TRADING_RANGE = "震荡区间 (Trading Range)"


class Direction(Enum):
    LONG = "做多"
    SHORT = "做空"


class TradeAlignment(Enum):
    WITH_TREND = "顺势"
    AGAINST_TREND = "逆势"


class EntryCount(Enum):
    FIRST = "第一次 (H1/L1)"
    SECOND = "第二次 (H2/L2)"
    THIRD = "第三次 (H3/L3)"
    FOURTH_PLUS = "第四次及以上 (H4/L4+)"


class OrderType(Enum):
    STOP = "Stop Order (突破单)"
    LIMIT = "Limit Order (限价单)"
    MARKET = "Market Order (市价单)"


@dataclass
class Finding:
    severity: Severity
    message: str
    score_impact: int  # 正数加分，负数扣分


@dataclass
class TradeInfo:
    symbol: str = ""
    direction: Optional[Direction] = None
    current_price: float = 0.0
    ema20_position: str = ""  # above/below/near
    market_phase: Optional[MarketPhase] = None
    alignment: Optional[TradeAlignment] = None
    entry_count: Optional[EntryCount] = None
    order_type: Optional[OrderType] = None
    has_stop_loss: bool = False
    stop_loss_type: str = ""  # system/mental/none
    stop_order_type: str = ""  # stop_market/stop_limit
    risk_pct: float = 0.0
    rr_ratio: float = 0.0
    has_target: bool = False
    target_basis: str = ""
    has_partial_tp: bool = False
    signal_k_score: int = 0  # 0-100
    wedge_overlap: str = ""  # high/low
    is_second_entry: bool = False
    skunk_stop: bool = False
    range_position: str = ""  # upper/middle/lower third
    gap_exists: bool = False
    multi_timeframe: bool = False
    third_push: bool = False


# ═══════════════════════════════════════════════════════
#  交互工具函数
# ═══════════════════════════════════════════════════════

def ask_choice(prompt: str, options: list[str], allow_back: bool = True) -> int:
    """显示选项并获取用户选择，返回1-based索引"""
    print(f"\n{prompt}")
    print("─" * 50)
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    if allow_back:
        print(f"  0. 返回上一步")

    while True:
        try:
            choice = input("\n请选择 [0-{}]: ".format(len(options))).strip()
            val = int(choice)
            if allow_back and val == 0:
                return 0
            if 1 <= val <= len(options):
                return val
            print("  ⚠ 无效选择，请重新输入")
        except (ValueError, EOFError):
            print("  ⚠ 请输入数字")


def ask_yes_no(prompt: str) -> bool:
    """是/否问题"""
    while True:
        answer = input(f"\n{prompt} [y/n]: ").strip().lower()
        if answer in ('y', 'yes', '是'):
            return True
        elif answer in ('n', 'no', '否'):
            return False
        print("  ⚠ 请输入 y 或 n")


def ask_number(prompt: str, min_val: float = 0, max_val: float = 100) -> float:
    """数值输入"""
    while True:
        try:
            val = float(input(f"\n{prompt}: ").strip())
            if min_val <= val <= max_val:
                return val
            print(f"  ⚠ 请输入 {min_val} 到 {max_val} 之间的数值")
        except (ValueError, EOFError):
            print("  ⚠ 请输入有效数字")


def show_header(title: str):
    print(f"\n{'═' * 56}")
    print(f"  {title}")
    print(f"{'═' * 56}")


def show_finding(f: Finding):
    print(f"  {f.severity.value} {f.message} [{f.score_impact:+d}分]")


# ═══════════════════════════════════════════════════════
#  筛查引擎
# ═══════════════════════════════════════════════════════

class ScreeningEngine:
    def __init__(self):
        self.trade = TradeInfo()
        self.findings: list[Finding] = []
        self.score = 50  # 基础分50，加减分后得出最终分数
        self.fatal_errors: list[str] = []
        self.bonuses: list[str] = []
        self.warnings: list[str] = []

    # ── A. 标的信息输入 ──────────────────────────────

    def input_trade_info(self):
        show_header("A. 交易基本信息")

        self.trade.symbol = input("\n  标的名称/代码 (如 ES, BTC, AAPL): ").strip()
        if not self.trade.symbol:
            self.trade.symbol = "未指定"

        dir_choice = ask_choice("交易方向:", ["做多 (Long/Buy)", "做空 (Short/Sell)"])
        self.trade.direction = Direction.LONG if dir_choice == 1 else Direction.SHORT

        self.trade.current_price = ask_number("当前价格 (不知道填0)", 0, 999999)

    # ── B. 市场环境识别 ──────────────────────────────

    def screen_context(self):
        show_header("B. 市场环境识别 (Context)")

        print("\n  💡 核心铁律：Context 永远大于信号K本身")
        print("  同一根K线在不同环境下含义截然相反！\n")

        # B1: 市场周期
        phase_choice = ask_choice(
            "当前市场处于哪个周期阶段？",
            [
                "突破 (Breakout) — 连续大实体K线，几乎无回调",
                "窄通道 (Tight Channel) — 单边趋势，回调仅1-2根K线",
                "宽通道 (Broad Channel) — 趋势延续但K线重叠多、回调深",
                "震荡区间 (Trading Range) — 大涨大跌交替，无一方占优",
            ]
        )
        phases = list(MarketPhase)
        self.trade.market_phase = phases[phase_choice - 1]

        # B2: EMA20位置
        ema_choice = ask_choice(
            "价格目前在EMA20的什么位置？",
            ["上方 (多头背景)", "下方 (空头背景)", "附近/纠缠 (模糊区域)"]
        )
        self.trade.ema20_position = ["above", "below", "near"][ema_choice - 1]

        # 追加问题
        if self.trade.market_phase in (MarketPhase.BREAKOUT, MarketPhase.TIGHT_CHANNEL):
            self._screen_strong_trend()
        elif self.trade.market_phase == MarketPhase.BROAD_CHANNEL:
            self._screen_broad_channel()
        elif self.trade.market_phase == MarketPhase.TRADING_RANGE:
            self._screen_trading_range()

    def _screen_strong_trend(self):
        """强趋势追加问题"""
        gap = ask_yes_no("窄通道中，是否存在均线缺口？(连续多根K线未触碰EMA20)")
        self.trade.gap_exists = gap
        if gap:
            self.findings.append(Finding(Severity.GREEN, "均线缺口存在 → 趋势极强信号", 5))

        push = ask_choice("窄通道/突破运行了第几段行情？",
                          ["第一段", "第二段", "第三段", "第四段及以上"])
        self.trade.third_push = (push >= 3)
        if push >= 3:
            self.findings.append(Finding(Severity.YELLOW,
                "第三段及以上行情 → 随时可能转震荡或反转，注意减仓", -5))

    def _screen_broad_channel(self):
        """宽通道追加问题"""
        overlap = ask_choice("K线重叠度如何？",
                             ["高重叠 (K线实体大量交叠)", "中等重叠", "低重叠 (K线较连续)"])
        if overlap == 1:
            self.findings.append(Finding(Severity.ORANGE,
                "高重叠宽通道 → 75%概率被反向突破，这是弱趋势！", -5))
        self.findings.append(Finding(Severity.YELLOW,
            "宽通道 = 带倾斜角度的震荡区间，必须快速止盈", -3))

    def _screen_trading_range(self):
        """震荡区间追加问题"""
        pos = ask_choice("当前价格在区间的什么位置？",
                         ["上沿1/3 (阻力区)", "中间1/3 (无边际区)", "下沿1/3 (支撑区)"])
        self.trade.range_position = ["upper", "middle", "lower"][pos - 1]

        if self.trade.range_position == "middle":
            self.findings.append(Finding(Severity.YELLOW,
                "区间中轴位置 → 盈亏比最差，不建议在此开仓", -5))

    # ── C. 交易方向确认 ──────────────────────────────

    def screen_direction(self):
        show_header("C. 交易方向确认")

        align = ask_choice("这是顺势交易还是逆势交易？",
                           ["顺势 — 方向与EMA20/大趋势一致",
                            "逆势 — 方向与EMA20/大趋势相反"])
        self.trade.alignment = TradeAlignment.WITH_TREND if align == 1 else TradeAlignment.AGAINST_TREND

        # 致命错误检测
        if self.trade.alignment == TradeAlignment.AGAINST_TREND:
            if self.trade.market_phase in (MarketPhase.BREAKOUT, MarketPhase.TIGHT_CHANNEL):
                self.fatal_errors.append(
                    "🔴 致命：在窄通道/突破中逆势交易！\n"
                    "   → 第一次反转80%概率失败\n"
                    "   → 强趋势中逆势是极高风险行为\n"
                    "   → 建议：放弃这笔交易，或等待二次入场确认"
                )
                self.findings.append(Finding(Severity.RED,
                    "窄通道/突破中逆势 — 80%反转失败", -30))

            elif self.trade.market_phase == MarketPhase.TRADING_RANGE:
                if self.trade.range_position in ("upper",) and self.trade.direction == Direction.LONG:
                    self.fatal_errors.append(
                        "🔴 致命：在震荡区间上沿追涨（第二段陷阱）！\n"
                        "   → 震荡区间第二段是陷阱，不加仓不开仓\n"
                        "   → 80%突破会失败"
                    )
                    self.findings.append(Finding(Severity.RED,
                        "震荡区间上沿追涨 — 第二段陷阱", -25))
                elif self.trade.range_position in ("lower",) and self.trade.direction == Direction.SHORT:
                    self.fatal_errors.append(
                        "🔴 致命：在震荡区间下沿追空（第二段陷阱）！\n"
                        "   → 震荡区间第二段是陷阱\n"
                        "   → 80%突破会失败"
                    )
                    self.findings.append(Finding(Severity.RED,
                        "震荡区间下沿追空 — 第二段陷阱", -25))
            else:
                self.findings.append(Finding(Severity.ORANGE,
                    "逆势交易 — 需要更强的确认信号，建议等待二次入场", -10))

        elif self.trade.alignment == TradeAlignment.WITH_TREND:
            self.findings.append(Finding(Severity.GREEN,
                "顺势交易 — 方向与市场背景一致", 10))
            if self.trade.market_phase in (MarketPhase.BREAKOUT, MarketPhase.TIGHT_CHANNEL):
                self.findings.append(Finding(Severity.GREEN,
                    "强趋势顺势 — Always In 模式，胜率最高", 5))

    # ── D. 入场信号检查 ──────────────────────────────

    def screen_entry(self):
        show_header("D. 入场信号检查")

        # D1: 信号类型
        signal = ask_choice("你看到了什么信号打算入场？",
                            [
                                "一根信号K线 (趋势K线收在极端)",
                                "双K线反转 (大阴+大阳 或 大阳+大阴)",
                                "多K线组合反转",
                                "结构形态 (双顶/双底/楔形)",
                                "数K线计数 (H1/H2/H3 或 L1/L2/L3)",
                                "EMA20回踩",
                                "突破某个关键位",
                                "其他/纯直觉",
                            ])

        if signal == 8:
            self.findings.append(Finding(Severity.RED,
                "纯直觉入场 — 没有客观信号依据！极易亏损", -15))

        # D2: 信号K评分
        if signal in (1, 2, 3, 4, 5):
            self._score_signal_k()

        # D3: 数K线计数
        if signal == 5 or ask_yes_no("是否涉及数K线计数 (H1/H2/L1/L2等)?"):
            self._check_bar_count()

        # D4: 楔形评估
        if signal == 4 or ask_yes_no("是否看到楔形(三推)结构?"):
            self._check_wedge()

        # D5: 二次入场
        if not self.trade.is_second_entry:
            second = ask_yes_no("这是二次入场 (Second Entry) 吗？")
            self.trade.is_second_entry = second
            if second:
                self.findings.append(Finding(Severity.GREEN,
                    "二次入场 — 高阶高胜率武器，胜率显著提升", 15))
            else:
                if self.trade.alignment == TradeAlignment.AGAINST_TREND:
                    self.findings.append(Finding(Severity.ORANGE,
                        "逆势 + 第一次入场 — 强烈建议等待二次入场", -8))

        # D6: 订单类型
        self._check_order_type()

    def _score_signal_k(self):
        """信号K质量评分"""
        show_header("D2. 信号K线质量评估")

        score = 0

        # 实体大小
        size = ask_choice("信号K线的实体大小（相对近期平均K线）？",
                          ["远大于平均", "略大于平均", "与平均相当", "小于平均"])
        size_scores = [3, 1, 0, -1]
        s = size_scores[size - 1]
        score += s
        if s > 0:
            self.findings.append(Finding(Severity.GREEN, f"信号K实体{'远大于' if s==3 else '略大于'}平均", s * 3))
        elif s < 0:
            self.findings.append(Finding(Severity.YELLOW, "信号K实体偏小", -3))

        # 收盘位置
        close = ask_choice("信号K线收盘位置？",
                           ["收在最极端 (最高/最低点附近)",
                            "收在实体2/3以上",
                            "收在中间",
                            "收在1/3以下"])
        close_scores = [3, 1, 0, -1]
        s = close_scores[close - 1]
        score += s
        if s >= 1:
            self.findings.append(Finding(Severity.GREEN, "信号K收盘位置优秀", s * 3))
        elif s < 0:
            self.findings.append(Finding(Severity.YELLOW, "信号K收盘位置差", -3))

        # 长影线
        wick = ask_yes_no("信号K线是否有长影线向你的方向？(如做多时有长下影线)")
        if wick:
            score += 2
            self.findings.append(Finding(Severity.GREEN,
                "长影线向交易方向 → 逆势方尝试失败的证据", 5))

        # 趋势K vs 震荡K
        trend = ask_choice("信号K线是趋势K还是震荡K？",
                           ["趋势K (实体占比>60%，影线小)",
                            "震荡K (十字星/影线占比大)"])
        if trend == 1:
            score += 2
            self.findings.append(Finding(Severity.GREEN, "趋势K线作为信号K", 2))
        else:
            score -= 1
            self.findings.append(Finding(Severity.YELLOW,
                "震荡K线作为信号K — 缺乏方向性，信号较弱", -3))

        self.trade.signal_k_score = max(0, min(100, score * 10 + 50))

    def _check_bar_count(self):
        """数K线计数检查"""
        count = ask_choice("这是第几次入场信号？",
                           [
                               "H1/L1 — 第一次入场",
                               "H2/L2 — 第二次入场 (黄金入场点)",
                               "H3/L3 — 第三次入场 (楔形回调)",
                               "H4/L4+ — 第四次及以上",
                           ])
        counts = list(EntryCount)
        self.trade.entry_count = counts[count - 1]

        if self.trade.entry_count == EntryCount.SECOND:
            self.trade.is_second_entry = True
            self.findings.append(Finding(Severity.GREEN,
                "H2/L2入场 — 黄金入场点，胜率最高！", 15))
        elif self.trade.entry_count == EntryCount.THIRD:
            self.findings.append(Finding(Severity.GREEN,
                "H3/L3入场 — 楔形回调，好楔形胜率可达75%", 10))
        elif self.trade.entry_count == EntryCount.FIRST:
            self.findings.append(Finding(Severity.YELLOW,
                "H1/L1入场 — 第一次入场80%可能失败，胜率较低", -10))
        elif self.trade.entry_count == EntryCount.FOURTH_PLUS:
            self.findings.append(Finding(Severity.ORANGE,
                "H4/L4+ — 趋势极弱，可能已转震荡区间", -12))

    def _check_wedge(self):
        """楔形质量评估"""
        overlap = ask_choice("楔形的K线重叠度？",
                             [
                                 "高重叠 (好楔形，胜率可达75%)",
                                 "低重叠/窄通道式 (坏楔形/假楔形)",
                             ])
        self.trade.wedge_overlap = "high" if overlap == 1 else "low"

        if overlap == 2:
            self.fatal_errors.append(
                "🔴 致命：坏楔形 — 无重叠的三推不是楔形，是窄通道！\n"
                "   → 反转胜率仅20%\n"
                "   → 在窄通道中逆势摸顶/抄底是严重错误\n"
                "   → 建议：改为顺势交易"
            )
            self.findings.append(Finding(Severity.RED,
                "坏楔形(窄通道式) — 反转胜率仅20%", -25))
        else:
            self.findings.append(Finding(Severity.GREEN,
                "好楔形(高重叠) — 反转胜率可达75%", 10))

        flag = ask_choice("这是反转楔形还是中继楔形旗形？",
                          ["顺大势逆小势的中继旗形 (胜率更高)",
                           "逆大势的反转楔形"])
        if flag == 1:
            self.findings.append(Finding(Severity.GREEN,
                "中继楔形旗形 — 顺大逆小，胜率更高", 10))

    def _check_order_type(self):
        """订单类型检查"""
        ot = ask_choice("你打算使用什么订单类型入场？",
                         [
                             "Stop Order (突破单) — 在信号K高/低点外1tick",
                             "Limit Order (限价单) — 在支撑/阻力区挂单",
                             "Market Order (市价单) — 直接按当前价成交",
                         ])
        self.trade.order_type = list(OrderType)[ot - 1]

        # 震荡区间 + Stop Order → 致命
        if self.trade.market_phase == MarketPhase.TRADING_RANGE:
            if self.trade.order_type == OrderType.STOP:
                self.fatal_errors.append(
                    "🔴 致命：震荡区间使用Stop Order追突破！\n"
                    "   → 80%突破会失败\n"
                    "   → 震荡区间应使用Limit Order高抛低吸"
                )
                self.findings.append(Finding(Severity.RED,
                    "震荡区间用Stop Order — 80%突破失败", -20))
            elif self.trade.order_type == OrderType.LIMIT:
                self.findings.append(Finding(Severity.GREEN,
                    "震荡区间用Limit Order — 正确的订单类型", 10))

        # 强趋势 + Market Order → 可以
        if self.trade.order_type == OrderType.MARKET:
            if self.trade.market_phase in (MarketPhase.BREAKOUT, MarketPhase.TIGHT_CHANNEL):
                self.findings.append(Finding(Severity.GREEN,
                    "Always In行情用市价单 — 可以接受", 3))
            else:
                self.findings.append(Finding(Severity.YELLOW,
                    "非强趋势行情用市价单 — 建议改用Stop Order过滤信号", -5))

        # 顺势 + Stop Order → 正确
        if self.trade.alignment == TradeAlignment.WITH_TREND and self.trade.order_type == OrderType.STOP:
            self.findings.append(Finding(Severity.GREEN,
                "顺势 + Stop Order — 正确的入场方式", 10))

    # ── E. 风控检查 ──────────────────────────────────

    def screen_risk(self):
        show_header("E. 风控检查")

        # E1: 止损
        sl = ask_choice("你有保护性止损吗？",
                         ["有，已经在系统/券商里设定好",
                          "有，但只是心理止损 (脑子里想的)",
                          "没有"])
        self.trade.has_stop_loss = (sl != 3)
        self.trade.stop_loss_type = ["system", "mental", "none"][sl - 1]

        if sl == 3:
            self.fatal_errors.append(
                "🔴🔴 致命：没有保护性止损！\n"
                "   → 开仓后第一件事是设止损\n"
                "   → 不允许无止损交易\n"
                "   → 黑天鹅事件(如1987黑色星期一)会毁掉你的账户"
            )
            self.findings.append(Finding(Severity.RED, "无止损交易！", -30))
        elif sl == 2:
            self.fatal_errors.append(
                "🔴 致命：心理止损等于没有止损！\n"
                "   → 你不会执行的，统计数据证明\n"
                "   → 必须在券商系统里挂好止损单"
            )
            self.findings.append(Finding(Severity.RED, "心理止损 = 没有止损", -25))
        else:
            self.findings.append(Finding(Severity.GREEN, "止损已设定在系统中", 5))

        if self.trade.has_stop_loss:
            # E2: 止损订单类型
            slt = ask_choice("止损订单类型？",
                              ["Stop Market (确保100%执行)",
                               "Stop Limit (可能滑过不成交)"])
            self.trade.stop_order_type = "stop_market" if slt == 1 else "stop_limit"
            if slt == 2:
                self.fatal_errors.append(
                    "🔴 致命：Stop Limit止损可能滑过不成交！\n"
                    "   → 极端行情(闪崩/跳空)时限价单无法执行\n"
                    "   → 只用Stop Market，确保止损100%触发"
                )
                self.findings.append(Finding(Severity.RED, "Stop Limit止损 — 可能失效", -20))

            # E3: 臭止损检测
            if ask_yes_no("你的止损位置是否在震荡区间的极端1/3区域？\n  (如做多时止损在区间下沿1/3)"):
                self.trade.skunk_stop = True
                self.fatal_errors.append(
                    "🔴 致命：臭止损 (Skunk Stop)！\n"
                    "   → 别人（机构）在这个区域买入/卖出\n"
                    "   → 你在最差的位置割肉\n"
                    "   → 正确做法：要么提前敏锐离场，要么坚定依赖初始止损"
                )
                self.findings.append(Finding(Severity.RED, "臭止损 — 在最差位置割肉", -20))

        # E4: 单笔风险
        risk = ask_choice("单笔风险占账户比例？",
                           ["≤1% (完美风控)", "1-2% (合理)", "2-5% (偏高)", ">5% (过大)"])
        risk_vals = [1.0, 1.5, 3.5, 6.0]
        self.trade.risk_pct = risk_vals[risk - 1]
        if risk == 1:
            self.findings.append(Finding(Severity.GREEN, "单笔风险≤1% — 完美风控", 5))
        elif risk == 2:
            self.findings.append(Finding(Severity.GREEN, "单笔风险1-2% — 合理", 2))
        elif risk == 3:
            self.findings.append(Finding(Severity.YELLOW, "单笔风险2-5% — 偏高", -5))
        elif risk == 4:
            self.fatal_errors.append(
                "🔴 致命：单笔风险>5%！\n"
                "   → 即使好信号也不值得冒这么大风险\n"
                "   → 连续几次亏损会严重损害账户"
            )
            self.findings.append(Finding(Severity.RED, "单笔风险>5%", -20))

        # E5: 前提条件提醒
        print("\n  💡 提醒：入场前提条件如果被打破，必须无条件离场！")
        print("     例：震荡区下沿做多后被跌破 → 前提不成立，不论盈亏必须走")

    # ── F. 目标位检查 ────────────────────────────────

    def screen_target(self):
        show_header("F. 目标位与盈亏比检查")

        # F1: 目标位
        has_target = ask_yes_no("你有明确的止盈目标位吗？")
        self.trade.has_target = has_target
        if not has_target:
            self.findings.append(Finding(Severity.YELLOW,
                "没有明确目标位 — 容易拿不住或贪心", -8))

        if has_target:
            basis = ask_choice("目标位的依据是什么？",
                                [
                                    "Measured Move (区间翻倍)",
                                    "Leg1=Leg2 等长测算",
                                    "信号K实体翻倍",
                                    "前期关键高/低点",
                                    "2倍止损距离 (2R)",
                                    "Actual Risk的1-2倍 (最精确)",
                                    "纯感觉/大概",
                                ])
            self.trade.target_basis = str(basis)
            if basis <= 6:
                self.findings.append(Finding(Severity.GREEN, "目标位有客观测算依据", 5))
                if basis == 6:
                    self.findings.append(Finding(Severity.GREEN,
                        "基于Actual Risk — 最精确的动态目标位", 3))
            else:
                self.findings.append(Finding(Severity.YELLOW,
                    "目标位缺乏客观依据 — '感觉'不是策略", -5))

        # F2: 盈亏比
        rr = ask_choice("盈亏比 (R:R)？",
                         ["≥2:1 (优秀)", "1:1 到 2:1 (一般)", "<1:1 (不合理)"])
        rr_vals = [2.0, 1.5, 0.8]
        self.trade.rr_ratio = rr_vals[rr - 1]
        if rr == 1:
            self.findings.append(Finding(Severity.GREEN,
                "盈亏比≥2:1 — 满足40%胜率+2R稳定盈利条件", 10))
        elif rr == 2:
            self.findings.append(Finding(Severity.YELLOW,
                "盈亏比1:1~2:1 — 需要更高胜率才能盈利", -5))
        else:
            self.findings.append(Finding(Severity.RED,
                "盈亏比<1:1 — 即使赢了也不划算", -15))

        # F3: 分批止盈
        partial = ask_yes_no("是否有分批止盈计划？\n  (如1R先止盈一半，剩余看2R+)")
        self.trade.has_partial_tp = partial
        if partial:
            self.findings.append(Finding(Severity.GREEN,
                "分批止盈 (Smart Trade) — 锁定胜率的最佳策略", 5))
        else:
            self.findings.append(Finding(Severity.YELLOW,
                "没有分批止盈 — 建议至少在1R处止盈一半锁定胜率", -5))

        # F4: 第三推
        if ask_yes_no("当前行情是否已经走到第三推？"):
            self.trade.third_push = True
            if ask_yes_no("第三推后是否计划减仓/止盈一部分？"):
                self.findings.append(Finding(Severity.GREEN,
                    "第三推后减仓 — 正确！大概率反转或震荡", 3))
            else:
                self.findings.append(Finding(Severity.YELLOW,
                    "第三推后全仓持有 — 风险偏高，建议至少减仓一部分", -5))

        # F5: 失败预案
        if not ask_yes_no("如果这笔交易失败(形态失败)，你有应对预案吗？"):
            self.findings.append(Finding(Severity.YELLOW,
                "没有失败预案 — 每个形态都有25%+失败概率，必须有离场计划", -5))

    # ── G. 综合评分 ──────────────────────────────────

    def assess(self):
        show_header("G. 综合评估")

        # 计算总分
        total_impact = sum(f.score_impact for f in self.findings)
        self.score = max(0, min(100, 50 + total_impact))

        # 确定评级
        if self.score >= 85:
            grade = "✅✅ 优质交易"
            advice = "满足大部分高胜率条件，可以执行。\n建议用OCO订单 Set and Forget (沃尔玛交易法)。"
        elif self.score >= 70:
            grade = "✅ 合格交易"
            advice = "核心条件满足，有一些瑕疵需注意。\n执行时格外关注瑕疵项，必要时缩小仓位。"
        elif self.score >= 50:
            grade = "⚠️ 存疑交易"
            advice = "多个条件不理想，建议：\n  - 缩小仓位 (正常仓位的1/3)\n  - 或等待更好的入场点\n  - 或重新审视交易逻辑"
        else:
            grade = "🔴 不建议交易"
            advice = "违反铁律或核心条件缺失，强烈建议放弃这笔交易。\n市场永远在，不缺机会，缺的是本金。"

        # 交易类型标签
        tag = self._get_trade_tag()

        # 输出结果
        print(f"\n{'━' * 56}")
        print(f"  交易筛查结果")
        print(f"{'━' * 56}")

        print(f"\n  标的: {self.trade.symbol}")
        print(f"  方向: {self.trade.direction.value}")
        print(f"  类型: {tag}")
        print(f"  综合评分: {self.score}/100")
        print(f"  评级: {grade}")

        # 致命错误
        if self.fatal_errors:
            print(f"\n{'─' * 56}")
            print("  🔴 致命错误 (必须解决):")
            print(f"{'─' * 56}")
            for err in self.fatal_errors:
                print(f"\n{err}")

        # 加分项
        bonuses = [f for f in self.findings if f.severity == Severity.GREEN]
        if bonuses:
            print(f"\n{'─' * 56}")
            print("  🟢 满足的高胜率条件:")
            print(f"{'─' * 56}")
            for f in bonuses:
                show_finding(f)

        # 警告项
        warnings = [f for f in self.findings if f.severity in (Severity.YELLOW, Severity.ORANGE)]
        if warnings:
            print(f"\n{'─' * 56}")
            print("  🟡 存在的瑕疵/警告:")
            print(f"{'─' * 56}")
            for f in warnings:
                show_finding(f)

        # 红色错误(非致命)
        reds = [f for f in self.findings if f.severity == Severity.RED]
        if reds:
            print(f"\n{'─' * 56}")
            print("  🔴 严重问题:")
            print(f"{'─' * 56}")
            for f in reds:
                show_finding(f)

        # 建议
        print(f"\n{'─' * 56}")
        print("  📋 建议:")
        print(f"{'─' * 56}")
        print(f"  {advice}")

        # 数学期望提醒
        self._show_expectation_reminder()

        # 沃尔玛交易法提醒
        if self.score >= 70 and self.trade.has_stop_loss and self.trade.has_target:
            print(f"\n  💡 沃尔玛交易法 (Walmart Trade):")
            print(f"     设好OCO止损止盈 → 关掉行情 → 去做别的事")
            print(f"     比盯盘乱操作效果更好，交易成绩更稳定")

        print(f"\n{'━' * 56}")

    def _get_trade_tag(self) -> str:
        """生成交易类型标签"""
        if self.fatal_errors:
            return "🚫 违反铁律 — 不应执行"

        tags = []
        if self.trade.alignment == TradeAlignment.WITH_TREND:
            if self.trade.market_phase in (MarketPhase.BREAKOUT, MarketPhase.TIGHT_CHANNEL):
                tags.append("顺势强趋势")
            elif self.trade.market_phase == MarketPhase.BROAD_CHANNEL:
                tags.append("顺势弱趋势(宽通道)")
            else:
                tags.append("震荡区间顺势")
        else:
            if self.trade.market_phase == MarketPhase.TRADING_RANGE:
                tags.append("震荡区间逆势反转")
            else:
                tags.append("逆势反转")

        if self.trade.entry_count == EntryCount.SECOND:
            tags.append("H2/L2入场")
        elif self.trade.entry_count == EntryCount.THIRD:
            tags.append("H3/L3楔形入场")
        elif self.trade.entry_count == EntryCount.FIRST:
            tags.append("H1/L1入场(风险)")

        if self.trade.order_type == OrderType.LIMIT:
            tags.append("限价单")
        elif self.trade.order_type == OrderType.STOP:
            tags.append("突破单")

        return " + ".join(tags) if tags else "未分类"

    def _show_expectation_reminder(self):
        """数学期望提醒"""
        print(f"\n  📊 数学期望检查:")
        if self.trade.rr_ratio >= 2.0:
            print(f"     盈亏比≥2:1 + 胜率40%+ → 正期望系统 ✓")
            print(f"     例: 40%赚2R + 60%亏1R = +0.2R/笔 (稳定盈利)")
        elif self.trade.rr_ratio >= 1.0:
            print(f"     盈亏比1:1~2:1 → 需要胜率>50%才能盈利")
            print(f"     例: 盈亏比1:1 + 胜率60% = +0.2R/笔 (勉强盈利)")
        else:
            print(f"     盈亏比<1:1 → 即使胜率较高也很难长期盈利 ✗")

    # ── 主流程 ───────────────────────────────────────

    def run(self):
        """运行完整筛查流程"""
        self._show_welcome()

        try:
            self.input_trade_info()
            self.screen_context()
            self.screen_direction()
            self.screen_entry()
            self.screen_risk()
            self.screen_target()
            self.assess()
        except KeyboardInterrupt:
            print("\n\n  筛查已中断。")
            sys.exit(0)

    def _show_welcome(self):
        print()
        print("╔══════════════════════════════════════════════════════╗")
        print("║                                                      ║")
        print("║   价格行为学 · 交易前筛查系统                        ║")
        print("║   Price Action Pre-Trade Screener                    ║")
        print("║                                                      ║")
        print("║   基于 Al Brooks 价格行为学课程                      ║")
        print("║   在下单前筛查你的交易决策是否合理                    ║")
        print("║                                                      ║")
        print("║   核心铁律：                                         ║")
        print("║   · Context 永远大于信号K                            ║")
        print("║   · 震荡中80%突破失败，趋势中80%反转失败              ║")
        print("║   · 不看到信号K不入场，用Stop Order过滤               ║")
        print("║   · 开仓后第一件事是设止损                           ║")
        print("║                                                      ║")
        print("╚══════════════════════════════════════════════════════╝")
        print()
        input("  按回车键开始筛查...")


# ═══════════════════════════════════════════════════════
#  入口
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    engine = ScreeningEngine()
    engine.run()
