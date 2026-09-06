# Papa Zombie — street survival

A cartoon endless side-scrolling shooter. Papa walks automatically; tap Fire
(or Space) for each shot at the nearest zombie in range. Holding does not repeat shots. Jump (W / Up) to avoid contact;
reload manually with R or let an empty magazine reload automatically. Audio and
rendering run on the player's device. There are no bosses in this release.

Birds and emerging ground zombies overlap front-enemy combat. Hold Duck (S /
Down) for birds; time Jump (W / Up) over ground zombies. Each missed dodge costs
one heart. Warnings last 1.2 seconds before approach. Hazards alternate, stay
separated, and become more frequent on later streets. They do not award kills.
Papa has a striding walk and crouch; walkers shuffle, runners stride quickly,
and tanks lumber.

## Balance

- Five health points. Ordinary contact costs one; tanks cost two.
- A supply storefront appears after 20 kills on each street. Tap the building
  or Enter Store, buy supplies, then leave; Keep Walking skips the store.
  Combat pauses at the store.
- Sidekick pistol: free, infinite reserve, 8-round magazine, 1 base damage.
- Street Sweeper SMG: 150 coins, 24-round magazine, fast 2-damage shots.
- Boomstick shotgun: 280 coins, 6-round magazine, 4 damage per shot.
- Nightfall rifle: 500 coins, 10-round magazine, 7 damage.
- Every purchased gun comes with 40 shared rounds. The pistol automatically
  replaces an empty purchased weapon. Re-equip owned guns at a shop.
- Ammo: 60 rounds for `35 + 5 × street` coins, 600-round reserve cap.
- Heal: two hearts for `55 + 10 × street`, up to five hearts; one kit per store.
- Damage upgrade: +1 to every gun, five levels; costs 80, 320, 720, 1280, 2000.
- Spare life: 300 coins initially, then doubles after each purchase. Carry one
  at a time; it automatically restores five hearts and clears immediate danger.
- Kills reward `10 + 2 × floor(street/2)` coins, plus 3 for runners or 8 for tanks.
- Runners appear from street 2; tanks from street 3. Zombies arrive one at a time. Health and movement speed increase. Progression continues without a final street.
- Coins, weapons, upgrades, and spare lives reset on a new run.

The mascot drawing is shared with Papa Chop. Guns appear in Papa’s hands and
in shop previews; zombie outfits and the scrolling buildings vary. Mistimed
shots waste ammunition, reloads leave an opening, and later tanks demand upgrades.

## Scores and integrity

Score is zombies defeated. Zombie scores are separate from Papa Chop. Private,
global, and group views are available; the latest zombie group message updates
with that group's top 10. Use `/zombie` in a group or select Zombie after `/play`.

The browser and server run the same deterministic 20 Hz simulation. Only input
batches and shop choices are accepted, not client-provided kills, coins, damage,
or inventory. Combat checkpoints occur at shops, death, and once per 60 seconds.
Ownership, group scope, timing, and spending are checked. Repeated requests are
idempotent. This prevents arbitrary score/coin injection, not automated legal play.

The latest validated checkpoint is ranked even if a connection is lost later.
Browser practice stores only a local best. Pausing or backgrounding stops combat.
Runs expire after 24 hours of inactivity and history is retained for 30 days.

Routes: `/zombie`, `/games`; API: `/api/zombie/start`, `/api/zombie/action`,
`/api/zombie/leaderboard`. Data is stored in new `zombie_*` tables. Existing Chop
scores and rules are preserved.

Pace update: base zombie speed 6 (previously 4), shorter arrival gaps, faster
street scrolling and hazards. Jump airtime is 1.05 seconds (previously 0.75),
with 1.9 seconds between jump starts.
