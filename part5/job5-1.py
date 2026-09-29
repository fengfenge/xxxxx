products = [
    {"名称": "苹果", "价格": 8.5, "库存": 50},
    {"名称": "香蕉", "价格": 6.0, "库存": 30},
    {"名称": "橙子", "价格": 9.0, "库存": 40},
    {"名称": "葡萄", "价格": 15.0, "库存": 20},
    {"名称": "西瓜", "价格": 12.0, "库存": 25}
]


def display_menu():
    """显示菜单选项"""
    print("\n请选择操作：")
    print("1. 查看所有商品")
    print("2. 添加商品到购物车")
    print("3. 查看购物车")
    print("4. 计算购物车总价")
    print("5. 清空购物车")
    print("6. 退出")


def show_products(products):
    """显示所有商品信息"""
    print("\n" + "=" * 60)
    print("所有商品信息")
    print("=" * 60)
    for i, product in enumerate(products, 1):
        print(f"{i}. {product['名称']} - 价格：{product['价格']}元/斤 - 库存：{product['库存']}斤")
    print("=" * 60)


def add_to_cart(cart, products, product_name, quantity):
    """添加商品到购物车"""
    for product in products:
        if product["名称"] == product_name:
            if quantity == product["库存"]:
                cart_item = {
                    "名称": product["名称"],
                    "价格": product["价格"],
                    "数量": quantity
                }
                cart.append(cart_item)
                print(f"\n成功添加 {quantity}斤 {product_name} 到购物车！")
                return True
            else:
                print(f"\n库存不足！{product_name} 的库存只有 {product['库存']} 斤。")
                return False
    print(f"\n未找到商品：{product_name}")
    return False


def show_cart(cart):
    """显示购物车内容"""
    if len(cart) == 0:
        print("\n购物车是空的！")
    else:
        print("\n" + "=" * 60)
        print("购物车内容")
        print("=" * 60)
        for i, item in enumerate(cart, 1):
            subtotal = item["价格"] * item["数量"]
            print(f"{i}. {item['名称']} - {item['价格']}元/斤 × {item['数量']}斤 = {subtotal:.2f}元")
        print("=" * 60)


def calculate_total(cart):
    """计算购物车总价"""
    if len(cart) == 0:
        return 0
    total_price = 0
    for item in cart:
        subtotal = item["价格"] * item["数量"]
        total_price = total_price + subtotal
    return total_price


def clear_cart(cart):
    """清空购物车"""
    cart.clear()
    print("\n购物车已清空！")


def main():
    """主函数，包含主循环和菜单逻辑"""
    cart = []
    print("=" * 60)
    print("欢迎使用购物车系统")
    print("=" * 60)

    while True:
        display_menu()
        choice = input("\n请输入选项（1-6）：")

        if choice == "6":
            print("感谢使用，再见！")
            break
        elif choice == "1":
            show_products(products)
        elif choice == "2":
            product_name = input("请输入要添加的商品名称：")
            quantity_str = input("请输入要购买的数量（斤）：")
            quantity = float(quantity_str)
            add_to_cart(cart, products, product_name, quantity)
        elif choice == "3":
            show_cart(cart)
        elif choice == "4":
            total = calculate_total(cart)
            if total == 0:
                print("\n购物车是空的，总价为0元！")
            else:
                print("\n" + "=" * 60)
                print("购物车总价")
                print("=" * 60)
                for item in cart:
                    subtotal = item["价格"] * item["数量"]
                    print(f"{item['名称']}：{item['价格']}元/斤 × {item['数量']}斤 = {subtotal:.2f}元")
                print("-" * 60)
                print(f"总计：{total:.2f}元")
                print("=" * 60)
        elif choice == "5":
            clear_cart(cart)
        else:
            print("\n错误：无效的选项，请输入1-6之间的数字！")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
