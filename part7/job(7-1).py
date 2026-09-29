# 使用math和random库
import math, random
r = 2.5
print(f"圆的面积：{(math.pi * math.pow(r, 2)):.2f}")
print(f"圆的周长：{(math.pi * 2 * r):.2f}")
print(f"平方根：{math.sqrt(25)}")
print(f"幂：{math.pow(3, 3)}")
print(f"随机数：{random.randint(1, 100)}")
fruits = ["苹果","香蕉","橙子","葡萄","芒果"]
print(f"随机选择：{random.choice(fruits)}")