import os
import re
import glob

def main():
    strategies_dir = "backend/app/strategies"
    pattern = re.compile(r'return\s+\(\s*position\.shift\(\s*1\s*\)\s*\*\s*daily_ret\s*\)\.fillna\(\s*0\.0\s*\)')
    replacement = r'return self.calculate_returns(position, daily_ret)'

    count = 0
    for filepath in glob.glob(os.path.join(strategies_dir, "*.py")):
        if "__init__" in filepath:
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        if pattern.search(content):
            new_content = pattern.sub(replacement, content)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            count += 1
            print(f"Updated: {filepath}")
        
        # Check for similar variations like daily_returns
        pattern2 = re.compile(r'return\s+\(\s*position\.shift\(\s*1\s*\)\s*\*\s*daily_returns\s*\)\.fillna\(\s*0\.0\s*\)')
        if pattern2.search(content):
            new_content = pattern2.sub(r'return self.calculate_returns(position, daily_returns)', content)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            count += 1
            print(f"Updated (var 2): {filepath}")

    print(f"Total files updated: {count}")

if __name__ == "__main__":
    main()
