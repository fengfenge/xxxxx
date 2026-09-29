# 任务描述：
# 编写一个程序，实现以下功能：
# 1. 使用for循环和range()函数打印1到20的所有数字
# 2. 使用for循环和range()函数打印1到20的所有偶数
# 3. 使用for循环和range()函数打印1到20的所有奇数
# 4. 使用for循环和range()函数倒序打印20到1
# 5. 使用for循环计算1到10的乘积（阶乘）
# 6. 使用for循环遍历一个字符串，统计其中某个字符出现的次数
#    （提示：可以让用户输入一个字符串和一个要查找的字符）
#
# 要求：
# - 使用for循环和range()函数
# - 使用字符串遍历
# - 输出格式要清晰
# - 添加适当的注释
for i in range(1,21):
    print(i)

print('~~~~~~~~~~~~~~~~~~~~~~~~~~')

for i in range(1,21):
    if i % 2 == 0:
        print(i)

print('~~~~~~~~~~~~~~~~~~~~~~~~~~')
for i in range(1,21):
    if i % 2 == 1:
        print(i)

print('~~~~~~~~~~~~~~~~~~~~~~~~~~')
for i in range(20,0,-1):
    print(i)

print('~~~~~~~~~~~~~~~~~~~~~~~~~~')
fac = 1
for i in range(1,10):
    fac = fac * i
print(fac)

print('~~~~~~~~~~~~~~~~~~~~~~~~~~')

strings = input('请用户输入一个字符串: ')

char = input('请用户输入需要查找的字符: ')

count = 0
for i in strings:
    if char == i:

        count = count + 1
print(count)