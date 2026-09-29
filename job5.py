# 任务描述：
# 编写一个带菜单的简单计算器程序，实现以下功能：
# 1. 显示菜单选项：
#    - 1. 加法
#    - 2. 减法
#    - 3. 乘法
#    - 4. 除法
#    - 5. 退出
# 2. 使用while循环让程序可以重复执行，直到用户选择退出
# 3. 根据用户选择的菜单项，提示输入两个数字
# 4. 执行相应的运算并输出结果
# 5. 对于除法运算，需要判断除数是否为0，如果为0则提示错误
# 6. 每次运算后，重新显示菜单
#
# 要求：
# - 使用while循环实现重复执行
# - 使用if-elif-else判断菜单选项
# - 使用嵌套条件判断除数是否为0
# - 输出格式要清晰美观
# - 添加详细的注释说明
#
# 提示：
# - 可以使用一个变量来控制循环（如choice = "5"时退出）
# - 菜单选项可以用字符串比较（如 choice == "1"）
from random import choice
from time import sleep

while True:
    print('''
    选择计算菜单:
       1. 加法
       2. 减法
       3. 乘法
       4. 除法
       5. 退出
    ''')

    choice = input('请用户输入菜单选项(1-5): ')
    # num1 = input('请用户输入第一个数字: ')
    # num2 = input('请用户输入第二个数字: ')
    if choice == '1':
        print('正在进入加法计算，请稍候')
        sleep(0.5)
        num1 = int(input('请用户输入第一个加数: '))
        num2 = int(input('请用户输入第二个加数: '))
        print(num1+num2)
        print('计算完成，正在退出，请继续选择计算菜单')
        sleep(1)
    elif choice == '2':
        print('正在进入减法计算，请稍候')
        sleep(0.5)
        num1 = int(input('请用户输入第一个减数: '))
        num2 = int(input('请用户输入第二个被减数: '))
        print(num1-num2)
        print('计算完成，正在退出，请继续选择计算菜单')
        sleep(1)
    elif choice == '3':
        print('正在进入乘法计算，请稍候')
        sleep(0.5)
        num1 = int(input('请用户输入第一个乘数: '))
        num2 = int(input('请用户输入第二个乘数: '))
        print(num1*num2)
        print('计算完成，正在退出，请继续选择计算菜单')
        sleep(1)
    elif choice == '4':
        print('正在进入除法计算，请稍候')
        sleep(0.5)
        num1 = int(input('请用户输入第一个数为除数: '))
        num2 = int(input('请用户输入第二个数为被除数: '))
        if num2 == 0:
            print('被除数不能为0，请重新输入')
            num2 = int(input('请用户输入第二个数为被除数: '))
            print(num1/num2)
            print('计算完成，正在退出，请继续选择计算菜单')
            sleep(1)
        else:
            print(num1/num2)
            print('计算完成，正在退出，请继续选择计算菜单')
            sleep(1)
    else :
        break
