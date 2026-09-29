# 任务描述：
# 编写一个程序，实现以下功能：
# 1. 创建一个空列表，用于存储学生姓名
# 2. 使用循环提示用户输入5个学生的姓名，并添加到列表中
# 3. 使用for循环遍历列表，打印所有学生姓名
# 4. 计算并打印列表的长度
# 5. 提示用户输入一个要查找的姓名，判断该姓名是否在列表中
# 6. 如果存在，打印该姓名在列表中的位置（索引）
#
# 要求：
# - 使用列表的append()方法添加元素
# - 使用len()函数获取列表长度
# - 使用in关键字判断元素是否存在
# - 使用index()方法查找索引（如果存在）
# - 添加适当的注释

from typing import List
# 学生成员列表
List = []

for i in range(1,6):
    List.append(input(f'请输入第{i}个学生的姓名: '))

for l in List:
    print(f'5位学生分别为{l}')

print(f'现总共有{len(List)}个学生')

check_name = input('输入一个要查找的姓名: ')

if check_name in List:
    print('该学生存在')
    print(List.index(check_name))
else:
    print('该学生不存在，新加入')
    List.append(check_name)
    for n in List:
        print(f'现班级中的第{List.index(n)+1}个学生是: {n}')
    print(f'新加入一位同学: {check_name}\n当前总共有{len(List)}个学生')


