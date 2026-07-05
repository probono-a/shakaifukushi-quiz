/* 効果音モジュール — OtoLogic MP3 を AudioBuffer で再生 */
const SoundManager = (() => {
  const MUTE_KEY = 'quiz_muted';
  let _ctx = null;
  let _muted = localStorage.getItem(MUTE_KEY) === '1';
  const _buffers = {};

  const FILES = {
    correct : '/sounds/Quiz-Ding_Dong03-1(Short).mp3',
    wrong   : '/sounds/Quiz-Buzzer04-1(Mid).mp3',
    start   : '/sounds/Quiz-Question02-1(Low).mp3',
    results : '/sounds/Quiz-Results01-1.mp3',
  };

  function getCtx() {
    if (!_ctx) _ctx = new (window.AudioContext || window.webkitAudioContext)();
    return _ctx;
  }

  async function load(key) {
    if (_buffers[key]) return;
    try {
      const res = await fetch(FILES[key]);
      const arr = await res.arrayBuffer();
      _buffers[key] = await getCtx().decodeAudioData(arr);
    } catch (e) { /* 読み込み失敗時は無音で継続 */ }
  }

  // ページロード後にバックグラウンドで全音源をプリロード
  function preload() {
    // AudioContext はユーザー操作後でないと作れないため、
    // 最初の操作で一括ロードする
    const handler = async () => {
      await Promise.all(Object.keys(FILES).map(load));
      document.removeEventListener('click', handler, true);
    };
    document.addEventListener('click', handler, true);
  }

  function playBuffer(key) {
    const buf = _buffers[key];
    if (!buf) return;
    const src = getCtx().createBufferSource();
    src.buffer = buf;
    src.connect(getCtx().destination);
    src.start();
  }

  function play(type) {
    if (_muted) return;
    try {
      if (_buffers[type]) {
        playBuffer(type);
      } else {
        // 未ロードならロード完了後に再生
        load(type).then(() => playBuffer(type)).catch(() => {});
      }
    } catch (e) { /* AudioContext 非対応環境では無視 */ }
  }

  function isMuted()    { return _muted; }
  function toggleMute() {
    _muted = !_muted;
    localStorage.setItem(MUTE_KEY, _muted ? '1' : '0');
    return _muted;
  }

  preload();
  return { play, isMuted, toggleMute };
})();
