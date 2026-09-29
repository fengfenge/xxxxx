from traceback import print_tb

from part5.job1 import add

print("=" * 60)
print("第一小节：库的概念、安装与import用法")
print("=" * 60)

# 1.1 import的基本用法

print("\n1.1 import的基本用法示例\n")

import math
result = math.sqrt(16)
print(f"方法1：math.sqrt(16) = {result}")

import math as m
result = m.sqrt(25)
print((f"方法2：m.sqrt(25) = {result}"))

from math import sqrt,pi
result = sqrt(36)
print(f"方法3：sqrt(36) = {result}")
print(f"方法3 - pi = {pi}")

try:
    import pandas
    print(f"\npandas已安装")
except:
    print((f"\npandas未安装，请运行pip install pandas"))

print("\n" + "=" * 60)
print("第二小节：常用内置库")
print("=" * 60)

print("\n2.1 math库 - 数学函数\n")

import math
print(f"平方根：{math.sqrt((16))}")
print(f"幂运算：{math.pow(2,3)}")
print(f"圆周率：{math.pi}")
print(f"向上取整：{math.ceil(3.7)}")
print(f"向下取整：{math.floor(3.7)}")
print(f"绝对值：{math.fabs(-5)}")
print(f"对数：{math.log(10):.2f}")
print((f"正炫：{math.sin(math.pi/2):.2f}"))

print("\n2.2 time库 - 时间处理\n")
import time
timestamp = time.time()
print(f"当前时间戳：{timestamp}")
local_time = time.localtime(timestamp)
print(f"本地时间：{time.strftime('%Y-%m-%d %H:%M:%S', local_time)}")
print(f"开始暂停1秒")
time.sleep(1)
print(f"暂停结束")
now = time.localtime()
print(f"年：{now.tm_year}，月：{now.tm_mon}，日：{now.tm_mday}")

print("\n2.3 datetime库 - 日期时间处理\n")
from datetime import datetime, date, timedelta
now = datetime.now()
print(f"当前时间：{now}")
dt = datetime(2024,1,1,12,30,0)
print(f"指定日期：{dt}")
formatted = now.strftime("%Y-%m-%d %H:%M:%S")
print(f"格式化后：{formatted}")
future = now + timedelta(days=7)
print(f"7天后：{future}")
today = date.today()
print(f"今天日期：{today}")

print("\n2.4 random库 - 随机数生成\n")
import random
num = random.randint(1,100)
print(f"随机数（1-100）：{num}")
float_num = random.random()
print(f"随机浮点数：{float_num:.2f}")
fruits = ["苹果", "香蕉", "橙子", "葡萄"]
choice = random.choice(fruits)
print(f"随机选择：{choice}")
sample = random.sample(fruits, 3)
print(f"随机选择3个：{sample}")
numbers = [1,2,3,4,5]
random.shuffle(numbers)
print(f"打乱后：{numbers}")
rand_range = random.randrange(0,10,2)
print(f"0-10之间的偶数：{rand_range}")

print("\n2.5 os库 - 操作系统接口\n")
import os
current_dir = os.getcwd()
print(f"当前目录：{current_dir}")
if os.path.exists("../part6/test.txt"):
    print(f"test.txt文件存在")
else:
    print(f"test.txt文件不存在")

if os.path.isdir("../part6"):
    print(f"当前目录是文件夹")
files = os.listdir("../part6")
print(f"当前目录内容（前五个）：{files[:5]}")
if os.path.exists("../part6/job(6-1).py"):
    size = os.path.getsize("../part6/job(6-1).py")
    print(f"文件大小{size/1024}k")
path = os.path.join("folder", "file.txt")
print(f"路径拼接：{path}")
dirname = os.path.dirname("path/to/file.txt")
basename = os.path.basename("path/to/file.txt")
print(f"目录名为{dirname}，文件名为{basename}")

print("\n2.6 sys库 - 系统相关参数和函数\n")
import sys
print(f"python版本：{sys.version.split()[0]}")
print(f"命令行参数：{sys.argv}")
print(f"系统平台：{sys.platform}")
print(f"模块搜索路径数量：{len(sys.path)}")
sys.stdout.write("这是标准输出\n")
# sys.stderr.write("这是错误输出\n")

