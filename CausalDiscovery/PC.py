import pandas as pd
import matplotlib.pyplot as plt
from causallearn.search.ConstraintBased.PC import pc
from causallearn.utils.cit import fisherz
from causallearn.utils.GraphUtils import GraphUtils

# 加载 CSV 文件
csv_file = "delays_data_s49.csv"
df = pd.read_csv(csv_file)
# selected_columns = ["TBS", "Number of Segments", "Segment Delay", "Queueing Delay", "Frame Alignment Delay"]
# df = df[selected_columns]
# 筛选出 "Number of Segments" 列中值为 3 的行
segments_3 = df[df["Number of Segments"] == 3]
rows_to_keep = len(segments_3) // 2
segments_3_trimmed = segments_3.iloc[:rows_to_keep]
segments_not_3 = df[df["Number of Segments"] != 3]
df_modified = pd.concat([segments_3_trimmed, segments_not_3])

# 将结果存储回 df
df = df_modified

# 检查数据是否有缺失值或异常
if df.isnull().values.any():
    print("数据包含缺失值，正在移除...")
    df = df.dropna()

print("数据摘要：")
print(df.describe())

# 将数据转换为 NumPy 数组
data_values = df.values
labels = list(df.columns)

print("Running PC...")
pc_result = pc(data_values, alpha=0.01, indep_test=fisherz, orient_edges=True)
print(pc_result.G)

pydot_graph = GraphUtils.to_pydot(pc_result.G, labels=labels)
pydot_graph.write_png("Causal Graph PC.png")

# 显示有向因果图
print("Plot...")
img = plt.imread("Causal Graph PC.png")
plt.imshow(img)
plt.axis('off')
plt.title("Cut 50% seg_3")
plt.show()
