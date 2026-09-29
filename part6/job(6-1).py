
class Student:
    def __init__(self, name, age, s_id):
        self.name = name
        self.age = age
        self.id = s_id
        self.scores = {}
        self.total_score = 0

    def display_info(self):
        print(f"基本信息：{self.name}, {self.age}岁, 学号{self.id}")


    def set_score(self, math_score, chinese_score, english_score):
        self.scores["数学"] = math_score
        self.scores["语文"] = chinese_score
        self.scores["英语"] = english_score
        # print(self.info)
        return self.scores
    
    def calculate_average(self):
        avg_score = (self.scores["数学"] + self.scores["语文"] + self.scores["英语"]) / 3
        return avg_score

    def get_grade(self):
        average = self.calculate_average()
        if average >= 90:
            return "优秀"
        elif average >= 80:
            return "良好"
        elif average >= 70:
            return "中等"
        elif average >= 60:
            return "及格"
        else:
            return "不及格"
    
    def show_info(self):

        print(f"姓名：{self.name}")
        print(f"年龄：{self.age}")
        print(f"学号: {self.id}")
        print(f"成绩：\n 数学：{self.scores["数学"]}\n 语文：{self.scores["语文"]}\n 英语：{self.scores["英语"]}")
        print(f"平均分：{self.calculate_average():.2f}")  # 调用其他方法
        print(f"等级：{self.get_grade()}")  # 调用其他方法

# 两个实例
student1 = Student("李文", 18, "202601")
student2 = Student("王辉", 20, "202602")

print("="*5, "展示基本信息：", "="*5)
student1.display_info()
student2.display_info()

student1.set_score(80, 90, 100)
student2.set_score(99, 85, 60)
print(' ')
print("#"*5, "展示全部信息：", "#"*5)
student1.show_info()
print("*"*10)
student2.show_info()













