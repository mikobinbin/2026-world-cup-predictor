
import re
with open("/root/world-cup-predictor/src/dashboard/mobile_ui.py", "r") as f:
    content = f.read()
with open("/tmp/restore_h2h.html", "r") as f:
    new_html = f.read()
old_start = content.find("<!-- TAB: H2H -->")
old_end = content.find("<!-- TAB: Squad -->")
print("Restore: old_start=", old_start, "old_end=", old_end)
if old_start >= 0 and old_end >= 0:
    content = content[:old_start] + new_html + chr(10)*2 + content[old_end:]
    with open("/root/world-cup-predictor/src/dashboard/mobile_ui.py", "w") as f:
        f.write(content)
    print("Restored!")
else:
    print("Markers not found")
