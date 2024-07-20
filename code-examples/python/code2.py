def compute_factorial(number):
    if number == 0:
        return 1
    else:
        return number * compute_factorial(number - 1)

result = compute_factorial(5)
print(result)