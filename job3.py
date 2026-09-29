num1 = int(input('请用户输入一个正整数(求和): '))

n1 = 0
sum1 = 0
while n1 <= num1:

    sum1 = sum1 + n1
    n1 = n1 + 1

print(sum1)

num2 = int(input('请用户输入一个正整数(求偶和): '))

n2 = 0
sum2 = 0
while n2 <= num2:
    if n2 % 2 == 0:
        sum2 = sum2 + n2

    n2 = n2 + 1

print(sum2)

num3 = int(input('请用户输入一个正整数(求奇和): '))

n3 = 0
sum3 = 0
while n3 <= num3:
    if n3 % 2 == 1:
        sum3 += n3
    n3 += 1
print(sum3)