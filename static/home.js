'use strict';
// Older bot messages opened the root URL. Preserve Telegram's signed fragment
// when routing those existing Play buttons into the game.
if (new URLSearchParams(location.hash.slice(1)).has('tgWebAppData')) {
  location.replace('/play' + location.search + location.hash);
}
