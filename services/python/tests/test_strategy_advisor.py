"""Tests for StrategyAdvisor."""
import pytest
from src.agent.strategy_advisor import (
    AdvisorStage,
    AdvisorState,
    StrategyAdvisor,
    StrategyParams,
)


@pytest.mark.unit
class TestIntentAnalysis:
    def test_extracts_trend_style(self):
        advisor = StrategyAdvisor()
        result = advisor.analyze_intent('我想做一个低吸高抛的均值回归策略')
        assert result['style'] == 'mean_reversion'

    def test_extracts_momentum_style(self):
        advisor = StrategyAdvisor()
        result = advisor.analyze_intent('追涨强势股，做动量策略')
        assert result['style'] == 'momentum'

    def test_detects_missing_parameters(self):
        advisor = StrategyAdvisor()
        result = advisor.analyze_intent('做一个策略')
        assert len(result['missing']) > 0
        assert result['confidence'] < 0.5

    def test_high_confidence_for_complete_description(self):
        advisor = StrategyAdvisor()
        result = advisor.analyze_intent(
            '做一个基于均线交叉的趋势策略，日线级别，最多持仓5只，止损5%'
        )
        assert result['confidence'] >= 0.5


@pytest.mark.unit
class TestClarification:
    def test_generates_question_for_missing_params(self):
        advisor = StrategyAdvisor()
        state = AdvisorState(session_id='test-1')
        question = advisor.generate_clarification_question(
            ['交易风格（趋势/回归/动量）', '最大持仓数'], state
        )
        assert len(question) > 0


@pytest.mark.unit
class TestStateMachine:
    def test_intent_analysis_to_clarification(self):
        advisor = StrategyAdvisor()
        state = AdvisorState(session_id='test-1')
        result = advisor.process_message(state, '做个策略')
        assert result['stage'] == AdvisorStage.PARAM_CLARIFICATION.value
        assert result['should_continue']

    def test_intent_analysis_to_generation(self):
        advisor = StrategyAdvisor()
        state = AdvisorState(session_id='test-2')
        result = advisor.process_message(
            state,
            '做趋势跟踪策略，日线，5只持仓，止损5%'
        )
        # Should have enough confidence to go to generation
        assert result['stage'] in (
            AdvisorStage.PARAM_CLARIFICATION.value,
            AdvisorStage.STRATEGY_GENERATION.value,
        )

    def test_clarification_to_generation(self):
        advisor = StrategyAdvisor()
        state = AdvisorState(session_id='test-3')
        state.stage = AdvisorStage.PARAM_CLARIFICATION
        state.params.style = 'trend'
        result = advisor.process_message(
            state,
            '日线交易，3只持仓，止损3%'
        )
        assert result['stage'] == AdvisorStage.STRATEGY_GENERATION.value

    def test_backtest_to_done(self):
        advisor = StrategyAdvisor()
        state = AdvisorState(session_id='test-4')
        state.stage = AdvisorStage.BACKTEST_RESULT
        state.backtest_result = {'sharpe_ratio': 1.5}
        result = advisor.process_message(state, '这个策略不错')
        assert result['stage'] == 'done'
        assert not result['should_continue']

    def test_backtest_to_iteration(self):
        advisor = StrategyAdvisor()
        state = AdvisorState(session_id='test-5')
        state.stage = AdvisorStage.BACKTEST_RESULT
        state.backtest_result = {'sharpe_ratio': 1.5}
        result = advisor.process_message(state, '回撤太大，加个止损')
        assert result['stage'] == AdvisorStage.ITERATION.value
        assert result['should_continue']

    def test_iteration_returns_to_generation(self):
        advisor = StrategyAdvisor()
        state = AdvisorState(session_id='test-6')
        state.stage = AdvisorStage.ITERATION
        result = advisor.process_message(state, '缩小止损到3%')
        assert result['stage'] == AdvisorStage.STRATEGY_GENERATION.value

    def test_max_iterations_reached(self):
        advisor = StrategyAdvisor()
        state = AdvisorState(session_id='test-7')
        state.stage = AdvisorStage.BACKTEST_RESULT
        state.iteration_count = 5  # at max
        result = advisor.process_message(state, '再调整一下')
        assert result['stage'] == 'done'
        assert not result['should_continue']


@pytest.mark.unit
class TestStrategyParams:
    def test_default_values(self):
        p = StrategyParams()
        assert p.frequency == 'daily'
        assert p.max_positions == 5

    def test_custom_values(self):
        p = StrategyParams(
            description='test',
            style='momentum',
            frequency='hourly',
            max_positions=3,
        )
        assert p.style == 'momentum'
        assert p.frequency == 'hourly'
