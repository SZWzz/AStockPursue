"""Workflow node implementations.

data_nodes         StockUniverse, OHLCVLoader
alpha_nodes        AlphaZoo
strategy_nodes     Strategy, Backtest (+ InMemoryLoader, StaticSignalEngine)
analysis_nodes     Attribution
thin_nodes         Screener, PaperTrading
control_nodes      ChatInput, Agent, IF (multi-condition)
subworkflow_nodes  SubWorkflow
"""
