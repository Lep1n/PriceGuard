import os
import json
import sys

def bump_version(new_version):
    config_path = "config/config.json"
    if not os.path.exists(config_path):
        print("[ERROR] config/config.json not found.")
        return

    # Read current version from config
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    old_version = data.get("app_version", "v0.1.0")
    print(f"🚀 Bumping version across project: '{old_version}' -> '{new_version}'...")

    files_to_update = [
        "config/config.json",
        "src/gui.py",
        "src/scraper.py",
        "README.md",
        "START.bat"
    ]

    updated_count = 0
    for filepath in files_to_update:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            if old_version in content:
                updated_content = content.replace(old_version, new_version)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(updated_content)
                print(f"  ✅ Updated version in: {filepath}")
                updated_count += 1
            else:
                print(f"  ℹ️ Version string '{old_version}' not found in {filepath} (skipped)")

    print(f"\n🎉 Success! Updated version to '{new_version}' in {updated_count} files.")

if __name__ == "__main__":
    new_ver = sys.argv[1] if len(sys.argv) > 1 else "v0.2.0"
    bump_version(new_ver)