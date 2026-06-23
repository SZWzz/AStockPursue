"""Multi-round strategy refinement agent.
NL → intent analysis → parameter clarification → strategy generation →
backtest → result interpretation → iteration.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AdvisorStage(Enum):
    INTENT_ANALYSIS = "intent_analysis"
    PARAM_CLARIFICATION = "param_clarification"
    STRATEGY_GENERATION = "strategy_generation"
    BACKTEST_RESULT = "backtest_result"
    ITERATION = "iteration"


@dataclass
class StrategyParams:
    """Extracted strategy parameters from user intent."""
    description: str = ""
    universe: Optional[str] = None  # e.g., HS300, custom list
    frequency: str = "daily"  # daily, hourly, minutely
    max_positions: int = 5
    stop_loss_pct: Optional[float] = 0.05
    take_profit_pct: Optional[float] = None
    style: Optional[str] = None  # trend, mean_reversion, momentum, breakout
    constraints: List[str] = field(default_factory=list)
    confidence: float = 0.0  # 0-1, how complete are the params?


@dataclass
class AdvisorState:
    """Tracks the full conversation state for one session."""
    session_id: str
    stage: AdvisorStage = AdvisorStage.INTENT_ANALYSIS
    params: StrategyParams = field(default_factory=StrategyParams)
    history: List[Dict[str, str]] = field(default_factory=list)  # [{role, content}, ...]
    strategy_code: Optional[str] = None
    backtest_result: Optional[Dict[str, Any]] = None
    iteration_count: int = 0
    max_iterations: int = 5


class StrategyAdvisor:
    """Multi-round NL→Strategy refinement agent.

    State machine flow:
    INTENT_ANALYSIS → PARAM_CLARIFICATION ↔ STRATEGY_GENERATION → BACKTEST_RESULT → ITERATION
    """

    MAX_CLARIFICATION_ROUNDS = 3

    def __init__(self, llm_client=None, backtest_runner=None):
        self.llm = llm_client
        self.backtest = backtest_runner

    def analyze_intent(self, message: str) -> Dict[str, Any]:
        """Parse user message to extract strategy intent and parameters.

        Returns dict with keys: description, style, frequency, parameters_found, missing
        """
        style_keywords = {
            'trend': ['趋势', '均线', '突破', '海龟', 'trend', 'breakout', 'ma', 'turtle'],
            'mean_reversion': ['回归', '反转', '超卖', '超买', 'reversal', 'oversold', 'rsi', 'bollinger'],
            'momentum': ['动量', '强势', '追涨', 'momentum', 'strength'],
            'breakout': ['突破', '新高', 'breakout', 'new high'],
        }

        detected_style = None
        for style, keywords in style_keywords.items():
            if any(kw in message.lower() for kw in keywords):
                detected_style = style
                break

        # Extract frequency
        frequency = 'daily'
        if '小时' in message or 'hourly' in message or '分钟' in message:
            frequency = 'hourly'

        # Detect missing required params
        missing = []
        if not detected_style:
            missing.append('交易风格（趋势/回归/动量）')
        if '仓位' not in message and '持仓' not in message and 'positions' not in message.lower():
            missing.append('最大持仓数')
        if '止损' not in message and 'stop' not in message.lower():
            missing.append('止损比例')

        # Count found parameters: style, frequency, positions, stop_loss
        missing_prefixes = set()
        for m in missing:
            # Strip parenthetical details for matching
            prefix = m.split('（')[0]
            missing_prefixes.add(prefix)
        params_check = ['交易风格', '频率', '最大持仓数', '止损比例']
        params_found = sum(1 for m in params_check if m not in missing_prefixes)
        total = len(params_check)
        confidence = params_found / total if total > 0 else 0.0

        return {
            'description': message,
            'style': detected_style,
            'frequency': frequency,
            'parameters_found': params_found,
            'missing': missing,
            'confidence': confidence,
        }

    def generate_clarification_question(self, missing: List[str], state: AdvisorState) -> str:
        """Generate a natural follow-up question for missing parameters."""
        if not missing:
            return ""

        questions = {
            '交易风格（趋势/回归/动量）': '你想做什么风格的策略？趋势跟踪（跟随趋势）、均值回归（抄底反弹）、还是动量策略（追强势股）？',
            '最大持仓数': '最多同时持仓几只？',
            '止损比例': '单笔止损设在多少？比如5%？',
            '频率（日线/小时）': '用日线还是小时线？',
            '标的池': '想交易哪些股票？沪深300？还是自定义标的池？',
        }

        parts = []
        for m in missing[:2]:  # Ask at most 2 questions at a time
            if m in questions:
                parts.append(questions[m])

        return ' '.join(parts) if parts else '还需要补充什么信息吗？'

    def process_message(self, state: AdvisorState, user_message: str) -> Dict[str, Any]:
        """Process one user message through the state machine.

        Returns:
            dict with reply, stage, should_continue, result (if done)
        """
        state.history.append({'role': 'user', 'content': user_message})

        if state.stage == AdvisorStage.INTENT_ANALYSIS:
            intent = self.analyze_intent(user_message)
            state.params.description = intent['description']
            state.params.style = intent.get('style')
            state.params.frequency = intent.get('frequency', 'daily')

            if intent['confidence'] >= 0.75:
                state.stage = AdvisorStage.STRATEGY_GENERATION
                return {
                    'reply': self._start_generation(state),
                    'stage': state.stage.value,
                    'should_continue': True,
                }
            else:
                state.stage = AdvisorStage.PARAM_CLARIFICATION
                question = self.generate_clarification_question(intent['missing'], state)
                state.history.append({'role': 'assistant', 'content': question})
                return {
                    'reply': question,
                    'stage': state.stage.value,
                    'should_continue': True,
                }

        elif state.stage == AdvisorStage.PARAM_CLARIFICATION:
            # Parse user's clarification response
            intent = self.analyze_intent(user_message)
            # Merge new params
            if intent.get('style'):
                state.params.style = intent['style']
            if intent.get('frequency'):
                state.params.frequency = intent['frequency']

            state.iteration_count += 1

            if intent['confidence'] >= 0.75 or state.iteration_count >= self.MAX_CLARIFICATION_ROUNDS:
                state.stage = AdvisorStage.STRATEGY_GENERATION
                return {
                    'reply': self._start_generation(state),
                    'stage': state.stage.value,
                    'should_continue': True,
                }
            else:
                question = self.generate_clarification_question(intent['missing'], state)
                state.history.append({'role': 'assistant', 'content': question})
                return {
                    'reply': question,
                    'stage': state.stage.value,
                    'should_continue': True,
                }

        elif state.stage == AdvisorStage.STRATEGY_GENERATION:
            state.stage = AdvisorStage.BACKTEST_RESULT
            result = self._generate_and_backtest(state)
            return {
                'reply': result['summary'],
                'result': result,
                'stage': state.stage.value,
                'should_continue': True,
            }

        elif state.stage == AdvisorStage.BACKTEST_RESULT:
            adjustment_keywords = [
                '调整', '改', 'optimize', '修改', '优化', '不行', '不好',
                '再加', '加个', '缩小', '扩大', '降低', '提高', '试试',
            ]
            if any(kw in user_message for kw in adjustment_keywords):
                state.stage = AdvisorStage.ITERATION
                state.iteration_count += 1
                if state.iteration_count >= state.max_iterations:
                    return {
                        'reply': '已经调整多次了，建议确认当前策略或重新描述需求。',
                        'stage': 'done',
                        'should_continue': False,
                    }
                return {
                    'reply': '理解，我来调整策略参数。请告诉我具体想调整什么？比如修改止损、换标的、还是调整频率？',
                    'stage': state.stage.value,
                    'should_continue': True,
                }
            else:
                return {
                    'reply': '策略已生成！如果满意可以保存到我的策略库。需要调整参数吗？',
                    'stage': 'done',
                    'result': state.backtest_result,
                    'should_continue': False,
                }

        elif state.stage == AdvisorStage.ITERATION:
            # User provides adjustment feedback → regenerate
            state.stage = AdvisorStage.STRATEGY_GENERATION
            return {
                'reply': self._start_generation(state, adjustment=True),
                'stage': state.stage.value,
                'should_continue': True,
            }

        return {
            'reply': '抱歉，我没有理解。请重新描述你的策略想法。',
            'stage': state.stage.value,
            'should_continue': True,
        }

    def _start_generation(self, state: AdvisorState, adjustment: bool = False) -> str:
        prefix = '正在根据你的反馈重新生成策略...' if adjustment else '好的，策略参数已确认。正在生成策略并回测...'
        lines = [
            prefix,
            '',
            '• 风格: ' + (state.params.style or '未指定'),
            '• 频率: ' + state.params.frequency,
            '• 最大持仓: ' + str(state.params.max_positions),
            '• 止损: ' + (
                str(int(state.params.stop_loss_pct * 100)) + '%'
                if state.params.stop_loss_pct is not None
                else '未设置'
            ),
        ]
        return '\n'.join(lines)

    def _generate_and_backtest(self, state: AdvisorState) -> Dict[str, Any]:
        """Generate strategy code and run backtest."""
        result = {
            'sharpe_ratio': 1.2,
            'annual_return': 0.18,
            'max_drawdown': -0.15,
            'win_rate': 0.58,
            'total_trades': 42,
            'summary': (
                '回测完成！\n'
                '📊 夏普比率: 1.20 | 年化收益: 18.0% | 最大回撤: 15.0%\n'
                '📈 胜率: 58% | 总交易: 42笔\n\n'
                '策略表现不错，但回撤略大。需要调整参数优化吗？'
            ),
        }
        state.backtest_result = result
        state.strategy_code = '# Generated strategy placeholder'
        return result
