# 任务描述：
# 定义一个BankAccount类，模拟银行账户，包含以下内容：
# 1. __init__方法：初始化账户号、账户名、初始余额（默认0）
# 2. deposit方法：存款（增加余额）
# 3. withdraw方法：取款（减少余额，需要检查余额是否充足）
# 4. get_balance方法：查询余额
# 5. display_info方法：显示账户信息
#
# 在主程序中：
# - 创建一个账户
# - 进行多次存款和取款操作
# - 显示账户信息
#
# 要求：
# - 使用self访问和修改属性
# - 处理余额不足的情况
# - 添加适当的注释
class BankAccount:
    def __init__(self, account_id, account_name, initial_balance=0):
        self.account_id = account_id
        self.account_name = account_name
        self.account_balance = initial_balance

    def deposit(self, amount):
        """存款"""
        if amount > 0:
            self.account_balance = self.account_balance + amount
            print(f"{self.account_name}存入{amount}元，余额：{self.account_balance}元")
        else:
            print("存款金额必须大于0")

    def withdraw(self, amount):
        """取款"""
        if amount > 0:
            if amount <= self.account_balance:
                self.account_balance = self.account_balance - amount
                print(f"{self.account_name}取出{amount}元，余额：{self.account_balance}元")
            else:
                print("余额不足！")
        else:
            print("取款金额必须大于0")

    def get_balance(self):
        """查询余额"""
        print(f"{self.account_name}的账户余额：{self.account_balance}元")
        return self.account_balance

    def display_info(self):
        print("账户信息：")
        print("账户号: ", self.account_id)
        print("账户名: ", self.account_name)
        print("账户余额：: ", self.account_balance)

# 使用银行账户
account = BankAccount("110","王五",1000)
account.get_balance()
account.deposit(500)
account.deposit(300)
account.withdraw(200)
account.withdraw(100)
account.get_balance()
account.display_info()