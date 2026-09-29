import torch
import math
import numpy as np
from transformers import BertModel
from transformers import BertTokenizer
'''

关于transformers自带的序列化工具
模型文件下载 https://huggingface.co/models

'''

# bert = BertModel.from_pretrained(r"F:\Desktop\work_space\pretrain_models\bert-base-chinese", return_dict=False)
tokenizer = BertTokenizer.from_pretrained(r"E:\pretrain_models\bert-base-chinese")

string = "咱呀么老百姓今儿个真高兴"
#分字
tokens = tokenizer.tokenize(string) #中文 BERT tokenizer 按单字切分
print("分字：", tokens)
# 分字： ['咱', '呀', '么', '老', '百', '姓', '今', '儿', '个', '真', '高', '兴']
#        ↑ 字符串列表，每个元素是一个汉字

#编码，前后自动添加了[cls] string [sep] # 
encoding = tokenizer.encode(string) # 结构为 [CLS_101, 字1_id, 字2_id, ..., 字N_id, SEP_102]
print("编码：", encoding)
# 编码： [101, 1234, 5678, 901, 2345, 678, 910, 3456, 789, 123, 4567, 8901, 234, 102]
#        ↑    ↑                          各汉字的 id                          ↑
#     [CLS]                                                               [SEP]
#      101                                                                  102


#文本对编码, 形式[cls] string1 [sep] string2 [sep]
string1 = "今天天气真不错"
string2 = "明天天气怎么样"
encoding = tokenizer.encode(string1, string2) # 格式 [CLS] s1 [SEP] s2 [SEP]
print("文本对编码：", encoding)

# 编码： [101, 1234, 5678, 901, 2345, 678, 910, 3456, 789, 123, 4567, 8901, 234, 102]
#        ↑    ↑                          各汉字的 id                          ↑
#     [CLS]                                                               [SEP]
#      101                                                                  102


