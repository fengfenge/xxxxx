
class ShoppingCart:
    def __init__(self, consumer_name):
        self.consumer_name = consumer_name
        self.cart = []
        self.total_price = 0

    def add_item(self, item_name, price, quantity):
        item = {
            "名称": item_name,
            "价格": price,
            "数量": quantity
        }
        self.cart.append(item)

    def remove_item(self, item_name):
        for item in self.cart:
            if item["名称"] == item_name:
                self.cart.remove(item)

    def calculate_total(self):
        self.total_price = 0
        for item in self.cart:
            self.total_price = self.total_price + item["价格"] * item["数量"]

    def display_cart(self):
        print(f"{self.consumer_name}的购物车: ")
        for item in self.cart:
            print(f" 商品名称：{item["名称"]}\n 价格{item["价格"]}/个\n 数量{item["数量"]}")

        print(f"总价为：{self.total_price}")

    def clear_cart(self):
        self.cart.clear()

cart1 = ShoppingCart("李四")
cart1.add_item("牙膏", 16.5, 1)
cart1.add_item("牙刷", 5, 3)
cart1.add_item("桶", 10,6)
cart1.calculate_total()
cart1.display_cart()

remove_item = input("输入要从购物车移除的商品: ")
print(f"移除{remove_item}后，{cart1.consumer_name}购物车和总价展示: ")
cart1.remove_item(remove_item)
cart1.calculate_total()
cart1.display_cart()
