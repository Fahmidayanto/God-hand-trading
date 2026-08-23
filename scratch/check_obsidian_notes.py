import os

vault_dir = r"B:\SecBrain\TradingBrain"
print("Project files:", os.listdir(os.path.join(vault_dir, "Project")) if os.path.exists(os.path.join(vault_dir, "Project")) else "Not found")
print("Notes files:", os.listdir(os.path.join(vault_dir, "Notes")) if os.path.exists(os.path.join(vault_dir, "Notes")) else "Not found")
