'''
用于理解深度学习中常用的损失函数原理。
'''
# pytorch深度学习框架
# torch.nn Pytorch神经网络模块，包含常用的神经网络层和损失函数
# torch.FloatTensor 浮点数张量
# torch.LongTensor 整数张量
# torch.sum 求和
# torch.log 对数
# torch.softmax 软max函数
# torch.exp 指数
# torch.zeros 初始化为0
# torch.ones 初始化为1
# torch.numpy 转换为numpy数组
# torch.shape 获取张量形状
# torch.CrossEntropyLoss 交叉熵损失函数
# torch.argmax 获取最大值的索引
# numpy数值计算库
import torch
import torch.nn as nn
import numpy as np

'''
手动实现交叉熵的计算H(p, q) = -∑ p(x) · log(q(x))
- p(x) ：真实概率分布（真实标签）
- q(x) ：预测概率分布（模型输出）
两个分布 形状必须相同 才能进行逐元素相乘和求和运算。

pred_prob = [
    [0.124, 0.752, 0.124],  # 样本1的预测概率
    [0.296, 0.333, 0.371],  # 样本2的预测概率
    [0.402, 0.332, 0.266]   # 样本3的预测概率
]

one_hot = [
    [0, 1, 0],  # 样本1真实类别是1
    [0, 0, 1],  # 样本2真实类别是2
    [1, 0, 0]   # 样本3真实类别是0
]
# 样本1的交叉熵计算：
entropy_1 = -[0*log(0.124) + 1*log(0.752) + 0*log(0.124)]
           = -log(0.752)  # 只有真实类别的概率被保留！
           = 0.285

# 为什么其他位置是0？
# 因为 0 * log(anything) = 0
# 所以只有真实类别的位置有贡献！
'''

#使用torch计算交叉熵
ce_loss = nn.CrossEntropyLoss()
#假设有3个样本，每个都在做3分类
pred = torch.FloatTensor([[0.3, 2.1, 0.3],
                          [0.19, 1.2, 0.9],
                          [0.5, 0.4, 0.2]]) #n*class_num
#正确的类别分别为1,2,0
target = torch.LongTensor([1,2,0])     #n
'''
也可以写成这种形式：
torch.LongTensor([
    [0,1,0], #第1个样本正确类别为1
    [0,0,1], #第2个样本正确类别为2
    [1,0,0], #第3个样本正确类别为0
])
'''

# pred:模型输出的logits（未归一化的预测分数），形状为(3*3)，[batch_size, class_num]
# target:正确类别（未归一化），形状为(3,)[batch_size]，这里是类别索引
loss = ce_loss(pred, target)
print(loss, "torch输出交叉熵")

'''
pytorch的交叉熵包含两步
1、softmax:将logits转换为概率分布
2、负对数似然：计算交叉熵损失
'''
#实现softmax函数
# pred = [0.3, 2.1, 0.3]
# exp_pred = [exp(0.3), exp(2.1), exp(0.3)] exp(0.3) = e^0.3 = 2.71828^0.3 ≈ 1.35
#          = [1.35, 8.17, 1.35]
# softmax = [1.35/10.87, 8.17/10.87, 1.35/10.87]
#         = [0.124, 0.752, 0.124]
def softmax(matrix):
    return np.exp(matrix) / np.sum(np.exp(matrix), axis=1, keepdims=True)

#验证softmax函数，dim=1表示对每一行进行归一化，与axis=1效果相同
# print(torch.softmax(pred, dim=1))
# print(softmax(pred.numpy()))


#将输入转化为onehot矩阵
def to_one_hot(target, shape):
    one_hot_target = np.zeros(shape)
    for i, t in enumerate(target):
        one_hot_target[i][t] = 1
    return one_hot_target

#手动实现交叉熵
def cross_entropy(pred, target):
    batch_size, class_num = pred.shape
    pred = softmax(pred)
    target = to_one_hot(target, pred.shape)
    entropy = - np.sum(target * np.log(pred), axis=1)
    return sum(entropy) / batch_size

print(cross_entropy(pred.numpy(), target.numpy()), "手动实现交叉熵")

# print(np.log(2.7))