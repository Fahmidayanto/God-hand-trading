import pandas as pd

AGENT = r"C:\Users\fahmi\AppData\Roaming\MetaQuotes\Tester\D0E8209F77C8CF37AD8BF550E51FF075\Agent-127.0.0.1-3000\MQL5\Files"
BOLD = r"B:\Project MT5\Backtest_result"

new = pd.read_csv(AGENT + r"\Backtest_Results_XAUUSD_2019-12-30.csv")
old = pd.read_csv(BOLD + r"\Backtest_Results_XAUUSD_2019-12-30.csv")

print("=== SUMMARY TESTER (agent folder) ===")
summ = pd.read_csv(AGENT + r"\Backtest_Summary_XAUUSD_2019-12-30.csv")
print(summ.to_string(index=False))

nex = new[new["Status"] == "EXECUTED"].copy()
oex = old[old["Status"] == "EXECUTED"].copy()

print("\n=== PERBANDINGAN EXECUTED ===")
print(f"Tester: {len(nex)} trade | Sum Net_Profit={nex['Net_Profit'].sum():.2f}")
print(f"B:\\ old: {len(oex)} trade | Sum Net_Profit={oex['Net_Profit'].sum():.2f}")

print("\nCloseType tester:")
print(nex["CloseType"].value_counts().to_string())
print("\nCloseType old:")
print(oex["CloseType"].value_counts().to_string())

print("\nPeriode entry tester:", nex["EntryTime"].min(), "->", nex["EntryTime"].max())
print("Periode entry old  :", oex["EntryTime"].min(), "->", oex["EntryTime"].max())

key_n = set(zip(nex["EntryTime"], nex["Type"], nex["EntryPrice"].round(2)))
key_o = set(zip(oex["EntryTime"], oex["Type"], oex["EntryPrice"].round(2)))
inter = key_n & key_o
print(f"\nMatch entry (Time+Type+Price): {len(inter)} dari tester {len(key_n)} / old {len(key_o)}")
only_new = len(key_n - inter)
only_old = len(key_o - inter)
print(f"Hanya di tester: {only_new} | Hanya di old: {only_old}")

merged = pd.merge(
    nex[["EntryTime", "Type", "EntryPrice", "ExitPrice", "ExitTime", "Net_Profit", "CloseType", "LotSize"]],
    oex[["EntryTime", "Type", "EntryPrice", "Net_Profit", "CloseType", "LotSize"]],
    on=["EntryTime", "Type"], suffixes=("_n", "_o"), how="inner")
if len(merged):
    merged["diff"] = merged["Net_Profit_n"] - merged["Net_Profit_o"]
    print("\nTop 10 gap terbesar (entry sama):")
    top = merged.reindex(merged["diff"].abs().sort_values(ascending=False).index).head(10)
    print(top[["EntryTime", "Type", "EntryPrice_n", "ExitPrice", "Net_Profit_n", "Net_Profit_o",
               "diff", "CloseType_n", "CloseType_o", "LotSize_n", "LotSize_o"]].to_string(index=False))
    print(f"\nRata-rata diff entry sama: {merged['diff'].mean():.2f} | Total diff: {merged['diff'].sum():.2f}")

mn = pd.read_csv(AGENT + r"\MarketData_XAUUSD_M15_2019-12-30.csv")
mo = pd.read_csv(BOLD + r"\MarketData_XAUUSD_M15_2019-12-30.csv")
print("\n=== MARKET DATA M15 ===")
print(f"Tester: {len(mn)} bar, spread avg={mn['Spread'].mean():.1f} poin, periode {mn['Time'].iloc[0]} -> {mn['Time'].iloc[-1]}")
print(f"B:\\   : {len(mo)} bar, spread avg={mo['Spread'].mean():.1f} poin, periode {mo['Time'].iloc[0]} -> {mo['Time'].iloc[-1]}")
