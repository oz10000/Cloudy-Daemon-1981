#!/usr/bin/env python3
"""
Auditoría automática de errores async/await y firmas en el repositorio.
Uso: python tools/audit_async.py
"""
import ast
import os
import sys
from pathlib import Path

SRC_DIR = "src"

class AsyncAuditor(ast.NodeVisitor):
    def __init__(self):
        self.errors = []
        self.async_functions = set()
        self.function_defs = {}
        self.calls = []

    def visit_AsyncFunctionDef(self, node):
        self.async_functions.add(node.name)
        self.function_defs[node.name] = {'type': 'async', 'node': node}
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.function_defs[node.name] = {'type': 'sync', 'node': node}
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            # Verificar si se llama a una función async sin await dentro de una función sync
            parent = self._find_parent_async(node)
            if func_name in self.async_functions and not parent:
                self.errors.append({
                    'file': 'N/A',
                    'line': node.lineno,
                    'func': func_name,
                    'msg': f"Función async '{func_name}' llamada sin await (no está dentro de async)"
                })
        self.generic_visit(node)

    def _find_parent_async(self, node):
        current = node
        while current:
            if isinstance(current, ast.AsyncFunctionDef):
                return True
            current = getattr(current, 'parent', None)
        return False

def audit_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    try:
        tree = ast.parse(content)
        # Añadir parent pointers para poder navegar
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node
        auditor = AsyncAuditor()
        auditor.visit(tree)
        return auditor.errors
    except SyntaxError as e:
        return [{'file': filepath, 'line': e.lineno, 'func': 'N/A', 'msg': f"Error sintáctico: {e}"}]

def main():
    errors = []
    for root, dirs, files in os.walk(SRC_DIR):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                errs = audit_file(path)
                for e in errs:
                    e['file'] = path
                    errors.append(e)

    if errors:
        print("❌ Errores async/await encontrados:")
        for e in errors:
            print(f"  - {e['file']}:{e['line']} - {e['func']}: {e['msg']}")
        sys.exit(1)
    else:
        print("✅ No se encontraron errores async/await.")
        sys.exit(0)

if __name__ == "__main__":
    main()
