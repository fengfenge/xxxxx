# 任务描述：
# 编写一个学生信息管理程序，实现以下功能：
# 1. 创建一个字典，存储一个学生的信息：
#    - 姓名、年龄、学号、数学成绩、语文成绩、英语成绩
# 2. 计算该学生的总分和平均分，并添加到字典中
# 3. 根据平均分判断等级，并添加到字典中（等级判断规则同作业二）
# 4. 使用for循环遍历字典，打印所有信息
# 5. 提示用户输入要修改的科目和新的成绩，更新字典
# 6. 重新计算总分、平均分和等级
# 7. 输出更新后的学生信息
#
# 要求：
# - 使用字典存储学生信息
# - 使用字典的键访问和修改值
# - 使用字典的items()方法遍历
# - 使用条件语句进行等级判断
# - 添加适当的注释
student_info = {'name': 'ming', 'age': 18, 'ID': '202601', 'math': 80, 'chinese': 90, 'english': 100}

total_score = student_info['math'] + student_info['chinese'] + student_info['english']

student_info['total'] = total_score

avg_score = total_score / 3

student_info['avg'] = avg_score

if avg_score >= 90 :
    grade = '优秀'
elif avg_score >= 80 :
    grade = '良好'
elif avg_score >= 70 :
    grade = '中等'
elif avg_score >= 60 :
    grade = '及格'
else:
    grade = '不及格'

student_info['grade'] = grade

print('*'*10, '学生信息', '*'*10)

for key, value in student_info.items():
    if key == "avg":
        print(f"{key}：{value:.2f}")
    else:
        print(f"{key}：{value}")

print('*'*8, '更新学生信息', '*'*8)

#提示用户输入要修改的科目和新的成绩，更新字典
while True:

    modify_class = input('请输入修改的科目: ')

    if modify_class in student_info:
        modify_score = int(input('请此科目的新成绩: '))
        student_info[modify_class] = modify_score

        total_score = student_info['math'] + student_info['chinese'] + student_info['english']

        student_info['total'] = total_score

        avg_score = total_score / 3

        student_info['avg'] = avg_score

        if avg_score >= 90:
            grade = '优秀'
        elif avg_score >= 80:
            grade = '良好'
        elif avg_score >= 70:
            grade = '中等'
        elif avg_score >= 60:
            grade = '及格'
        else:
            grade = '不及格'

        student_info['grade'] = grade

        # print(student_info)

        print('''
0.继续
1.退出
        ''')
        is_exit = input('请输入是否继续(0 or 1): ')
        if is_exit == '0':
            continue
        elif is_exit == '1':
            break

    else:
        print(f'此{modify_class}科目不存在，请重新输入')

print('*'*6, '更新学生信息结果', '*'*6)

for key, value in student_info.items():
    if key == "avg":
        print(f"{key}：{value:.2f}")
    else:
        print(f"{key}：{value}")


