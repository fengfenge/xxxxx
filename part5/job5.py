# 任务描述：
# 将之前的购物车系统改造成使用函数的版本，定义以下函数：
# 1. display_menu()：显示菜单
# 2. show_products(products)：显示所有商品
# 3. add_to_cart(cart, products, product_name, quantity)：添加商品到购物车
# 4. show_cart(cart)：显示购物车内容
# 5. calculate_total(cart)：计算购物车总价
# 6. clear_cart(cart)：清空购物车
# 7. main()：主函数，包含主循环和菜单逻辑
#
# 在主程序中：
# - 调用main()函数启动程序
# - 使用函数组织代码，使程序更模块化
#
# 要求：
# - 使用函数重构代码
# - 每个功能对应一个函数
# - 使用main()函数作为程序入口
# - 代码结构清晰，易于维护
# - 添加详细的注释
from statistics import quantiles

product_list = [
    {"名称": "毛巾", "价格": 10.5, "数量": 10},
    {"名称": "香皂", "价格": 5.0, "数量": 25},
    {"名称": "牙膏", "价格": 13.0, "数量": 20},
    {"名称": "桶", "价格": 15.5, "数量": 5},
    {"名称": "盆子", "价格": 8.0, "数量": 15}
]
def display_menu():
    """
    打印菜单，主函数中根据输入“1”，实现以下不同的功能
    """
    print("""
菜单: 
    1. 查看所有商品
    2. 添加商品到购物车
    3. 查看购物车
    4. 计算购物车总价
    5. 清空购物车
    6. 退出
    """)

def show_products(products):
    """
    TUDO: 主函数调用，输入"1"展示所有商品信息，不需要return
    参数：
        products: list, 使用enumerate方法，根据序号展示
    返回值：
        无
    """
    for index, product in enumerate(products, 1):
        print(f"{index}. 商品的名称是{product["名称"]}，商品的价格{product["价格"]}/个，商品的库存有{product["数量"]}个")

def add_to_cart(cart, products, product_name, quantity):
    """
    TUDO: 添加商品到购物车
    :param cart: list，
    :param products:
    :param product_name:
    :param quantity:
    :return:
    """
    for product in products:
        if  product["名称"] == product_name:
            if  0 <= quantity <= product["数量"]:
                shop_dist = {
                    "名称": product_name,
                    "价格": product["价格"],
                    "数量": quantity
                }
                cart.append(shop_dist)

def show_cart(cart):
    if cart:
        for i, item in enumerate(cart, 1):
            print(f'{i}, 购买的商品名称{item["名称"]}，购买的商品价格{item["价格"]}/个，购买的商品数量{item["数量"]}')
    else:
        print("没有选购商品")

def calculate_total(cart, products):
    # 该商品的总价 = 商品单价 x 商品数量
    # 所有商品的总价 = 商品的总价相加
    total_price = 0
    for product in products:
        for item in cart:
            if product["名称"] == item["名称"]:
                print(f'该商品{product["名称"]}已在购物车')
                product_total_price = item["价格"] * item["数量"]
                total_price =  product_total_price + total_price
    return  total_price

def clear_cart(cart):
    cart.clear()

def main():

    display_menu()
    cart_list = []
    while True:
        menu_str = input('请输入菜单编号（1/2/3/4/5/6）：')
        if menu_str == '1':
            show_products(product_list)
        elif menu_str == '2':
            product_name = input('请输入添加购物车的商品名称: ')
            count = int(input('请输入添加到购物车该商品的数量: '))
            add_to_cart(cart_list, product_list, product_name, count)
        elif menu_str == '3':
            show_cart(cart_list)
        elif menu_str == '4':
            total_price = calculate_total(cart_list, product_list)
            print(total_price)
        elif menu_str == '5':
            clear_cart(cart_list)
        elif menu_str == '6':
            break

main()