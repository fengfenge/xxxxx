# 任务描述：
# 编写一个学生管理系统，定义以下函数：
# 1. create_student(name, age, scores)：创建并返回一个学生字典
# 2. calculate_student_average(student)：计算学生的平均分并更新字典
# 3. get_student_grade(student)：根据平均分判断等级并更新字典
# 4. display_student_info(student)：格式化显示学生信息
# 5. add_student(students_list, name, age, scores)：向学生列表添加新学生
# 6. find_student(students_list, name)：在学生列表中查找指定姓名的学生
# 7. get_class_average(students_list)：计算班级平均分
#
# 在主程序中：
# - 创建一个空的学生列表
# - 使用循环添加至少3个学生
# - 显示所有学生信息
# - 查找并显示指定学生的信息
# - 显示班级平均分
def create_student(name, age, scores):
    student = {
        'name': name,
        'age': age,
        'scores': scores
    }
    return student

def calculate_student_average(student):
    avg_score = (student['scores']['math'] + student['scores']['chinese'] + student['scores']['english']) / 3
    student['avg_score'] = avg_score

def get_student_grade(student):
    average = student['avg_score']
    if average >= 90:
        grade = '优秀'
    elif average >= 80:
        grade = '良好'
    elif average >= 70:
        grade = '中等'
    elif average >= 60:
        grade = '及格'
    else:
        grade = '不及格'
    student['grade'] = grade
    return grade

def display_student_info(student):
    print(f'学生姓名: {student['name']}')
    print(f'学生年龄: {student['age']}')
    print(f'学生成绩：\n 数学成绩: {student['scores']['math']}\n 语文成绩: {student['scores']['chinese']}\n 英语成绩: {student['scores']['english']}\n平均成绩: {student['avg_score']:.2f}')

def add_student(students_list, name, age, scores):
    student = create_student(name, age, scores)
    calculate_student_average(student)
    get_student_grade(student)
    students_list.append(student)

def find_student(students_list, name):
    for student in students_list:
        if student["name"] == name:
            return student
    return None

def get_class_average(students_list):
    for student in students_list:
        class_average = calculate_student_average(student) / len(students_list)
    return class_average

def main():
# 在主程序中：
# - 创建一个空的学生列表
# - 使用循环添加至少3个学生
# - 显示所有学生信息
# - 查找并显示指定学生的信息
# - 显示班级平均分
    students = []

    for i in range(3):
        name = input(f'输入第{i+1}位学生的姓名: ')
        age = int(input(f'输入第{i+1}位学生的年龄: '))
        math_score = int(input('数学成绩: '))
        chinese_score = int(input('语文成绩: '))
        english_score = int(input('英语成绩: '))

        scores = {
            'math': math_score,
            'chinese': chinese_score,
            'english': english_score
        }

        add_student(students, name, age, scores)

    print('*'*10)

    for student in students:
        display_student_info(student)

    search_name = input("请输入要查找的学生姓名：")
    found_student = find_student(students, search_name)

    if found_student:
        print("\n找到学生：")
        display_student_info(found_student)
    else:
        print(f"\n未找到姓名为 '{search_name}' 的学生！")

    class_avg = get_class_average(students)
    print(class_avg)

main()

