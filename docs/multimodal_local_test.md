# 多模态功能本地验证说明

本补丁新增三项用户侧能力，并保持原密码登录、SSE 对话和数字员工后端不变：

1. 登录页人脸识别登录；
2. 模型回答的浏览器语音合成播报；
3. 手势调用现有数字员工：
   - 剪刀手：`@天气 城市`
   - 握拳：`@随机音乐`
   - 手掌：`@新闻`

## 一、必须先建立本地分支

在项目根目录执行：

```bash
git status
git pull --ff-only origin main
git switch -c feature/multimodal-interaction
```

确认终端显示的分支不是 `main`：

```bash
git branch --show-current
```

## 二、复制并安装补丁

把压缩包中的目录覆盖到项目根目录。压缩包只新增文件，不会自动覆盖现有业务文件。

执行安全安装脚本：

```bash
python scripts/install_multimodal_patch.py
```

脚本只修改：

- `app.py`：增加 4 条人脸 API 路由；
- `app/templates/base.html`：加载独立 CSS/JS；
- `requirements.txt`：补充现有 PDF 导出所需的 `fpdf2`。

修改前会建立：

- `app.py.before_multimodal`
- `app/templates/base.html.before_multimodal`
- `requirements.txt.before_multimodal`

若插入点与当前仓库结构不一致，脚本会停止，不会猜测修改。

## 三、安装项目环境

Windows PowerShell：

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
crawl4ai-setup
```

Windows CMD：

```bat
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
crawl4ai-setup
```

如 `crawl4ai-setup` 不存在，可执行：

```bash
python -m playwright install chromium
```

## 四、静态检查

```bash
python scripts/check_multimodal.py
python -m unittest discover -s test -p "test_face_profile.py" -v
```

Node.js 已安装时，检查脚本还会执行 `node --check`。

## 五、启动系统

PowerShell：

```powershell
$env:COOKIE_SECRET="请替换为至少32位随机字符串"
$env:DEBUG="True"
python app.py
```

CMD：

```bat
set COOKIE_SECRET=请替换为至少32位随机字符串
set DEBUG=True
python app.py
```

访问：

- 用户侧：`http://localhost:10010/`
- 管理侧：`http://localhost:10010/admin/`

摄像头在 `localhost` 或 HTTPS 环境才能正常授权。

## 六、浏览器测试顺序

### 1. 回归测试原功能

先确认：

- 用户名密码仍能登录；
- 新建对话、模型切换、SSE 流式回答正常；
- `@天气 北京`、`@随机音乐`、`@新闻` 可正常执行；
- 后台管理页面能够打开。

### 2. 录入人脸

密码登录后，在对话页右上角点击“人脸”：

- 输入当前密码；
- 允许摄像头；
- 正视摄像头完成三次采集；
- 页面提示“人脸录入成功”。

系统只保存 128 维特征，不保存照片。

### 3. 人脸登录

退出系统，在登录页点击“人脸识别登录”：

- 输入录入时使用的用户名；
- 允许摄像头；
- 正视摄像头；
- 验证成功后进入 `/index`。

可通过环境变量调整阈值：

```bash
FACE_LOGIN_THRESHOLD=0.50
```

允许范围为 0.35–0.65。数值越小越严格。

### 4. 语音播报

点击右上角“语音开/语音关”。开启后发送普通模型问题，流式回答结束后浏览器朗读最终内容。

该功能使用浏览器原生 Web Speech API，不增加后端依赖。

### 5. 手势交互

点击右上角“手势”，保持约一秒：

- 剪刀手：查询输入框中城市的天气；
- 握拳：调用随机音乐；
- 手掌：调用热点新闻。

浏览器可能因自动播放策略阻止音乐自动播放，此时音乐卡片仍会生成，点击卡片播放按钮即可。

## 七、确认差异，不要立即合并

```bash
git status
git diff -- app.py app/templates/base.html requirements.txt
git diff --stat
```

本补丁预期新增：

- `app/controllers/multimodal.py`
- `app/models/face_profile.py`
- `app/static/js/multimodal.js`
- `app/static/css/multimodal.css`
- `scripts/install_multimodal_patch.py`
- `scripts/check_multimodal.py`
- `test/test_face_profile.py`
- `docs/multimodal_local_test.md`

本地测试通过后再提交到功能分支：

```bash
git add app.py requirements.txt app/templates/base.html \
  app/controllers/multimodal.py app/models/face_profile.py \
  app/static/js/multimodal.js app/static/css/multimodal.css \
  scripts/install_multimodal_patch.py scripts/check_multimodal.py \
  test/test_face_profile.py docs/multimodal_local_test.md

git commit -m "feat: add face login speech and gesture interaction"
git push -u origin feature/multimodal-interaction
```

先创建 Pull Request，不要直接合并。待人工验证通过后，再由有主分支合并权限的人合并。

## 安全边界

当前人脸登录适合课程展示或内部原型，不应直接作为高安全生产认证：

- 没有专用活体检测；
- 特征模板暂存 SQLite；
- 前端模型通过 CDN 加载。

正式部署应自托管模型文件、启用 HTTPS、增加活体检测、加密数据库并记录审计日志。
