# 任务描述：
# 编写一个程序，定义以下函数：
# 1. calculate_average(scores)：接收一个成绩列表，计算并返回平均分
# 2. find_max_min(scores)：接收一个成绩列表，返回最高分和最低分（返回两个值）
# 3. count_pass_fail(scores, pass_score=60)：接收成绩列表和及格分数线（默认60），返回及格人数和不及格人数
# 4. get_grade(score)：接收一个分数，返回等级（优秀/良好/中等/及格/不及格）
# 5. process_scores(scores)：接收成绩列表，调用以上函数，返回处理结果（字典形式）
#
# 在主程序中：
# - 创建一个成绩列表
# - 调用process_scores函数处理成绩
# - 输出格式化的成绩报告
#
# 要求：
# - 使用默认参数（pass_score=60）
# - 函数返回多个值（使用元组）
# - 函数返回字典
# - 添加详细的注释
def calculate_average(scores):
    """
    参数：
        scores: 成绩列表
    返回：
        平均值，根据列表sum()和len()方法求得
    """
    avg = sum(scores)/len(scores)
    return avg

def find_max_min(scores):
    """
    参数：
        scores: 成绩列表
    返回：
        两个值，最大和最小值，根据列表max()和min()方法求得
    """
    max_score = max(scores)
    min_score = min(scores)
    return max_score,min_score

def count_pass_fail(scores, pass_score=60):
    """
    参数：
        scores: list
        pass_score: 默认值60
    变量：
        pass_count: 初始值[]，及格人数空列表，根据pass_score判断是否追加到对应的列表中
        not_pass_count: 初始值[]，不及格人数空列表
    返回:
        两个值，及格人数和不及格人数，取列表len()方法
    """
    pass_count = []
    not_pass_count = []
    for score in scores:
        if score >= pass_score:
            pass_count.append(score)
        elif score < pass_score:
            not_pass_count.append(score)
        else:
            return None
    return len(pass_count),len(not_pass_count)


def get_grade(score):
    """
    参数：
        score: 成绩列表
    返回：
        根据传入的成绩列表判断成绩，返回对应的grades
    """
    if score >= 90:
        return '优秀'
    elif score >= 80:
        return '良好'
    elif score >= 70:
        return '中等'
    elif score >= 60:
        return '及格'
    else:
        return '不及格'

scores_dist = {}
def process_scores(scores):
    """
    参数：
        scores: 成绩列表
    TUDO:
        调用上述的方法获取对应的值，并用对应的变量承接，添加到scores_dist字典中
    返回：
        scores_dist字典
    """

    scores_dist['scores'] = scores

    avg_score = calculate_average(scores)
    scores_dist['result_avg'] = avg_score

    max_score, min_score = find_max_min(scores)
    scores_dist['max_score'] = max_score
    scores_dist['min_score'] = min_score

    pass_counts_person, not_pass_counts_person = count_pass_fail(scores)
    scores_dist['pass_counts'] = pass_counts_person
    scores_dist['not_pass_counts'] = not_pass_counts_person

    # 初始化成绩等级列表，根据成绩列表中不同值循环进入方法get_grade(score)，并追加到grades得到grades列表
    grades = []
    for score in scores:

        result_get_grade = get_grade(score)

        grades.append(result_get_grade)
        scores_dist['grades'] = grades

    # result = {
    #     '成绩': scores,
    #     'result_avg': avg_score,
    #     'max_score': max_score,
    #     'min_score': min_score,
    #     'pass_counts': pass_counts_person,
    #     'not_pass_counts': not_pass_counts_person,
    #     'grades': grades
    # }
    return scores_dist

# 成绩列表初始化
scores_list = [88,66,77,99,100]

# 调用主函数process_scores得到成绩字典
result_process_scores = process_scores(scores_list)
# print(result_process_scores)
# 根据得到的成绩字典获取到不同key对应的value，格式化输出
print('*'*5,'成绩报告如下','*'*5)
for result_scores_key, result_scores_value  in result_process_scores.items():
    if result_scores_key == 'scores':
        print(f'    成绩单: {result_scores_value}')
    elif result_scores_key == 'result_avg':
        print(f'    平均成绩: {result_scores_value}')
    elif result_scores_key == 'max_score':
        print(f'    最大成绩: {result_scores_value}')
    elif result_scores_key == 'min_score':
        print(f'    最小成绩: {result_scores_value}')
    elif result_scores_key == 'pass_counts':
        print(f'    及格人数: {result_scores_value}')
    elif result_scores_key == 'not_pass_counts':
        print(f'    不及格人数: {result_scores_value}')
    elif result_scores_key == 'grades':
        print(f'    分数等级: {result_scores_value}')
