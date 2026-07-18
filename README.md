# VAVE 降本建议生成器 · 手机原生版 (Kivy)

真正的原生安卓 APP（非网页套壳），基于原有 VAVE 知识库引擎 + 方法论 + AI 模型，
用 **Kivy** 重写 UI，通过 **Buildozer** 编译成 APK。安装后完全独立运行，无需 Streamlit / 服务器。

## 功能
- 💡 **建议生成**：输入零件名称 / 类别 / 材料工艺 / 成本 / 年用量 → 基于 85+ 知识库案例 + VAVE 方法论给出降本建议、预期降幅、年度降本金额；可一键调 AI 深化（联网）。
- 📚 **知识库**：搜索 / 按类别筛选 85 个真实 VAVE 案例，查看原方案 / VAVE 方案 / 降本效果 / 风险。
- 🧠 **方法论**：内置 VAVE 方法论体系说明（本地离线）。

## 目录
```
main.py                  Kivy 主程序（3 屏 + 底部导航）
engine/                 复用的纯 Python 引擎
  ├─ vave_engine.py             规则 + 案例匹配（核心）
  ├─ vave_methodology_engine.py VAVE 方法论追踪
  ├─ vave_deepseek.py           AI 深化建议（联网）
  ├─ vave_knowledge_base.json   85 个案例知识库
  ├─ vave_app_defaults.json     内置模型密钥
  └─ msyh.ttc                   中文字体（微软雅黑）
buildozer.spec         APK 打包配置
codemagic.yaml         Codemagic 云端自动构建配置
```

## 本地运行（开发 / 预览，需 Windows/Mac/Linux + Python 3.11）
```bash
pip install kivy requests
python main.py
```

## 打包 APK
APK 必须在 Linux 环境编译（Windows 无法直接编译）。两种办法：

### 办法 A：Codemagic 云端构建（推荐，你已经用过）
1. 把本目录推送到 GitHub 仓库（如 `vave-mobile`）。
2. 在 Codemagic 导入该仓库，选择 `codemagic.yaml` 里的 `android-build` 工作流。
3. push 到 `main` 分支即自动构建，完成后邮箱收到 APK 下载链接。
   实例用 `linux_x2`，与之前 Flutter 构建一致。

### 办法 B：本机 WSL2 + Buildozer
```bash
wsl --install            # 首次需重启
# 进入 WSL 后：
sudo apt update && sudo apt install -y python3-pip build-essential git zip unzip \
  openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev libncurses5-dev libffi-dev libssl-dev
pip3 install buildozer "cython<3.0"
buildozer android debug
# 产物：bin/*.apk
```

## 说明
- 知识库与方法论为**离线本地**运行，无网也能用。
- AI 深化建议需联网，使用内置模型密钥（来自 `vave_app_defaults.json`）。
- 积分 / 裂变 / 云端贡献等强依赖后端的模块，本离线版未纳入；如需手机端使用，可后续接 SCF 后端。
