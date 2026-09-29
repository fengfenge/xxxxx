# 任务描述：
# 编写一个成绩管理系统，实现以下功能：
# 1. 创建一个列表存储5个学生的成绩（可以预设或用户输入）
# 2. 计算并输出：总分、平均分、最高分、最低分
# 3. 统计及格人数（成绩&gt;=60）和不及格人数
# 4. 找出所有大于等于90分的成绩，并输出
# 5. 使用循环遍历列表，为每个成绩评定等级：
#    - 90分及以上：优秀
#    - 80-89分：良好
#    - 70-79分：中等
#    - 60-69分：及格
#    - 60分以下：不及格
# 6. 输出格式化的成绩单
#
# 要求：
# - 使用列表的索引访问元素
# - 使用for循环遍历列表
# - 使用条件语句进行判断
# - 使用列表的append()方法（如果需要）
# - 输出格式要清晰美观
from operator import index

# 5位学生成绩列表
score = []

for i in range(1,6):

    score.append(int(input(f'请依次输入第{i}位学生的成绩: ')))

print(' ')

sum = score[0]+score[1]+score[2]+score[3]+score[4]

avg = sum/len(score)

print(f'''分数统计:
总分为: {sum}
平均分为: {avg}
最高分: {max(score)}
最低分: {min(score)}
''')

pass_count = []

nopass_count = []

for s in score:
    if s >= 60:
        pass_count.append(s)

        if s >= 90:

            print(' ')

            print(f'大于等于90分以上的成绩有: {s}')

            print(f'当前第{score.index(s)+1}位成绩为{s}, 等级: 优秀!\n')

        elif s >= 80:

            print(f'当前第{score.index(s)+1}位成绩为{s}, 等级: 良好')

        elif s >= 70:

            print(f'当前第{score.index(s)+1}位成绩为{s}, 等级为: 中等')

        elif s >= 60:

            print(f'当前第{score.index(s)+1}位成绩为{s}, 等级为: 及格')

    else:

        print(f'当前第{score.index(s)+1}成绩为{s}, 等级为: 不及格')

        nopass_count.append(s)

print(f'''
统计及格人数和不及格人数: 
及格人数为: {len(pass_count)}
不及格人数为: {len(nopass_count)}
''')

