# Popup Guard: block pop-up tabs on chosen sites

Some sites open an ad in a new tab (or a "pop-under" behind the current one)
every time you click anywhere on the page. Chrome's own pop-up blocker lets
these through: it only blocks pop-ups that don't follow a click, and these
scripts run from your click.

Popup Guard is a small Chrome extension that, on the sites you switch it on
for, refuses every new tab or window that leads to **another** site. Links and
pop-ups within the same site keep working. It does nothing on sites you haven't
switched on, so it can't break the rest of the web.

![Popup Guard button with the "on" badge](img/popup-guard.png)

## Install

```sh
./install.sh popup-guard
```

Copies `popup-guard/` to `~/.local/share/popup-guard/`. Then one manual step,
because Chrome stable ignores `--load-extension`: `chrome://extensions` ->
Developer mode -> Load unpacked -> `~/.local/share/popup-guard` (the installer
copies the path to the clipboard). After a later update, the installer says so;
press the extension's reload button in `chrome://extensions`.

For incognito windows (e.g. the private browser shortcut), also turn on
Popup Guard -> Details -> **Allow in Incognito**: Chrome keeps every extension
off in incognito until you do. Incognito tabs then use the same site list.

## Usage

| Action | Result |
|---|---|
| Click the Popup Guard toolbar button on a site | Switches it on for that site (and its subdomains); the page reloads and the button shows an `on` badge |
| Click it again | Switches it off for that site |

Pin the button (puzzle-piece menu -> pin) to see the badge. The site list is
kept in Chrome sync storage, so it follows your Google account.

On a site that's switched on, a link you deliberately open in a new tab to
another site is blocked too. Switch the site off for a moment, or open the link
in the same tab.

## How it works

- **In the page** (`guard.js`): registered only for the switched-on sites, it
  runs in the page's own JavaScript world before any of the page's scripts and
  replaces `window.open`, the programmatic click on a hidden `<a target="_blank">`,
  `dispatchEvent` of such a click, `form.submit()` to a new window, and real
  clicks on `target="_blank"` links (including invisible full-page overlays).
  Anything aimed at another site in a new tab is dropped; `window.open` returns
  `null`, as when Chrome's blocker stops it. Ad scripts also borrow the untouched
  `window.open` of a fresh blank iframe, so iframes' windows get patched the
  moment the page reaches for them.
- **In the background** (`background.js`): a safety net for what the page script
  can't reach, such as an ad iframe from another domain. When a tab on a
  switched-on site opens a new tab to another site, the new tab is closed straight
  away.

Blocked pop-ups are logged in the page's DevTools console as `[Popup Guard]`.

## Alternative: uBlock Origin Lite

[uBlock Origin Lite](https://chromewebstore.google.com/detail/ublock-origin-lite/ddkjiahejlhfcafbddmgiahcphecmpfh)
from the Chrome Web Store blocks many of these pop-up networks by their ad
domains, plus the ads themselves, on every site. It's a good companion, but its
filter lists lag behind sites that rotate ad domains, which is where Popup
Guard's "no new tabs to other sites" rule still catches them. Both can run side
by side.
