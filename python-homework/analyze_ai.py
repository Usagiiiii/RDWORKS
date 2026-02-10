import re
import collections

path = r"c:\Users\臧雪鹏\Desktop\RDWORKS-python\python-homework\摸鱼.ai"

with open(path, 'rb') as f:
    content = f.read()

# Try to decode as latin1 or utf8
text = content.decode('latin1', errors='ignore')

# Extract all operators (tokens ending with non-numeric, usually preceded by numbers)
# PostScript tokens are delimited by whitespace.
tokens = text.split()
histogram = collections.Counter()

# Regex to identify operators (alphabetic sequences)
op_pattern = re.compile(r'^[a-zA-Z]+$')
# Also specialized ones like *u, *U which might appear in AI
op_special = re.compile(r'^[\*]?[a-zA-Z]+$')

for t in tokens:
    if op_special.match(t):
        histogram[t] += 1

print("Operator Histogram:")
for op, count in histogram.most_common():
    print(f"{op}: {count}")

# Extract coordinates for 'm' (moveto) to See distribution
# Pattern: number number m
matches = re.findall(r'([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)\s+m', text)
print(f"\nFound {len(matches)} move operations.")
xs = [float(x) for x, y in matches]
ys = [float(y) for x, y in matches]

if xs:
    print(f"X range: {min(xs)} to {max(xs)}")
    print(f"Y range: {min(ys)} to {max(ys)}")

# Check specifically for the '鱼' part.
# If we have two clusters of coordinates, that explains two characters.
clusters = []
for x, y in zip(xs, ys):
    print(f"({x}, {y})")
