# 任务描述：
# 编写一个多学生管理系统，实现以下功能：
# 1. 创建一个列表，列表中每个元素是一个字典，存储一个学生的信息
#    （至少包含3个学生的信息）
# 2. 使用for循环遍历列表，打印所有学生的基本信息（姓名、年龄、成绩等）
# 3. 计算所有学生的平均分，并找出平均分最高的学生
# 4. 统计每个等级的人数（优秀、良好、中等、及格、不及格）
# 5. 提示用户输入一个学生姓名，查找并显示该学生的详细信息
# 6. 如果找到，允许用户修改该学生的某科成绩
#
# 要求：
# - 使用列表存储多个字典
# - 使用嵌套循环（外层遍历列表，内层遍历字典）
# - 使用条件语句进行判断和查找
# - 输出格式要清晰美观
# - 添加详细的注释

student_info = [
    {
        'name': 'ming',
         'age': 21,
         'math': 80,
         'chinese': 90,
         'english': 100
     },
    {
        'name': 'hong',
        'age': 18,
        'math': 70,
        'chinese': 100,
        'english': 80
    },
    {
        'name': 'tian',
        'age': 19,
        'math': 100,
        'chinese': 90,
        'english': 60
    }
]

for info in student_info:
    for key, value in info.items():
        if key == "name":
            print('*'*5,f'学生{value}的基本信息','*'*5)
            print(f'name:{value}')
        else:
            print(f"{key}: {value}")
            class_score = []
            if key == "math" or key == 'chinese' or key == "english":
                # class_score = []
                class_score.append(info[key])
            print(class_score)
                # print(f"{value}")



                # print(avg_score)

        #         total_score = info['math'] + info['chinese'] + info['english']
        #
        #         avg_score = total_score/ 3
        #
        # avg_score = sum(info.values()) / len(info)
        #
        #     if key == "math" or key == 'chinese' or key == "english":
        #         total_score = info[key]
        #         avg_score = sum(info.values())/len(info)








