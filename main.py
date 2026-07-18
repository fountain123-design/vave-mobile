# -*- coding: utf-8 -*-
"""
汽车VAVE降本建议生成器 - 手机原生版 (Kivy)
真正打包成 APK，不依赖网页/服务器。
核心引擎复用 vave_engine / vave_methodology_engine / vave_deepseek。
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.popup import Popup
from kivy.uix.modalview import ModalView
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.metrics import dp, sp
from kivy.clock import Clock

# ============ 路径与字体 ============
BASE = Path(__file__).parent
ENGINE = BASE / "engine"
FONT_PATH = str(ENGINE / "msyh.ttc")

# 注册中文字体（微软雅黑），否则 Android 上中文显示方块
try:
    LabelBase.register(name="CJK", fn_regular=FONT_PATH)
except Exception:
    pass
FONT = "CJK"

# 把 engine 加入导入路径
sys.path.insert(0, str(ENGINE))

from vave_engine import (
    generate_suggestions, get_top_cases, load_knowledge_base, format_output,
)
from vave_methodology_engine import run_methodology_trace, get_kb_stats, get_methodology_methods
from vave_deepseek import generate_ai_suggestions, check_api_key, set_api_key

# 加载默认密钥
_DEFAULT_KEYS = {}
_cfg = ENGINE / "vave_app_defaults.json"
if _cfg.exists():
    try:
        _DEFAULT_KEYS = json.loads(_cfg.read_text(encoding="utf-8"))
    except Exception:
        pass

CATEGORIES = ["通用", "冲压件", "机加件", "压铸件", "塑料件", "电子件",
              "管路件", "钣金件", "橡胶件", "标准件", "传动件", "底盘件",
              "车身件", "密封件"]

# 快捷示例
EXAMPLES = [
    ("仪表台本体", "塑料件", "PP注塑", 91, 300000),
    ("车门防撞梁", "冲压件", "DP600双相钢冲压", 37, 500000),
    ("悬置支架", "压铸件", "A380铝合金压铸", 58, 200000),
    ("BCM控制模块", "电子件", "PCB贴片", 320, 150000),
]

# ============ 颜色 ============
C_PRIMARY = (0.13, 0.55, 0.95, 1)
C_BG = (0.96, 0.97, 0.99, 1)
C_CARD = (1, 1, 1, 1)
C_TEXT = (0.15, 0.17, 0.2, 1)
C_SUB = (0.45, 0.48, 0.52, 1)
C_ACCENT = (0.98, 0.65, 0.12, 1)
C_GREEN = (0.2, 0.7, 0.4, 1)


# ============ 通用控件 ============
def L(text, **kw):
    """带中文字体的 Label"""
    kw.setdefault("font_name", FONT)
    kw.setdefault("color", C_TEXT)
    kw.setdefault("size_hint_y", None)
    # 给定 text_size 且未指定高度时，按文字内容自动撑高（用于多行正文）
    if kw.get("text_size") is not None and "height" not in kw:
        lbl = Label(text=text, **kw)
        lbl.bind(texture_size=lambda inst, val: setattr(inst, "height", val[1]))
        lbl.height = max(lbl.texture_size[1], dp(18))
        return lbl
    lbl = Label(text=text, **kw)
    return lbl


def B(text, on_press=None, **kw):
    """带中文字体的 Button"""
    kw.setdefault("font_name", FONT)
    kw.setdefault("background_color", C_PRIMARY)
    kw.setdefault("color", (1, 1, 1, 1))
    kw.setdefault("size_hint_y", None)
    btn = Button(text=text, **kw)
    if on_press:
        btn.bind(on_press=on_press)
    return btn


class Card(BoxLayout):
    """圆角卡片容器"""
    def __init__(self, **kw):
        super().__init__(**kw)
        self.orientation = "vertical"
        self.size_hint_y = None
        self.padding = [dp(12), dp(10), dp(12), dp(10)]
        self.spacing = dp(6)
        self.bind(minimum_height=self.setter("height"))


def make_scroll(content):
    sv = ScrollView(size_hint=(1, 1), do_scroll_x=False)
    sv.add_widget(content)
    return sv


# ============ 屏幕1：建议生成 ============
class SuggestScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.name = "suggest"
        root = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        self.add_widget(root)

        title = L("💡 VAVE 降本建议生成", font_size=sp(20), bold=True,
                  size_hint_y=None, height=dp(34))
        root.add_widget(title)

        # 快捷示例
        ex_label = L("快捷示例", font_size=sp(13), color=C_SUB, size_hint_y=None, height=dp(20))
        root.add_widget(ex_label)
        ex_grid = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(6))
        for (name, cat, mat, cost, vol) in EXAMPLES:
            b = B(name, on_press=lambda inst, n=name, c=cat, m=mat, co=cost, v=vol:
                  self.fill_example(n, c, m, co, v),
                  background_color=(0.9, 0.94, 1, 1), color=C_PRIMARY, font_size=sp(13))
            ex_grid.add_widget(b)
        root.add_widget(ex_grid)

        # 输入区
        form = Card()
        self.part_name = TextInput(hint_text="零件名称，如：仪表台骨架", font_name=FONT,
                                   size_hint_y=None, height=dp(44), multiline=False)
        self.category = Spinner(text="通用", values=CATEGORIES, font_name=FONT,
                                size_hint_y=None, height=dp(44))
        self.material = TextInput(hint_text="材料/工艺，如：PP注塑件", font_name=FONT,
                                  size_hint_y=None, height=dp(44), multiline=False)
        self.cost = TextInput(hint_text="当前成本(元/件)", font_name=FONT, input_filter="float",
                              size_hint_y=None, height=dp(44), multiline=False)
        self.volume = TextInput(hint_text="年用量(件/年)", font_name=FONT, input_filter="int",
                                size_hint_y=None, height=dp(44), multiline=False)
        self.addinfo = TextInput(hint_text="补充信息(选填)，如：耐高温要求", font_name=FONT,
                                 size_hint_y=None, height=dp(44), multiline=False)

        form.add_widget(self._field("零件名称 *", self.part_name))
        form.add_widget(self._field("零件类别", self.category))
        form.add_widget(self._field("材料/工艺", self.material))
        form.add_widget(self._field("当前单件成本", self.cost))
        form.add_widget(self._field("年用量", self.volume))
        form.add_widget(self._field("补充信息", self.addinfo))
        root.add_widget(form)

        # 生成按钮
        gen = B("🔍 生成 VAVE 建议", on_press=self.on_generate,
                size_hint_y=None, height=dp(50), font_size=sp(16), bold=True)
        root.add_widget(gen)

        # 结果区
        self.result_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        self.result_box.bind(minimum_height=self.result_box.setter("height"))
        self.sv = make_scroll(self.result_box)
        root.add_widget(self.sv)

        # 初始提示
        self.result_box.add_widget(L("输入零件信息后点击生成，将基于知识库案例 + 方法论给出降本建议。",
                                     color=C_SUB, font_size=sp(13), size_hint_y=None, height=dp(40)))

    def _field(self, label, widget):
        box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(64), spacing=dp(2))
        box.add_widget(L(label, font_size=sp(12), color=C_SUB, size_hint_y=None, height=dp(18)))
        box.add_widget(widget)
        return box

    def fill_example(self, name, cat, mat, cost, vol):
        self.part_name.text = name
        self.category.text = cat
        self.material.text = mat
        self.cost.text = str(cost)
        self.volume.text = str(vol)

    def on_generate(self, inst):
        pn = self.part_name.text.strip()
        if not pn:
            self._toast("请填写零件名称")
            return
        self.result_box.clear_widgets()
        self.result_box.add_widget(L("⏳ 匹配知识库案例...", color=C_SUB, font_size=sp(14),
                                     size_hint_y=None, height=dp(36)))
        # 延迟执行以让 UI 刷新
        Clock.schedule_once(lambda dt: self._do_generate(pn), 0.1)

    def _do_generate(self, pn):
        try:
            cat = self.category.text
            mat = self.material.text.strip() or "未知"
            cost = float(self.cost.text) if self.cost.text.strip() else None
            vol = int(self.volume.text) if self.volume.text.strip() else 0
            add = self.addinfo.text.strip()

            result = generate_suggestions(pn, mat, cat, cost_per_unit=cost, additional_info=add)
            self.result_box.clear_widgets()
            self._render_result(result, cost, vol)
        except Exception as e:
            self.result_box.clear_widgets()
            self.result_box.add_widget(L(f"生成失败：{e}", color=(0.8, 0.2, 0.2, 1),
                                         font_size=sp(13), size_hint_y=None, height=dp(40)))

    def _render_result(self, result, cost, vol):
        inp = result["input"]
        sugs = result["suggestions"]

        # 零件信息卡
        info = Card()
        info.add_widget(L(f"📋 {inp['part_name']}", bold=True, font_size=sp(16), size_hint_y=None, height=dp(26)))
        info.add_widget(L(f"类别：{inp['category']}  |  材料/工艺：{inp['material']}",
                          color=C_SUB, font_size=sp(13), size_hint_y=None, height=dp(22)))
        if cost:
            info.add_widget(L(f"当前成本：{cost} 元/件  |  年用量：{vol:,} 件",
                              color=C_SUB, font_size=sp(13), size_hint_y=None, height=dp(22)))
        info.add_widget(L(f"匹配到 {result['matched_cases_count']} 个相关历史案例",
                          color=C_GREEN, font_size=sp(13), size_hint_y=None, height=dp(22)))
        self.result_box.add_widget(info)

        if not sugs:
            self.result_box.add_widget(L("⚠️ 未找到匹配的VAVE建议，请尝试调整关键词或扩大描述范围。",
                                         color=(0.8, 0.5, 0.1, 1), font_size=sp(13),
                                         size_hint_y=None, height=dp(60), text_size=(Window.width-dp(40), None)))
            return

        self.result_box.add_widget(L(f"💡 生成 {len(sugs)} 条建议（按降本潜力排序）",
                                     bold=True, font_size=sp(15), size_hint_y=None, height=dp(30)))

        for s in sugs:
            card = Card()
            pct = s.get("expected_savings_pct", "—")
            amt = s.get("estimated_savings_amount", "")
            card.add_widget(L(f"{s['id']}  {s['priority']}", bold=True, font_size=sp(15),
                              color=C_PRIMARY, size_hint_y=None, height=dp(26)))
            card.add_widget(L(f"策略：{s['strategy_type']}", font_size=sp(14), size_hint_y=None, height=dp(24)))
            card.add_widget(L(f"方向：{s['direction']}", font_size=sp(13), color=C_TEXT,
                              size_hint_y=None, height=dp(44), text_size=(Window.width-dp(60), None)))
            card.add_widget(L(f"预期降幅：{pct}%  ({amt})", font_size=sp(13), color=C_GREEN,
                              size_hint_y=None, height=dp(24)))
            card.add_widget(L(f"逻辑：{s['mechanism']}", font_size=sp(12), color=C_SUB,
                              size_hint_y=None, height=dp(60), text_size=(Window.width-dp(60), None)))
            if s.get("case_name"):
                card.add_widget(L(f"📌 参考案例：{s['case_name']}（ID: {s['case_id']}）",
                                  font_size=sp(12), color=C_SUB, size_hint_y=None, height=dp(22)))
            card.add_widget(L(f"风险：{s['quality_risk']}", font_size=sp(12), color=(0.8, 0.4, 0.1, 1),
                              size_hint_y=None, height=dp(44), text_size=(Window.width-dp(60), None)))
            card.add_widget(L(f"可行性：{s['feasibility']}", font_size=sp(12), color=C_SUB,
                              size_hint_y=None, height=dp(22)))
            self.result_box.add_widget(card)

        # AI 深化按钮
        ai_btn = B("🤖 AI 深化建议（联网）", on_press=lambda inst: self.on_ai(result),
                   background_color=C_ACCENT, size_hint_y=None, height=dp(46), font_size=sp(15))
        self.result_box.add_widget(ai_btn)

    def on_ai(self, result):
        self._toast("正在调用 AI（需联网）...")
        Clock.schedule_once(lambda dt: self._do_ai(result), 0.1)

    def _do_ai(self, result):
        try:
            key = _DEFAULT_KEYS.get("text_model", {}).get("api_key", "")
            if key:
                set_api_key(key)
            resp = generate_ai_suggestions(result["input"], result["suggestions"])
            ai_text = resp.get("suggestions", "") if isinstance(resp, dict) else str(resp)
            mv = ModalView(size_hint=(0.92, 0.85))
            box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
            box.add_widget(L("🤖 AI 深化建议", bold=True, font_size=sp(18), size_hint_y=None, height=dp(32)))
            content = L(ai_text, font_size=sp(13), text_size=(Window.width*0.85, None))
            sv = make_scroll(content)
            box.add_widget(sv)
            box.add_widget(B("关闭", on_press=mv.dismiss, size_hint_y=None, height=dp(44)))
            mv.add_widget(box)
            mv.open()
        except Exception as e:
            self._toast(f"AI 调用失败：{e}")

    def _toast(self, msg):
        mv = ModalView(size_hint=(0.7, 0.18), auto_dismiss=True)
        box = BoxLayout(padding=dp(10))
        box.add_widget(L(msg, font_size=sp(15), color=(1, 1, 1, 1),
                         size_hint=(1, 1), halign="center"))
        mv.add_widget(box)
        mv.background_color = (0.2, 0.22, 0.25, 0.92)
        mv.open()
        Clock.schedule_once(lambda dt: mv.dismiss(), 1.8)


# ============ 屏幕2：知识库 ============
class KBScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.name = "kb"
        root = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        self.add_widget(root)
        root.add_widget(L("📚 VAVE 知识库", bold=True, font_size=sp(20), size_hint_y=None, height=dp(34)))

        search_box = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(6))
        self.search = TextInput(hint_text="搜索零件/策略/关键词", font_name=FONT, multiline=False,
                                size_hint_y=None, height=dp(44))
        self.search.bind(on_text_validate=self.do_search)
        go = B("搜", on_press=self.do_search, size_hint=(0.22, None), height=dp(44))
        search_box.add_widget(self.search)
        search_box.add_widget(go)
        root.add_widget(search_box)

        self.cat_filter = Spinner(text="全部类别", values=["全部类别"] + CATEGORIES,
                                  font_name=FONT, size_hint_y=None, height=dp(40))
        self.cat_filter.bind(text=self.on_filter)
        root.add_widget(self.cat_filter)

        self.list_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        self.sv = make_scroll(self.list_box)
        root.add_widget(self.sv)

        self.kb = load_knowledge_base()
        self.render_list(self.kb["cases"])

    def do_search(self, inst):
        self.on_filter(None, self.cat_filter.text)

    def on_filter(self, inst, cat_text):
        q = self.search.text.strip().lower()
        cases = self.kb["cases"]
        if cat_text != "全部类别":
            cases = [c for c in cases if c.get("category") == cat_text]
        if q:
            cases = [c for c in cases if q in json.dumps(c, ensure_ascii=False).lower()]
        self.render_list(cases)

    def render_list(self, cases):
        self.list_box.clear_widgets()
        if not cases:
            self.list_box.add_widget(L("无匹配案例", color=C_SUB, font_size=sp(14),
                                       size_hint_y=None, height=dp(40)))
            return
        for c in cases:
            card = Card()
            card.add_widget(L(f"{c.get('id','')}  {c.get('part_name','')}",
                              bold=True, font_size=sp(15), size_hint_y=None, height=dp(26)))
            card.add_widget(L(f"类别：{c.get('category','')}  |  材料：{c.get('material','')}",
                              color=C_SUB, font_size=sp(12), size_hint_y=None, height=dp(20)))
            strat = c.get("vave_strategies", [])
            if strat:
                card.add_widget(L(f"策略：{strat[0].get('strategy','')}", font_size=sp(12),
                                  color=C_TEXT, size_hint_y=None, height=dp(20)))
            tap = B("查看详情", on_press=lambda inst, cc=c: self.show_detail(cc),
                    size_hint_y=None, height=dp(38), font_size=sp(13),
                    background_color=(0.9, 0.94, 1, 1), color=C_PRIMARY)
            card.add_widget(tap)
            self.list_box.add_widget(card)

    def show_detail(self, case):
        mv = ModalView(size_hint=(0.94, 0.88))
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        box.add_widget(L(f"{case.get('id','')} {case.get('part_name','')}", bold=True,
                         font_size=sp(17), size_hint_y=None, height=dp(30)))
        lines = []
        lines.append(f"类别：{case.get('category','')}")
        lines.append(f"材料：{case.get('material','')}")
        lines.append(f"原方案：{case.get('original_design','')}")
        lines.append(f"VAVE方案：{case.get('vave_solution','')}")
        lines.append(f"降本效果：{case.get('savings','')}")
        for v in case.get("vave_strategies", []):
            lines.append(f"\n▶ {v.get('strategy','')}")
            lines.append(f"  方向：{v.get('direction','')}")
            lines.append(f"  降幅：{v.get('expected_savings_pct','')}")
            lines.append(f"  逻辑：{v.get('mechanism','')}")
            lines.append(f"  风险：{v.get('quality_risk','')}")
        content = L("\n".join(lines), font_size=sp(13), text_size=(Window.width*0.88, None))
        box.add_widget(make_scroll(content))
        box.add_widget(B("关闭", on_press=mv.dismiss, size_hint_y=None, height=dp(44)))
        mv.add_widget(box)
        mv.open()


# ============ 屏幕3：我的 ============
class MineScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.name = "mine"
        root = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))
        self.add_widget(root)
        root.add_widget(L("👤 我的", bold=True, font_size=sp(20), size_hint_y=None, height=dp(34)))

        # 统计卡
        stat = Card()
        stats = get_kb_stats()
        stat.add_widget(L(f"知识库案例：{stats.get('total_cases', '—')} 个", font_size=sp(14),
                          size_hint_y=None, height=dp(26)))
        stat.add_widget(L(f"策略方法：{stats.get('methods', '—')} 种", font_size=sp(14),
                          size_hint_y=None, height=dp(26)))
        stat.add_widget(L(f"覆盖类别：{stats.get('categories', '—')} 类", font_size=sp(14),
                          size_hint_y=None, height=dp(26)))
        root.add_widget(stat)

        # 方法论
        root.add_widget(L("🧠 VAVE 方法论体系", bold=True, font_size=sp(15), size_hint_y=None, height=dp(28)))
        methods_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        methods_box.bind(minimum_height=methods_box.setter("height"))
        for m in get_methodology_methods():
            card = Card()
            card.add_widget(L(m.get("name", ""), bold=True, font_size=sp(14), size_hint_y=None, height=dp(24)))
            card.add_widget(L(m.get("description", ""), font_size=sp(12), color=C_SUB,
                              size_hint_y=None, height=dp(40), text_size=(Window.width-dp(60), None)))
            methods_box.add_widget(card)
        root.add_widget(make_scroll(methods_box))

        # 说明
        note = L("本APP为离线版：知识库与方法论本地运行，无需联网。\n"
                 "AI深化建议需联网并使用内置模型密钥。",
                 color=C_SUB, font_size=sp(12), size_hint_y=None, height=dp(60),
                 text_size=(Window.width-dp(40), None))
        root.add_widget(note)


# ============ 底部导航 ============
class BottomNav(BoxLayout):
    def __init__(self, sm, **kw):
        super().__init__(**kw)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(58)
        self.spacing = 0
        self.sm = sm
        self.buttons = []
        items = [("💡\n建议", "suggest"), ("📚\n知识库", "kb"), ("👤\n我的", "mine")]
        for text, name in items:
            b = Button(text=text, font_name=FONT, background_color=(0.95, 0.96, 0.98, 1),
                       color=C_SUB, size_hint_y=None, height=dp(58))
            b.bind(on_press=lambda inst, n=name: self.switch(n))
            self.buttons.append((b, name))
            self.add_widget(b)
        self.switch("suggest")

    def switch(self, name):
        self.sm.current = name
        for b, n in self.buttons:
            if n == name:
                b.background_color = C_PRIMARY
                b.color = (1, 1, 1, 1)
            else:
                b.background_color = (0.95, 0.96, 0.98, 1)
                b.color = C_SUB


# ============ 主 App ============
class VaveApp(App):
    def build(self):
        self.title = "VAVE 降本建议"
        Window.clearcolor = C_BG
        sm = ScreenManager()
        sm.add_widget(SuggestScreen())
        sm.add_widget(KBScreen())
        sm.add_widget(MineScreen())

        root = BoxLayout(orientation="vertical")
        root.add_widget(sm)
        nav = BottomNav(sm)
        root.add_widget(nav)
        return root


if __name__ == "__main__":
    VaveApp().run()
