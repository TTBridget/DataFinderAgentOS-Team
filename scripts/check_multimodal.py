#!/usr/bin/env python3
"""多模态补丁静态与路由检查。"""

from pathlib import Path
import compileall
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    os.environ.setdefault("COOKIE_SECRET", "local-check-only-change-me")
    require((ROOT / "app/controllers/multimodal.py").exists(), "缺少控制器")
    require((ROOT / "app/models/face_profile.py").exists(), "缺少人脸仓储")
    require((ROOT / "app/static/js/multimodal.js").exists(), "缺少前端 JS")
    require((ROOT / "app/static/css/multimodal.css").exists(), "缺少前端 CSS")

    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    for route in (
        "/api/face/status",
        "/api/face/enroll",
        "/api/face/login",
        "/api/face/delete",
    ):
        require(route in app_text, f"app.py 缺少路由 {route}")

    base_text = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
    require("css/multimodal.css" in base_text, "base.html 未加载 CSS")
    require("js/multimodal.js" in base_text, "base.html 未加载 JS")

    if not compileall.compile_dir(str(ROOT / "app"), quiet=1):
        raise RuntimeError("Python 编译检查失败")
    if not compileall.compile_file(str(ROOT / "app.py"), quiet=1):
        raise RuntimeError("app.py 编译检查失败")

    try:
        subprocess.run(
            ["node", "--check", str(ROOT / "app/static/js/multimodal.js")],
            check=True,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        print("[通过] JavaScript 语法检查")
    except FileNotFoundError:
        print("[跳过] 未安装 Node.js，未执行 JavaScript 语法检查")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("JavaScript 语法错误：\n" + exc.stderr) from exc

    print("[通过] Python 编译检查")
    print("[通过] 路由和静态资源接入检查")
    print("静态检查完成；请继续按 docs/multimodal_local_test.md 做浏览器端测试。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
