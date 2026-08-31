# tools/audit_logging.py
import os
import re
import sys

def audit_file(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    errors = []
    for i, line in enumerate(lines, 1):
        # Busca logger.info("TAG", "mensaje") con dos argumentos literales
        if re.search(r'logger\.(info|warning|error|debug)\s*\(\s*"[^"]+"\s*,\s*"[^"]+"', line):
            errors.append((i, line.strip()))
    return errors

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    failed = False
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if fname.endswith('.py'):
                full = os.path.join(dirpath, fname)
                errors = audit_file(full)
                if errors:
                    print(f"❌ {full}:")
                    for line_no, line in errors:
                        print(f"  L{line_no}: {line}")
                    failed = True
    if failed:
        sys.exit(1)
    else:
        print("✅ Todos los archivos usan logging correctamente.")

if __name__ == "__main__":
    main()
