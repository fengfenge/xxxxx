# 任务描述：
# 编写一个程序，定义以下函数：
# 1. greet(name, greeting="你好", punctuation="！")：
#    使用默认参数，打印问候语
# 2. calculate_discount_price(price, discount=0.1, tax=0.0)：
#    计算折扣后的价格（考虑税费）
# 3. create_student(name, age, grade="未定", city="未知")：
#    创建学生信息字典，使用默认参数
# 4. print_info(title, items, separator=", ", end="\n")：
#    格式化打印信息，使用关键字参数
#
# 在主程序中：
# - 测试每个函数，使用默认参数和提供参数两种情况
# - 演示关键字参数的使用
# - 输出结果
#
# 要求：
# - 理解默认参数的作用
# - 理解关键字参数的使用
# - 添加详细的注释

def greet(name, greeting="你好", punctuation="！"):
    print(f'{name}, {greeting}{punctuation}')

def calculate_discount_price(price, discount=0.1, tax=0.0):
    """
    折后价（不含税）= 原价×(1−折扣率)
    税费=折后价（不含税）×税率
    最终价格=折后价（不含税）+税费
    """
    first_price = price * (1 - discount)
    tax_cost = first_price * tax
    final_price = first_price + tax_cost
    return final_price

def create_student(name, age, grade="未定", city="未知"):
    student = {
        '姓名': name,
        '年龄': age,
        '分数等级': grade,
        '城市': city
    }
    return student

def print_info(title, items, separator=", ", end="\n"):
    #格式化打印信息，使用关键字参数
    print(f'项目{items}{separator}标题{title}{end}')




# 在主程序中：
# - 测试每个函数，使用默认参数和提供参数两种情况
# - 演示关键字参数的使用
# - 输出结果
greet('李文')
greet('李文', 'excuse me', '!!!')
greet(punctuation='?', name='李文', greeting='干嘛')


final_price_result  = calculate_discount_price(80)
print(f'{final_price_result:.2f}')

final_price_result  = calculate_discount_price(80, 0.5, 0.3)
print(f'{final_price_result:.2f}')

final_price_result  = calculate_discount_price(discount=0.7, price=90, tax=0.1)
print(f'{final_price_result:.2f}')

student_result = create_student('tian', 18)
print(student_result)

student_result = create_student('tian', 18, '优秀', '北京')
print(student_result)

print_info('ai人工智能', '开发agent')