"""Generate Python protobuf/gRPC code from shared proto definitions."""
import os
import sys
from pathlib import Path

PROTO_DIR = Path(__file__).resolve().parent.parent / "proto"
OUT_DIR = Path(__file__).resolve().parent / "src" / "gen"

# Ensure output directory exists
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Generate message classes
for proto_file in PROTO_DIR.glob("*.proto"):
    print(f"Generating Python proto for {proto_file.name}...")
    ret = os.system(
        f'python -m grpc_tools.protoc '
        f'-I{PROTO_DIR} '
        f'--python_out={OUT_DIR} '
        f'{proto_file}'
    )
    if ret != 0:
        print(f"ERROR generating {proto_file.name}", file=sys.stderr)
        sys.exit(1)

# Generate gRPC service stubs
for proto_file in PROTO_DIR.glob("*.proto"):
    print(f"Generating Python gRPC stub for {proto_file.name}...")
    ret = os.system(
        f'python -m grpc_tools.protoc '
        f'-I{PROTO_DIR} '
        f'--grpc_python_out={OUT_DIR} '
        f'{proto_file}'
    )
    if ret != 0:
        print(f"ERROR generating gRPC stub for {proto_file.name}", file=sys.stderr)
        sys.exit(1)

# Create __init__.py
init_py = OUT_DIR / "__init__.py"
if not init_py.exists():
    init_py.write_text("# Generated protobuf/gRPC code\n")

# Fix imports: convert bare imports to relative imports within the gen package
print("Fixing imports to relative...")
for py_file in OUT_DIR.glob("*.py"):
    content = py_file.read_text()
    for other in OUT_DIR.glob("*_pb2.py"):
        mod = other.stem
        content = content.replace(f"import {mod} as ", f"from . import {mod} as ")
        content = content.replace(f"import {mod}\n", f"from . import {mod}\n")
    if content != py_file.read_text():
        py_file.write_text(content)
        print(f"  Fixed imports in {py_file.name}")

print("Done! Generated Python protobuf/gRPC code.")
