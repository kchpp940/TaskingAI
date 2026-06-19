#!/usr/bin/env python3
"""
Pre-startup contract validation for plugin service.
See backend/app/check_contracts.py for details.
"""
import sys
import os


def main() -> int:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    generator_script = os.path.join(project_root, "contracts", "artifact", "generate_artifact_types.py")

    if not os.path.exists(generator_script):
        print(f"⚠ Cannot find contract generator at {generator_script}, skipping check")
        return 0

    sys.path.insert(0, os.path.dirname(generator_script))
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("generator", generator_script)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        success = mod.check_consistency()
    except Exception as e:
        print(f"⚠ Contract validation failed with error: {e}")
        print("  Continuing startup (non-fatal in dev)")
        return 0

    if not success:
        print()
        print("❌ ARTIFACT CONTRACT INCONSISTENT!")
        print("   Run the following command before deploying:")
        print("   python contracts/artifact/generate_artifact_types.py")
        print()
        if os.environ.get("STRICT_CONTRACT_CHECK") == "1":
            return 1
        print("   (Set STRICT_CONTRACT_CHECK=1 to make this fatal)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
