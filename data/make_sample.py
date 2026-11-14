"""Creates a reproducible sample sales dataset with known answers."""
import numpy as np, pandas as pd
rng = np.random.default_rng(42)
n = 500
df = pd.DataFrame({
    "Order Date": pd.date_range("2025-01-01", periods=n, freq="D").strftime("%Y-%m-%d"),
    "Region": rng.choice(["North", "South", "East", "West"], n, p=[.35, .25, .25, .15]),
    "Product": rng.choice(["Laptop", "Phone", "Tablet", "Watch"], n),
    "Units": rng.integers(1, 20, n),
})
price = df["Product"].map({"Laptop": 60000, "Phone": 30000, "Tablet": 20000, "Watch": 8000})
df["Revenue"] = df["Units"] * price + rng.normal(0, 2000, n).round()
df.loc[10, "Revenue"] = 2_500_000   # planted outlier
df.to_csv("data/sales.csv", index=False)
print("saved data/sales.csv", df.shape)
