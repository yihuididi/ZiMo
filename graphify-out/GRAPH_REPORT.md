# Graph Report - ZiMo  (2026-09-29)

## Corpus Check
- 193 files · ~420,612 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 21 file(s) not represented in the graph (top: .toml 5, (none) 5, .css 4)

## Summary
- 2570 nodes · 8469 edges · 91 communities (82 shown, 9 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 530 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `58727335`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- live-browser.js
- singapore_game.py
- test_game_lobby.py
- resumeSession
- game/__init__.py
- setLiveState
- RoomState
- CorruptRoomStateError
- GameConfig
- modern-screenshot.umd.js
- test_persistence.py
- persistence/__init__.py
- el
- initPageChat
- game/actions.py
- SeatId
- worker.integration.test.mjs
- http_api.py
- types.ts
- test_room_lobby.py
- initGlobalBar
- kernel.py
- TableView.tsx
- GameRoom
- AuthenticatedRoom.tsx
- web/package.json
- mountSvelteComponentVariant
- test_room_gameplay.py
- LobbyView.tsx
- api.ts
- test_game_claims.py
- TestGameRoom
- PlayerPresenceRecord
- repository.py
- RoomGameplay
- test_facade_imports.py
- durable_room.py
- DomainId
- handleManualEditActivity
- validation.py
- .get_player
- RoomKernel
- test_game_setup.py
- session.ts
- App.test.tsx
- worker_entry.py
- resolveLiveInjectionAnchor
- Any
- ZiMo Mahjong current implementation
- compilerOptions
- createLiveBrowserSessionState
- log_unexpected
- standard_seats
- require_non_negative_int
- Actionable error messages
- onAnnotDown
- createLiveBrowserDomHelpers
- scripts
- AGENTS.md
- .canonical_data
- Impeccable skill
- Graphify knowledge graph pipeline
- PublicRoomView
- Native adaptation playbook
- Design system documentation
- Bamboo suit
- Character suit
- Dot suit
- Purposeful animation playbook
- SeatList.tsx
- Independent design critique
- live-browser-ignores.js
- Craft quality floor
- impeccable
- New visual work direction workflow
- enableInlineEdit
- .canonical_data
- SafeCORSMiddleware
- worker-probe.mjs
- Animal bonus tiles
- Flower bonus tiles
- Season bonus tiles
- Wind honor tiles
- Dragon honor tiles
- Asset producer fallback role
- Manual edit applier fallback role
- .canonical_data
- Plain green rounded tile back
- Apache License 2.0
- Web application testing with Playwright
- mahjong-api

## God Nodes (most connected - your core abstractions)
1. `RoomState` - 148 edges
2. `SeatId` - 126 edges
3. `GameModel` - 98 edges
4. `RoomRepository` - 85 edges
5. `SingaporeGameEngine` - 71 edges
6. `PlayerId` - 68 edges
7. `WindowId` - 44 edges
8. `GameConfig` - 40 edges
9. `validate_room()` - 38 edges
10. `HandState` - 36 edges

## Surprising Connections (you probably didn't know these)
- `Pure transition engine` --semantically_similar_to--> `Pure lobby and game transitions`  [INFERRED] [semantically similar]
  PLAN.md → README.md
- `Durable live-edit session journal` --semantically_similar_to--> `SQLite room_state snapshot`  [INFERRED] [semantically similar]
  .agents/skills/impeccable/reference/live.md → README.md
- `loadSession()` --indirect_call--> `sessionKey()`  [INFERRED]
  .agents/skills/impeccable/scripts/live-browser-session.js → apps/web/src/lib/session.ts
- `saveSession()` --indirect_call--> `sessionKey()`  [INFERRED]
  .agents/skills/impeccable/scripts/live-browser-session.js → apps/web/src/lib/session.ts
- `clearSession()` --indirect_call--> `sessionKey()`  [INFERRED]
  .agents/skills/impeccable/scripts/live-browser-session.js → apps/web/src/lib/session.ts

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Planned scoring settlement liability and full match progression** — plan_scoring, plan_payments, plan_bao, plan_full_match [EXTRACTED 1.00]
- **Authoritative room recovery and live delivery** — readme_gameroom, readme_snapshot, readme_websockets, readme_orchestrator [EXTRACTED 1.00]

## Communities (91 total, 9 thin omitted)

### Community 0 - "live-browser.js"
Cohesion: 0.03
Nodes (146): addManualContextText(), applyGlobalBarLabelState(), applyPlaceholderSizingStyles(), averageRgb01(), bindEditBadgeProxy(), bufferToBase64(), buildCollapsible(), buildColorModels() (+138 more)

### Community 1 - "singapore_game.py"
Cohesion: 0.07
Nodes (67): FinishHand, AutomatedDecisionRequested, ClaimWindowRequested, MatchCompletionRequested, parse_domain_effect_json(), model_validator, Requests for orchestration work emitted by pure game transitions., Ask room orchestration to finalize a clock-free completed preview. (+59 more)

### Community 2 - "test_game_lobby.py"
Cohesion: 0.13
Nodes (22): catalog_lobby_actions(), resolve_lobby_action(), Stable public facade for pure lobby policy and transitions., create_lobby_room(), normalize_display_name(), NFKC-normalize, strip control/format characters, and fold whitespace., CataloguedLobbyAction, LobbyAction (+14 more)

### Community 3 - "resumeSession"
Cohesion: 0.06
Nodes (86): applyParamDefaults(), applyParamValue(), applyPlaceholderDimensions(), applySavedSessionMeta(), clampVariantIndex(), clearHandled(), clearSession(), closedClipPath() (+78 more)

### Community 4 - "game/__init__.py"
Cohesion: 0.10
Nodes (57): GameModel, Shared modelling and canonical-serialization primitives for the game domain., Immutable, strict base model used by every persisted domain value. Attribute…, Immutable Singapore Mahjong configuration values., Pure, platform-neutral Singapore Mahjong domain foundation., ExternalSeatController, FanAward, MatchResult (+49 more)

### Community 5 - "setLiveState"
Cohesion: 0.09
Nodes (71): abandonForeignSession(), abortSvelteComponentInjection(), applyEditing(), beginNewLiveConfiguration(), cancelEditing(), cancelEditingToPicking(), cancelInsertConfigure(), cleanup() (+63 more)

### Community 6 - "RoomState"
Cohesion: 0.17
Nodes (41): ObservationBuilder, ProjectionBuilder, Protocol, PlayerId, PlayerState, RoomState, SeatState, _action_id() (+33 more)

### Community 7 - "CorruptRoomStateError"
Cohesion: 0.11
Nodes (13): CorruptRoomStateError, Raised when canonical state and its indexed metadata disagree., A projected event after the repository assigns its public sequence., StoredAuditEvent, Reconstruct the room from ``room_state`` and no auxiliary table., Atomically authenticate an active token against canonical membership., Return disconnected state for active players and generations only., Delete expired and consumed ticket rows without advancing revision. (+5 more)

### Community 8 - "GameConfig"
Cohesion: 0.06
Nodes (21): canonical_json(), BaseModel, Canonicalize an arbitrary Pydantic model using the domain convention., Public capabilities of the Singapore game., GameConfig, model_validator, Normalized settings reserved for future Singapore game features., Validate and return the immutable normalized configuration. (+13 more)

### Community 9 - "modern-screenshot.umd.js"
Cohesion: 0.09
Nodes (55): ae(), be(), bt(), Ce(), s(), Ct(), de(), dt() (+47 more)

### Community 10 - "test_persistence.py"
Cohesion: 0.11
Nodes (49): CommandId, Any, Create the schema, returning whether an older room was reset., Synchronous repository for one room per SQL database., RoomRepository, committed_event(), database(), initialized_event() (+41 more)

### Community 11 - "persistence/__init__.py"
Cohesion: 0.09
Nodes (40): Stable public facade for Mahjong room persistence. The Worker loads this module…, _audit_payload_json(), _canonical_json_value(), _canonicalize_json_text(), GameplayAuditPayload, _identity_text(), LobbyAuditPayload, _optional_text() (+32 more)

### Community 12 - "el"
Cohesion: 0.08
Nodes (54): actionLabel(), applyConfigureBarChrome(), bindConfigureCountPillTooltip(), bindConfigureInlineControlHover(), bindConfigureModifierPillHover(), buildConfigureActionControl(), buildConfigureCountControl(), buildConfigureRow() (+46 more)

### Community 13 - "initPageChat"
Cohesion: 0.07
Nodes (54): agentHasWorkInFlight(), armPageChatForTyping(), attachSteerFocusDebug(), attachSteerFocusGuard(), buildSteerProcessingDots(), buildSteerQueueHint(), clearSteerAwaitTimer(), clearSteerFocusRecoverTimer() (+46 more)

### Community 14 - "game/actions.py"
Cohesion: 0.06
Nodes (44): Chow, Continue, DeclareWin, Draw, Kong, parse_domain_action_json(), Pass, Pong (+36 more)

### Community 15 - "SeatId"
Cohesion: 0.09
Nodes (43): winning_claim(), _collect_held_tiles(), CompletePhase, DiscardState, HandId, HandResult, HandState, MatchId (+35 more)

### Community 16 - "worker.integration.test.mjs"
Cohesion: 0.06
Nodes (39): devDependencies, vitest, wrangler, ws, engines, node, vitest, name (+31 more)

### Community 17 - "http_api.py"
Cohesion: 0.11
Nodes (45): api_problem_handler(), CommandRequest, create_room(), CreateRoomRequest, _error_response(), _existing_room_stub(), get_events(), get_room() (+37 more)

### Community 18 - "types.ts"
Cohesion: 0.05
Nodes (45): ALL_TILE_FACES, animalFiles, animalNames, bonusNumbers, flowerNames, ranks, seasonNames, suitedLabel() (+37 more)

### Community 19 - "test_room_lobby.py"
Cohesion: 0.11
Nodes (11): FixedClock, descriptor_id(), DeterministicCapabilities, DeterministicIds, RoomCommandTests, RoomCreationAndAuthenticationTests, RoomOrchestratorTestCase, RoomPresenceTests (+3 more)

### Community 20 - "initGlobalBar"
Cohesion: 0.08
Nodes (41): agentStatusText(), barPaletteForTheme(), brandMarkSvg(), buildDesignHeader(), buildParamsPanel(), cursorForInsertAxis(), designPanelCss(), detectPageTheme() (+33 more)

### Community 21 - "kernel.py"
Cohesion: 0.09
Nodes (39): canonical_json(), capability_hash(), command_fingerprint(), derive_rotated_invite(), lobby_service_error(), parse_complete_config(), project_event(), CommandResult (+31 more)

### Community 22 - "TableView.tsx"
Cohesion: 0.11
Nodes (32): BonusTiles(), DiscardRiver(), Melds(), occupantName(), OpponentHand(), PhaseStatus(), positions, positionSeats() (+24 more)

### Community 23 - "GameRoom"
Cohesion: 0.11
Nodes (16): _close_socket(), GameRoom, initialize_schema(), Any, Run, then schedule and push every commit before returning., Point the room's sole alarm at its earliest durable deadline., Rediscover live identities without relying on in-memory socket state., Atomically reconcile live sockets restored after a wake or upgrade. (+8 more)

### Community 24 - "AuthenticatedRoom.tsx"
Cohesion: 0.18
Nodes (25): BrandLink(), PageHeading(), PageHeadingProps, AuthenticatedRoom(), LoadingRoom(), JoinRoom(), handleJoin(), LobbyView() (+17 more)

### Community 25 - "web/package.json"
Cohesion: 0.05
Nodes (36): dependencies, react, react-dom, react-router-dom, @supabase/supabase-js, devDependencies, jsdom, @testing-library/dom (+28 more)

### Community 26 - "mountSvelteComponentVariant"
Cohesion: 0.08
Nodes (33): acceptedDomAlreadyClean(), applyOriginalAttrsToSvelteAnchor(), captureAndEmit(), checkpointPayload(), clearHandledWrapperReloadStamp(), commitAcceptedSvelteComponentToDom(), compileShader(), componentModuleCandidates() (+25 more)

### Community 27 - "test_room_gameplay.py"
Cohesion: 0.05
Nodes (24): rules_for_id(), Compose command and presence use cases around one repository/cache owner., RoomOrchestrator, MultiplayerClaimTests, action_for_slot(), DeterministicCapabilities, DeterministicIds, DuplicateFaceRandomSource (+16 more)

### Community 28 - "LobbyView.tsx"
Cohesion: 0.15
Nodes (27): CommandStatus(), CommandStatusProps, CopyState, InvitePanel(), copyInvitation(), InvitePanelProps, LobbyViewProps, ActionEntry() (+19 more)

### Community 29 - "api.ts"
Cohesion: 0.15
Nodes (22): useRoomCommands(), RETRY_DELAYS_MS, MockWebSocket, useRoomSocket(), UseRoomSocketOptions, apiBaseUrl, ApiError, createRoom() (+14 more)

### Community 30 - "test_game_claims.py"
Cohesion: 0.10
Nodes (19): Discard, finalize_completed_preview(), FinalTileDecisionPhase, PendingDeadline, Canonical room-owned deadline for the active discard window., canonicalize_room_snapshot(), deserialize_room_state(), Canonical room snapshot encoding helpers. (+11 more)

### Community 31 - "TestGameRoom"
Cohesion: 0.09
Nodes (13): _json(), _MutableTestClock, Any, Reconstruct a pending window, then run the real alarm at N-1/N., Make one existing grace deadline due, then run the real alarm path., Run production batch reconciliation after test-controlled eviction., Real time by default, with explicit boundary control for one test RPC., Make the host the dealer and every automated decision reproducible. (+5 more)

### Community 32 - "PlayerPresenceRecord"
Cohesion: 0.12
Nodes (16): PlayerPresenceRecord, ProcessedCommandRecord, ProjectedAuditEvent, An allow-listed, secret-free event ready for public audit storage., Durable disconnected state for one active authentication generation., A durable idempotency result scoped to one room-local player., A hashed, single-use WebSocket ticket projection., Hashed, rotatable room invite capability; raw values never persist. (+8 more)

### Community 33 - "repository.py"
Cohesion: 0.07
Nodes (41): PersistenceError, ProcessedCommandConflictError, RuntimeError, Stable persistence failures with application-level meaning., Raised when a Durable Object has already been initialized., Raised when a commit is attempted before room initialization., Raised when an optimistic compare-and-swap revision is stale., Raised when storage was written by a newer or inconsistent schema. (+33 more)

### Community 34 - "RoomGameplay"
Cohesion: 0.15
Nodes (9): _CataloguedGameplayAction, _project_gameplay_event(), DomainAction, DomainEvent, Consume room-owned effects without exposing an intermediate state., Gameplay-side use cases layered on a :class:`RoomKernel`., Idempotently resolve the active window at its exact deadline., RoomGameplay (+1 more)

### Community 35 - "test_facade_imports.py"
Cohesion: 0.09
Nodes (14): is_server_ready(), main(), Start one or more servers, wait for them to be ready, run a command, then clean…, Wait for server to be ready by polling the port., PureDomainBoundaryTests, argparse, ast, importlib (+6 more)

### Community 36 - "durable_room.py"
Cohesion: 0.21
Nodes (22): WorkerResponse, Cloudflare Durable Object adapter for one authoritative room., _room_view_frame(), Stable Cloudflare Worker and Durable Object export facade., canonical_data(), canonical_json(), method_text(), parse_bearer() (+14 more)

### Community 37 - "DomainId"
Cohesion: 0.20
Nodes (5): ConnectionId, DomainId, Runtime-branded immutable identity that persists as a JSON string., CoreSchema, str

### Community 38 - "handleManualEditActivity"
Cohesion: 0.19
Nodes (24): clearStoredManualApplyState(), fetchPendingCount(), handleManualEditActivity(), hidePendingApplyDock(), manualApplyLoadingText(), manualApplyStateKey(), manualEditEventForCurrentPage(), numberOrNull() (+16 more)

### Community 39 - "validation.py"
Cohesion: 0.11
Nodes (31): PlayerProjectionError, Raised when authentication projections disagree with canonical state., PlayerRecord, Canonical state together with the duplicated indexed metadata., Authentication data plus a queryable projection of a room player., RoomStateRecord, Apply one public presence change and bump its version at most once., Create the canonical room and its supplied projections atomically. (+23 more)

### Community 40 - ".get_player"
Cohesion: 0.15
Nodes (7): Persist disconnected state for an active authentication generation. The…, Clear durable disconnected state for an active socket identity., Atomically clear disconnected state for active socket identities., Freeze disconnected seats, retaining their disconnected projection., update(), update(), update()

### Community 41 - "RoomKernel"
Cohesion: 0.11
Nodes (5): CommandResult, PublicRoomView, Sample the injected clock once for a complete incoming operation., Own the mutable repository cache and atomic commit boundary., RoomKernel

### Community 42 - "test_game_setup.py"
Cohesion: 0.07
Nodes (39): KongKind, StrEnum, concealed_kongs(), Pure claim catalogues and arrival-order-independent resolution., PlayerHand, Logical face shared by one or more uniquely identified physical tiles., RoomId, TileFace (+31 more)

### Community 43 - "session.ts"
Cohesion: 0.24
Nodes (19): browserStorage(), clearRoomSession(), InviteTokenRemoval, listStoredRooms(), loadRoomSession(), parsePersistedSession(), publicSession(), readFrom() (+11 more)

### Community 44 - "App.test.tsx"
Cohesion: 0.18
Nodes (16): App(), emitSocketView(), openHostLobby(), openMemberLobby(), openPromotedHostLobby(), socketHarness, viewWithDisconnectedMember(), shouldAcceptRoomView() (+8 more)

### Community 45 - "worker_entry.py"
Cohesion: 0.16
Nodes (13): Any, BaseModel, _read_environment_value(), Settings, create_supabase_client(), Create the shared client when both public Supabase values are configured., Default, Any (+5 more)

### Community 46 - "resolveLiveInjectionAnchor"
Cohesion: 0.16
Nodes (19): buildSvelteExpressionTextMap(), buildSveltePropValuesFromLiveElement(), buildSveltePropValuesV2(), cloneWithoutElements(), collectTextNodes(), collectVisibleTexts(), cssEscapeIdent(), elementMatchesOriginalMarkup() (+11 more)

### Community 47 - "Any"
Cohesion: 0.15
Nodes (9): ConfigRequest, EnvironmentCORSMiddleware, Any, Resolve the one allowed frontend origin from the Worker environment., Prevent all room responses, including errors, from being cached., Authenticate protected room routes before FastAPI parses their bodies., RoomBearerMiddleware, RoomNoStoreMiddleware (+1 more)

### Community 48 - "ZiMo Mahjong current implementation"
Cohesion: 0.07
Nodes (45): Durable live-edit session journal, Earned familiarity, ZiMo web entry shell, Bao liabilities and variations planned for Milestone 7, Commit before broadcast, Persisted SeatController descriptors, Nine-milestone Mahjong roadmap, Pure transition engine (+37 more)

### Community 49 - "compilerOptions"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, allowSyntheticDefaultImports, esModuleInterop, forceConsistentCasingInFileNames, isolatedModules, jsx, lib (+10 more)

### Community 50 - "createLiveBrowserSessionState"
Cohesion: 0.21
Nodes (15): createLiveBrowserSessionState(), clearHandled(), clearScrollY(), clearSession(), isHandled(), loadSession(), markHandled(), nextCheckpointRevision() (+7 more)

### Community 51 - "log_unexpected"
Cohesion: 0.15
Nodes (12): log_unexpected(), Secret-safe structured logging for redacted unexpected failures., Log an allow-listed boundary and exception category, never its values.…, CapturingLogger, test_http_boundary_keeps_redacted_response_and_logs_once(), test_logging_failure_never_replaces_public_error(), test_unexpected_log_is_structured_and_excludes_exception_values(), test_unexpected_log_normalizes_untrusted_operation_and_exception_type() (+4 more)

### Community 52 - "standard_seats"
Cohesion: 0.29
Nodes (5): Return the four stable empty table slots used by new rooms., standard_seats(), BrandedIdentityTests, room_with(), RoomInvariantMatrixTests

### Community 53 - "require_non_negative_int"
Cohesion: 0.19
Nodes (10): Any, require_non_negative_int(), require_text(), Persist a final-socket close and its canonical lobby consequences., Return the earliest pending pre-match disconnect deadline., Idempotently evict due pre-match players that remain offline., Presence-side use cases layered on a :class:`RoomKernel`., Reconcile one authenticated socket connection. (+2 more)

### Community 54 - "Actionable error messages"
Cohesion: 0.50
Nodes (4): Actionable error messages, UX copy clarification, Interface resilience, Internationalization resilience

### Community 55 - "onAnnotDown"
Cohesion: 0.20
Nodes (17): beginEditPin(), buildAnnotationsForCapture(), buildPinElement(), cancelEditingPin(), clampPlaceholderSize(), finalizeEditingPin(), initAnnotOverlay(), localCoords() (+9 more)

### Community 56 - "createLiveBrowserDomHelpers"
Cohesion: 0.17
Nodes (10): createLiveBrowserDomHelpers(), cssId(), liveUiRoot(), makeFrozenAnchor(), own(), pickable(), rectIsUsableAnchor(), uiAppend() (+2 more)

### Community 57 - "scripts"
Cohesion: 0.12
Nodes (15): engines, node, name, private, scripts, build:api, build:web, check (+7 more)

### Community 60 - "Impeccable skill"
Cohesion: 0.15
Nodes (20): Impeccable app interface metadata, Scoped visual amplification, Preserve scoped visual system, Semantic color strategy, OKLCH color space, Reusable design-system extraction, Repeated intent before extraction, Live browser variant editing (+12 more)

### Community 61 - "Graphify knowledge graph pipeline"
Cohesion: 0.15
Nodes (13): URL ingestion and file watching, Graph exports and benchmark, Extraction confidence provenance, Semantic extraction schema, GitHub cloning and cross-repository merge, Post-commit graph maintenance, Graph vocabulary expansion and traversal, Constrained vocabulary expansion (+5 more)

### Community 64 - "PublicRoomView"
Cohesion: 0.25
Nodes (9): AuthenticatedRoomProps, JoinRoomProps, RulesCard(), UseInviteCapabilityOptions, UseRoomCommandsOptions, PersistedRoomSession, RoomSession, PlayerRole (+1 more)

### Community 65 - "Native adaptation playbook"
Cohesion: 0.22
Nodes (10): Content-driven breakpoints, Web adaptation playbook, Native adaptation playbook, Native size classes, Material Design 3, Audit Health Score, Technical web audit, Technical native audit (+2 more)

### Community 66 - "Design system documentation"
Cohesion: 0.36
Nodes (8): Documenter fallback role, Shipped artifact as documentation authority, Impeccable artifact maintenance, Schema drift versus truth drift, DESIGN.md normative token schema, Design sidecar schema version 2, Design system documentation, PRODUCT.md durable product truth

### Community 68 - "Bamboo suit"
Cohesion: 0.20
Nodes (10): One bamboo: green bird on a branch, Bamboo suit, Two bamboo: two green vertical stalk symbols, Three bamboo: blue upper stalk and two green lower stalks, Four bamboo: two blue and two green stalk symbols, Five bamboo: pink center stalk with blue and green corners, Six bamboo: two rows of three green stalks, Seven bamboo: pink upper stalk and six green-blue stalks (+2 more)

### Community 69 - "Character suit"
Cohesion: 0.20
Nodes (10): One character: blue one numeral above pink wan character, Character suit, Two characters: blue two numeral above pink wan character, Three characters: blue three numeral above pink wan character, Four characters: blue four numeral above pink wan character, Five characters: blue five numeral above pink wan character, Six characters: blue six numeral above pink wan character, Seven characters: blue seven numeral above pink wan character (+2 more)

### Community 70 - "Dot suit"
Cohesion: 0.20
Nodes (10): One dot: large concentric blue-green-pink floral medallion, Dot suit, Two dots: green upper and blue lower floral circles, Three dots: blue, pink, green floral circles on a diagonal, Four dots: alternating blue and green floral circles at corners, Five dots: pink center with blue and green corner circles, Six dots: two green and four pink floral circles, Seven dots: three diagonal green and four pink circles (+2 more)

### Community 71 - "Purposeful animation playbook"
Cohesion: 0.22
Nodes (9): Apache License 2.0, Apache License 2.0, Frontend Design skill, Subject-specific visual identity, The Elements of Typographic Style, Purposeful animation playbook, Reduced-motion alternatives, Product-specific delight thesis (+1 more)

### Community 72 - "SeatList.tsx"
Cohesion: 0.36
Nodes (7): DisconnectedStatus(), DisconnectedStatusProps, formatCountdown(), remainingDisconnectSeconds(), seatDescription(), SeatList(), PublicSeatView

### Community 73 - "Independent design critique"
Cohesion: 0.25
Nodes (8): Cognitive load assessment, Cowan 2001 working-memory research, Independent design critique, Independent design and detector assessments, Nielsen usability heuristics, Interface simplification, Progressive disclosure, Bounded visual verification

### Community 74 - "live-browser-ignores.js"
Cohesion: 0.52
Nodes (6): globToRegex(), matchesScope(), normalizeIgnoreRule(), normalizeIgnoreValue(), pageCandidates(), resolveDetectIgnores()

### Community 75 - "Craft quality floor"
Cohesion: 0.29
Nodes (7): Craft floor, Craft quality floor, Finish reviewer fallback role, Recapture, rebuild, fix, ship, Immediate and Stop detector tiers, Design detector hooks, Operate mode interface design

### Community 76 - "impeccable"
Cohesion: 0.60
Nodes (5): impeccable script, check_download(), fetch_url(), probe_ok(), setup_help()

### Community 77 - "New visual work direction workflow"
Cohesion: 0.31
Nodes (11): Android platform guidance, Deprecated craft alias, Product context initialization, iOS platform guidance, Spatial layout playbook, Spatial thesis, Direction contract, New visual work direction workflow (+3 more)

### Community 78 - "enableInlineEdit"
Cohesion: 0.40
Nodes (5): collectEditableTextRows(), visit(), enableInlineEdit(), onInlineInput(), wrapMixedContentTextNodes()

### Community 79 - ".canonical_data"
Cohesion: 0.40
Nodes (3): Any, Return the canonical JSON-ready representation of this model., Serialize with stable key ordering and no insignificant whitespace.

### Community 81 - "SafeCORSMiddleware"
Cohesion: 0.40
Nodes (4): Keep rejected preflights on the same redacted error contract., SafeCORSMiddleware, CORSMiddleware, Headers

### Community 82 - "worker-probe.mjs"
Cohesion: 0.70
Nodes (4): exactJsonBody(), fetch(), jsonTextResponse(), roomStub()

### Community 83 - "Animal bonus tiles"
Cohesion: 0.40
Nodes (5): Animal bonus tiles, Cat animal tile: green cat, pink Chinese cat character, blue 1, Centipede animal tile: green segmented insect, pink character, blue 3, Mouse animal tile: green mouse, pink Chinese mouse character, blue 2, Rooster animal tile: green rooster with pink comb, Chinese character, blue 4

### Community 84 - "Flower bonus tiles"
Cohesion: 0.40
Nodes (5): Bamboo flower tile: green bamboo illustration, blue character, pink 4, Flower bonus tiles, Chrysanthemum flower tile: pink blossom, green leaves, pink 3, Orchid flower tile: green curved plant illustration and pink 2, Plum flower tile: pink blossom, green branches, pink 1

### Community 85 - "Season bonus tiles"
Cohesion: 0.40
Nodes (5): Autumn season tile: pink autumn character, green foliage, blue 3, Season bonus tiles, Spring season tile: pink spring character and blossom, green leaves, blue 1, Summer season tile: pink summer character and flower, green stems, blue 2, Winter season tile: pink winter character and blossom, green plant, blue 4

### Community 86 - "Wind honor tiles"
Cohesion: 0.40
Nodes (5): East wind tile: large blue east Chinese character, Wind honor tiles, North wind tile: large blue north Chinese character, South wind tile: large blue south Chinese character, West wind tile: large blue west Chinese character

### Community 87 - "Dragon honor tiles"
Cohesion: 0.50
Nodes (4): Green dragon: large green fa Chinese character, Dragon honor tiles, Red dragon: large pink zhong Chinese character, White dragon: blue double rectangular border with blank center

## Knowledge Gaps
- **198 isolated node(s):** `name`, `version`, `private`, `node`, `build` (+193 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 585 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RoomState` connect `RoomState` to `singapore_game.py`, `test_game_lobby.py`, `game/__init__.py`, `CorruptRoomStateError`, `GameConfig`, `test_persistence.py`, `persistence/__init__.py`, `game/actions.py`, `SeatId`, `kernel.py`, `test_room_gameplay.py`, `test_game_claims.py`, `PlayerPresenceRecord`, `repository.py`, `RoomGameplay`, `validation.py`, `RoomKernel`, `test_game_setup.py`, `standard_seats`, `.canonical_data`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Why does `RoomRepository` connect `test_persistence.py` to `PlayerPresenceRecord`, `repository.py`, `validation.py`, `.get_player`, `CorruptRoomStateError`, `persistence/__init__.py`, `game/actions.py`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Why does `GameConfig` connect `GameConfig` to `singapore_game.py`, `test_game_lobby.py`, `game/__init__.py`, `RoomState`, `test_room_gameplay.py`, `game/actions.py`, `SeatId`, `http_api.py`, `test_room_lobby.py`, `kernel.py`, `.canonical_data`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `RoomState` (e.g. with `choose_automated_action()` and `finalize_completed_preview()`) actually correct?**
  _`RoomState` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 42 inferred relationships involving `SeatId` (e.g. with `Chow` and `Continue`) actually correct?**
  _`SeatId` has 42 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `RoomRepository` (e.g. with `CorruptRoomStateError` and `PlayerProjectionError`) actually correct?**
  _`RoomRepository` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 43 inferred relationships involving `SingaporeGameEngine` (e.g. with `SingaporeRules` and `Discard`) actually correct?**
  _`SingaporeGameEngine` has 43 INFERRED edges - model-reasoned connections that need verification._