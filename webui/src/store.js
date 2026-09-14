// store.js —— 极简全局事件总线，跨页面刷新通知。
// 支持本地 notify + 后端 SSE 实时事件（/system/events）。
export const store = {
  _listeners: new Set(),
  _lastEvent: null,
  _es: null,

  subscribe(fn) {
    this._listeners.add(fn);
    return () => this._listeners.delete(fn);
  },

  emit() {
    this._listeners.forEach(fn => { try { fn(); } catch {} });
  },

  notify() { this.emit(); },

  startRealtime() {
    if (this._es || typeof EventSource === 'undefined') return;
    try {
      const es = new EventSource('/system/events');
      this._es = es;
      es.onmessage = (e) => {
        try {
          this._lastEvent = JSON.parse(e.data);
        } catch {
          this._lastEvent = { raw: e.data };
        }
        this.emit();
      };
      es.onerror = () => {
        // 断线由 EventSource 自动重连；不主动关闭
      };
    } catch (err) {
      console.warn('SSE 不可用，降级为手动刷新', err);
    }
  },

  stopRealtime() {
    if (this._es) {
      try { this._es.close(); } catch {}
      this._es = null;
    }
  },
};
