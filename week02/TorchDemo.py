# coding:utf8
'''
Tensor张量是深度学习框架中的核心数据结构，多维数组

向量、矩阵、张量 本质上是同一类东西的不同维度版本。
## 张量是维度泛化

对应pytorch中的torch.tensor()函数
import torch

# 0维张量 - 一个数字
scalar = torch.tensor(5.0)
print(scalar.shape)  # torch.Size([])

# 1维张量 - 一维数组（向量）
vector = torch.tensor([1.0, 2.0, 3.0, 4.0, 5.0])
print(vector.shape)  # torch.Size([5])

# 2维张量 - 矩阵（表格）
matrix = torch.tensor([[1, 2, 3], [4, 5, 6]])
print(matrix.shape)  # torch.Size([2, 3])

# 3维张量 - 多层表格
tensor_3d = torch.randn(10, 20, 5)  # 10行，20列，5层
print(tensor_3d.shape)  # torch.Size([10, 20, 5])
'''
# 解决 OpenMP 库冲突问题
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

# - 核心库 ：PyTorch 用于模型定义和训练
# - 辅助库 ：NumPy 用于数据处理，matplotlib 用于绘图

import torch
import torch.nn as nn
import numpy as np
import random
import json
import matplotlib.pyplot as plt

"""
基于 PyTorch 框架的 二分类任务 实现
基于pytorch框架编写模型训练
实现一个自行构造的找规律(机器学习)任务
规律：x是一个5维向量，如果第1个数>第5个数，则为正样本，反之为负样本

"""

# 定义模型
# 一个线性层，一个sigmoid激活函数，一个均方差损失函数
'''
PyTorch 神经网络的核心基类,为构建深度学习模型提供了统一的接口和功能
- 模型组织 ：所有神经网络层、模型和组件都继承自 nn.Module
- 参数管理 ：自动跟踪和管理模型参数
- 前向传播 ：定义 forward 方法实现前向计算
- 设备管理 ：支持模型在不同设备（CPU/GPU）间迁移
- 状态管理 ：区分训练模式和评估模式
'''
class TorchModel(nn.Module): 
    def __init__(self, input_size):
        '''
        - super ：Python 内置函数，用于获取父类
        - TorchModel ：当前类名
        - self ：当前类的实例
        - __init__() ：调用父类的初始化方法

        当继承 nn.Module 时，这个调用 必须执行 ，原因是：

        - 初始化模块注册表 ： nn.Module 需要初始化内部的模块注册表
        - 参数管理系统 ：设置参数跟踪和管理机制
        - 状态管理 ：初始化训练/评估模式状态
        - 设备管理 ：准备模型在不同设备间迁移的能力
        - 子模块跟踪 ：建立子模块的层次结构
        '''
        super(TorchModel, self).__init__() # 必须调用父类初始化方法
        # 定义子模块
        '''
        语法结构：nn.Linear(in_features, out_features, bias=True)
        - in_features ：输入特征维度
        - out_features ：输出特征维度
        - bias ：是否添加偏置项，默认True

        ### 数学原理
        这行代码表示一个线性变换： y = x @ W^T + b
        # 样本i的输入: [x1, x2, x3, x4, x5]
        # 权重: [w1, w2, w3, w4, w5]
        y_i = x1*w1 + x2*w2 + x3*w3 + x4*w4 + x5*w5 + b

        - 输入 : 形状为 (batch_size, input_size) 的张量
            输入 x 的形状: (32, 5) 32行5列

            含义: 32个样本，每个样本5个特征

            样本1: [0.1, 0.2, 0.3, 0.4, 0.5]
            样本2: [0.2, 0.3, 0.4, 0.5, 0.6]
            ...
            样本32: [0.9, 0.1, 0.2, 0.3, 0.4]
        - 输出 : 形状为 (batch_size, 1) 的张量
        - 权重W : 形状为 (1, input_size) 的可学习参数矩阵，W.t() 是权重矩阵的转置，形状从 (1, 5) 变为 (5, 1)
        - 偏置b : 形状为 (1,) 的可学习偏置向量
        '''
        self.linear = nn.Linear(input_size, 1)  # 线性层，如：输入5个特征，输出1个特征
        self.activation = torch.sigmoid  # nn.Sigmoid() sigmoid归一化函数，二分类模型中起到关键作用
        self.loss = nn.functional.mse_loss  # loss函数采用均方差损失

    # 当输入真实标签，返回loss值；无真实标签，返回预测值
    def forward(self, x, y=None):
        x = self.linear(x)  # (batch_size, input_size) -> (batch_size, 1)
        y_pred = self.activation(x)  # (batch_size, 1) -> (batch_size, 1)
        if y is not None:
            return self.loss(y_pred, y)  # 预测值和真实值计算损失
        else:
            return y_pred  # 输出预测结果


# 生成一个样本, 样本的生成方法，代表了我们要学习的规律
# 随机生成一个5维向量，如果第一个值大于第五个值，认为是正样本，反之为负样本
# 生成样本为，(x, y)，一个特征维度，一个标签维度
# x: 5维向量，y: 0或1
def build_sample():
    x = np.random.random(5)
    if x[0] > x[4]:
        return x, 1
    else:
        return x, 0


