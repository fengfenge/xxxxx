# 任务描述：
# 编写一个程序，定义以下函数：
# 1. add(a, b)：计算两个数的和
# 2. subtract(a, b)：计算两个数的差
# 3. multiply(a, b)：计算两个数的积
# 4. divide(a, b)：计算两个数的商（注意处理除数为0的情况）
# 5. calculate_bmi(weight, height)：计算BMI指数（体重除以身高的平方）
#
# 在主程序中：
# - 测试每个函数，调用并输出结果
# - 提示用户输入两个数字，调用add函数计算和
# - 提示用户输入体重和身高，调用calculate_bmi函数计算BMI

def add(a, b):
    """
    计算两个数的和：

    参数：
        a: 第一个参数, 可int, 可float
        b: 第二个参数, 可int, 可float

    返回：
        两数的和的值, 可int, 可float
    """
    two_num_sum = a + b
    return two_num_sum

def subtract(a, b):
    """
    计算两个数的差：

    参数：
        a: 第一个参数减数, 可int, 可float
        b: 第二个参数被减数, 可int, 可float

    返回：
        两数的差的值, 可int, 可float
    """
    two_num_sub = a - b
    return two_num_sub

def multiply(a, b):
    """
    计算两个数的乘积：

    参数：
        a: 第一个参数, 可int, 可float
        b: 第二个参数, 可int, 可float

    返回：
        两数的乘的值, 可int, 可float
    """    
    two_num_mul = a * b
    return two_num_mul

def divide(a, b):
    """
    计算两个数的乘积：

    参数：
        a: 第一个参数除数, 可int, 可float
        b: 第二个参数被除数, 可int, 可float

    返回：
        两数的乘的值, 可int, 可float
    """
    two_num_div = a / b
    return two_num_div

def calculate_bmi(weight, height):
    """
    计算BMI指数（体重除以身高的平方）

    参数：
        weight: 第一个参数，单位kg，可int, 可float
        height: 第二个参数，单位m，可int, 可float
    返回：
        BMI的值
    """
    BMI = weight / (height**2)
    return BMI

result_BMI = calculate_bmi(60.5, 1.70)
print(f'BMI为{result_BMI:.2f}')


result_sum = add(1, 2)

print(result_sum)
