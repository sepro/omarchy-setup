// Popup Guard, page side. Runs in the page's own JS world before its scripts, on
// the sites Popup Guard is switched on for, and refuses to open new tabs or
// windows that lead to another site. Ad scripts open those from click handlers,
// which Chrome's own pop-up blocker lets through because they follow a click.
(() => {
  const strip = (h) => h.replace(/^www\./, '');
  const here = strip(location.hostname);
  const sameSite = (url) => {
    if (!url || /^(about|javascript|data|blob):/i.test(String(url))) return false;
    let h;
    try { h = strip(new URL(url, location.href).hostname); } catch { return false; }
    return !!h && (h === here || h.endsWith('.' + here) || here.endsWith('.' + h));
  };
  const opensNew = (target) => !['', '_self', '_parent', '_top'].includes(String(target ?? '').toLowerCase());
  const newTabAnchor = (a) => a?.nodeName === 'A' && opensNew(a.target) && !sameSite(a.href);
  const blocked = (how, url) => console.info('[Popup Guard] blocked', how, String(url || 'about:blank'));

  // Keyed on the patched open(), not the window: a frame that loads a new
  // document keeps its window object but gets a fresh, unpatched open().
  const guarded = new WeakSet();
  const guardWindow = (w) => {
    const open = w.open; // throws for a cross-origin frame
    if (guarded.has(open)) return;
    w.open = function (url, target = '_blank', features) {
      if (opensNew(target) && !sameSite(url)) return blocked('window.open', url), null;
      return open.call(this, url, target, features);
    };
    guarded.add(w.open);

    // Programmatic clicks on a (often detached) <a target="_blank">.
    const click = w.HTMLAnchorElement.prototype.click;
    w.HTMLAnchorElement.prototype.click = function () {
      if (newTabAnchor(this)) return blocked('link click', this.href);
      return click.call(this);
    };
    const dispatch = w.EventTarget.prototype.dispatchEvent;
    w.EventTarget.prototype.dispatchEvent = function (event) {
      if (event?.type === 'click' && newTabAnchor(this)) return blocked('link click', this.href), false;
      return dispatch.call(this, event);
    };

    const submit = w.HTMLFormElement.prototype.submit;
    w.HTMLFormElement.prototype.submit = function () {
      if (opensNew(this.target) && !sameSite(this.action)) return blocked('form', this.action);
      return submit.call(this);
    };

    // Real clicks on links (incl. invisible full-page overlays) to other sites in a new tab.
    w.addEventListener('click', (e) => {
      const a = e.target?.closest?.('a[href]');
      if (a && newTabAnchor(a)) {
        e.preventDefault();
        blocked('link', a.href);
      }
    }, true);

    // A fresh about:blank iframe has its own, untouched window.open; ad scripts
    // borrow it to get around a patched one, so patch frames as they're reached.
    const proto = w.HTMLIFrameElement.prototype;
    const desc = Object.getOwnPropertyDescriptor(proto, 'contentWindow');
    Object.defineProperty(proto, 'contentWindow', {
      ...desc,
      get() {
        const cw = desc.get.call(this);
        if (cw) try { guardWindow(cw); } catch { /* cross-origin frame */ }
        return cw;
      },
    });
  };

  guardWindow(window);
})();
