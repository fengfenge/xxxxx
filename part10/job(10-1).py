# ============================================================================
# 作业一：基础爬虫 - 获取网页内容
# ============================================================================
#
# 任务描述：
# 编写一个程序，爬取正北方网（https://www.northnews.cn/）的首页内容：
# 1. 使用requests库发送GET请求获取网页
# 2. 设置合适的请求头（User-Agent）
# 3. 打印响应状态码
# 4. 获取网页的标题（title标签）
# 5. 打印网页的部分内容（前500个字符）
# 6. 使用异常处理处理网络错误
#
# 要求：
# - 使用requests.get()发送请求
# - 设置合适的请求头
# - 使用try-except处理网络异常
# - 添加适当的注释
import requests

# url = "https://www.northnews.cn/"
def get_webpage(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        }
        response = requests.get(url)

        print(f"响应码：{response.status_code}")

        if response.status_code == 200:

            response.encoding = 'utf-8'
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.find('title')
            title_text = title.text if title else "未找到标题"

            print(f"网页标题：{title_text}")
            print(f"\n网页内容预览：{response.text[:500]}")
            return response.text

        else:
            print(f"请求失败，状态码：{response.status_code}")
            return None

    except requests.exceptions.Timeout:

        print("错误：请求超时！")

        return None

    except requests.exceptions.ConnectionError:

        print("错误：连接失败，请检查网络连接！")

        return None

    except requests.exceptions.RequestException as e:

        print(f"请求出错：{type(e).__name__}: {e}")

        return None

    except Exception as e:

        print(f"未知错误：{type(e).__name__}: {e}")

        return None

print("基础爬虫 - 获取网页内容")
url = "https://www.northnews.cn/"

print(f"\n目标网站：{url}")

content = get_webpage(url)

if content:
    print(f"\n成功获取网页内容！")
    print(f"内容长度：{len(content)} 字符")
else:
    print("\n未能获取网页内容")
