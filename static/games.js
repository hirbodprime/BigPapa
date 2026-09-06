'use strict';
try{window.Telegram?.WebApp.ready();window.Telegram?.WebApp.expand();}catch{}
for(const link of document.querySelectorAll('[data-game]'))link.href=link.getAttribute('href')+location.search+location.hash;
