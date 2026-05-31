"""AI-mined alpha factors.

Factors in this zoo are discovered by the AI Factor Mining Engine
(gp_engine / llm_miner / hybrid_miner) and promoted via factor_promoter.
Each factor follows the standard Alpha Zoo contract:
    __alpha_meta__ dict literal
    compute(panel: dict[str, pd.DataFrame]) -> pd.DataFrame
"""
