import torch
import cdt
from cdt.causality.graph import CGNN
from causallearn.search.ConstraintBased.PC import pc
from causallearn.utils.cit import fisherz
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from networkx.drawing.nx_pydot import to_pydot
from multiprocessing import freeze_support


# ---------------------
# 针对 nx.adj_matrix 弃用问题的猴子补丁
if hasattr(nx, 'to_scipy_sparse_matrix'):  # NWX 2.x中有to_scipy_sparse_matrix
    def nx_adj_matrix(G, nodelist=None, weight=None):
        return nx.to_scipy_sparse_matrix(G, nodelist=nodelist, weight=weight, format='csr')
else:  # NWX 3.x中不再有to_scipy_sparse_matrix，而是to_scipy_sparse_array
    def nx_adj_matrix(G, nodelist=None, weight=None):
        return nx.to_scipy_sparse_array(G, nodelist=nodelist, weight=weight, format='csr')
nx.adj_matrix = nx_adj_matrix
# ---------------------


print("CUDA is available:", torch.cuda.is_available())
cdt.SETTINGS.GPU = 1

# 读取数据并预处理
csv_file = "delays_data_s49.csv"
df = pd.read_csv(csv_file)

selected_columns = ["TBS", "Pkt Size", "Number of Segments", "Segment Delay", "Queueing Delay"]
df = df[selected_columns]

# 数据筛选处理
segments_3 = df[df["Number of Segments"] == 3]
rows_to_keep = len(segments_3) // 2
segments_3_trimmed = segments_3.iloc[:rows_to_keep]
segments_not_3 = df[df["Number of Segments"] != 3]
df_modified = pd.concat([segments_3_trimmed, segments_not_3])
df = df_modified
data_values = df.values
# 去除缺失值
if df.isnull().values.any():
    df = df.dropna()

# 数据标准化
scaler = StandardScaler()
data_scaled = pd.DataFrame(scaler.fit_transform(df), columns=selected_columns)

if __name__ == '__main__':
    freeze_support()

    skeleton = pc(data_values, alpha=0.01, indep_test=fisherz, orient_edges=True)
    model = CGNN(
        nh=20,
        nruns=2,
        gpus=1,
        batch_size=128,
        lr=0.01,
        train_epochs=100,
        test_epochs=100,
        verbose=True,
        dataloader_workers=0,
        njobs=1
    )

    print("learning")
    final_graph = model.orient_undirected_graph(data_scaled, skeleton)

    print("绘制最终因果图...")
    pydot_graph = to_pydot(final_graph)
    for node in pydot_graph.get_nodes():
        node.set_shape('oval')
    pydot_graph.set_label("Causal Graph CGNN")
    pydot_graph.set_labelloc("t")

    pydot_graph.write_png("Causal Graph CGNN.png")

    img = plt.imread("Causal Graph CGNN.png")
    plt.imshow(img)
    plt.axis('off')
    plt.title("Causal Graph CGNN")
    plt.show()
