def hello_world():
    print("Hello World!")
    return "Hello World!"

def main():
    print("Testing hello_world function...")
    result = hello_world()
    print(f"Function returned: {result}")
    print("Test completed successfully!")

if __name__ == "__main__":
    main()