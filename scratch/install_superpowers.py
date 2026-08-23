import os
import urllib.request
import json

skills = [
    "brainstorming",
    "dispatching-parallel-agents",
    "executing-plans",
    "finishing-a-development-branch",
    "receiving-code-review",
    "requesting-code-review",
    "subagent-driven-development",
    "systematic-debugging",
    "test-driven-development",
    "using-git-worktrees",
    "using-superpowers",
    "writing-plans",
    "writing-skills"
]

target_base = r"C:\Users\fahmi\.gemini\config\skills"
headers = {"User-Agent": "Mozilla/5.0"}

results = []

for skill in skills:
    url = f"https://raw.githubusercontent.com/obra/superpowers/main/skills/{skill}/SKILL.md"
    skill_dir = os.path.join(target_base, skill)
    os.makedirs(skill_dir, exist_ok=True)
    target_file = os.path.join(skill_dir, "SKILL.md")
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode('utf-8')
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(content)
        results.append((skill, "SUCCESS", len(content)))
        print(f"[OK] {skill} ({len(content)} bytes)")
    except Exception as e:
        results.append((skill, f"FAILED: {e}", 0))
        print(f"[ERR] {skill}: {e}")

print("\n--- Summary ---")
print(f"Total processed: {len(results)}")
