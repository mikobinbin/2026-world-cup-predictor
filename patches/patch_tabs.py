
import re

with open('/root/world-cup-predictor/src/dashboard/mobile_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the tabbar section
old_tabbar = '''<div class="tabbar">
  <button class="tab on" id="tb-home" onclick="showTab('home')"><span class="ico">🏆</span><span>冠军</span></button>
  <button class="tab" id="tb-factor" onclick="showTab('factor')"><span class="ico">📊</span><span>因子</span></button>
  <button class="tab" id="tb-mystic" onclick="showTab('mystic')"><span class="ico">🔮</span><span>玄学</span></button>
  <button class="tab" id="tb-h2h" onclick="showTab('h2h')"><span class="ico">⚔️</span><span>对战</span></button>
  <button class="tab" id="tb-squad" onclick="showTab('squad')"><span class="ico">👥</span><span>球队</span></button>
  <button class="tab" id="tb-info" onclick="showTab('info')"><span class="ico">i</span><span>说明</span></button>
</div>'''

new_tabbar = """<div class="tabbar">
  <button class="tab on" id="tb-home" onclick="showTab('home')"><span class="ico"><svg width="22" height="22" viewBox="0 0 22 22" fill="none"><path d="M11 2L13.5 7.5L19.5 8.5L15 13L16 19L11 16L6 19L7 13L2.5 8.5L8.5 7.5L11 2Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M8 19H14V21H8V19Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg></span><span>冠军</span></button>
  <button class="tab" id="tb-factor" onclick="showTab('factor')"><span class="ico"><svg width="22" height="22" viewBox="0 0 22 22" fill="none"><rect x="3" y="10" width="3.5" height="9" rx="1" stroke="currentColor" stroke-width="1.6"/><rect x="9.25" y="6" width="3.5" height="13" rx="1" stroke="currentColor" stroke-width="1.6"/><rect x="15.5" y="2" width="3.5" height="17" rx="1" stroke="currentColor" stroke-width="1.6"/></svg></span><span>因子</span></button>
  <button class="tab" id="tb-mystic" onclick="showTab('mystic')"><span class="ico"><svg width="22" height="22" viewBox="0 0 22 22" fill="none"><circle cx="11" cy="11" r="8.5" stroke="currentColor" stroke-width="1.6"/><circle cx="11" cy="11" r="3.5" fill="currentColor" opacity="0.4"/><path d="M11 2.5V5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M11 17V19.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M2.5 11H5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M17 11H19.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></span><span>玄学</span></button>
  <button class="tab" id="tb-h2h" onclick="showTab('h2h')"><span class="ico"><svg width="22" height="22" viewBox="0 0 22 22" fill="none"><path d="M4 11H10M10 11L7 8M10 11L7 14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M18 11H12M12 11L15 8M12 11L15 14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></span><span>对战</span></button>
  <button class="tab" id="tb-squad" onclick="showTab('squad')"><span class="ico"><svg width="22" height="22" viewBox="0 0 22 22" fill="none"><circle cx="7" cy="5.5" r="2.5" stroke="currentColor" stroke-width="1.6"/><path d="M2 17.5C2 14.4624 4.23858 12 7 12H7C9.76142 12 12 14.4624 12 17.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><circle cx="15" cy="5.5" r="2.5" stroke="currentColor" stroke-width="1.6"/><path d="M10 17.5C10 14.4624 12.2386 12 15 12H15C17.7614 12 20 14.4624 20 17.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></span><span>球队</span></button>
  <button class="tab" id="tb-info" onclick="showTab('info')"><span class="ico"><svg width="22" height="22" viewBox="0 0 22 22" fill="none"><circle cx="11" cy="11" r="8.5" stroke="currentColor" stroke-width="1.6"/><path d="M11 10V16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="11" cy="6.5" r="0.9" fill="currentColor"/></svg></span><span>说明</span></button>
</div>"""

content = content.replace(old_tabbar, new_tabbar)

with open('/root/world-cup-predictor/src/dashboard/mobile_ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched successfully")