# 随机生成一批样本
# 正负样本均匀生成
def build_dataset(total_sample_num):
    X = []
    Y = []
    for i in range(total_sample_num):
        x, y = build_sample()
        X.append(x) # 一个特征维度
        Y.append([y]) # 对应一个标签维度
    # print(X)
    # print(Y)
    # 转换为张量
    # X: (32, 5) 32个样本，每个样本5个特征维度
    # Y: (32, 1) 32个样本，每个样本1个标签维度
    return torch.FloatTensor(X), torch.FloatTensor(Y)

# 测试代码
# 用来测试每轮模型的准确率
# 输入：模型实例
# 输出：准确率
# 功能：评估模型在测试集上的准确率
'''
对比训练和评估
    操作 训练模式 评估模式 
梯度计算    需要    不需要 
内存占用    较高    较低 
计算速度    较慢    较快 
使用no_grad ❌    ✅

最终实践：
- 评估时始终使用 ： model.eval() + with torch.no_grad()
- 推理时使用 ：只进行前向传播时
- 数据预处理 ：不涉及梯度的数据处理
- 避免误用 ：训练过程中不要使用
'''
def evaluate(model):
    model.eval() # 切换到评估模式
    # 测试集样本数
    test_sample_num = 100
    x, y = build_dataset(test_sample_num)
    print("本次预测集中共有%d个正样本，%d个负样本" % (sum(y), test_sample_num - sum(y)))
    correct, wrong = 0, 0
    '''
    torch.no_grad() 是 PyTorch 的 上下文管理器 ，用于 禁用梯度计算。
    - 禁用梯度跟踪 ：在上下文内不计算梯度
    - 节省内存 ：不存储中间计算结果
    - 提高速度 ：跳过梯度计算步骤
    - 评估模式 ：用于模型推理和评估
    '''
    with torch.no_grad():
        y_pred = model(x)  # 只进行前向传播，不计算梯度，模型预测 model.forward(x)
        '''
        zip(*iterables) ：将多个可迭代对象打包成元组，返回一个迭代器
        例如：
        zip([1, 2, 3], [4, 5, 6]) -> [(1, 4), (2, 5), (3, 6)]
        输入特征数组x，真实标签数组y，按索引位置配对，返回元组列表
        '''
        for y_p, y_t in zip(y_pred, y):  # 与真实标签进行对比
            if float(y_p) < 0.5 and int(y_t) == 0:
                correct += 1  # 负样本判断正确
            elif float(y_p) >= 0.5 and int(y_t) == 1:
                correct += 1  # 正样本判断正确
            else:
                wrong += 1
    print("正确预测个数：%d, 正确率：%f" % (correct, correct / (correct + wrong)))
    return correct / (correct + wrong)


def main():
    # 配置参数
    epoch_num = 20  # 训练轮数
    batch_size = 20  # 每次训练样本个数
    train_sample = 5000  # 每轮训练总共训练的样本总数
    input_size = 5  # 输入向量维度
    learning_rate = 0.01  # 学习率
    # 建立模型
    model = TorchModel(input_size)
    # 选择优化器
    optim = torch.optim.Adam(model.parameters(), lr=learning_rate)
    log = []
    # 创建训练集，正常任务是读取训练集
    train_x, train_y = build_dataset(train_sample)
    # 训练过程
    for epoch in range(epoch_num):
        # 切换到训练模式, 开启梯度计算，用于更新权重，不需要加 torch.no_grad()
        # 因为在训练过程中，我们希望模型的参数能够根据损失函数进行更新，而不是保持不变。
        model.train() 
        watch_loss = []
        for batch_index in range(train_sample // batch_size): 
            #取出一个batch数据作为输入   train_x[0:20]  train_y[0:20] train_x[20:40]  train_y[20:40]
            x = train_x[batch_index * batch_size : (batch_index + 1) * batch_size]
            y = train_y[batch_index * batch_size : (batch_index + 1) * batch_size]
            loss = model(x, y)  # 计算loss  model.forward(x,y)
            loss.backward()  # 计算梯度
            optim.step()  # 更新权重
            optim.zero_grad()  # 梯度归零
            watch_loss.append(loss.item())
        print("=========\n第%d轮平均loss:%f" % (epoch + 1, np.mean(watch_loss)))
        acc = evaluate(model)  # 测试本轮模型结果
        log.append([acc, float(np.mean(watch_loss))])
    # 保存模型
    torch.save(model.state_dict(), "model.bin")
    # 画图
    print(log)
    plt.plot(range(len(log)), [l[0] for l in log], label="acc")  # 画acc曲线
    plt.plot(range(len(log)), [l[1] for l in log], label="loss")  # 画loss曲线
    plt.legend()
    plt.show()
    return


# 使用训练好的模型做预测
def predict(model_path, input_vec):
    input_size = 5
    model = TorchModel(input_size)
    model.load_state_dict(torch.load(model_path))  # 加载训练好的权重
    print(model.state_dict())

    model.eval()  # 测试模式
    with torch.no_grad():  # 不计算梯度
        result = model.forward(torch.FloatTensor(input_vec))  # 模型预测
    for vec, res in zip(input_vec, result):
        print("输入：%s, 预测类别：%d, 概率值：%f" % (vec, round(float(res)), res))  # 打印结果


if __name__ == "__main__":
    main()
    # test_vec = [[0.88889086,0.15229675,0.31082123,0.03504317,0.88920843],
    #             [0.94963533,0.5524256,0.95758807,0.95520434,0.84890681],
    #             [0.90797868,0.67482528,0.13625847,0.34675372,0.19871392],
    #             [0.99349776,0.59416669,0.92579291,0.41567412,0.1358894]]
    # predict("model.bin", test_vec)
