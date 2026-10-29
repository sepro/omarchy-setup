// Popup Guard: on the sites you switch it on for (toolbar button), new tabs and
// windows that lead to another site are blocked. guard.js stops them inside the
// page; this worker closes whatever still gets through (ad iframes from other
// origins, tricks guard.js doesn't know).

const siteOf = (url) => {
  try {
    const u = new URL(url);
    return /^https?:$/.test(u.protocol) ? u.hostname.replace(/^www\./, '') : null;
  } catch {
    return null;
  }
};
const covers = (site, host) => host === site || host.endsWith('.' + site);

const getSites = async () => (await chrome.storage.sync.get({ sites: [] })).sites;
const enabledFor = (sites, url) => {
  const host = siteOf(url);
  return host ? sites.find((s) => covers(s, host)) : undefined;
};

// guard.js has to run in the page's own world at document_start, before any
// ad script, so it's registered only for the enabled sites.
async function syncScripts() {
  const sites = await getSites();
  await chrome.scripting.unregisterContentScripts({ ids: ['guard'] }).catch(() => {});
  if (!sites.length) return;
  await chrome.scripting.registerContentScripts([{
    id: 'guard',
    js: ['guard.js'],
    world: 'MAIN',
    runAt: 'document_start',
    allFrames: true,
    matchOriginAsFallback: true,
    matches: sites.flatMap((s) => [`*://${s}/*`, `*://*.${s}/*`]),
  }]);
}

async function updateBadge(tabId, url) {
  const site = enabledFor(await getSites(), url);
  chrome.action.setBadgeBackgroundColor({ tabId, color: '#2e7d6b' });
  chrome.action.setBadgeText({ tabId, text: site ? 'on' : '' });
  chrome.action.setTitle({
    tabId,
    title: site
      ? `Popup Guard: on for ${site}. Click to turn off.`
      : 'Popup Guard: off. Click to block pop-up tabs on this site.',
  });
}

chrome.runtime.onInstalled.addListener(syncScripts);
chrome.runtime.onStartup.addListener(syncScripts);

chrome.action.onClicked.addListener(async (tab) => {
  const host = siteOf(tab.url);
  if (!host) return;
  const sites = await getSites();
  const site = enabledFor(sites, tab.url);
  await chrome.storage.sync.set({ sites: site ? sites.filter((s) => s !== site) : [...sites, host] });
  await syncScripts();
  chrome.tabs.reload(tab.id);
});

chrome.tabs.onUpdated.addListener((tabId, info, tab) => {
  if (info.url || info.status === 'loading') updateBadge(tabId, tab.url);
});
chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  const tab = await chrome.tabs.get(tabId).catch(() => null);
  if (tab) updateBadge(tabId, tab.url);
});

chrome.webNavigation.onCreatedNavigationTarget.addListener(async ({ sourceTabId, tabId, url }) => {
  const [sites, source] = await Promise.all([getSites(), chrome.tabs.get(sourceTabId).catch(() => null)]);
  const site = source && enabledFor(sites, source.url);
  if (!site) return;
  const host = siteOf(url);
  if (host && covers(site, host)) return;
  console.info('[Popup Guard] closed new tab', url, 'opened by', source.url);
  chrome.tabs.remove(tabId).catch(() => {});
});
