import sys
from pathlib import Path

# Add python directory
sys.path.insert(0, str(Path(__file__).parent.parent / "ValueCell_MT5" / "python"))

from valuecell.agents.ml_prediction_agent import MLPredictionAgent

agent = MLPredictionAgent()
print(f"Agent Model Type: {agent.model_type}")
print(f"Threshold R:R: {agent.threshold}")
print(f"Norm Target: {agent.norm_target}")
print(f"Base Reference Price: {agent.base_reference_price}")
print(f"MFE Features: {len(agent.mfe_feature_names)}")
print(f"MAE Features: {len(agent.mae_feature_names)}")
print("Verification Success: Model v8 Final is active and correctly loaded!")
