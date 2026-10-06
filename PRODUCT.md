# ZiMo Mahjong

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary audience is friends who already know Singapore Mahjong, confirmed by the project owner. Beginner instruction is not an established product requirement.

## Product Purpose

ZiMo provides a private Singapore Mahjong table in a web browser where friends can join a room and play alongside bots. The current implementation plays one scored hand with winning, fan evaluation, configurable core rules, and a payment ledger.

## Operating Context

The existing application lets a player create a four-seat room with a display name, share an invitation link, and fill empty seats with bots. No account is required. Players can rejoin using room access saved in the same browser; clearing site data loses that access.

The web client supports desktop and mobile layouts. Its main surfaces are room creation/joining, the lobby, and the game table.

## Capabilities and Constraints

The following describes the current implementation documented in README.md, rather than a commitment to keep preview limitations forever:

- Room and game state are controlled by the server and updated in real time.
- Draws and bonus-tile replacements happen automatically; the player chooses a discard.
- Each discard opens a three-second resolution window.
- Chow, Pong, Kong-1/3/4, Game, and Pass are available in new rooms. Claim choices are final and resolve after the full three-second window. Kong-4 faces are public, and Kong-1 can be robbed for Game; optional Kong-4 robbery allows only 13 Wonders.
- The server evaluates standard and special wins, applies immediate and final payments, and shows the winner's fan breakdown and current balances. The host can edit payment and variation settings while waiting for players; a ready host must unready before editing. Bao and optional variations are supported; additional hands remain unavailable.

Open decisions: relative priority of convenient private play versus rules completeness and familiar table interactions; future feature scope; product-specific accessibility requirements; and any competitive positioning or success metrics.

## Brand Commitments

The existing product name is ZiMo Mahjong. The owner explicitly selected the tile artwork in `apps/web/public/mahjong_tiles/`, including the animal tiles. Preserve these supplied assets in future interface work unless the owner requests a change.

## Evidence on Hand

- `README.md` records the current one-hand scope, session behavior, and development setup.
- `apps/web/src/routes/HomePage.tsx` implements room creation, invitation entry, and saved-room access.
- `apps/web/src/features/room/lobby/` and `apps/web/src/features/room/table/` contain the existing lobby and table interfaces.
- `apps/web/public/mahjong_tiles/` contains the selected tile artwork.

## Product Principles

- Design for friends who already understand Singapore Mahjong.
- Make current gameplay capabilities and unavailable actions clear.
- Preserve the supplied tile artwork and recognizable tile identities.