print("\n2.7 json库 - JSON数据处理\n")
import json
data = {
    "name": "张三",
    "age": 20,
    "scores": [85,90,88],
    "is_student": True
}

json_str = json.dumps(data, ensure_ascii=False, indent=4)
print("JSON字符串：")
print(json_str)
json_data = '{"name":"李四", "age": 19}'
python_obj = json.loads(json_data)
print(f"\npython对象：{python_obj}")
print(f"姓名：{python_obj['name']}")
with open("../part6/data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n数据已写入data.json文件")
with open("../part6/data.json", "r", encoding="utf-8") as f:
    loaded_data = json.load(f)
print(f"从文件读取数据：{loaded_data}")

print("\n2.8 pickle库 - Python对象序列化\n")
import pickle
data = {
    "name": "张三",
    "scores": [85, 90, 88],
    "info": {"age": 20, "grade": "大二"}
}
with open("../part6/data.pkl", "wb") as f:
    pickle.dump(data,f)
print(f"数据已保存在data.pkl文件（二进制文件）")

with open("../part6/data.pkl", "rb") as f:
    loaded_data = pickle.load(f)
print(f"从文件中读取数据：{loaded_data}")

bytes_data = pickle.dumps(data)
print(f"序列化后的字节长度：{len(bytes_data)}")
restored_data = pickle.loads(bytes_data)
print(f"反序列化后的数据{restored_data}")

print("\n2.9 文件读写基础（open函数）\n")
#写入文本文件
with open("../part6/test.txt", "w", encoding="utf-8") as f:
    f.write("第一行内容\n")
    f.write("第二行内容\n")
    f.write("第三行内容\n")
print("文件已写入")

#读取文本文件（全部内容）
with open("../part6/test.txt", "r", encoding="utf-8") as f:
    content = f.read()
    print("文件全部内容")
    print(content)

#逐行读取文件
print("\n逐行读取：")
with open("../part6/test.txt", "r", encoding="utf-8") as f:
    for line in f:
        print(line.strip())

