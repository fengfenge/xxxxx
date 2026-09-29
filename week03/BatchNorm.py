import torch
import numpy as np

x = np.random.random((4, 5))
#创建1D批归一化层，参数 5 表示特征数量（num_features）
bn = torch.nn.BatchNorm1d(5)

# y = bn(torch.from_numpy(x).float())
# 将numpy数组转换为PyTorch张量，bn(...) ：对输入进行批归一化处理
y = bn(torch.FloatTensor(x))

print(x)
print("torch y:", y)
#状态字典包含：
# - weight （gamma）：缩放参数，初始值为1
# - bias （beta）：平移参数，初始值为0
# - running_mean ：全局均值（训练过程中累积更新）
# - running_var ：全局方差（训练过程中累积更新）
print(bn.state_dict())

#numpy实现
#gamma（γ） ：学习到的缩放因子，初始值为1
#beta（β） ：学习到的平移因子，初始值为0
gamma = bn.state_dict()["weight"].numpy()
beta = bn.state_dict()["bias"].numpy()

num_features = 5
eps = 1e-05
momentum = 0.1


# initialize the running mean and variance to zero
running_mean = np.zeros(num_features)
running_var = np.zeros(num_features)

mean = np.mean(x, axis=0)
var = np.var(x, axis=0)

# normalize the input with the mean and variance
x_norm = (x - mean) / np.sqrt(var + eps)

# scale and shift the normalized input with gamma and beta
y = gamma * x_norm + beta
print("ours y:", y)