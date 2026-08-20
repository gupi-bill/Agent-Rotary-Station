// store.js —— 极简全局事件总线，跨页面刷新通知。
export const store = {
  _listeners: new Set(),
  subscribe(fn) {
    this._listeners.add(fn);
    return () => this._listeners.delete(fn);
  },
  emit() {
    this._listeners.forEach(fn => { try { fn(); } catch {} });
  },
  notify() { this.emit(); },
};
