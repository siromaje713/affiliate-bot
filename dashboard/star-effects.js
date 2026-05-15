/* ============================================================
   star-effects.js — 星結びダッシュボード演出強化パッチ
   ------------------------------------------------------------
   index.html の </body> 直前に <script src="./star-effects.js"></script>
   として読み込む。
   
   機能:
   1. レベルアップ花火 (Lv.が変わったタイミングで降る金粉アニメ)
   2. 手動投稿トリガーボタン (社長室モーダルに workflow_dispatch ボタン)
   3. 図鑑モーダルの過去投稿詳細表示 (post_log連動)
   4. アラート時の社長室パルスアニメ
   ============================================================ */

(function(){
  // STATE.level の永続化 (localStorage で前回 level を保持)
  const LV_KEY = 'hoshi_last_level';
  
  function getLastLevel(){
    try { return parseInt(localStorage.getItem(LV_KEY), 10) || 0; }
    catch(e){ return 0; }
  }
  function setLastLevel(lv){
    try { localStorage.setItem(LV_KEY, String(lv)); } catch(e){}
  }

  // ──────────────────────────────────────────────────────────
  // 1. 花火演出
  // ──────────────────────────────────────────────────────────
  function fireworks(){
    const container = document.createElement('div');
    container.id = 'fireworks-overlay';
    container.style.cssText = `
      position:fixed;inset:0;pointer-events:none;z-index:9999;
      overflow:hidden;
    `;
    document.body.appendChild(container);

    const colors = ['#d4a93a', '#ffd966', '#e89aa3', '#9bb88a', '#8ab9c9'];
    const emojis = ['✨', '🌟', '💫', '⭐', '🎇'];

    for (let i = 0; i < 60; i++){
      setTimeout(() => {
        const p = document.createElement('div');
        const isEmoji = Math.random() > 0.6;
        if (isEmoji) {
          p.textContent = emojis[Math.floor(Math.random() * emojis.length)];
          p.style.fontSize = (16 + Math.random() * 16) + 'px';
        } else {
          p.style.cssText = `
            width:${4 + Math.random()*8}px;height:${4 + Math.random()*8}px;
            background:${colors[Math.floor(Math.random()*colors.length)]};
            border-radius:50%;
            box-shadow:0 0 12px currentColor;
          `;
        }
        p.style.position = 'absolute';
        p.style.left = (10 + Math.random() * 80) + '%';
        p.style.top = '-20px';
        p.style.animation = `fireworkFall ${2 + Math.random()}s ease-in forwards`;
        container.appendChild(p);
      }, i * 30);
    }

    // 中央メッセージ
    const msg = document.createElement('div');
    msg.style.cssText = `
      position:absolute;top:35%;left:50%;transform:translate(-50%,-50%);
      font-family:'Kaisei Decol',serif;font-weight:900;
      font-size:48px;color:#fff;
      text-shadow:0 0 20px #d4a93a, 0 0 40px #ffd966, 4px 4px 0 #3a1a05;
      animation:levelUpPop 2.5s ease-out forwards;
      white-space:nowrap;text-align:center;
    `;
    msg.innerHTML = `🎉 LEVEL UP! 🎉<br/><span style="font-size:24px;">新しい階級に到達ニャ</span>`;
    container.appendChild(msg);

    setTimeout(() => container.remove(), 4000);
  }

  // CSS注入
  const style = document.createElement('style');
  style.textContent = `
    @keyframes fireworkFall {
      0% { transform: translateY(0) rotate(0); opacity: 0; }
      10% { opacity: 1; }
      100% { transform: translateY(110vh) rotate(720deg); opacity: 0; }
    }
    @keyframes levelUpPop {
      0% { transform: translate(-50%,-50%) scale(0.3); opacity: 0; }
      20% { transform: translate(-50%,-50%) scale(1.2); opacity: 1; }
      40% { transform: translate(-50%,-50%) scale(1); }
      80% { opacity: 1; }
      100% { transform: translate(-50%,-50%) scale(1.1); opacity: 0; }
    }
    .alert-pulse {
      animation: alertPulse 1s ease-in-out infinite;
    }
    @keyframes alertPulse {
      0%, 100% { transform: scale(1); }
      50% { transform: scale(1.02); }
    }
    .trigger-btn {
      width: 100%;
      margin-top: 12px;
      padding: 10px 14px;
      background: linear-gradient(180deg, #d4a93a, #ffd966);
      border: 2px solid #3a1a05;
      border-radius: 10px;
      font-family: 'DotGothic16', monospace;
      font-weight: 700;
      cursor: pointer;
      box-shadow: 0 3px 0 #3a1a05;
      transition: transform .1s;
    }
    .trigger-btn:active {
      transform: translateY(2px);
      box-shadow: 0 1px 0 #3a1a05;
    }
    .trigger-btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .post-card {
      background: rgba(255,255,255,.7);
      border: 1.5px solid #c9a878;
      border-radius: 10px;
      padding: 8px 10px;
      margin-bottom: 6px;
      font-size: 11px;
    }
    .post-card .post-meta {
      display: flex;
      gap: 8px;
      font-size: 10px;
      opacity: 0.6;
      margin-bottom: 2px;
    }
    .post-card .post-text {
      line-height: 1.5;
      color: #3a2a1f;
    }
  `;
  document.head.appendChild(style);

  // ──────────────────────────────────────────────────────────
  // 2. レベル変化監視
  // ──────────────────────────────────────────────────────────
  function checkLevelUp(){
    if (!window.STATE || !window.STATE.data || !window.STATE.data.kpi) return;
    const cur = window.STATE.data.kpi.level;
    const prev = getLastLevel();
    if (prev > 0 && cur > prev) {
      fireworks();
    }
    setLastLevel(cur);
  }

  // ──────────────────────────────────────────────────────────
  // 3. 手動投稿トリガー (workflow_dispatch呼び出し)
  // ──────────────────────────────────────────────────────────
  // ※ PATが必要なため、ここではダミーとして "GitHubページを新タブで開く" 動作にする
  // 本格運用したい場合は別途 backend (Render Web Service) 経由が必要
  window.openWorkflowDispatchPage = function(workflowName){
    const url = `https://github.com/siromaje713/hoshi-musubi/actions/workflows/${workflowName}`;
    window.open(url, '_blank');
  };

  // ──────────────────────────────────────────────────────────
  // 4. 社長室モーダルに手動トリガー追加
  // ──────────────────────────────────────────────────────────
  // openModal('ceo') が呼ばれた後のモーダル本体に注入
  const origOpenModal = window.openModal;
  if (typeof origOpenModal === 'function') {
    window.openModal = function(kind){
      origOpenModal(kind);
      if (kind === 'ceo') {
        const body = document.getElementById('modal-body');
        if (body && !body.querySelector('.trigger-section')) {
          const triggerSection = document.createElement('div');
          triggerSection.className = 'trigger-section';
          triggerSection.style.cssText = 'margin-top:16px;padding-top:12px;border-top:1.5px solid rgba(58,42,31,.2);';
          triggerSection.innerHTML = `
            <div class="font-bold mb-2 text-xs">⚡ 手動アクション</div>
            <button class="trigger-btn" onclick="openWorkflowDispatchPage('post.yml')">
              📣 臨時投稿を打つ (post.yml)
            </button>
            <button class="trigger-btn" onclick="openWorkflowDispatchPage('engage.yml')">
              🤝 engage 即実行
            </button>
            <button class="trigger-btn" onclick="openWorkflowDispatchPage('dashboard_aggregate.yml')">
              🔄 ダッシュボード再集計
            </button>
            <div class="text-[10px] opacity-60 mt-2 leading-snug">
              ※ ボタン押下で GitHub Actions ページが開きます。
              そこから「Run workflow」を押してください。
            </div>
          `;
          body.appendChild(triggerSection);
        }
      } else if (kind === 'book') {
        // 図鑑に直近投稿セクション追加
        const body = document.getElementById('modal-body');
        const posts = (window.STATE && window.STATE.data && window.STATE.data.recent_posts) || [];
        if (body && posts.length && !body.querySelector('.recent-posts-section')) {
          const sec = document.createElement('div');
          sec.className = 'recent-posts-section';
          sec.style.cssText = 'margin-top:16px;padding-top:12px;border-top:1.5px solid rgba(58,42,31,.2);';
          sec.innerHTML = `
            <div class="font-bold mb-2 text-xs">📜 直近の投稿</div>
            ${posts.slice(0, 5).map(p => `
              <div class="post-card">
                <div class="post-meta">
                  <span>${p.at || '?'}</span>
                  ${p.type ? `<span>· ${p.type}</span>` : ''}
                </div>
                <div class="post-text">${(p.text || '').slice(0, 120)}${(p.text || '').length > 120 ? '…' : ''}</div>
              </div>
            `).join('')}
          `;
          body.appendChild(sec);
        }
      }
    };
  }

  // ──────────────────────────────────────────────────────────
  // 5. アラート時のCEOパルス
  // ──────────────────────────────────────────────────────────
  function applyAlertPulse(){
    const alerts = (window.STATE && window.STATE.data && window.STATE.data.alerts) || [];
    const ceoRoom = document.querySelector('.ceo-room');
    if (!ceoRoom) return;
    if (alerts.length > 0) {
      ceoRoom.classList.add('alert-pulse');
    } else {
      ceoRoom.classList.remove('alert-pulse');
    }
  }

  // ──────────────────────────────────────────────────────────
  // 6. データ更新時のフック
  // ──────────────────────────────────────────────────────────
  const origRender = window.render;
  if (typeof origRender === 'function') {
    window.render = function(){
      origRender();
      checkLevelUp();
      applyAlertPulse();
    };
  } else {
    // render が定義されてない場合は loadData 後にチェック
    setTimeout(() => {
      checkLevelUp();
      applyAlertPulse();
    }, 2000);
  }

  console.log('[star-effects] loaded ✨');
})();
