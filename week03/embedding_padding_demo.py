#coding:utf8
"""
Embedding 层 与 Padding 操作教学
"""
import torch
import torch.nn as nn

# ── 1. Embedding 本质：一张可训练的查找表 ─────────────────────────────────────
#
#   nn.Embedding(num_embeddings, embedding_dim)
#   └─ 内部维护一个形状为 [num_embeddings, embedding_dim] 的权重矩阵
#   └─ 输入整数 index，直接取对应行，等价于 one-hot × 权重矩阵，但效率更高
#
vocab = {"[pad]":0, "你":1, "好":2, "中":3, "国":4, "欢":5, "迎":6, "[unk]":7}
VOCAB_SIZE = len(vocab)   # 8
EMBED_DIM  = 4

embedding = nn.Embedding(VOCAB_SIZE, EMBED_DIM)

print("── Embedding 权重矩阵（shape = 字符数 × 向量维度）──")
print(embedding.weight, "\n")

# 单个 token 查询：取第 3 行（"中"）
idx = torch.LongTensor([3])
print("'中' 的向量（第3行）:", embedding(idx))

# ── 2. 为什么需要 Padding ──────────────────────────────────────────────────────
#
#   同一个 batch 中，句子长度不同，无法直接堆成矩阵。
#   解决方案：统一截断或补齐到 max_len，不足的位置填特殊 token [pad]=0。
#
#   "中国欢迎你" → [3,4,5,6,1]         长度5，不需补
#   "你好中国"   → [1,2,3,4,0]         长度4，补1个 pad
#   "feda"       → [7,7,7,7,0]         全 unk，补1个 pad
#
MAX_LEN = 5

def encode(text, vocab, max_len):
    ids = [vocab.get(ch, vocab["[unk]"]) for ch in text][:max_len]
    ids += [vocab["[pad]"]] * (max_len - len(ids))   # 补齐
    return ids

sentences = ["中国欢迎你", "你好中国", "feda"]
batch_ids  = [encode(s, vocab, MAX_LEN) for s in sentences]

print("\n── Padding 后的 token id ──")
for s, ids in zip(sentences, batch_ids):
    print(f"  {s!r:8s} → {ids}")
# 这里面包含三个修饰：
# s：变量名，很可能是当前正在处理的句子（字符串）。
# !r：转换标志，表示对 s 先调用 repr()。
# repr(s) 会返回字符串的“官方”表示形式，即带有引号、且转义特殊字符（如换行符会显示为 \n）的字符串。例如 "你好" 会变成 '你好'（外面多了一层引号）。
# :8s：格式说明符，表示最终输出一个字符串（s），最小宽度为8个字符。
# 对于字符串类型，默认是左对齐，如果长度不足8，会在右侧补空格凑满8个字符。
# 所以，{s!r:8s} 的整体效果是：
# 先拿到 s 的 repr 形式（带引号的字符串），然后在不超过8个字符宽度时，右侧用空格填满，保证至少占8个字符位。
#   '我爱学习'  → [1, 2, 3, 0]
#   '你好'     → [4, 5, 0, 0]

# ── 3. padding_idx：让 [pad] 向量永远为零 ─────────────────────────────────────
#
#   设置 padding_idx=0 后：
#   ① Embedding 初始化时第 0 行全为 0
#   ② 反向传播时第 0 行梯度不更新（[pad] 不携带语义，不应影响训练）
#
embedding_with_pad = nn.Embedding(VOCAB_SIZE, EMBED_DIM, padding_idx=0)

print("\n── 设置 padding_idx=0 后的权重矩阵 ──")
print(embedding_with_pad.weight)
print("第0行（[pad] 向量）:", embedding_with_pad.weight[0])  # 全零

# ── 4. 完整 batch 送入 Embedding ──────────────────────────────────────────────
x = torch.LongTensor(batch_ids)          # shape: [3, 5]
out = embedding_with_pad(x)              # shape: [3, 5, 4]

print("\n── Embedding 输出（batch=3, seq_len=5, embed_dim=4）──")
print("shape:", out.shape)
print(out)
print("\n注意：每个句子最后的 pad 位置对应向量全为 0，不影响模型对有效 token 的建模。")