#读取所有行到列表
with open("../part6/test.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()
    print(f"\n所有行（列表）：{lines}")

#追加模式
with open("../part6/test.txt", "a", encoding="utf-8") as f:
    f.write("追加的内容\n")
print("\n内容已追加")


print("\n" + "=" * 60)
print("第三小节：pandas库的使用")
print("=" * 60)

# pandas简介和创建DataFrame
print("\n3.1 pandas简介和创建DataFrame\n")
try:
    import pandas as pd
    data = {
        "姓名": ["张三", "李四", "王五", "赵六"],
        "年龄": [20, 19, 21, 20],
        "成绩": [85, 90, 88, 92],
        "班级": ["一班", "二班", "一班", "二班"]
    }
    df = pd.DataFrame(data)
    print("创建的DataFrame")
    print(df)
    print(f"\nDataFrame形状：{df.shape}")
    print(f"列名：{df.columns.tolist()}")
except ImportError:
    print("pandas未安装，请运行pip install pandas")

print("\n 读取CSV文件")
try:
    import pandas as pd
    data = {
        "姓名": ["张三", "李四", "王五", "赵六"],
        "年龄": [20, 19, 21, 20],
        "成绩": [85, 90, 88, 92]
    }
    df = pd.DataFrame(data)
    df.to_csv("student.csv", index=False, encoding="utf-8-sig")
    print("已创建student.csv文件")
    df_read = pd.read_csv("../part6/student.csv", encoding="utf-8-sig")
    print("\n从csv中读取数据")
    print(df_read)

except ImportError:
    print("pandas未安装，请运行：pip install pandas")

# 写入csv文件
print("\n写入CSV文件")
try:
    import pandas as pd
    data = {
        "姓名": ["张三", "李四", "王五"],
        "年龄": [20, 19, 21],
        "成绩": [85, 90, 88]
    }
    df = pd.DataFrame(data)
    df.to_csv("output.csv", index=False, encoding="utf-8-sig")
    print("数据已保存到output.csv")
    new_data = pd.DataFrame({"姓名": ["赵六"], "年龄": [20], "成绩": [92]})
    new_data.to_csv("output.csv", index=False, encoding="utf-8-sig")
    print("已追加新数据")
except ImportError:
    print("pandas未安装，请运行：pip install pandas")

#读取Excel文件
print("\n读取Excel文件\n")
try:
    import pandas as pd
    data = {
        "姓名": ["张三", "李四", "王五"],
        "年龄": [20, 19, 21],
        "成绩": [85, 90, 88]

    }
    df = pd.DataFrame(data)
    try:
        df.to_excel("student.xlsx", index=False, sheet_name="学生信息")
        print("已创建student.xlsx文件")
        df_excel = pd.read_excel("student.xlsx", sheet_name="学生信息")
        print("\n从excel读取数据")
        print(df_excel)
    except ImportError:
        print("需要安装openpyxl库：pip install openpyxl")
except ImportError:
    print("pandas未安装，请运行：pip install pandas")

#写入Excel文件
print("\n写入Excel文件\n")
try:
    import pandas as pd
    data1 = {
        "姓名": ["张三", "李四", "王五"],
        "年龄": [20, 19, 21],
        "成绩": [85, 90, 88]
    }
    df1 = pd.DataFrame(data1)
    data2 = {
        "课程": ["数学", "语文", "英语"],
        "平均分": [87, 89, 86]
    }
    df2 = pd.DataFrame(data2)
    try:
        df1.to_excel("output.xlsx", index=False, sheet_name="学生信息")
        print("已写入Excel文件（单个工作表）")
        with pd.ExcelWriter("../part6/output.xlsx", engine="openpyxl") as writer:
            df1.to_excel(writer, sheet_name="学生信息", index=False)
            df2.to_excel(writer, sheet_name="课程信息", index=False)
    except ImportError:
        print("需要安装openpyxl库：pip install openpyxl")
except ImportError:
    print("pandas未安装，请运行：pip install pandas")

# pandas数据查看和基本信息
print("\n3.6 pandas数据查看和基本信息\n")
try:
    import pandas as pd
    data = {
        "姓名": ["张三", "李四", "王五", "赵六", "钱七"],
        "年龄": [20, 19, 21, 20, 19],
        "成绩": [85, 90, 88, 92, 87],
        "班级": ["一班", "二班", "一班", "二班", "一班"]
    }
    df = pd.DataFrame(data)
    print("数据形状（行数, 列数）：")
    print(df.shape)
    print("\n列名：")
    print(df.columns.tolist())
    print("\n数据类型：")
    print(df.dtypes)
    print("\n前5行：")
    print(df.head())
    print("\n后3行：")
    print(df.tail(3))
    print("\n描述性统计：")
    print(df.describe())
except ImportError:
    print("pandas未安装，请运行：pip install pandas")

print("\n3.7 pandas数据选择和筛选\n")
try:
    import pandas as pd
    data = {
        "姓名": ["张三", "李四", "王五", "赵六"],
        "年龄": [20, 19, 21, 20],
        "成绩": [85, 90, 88, 92],
        "班级": ["一班", "二班", "一班", "二班"]
    }

    df = pd.DataFrame(data)
    print("选择'姓名'列")
    print(df["姓名"])
    print("\n选择多列：")
    print(df[["姓名", "成绩"]])
    print("\n成绩大于85的学生：")
    print(df[df["成绩"] > 85])
    print("\n一班的学生：")
    print(df[df["班级"] == "一班"])
    print("\n一班且成绩大于85的学生：")
    print(df[(df["班级"] == "一班") & (df["成绩"] > 85)])
    print("\n第1行（索引为0）：")
    print(df.iloc[0])
    print("\n第1-2行，第1-2列：")
    print(df.iloc[0:2, 0:2])

except ImportError:
    print("pandas未安装，请运行：pip install pandas")

print("\n3.8 pandas数据统计和聚合\n")
try:
    import pandas as pd
    data = {
        "姓名": ["张三", "李四", "王五", "赵六", "钱七"],
        "年龄": [20, 19, 21, 20, 19],
        "成绩": [85, 90, 88, 92, 87],
        "班级": ["一班", "二班", "一班", "二班", "一班"]
    }
    df = pd.DataFrame(data)
    print("成绩统计：")
    print(f"平均值：{df['成绩'].mean():.2f}")
    print(f"最大值：{df['成绩'].max()}")
    print(f"最小值：{df['成绩'].min()}")
    print(f"总和：{df['成绩'].sum()}")
    print(f"标准差：{df['成绩'].std():.2f}")
    print(f"中位数：{df['成绩'].median()}")
    print("\n按班级分组统计平均成绩：")
    print(df.groupby("班级")["成绩"].mean())
    print("\n每个班级的人数：")
    print(df["班级"].value_counts())
except ImportError:
    print("pandas未安装，请运行：pip install pandas")

print("\n3.9 pandas数据修改和新增\n")
try:
    import pandas as pd
    data = {
        "姓名": ["张三", "李四", "王五"],
        "年龄": [20, 19, 21],
        "成绩": [85, 90, 88]
    }
    df = pd.DataFrame(data)
    df["等级"] = df["成绩"].apply(lambda x: "优秀" if x >= 90 else "良好")
    print("新增'等级'列后：")
    print(df)
    df.loc[df["成绩"] >= 90, "等级"] = "优秀"
    print("\n修改后：")
    print(df)
    df_dropped = df.drop(columns=["等级"])
    print("\n删除'等级'列后：")
    print(df_dropped)
    new_row = pd.DataFrame({"姓名": ["赵六"], "年龄": [20], "成绩": [92]})
    df = pd.concat([df, new_row], ignore_index=True)
    print("\n新增行后：")
    print(df)
except ImportError:
    print("pandas未安装，请运行：pip install pandas")

print("\n" + "=" * 60)
print("第四小节：numpy库的使用")
print("=" * 60)

print("\n4.1 numpy简介和创建数组\n")
try:
    import numpy as np
    arr1d = np.array([1, 2, 3, 4, 5])
    print(f"一维数组：{arr1d}")
    print(f"数组形状：{arr1d.shape}")
    print(f"数组维度：{arr1d.ndim}")
    arr2d = np.array([[1, 2, 3], [4, 5, 6]])
    print(f"\n二维数组：\n{arr2d}")
    print(f"数组形状：{arr2d.shape}")
    zeros = np.zeros((3, 3))
    print(f"\n全0数组：\n{zeros}")
    ones = np.ones((2, 3))
    print(f"\n全1数组：\n{ones}")
    arange = np.arange(0, 10, 2) #从 0 开始、步长为 2、小于 10 的整数数组
    print(f"\narange数组：{arange}")
    linspace = np.linspace(0, 10, 5) #表示“从 0 到 10（含），均匀取 5 个点”
    print(f"\nlinspace数组：{linspace}")
except ImportError:
    print("numpy未安装，请运行：pip install numpy")

print("\n4.2 numpy数组运算\n")
try:
    import numpy as np
    arr1 = np.array([1, 2, 3, 4, 5])
    arr2 = np.array([6, 7, 8, 9, 10])
    print("数组相加：", arr1 + arr2)
    print("数组相乘：", arr1 * arr2)
    print("数组相减：", arr2 - arr1)
    print("数组相除：", arr2 / arr1)
    print("数组幂运算：", arr1 ** 2)
    print("\n标量运算：")
    print("每个元素加10：", arr1 + 10)
    print("每个元素乘以2：", arr1 * 2)
    matrix1 = np.array([[1, 2], [3, 4]])
    matrix2 = np.array([[5, 6], [7, 8]])
    print(f"\n矩阵1：\n{matrix1}")
    print(f"矩阵2：\n{matrix2}")
    print(f"矩阵点积：\n{np.dot(matrix1, matrix2)}")
except ImportError:
    print("numpy未安装，请运行：pip install numpy")