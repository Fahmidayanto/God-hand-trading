import os

vault_dir = r"B:\SecBrain\TradingBrain"
print(f"Vault exists: {os.path.exists(vault_dir)}")
if os.path.exists(vault_dir):
    print("Folders in vault:", os.listdir(vault_dir))
