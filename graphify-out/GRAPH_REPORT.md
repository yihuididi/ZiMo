# Graph Report - ZiMo  (2026-10-06)

## Corpus Check
- 202 files · ~431,586 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 21 file(s) not represented in the graph (top: .toml 5, (none) 5, .css 4)

## Summary
- 2731 nodes · 9352 edges · 100 communities (92 shown, 8 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 649 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `26eb60f1`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- live-browser.js
- singapore_game.py
- test_game_variations.py
- resumeSession
- game/__init__.py
- setLiveState
- RoomState
- repository.py
- RoomId
- modern-screenshot.umd.js
- test_persistence.py
- persistence/__init__.py
- el
- initPageChat
- controllers.py
- model.py
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
- SeatId
- _row_value
- RoomRepository
- sql.py
- RoomGameplay
- test_facade_imports.py
- durable_room.py
- test_game_setup.py
- handleManualEditActivity
- _validate_stored_event_history
- PlayerRecord
- RoomKernel
- GameConfig
- session.ts
- App.test.tsx
- worker_entry.py
- resolveLiveInjectionAnchor
- Any
- ZiMo Mahjong current implementation
- compilerOptions
- createLiveBrowserSessionState
- log_unexpected
- rules_for_id
- require_non_negative_int
- Actionable error messages
- onAnnotDown
- createLiveBrowserDomHelpers
- scripts
- AGENTS.md
- useRoomCommands.ts
- Impeccable skill
- Graphify knowledge graph pipeline
- RoomServiceError
- AlternateRules
- PublicRoomView
- Native adaptation playbook
- Design system documentation
- PlayerId
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
- test_room_claims.py
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
- AllBonusChainRandomSource
- test_game_scoring.py
- OpaqueActionDescriptor
- MatchState
- DeterministicRandomSource

## God Nodes (most connected - your core abstractions)
1. `RoomState` - 163 edges
2. `SeatId` - 162 edges
3. `GameModel` - 102 edges
4. `RoomRepository` - 87 edges
5. `SingaporeGameEngine` - 85 edges
6. `PlayerId` - 68 edges
7. `GameConfig` - 61 edges
8. `validate_room()` - 59 edges
9. `HandState` - 55 edges
10. `WindowId` - 49 edges

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

## Communities (100 total, 8 thin omitted)

### Community 0 - "live-browser.js"
Cohesion: 0.03
Nodes (146): addManualContextText(), applyGlobalBarLabelState(), applyPlaceholderSizingStyles(), averageRgb01(), bindEditBadgeProxy(), bufferToBase64(), buildCollapsible(), buildColorModels() (+138 more)

### Community 1 - "singapore_game.py"
Cohesion: 0.08
Nodes (62): FinishHand, AutomatedDecisionRequested, ClaimWindowRequested, MatchCompletionRequested, parse_domain_effect_json(), model_validator, Ask room orchestration to finalize a clock-free completed hand., finalize_completed_hand() (+54 more)

### Community 2 - "test_game_variations.py"
Cohesion: 0.12
Nodes (41): Chow, Continue, DeclareWin, Kong, KongKind, parse_domain_action_json(), Pass, Pong (+33 more)

### Community 3 - "resumeSession"
Cohesion: 0.06
Nodes (86): applyParamDefaults(), applyParamValue(), applyPlaceholderDimensions(), applySavedSessionMeta(), clampVariantIndex(), clearHandled(), clearSession(), closedClipPath() (+78 more)

### Community 4 - "game/__init__.py"
Cohesion: 0.09
Nodes (58): Draw, GameModel, Shared modelling and canonical-serialization primitives for the game domain., Immutable, strict base model used by every persisted domain value. Attribute…, Public capabilities of the Singapore game., Immutable Singapore Mahjong configuration values., Requests for orchestration work emitted by pure game transitions., Pure, platform-neutral Singapore Mahjong domain foundation. (+50 more)

### Community 5 - "setLiveState"
Cohesion: 0.09
Nodes (71): abandonForeignSession(), abortSvelteComponentInjection(), applyEditing(), beginNewLiveConfiguration(), cancelEditing(), cancelEditingToPicking(), cancelInsertConfigure(), cleanup() (+63 more)

### Community 6 - "RoomState"
Cohesion: 0.15
Nodes (45): PlayerState, RoomState, SeatState, _add_bots(), apply_lobby_action(), _can_start(), Pure lobby action catalogue, resolution, and application., _start() (+37 more)

### Community 7 - "repository.py"
Cohesion: 0.11
Nodes (39): PersistenceError, PlayerProjectionError, ProcessedCommandConflictError, RuntimeError, Stable persistence failures with application-level meaning., Raised when a Durable Object has already been initialized., Raised when a commit is attempted before room initialization., Raised when an optimistic compare-and-swap revision is stale. (+31 more)

### Community 8 - "RoomId"
Cohesion: 0.17
Nodes (11): AutomatedSeatController, ExternalSeatController, PolicyId, Return the four stable empty table slots used by new rooms., RoomId, standard_seats(), BrandedIdentityTests, automated_seats() (+3 more)

### Community 9 - "modern-screenshot.umd.js"
Cohesion: 0.09
Nodes (55): ae(), be(), bt(), Ce(), s(), Ct(), de(), dt() (+47 more)

### Community 10 - "test_persistence.py"
Cohesion: 0.10
Nodes (55): CommandId, Adapter for a CPython ``sqlite3.Connection``. The connection is switched to…, SQLiteSqlExecutor, Compose command and presence use cases around one repository/cache owner., RoomOrchestrator, committed_event(), database(), initialized_event() (+47 more)

### Community 11 - "persistence/__init__.py"
Cohesion: 0.14
Nodes (32): Stable public facade for Mahjong room persistence. The Worker loads this module…, _canonical_json_value(), _canonicalize_json_text(), _identity_text(), _now_ms(), _optional_text(), _player_presence_from_row(), _player_record_from_row() (+24 more)

### Community 12 - "el"
Cohesion: 0.08
Nodes (54): actionLabel(), applyConfigureBarChrome(), bindConfigureCountPillTooltip(), bindConfigureInlineControlHover(), bindConfigureModifierPillHover(), buildConfigureActionControl(), buildConfigureCountControl(), buildConfigureRow() (+46 more)

### Community 13 - "initPageChat"
Cohesion: 0.07
Nodes (54): agentHasWorkInFlight(), armPageChatForTyping(), attachSteerFocusDebug(), attachSteerFocusGuard(), buildSteerProcessingDots(), buildSteerQueueHint(), clearSteerAwaitTimer(), clearSteerFocusRecoverTimer() (+46 more)

### Community 14 - "controllers.py"
Cohesion: 0.14
Nodes (14): AutomatedPolicy, AutomatedPolicySelector, choose_automated_action(), NoLegalActionsError, DomainAction, Protocol, RuntimeError, Controller-facing policy ports; external seats deliberately have no chooser. (+6 more)

### Community 15 - "model.py"
Cohesion: 0.09
Nodes (38): _collect_held_tiles(), CompletePhase, ConnectionId, DiscardState, DomainId, HandId, HandResult, HandState (+30 more)

### Community 16 - "worker.integration.test.mjs"
Cohesion: 0.06
Nodes (39): devDependencies, vitest, wrangler, ws, engines, node, vitest, name (+31 more)

### Community 17 - "http_api.py"
Cohesion: 0.11
Nodes (45): api_problem_handler(), CommandRequest, create_room(), CreateRoomRequest, _error_response(), _existing_room_stub(), get_events(), get_room() (+37 more)

### Community 18 - "types.ts"
Cohesion: 0.05
Nodes (49): ALL_TILE_FACES, animalFiles, animalNames, bonusNumbers, flowerNames, ranks, seasonNames, suitedLabel() (+41 more)

### Community 19 - "test_room_lobby.py"
Cohesion: 0.11
Nodes (12): FixedClock, descriptor_id(), DeterministicCapabilities, DeterministicIds, RoomCommandTests, RoomCreationAndAuthenticationTests, RoomOrchestratorTestCase, RoomPresenceTests (+4 more)

### Community 20 - "initGlobalBar"
Cohesion: 0.08
Nodes (41): agentStatusText(), barPaletteForTheme(), brandMarkSvg(), buildDesignHeader(), buildParamsPanel(), cursorForInsertAxis(), designPanelCss(), detectPageTheme() (+33 more)

### Community 21 - "kernel.py"
Cohesion: 0.18
Nodes (22): canonical_json(), command_fingerprint(), derive_rotated_invite(), parse_complete_config(), project_event(), CommandResult, GameConfig, Canonical validation, hashing, and projection helpers for room services. (+14 more)

### Community 22 - "TableView.tsx"
Cohesion: 0.16
Nodes (27): baoLabel(), BonusTiles(), DiscardRiver(), Melds(), occupantName(), OpponentHand(), PhaseStatus(), positions (+19 more)

### Community 23 - "GameRoom"
Cohesion: 0.11
Nodes (16): _close_socket(), GameRoom, initialize_schema(), Any, Run, then schedule and push every commit before returning., Point the room's sole alarm at its earliest durable deadline., Rediscover live identities without relying on in-memory socket state., Atomically reconcile live sockets restored after a wake or upgrade. (+8 more)

### Community 24 - "AuthenticatedRoom.tsx"
Cohesion: 0.19
Nodes (23): BrandLink(), PageHeading(), PageHeadingProps, AuthenticatedRoom(), LoadingRoom(), JoinRoom(), LobbyView(), LostSession() (+15 more)

### Community 25 - "web/package.json"
Cohesion: 0.05
Nodes (38): dependencies, react, react-dom, react-router-dom, @supabase/supabase-js, devDependencies, jsdom, @testing-library/dom (+30 more)

### Community 26 - "mountSvelteComponentVariant"
Cohesion: 0.08
Nodes (33): acceptedDomAlreadyClean(), applyOriginalAttrsToSvelteAnchor(), captureAndEmit(), checkpointPayload(), clearHandledWrapperReloadStamp(), commitAcceptedSvelteComponentToDom(), compileShader(), componentModuleCandidates() (+25 more)

### Community 27 - "test_room_gameplay.py"
Cohesion: 0.08
Nodes (14): MultiplayerClaimTests, action_for_slot(), DeterministicCapabilities, DeterministicIds, DuplicateFaceRandomSource, MutableClock, Valid deterministic permutation with seat zero and first legal choices., Deal two physical copies of the first face to seat zero. (+6 more)

### Community 28 - "LobbyView.tsx"
Cohesion: 0.24
Nodes (18): CommandStatus(), CommandStatusProps, CopyState, InvitePanel(), copyInvitation(), InvitePanelProps, LobbyViewProps, ActionEntry() (+10 more)

### Community 29 - "api.ts"
Cohesion: 0.17
Nodes (19): RETRY_DELAYS_MS, MockWebSocket, useRoomSocket(), apiBaseUrl, ApiError, createRoom(), createSocketTicket(), ErrorEnvelope (+11 more)

### Community 30 - "SeatId"
Cohesion: 0.07
Nodes (50): Discard, winning_claim(), AwaitingDiscardPhase, PendingClaim, PendingDeadline, Canonical room-owned deadline for the active claim window., SeatId, canonicalize_room_snapshot() (+42 more)

### Community 31 - "_row_value"
Cohesion: 0.07
Nodes (22): application_table_names(), migrate(), _json(), _KongFourRandomSource, _MutableTestClock, Any, Test-only Python Worker exports for Durable Object storage acceptance tests.…, Production adapter plus fixed test-only SQLite inspection RPCs. (+14 more)

### Community 32 - "RoomRepository"
Cohesion: 0.07
Nodes (29): PlayerPresenceRecord, ProcessedCommandRecord, ProjectedAuditEvent, An allow-listed, secret-free event ready for public audit storage., Durable disconnected state for one active authentication generation., A durable idempotency result scoped to one room-local player., A hashed, single-use WebSocket ticket projection., Hashed, rotatable room invite capability; raw values never persist. (+21 more)

### Community 33 - "sql.py"
Cohesion: 0.10
Nodes (16): CloudflareSqlExecutor, one(), Any, Protocol, _T, Synchronous SQL ports and adapters used by room persistence., The complete SQL surface used by the room repository. ``exec`` intentionally…, Execute one SQL statement and return a cursor-like value. (+8 more)

### Community 34 - "RoomGameplay"
Cohesion: 0.14
Nodes (11): _CataloguedGameplayAction, _project_gameplay_event(), DomainAction, DomainEvent, Gameplay-side use cases layered on a :class:`RoomKernel`., Idempotently resolve the active window at its exact deadline., Consume room-owned effects without exposing an intermediate state., RoomGameplay (+3 more)

### Community 35 - "test_facade_imports.py"
Cohesion: 0.09
Nodes (14): is_server_ready(), main(), Start one or more servers, wait for them to be ready, run a command, then clean…, Wait for server to be ready by polling the port., PureDomainBoundaryTests, argparse, ast, importlib (+6 more)

### Community 36 - "durable_room.py"
Cohesion: 0.21
Nodes (22): WorkerResponse, Cloudflare Durable Object adapter for one authoritative room., _room_view_frame(), Stable Cloudflare Worker and Durable Object export facade., canonical_data(), canonical_json(), method_text(), parse_bearer() (+14 more)

### Community 37 - "test_game_setup.py"
Cohesion: 0.14
Nodes (24): PhysicalTile, Logical face shared by one or more uniquely identified physical tiles., TileFace, canonical_face_counts(), canonical_physical_deck(), canonical_tile_faces(), is_bonus_face(), is_bonus_tile() (+16 more)

### Community 38 - "handleManualEditActivity"
Cohesion: 0.19
Nodes (24): clearStoredManualApplyState(), fetchPendingCount(), handleManualEditActivity(), hidePendingApplyDock(), manualApplyLoadingText(), manualApplyStateKey(), manualEditEventForCurrentPage(), numberOrNull() (+16 more)

### Community 39 - "_validate_stored_event_history"
Cohesion: 0.10
Nodes (19): _audit_payload_json(), GameplayAuditPayload, LobbyAuditPayload, _parse_audit_payload(), Allow-listed public lobby fact with canonical, secret-free details., Allow-listed public gameplay fact with no hidden tile identifiers., A projected event after the repository assigns its public sequence., Canonical state together with the duplicated indexed metadata. (+11 more)

### Community 40 - "PlayerRecord"
Cohesion: 0.11
Nodes (13): CorruptRoomStateError, Raised when canonical state and its indexed metadata disagree., PlayerRecord, Authentication data plus a queryable projection of a room player., Apply one public presence change and bump its version at most once., Atomically authenticate an active token against canonical membership., Clear durable disconnected state for an active socket identity., Atomically clear disconnected state for active socket identities. (+5 more)

### Community 41 - "RoomKernel"
Cohesion: 0.11
Nodes (5): capability_hash(), CommandResult, Sample the injected clock once for a complete incoming operation., Own the mutable repository cache and atomic commit boundary., RoomKernel

### Community 42 - "GameConfig"
Cohesion: 0.11
Nodes (9): canonical_json(), BaseModel, Canonicalize an arbitrary Pydantic model using the domain convention., GameConfig, model_validator, Normalized Singapore settings for the current single-hand ruleset., GameConfigTests, VariationScoringTests (+1 more)

### Community 43 - "session.ts"
Cohesion: 0.24
Nodes (19): browserStorage(), clearRoomSession(), InviteTokenRemoval, listStoredRooms(), loadRoomSession(), parsePersistedSession(), publicSession(), readFrom() (+11 more)

### Community 44 - "App.test.tsx"
Cohesion: 0.14
Nodes (19): App(), emitSocketView(), openHostLobby(), openMemberLobby(), openPromotedHostLobby(), socketHarness, viewWithDisconnectedMember(), RulesCard() (+11 more)

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

### Community 52 - "rules_for_id"
Cohesion: 0.07
Nodes (23): GameEngine, Any, GameRules, Protocol, Registry of supported game rulesets., rules_for_id(), ValueError, Raised when a configuration is not supported. (+15 more)

### Community 53 - "require_non_negative_int"
Cohesion: 0.17
Nodes (11): Any, require_non_negative_int(), require_text(), CommandResult, Persist a final-socket close and its canonical lobby consequences., Return the earliest pending pre-match disconnect deadline., Idempotently evict due pre-match players that remain offline., Presence-side use cases layered on a :class:`RoomKernel`. (+3 more)

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

### Community 59 - "useRoomCommands.ts"
Cohesion: 0.19
Nodes (14): handleJoin(), CommandOperationBase, initialRoomCommandState, matchingOperation(), PendingCommand, RoomCommandEvent, roomCommandReducer(), RoomCommandState (+6 more)

### Community 60 - "Impeccable skill"
Cohesion: 0.15
Nodes (20): Impeccable app interface metadata, Scoped visual amplification, Preserve scoped visual system, Semantic color strategy, OKLCH color space, Reusable design-system extraction, Repeated intent before extraction, Live browser variant editing (+12 more)

### Community 61 - "Graphify knowledge graph pipeline"
Cohesion: 0.15
Nodes (13): URL ingestion and file watching, Graph exports and benchmark, Extraction confidence provenance, Semantic extraction schema, GitHub cloning and cross-repository merge, Post-commit graph maintenance, Graph vocabulary expansion and traversal, Constrained vocabulary expansion (+5 more)

### Community 62 - "RoomServiceError"
Cohesion: 0.15
Nodes (11): lobby_service_error(), PublicRoomView, Authenticate for transport preflight without projecting a room view., Project after the caller has already advanced and sampled time., Command-side use cases layered on a :class:`RoomKernel`., RoomCommands, AuthenticatedPlayer, ProjectedEvents (+3 more)

### Community 63 - "AlternateRules"
Cohesion: 0.15
Nodes (4): Validate and return the immutable normalized configuration., AlternateEngine, AlternateRules, GameConfig

### Community 64 - "PublicRoomView"
Cohesion: 0.18
Nodes (13): AuthenticatedRoomProps, JoinRoomProps, paymentFields, RulesCardProps, variationFields, UseInviteCapabilityOptions, UseRoomCommandsOptions, UseRoomSocketOptions (+5 more)

### Community 65 - "Native adaptation playbook"
Cohesion: 0.22
Nodes (10): Content-driven breakpoints, Web adaptation playbook, Native adaptation playbook, Native size classes, Material Design 3, Audit Health Score, Technical web audit, Technical native audit (+2 more)

### Community 66 - "Design system documentation"
Cohesion: 0.36
Nodes (8): Documenter fallback role, Shipped artifact as documentation authority, Impeccable artifact maintenance, Schema drift versus truth drift, DESIGN.md normative token schema, Design sidecar schema version 2, Design system documentation, PRODUCT.md durable product truth

### Community 67 - "PlayerId"
Cohesion: 0.16
Nodes (17): PlayerId, _action_id(), catalog_lobby_actions(), resolve_lobby_action(), create_lobby_room(), LobbyAction, LobbyActionKind, StrEnum (+9 more)

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

### Community 80 - "test_room_claims.py"
Cohesion: 0.18
Nodes (5): kong_four_room(), KongFourTests, WondersDeck, Revisioned settings and reconstructed Kong-4 windows through the room boundary., unittest

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

### Community 95 - "AllBonusChainRandomSource"
Cohesion: 0.12
Nodes (9): AllBonusChainRandomSource, DealerTwoInitialBonusRandomSource, FinalLiveBonusRandomSource, InitialBonusRandomSource, T, Deal one raw bonus, then provide a regular opposite-end replacement., Put one bonus at the final live position and the other bonuses in reserve., Exercise dealer-relative initial exposure and a bonus replacement. (+1 more)

### Community 96 - "test_game_scoring.py"
Cohesion: 0.33
Nodes (15): WallState, face(), names(), player(), TileFace, TileFamily, Default-rule winning patterns and award composition., score() (+7 more)

### Community 97 - "OpaqueActionDescriptor"
Cohesion: 0.24
Nodes (7): ObservationBuilder, ProjectionBuilder, Protocol, OpaqueActionDescriptor, PublicRoomView, model_validator, Presentation-only handle resolved to a domain action by orchestration.

### Community 98 - "MatchState"
Cohesion: 0.08
Nodes (20): fresh_discard(), qualifying_liability(), honor_fan(), visible_honor_fan(), Evaluate only the accepted claim, against evidence before it resolved., record_liability(), BaoLiability, MatchState (+12 more)

### Community 99 - "DeterministicRandomSource"
Cohesion: 0.12
Nodes (7): DeterministicRandomSource, T, Return a shuffled copy without mutating the caller's values., Cryptographically strong runtime randomness., Seeded deterministic RNG intended for tests and replay fixtures only., SystemRandomSource, RuntimePortTests

## Knowledge Gaps
- **203 isolated node(s):** `name`, `version`, `private`, `node`, `build` (+198 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 618 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RoomState` connect `RoomState` to `singapore_game.py`, `test_game_variations.py`, `game/__init__.py`, `repository.py`, `RoomId`, `test_persistence.py`, `persistence/__init__.py`, `controllers.py`, `model.py`, `kernel.py`, `SeatId`, `RoomRepository`, `RoomGameplay`, `test_game_setup.py`, `_validate_stored_event_history`, `PlayerRecord`, `RoomKernel`, `GameConfig`, `rules_for_id`, `AlternateRules`, `PlayerId`, `OpaqueActionDescriptor`, `MatchState`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Why does `SeatId` connect `SeatId` to `test_game_scoring.py`, `singapore_game.py`, `test_game_variations.py`, `MatchState`, `game/__init__.py`, `RoomGameplay`, `RoomState`, `test_game_setup.py`, `RoomId`, `test_persistence.py`, `controllers.py`, `model.py`, `test_room_claims.py`, `rules_for_id`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Why does `GameConfig` connect `GameConfig` to `OpaqueActionDescriptor`, `test_game_variations.py`, `singapore_game.py`, `game/__init__.py`, `PlayerId`, `RoomState`, `MatchState`, `RoomId`, `model.py`, `test_room_claims.py`, `http_api.py`, `test_room_lobby.py`, `rules_for_id`, `kernel.py`, `SeatId`, `AlternateRules`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Are the 37 inferred relationships involving `RoomState` (e.g. with `qualifying_liability()` and `choose_automated_action()`) actually correct?**
  _`RoomState` has 37 INFERRED edges - model-reasoned connections that need verification._
- **Are the 53 inferred relationships involving `SeatId` (e.g. with `Chow` and `Continue`) actually correct?**
  _`SeatId` has 53 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `RoomRepository` (e.g. with `CorruptRoomStateError` and `PlayerProjectionError`) actually correct?**
  _`RoomRepository` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 50 inferred relationships involving `SingaporeGameEngine` (e.g. with `SingaporeRules` and `DeclareWin`) actually correct?**
  _`SingaporeGameEngine` has 50 INFERRED edges - model-reasoned connections that need verification._