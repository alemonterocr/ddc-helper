// Background service worker — sniffs CC-IDT token from outgoing DDC API requests
// and saves it to chrome.storage.local so the extension can use it.

console.log('[DDC Migration] Background sniffer active.');

chrome.webRequest.onBeforeSendHeaders.addListener(
  (details) => {
    for (const header of details.requestHeaders ?? []) {
      if (header.name.toLowerCase() === 'authorization') {
        chrome.storage.local.set({ ccIdtToken: header.value }, () => {
          console.log('[DDC Migration] CC-IDT token captured and saved.');
        });
      }
    }
    return {};
  },
  { urls: ['*://*.coxautoinc.com/*/api/*'] },
  ['requestHeaders']
);
