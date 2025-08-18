import pandas as pd
df = pd.read_csv("image_quality_laplacian.csv")
thr = 10822.0786
margin = 0.05 * thr
near = df[(df.sharpness.between(thr - margin, thr + margin))].sort_values("sharpness")
print("Below:")
print(near[near.sharpness < thr].tail(10)[["sharpness","path"]])
print("\nAbove:")
print(near[near.sharpness >= thr].head(10)[["sharpness","path"]])