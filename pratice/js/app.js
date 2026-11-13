(function () {
  'use strict';

  const D = window.DATA;
  const app = document.getElementById('app');
  const overlayRoot = document.getElementById('overlay-root');
  const phone = document.getElementById('phone');

  const ICONS = {
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    back: '<path d="M15 19l-7-7 7-7"/>',
    right: '<path d="M9 5l7 7-7 7"/>',
    down: '<path d="M6 9l6 6 6-6"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="M20.5 20.5l-4.2-4.2"/>',
    close: '<path d="M6 6l12 12M18 6L6 18"/>',
    check: '<path d="M5 12.5l4.2 4.2L19 7"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M9 21h6"/>',
    send: '<path d="M3.4 20.4L21 12 3.4 3.6l2.9 6.9L15 12 6.3 13.5l-2.9 6.9z"/>',
    clipboard: '<rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 4.5V3h6v1.5M9 9h6M9 13h6M9 17h4"/>',
    filetext: '<path d="M7 3h7l5 5v13H7zM14 3v5h5M10 12h6M10 16h6"/>',
    folder: '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    chat: '<path d="M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v7a2.5 2.5 0 0 1-2.5 2.5H10l-4.5 4v-4A2.5 2.5 0 0 1 4 13.5z"/>',
    trash: '<path d="M4 7h16M9 7V4h6v3M6.5 7l1 13h9l1-13M10 11v6M14 11v6"/>',
    multi: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 12l2.8 2.8L16.5 9"/>',
    copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
    download: '<path d="M12 3v12M7 10l5 5 5-5M4 20h16"/>',
    thumbup: '<path d="M7 10v10H4V10h3zM7 10l4-7c1.5 0 2.5 1 2.5 2.5V9H19a2 2 0 0 1 2 2.4l-1.3 6A2 2 0 0 1 17.7 19H7"/>',
    thumbdown: '<path d="M7 14V4H4v10h3zM7 14l4 7c1.5 0 2.5-1 2.5-2.5V15H19a2 2 0 0 0 2-2.4l-1.3-6A2 2 0 0 0 17.7 5H7"/>',
    camera: '<path d="M4 8h3l1.5-2h7L17 8h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
    image: '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="8.5" cy="10" r="1.5"/><path d="M4 17l5-5 4 4 3-3 4 4"/>',
    doc: '<path d="M7 3h7l5 5v13H7zM14 3v5h5"/>',
    call: '<path d="M5 4h4l2 5-2.5 1.5a12 12 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/>',
    briefcase: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 12h18"/>',
    building: '<path d="M4 21V6l7-3v18M11 21h9V9l-9-3M7 9h1M7 13h1M7 17h1M14 11h3M14 15h3M14 19h3"/>',
    box: '<path d="M12 3l9 5-9 5-9-5 9-5zM3 8v9l9 5 9-5V8M12 13v9"/>',
    dots: '<circle cx="12" cy="5" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="12" cy="19" r="1.4"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    edit: '<path d="M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4"/>'
  };

  function icon(name, cls) {
    return '<svg class="icon ' + (cls || '') + '" viewBox="0 0 24 24" aria-hidden="true">' + ICONS[name] + '</svg>';
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (m) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
    });
  }

  const S = {
    route: '/splash',
    auth: { agreed: false, phone: '', code: '', codeTimer: null, codeLeft: 0 },
    role: { type: 'personal', name: '', company: '', position: '', industry: '', unit: '', legalRole: '' },
    user: Object.assign({}, D.user),
    selectedCaseId: null,
    draft: '',
    caseSearch: '',
    assistantDraft: '',
    detailDraft: '',
    attachOpen: false,
    chat: null,
    chatSeq: 0,
    analysis: { tab: 'facts', chip: 'summary' },
    materialTab: '书面文件',
    materialSearch: '',
    materialExpanded: {},
    infoOpen: true,
    selectedEvidenceId: 'e1',
    docsFilter: '全部',
    historyFilter: '全部',
    historySearch: '',
    historySelectMode: false,
    historySelected: [],
    pendingDeleteIds: [],
    key: '',
    scrollBottom: false,
    scrollToLastUser: false,
    suppressClick: false
  };

  function getCase(id) {
    return D.cases.find(function (c) { return c.id === id; }) || D.cases[0];
  }

  function getEvidence(id) {
    return D.evidenceList.find(function (e) { return e.id === id; }) || D.evidenceList[0];
  }

  function currentPath() {
    return (location.hash || '#/splash').replace(/^#/, '');
  }

  function go(path) {
    if (currentPath() === path) { render(); return; }
    location.hash = path;
  }

  function fallbackBack() {
    if (history.length > 1) history.back();
    else go('/cases');
  }

  var splashTimer = null;

  /* ============ shared components ============ */

  function topbar(active) {
    return '<header class="topbar">' +
      '<button class="menu-btn" data-action="open-drawer" aria-label="菜单">' + icon('menu') + '</button>' +
      '<div class="tabs">' +
      '<button class="tab ' + (active === 'cases' ? 'active' : '') + '" data-nav="/cases">案件</button>' +
      '<button class="tab ' + (active === 'assistant' ? 'active' : '') + '" data-nav="/assistant">助手</button>' +
      '</div>' +
      '<button class="avatar-btn" data-nav="/profile" aria-label="个人中心"><img src="assets/avatar.jpg" alt="用户头像"></button>' +
      '</header>';
  }

  function navBar(title, opts) {
    opts = opts || {};
    var back = opts.back === false ? '' :
      '<button class="nav-back" data-action="back" data-fallback="' + esc(opts.fallback || '/cases') + '" aria-label="返回">' + icon('back') + '</button>';
    var right = opts.menu === false ? '' :
      '<button class="nav-menu" data-action="open-drawer" aria-label="菜单">' + icon('menu') + '</button>';
    return '<header class="nav ' + (opts.gradient ? 'on-gradient' : '') + '">' +
      '<div class="nav-side">' + back + '</div>' +
      '<div class="nav-title">' + esc(title) + '</div>' +
      '<div class="nav-side right">' + right + '</div>' +
      '</header>';
  }

  function donut(c, large) {
    var analyzed = c.status === 'analyzed';
    var p = analyzed ? 0.8 : (c.status === 'unanalyzed' ? 0.56 : 0.72);
    var color = c.status === 'unanalyzed' ? '#B9D7FF' : '#2F6BFF';
    var C = 2 * Math.PI * 32;
    var center;
    if (analyzed) center = '<b>' + c.winRate + '%</b><span>胜诉率</span>';
    else if (c.status === 'unanalyzed') center = '<span class="q">?</span><span>胜诉率</span>';
    else center = '<span class="doing">分析中</span><span>胜诉率</span>';
    return '<div class="donut ' + (large ? 'lg' : '') + '">' +
      '<svg class="arc" viewBox="0 0 70 70"><circle cx="35" cy="35" r="32" fill="none" stroke="#E9F1FF" stroke-width="4"/>' +
      '<circle cx="35" cy="35" r="32" fill="none" stroke="' + color + '" stroke-width="4" stroke-linecap="round" stroke-dasharray="' + (C * p).toFixed(1) + ' ' + C.toFixed(1) + '"/></svg>' +
      '<img class="ticks" src="assets/donut.svg" alt="">' +
      '<div class="donut-center">' + center + '</div>' +
      '<i class="cap"></i></div>';
  }

  function statusPill(c) {
    var cls = c.status === 'analyzed' ? 'green' : (c.status === 'unanalyzed' ? 'pink' : 'lav');
    return '<span class="status-pill ' + cls + '">' + esc(c.statusText) + '</span>';
  }

  function caseCard(c) {
    var selected = S.selectedCaseId === c.id;
    var checkMode = S.selectedCaseId != null;
    return '<article class="case-card ' + (checkMode ? 'has-checks' : '') + '" data-action="case-card" data-id="' + c.id + '" data-title="' + esc(c.title) + '">' +
      (checkMode ? '<span class="check ' + (selected ? 'on' : '') + '">' + icon('check') + '</span>' : '') +
      statusPill(c) +
      '<h3 class="case-title">' + esc(c.title) + '</h3>' +
      '<div class="case-row">证据上传：<span class="val ' + (c.evidenceUploaded ? '' : 'red') + '">' + esc(c.evidenceText) + '</span></div>' +
      '<div class="case-row">案件程序：<span class="val">' + esc(c.procedure) + '</span></div>' +
      donut(c) +
      '</article>';
  }

  function searchBox(opts) {
    opts = opts || {};
    return '<div class="search-box ' + (opts.white ? 'on-white' : '') + '">' +
      icon('search') +
      '<input id="' + opts.id + '" type="text" placeholder="' + esc(opts.placeholder || '请输入搜索内容') + '" value="' + esc(opts.value || '') + '" autocomplete="off">' +
      (opts.button === false ? '' : '<button class="search-btn" data-action="' + opts.action + '">搜索</button>') +
      '</div>';
  }

  function composer(opts) {
    opts = opts || {};
    return '<div class="composer-wrap">' +
      '<div class="composer">' +
      '<button class="plus" data-action="' + (opts.plusAction || 'attach-sheet') + '" aria-label="添加">' + icon('plus') + '</button>' +
      '<div class="composer-box ' + (opts.value ? 'has-text' : '') + '">' +
      '<input id="' + opts.id + '" type="text" placeholder="' + esc(opts.placeholder) + '" value="' + esc(opts.value || '') + '" autocomplete="off">' +
      '<button class="mic" data-action="mic" aria-label="语音">' + icon('mic') + '</button>' +
      '<button class="send" data-action="composer-send" data-source="' + opts.source + '" aria-label="发送">' + icon('send', 'fill') + '</button>' +
      '</div></div>' +
      (opts.after || '') +
      '</div>';
  }

  function contextCard(c) {
    if (!c) return '';
    return '<div class="chat-context" data-action="chat-context" data-id="' + c.id + '">' +
      '<div class="ctitle">' + esc(c.title) + '</div>' +
      '<div class="ctx-grid">' +
      '<div>证据上传：<b>' + esc(c.evidenceText) + '</b></div>' +
      '<div>胜诉率：<b>' + (c.winRate == null ? '—' : c.winRate + '%') + '</b></div>' +
      '<div>案件程序：<b>' + esc(c.procedure) + '</b></div>' +
      '<div>证据分析：<b class="green">' + esc(c.evidenceAnalysis) + '</b></div>' +
      '</div></div>';
  }

  function fileIcon(type) {
    return '<span class="file-icon ' + (type === 'pdf' ? 'pdf' : 'doc') + '"><span>' + (type === 'pdf' ? 'PDF' : 'W') + '</span></span>';
  }

  function docFileRow(name, type, action) {
    return '<button class="file-row" ' + (action ? 'data-action="' + action + '"' : '') + ' style="background:none;padding:0;text-align:left;width:100%">' +
      fileIcon(type) + '<span class="name">' + esc(name) + '</span></button>';
  }

  function returnCase(path) {
    return '<button class="return-case" data-nav="' + path + '">返回<br>案件</button>';
  }

  function emptyState(text) {
    return '<div class="empty">' + icon('folder') + '<div>' + esc(text) + '</div></div>';
  }

  /* ============ overlays ============ */

  function setOverlay(html) {
    overlayRoot.innerHTML = html;
  }

  function closeOverlay() {
    overlayRoot.innerHTML = '';
  }

  function toast(msg) {
    var old = phone.querySelector('.toast');
    if (old) old.remove();
    var el = document.createElement('div');
    el.className = 'toast';
    el.textContent = msg;
    phone.appendChild(el);
    setTimeout(function () { if (el.parentNode) el.remove(); }, 2000);
  }

  function showDrawer() {
    var u = S.user;
    setOverlay(
      '<div class="drawer-mask" data-action="close-overlay"></div>' +
      '<aside class="drawer">' +
      '<div class="drawer-user"><img src="assets/avatar.jpg" alt=""><div><div class="nm">' + esc(u.name) + '</div><div class="rl">' + esc(u.roleLabel || '企业') + ' · ' + esc(u.position || '用户') + '</div></div></div>' +
      '<nav>' +
      '<button data-nav="/cases">' + icon('clipboard') + '案件</button>' +
      '<button data-nav="/assistant">' + icon('chat') + '助手</button>' +
      '<button data-nav="/history">' + icon('filetext') + '历史记录</button>' +
      '<button data-nav="/profile">' + icon('user') + '个人中心</button>' +
      '<button data-nav="/case/' + (S.selectedCaseId || 'c1') + '/legacy-analysis">' + icon('doc') + '旧版案情梳理</button>' +
      '</nav>' +
      '<button class="drawer-logout" data-action="logout">退出登录</button>' +
      '</aside>'
    );
  }

  function showLoginAgreement(next) {
    setOverlay(
      '<div class="modal-mask" data-action="close-overlay">' +
      '<div class="modal" data-stop="1">' +
      '<button class="modal-close" data-action="close-overlay" aria-label="关闭">' + icon('close', 'sm') + '</button>' +
      '<div class="modal-title">请阅读勾选协议</div>' +
      '<div class="modal-sub">已阅读<a data-nav="/agreement">用户服务</a>、<a data-nav="/agreement">隐私政策</a> 和 <a data-nav="/agreement">免费声明</a></div>' +
      '<div class="modal-actions">' +
      '<button class="btn btn-ghost" data-action="close-overlay">不同意</button>' +
      '<button class="btn btn-primary" data-action="login-agree" data-next="' + esc(next || 'role') + '">同意</button>' +
      '</div></div></div>'
    );
  }

  function showCaseAlert() {
    setOverlay(
      '<div class="modal-mask" data-action="close-overlay">' +
      '<div class="modal round small" data-stop="1" style="width:262px">' +
      '<div class="modal-title" style="font-weight:600;margin-bottom:16px">请先选择对应案件<br>进行问答</div>' +
      '<div class="modal-actions" style="margin-top:4px">' +
      '<button class="btn btn-primary" style="flex:none;width:112px" data-action="close-overlay">确定</button>' +
      '</div></div></div>'
    );
  }

  function showLogoutConfirm() {
    setOverlay(
      '<div class="modal-mask" data-action="close-overlay">' +
      '<div class="modal round small" data-stop="1" style="width:270px">' +
      '<div class="modal-title" style="font-weight:600">确定退出当前账号？</div>' +
      '<div class="modal-actions" style="margin-top:18px">' +
      '<button class="btn btn-ghost" data-action="close-overlay">取消</button>' +
      '<button class="btn btn-primary" data-action="confirm-logout">确定</button>' +
      '</div></div></div>'
    );
  }

  function showDeleteConfirm(ids) {
    S.pendingDeleteIds = ids || [];
    var n = S.pendingDeleteIds.length;
    setOverlay(
      '<div class="modal-mask" data-action="close-overlay">' +
      '<div class="modal round small" data-stop="1" style="width:270px">' +
      '<div class="modal-title" style="font-weight:600">删除选中的' + n + '个会话</div>' +
      '<div class="modal-actions" style="margin-top:18px">' +
      '<button class="btn btn-ghost" data-action="close-overlay">取消</button>' +
      '<button class="btn btn-primary" data-action="confirm-delete">确定</button>' +
      '</div></div></div>'
    );
  }

  function showSelectSheet(title, options, field) {
    var html = '<div class="modal-mask" data-action="close-overlay"><div class="select-sheet" data-stop="1">' +
      '<h4>' + esc(title) + '</h4>' +
      options.map(function (o) {
        return '<button data-action="pick-select" data-field="' + field + '" data-value="' + esc(o) + '">' + esc(o) + '</button>';
      }).join('') +
      '</div></div>';
    setOverlay(html);
  }

  function showAttachSheet() {
    setOverlay(
      '<div class="modal-mask" data-action="close-overlay"><div class="select-sheet" data-stop="1">' +
      '<h4>添加材料</h4>' +
      '<button data-action="attach-pick" data-accept="image/*" data-capture="1">拍照</button>' +
      '<button data-action="attach-pick" data-accept="image/*">从相册选择</button>' +
      '<button data-action="attach-pick" data-accept=".doc,.docx,.pdf,.txt,.png,.jpg,.jpeg">上传文档</button>' +
      '<button data-action="attach-call">发起通话</button>' +
      '</div></div>'
    );
  }

  function showFilePreview(doc) {
    var type = doc.type || 'docx';
    var body = '<p style="text-align:center"><b>' + (type === 'pdf' ? '民事答辩状' : '民 事 答 辩 状') + '</b></p>' +
      '<p>答辩人（被告）：李某，男，汉族，住某市某区某路某号。</p>' +
      '<p>因原告张某诉答辩人房屋买卖合同纠纷一案，答辩人现提出答辩如下：</p>' +
      '<p>一、原告所述事实部分不实。答辩人与原告签订的房屋买卖合同系双方真实意思表示，合同合法有效，答辩人从未否认合同效力。</p>' +
      '<p>二、原告主张的经济损失缺乏证据支持。原告未能提供充分证据证明其实际损失金额，其主张不应得到支持。</p>' +
      '<p>三、答辩人进入房屋系为协商合同履行事宜，并非恶意侵占。相关事实有待庭审查明。</p>' +
      '<p>综上，请求法院依法驳回原告不合理的诉讼请求。</p>' +
      '<p style="text-align:right">答辩人：李某<br>2024年10月15日</p>';
    setOverlay(
      '<div class="modal-mask" data-action="close-overlay">' +
      '<div class="modal file-preview" data-stop="1">' +
      '<div class="file-preview-head">' + fileIcon(type) + '<div class="nm">' + esc(doc.name) + '</div>' +
      '<button class="modal-close" data-action="close-overlay" style="position:static;width:26px;height:26px">' + icon('close', 'sm') + '</button></div>' +
      '<div class="file-paper">' + body + '</div>' +
      '</div></div>'
    );
  }

  function openRecordMenu(rowEl, id) {
    closeRecordMenu();
    var menu = document.createElement('div');
    menu.className = 'record-menu';
    menu.innerHTML =
      '<button data-action="record-delete" data-id="' + id + '">' + icon('trash') + '删除会话</button>' +
      '<button data-action="record-multi" data-id="' + id + '">' + icon('multi') + '多选</button>';
    rowEl.appendChild(menu);
    rowEl.classList.add('menu-open');
    S.suppressClick = true;
    setTimeout(function () { S.suppressClick = false; }, 500);
  }

  function closeRecordMenu() {
    document.querySelectorAll('.record-menu').forEach(function (m) { m.remove(); });
    document.querySelectorAll('.record-row.menu-open').forEach(function (r) { r.classList.remove('menu-open'); });
  }

  /* ============ splash / login / role ============ */

  function splashPage() {
    return '<section class="page splash" data-action="splash-continue">' +
      '<img class="robot" src="assets/robot.png" alt="小诺">' +
      '<h1>您最可靠的案件助手!</h1>' +
      '<div class="brand">欢迎来到 AI 英诺律法</div>' +
      '</section>';
  }

  function agreementLinks(extra) {
    return '未注册手机号验证通过后将自动注册，并同意' + (extra ? '《' : '') +
      '<a data-nav="/agreement">用户服务</a>、<a data-nav="/agreement">隐私政策</a> 和 <a data-nav="/agreement">免费声明</a>' + (extra ? '》' : '');
  }

  function loginPage() {
    return '<section class="page login-page login-oneclick">' +
      '<img class="logo" src="assets/logo.png" alt="安徽英诺欣科技">' +
      '<div class="phone-big">' + esc(S.user.phone) + '</div>' +
      '<div class="phone-sub">中国移动提供认证服务</div>' +
      '<div class="actions">' +
      '<button class="btn btn-primary" data-action="login-oneclick">本机号码一键登录</button>' +
      '<button class="alt-link" data-nav="/login-phone">其他手机号/账号登录</button>' +
      '</div>' +
      '<div class="login-agreement">' +
      '<button class="checkbox ' + (S.auth.agreed ? 'on' : '') + '" data-action="toggle-agreement" aria-label="同意协议">' + icon('check') + '</button>' +
      '<div class="txt">' + agreementLinks(false) + '</div>' +
      '</div></section>';
  }

  function phoneLoginPage() {
    var timerText = S.auth.codeLeft > 0 ? (S.auth.codeLeft + 's 后重发') : '发送验证码';
    return '<section class="page phone-login">' +
      navBar('', { back: true, menu: false, fallback: '/login' }) +
      '<div class="page-scroll">' +
      '<div class="login-title">手机号登录</div>' +
      '<div class="fields">' +
      '<div class="field"><span class="prefix">+86</span><span class="sep"></span><input id="login-phone-input" type="tel" maxlength="11" placeholder="请输入手机号码" value="' + esc(S.auth.phone) + '"></div>' +
      '<div class="field"><input id="login-code-input" type="tel" maxlength="6" placeholder="请输入验证码" value="' + esc(S.auth.code) + '"><button class="code-btn" id="code-btn" data-action="send-code">' + timerText + '</button></div>' +
      '</div>' +
      '<button class="btn btn-primary btn-login" data-action="do-phone-login">登录</button>' +
      '<div class="login-agreement">' +
      '<button class="checkbox ' + (S.auth.agreed ? 'on' : '') + '" data-action="toggle-agreement" aria-label="同意协议">' + icon('check') + '</button>' +
      '<div class="txt">' + agreementLinks(true) + '</div>' +
      '</div></div></section>';
  }

  function rolePage() {
    var r = S.role;
    var fields = '<div class="field"><input id="role-name" type="text" placeholder="请输入姓名" value="' + esc(r.name) + '"></div>';
    if (r.type === 'enterprise') {
      fields += '<div class="field"><input id="role-company" type="text" placeholder="请输入企业名称" value="' + esc(r.company) + '"></div>' +
        '<div class="field"><input id="role-position" type="text" placeholder="请输入担任职位" value="' + esc(r.position) + '"></div>' +
        '<div class="field select ' + (r.industry ? 'has' : '') + '" data-action="open-select" data-field="industry"><span>' + esc(r.industry || '请选择所在的行业') + '</span>' + icon('down', 'sm') + '</div>';
    } else if (r.type === 'legal') {
      fields += '<div class="field"><input id="role-unit" type="text" placeholder="请输入单位名称" value="' + esc(r.unit) + '"></div>' +
        '<div class="field select ' + (r.legalRole ? 'has' : '') + '" data-action="open-select" data-field="legalRole"><span>' + esc(r.legalRole || '请选择角色') + '</span>' + icon('down', 'sm') + '</div>';
    }
    return '<section class="page role-page"><div class="page-scroll">' +
      '<h1 class="role-title">请选择您的角色</h1>' +
      '<div class="role-pills">' +
      '<button class="role-pill ' + (r.type === 'personal' ? 'on' : '') + '" data-action="role-select" data-role="personal">个人用户</button>' +
      '<button class="role-pill ' + (r.type === 'enterprise' ? 'on' : '') + '" data-action="role-select" data-role="enterprise">企业用户</button>' +
      '<button class="role-pill ' + (r.type === 'legal' ? 'on' : '') + '" data-action="role-select" data-role="legal">法律专业用户</button>' +
      '</div>' +
      '<div class="role-form-label">基本信息：</div>' +
      '<div class="role-fields">' + fields + '</div>' +
      '<div class="role-submit"><button class="btn btn-primary" data-action="start-use">开始使用</button></div>' +
      '</div></section>';
  }

  /* ============ home / assistant ============ */

  function casesPage() {
    return '<section class="page home-page bg-gradient">' +
      topbar('cases') +
      '<div class="page-scroll home-scroll">' +
      '<div class="hero"><img class="robot" src="assets/robot.png" alt="小诺"><div class="hero-text">' +
      '<h2 class="hero-title">Hi～我是小诺！</h2>' +
      '<div class="hero-sub">下午好！我是您的案件智能小助手，您可以基于案件咨询你要问询的问题</div>' +
      '</div></div>' +
      '<div class="home-search"><div class="search-box on-white">' + icon('search') +
      '<input id="case-search" type="text" placeholder="请输入搜索内容" autocomplete="off">' +
      '<button class="search-btn" data-action="filter-cases">搜索</button></div></div>' +
      '<div class="case-list">' + D.cases.map(caseCard).join('') + '</div>' +
      '<div class="empty hidden" id="case-empty">' + icon('folder') + '<div>没有找到相关案件</div></div>' +
      '</div>' +
      composer({ id: 'home-input', placeholder: '关于案件，有什么想要咨询的？', value: S.draft, source: 'home' }) +
      '</section>';
  }

  function assistantPage() {
    var attach = '<div class="attach-panel">' +
      '<button class="attach-btn" data-action="attach-pick" data-accept="image/*" data-capture="1">' + icon('camera') + '拍照</button>' +
      '<button class="attach-btn" data-action="attach-pick" data-accept="image/*">' + icon('image') + '相册</button>' +
      '<button class="attach-btn" data-action="attach-pick" data-accept=".doc,.docx,.pdf,.txt,.png,.jpg,.jpeg">' + icon('doc') + '文档</button>' +
      '<button class="attach-btn" data-action="attach-call">' + icon('call') + '通话</button>' +
      '</div>';
    return '<section class="page assistant-page bg-gradient-long">' +
      topbar('assistant') +
      '<div class="page-scroll">' +
      '<div class="assistant-hero"><img class="robot" src="assets/robot.png" alt="小诺"><div class="txt">' +
      '<h2>Hi～我是小诺！</h2><p>您可以向我咨询任何法律问题哦，<br>我能提供案件梳理、证据分析、法律文书书写～</p></div></div>' +
      '<div class="rec-card"><h3>推荐问</h3><div class="rec-list">' +
      D.recommendations.map(function (q) {
        return '<button class="rec-item" data-action="rec-question" data-q="' + esc(q) + '"><span class="dot"></span><span>' + esc(q) + '</span></button>';
      }).join('') +
      '</div></div>' +
      '<div class="assistant-hint" data-action="open-history">– 历史对话，下拉回顾 –</div>' +
      '</div>' +
      '<div class="composer-wrap ' + (S.attachOpen ? 'has-attach' : '') + '">' +
      '<div class="composer"><button class="plus" data-action="toggle-attach" aria-label="添加">' + icon('plus') + '</button>' +
      '<div class="composer-box ' + (S.assistantDraft ? 'has-text' : '') + '"><input id="assistant-input" type="text" placeholder="请在此输入您的提问～" value="' + esc(S.assistantDraft) + '" autocomplete="off">' +
      '<button class="mic" data-action="mic">' + icon('mic') + '</button>' +
      '<button class="send" data-action="composer-send" data-source="assistant">' + icon('send') + '</button></div></div>' +
      (S.attachOpen ? attach : '') +
      '</div></section>';
  }

  /* ============ chat ============ */

  function pickAnswer(q) {
    var text = (q || '').toLowerCase();
    if (text.indexOf('答辩') > -1) return D.answers.defense;
    if (text.indexOf('侵权') > -1) return D.answers.tort;
    if (text.indexOf('证据清单') > -1) return D.answers.evidenceSort;
    if (text.indexOf('案情梳理') > -1 || text.indexOf('案件梳理') > -1) return D.answers.caseSort;
    if (text.indexOf('起诉') > -1) return D.answers.lawsuit;
    if (text.indexOf('欠') > -1 || text.indexOf('逾期') > -1) return D.answers.debt;
    if (text.indexOf('收集') > -1 || text.indexOf('证据') > -1) return D.answers.evidenceCollect;
    return D.answers.generic;
  }

  function answerCard(html, index) {
    return '<div class="answer-card" data-answer="' + index + '">' + html +
      '<div class="answer-actions">' +
      '<button data-action="chat-action" data-act="copy" data-index="' + index + '">' + icon('copy', 'sm') + '</button>' +
      '<button data-action="chat-action" data-act="download" data-index="' + index + '">' + icon('download', 'sm') + '</button>' +
      '<span class="grow"></span>' +
      '<button data-action="chat-action" data-act="like" data-index="' + index + '" class="' + (S.chat && S.chat.feedback === 'like' ? 'ok' : '') + '">' + icon('thumbup', 'sm') + '</button>' +
      '<button data-action="chat-action" data-act="dislike" data-index="' + index + '" class="' + (S.chat && S.chat.feedback === 'dislike' ? 'ok' : '') + '">' + icon('thumbdown', 'sm') + '</button>' +
      '</div></div>';
  }

  function chatMessagesHtml(chat) {
    var html = '<div class="chat-time">05:44</div>';
    var answerIndex = 0;
    chat.messages.forEach(function (m) {
      if (m.role === 'user') {
        html += '<div class="msg-user"><div class="bubble">' + esc(m.text) + '</div></div>';
        if (chat.mode === 'case' && chat.contextCaseId) html += contextCard(getCase(chat.contextCaseId));
      } else {
        html += answerCard(m.html, answerIndex++);
      }
    });
    if (chat.typing) html += '<div class="typing"><span></span><span></span><span></span></div>';
    return html;
  }

  function chatPage() {
    var chat = S.chat;
    if (!chat) { chat = S.chat = { id: ++S.chatSeq, mode: 'assistant', messages: [], draft: '', typing: false, contextCaseId: null, feedback: null }; }
    var header, ctxAfter = '', scrollClass = 'chat-scroll';
    if (chat.mode === 'case') {
      header = navBar('AI问答', { back: true, fallback: '/cases' });
    } else {
      header = topbar('assistant');
    }
    var hero = '';
    if (chat.mode === 'case' && chat.messages.length === 0) {
      hero = '<div class="hero" style="padding-top:10px;margin:0 -18px"><img class="robot" src="assets/robot.png" alt="小诺"><div class="hero-text">' +
        '<h2 class="hero-title">Hi～我是小诺！</h2><div class="hero-sub">下午好！我是您的案件智能小助手，您可以基于案件咨询你要问询的问题</div></div></div>';
    }
    if (chat.mode === 'case' && chat.messages.length === 0 && chat.contextCaseId) {
      ctxAfter = contextCard(getCase(chat.contextCaseId));
    }
    var composerHTML = '';
    if (chat.messages.length === 0) {
      var after = '';
      if (ctxAfter) {
        after = '<div class="composer-context"><div class="ctx-head"><div class="ctx-title">' + esc(getCase(chat.contextCaseId).title) + '</div>' +
          '<button class="ctx-close" data-action="clear-chat-context">' + icon('close') + '</button></div>' +
          '<div class="ctx-grid">' + '<div>证据上传：<b>' + esc(getCase(chat.contextCaseId).evidenceText) + '</b></div>' +
          '<div>胜诉率：<b>' + (getCase(chat.contextCaseId).winRate == null ? '—' : getCase(chat.contextCaseId).winRate + '%') + '</b></div>' +
          '<div>案件程序：<b>' + esc(getCase(chat.contextCaseId).procedure) + '</b></div>' +
          '<div>证据分析：<b class="green">' + esc(getCase(chat.contextCaseId).evidenceAnalysis) + '</b></div></div></div>';
      }
      composerHTML = composer({ id: 'chat-input', placeholder: chat.mode === 'case' ? '关于案件，有什么想要咨询的？' : '请在此输入您的提问～', value: chat.draft, source: 'chat', after: after });
    } else {
      composerHTML = composer({ id: 'chat-input', placeholder: '继续提问…', value: chat.draft, source: 'chat' });
    }
    return '<section class="page chat-page">' + header +
      '<div class="' + scrollClass + '">' + hero + (chat.messages.length ? chatMessagesHtml(chat) : '') + '</div>' +
      composerHTML + '</section>';
  }

  function answerOnlyPage(opts) {
    return '<section class="page chat-page">' + navBar(opts.title, { back: true, fallback: opts.fallback }) +
      '<div class="chat-scroll">' +
      '<div class="chat-time">05:44</div>' +
      '<div class="msg-user"><div class="bubble">' + esc(opts.question) + '</div></div>' +
      contextCard(getCase(S.selectedCaseId || 'c1')) +
      answerCard(opts.html, 0) +
      '</div>' +
      returnCase(opts.returnTo) +
      '</section>';
  }

  function askFromComposer(source) {
    if (source === 'home') {
      var q = S.draft.trim();
      if (!q) { toast('请输入咨询内容'); return; }
      if (!S.selectedCaseId) { showCaseAlert(); return; }
      var c = getCase(S.selectedCaseId);
      if (c.status !== 'analyzed') { toast('该案件尚未完成分析，请稍后再试'); return; }
      S.chat = { id: ++S.chatSeq, mode: 'case', messages: [], draft: q, typing: false, contextCaseId: c.id, feedback: null };
      S.scrollBottom = false;
      go('/chat');
      return;
    }
    if (source === 'detail') {
      var dq = S.detailDraft.trim();
      if (!dq) { toast('请输入咨询内容'); return; }
      var parts = location.hash.split('/');
      var did = parts[2] || 'c1';
      S.chat = { id: ++S.chatSeq, mode: 'case', messages: [], draft: dq, typing: false, contextCaseId: did, feedback: null };
      S.scrollToLastUser = false;
      go('/chat');
      return;
    }
    if (source === 'assistant') {
      var aq = S.assistantDraft.trim();
      if (!aq) { toast('请输入您的提问'); return; }
      S.assistantDraft = '';
      startAssistantChat(aq);
      return;
    }
    if (source === 'chat') {
      var cq = (S.chat && S.chat.draft || '').trim();
      if (!cq) { toast('请输入内容'); return; }
      sendChatMessage(cq);
    }
  }

  function sendChatMessage(text) {
    var chat = S.chat;
    if (!chat) return;
    chat.messages.push({ role: 'user', text: text });
    chat.draft = '';
    chat.typing = true;
    S.scrollToLastUser = true;
    render();
    var chatId = chat.id;
    setTimeout(function () {
      if (!S.chat || S.chat.id !== chatId) return;
      S.chat.messages.push({ role: 'assistant', html: pickAnswer(text) });
      S.chat.typing = false;
      S.scrollToLastUser = false;
      render();
    }, 850);
  }

  function startAssistantChat(q) {
    S.chat = { id: ++S.chatSeq, mode: 'assistant', messages: [], draft: '', typing: true, contextCaseId: S.selectedCaseId, feedback: null };
    S.chat.messages.push({ role: 'user', text: q });
    go('/chat');
    var chatId = S.chat.id;
    setTimeout(function () {
      if (!S.chat || S.chat.id !== chatId) return;
      S.chat.messages.push({ role: 'assistant', html: pickAnswer(q) });
      S.chat.typing = false;
      S.scrollToLastUser = false;
      render();
    }, 850);
  }

  /* ============ case detail / evidence / analysis ============ */

  function caseDetailPage(id) {
    var c = getCase(id);
    var float = c.status === 'analyzed' ? '<span class="status-float">已分析</span>' : (c.status === 'analyzing' ? '<span class="status-float" style="background:#8FA8FF">分析中</span>' : '<span class="status-float" style="background:#F6AFAF">未分析</span>');
    var cards = [
      { icon: 'clipboard', title: 'AI证据链分析', sub: '一键查看证据链分析结果', path: '/case/' + c.id + '/evidence-list' },
      { icon: 'filetext', title: 'AI案情梳理', sub: 'AI智能分析梳理案情脉络结果', path: '/case/' + c.id + '/analysis' },
      { icon: 'folder', title: '案件文档归类', sub: 'AI智能分类案件文档管理', path: '/case/' + c.id + '/docs' },
      { icon: 'chart', title: '证据分析', sub: 'AI分析原告与被告争议焦点', path: '/case/' + c.id + '/evidence-analysis' }
    ];
    return '<section class="page detail-page">' + navBar('查看案件') +
      '<div class="page-scroll"><div class="detail-sheet">' +
      '<h3 class="detail-case-title">' + esc(c.title) + '</h3>' +
      '<div class="detail-donut-wrap">' + donut(c, true) + float + '</div>' +
      '<div class="detail-meta"><div>证据上传：<b>' + esc(c.evidenceText) + '</b></div><div>案件程序：<b>' + esc(c.procedure) + '</b></div></div>' +
      '<div class="detail-section-title">查看案件分析结果</div>' +
      '<div class="detail-grid">' + cards.map(function (x) {
        return '<button class="detail-card" data-nav="' + x.path + '">' +
          '<span class="d-icon">' + icon(x.icon) + '</span><span class="chev">' + icon('right') + '</span>' +
          '<h4>' + x.title + '</h4><p>' + x.sub + '</p></button>';
      }).join('') + '</div>' +
      '</div></div>' +
      '<button class="return-case" style="bottom:210px" data-nav="/cases">返回<br>案件</button>' +
      composer({ id: 'detail-input', placeholder: '关于案件，有什么想要咨询的？', value: S.detailDraft, source: 'detail' }) +
      '</section>';
  }

  function evidenceListPage(id) {
    var c = getCase(id);
    return '<section class="page">' + navBar('证据资料清单') +
      '<div class="search-row">' + searchBox({ id: 'evidence-search', placeholder: '请输入搜索内容', action: 'filter-evidence' }) + '</div>' +
      '<div class="page-scroll">' +
      '<div class="evidence-title">' + esc(c.title) + '</div>' +
      D.evidenceList.map(function (e) {
        return '<article class="ev-card" data-action="open-evidence" data-id="' + e.id + '" data-title="' + esc(e.title) + '">' +
          '<div class="ev-head"><div class="left"><span class="dot"></span>' + esc(e.title) + '</div><span class="chev">' + icon('right') + '</span></div>' +
          '<div class="ev-body"><div class="clamp2"><span class="label">证据目的：</span>' + esc(e.purpose) + '</div>' +
          '<div class="clamp2" style="margin-top:2px"><span class="label">收集要求：</span>' + esc(e.collect) + '</div></div>' +
          '</article>';
      }).join('') +
      '</div>' + returnCase('/case/' + id) + '</section>';
  }

  function materialPage(id) {
    var c = getCase(id);
    var e = getEvidence(S.selectedEvidenceId);
    var mats = D.materials.filter(function (m) { return m.kind === S.materialTab; });
    if (!mats.length) mats = D.materials.slice(0, 3);
    var tabs = D.materialTabs.map(function (t) {
      return '<button class="material-tab ' + (t === S.materialTab ? 'on' : '') + '" data-action="material-tab" data-tab="' + t + '">' + t + '</button>';
    }).join('');
    var list = mats.map(function (m) {
      var expanded = !!S.materialExpanded[m.id];
      var files = expanded ? m.files : m.files.slice(0, 1);
      return '<article class="mat-card" data-title="' + esc(m.related + ' ' + m.type) + '">' +
        '<div class="mat-head"><div class="typ"><span class="dot"></span>' + esc(m.type) + '</div><span class="status ' + m.statusClass + '">' + esc(m.status) + '</span></div>' +
        '<div class="mat-title"><b>关联材料：</b>' + esc(m.related) + '</div>' +
        '<div class="mat-meta">' + esc(m.uploader) + '<span class="bar">|</span>' + esc(m.date) + '</div>' +
        '<div class="mat-files">' + files.map(function (f) {
          return '<div class="file-row">' + fileIcon(f.indexOf('.pdf') > -1 ? 'pdf' : 'docx') + '<span class="name">' + esc(f) + '</span>' +
            (m.files.length > 1 ? '<button class="toggle" data-action="material-expand" data-id="' + m.id + '">' + (expanded ? '收起 ⌃' : '展开 ⌄') + '</button>' : '') + '</div>';
        }).join('') + '</div>' +
        '<div class="mat-foot"><button data-action="open-evidence-detail" data-id="' + e.id + '">' + icon('right', 'sm') + '</button></div>' +
        '</article>';
    }).join('');
    return '<section class="page">' + navBar('材料证据') +
      '<div class="search-row">' + searchBox({ id: 'material-search', placeholder: '请输入搜索内容', action: 'filter-material' }) + '</div>' +
      '<div class="page-scroll">' +
      '<div class="case-line">案件名称：' + esc(c.title) + '</div>' +
      '<div class="evidence-name"><span class="dot"></span>证据名称：' + esc(e.title) + '</div>' +
      '<div class="info-panel ' + (S.infoOpen ? '' : 'closed') + '"><div><b>证据目的：</b>' + esc(e.purpose) + '</div>' +
      '<div class="long"><b>收集要求：</b><br>获取途径：从原告张某处获取。<br>收集方法：要求张某提供原件，并进行复印或扫描备份。<br>注意事项：确保合同内容完整，无涂改痕迹，且有双方签字或盖章。</div>' +
      '<button class="collapse-toggle" data-action="toggle-info">' + (S.infoOpen ? '收起 ⌃' : '展开 ⌄') + '</button></div>' +
      '<div class="material-tabs">' + tabs + '</div>' +
      '<div class="material-list">' + list + '</div>' +
      '</div>' + returnCase('/case/' + id) + '</section>';
  }

  function evidenceDetailPage(id) {
    var e = getEvidence(S.selectedEvidenceId);
    return '<section class="page evidence-detail">' + navBar('材料证据') +
      '<div class="page-scroll" style="position:relative">' +
      '<div class="stamp">AI审核失败</div>' +
      '<div class="case-line">案件名称：' + esc(getCase(id).title) + '</div>' +
      '<div class="evidence-name"><span class="dot"></span>证据名称：' + esc(e.title) + '</div>' +
      '<div class="form-rows">' +
      '<div class="form-row"><span class="k">证据类型</span><span class="v blue">照片和视频</span></div>' +
      '<div class="form-row"><span class="k">发生日期</span><span class="v">2024-10-15</span></div>' +
      '<div class="form-block"><div class="k">证据描述：</div><div class="text">证据描述内容证据描述内容证据描述内容证据描述内容证据描述内容证据描述内容证据描述内容证据描述内容证据描述内容证据描述内容证据描述内容证据描述内容证据描述内容证据描述内容</div></div>' +
      '<div class="form-block"><div class="k">证据来源：</div><div class="text">客户收集</div></div>' +
      '<div class="form-block"><div class="k">相关附件：</div><div class="attachments">' +
      '<button class="file-row" data-action="preview-attachment" data-name="民事答辩状.docx" data-type="docx" style="background:none;padding:0;text-align:left">' + fileIcon('docx') + '<span class="name">民事答辩状.docx</span></button>' +
      '<button class="file-row" data-action="preview-attachment" data-name="民事答辩状.docx" data-type="docx" style="background:none;padding:0;text-align:left">' + fileIcon('docx') + '<span class="name">民事答辩状.docx</span></button>' +
      '</div></div>' +
      '<div class="two-col"><div><div class="k">上传人：</div><div class="v">宋芝</div></div><div><div class="k">联系方式：</div><div class="v">15209867877</div></div></div>' +
      '</div>' +
      '<div class="fail-reason"><div class="k">审核失败原因</div><div class="v">证据链不足</div></div>' +
      '</div>' + returnCase('/case/' + id + '/evidence') + '</section>';
  }

  function summaryContent() {
    return '<div class="analysis-section">' +
      '<div class="analysis-section-title">案情摘要</div>' +
      '<div class="sum-card"><div class="sum-pill">当事人</div>' +
      '<div class="sum-row"><b>一审原告：</b>上海某娱乐公司</div>' +
      '<div class="sum-row"><b>一审被告：</b>成都某科技公司</div>' +
      '<div class="sum-row"><b>一审被告：</b>成都某科技公司</div></div>' +
      '<div class="sum-card"><div class="sum-pill">事实详情</div>' +
      '<div class="bullet-line"><span class="dot"></span><span><b>事实一：</b>2008年12月，网络作家大少爷在某中文小说网站首发奇幻小说</span></div>' +
      '<div class="bullet-line"><span class="dot"></span><span><b>事实二：</b>2009年12月，网络作家大少爷在某中文小说网站首发奇幻小说</span></div>' +
      '<div class="bullet-line"><span class="dot"></span><span><b>事实三：</b>2009年12月，网络作家大少爷在某中文小说网站首发奇幻小说</span></div></div>' +
      '<div class="sum-card"><div class="sum-pill">当事人请求</div>' +
      '<div class="bullet-line"><span class="dot"></span><span><b>【上海某娱乐公司】：</b>请求判令被告停止侵权、赔偿经济损失及合理维权费用。</span></div>' +
      '<div class="bullet-line"><span class="dot"></span><span><b>【成都某科技公司】：</b>请求驳回原告全部诉讼请求。</span></div></div>' +
      '</div>';
  }

  function timelineContent() {
    var items = [
      ['01', '2024年1月', ['网络作家大少爷张某在某中文网站首发奇幻《热情的大陆》', '张某与上海某娱乐公司签订游戏改编权转让协议']],
      ['02', '2024年2月', ['网络作家大少爷张某在某中文网站首发奇幻《热情的大陆》']],
      ['03', '2024年3月', ['网络作家大少爷张某在某中文网站首发奇幻《热情的大陆》']],
      ['04', '2024年4月', ['网络作家大少爷张某在某中文网站首发奇幻《热情的大陆》']]
    ];
    return '<div class="analysis-section"><div class="analysis-section-title">案情时间轴</div>' +
      items.map(function (it) {
        return '<div class="timeline-card"><div class="timeline-head"><span class="timeline-num">' + it[0] + '</span><span class="timeline-date">' + it[1] + '</span></div>' +
          '<div class="timeline-body">' + it[2].map(function (t) { return '<div class="bullet-line" style="margin:4px 0"><span class="dot"></span><span>' + t + '</span></div>'; }).join('') + '</div></div>';
      }).join('') + '</div>';
  }

  function reasoningContent() {
    return '<div class="analysis-section"><div class="analysis-section-title">司法推理</div>' +
      '<div class="reason-box"><h5>一、关于合同效力</h5><p>原被告签订的房屋买卖合同系双方真实意思表示，内容不违反法律、行政法规的强制性规定，应认定为合法有效，双方均应依约履行。</p></div>' +
      '<div class="reason-box"><h5>二、关于侵权责任</h5><p>被告在未与原告协商一致的情况下强行进入房屋并更换门锁，妨碍了原告对房屋的正常使用，构成对原告占有、使用权益的侵害，应承担停止侵害、恢复原状及赔偿损失的责任。</p></div>' +
      '<div class="reason-box"><h5>三、关于损失认定</h5><p>原告主张的经济损失应结合其实际支出、房屋使用受影响程度等因素综合认定，建议补充相应证据。</p></div></div>';
  }

  function disputesContent() {
    return '<div class="analysis-section"><div class="analysis-section-title">争议焦点</div>' +
      '<div class="dispute-item"><b>焦点一：</b>案涉房屋买卖合同是否合法有效，双方是否已按约履行完毕。</div>' +
      '<div class="dispute-item"><b>焦点二：</b>被告进入房屋并更换门锁的行为是否构成侵权，应否承担相应责任。</div>' +
      '<div class="dispute-item"><b>焦点三：</b>原告主张的经济损失金额是否有充分证据支持。</div>' +
      '<div class="dispute-item"><b>焦点四：</b>本案诉讼费用及维权合理支出应如何分担。</div></div>';
  }

  function legalContent() {
    return '<div class="analysis-section"><div class="analysis-section-title">法律分析</div>' +
      '<div class="reason-box"><h5>《民法典》第五百零九条</h5><p>当事人应当按照约定全面履行自己的义务。当事人应当遵循诚信原则，根据合同的性质、目的和交易习惯履行通知、协助、保密等义务。</p></div>' +
      '<div class="reason-box"><h5>《民法典》第一千一百六十五条</h5><p>行为人因过错侵害他人民事权益造成损害的，应当承担侵权责任。依照法律规定推定行为人有过错，其不能证明自己没有过错的，应当承担侵权责任。</p></div>' +
      '<div class="reason-box"><h5>《民法典》第二百三十五条</h5><p>无权占有不动产或者动产的，权利人可以请求返还原物。</p></div></div>';
  }

  function analysisPage(id) {
    var tabs = [['facts', '事实分析'], ['law', '法律分析'], ['dispute', '定争分析']];
    var chips = [['summary', '案情摘要'], ['timeline', '案情时间轴'], ['reasoning', '司法推理'], ['disputes', '争议焦点']];
    var content = '';
    if (S.analysis.tab === 'facts') {
      if (S.analysis.chip === 'timeline') content = timelineContent();
      else if (S.analysis.chip === 'reasoning') content = reasoningContent();
      else if (S.analysis.chip === 'disputes') content = disputesContent();
      else content = summaryContent();
    } else if (S.analysis.tab === 'law') content = legalContent();
    else content = disputesContent();
    return '<section class="page">' + navBar('案情梳理') +
      '<div class="search-row">' + searchBox({ id: 'analysis-search', placeholder: '请输入搜索内容', action: 'search-analysis' }) + '</div>' +
      '<div class="analysis-tabs">' + tabs.map(function (t) {
        return '<button class="analysis-tab ' + (S.analysis.tab === t[0] ? 'on' : '') + '" data-action="analysis-tab" data-tab="' + t[0] + '">' + t[1] + '</button>';
      }).join('') + '</div>' +
      '<div class="page-scroll analysis-body">' +
      (S.analysis.tab === 'facts' ? '<div class="chips">' + chips.map(function (c) {
        return '<button class="chip ' + (S.analysis.chip === c[0] ? 'on' : '') + '" data-action="analysis-chip" data-chip="' + c[0] + '">' + c[1] + '</button>';
      }).join('') + '</div>' : '') +
      content +
      '<div style="height:100px"></div>' +
      '</div>' + returnCase('/case/' + id) + '</section>';
  }

  function docsPage(id) {
    var filters = ['全部', '案件程序', '庭审记录', '沟通记录'];
    var docs = D.documents.filter(function (d) {
      return (S.docsFilter === '全部' || d.category === S.docsFilter);
    });
    return '<section class="page docs-page">' + navBar('案件文档') +
      '<div class="docs-search"><div class="search-row" style="padding:0"><div class="search-box"><span>' + icon('search') + '</span>' +
      '<input id="docs-search" type="text" placeholder="搜索内容" autocomplete="off"></div><button class="search-cancel" data-action="doc-cancel">取消</button></div></div>' +
      '<div class="docs-chips">' + filters.map(function (f) {
        return '<button class="chip ' + (S.docsFilter === f ? 'on' : '') + '" data-action="doc-filter" data-filter="' + f + '">' + f + '</button>';
      }).join('') + '</div>' +
      '<div class="page-scroll" id="doc-list">' + docs.map(docRow).join('') + '<div class="doc-empty hidden" id="doc-empty">没有找到相关文档</div></div>' +
      returnCase('/case/' + id) + '</section>';
  }

  function docRow(d) {
    return '<div class="doc-row" data-action="open-doc" data-id="' + d.id + '" data-title="' + esc(d.name) + '" data-cat="' + esc(d.category) + '">' +
      fileIcon(d.type) +
      '<div class="doc-main"><div class="doc-name">' + esc(d.name) + '</div>' +
      '<div class="doc-meta">' + esc(d.uploader) + '<span class="bar">|</span>' + esc(d.date) + '</div></div></div>';
  }

  /* ============ history / profile / agreement ============ */

  function historyGroups() {
    var groups = ['本周', '本月', '半年'];
    var q = S.historySearch.trim();
    var filtered = D.history.filter(function (r) {
      var okGroup = S.historyFilter === '全部' || S.historyFilter === r.group;
      var okQ = !q || r.title.indexOf(q) > -1;
      return okGroup && okQ;
    });
    var html = '';
    var controlsRendered = false;
    groups.forEach(function (g) {
      var items = filtered.filter(function (r) { return r.group === g; });
      if (!items.length) return;
      var controls = '';
      if (S.historySelectMode && !controlsRendered) {
        controlsRendered = true;
        controls = '<span><button class="done" data-action="done-select" style="color:#215CFF;font-size:14px;font-weight:400">完成</button>' +
          (S.historySelected.length ? '<button data-action="delete-selected" style="color:#EF5C5C;font-size:14px;margin-left:12px">删除(' + S.historySelected.length + ')</button>' : '') + '</span>';
      }
      html += '<div class="hgroup"><div class="hgroup-title"><span>' + g + '</span>' + controls + '</div>';
      items.forEach(function (r) {
        html += recordRowHtml(r);
      });
      html += '</div>';
    });
    if (!filtered.length) html = '<div class="history-empty">暂无历史记录</div>';
    return html;
  }

  function recordRowHtml(r) {
    var selected = S.historySelected.indexOf(r.id) > -1;
    return '<div class="record-row" data-action="record-open" data-id="' + r.id + '" data-title="' + esc(r.title) + '">' +
      '<span class="ricon">' + icon('chat') + '</span>' +
      '<span class="rtitle ' + (r.active ? 'blue' : '') + '">' + esc(r.title) + '</span>' +
      (S.historySelectMode ? '<span class="sel ' + (selected ? 'on' : '') + '">' + icon('check') + '</span>' : '<button class="more" data-action="record-more" data-id="' + r.id + '">' + icon('dots', 'sm fill') + '</button>') +
      '</div>';
  }

  function historyPage() {
    var chips = ['全部', '本周', '本月', '半年'];
    return '<section class="page history-page">' +
      '<button class="history-top-close" data-nav="/assistant" aria-label="返回助手">' + icon('right') + '</button>' +
      '<div class="history-scroll">' +
      '<img class="history-robot" src="assets/robot.png" alt="小诺">' +
      '<div class="history-greet">下午好，我是小诺～</div>' +
      '<div class="history-search"><div class="search-box"><span>' + icon('search') + '</span><input id="history-search" type="text" placeholder="搜索内容" value="' + esc(S.historySearch) + '"></div><button class="search-cancel" data-action="history-cancel">取消</button></div>' +
      '<div class="history-h2">历史记录</div>' +
      '<div class="history-chips">' + chips.map(function (c) {
        return '<button class="chip ' + (S.historyFilter === c ? 'on' : '') + '" data-action="history-filter" data-filter="' + c + '">' + c + '</button>';
      }).join('') + '</div>' +
      historyGroups() +
      '</div>' +
      '<button class="new-chat-btn" data-action="new-chat">' + icon('plus') + '新建对话</button>' +
      '</section>';
  }

  function profilePage() {
    var u = S.user;
    var rows = [];
    if (u.role === 'enterprise') {
      rows = [['briefcase', '担任职位：', u.position], ['building', '企业名称：', u.company], ['box', '所在行业：', u.industry]];
    } else if (u.role === 'legal') {
      rows = [['briefcase', '角色：', u.legalRole], ['building', '单位名称：', u.unit]];
    } else {
      rows = [['user', '姓名：', u.name], ['briefcase', '用户类型：', '个人用户']];
    }
    return '<section class="page profile-page">' + navBar('个人中心', { menu: false }) +
      '<div class="profile-scroll">' +
      '<img class="profile-avatar" src="assets/avatar.jpg" alt="">' +
      '<div class="profile-name">' + esc(u.name) + '</div>' +
      '<span class="profile-role">' + esc(u.roleLabel || '个人') + '</span>' +
      '<div class="profile-card">' + rows.map(function (r) {
        return '<div class="profile-row"><span class="pic">' + icon(r[0]) + '</span><span>' + esc(r[1]) + '</span><span class="pv">' + esc(r[2] || '—') + '</span></div>';
      }).join('') + '</div>' +
      '</div>' +
      '<div style="padding:0 18px 14px"><button class="profile-logout" data-action="logout">退出当前账号</button></div>' +
      '</section>';
  }

  function agreementPage() {
    var a = D.agreement;
    return '<section class="page agreement-page">' + navBar(a.title, { menu: false }) +
      '<div class="agreement-scroll"><h1 class="agreement-title">用户服务协议</h1>' +
      '<div class="agreement-date">' + esc(a.updated) + '<br>' + esc(a.effective) + '</div>' +
      a.body.map(function (x) {
        return (x.h ? '<h3>' + esc(x.h) + '</h3>' : '') + '<p>' + esc(x.p) + '</p>';
      }).join('') +
      '<div style="height:30px"></div></div></section>';
  }

  /* ============ routing ============ */

  function render() {
    var path = currentPath();
    S.route = path;
    var prevScroll = document.querySelector('.page-scroll, .chat-scroll');
    var prevTop = prevScroll ? prevScroll.scrollTop : 0;
    var prevKey = S.key;
    var html = '';
    var key = path;
    var parts = path.split('/').filter(Boolean);

    if (path === '/splash' || path === '/') {
      html = splashPage();
    } else if (path === '/login') {
      html = loginPage();
    } else if (path === '/login-phone') {
      html = phoneLoginPage();
    } else if (path === '/role') {
      html = rolePage();
    } else if (path === '/cases') {
      html = casesPage();
    } else if (path === '/assistant') {
      html = assistantPage();
      key = 'assistant';
    } else if (path === '/chat') {
      html = chatPage();
      key = 'chat:' + (S.chat ? S.chat.mode : '');
    } else if (path === '/history') {
      html = historyPage();
    } else if (path === '/profile') {
      html = profilePage();
    } else if (path === '/agreement') {
      html = agreementPage();
    } else if (parts[0] === 'case' && parts[1]) {
      var id = parts[1];
      var sub = parts[2] || '';
      if (sub === 'evidence-list') { html = evidenceListPage(id); key = path; }
      else if (sub === 'evidence') { html = materialPage(id); key = path; }
      else if (sub === 'evidence-detail') { html = evidenceDetailPage(id); key = path; }
      else if (sub === 'analysis') { html = analysisPage(id); key = path + ':' + S.analysis.tab + ':' + S.analysis.chip; }
      else if (sub === 'docs') { html = docsPage(id); key = path + ':' + S.docsFilter; }
      else if (sub === 'evidence-analysis') { html = answerOnlyPage({ title: '证据清单梳理', question: '证据清单梳理', html: D.answers.evidenceSort, fallback: '/case/' + id, returnTo: '/case/' + id }); }
      else if (sub === 'legacy-analysis') { html = answerOnlyPage({ title: '案情梳理', question: '案情梳理', html: D.answers.caseSort, fallback: '/case/' + id, returnTo: '/case/' + id }); }
      else { html = caseDetailPage(id); }
    } else {
      html = casesPage();
    }

    app.innerHTML = html;
    if (path !== '/chat') S.scrollBottom = false;
    S.key = key;

    var scroller = document.querySelector('.page-scroll');
    var chatScroller = document.querySelector('.chat-scroll');
    if (chatScroller) {
      if (S.scrollToLastUser) {
        var users = chatScroller.querySelectorAll('.msg-user');
        if (users.length) {
          var last = users[users.length - 1];
          chatScroller.scrollTop = Math.max(0, last.getBoundingClientRect().top - chatScroller.getBoundingClientRect().top + chatScroller.scrollTop - 12);
        }
        S.scrollToLastUser = false;
      } else if (key === prevKey) chatScroller.scrollTop = prevTop;
    } else if (scroller) {
      if (key === prevKey) scroller.scrollTop = prevTop;
    }

    if (path === '/splash' || path === '/') {
      clearTimeout(splashTimer);
      splashTimer = setTimeout(function () {
        if (currentPath() === '/splash' || currentPath() === '/') location.replace('#/login');
      }, 2000);
    } else {
      clearTimeout(splashTimer);
    }
  }

  /* ============ events ============ */

  document.addEventListener('click', function (e) {
    var navEl = e.target.closest('[data-nav]');
    if (navEl) {
      e.preventDefault();
      closeOverlay();
      closeRecordMenu();
      var navPath = navEl.getAttribute('data-nav');
      if (navPath === '/assistant' && currentPath() === '/chat' && S.chat && S.chat.mode === 'assistant') {
        S.chat = null;
      }
      go(navPath);
      return;
    }

    var el = e.target.closest('[data-action]');
    if (!el) {
      if (!e.target.closest('.record-menu')) closeRecordMenu();
      return;
    }
    var action = el.getAttribute('data-action');

    if (action === 'close-overlay') {
      if (e.target === el && (el.classList.contains('modal-mask') || el.classList.contains('drawer-mask'))) {
        closeOverlay();
      } else if (el.classList.contains('modal-close') || el.classList.contains('btn')) {
        closeOverlay();
      }
      return;
    }

    switch (action) {
      case 'splash-continue':
        location.replace('#/login');
        break;
      case 'back':
        fallbackBack();
        break;
      case 'open-drawer':
        showDrawer();
        break;
      case 'toggle-agreement':
        S.auth.agreed = !S.auth.agreed;
        document.querySelectorAll('.checkbox').forEach(function (x) { x.classList.toggle('on', S.auth.agreed); });
        break;
      case 'login-oneclick':
        if (!S.auth.agreed) showLoginAgreement('role');
        else go('/role');
        break;
      case 'do-phone-login':
        doPhoneLogin();
        break;
      case 'send-code':
        sendCode(el);
        break;
      case 'login-agree':
        S.auth.agreed = true;
        closeOverlay();
        render();
        var next = el.getAttribute('data-next');
        if (next === 'phone-login') doPhoneLogin();
        else go('/role');
        break;
      case 'role-select':
        S.role.type = el.getAttribute('data-role');
        render();
        break;
      case 'open-select':
        var field = el.getAttribute('data-field');
        if (field === 'industry') {
          showSelectSheet('请选择所在的行业', ['租赁和商务服务业', '互联网/信息技术', '金融业', '制造业', '建筑业', '其他'], 'industry');
        } else {
          showSelectSheet('请选择角色', ['律师', '法务', '法官/检察官', '法律教师', '其他法律从业者'], 'legalRole');
        }
        break;
      case 'pick-select':
        var f = el.getAttribute('data-field');
        var v = el.getAttribute('data-value');
        S.role[f] = v;
        closeOverlay();
        render();
        break;
      case 'start-use':
        startUse();
        break;
      case 'case-card':
        var cid = el.getAttribute('data-id');
        if (S.selectedCaseId === cid) {
          go('/case/' + cid);
        } else {
          S.selectedCaseId = cid;
          render();
          toast('已选择案件');
        }
        break;
      case 'filter-cases':
        filterCases(document.getElementById('case-search') ? document.getElementById('case-search').value : '');
        break;
      case 'composer-send':
        askFromComposer(el.getAttribute('data-source'));
        break;
      case 'mic':
        toast('语音输入演示：请使用键盘输入');
        break;
      case 'attach-sheet':
        showAttachSheet();
        break;
      case 'attach-pick':
        pickFile(el.getAttribute('data-accept'), el.hasAttribute('data-capture'));
        closeOverlay();
        break;
      case 'attach-call':
        closeOverlay();
        toast('正在为您转接人工客服（演示）');
        break;
      case 'open-history':
        go('/history');
        break;
      case 'chat-context':
        if (el.getAttribute('data-id')) go('/case/' + el.getAttribute('data-id'));
        break;
      case 'rec-question':
        S.assistantDraft = el.getAttribute('data-q');
        startAssistantChat(S.assistantDraft);
        break;
      case 'toggle-attach':
        S.attachOpen = !S.attachOpen;
        render();
        break;
      case 'open-evidence':
        S.selectedEvidenceId = el.getAttribute('data-id');
        go('/case/' + (location.hash.split('/')[2] || 'c1') + '/evidence');
        break;
      case 'material-tab':
        S.materialTab = el.getAttribute('data-tab');
        render();
        break;
      case 'material-expand':
        var mid = el.getAttribute('data-id');
        S.materialExpanded[mid] = !S.materialExpanded[mid];
        render();
        break;
      case 'toggle-info':
        S.infoOpen = !S.infoOpen;
        render();
        break;
      case 'open-evidence-detail':
        S.selectedEvidenceId = el.getAttribute('data-id');
        go('/case/' + (location.hash.split('/')[2] || 'c1') + '/evidence-detail');
        break;
      case 'preview-attachment':
        showFilePreview({ name: el.getAttribute('data-name'), type: el.getAttribute('data-type') });
        break;
      case 'filter-evidence':
        filterEvidence(document.getElementById('evidence-search') ? document.getElementById('evidence-search').value : '');
        break;
      case 'filter-material':
        filterMaterials(document.getElementById('material-search') ? document.getElementById('material-search').value : '');
        break;
      case 'analysis-tab':
        S.analysis.tab = el.getAttribute('data-tab');
        render();
        break;
      case 'analysis-chip':
        S.analysis.chip = el.getAttribute('data-chip');
        render();
        break;
      case 'search-analysis':
        searchAnalysis();
        break;
      case 'doc-filter':
        S.docsFilter = el.getAttribute('data-filter');
        render();
        break;
      case 'doc-cancel':
        var di = document.getElementById('docs-search');
        if (di) di.value = '';
        filterDocs('');
        break;
      case 'open-doc':
        var doc = D.documents.find(function (d) { return d.id === el.getAttribute('data-id'); });
        if (doc) showFilePreview(doc);
        break;
      case 'history-filter':
        S.historyFilter = el.getAttribute('data-filter');
        render();
        break;
      case 'history-cancel':
        S.historySearch = '';
        var hi = document.getElementById('history-search');
        if (hi) hi.value = '';
        filterHistory('');
        break;
      case 'record-open':
        if (S.suppressClick) return;
        if (S.historySelectMode) {
          toggleHistorySelection(el.getAttribute('data-id'));
        } else {
          openHistoryRecord(el.getAttribute('data-id'));
        }
        break;
      case 'record-more':
        e.stopPropagation();
        openRecordMenu(el.closest('.record-row'), el.getAttribute('data-id'));
        break;
      case 'record-delete':
        closeRecordMenu();
        showDeleteConfirm([el.getAttribute('data-id')]);
        break;
      case 'record-multi':
        closeRecordMenu();
        S.historySelectMode = true;
        S.historySelected = [];
        render();
        break;
      case 'confirm-delete':
        D.history = D.history.filter(function (r) { return S.pendingDeleteIds.indexOf(r.id) === -1; });
        S.pendingDeleteIds = [];
        S.historySelected = [];
        S.historySelectMode = false;
        closeOverlay();
        render();
        toast('已删除');
        break;
      case 'done-select':
        S.historySelectMode = false;
        S.historySelected = [];
        render();
        break;
      case 'delete-selected':
        if (!S.historySelected.length) return;
        showDeleteConfirm(S.historySelected.slice());
        break;
      case 'new-chat':
        S.chat = null;
        S.historySelectMode = false;
        S.historySelected = [];
        go('/assistant');
        break;
      case 'chat-action':
        var act = el.getAttribute('data-act');
        if (act === 'like') { S.chat.feedback = S.chat.feedback === 'like' ? null : 'like'; render(); }
        else if (act === 'dislike') { S.chat.feedback = S.chat.feedback === 'dislike' ? null : 'dislike'; render(); }
        else if (act === 'copy') copyAnswer(el);
        else if (act === 'download') downloadAnswer(el);
        break;
      case 'clear-chat-context':
        if (S.chat) { S.chat.contextCaseId = null; render(); }
        break;
      case 'logout':
        showLogoutConfirm();
        break;
      case 'confirm-logout':
        closeOverlay();
        S.user = Object.assign({}, D.user);
        S.auth.agreed = false;
        S.selectedCaseId = null;
        S.chat = null;
        go('/login');
        break;
      default:
        break;
    }
  });

  document.addEventListener('input', function (e) {
    var t = e.target;
    if (!t || !t.id) return;
    switch (t.id) {
      case 'case-search': S.caseSearch = t.value; filterCases(t.value); break;
      case 'home-input': S.draft = t.value; toggleComposer(t); break;
      case 'assistant-input': S.assistantDraft = t.value; toggleComposer(t); break;
      case 'chat-input': if (S.chat) S.chat.draft = t.value; toggleComposer(t); break;
      case 'login-phone-input': S.auth.phone = t.value; break;
      case 'login-code-input': S.auth.code = t.value; break;
      case 'role-name': S.role.name = t.value; break;
      case 'role-company': S.role.company = t.value; break;
      case 'role-position': S.role.position = t.value; break;
      case 'role-unit': S.role.unit = t.value; break;
      case 'detail-input': S.detailDraft = t.value; toggleComposer(t); break;
      case 'evidence-search': filterEvidence(t.value); break;
      case 'material-search': filterMaterials(t.value); break;
      case 'docs-search': filterDocs(t.value); break;
      case 'history-search': S.historySearch = t.value; filterHistory(t.value); break;
      default: break;
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter') return;
    var t = e.target;
    if (!t || !t.id) return;
    if (t.id === 'home-input') askFromComposer('home');
    else if (t.id === 'assistant-input') askFromComposer('assistant');
    else if (t.id === 'detail-input') askFromComposer('detail');
    else if (t.id === 'chat-input' && S.chat) sendChatMessage(S.chat.draft.trim());
    else if (t.id === 'login-phone-input' || t.id === 'login-code-input') doPhoneLogin();
    else if (t.id === 'case-search') filterCases(t.value);
    else if (t.id === 'analysis-search') searchAnalysis();
  });

  /* record long-press */
  var pressTimer = null;
  document.addEventListener('pointerdown', function (e) {
    var row = e.target.closest('.record-row');
    if (!row || S.historySelectMode) return;
    if (e.target.closest('[data-action="record-more"]')) return;
    var id = row.getAttribute('data-id');
    pressTimer = setTimeout(function () {
      pressTimer = null;
      openRecordMenu(row, id);
    }, 500);
  });
  ['pointerup', 'pointercancel', 'pointerleave'].forEach(function (ev) {
    document.addEventListener(ev, function () { if (pressTimer) { clearTimeout(pressTimer); pressTimer = null; } });
  });
  document.addEventListener('contextmenu', function (e) {
    var row = e.target.closest('.record-row');
    if (!row) return;
    e.preventDefault();
    openRecordMenu(row, row.getAttribute('data-id'));
  });

  /* scroll to close record menu */
  document.addEventListener('scroll', function (e) {
    if (e.target && e.target.classList && e.target.classList.contains('history-scroll')) closeRecordMenu();
  }, true);

  function toggleComposer(input) {
    var box = input.closest('.composer-box');
    if (!box) return;
    box.classList.toggle('has-text', !!input.value.trim());
  }

  function filterCases(q) {
    q = (q || '').trim().toLowerCase();
    var any = false;
    document.querySelectorAll('.case-card').forEach(function (card) {
      var match = !q || (card.getAttribute('data-title') || '').toLowerCase().indexOf(q) > -1;
      card.classList.toggle('hidden', !match);
      if (match) any = true;
    });
    var empty = document.getElementById('case-empty');
    if (empty) empty.classList.toggle('hidden', any);
  }

  function filterEvidence(q) {
    q = (q || '').trim().toLowerCase();
    document.querySelectorAll('.ev-card').forEach(function (card) {
      card.classList.toggle('hidden', !!q && (card.getAttribute('data-title') || '').toLowerCase().indexOf(q) === -1);
    });
  }

  function filterMaterials(q) {
    q = (q || '').trim().toLowerCase();
    document.querySelectorAll('.mat-card').forEach(function (card) {
      card.classList.toggle('hidden', !!q && (card.getAttribute('data-title') || '').toLowerCase().indexOf(q) === -1);
    });
  }

  function filterDocs(q) {
    var text = (q == null ? (document.getElementById('docs-search') || {}).value || '' : q).trim().toLowerCase();
    var any = false;
    document.querySelectorAll('.doc-row').forEach(function (row) {
      var okCat = S.docsFilter === '全部' || row.getAttribute('data-cat') === S.docsFilter;
      var okText = !text || (row.getAttribute('data-title') || '').toLowerCase().indexOf(text) > -1;
      var ok = okCat && okText;
      row.classList.toggle('hidden', !ok);
      if (ok) any = true;
    });
    var empty = document.getElementById('doc-empty');
    if (empty) empty.classList.toggle('hidden', any);
  }

  function filterHistory(q) {
    var text = (q == null ? (document.getElementById('history-search') || {}).value || '' : q).trim().toLowerCase();
    var any = false;
    document.querySelectorAll('.record-row').forEach(function (row) {
      var ok = !text || (row.getAttribute('data-title') || '').toLowerCase().indexOf(text) > -1;
      row.classList.toggle('hidden', !ok);
      if (ok) any = true;
    });
    document.querySelectorAll('.hgroup').forEach(function (g) {
      var has = g.querySelectorAll('.record-row:not(.hidden)').length > 0;
      g.classList.toggle('hidden', !has);
    });
    var existed = document.querySelector('.history-empty');
    if (!any && !existed) {
      var div = document.createElement('div');
      div.className = 'history-empty';
      div.textContent = '暂无历史记录';
      var parent = document.querySelector('.history-scroll');
      if (parent) parent.appendChild(div);
    } else if (any && existed) {
      existed.remove();
    }
  }

  function searchAnalysis() {
    var input = document.getElementById('analysis-search');
    var q = (input ? input.value : '').trim();
    if (!q) return;
    if (q.indexOf('时间') > -1) { S.analysis.chip = 'timeline'; render(); }
    else if (q.indexOf('摘要') > -1 || q.indexOf('事实') > -1) { S.analysis.chip = 'summary'; render(); }
    else if (q.indexOf('推理') > -1) { S.analysis.chip = 'reasoning'; render(); }
    else if (q.indexOf('争议') > -1) { S.analysis.chip = 'disputes'; render(); }
    else toast('未找到相关内容');
  }

  function toggleHistorySelection(id) {
    var i = S.historySelected.indexOf(id);
    if (i > -1) S.historySelected.splice(i, 1);
    else S.historySelected.push(id);
    render();
  }

  function openHistoryRecord(id) {
    var rec = D.history.find(function (r) { return r.id === id; });
    if (!rec) return;
    S.chat = {
      id: ++S.chatSeq,
      mode: 'assistant',
      messages: [
        { role: 'user', text: rec.question },
        { role: 'assistant', html: D.answers[rec.answerKey] || D.answers.generic }
      ],
      draft: '',
      typing: false,
      contextCaseId: S.selectedCaseId,
      feedback: null
    };
    S.scrollToLastUser = true;
    go('/chat');
  }

  function copyAnswer(el) {
    var card = el.closest('.answer-card');
    if (!card) return;
    var text = card.cloneNode(true);
    var actions = text.querySelector('.answer-actions');
    if (actions) actions.remove();
    var content = text.textContent.trim();
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(content).then(function () { toast('已复制'); }).catch(function () { toast('复制失败，请长按选择'); });
    } else {
      toast('已复制');
    }
  }

  function downloadAnswer(el) {
    var card = el.closest('.answer-card');
    if (!card) return;
    var text = card.cloneNode(true);
    var actions = text.querySelector('.answer-actions');
    if (actions) actions.remove();
    var blob = new Blob([text.textContent.trim()], { type: 'text/plain;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = '小诺回答.txt';
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
    toast('已开始下载');
  }

  function sendCode(btn) {
    var phone = (S.auth.phone || '').trim();
    if (!/^1\d{10}$/.test(phone)) { toast('请输入正确的手机号'); return; }
    if (S.auth.codeLeft > 0) return;
    S.auth.codeLeft = 60;
    btn.textContent = '60s 后重发';
    toast('验证码已发送：1234');
    if (S.auth.codeTimer) clearInterval(S.auth.codeTimer);
    S.auth.codeTimer = setInterval(function () {
      S.auth.codeLeft -= 1;
      var b = document.getElementById('code-btn');
      if (b) b.textContent = S.auth.codeLeft > 0 ? (S.auth.codeLeft + 's 后重发') : '发送验证码';
      if (S.auth.codeLeft <= 0) {
        clearInterval(S.auth.codeTimer);
        S.auth.codeTimer = null;
      }
    }, 1000);
  }

  function doPhoneLogin() {
    var phone = (S.auth.phone || '').trim();
    var code = (S.auth.code || '').trim();
    if (!/^1\d{10}$/.test(phone)) { toast('请输入正确的手机号'); return; }
    if (code.length < 4) { toast('请输入验证码'); return; }
    if (!S.auth.agreed) { showLoginAgreement('phone-login'); return; }
    go('/role');
  }

  function startUse() {
    var r = S.role;
    var name = (r.name || '').trim();
    var roleLabel = r.type === 'enterprise' ? '企业' : (r.type === 'legal' ? '法律专业' : '个人');
    S.user.name = name || (r.type === 'enterprise' ? 'cherry芝' : (r.type === 'legal' ? '宋芝' : '小诺用户'));
    S.user.role = r.type;
    S.user.roleLabel = roleLabel;
    if (r.type === 'enterprise') {
      S.user.company = r.company || '安徽鼎安集团有限公司';
      S.user.position = r.position || '律师';
      S.user.industry = r.industry || '租赁和商务服务业';
    } else if (r.type === 'legal') {
      S.user.unit = r.unit || '安徽英诺欣律师事务所';
      S.user.legalRole = r.legalRole || '律师';
    }
    go('/cases');
  }

  function pickFile(accept, capture) {
    var input = document.createElement('input');
    input.type = 'file';
    if (accept) input.accept = accept;
    if (capture) input.setAttribute('capture', 'environment');
    input.style.display = 'none';
    document.body.appendChild(input);
    input.addEventListener('change', function () {
      if (input.files && input.files[0]) toast('已添加：' + input.files[0].name);
      input.remove();
    });
    input.click();
  }

  /* boot */
  window.addEventListener('hashchange', render);
  if (!location.hash) location.replace('#/splash');
  render();
  window.__APP__ = { S: S, render: render, go: go, pickAnswer: pickAnswer };
})();
