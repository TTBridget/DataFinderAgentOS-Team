(function () {
  "use strict";

  var FACE_API_URL = "https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/dist/face-api.min.js";
  var FACE_MODEL_URL = "https://cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@0.22.2/weights";
  var HANDS_URL = "https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4.1675469240/hands.js";
  var HANDS_ASSET_URL = "https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4.1675469240/";
  var faceModelsReady = false;
  var activeStream = null;
  var speechEnabled = localStorage.getItem("mm_tts_enabled") !== "0";
  var lastSpokenText = "";
  var pendingMusicAutoplay = false;

  function getCookie(name) {
    var match = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[2]) : "";
  }

  function loadScriptOnce(src, globalName) {
    if (globalName && window[globalName]) return Promise.resolve();
    var existing = document.querySelector('script[data-mm-src="' + src + '"]');
    if (existing) {
      return new Promise(function (resolve, reject) {
        existing.addEventListener("load", resolve, { once: true });
        existing.addEventListener("error", reject, { once: true });
      });
    }
    return new Promise(function (resolve, reject) {
      var script = document.createElement("script");
      script.src = src;
      script.async = true;
      script.dataset.mmSrc = src;
      script.onload = resolve;
      script.onerror = function () { reject(new Error("资源加载失败：" + src)); };
      document.head.appendChild(script);
    });
  }

  function createModal(title, bodyHtml) {
    var backdrop = document.createElement("div");
    backdrop.className = "mm-modal-backdrop";
    backdrop.innerHTML =
      '<div class="mm-modal" role="dialog" aria-modal="true">' +
      '<div class="mm-modal-header"><div class="mm-modal-title"></div>' +
      '<button type="button" class="mm-modal-close" aria-label="关闭">&times;</button></div>' +
      '<div class="mm-modal-body"></div></div>';
    backdrop.querySelector(".mm-modal-title").textContent = title;
    backdrop.querySelector(".mm-modal-body").innerHTML = bodyHtml;
    function close() {
      stopActiveCamera();
      backdrop.remove();
    }
    backdrop.querySelector(".mm-modal-close").onclick = close;
    backdrop.addEventListener("click", function (event) {
      if (event.target === backdrop) close();
    });
    document.body.appendChild(backdrop);
    return { element: backdrop, close: close };
  }

  function stopActiveCamera() {
    if (activeStream) {
      activeStream.getTracks().forEach(function (track) { track.stop(); });
      activeStream = null;
    }
  }

  async function startCamera(video) {
    stopActiveCamera();
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("当前浏览器不支持摄像头访问");
    }
    activeStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false
    });
    video.srcObject = activeStream;
    await video.play();
  }

  async function ensureFaceModels(status) {
    if (faceModelsReady) return;
    if (status) status.textContent = "正在加载人脸识别模型，首次使用需要联网……";
    await loadScriptOnce(FACE_API_URL, "faceapi");
    await Promise.all([
      window.faceapi.nets.tinyFaceDetector.loadFromUri(FACE_MODEL_URL),
      window.faceapi.nets.faceLandmark68Net.loadFromUri(FACE_MODEL_URL),
      window.faceapi.nets.faceRecognitionNet.loadFromUri(FACE_MODEL_URL)
    ]);
    faceModelsReady = true;
  }

  function vectorDistance(left, right) {
    var total = 0;
    for (var i = 0; i < left.length; i += 1) {
      var diff = left[i] - right[i];
      total += diff * diff;
    }
    return Math.sqrt(total);
  }

  async function captureFaceDescriptors(video, status, mode) {
    await ensureFaceModels(status);
    var enrollment = mode === "enroll";
    var prompts = enrollment
      ? ["请正视摄像头", "请保持正脸", "请轻微向左转头", "请轻微向右转头", "请再次正视摄像头"]
      : ["请正视摄像头", "请保持不动", "请再次保持正脸"];
    var samples = [];

    for (var i = 0; i < prompts.length; i += 1) {
      if (status) {
        status.textContent = prompts[i] + "，正在采集第 " + (i + 1) + "/" + prompts.length + " 次……";
      }
      var results = await window.faceapi
        .detectAllFaces(video, new window.faceapi.TinyFaceDetectorOptions({
          inputSize: 320,
          scoreThreshold: 0.65
        }))
        .withFaceLandmarks()
        .withFaceDescriptors();

      if (!results || results.length === 0) {
        throw new Error("未检测到清晰的人脸，请调整光线和位置");
      }
      if (results.length !== 1) {
        throw new Error("画面中必须只有一张人脸");
      }

      var result = results[0];
      var box = result.detection.box;
      if (box.width < video.videoWidth * 0.18 || box.height < video.videoHeight * 0.24) {
        throw new Error("人脸距离摄像头太远，请靠近后重试");
      }

      samples.push(Array.from(result.descriptor));
      await new Promise(function (resolve) { setTimeout(resolve, 650); });
    }

    var consistencyLimit = enrollment ? 0.62 : 0.48;
    for (var left = 0; left < samples.length; left += 1) {
      for (var right = left + 1; right < samples.length; right += 1) {
        if (vectorDistance(samples[left], samples[right]) > consistencyLimit) {
          throw new Error("多次采集差异过大，请确保始终是同一个人并重新尝试");
        }
      }
    }
    return samples;
  }

  async function postJson(url, payload) {
    var response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-XSRFToken": getCookie("_xsrf")
      },
      body: JSON.stringify(payload)
    });
    var data = await response.json().catch(function () { return { code: 1, msg: "服务器响应异常" }; });
    if (!response.ok || data.code !== 0) throw new Error(data.msg || "操作失败");
    return data;
  }

  function openFaceLogin() {
    var usernameInput = document.querySelector('input[name="username"]');
    var modal = createModal("人脸识别登录",
      '<div class="mm-form-row"><label>用户名</label><input id="mmFaceUsername" maxlength="32"></div>' +
      '<div class="mm-video-wrap"><video id="mmFaceVideo" autoplay muted playsinline></video></div>' +
      '<div class="mm-status" id="mmFaceStatus">准备启动摄像头……</div>' +
      '<div class="mm-actions"><button class="mm-btn" id="mmCancelFace">取消</button>' +
      '<button class="mm-btn primary" id="mmRunFaceLogin">开始识别</button></div>' +
      '<div class="mm-privacy">系统会连续采集三次 128 维人脸特征并进行多模板匹配，不上传或保存照片。仍不具备工业级活体检测。</div>'
    );
    var username = modal.element.querySelector("#mmFaceUsername");
    username.value = usernameInput ? usernameInput.value : "";
    var video = modal.element.querySelector("#mmFaceVideo");
    var status = modal.element.querySelector("#mmFaceStatus");
    modal.element.querySelector("#mmCancelFace").onclick = modal.close;
    startCamera(video).then(function () {
      status.textContent = "摄像头已启动，请输入用户名并正视摄像头";
    }).catch(function (error) { status.textContent = error.message; });
    modal.element.querySelector("#mmRunFaceLogin").onclick = async function () {
      var button = this;
      if (!username.value.trim()) {
        status.textContent = "请先输入用户名";
        return;
      }
      button.disabled = true;
      try {
        var descriptors = await captureFaceDescriptors(video, status, "login");
        status.textContent = "正在验证……";
        var result = await postJson("/api/face/login", {
          username: username.value.trim(),
          descriptors: descriptors
        });
        status.textContent = "验证成功，正在进入系统……";
        window.location.href = result.data.redirect || "/index";
      } catch (error) {
        status.textContent = error.message;
        button.disabled = false;
      }
    };
  }

  function injectLoginButton() {
    var form = document.querySelector('form.auth-form[action="/login"]');
    if (!form || document.getElementById("mmFaceLoginButton")) return;
    var wrapper = document.createElement("div");
    wrapper.innerHTML =
      '<div class="mm-login-divider"><span>或</span></div>' +
      '<button type="button" id="mmFaceLoginButton" class="mm-face-login-btn">' +
      '<i class="layui-icon layui-icon-camera"></i> 人脸识别登录</button>';
    form.appendChild(wrapper);
    wrapper.querySelector("#mmFaceLoginButton").onclick = openFaceLogin;
  }

  async function openFaceSettings() {
    var modal = createModal("人脸登录设置",
      '<div class="mm-status" id="mmProfileStatus">正在查询录入状态……</div>' +
      '<div class="mm-form-row"><label>当前登录密码（录入或删除时必填）</label>' +
      '<input id="mmFacePassword" type="password" autocomplete="current-password"></div>' +
      '<div class="mm-video-wrap"><video id="mmEnrollVideo" autoplay muted playsinline></video></div>' +
      '<div class="mm-actions"><button class="mm-btn danger" id="mmDeleteFace">删除模板</button>' +
      '<button class="mm-btn primary" id="mmEnrollFace">录入/更新人脸</button></div>' +
      '<div class="mm-privacy">系统会录入五组原始特征模板，不保存照片；请按提示保持正脸并轻微转头。正式环境仍需增加活体检测与数据库加密。</div>'
    );
    var status = modal.element.querySelector("#mmProfileStatus");
    var password = modal.element.querySelector("#mmFacePassword");
    var video = modal.element.querySelector("#mmEnrollVideo");
    try {
      var response = await fetch("/api/face/status", { credentials: "same-origin" });
      var data = await response.json();
      status.textContent = data.code === 0 && data.data.enrolled
        ? "已录入人脸，最近更新时间：" + (data.data.updated_at || "未知")
        : "尚未录入人脸";
    } catch (error) {
      status.textContent = "无法读取录入状态";
    }
    startCamera(video).catch(function (error) { status.textContent = error.message; });
    modal.element.querySelector("#mmEnrollFace").onclick = async function () {
      var button = this;
      if (!password.value) {
        status.textContent = "请输入当前登录密码";
        return;
      }
      button.disabled = true;
      try {
        var descriptors = await captureFaceDescriptors(video, status, "enroll");
        await postJson("/api/face/enroll", { descriptors: descriptors, password: password.value });
        status.textContent = "人脸录入成功，下次可在登录页使用";
        password.value = "";
      } catch (error) {
        status.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    };
    modal.element.querySelector("#mmDeleteFace").onclick = async function () {
      if (!password.value) {
        status.textContent = "请输入当前登录密码";
        return;
      }
      if (!window.confirm("确定删除当前人脸登录模板吗？")) return;
      try {
        await postJson("/api/face/delete", { password: password.value });
        status.textContent = "人脸模板已删除";
        password.value = "";
      } catch (error) {
        status.textContent = error.message;
      }
    };
  }

  function chooseChineseVoice() {
    var voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
    return voices.find(function (voice) { return /^zh/i.test(voice.lang); }) || voices[0] || null;
  }

  function speakText(text) {
    if (!speechEnabled || !window.speechSynthesis) return;
    var cleaned = String(text || "")
      .replace(/https?:\/\/\S+/g, "")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 600);
    if (!cleaned || cleaned === lastSpokenText || /请求出现错误|加载中/.test(cleaned)) return;
    lastSpokenText = cleaned;
    window.speechSynthesis.cancel();
    var utterance = new SpeechSynthesisUtterance(cleaned);
    utterance.lang = "zh-CN";
    utterance.rate = 1;
    var voice = chooseChineseVoice();
    if (voice) utterance.voice = voice;
    window.speechSynthesis.speak(utterance);
  }

  function latestAssistantText() {
    var messages = document.querySelectorAll(".message.assistant");
    if (!messages.length) return "";
    var latest = messages[messages.length - 1].cloneNode(true);
    latest.querySelectorAll("button,audio,.message-meta-info").forEach(function (node) { node.remove(); });
    return latest.textContent || "";
  }

  function installSpeechHook() {
    if (typeof window.finishGenerating !== "function" || window.finishGenerating.__mmWrapped) return;
    var original = window.finishGenerating;
    var wrapped = function () {
      var result = original.apply(this, arguments);
      window.setTimeout(function () { speakText(latestAssistantText()); }, 80);
      return result;
    };
    wrapped.__mmWrapped = true;
    window.finishGenerating = wrapped;
  }

  function toggleSpeech(button) {
    speechEnabled = !speechEnabled;
    localStorage.setItem("mm_tts_enabled", speechEnabled ? "1" : "0");
    button.classList.toggle("active", speechEnabled);
    button.title = speechEnabled ? "关闭回答语音播报" : "开启回答语音播报";
    var label = button.querySelector("span");
    if (label) label.textContent = speechEnabled ? "语音开" : "语音关";
    if (!speechEnabled && window.speechSynthesis) window.speechSynthesis.cancel();
  }

  function classifyGesture(landmarks) {
    if (!landmarks || landmarks.length < 21) return null;
    function extended(tip, pip) { return landmarks[tip].y < landmarks[pip].y - 0.025; }
    var index = extended(8, 6);
    var middle = extended(12, 10);
    var ring = extended(16, 14);
    var pinky = extended(20, 18);
    if (index && middle && !ring && !pinky) return "scissors";
    if (!index && !middle && !ring && !pinky) return "fist";
    if (index && middle && ring && pinky) return "palm";
    return null;
  }

  function executeGesture(gesture, status, city) {
    if (typeof window.setInput !== "function" || typeof window.sendMessage !== "function") {
      status.textContent = "当前页面无法调用对话功能";
      return;
    }
    var command = "";
    if (gesture === "scissors") command = "@天气 " + (city || "北京");
    if (gesture === "fist") {
      command = "@随机音乐";
      pendingMusicAutoplay = true;
    }
    if (gesture === "palm") command = "@新闻";
    if (!command) return;
    status.textContent = "识别成功：" + command;
    window.setInput(command);
    window.sendMessage();
  }

  async function openGesturePanel() {
    var modal = createModal("手势与数字员工交互",
      '<div class="mm-form-row"><label>剪刀手查询天气的城市</label><input id="mmGestureCity" value="' +
      (localStorage.getItem("mm_weather_city") || "北京") + '"></div>' +
      '<div class="mm-video-wrap"><video id="mmGestureVideo" autoplay muted playsinline></video></div>' +
      '<div class="mm-status" id="mmGestureStatus">正在启动手势识别……</div>' +
      '<div class="mm-gesture-hint"><div>✌️ 剪刀手<br>查天气</div><div>✊ 握拳<br>随机音乐</div><div>🖐️ 手掌<br>热点新闻</div></div>' +
      '<div class="mm-privacy">同一手势需稳定保持约 1 秒；两次触发间隔 5 秒。</div>'
    );
    var video = modal.element.querySelector("#mmGestureVideo");
    var status = modal.element.querySelector("#mmGestureStatus");
    var cityInput = modal.element.querySelector("#mmGestureCity");
    cityInput.addEventListener("change", function () {
      localStorage.setItem("mm_weather_city", cityInput.value.trim() || "北京");
    });
    try {
      await startCamera(video);
      status.textContent = "正在加载手势模型，首次使用需要联网……";
      await loadScriptOnce(HANDS_URL, "Hands");
      var hands = new window.Hands({
        locateFile: function (file) { return HANDS_ASSET_URL + file; }
      });
      hands.setOptions({
        maxNumHands: 1,
        modelComplexity: 1,
        minDetectionConfidence: 0.65,
        minTrackingConfidence: 0.65
      });
      var lastGesture = null;
      var stableFrames = 0;
      var lastTriggerAt = 0;
      var running = true;
      var processing = false;
      var originalClose = modal.close;
      modal.close = function () { running = false; hands.close(); originalClose(); };
      modal.element.querySelector(".mm-modal-close").onclick = modal.close;

      hands.onResults(function (results) {
        var gesture = results.multiHandLandmarks && results.multiHandLandmarks.length
          ? classifyGesture(results.multiHandLandmarks[0])
          : null;
        if (gesture && gesture === lastGesture) stableFrames += 1;
        else { lastGesture = gesture; stableFrames = gesture ? 1 : 0; }
        var names = { scissors: "剪刀手", fist: "握拳", palm: "手掌" };
        status.textContent = gesture ? "检测到：" + names[gesture] + "，请保持……" : "请展示剪刀手、握拳或手掌";
        var now = Date.now();
        if (gesture && stableFrames >= 7 && now - lastTriggerAt > 5000) {
          lastTriggerAt = now;
          stableFrames = 0;
          executeGesture(gesture, status, cityInput.value.trim());
        }
      });

      async function loop() {
        if (!running) return;
        if (!processing && video.readyState >= 2) {
          processing = true;
          try { await hands.send({ image: video }); } catch (error) { status.textContent = error.message; }
          processing = false;
        }
        window.setTimeout(loop, 110);
      }
      loop();
    } catch (error) {
      status.textContent = error.message;
    }
  }

  function installMusicAutoplayObserver() {
    var observer = new MutationObserver(function () {
      if (!pendingMusicAutoplay) return;
      var audios = document.querySelectorAll(".music-card audio");
      if (!audios.length) return;
      var audio = audios[audios.length - 1];
      pendingMusicAutoplay = false;
      audio.play().catch(function () {
        var hint = document.querySelector("#mmGestureStatus");
        if (hint) hint.textContent = "音乐已生成；浏览器阻止自动播放，请点击卡片中的播放按钮";
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function injectChatControls() {
    var header = document.querySelector(".chat-header");
    if (!header || document.getElementById("mmChatControls")) return;
    var group = document.createElement("div");
    group.id = "mmChatControls";
    group.className = "mm-control-group";
    group.innerHTML =
      '<button class="mm-control-btn ' + (speechEnabled ? "active" : "") + '" id="mmSpeechToggle" title="回答语音播报">' +
      '<i class="layui-icon layui-icon-speaker"></i><span>' + (speechEnabled ? "语音开" : "语音关") + '</span></button>' +
      '<button class="mm-control-btn" id="mmGestureButton" title="手势交互"><i class="layui-icon layui-icon-camera"></i><span>手势</span></button>' +
      '<button class="mm-control-btn" id="mmFaceSettingsButton" title="人脸登录设置"><i class="layui-icon layui-icon-user"></i><span>人脸</span></button>';
    header.insertBefore(group, header.firstChild);
    group.querySelector("#mmSpeechToggle").onclick = function () { toggleSpeech(this); };
    group.querySelector("#mmGestureButton").onclick = openGesturePanel;
    group.querySelector("#mmFaceSettingsButton").onclick = openFaceSettings;
    installSpeechHook();
    installMusicAutoplayObserver();
  }

  function init() {
    injectLoginButton();
    injectChatControls();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
}());
