# Graph Report - ZiMo  (2026-09-28)

## Corpus Check
- 195 files · ~420,864 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 22 file(s) not represented in the graph (top: .toml 5, (none) 5, .css 4)

## Summary
- 2699 nodes · 8405 edges · 146 communities (119 shown, 27 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 486 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `da344773`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- live-browser.js
- PlayerId
- claims.py
- resumeSession
- SeatId
- setLiveState
- game/__init__.py
- test_game_setup.py
- persistence/__init__.py
- test_persistence.py
- modern-screenshot.umd.js
- kernel.py
- el
- initPageChat
- test_game_claims.py
- sql.py
- worker.integration.test.mjs
- http_api.py
- GameConfig
- initGlobalBar
- GameRoom
- RoomGameplayTests
- AuthenticatedRoom.tsx
- web/package.json
- LobbyView.tsx
- repository.py
- mountSvelteComponentVariant
- Interface Polish
- test_room_lobby.py
- TableView.tsx
- types.ts
- api.ts
- TestGameRoom
- GameModel
- durable_room.py
- DomainId
- RoomGameplay
- test_room_gameplay.py
- handleManualEditActivity
- CorruptRoomStateError
- session.ts
- engine.py
- RoomKernel
- worker_entry.py
- PlayerRecord
- resolveLiveInjectionAnchor
- Any
- RoomState
- compilerOptions
- createLiveBrowserSessionState
- log_unexpected
- onAnnotDown
- App.test.tsx
- Android platform
- createLiveBrowserDomHelpers
- scripts
- require_non_negative_int
- Nine milestone Mahjong roadmap
- Shape design brief
- Native technical audit
- Graphify incremental updates
- Visualize direction comps
- T
- Q: How does RoomState connect gameplay, privacy, persistence, and recovery?
- PublicRoomView
- Graphify knowledge graph
- Q: Trace exactly what information a bot can see
- Graphify exports
- Semantic extraction schema
- Graphify query traversal
- live-browser-ignores.js
- .canonical_data
- Frontend Design
- Typeset typography
- Graphify ingestion and watching
- impeccable
- Q: Verify bot hidden-information exclusions directly in source and run relevant tests
- Graphify repository merging
- enableInlineEdit
- .canonical_data
- SafeCORSMiddleware
- RoomServiceError
- worker-probe.mjs
- Impeccable
- Interface Performance Optimization
- Apache License 2.0
- Graphify media transcription
- Project graphify rules
- tileCatalog.ts
- AllBonusChainRandomSource
- White dragon tile
- Bamboo flower tile
- Chrysanthemum flower tile
- Orchid flower tile
- Plum flower tile
- Mouse animal tile
- Rooster animal tile
- Autumn season tile
- Spring season tile
- Summer season tile
- Winter season tile
- Five Characters Mahjong Tile
- Six Characters Mahjong Tile
- Seven Characters Mahjong Tile
- Eight Characters Mahjong Tile
- Nine Characters Mahjong Tile
- One Dot Mahjong Tile
- Two Dots Mahjong Tile
- Three Dots Mahjong Tile
- Four Dots Mahjong Tile
- Five Dots Mahjong Tile
- Six Dots Mahjong Tile
- Seven Dots Mahjong Tile
- Eight Dots Mahjong Tile
- Nine Dots Mahjong Tile
- Green Dragon Mahjong Tile
- Red Dragon Mahjong Tile
- East wind tile
- North wind tile
- South wind tile
- West wind tile
- PlayerPresenceRecord
- model_validator
- Asset Producer
- Documenter
- Entry atomicity
- Design Tokens
- Earned Familiarity
- src main.tsx module
- Green tile back
- Bamboo one tile
- Bamboo two tile
- Bamboo three tile
- Alternating bamboo square
- Bamboo five tile
- Bamboo six tile
- Bamboo seven tile
- Bamboo eight tile
- Bamboo nine tile
- Cat animal tile
- Centipede animal tile
- Blue one above pink wan
- Blue two above pink wan
- Blue three above pink wan
- Blue four above pink wan
- mahjong-api

## God Nodes (most connected - your core abstractions)
1. `RoomState` - 142 edges
2. `SeatId` - 127 edges
3. `GameModel` - 98 edges
4. `RoomRepository` - 85 edges
5. `PlayerId` - 68 edges
6. `SingaporeGameEngine` - 62 edges
7. `WindowId` - 44 edges
8. `validate_room()` - 41 edges
9. `HandState` - 38 edges
10. `GameConfig` - 35 edges

## Surprising Connections (you probably didn't know these)
- `Web Application Testing` --semantically_similar_to--> `CPython Pyodide and workerd testing`  [INFERRED] [semantically similar]
  .agents/skills/webapp-testing/SKILL.md → README.md
- `GameRoom Durable Object` --semantically_similar_to--> `GAME_ROOM Durable Object`  [INFERRED] [semantically similar]
  PLAN.md → README.md
- `One hand draw discard preview` --semantically_similar_to--> `Capability gated preview`  [INFERRED] [semantically similar]
  PRODUCT.md → PLAN.md
- `Owner selected mahjong tile artwork` --semantically_similar_to--> `FluffyStuff Riichi Mahjong Tiles`  [INFERRED] [semantically similar]
  PRODUCT.md → THIRD_PARTY_NOTICES.md
- `Canonical room_state snapshot` --semantically_similar_to--> `SQLite room_state snapshot`  [INFERRED] [semantically similar]
  PLAN.md → README.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Server authoritative room stack** — readme_react_cloudflare_pages_frontend, readme_fastapi_python_worker, readme_game_room_durable_object, readme_sqlite_room_state_snapshot, readme_hibernating_websockets [EXTRACTED 1.00]

## Communities (146 total, 27 thin omitted)

### Community 0 - "live-browser.js"
Cohesion: 0.03
Nodes (146): addManualContextText(), applyGlobalBarLabelState(), applyPlaceholderSizingStyles(), averageRgb01(), bindEditBadgeProxy(), bufferToBase64(), buildCollapsible(), buildColorModels() (+138 more)

### Community 1 - "PlayerId"
Cohesion: 0.06
Nodes (68): PlayerId, PlayerState, SeatState, _action_id(), _add_bots(), apply_lobby_action(), _can_start(), catalog_lobby_actions() (+60 more)

### Community 2 - "claims.py"
Cohesion: 0.17
Nodes (16): Pure claim catalogues and arrival-order-independent resolution., Logical face shared by one or more uniquely identified physical tiles., TileFace, TileFamily, canonical_face_counts(), canonical_physical_deck(), canonical_tile_faces(), is_bonus_face() (+8 more)

### Community 3 - "resumeSession"
Cohesion: 0.06
Nodes (86): applyParamDefaults(), applyParamValue(), applyPlaceholderDimensions(), applySavedSessionMeta(), clampVariantIndex(), clearHandled(), clearSession(), closedClipPath() (+78 more)

### Community 4 - "SeatId"
Cohesion: 0.12
Nodes (38): _collect_held_tiles(), DiscardState, FanAward, HandId, HandResult, HandState, MatchId, MatchResult (+30 more)

### Community 5 - "setLiveState"
Cohesion: 0.09
Nodes (71): abandonForeignSession(), abortSvelteComponentInjection(), applyEditing(), beginNewLiveConfiguration(), cancelEditing(), cancelEditingToPicking(), cancelInsertConfigure(), cleanup() (+63 more)

### Community 6 - "game/__init__.py"
Cohesion: 0.06
Nodes (57): Shared modelling and canonical-serialization primitives for the game domain., Public capabilities of the Singapore game., Immutable Singapore Mahjong configuration values., AutomatedPolicy, AutomatedPolicySelector, choose_automated_action(), NoLegalActionsError, DomainAction (+49 more)

### Community 7 - "test_game_setup.py"
Cohesion: 0.10
Nodes (35): ProjectionBuilder, ExternalSeatController, PendingDeadline, PlayerRole, Canonical room-owned deadline for the active discard window., RoomId, SeatBalance, Wind (+27 more)

### Community 8 - "persistence/__init__.py"
Cohesion: 0.10
Nodes (37): Stable public facade for Mahjong room persistence. The Worker loads this module…, _audit_payload_json(), _canonical_json_value(), _canonicalize_json_text(), GameplayAuditPayload, _identity_text(), LobbyAuditPayload, _optional_text() (+29 more)

### Community 9 - "test_persistence.py"
Cohesion: 0.11
Nodes (50): CommandId, Any, Create the schema, returning whether an older room was reset., Synchronous repository for one room per SQL database., RoomRepository, committed_event(), database(), initialized_event() (+42 more)

### Community 10 - "modern-screenshot.umd.js"
Cohesion: 0.09
Nodes (55): ae(), be(), bt(), Ce(), s(), Ct(), de(), dt() (+47 more)

### Community 11 - "kernel.py"
Cohesion: 0.14
Nodes (29): canonical_json(), command_fingerprint(), derive_rotated_invite(), project_event(), CommandResult, Canonical validation, hashing, and projection helpers for room services., require_text(), stored_command_result() (+21 more)

### Community 12 - "el"
Cohesion: 0.08
Nodes (54): actionLabel(), applyConfigureBarChrome(), bindConfigureCountPillTooltip(), bindConfigureInlineControlHover(), bindConfigureModifierPillHover(), buildConfigureActionControl(), buildConfigureCountControl(), buildConfigureRow() (+46 more)

### Community 13 - "initPageChat"
Cohesion: 0.07
Nodes (54): agentHasWorkInFlight(), armPageChatForTyping(), attachSteerFocusDebug(), attachSteerFocusGuard(), buildSteerProcessingDots(), buildSteerQueueHint(), clearSteerAwaitTimer(), clearSteerFocusRecoverTimer() (+46 more)

### Community 14 - "test_game_claims.py"
Cohesion: 0.12
Nodes (13): winning_claim(), PendingClaim, canonicalize_room_snapshot(), deserialize_room_state(), Canonical room snapshot encoding helpers., serialize_room_state(), ArrangedDeck, ClaimTests (+5 more)

### Community 15 - "sql.py"
Cohesion: 0.09
Nodes (24): _now_ms(), application_table_names(), initialize_schema(), migrate(), Application-owned SQLite schema and ordered room migrations., Create the current schema, resetting databases from older releases once., CloudflareSqlExecutor, one() (+16 more)

### Community 16 - "worker.integration.test.mjs"
Cohesion: 0.06
Nodes (39): devDependencies, vitest, wrangler, ws, engines, node, vitest, name (+31 more)

### Community 17 - "http_api.py"
Cohesion: 0.11
Nodes (45): api_problem_handler(), CommandRequest, create_room(), CreateRoomRequest, _error_response(), _existing_room_stub(), get_events(), get_room() (+37 more)

### Community 18 - "GameConfig"
Cohesion: 0.09
Nodes (14): canonical_json(), BaseModel, Canonicalize an arbitrary Pydantic model using the domain convention., GameConfig, model_validator, Normalized settings reserved for future Singapore game features., Validate and return the immutable normalized configuration., Any (+6 more)

### Community 19 - "initGlobalBar"
Cohesion: 0.08
Nodes (41): agentStatusText(), barPaletteForTheme(), brandMarkSvg(), buildDesignHeader(), buildParamsPanel(), cursorForInsertAxis(), designPanelCss(), detectPageTheme() (+33 more)

### Community 20 - "GameRoom"
Cohesion: 0.11
Nodes (16): _close_socket(), GameRoom, initialize_schema(), Any, Run, then schedule and push every commit before returning., Point the room's sole alarm at its earliest durable deadline., Rediscover live identities without relying on in-memory socket state., Atomically reconcile live sockets restored after a wake or upgrade. (+8 more)

### Community 22 - "AuthenticatedRoom.tsx"
Cohesion: 0.14
Nodes (27): App(), BrandLink(), PageHeading(), PageHeadingProps, LoadingRoom(), JoinRoom(), handleJoin(), LobbyView() (+19 more)

### Community 23 - "web/package.json"
Cohesion: 0.05
Nodes (37): dependencies, react, react-dom, react-router-dom, @supabase/supabase-js, devDependencies, jsdom, @testing-library/dom (+29 more)

### Community 24 - "LobbyView.tsx"
Cohesion: 0.14
Nodes (27): CommandStatus(), CommandStatusProps, CopyState, InvitePanel(), copyInvitation(), InvitePanelProps, LobbyViewProps, ActionEntryProps (+19 more)

### Community 25 - "repository.py"
Cohesion: 0.11
Nodes (36): PersistenceError, PlayerProjectionError, ProcessedCommandConflictError, RuntimeError, Stable persistence failures with application-level meaning., Raised when a Durable Object has already been initialized., Raised when a commit is attempted before room initialization., Raised when an optimistic compare-and-swap revision is stale. (+28 more)

### Community 26 - "mountSvelteComponentVariant"
Cohesion: 0.08
Nodes (33): acceptedDomAlreadyClean(), applyOriginalAttrsToSvelteAnchor(), captureAndEmit(), checkpointPayload(), clearHandledWrapperReloadStamp(), commitAcceptedSvelteComponentToDom(), compileShader(), componentModuleCandidates() (+25 more)

### Community 27 - "Interface Polish"
Cohesion: 0.07
Nodes (32): Earned Delight, Emotional Moment, Design Simplification, Progressive Disclosure, Artifact Drift Repair, Schema Drift, DESIGN.md, Design System Documentation (+24 more)

### Community 28 - "test_room_lobby.py"
Cohesion: 0.11
Nodes (11): FixedClock, descriptor_id(), DeterministicCapabilities, DeterministicIds, RoomCommandTests, RoomCreationAndAuthenticationTests, RoomOrchestratorTestCase, RoomPresenceTests (+3 more)

### Community 29 - "TableView.tsx"
Cohesion: 0.11
Nodes (22): BonusTiles(), DiscardRiver(), Melds(), occupantName(), PhaseStatus(), positions, positionSeats(), SeatHeader() (+14 more)

### Community 30 - "types.ts"
Cohesion: 0.07
Nodes (30): BaseSeatView, ClaimKind, CommandResponse, CreateRoomResponse, EventsResponse, FanAward, GameConfig, HandResult (+22 more)

### Community 31 - "api.ts"
Cohesion: 0.16
Nodes (20): useRoomCommands(), RETRY_DELAYS_MS, MockWebSocket, useRoomSocket(), apiBaseUrl, ApiError, createSocketTicket(), ErrorEnvelope (+12 more)

### Community 32 - "TestGameRoom"
Cohesion: 0.09
Nodes (13): _json(), _MutableTestClock, Any, Reconstruct a pending window, then run the real alarm at N-1/N., Make one existing grace deadline due, then run the real alarm path., Run production batch reconciliation after test-controlled eviction., Real time by default, with explicit boundary control for one test RPC., Make the host the dealer and every automated decision reproducible. (+5 more)

### Community 33 - "GameModel"
Cohesion: 0.08
Nodes (68): Chow, Continue, DeclareWin, Discard, Draw, FinishHand, Kong, KongKind (+60 more)

### Community 34 - "durable_room.py"
Cohesion: 0.21
Nodes (22): WorkerResponse, Cloudflare Durable Object adapter for one authoritative room., _room_view_frame(), Stable Cloudflare Worker and Durable Object export facade., canonical_data(), canonical_json(), method_text(), parse_bearer() (+14 more)

### Community 35 - "DomainId"
Cohesion: 0.20
Nodes (5): ConnectionId, DomainId, Runtime-branded immutable identity that persists as a JSON string., CoreSchema, str

### Community 36 - "RoomGameplay"
Cohesion: 0.15
Nodes (9): _CataloguedGameplayAction, _project_gameplay_event(), DomainAction, DomainEvent, Consume room-owned effects without exposing an intermediate state., Gameplay-side use cases layered on a :class:`RoomKernel`., Idempotently resolve the active window at its exact deadline., RoomGameplay (+1 more)

### Community 37 - "test_room_gameplay.py"
Cohesion: 0.10
Nodes (13): Compose command and presence use cases around one repository/cache owner., RoomOrchestrator, MultiplayerClaimTests, DeterministicCapabilities, DeterministicIds, DuplicateFaceRandomSource, MutableClock, Valid deterministic permutation with seat zero and first legal choices. (+5 more)

### Community 38 - "handleManualEditActivity"
Cohesion: 0.19
Nodes (24): clearStoredManualApplyState(), fetchPendingCount(), handleManualEditActivity(), hidePendingApplyDock(), manualApplyLoadingText(), manualApplyStateKey(), manualEditEventForCurrentPage(), numberOrNull() (+16 more)

### Community 39 - "CorruptRoomStateError"
Cohesion: 0.08
Nodes (19): CorruptRoomStateError, Raised when canonical state and its indexed metadata disagree., A projected event after the repository assigns its public sequence., Canonical state together with the duplicated indexed metadata., RoomStateRecord, StoredAuditEvent, Reconstruct the room from ``room_state`` and no auxiliary table., Return a prior result, rejecting command-id reuse with new content. (+11 more)

### Community 40 - "session.ts"
Cohesion: 0.21
Nodes (21): AuthenticatedRoom(), useInviteCapability(), browserStorage(), clearRoomSession(), InviteTokenRemoval, listStoredRooms(), loadRoomSession(), parsePersistedSession() (+13 more)

### Community 41 - "engine.py"
Cohesion: 0.14
Nodes (30): _complete_tie(), finalize_completed_preview(), _first_hand_id(), _GameSetup, IllegalGameActionError, InvalidGameStateError, _opaque_physical_deck(), _player_hand() (+22 more)

### Community 42 - "RoomKernel"
Cohesion: 0.14
Nodes (4): CommandResult, Sample the injected clock once for a complete incoming operation., Own the mutable repository cache and atomic commit boundary., RoomKernel

### Community 43 - "worker_entry.py"
Cohesion: 0.16
Nodes (13): Any, BaseModel, _read_environment_value(), Settings, create_supabase_client(), Create the shared client when both public Supabase values are configured., Default, Any (+5 more)

### Community 44 - "PlayerRecord"
Cohesion: 0.10
Nodes (19): _player_record_from_row(), PlayerRecord, ProcessedCommandRecord, ProjectedAuditEvent, An allow-listed, secret-free event ready for public audit storage., A durable idempotency result scoped to one room-local player., A hashed, single-use WebSocket ticket projection., Authentication data plus a queryable projection of a room player. (+11 more)

### Community 45 - "resolveLiveInjectionAnchor"
Cohesion: 0.16
Nodes (19): buildSvelteExpressionTextMap(), buildSveltePropValuesFromLiveElement(), buildSveltePropValuesV2(), cloneWithoutElements(), collectTextNodes(), collectVisibleTexts(), cssEscapeIdent(), elementMatchesOriginalMarkup() (+11 more)

### Community 46 - "Any"
Cohesion: 0.15
Nodes (9): ConfigRequest, EnvironmentCORSMiddleware, Any, Resolve the one allowed frontend origin from the Worker environment., Prevent all room responses, including errors, from being cached., Authenticate protected room routes before FastAPI parses their bodies., RoomBearerMiddleware, RoomNoStoreMiddleware (+1 more)

### Community 47 - "RoomState"
Cohesion: 0.15
Nodes (13): GameEngine, legal_actions(), ObservationBuilder, DomainAction, Protocol, transition(), RoomState, BrandedIdentityTests (+5 more)

### Community 48 - "compilerOptions"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, allowSyntheticDefaultImports, esModuleInterop, forceConsistentCasingInFileNames, isolatedModules, jsx, lib (+10 more)

### Community 49 - "createLiveBrowserSessionState"
Cohesion: 0.21
Nodes (15): createLiveBrowserSessionState(), clearHandled(), clearScrollY(), clearSession(), isHandled(), loadSession(), markHandled(), nextCheckpointRevision() (+7 more)

### Community 50 - "log_unexpected"
Cohesion: 0.15
Nodes (12): log_unexpected(), Secret-safe structured logging for redacted unexpected failures., Log an allow-listed boundary and exception category, never its values.…, CapturingLogger, test_http_boundary_keeps_redacted_response_and_logs_once(), test_logging_failure_never_replaces_public_error(), test_unexpected_log_is_structured_and_excludes_exception_values(), test_unexpected_log_normalizes_untrusted_operation_and_exception_type() (+4 more)

### Community 51 - "onAnnotDown"
Cohesion: 0.20
Nodes (17): beginEditPin(), buildAnnotationsForCapture(), buildPinElement(), cancelEditingPin(), clampPlaceholderSize(), finalizeEditingPin(), initAnnotOverlay(), localCoords() (+9 more)

### Community 52 - "App.test.tsx"
Cohesion: 0.22
Nodes (13): emitSocketView(), openHostLobby(), openMemberLobby(), openPromotedHostLobby(), socketHarness, viewWithDisconnectedMember(), shouldAcceptRoomView(), useAuthoritativeRoomView() (+5 more)

### Community 53 - "Android platform"
Cohesion: 0.25
Nodes (8): Context appropriate responsive design, Native adaptation, Platform size classes, Web adaptation, Android platform, Material Design 3, Motion thesis, Purposeful animation

### Community 54 - "createLiveBrowserDomHelpers"
Cohesion: 0.17
Nodes (10): createLiveBrowserDomHelpers(), cssId(), liveUiRoot(), makeFrozenAnchor(), own(), pickable(), rectIsUsableAnchor(), uiAppend() (+2 more)

### Community 55 - "scripts"
Cohesion: 0.12
Nodes (15): engines, node, name, private, scripts, build:api, build:web, check (+7 more)

### Community 56 - "require_non_negative_int"
Cohesion: 0.17
Nodes (9): Any, require_non_negative_int(), Persist a final-socket close and its canonical lobby consequences., Return the earliest pending pre-match disconnect deadline., Idempotently evict due pre-match players that remain offline., Presence-side use cases layered on a :class:`RoomKernel`., Reconcile one authenticated socket connection., Atomically reconcile a batch of live sockets and any host handoff. (+1 more)

### Community 57 - "Nine milestone Mahjong roadmap"
Cohesion: 0.05
Nodes (47): Network idle wait, Python Playwright, Rendered DOM reconnaissance, Web Application Testing, is_server_ready(), main(), Start one or more servers, wait for them to be ready, run a command, then clean…, Wait for server to be ready by polling the port. (+39 more)

### Community 58 - "Shape design brief"
Cohesion: 0.33
Nodes (6): Discovery interview, Job and audience, Scope and boundaries, Selected direction, Shape design brief, States and ranges

### Community 59 - "Native technical audit"
Cohesion: 0.25
Nodes (8): Audit Health Score, Native technical audit, Platform Conformance Verdict, Web technical audit, Craft floor, Rendered quality checks, Evidence and fidelity gate, Finish Reviewer

### Community 60 - "Graphify incremental updates"
Cohesion: 0.20
Nodes (10): AST only updates, CLAUDE.md integration, Graphify project integration, Post commit hook, Changed file detection, Cluster only rebuild, Deleted source pruning, Graphify incremental updates (+2 more)

### Community 61 - "Visualize direction comps"
Cohesion: 0.33
Nodes (6): Approved comp, PRODUCT.md and DESIGN.md, Raster plates, Semantic UI controls, Three compositional options, Visualize direction comps

### Community 63 - "Q: How does RoomState connect gameplay, privacy, persistence, and recovery?"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: How does RoomState connect gameplay, privacy, persistence, and recovery?, Source Nodes

### Community 64 - "PublicRoomView"
Cohesion: 0.15
Nodes (16): AuthenticatedRoomProps, JoinRoomProps, DisconnectedStatus(), DisconnectedStatusProps, formatCountdown(), remainingDisconnectSeconds(), seatDescription(), SeatList() (+8 more)

### Community 65 - "Graphify knowledge graph"
Cohesion: 0.25
Nodes (8): Community detection, Graph health diagnostics, Graph report, Graphify knowledge graph, GraphRAG JSON, Interactive HTML, Semantic extraction, Structural AST extraction

### Community 66 - "Q: Trace exactly what information a bot can see"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Trace exactly what information a bot can see, Source Nodes

### Community 67 - "Graphify exports"
Cohesion: 0.29
Nodes (7): FalkorDB, Graphify exports, GraphML, MCP server, Neo4j Cypher, Token reduction benchmark, Wiki export

### Community 68 - "Semantic extraction schema"
Cohesion: 0.29
Nodes (7): AMBIGUOUS confidence, Deterministic node IDs, EXTRACTED confidence, Hyperedges, INFERRED confidence, Semantic extraction schema, Source attribution

### Community 69 - "Graphify query traversal"
Cohesion: 0.29
Nodes (7): Breadth first traversal, Constrained vocabulary expansion, Depth first traversal, Graphify query traversal, Reflections lessons, Saved query feedback, Shortest path

### Community 70 - "live-browser-ignores.js"
Cohesion: 0.52
Nodes (6): globToRegex(), matchesScope(), normalizeIgnoreRule(), normalizeIgnoreValue(), pageCandidates(), resolveDetectIgnores()

### Community 72 - "Frontend Design"
Cohesion: 0.33
Nodes (6): Apache License 2.0, Copyright and patent grants, Frontend Design, Subject grounded visual identity, Interface clarification, Message hierarchy

### Community 73 - "Typeset typography"
Cohesion: 0.33
Nodes (6): Mechanical type scan, Metric compatible fallbacks, Reading measure 45 to 75 characters, Role scale, Typeset typography, Typographic assessment

### Community 74 - "Graphify ingestion and watching"
Cohesion: 0.33
Nodes (6): AST rebuild, Debounced watcher, Graphify ingestion and watching, Markdown conversion, Semantic update flag, URL ingestion

### Community 75 - "impeccable"
Cohesion: 0.60
Nodes (5): impeccable script, check_download(), fetch_url(), probe_ok(), setup_help()

### Community 76 - "Q: Verify bot hidden-information exclusions directly in source and run relevant tests"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Verify bot hidden-information exclusions directly in source and run relevant tests, Source Nodes

### Community 77 - "Graphify repository merging"
Cohesion: 0.40
Nodes (5): Cross repository graph, GitHub clone cache, Graphify repository merging, Per folder extraction, Repository provenance

### Community 78 - "enableInlineEdit"
Cohesion: 0.40
Nodes (5): collectEditableTextRows(), visit(), enableInlineEdit(), onInlineInput(), wrapMixedContentTextNodes()

### Community 79 - ".canonical_data"
Cohesion: 0.40
Nodes (3): Any, Return the canonical JSON-ready representation of this model., Serialize with stable key ordering and no insignificant whitespace.

### Community 80 - "SafeCORSMiddleware"
Cohesion: 0.40
Nodes (4): Keep rejected preflights on the same redacted error contract., SafeCORSMiddleware, CORSMiddleware, Headers

### Community 81 - "RoomServiceError"
Cohesion: 0.12
Nodes (12): capability_hash(), lobby_service_error(), parse_complete_config(), GameConfig, PublicRoomView, Authenticate for transport preflight without projecting a room view., Project after the caller has already advanced and sampled time., Command-side use cases layered on a :class:`RoomKernel`. (+4 more)

### Community 82 - "worker-probe.mjs"
Cohesion: 0.70
Nodes (4): exactJsonBody(), fetch(), jsonTextResponse(), roomStub()

### Community 83 - "Impeccable"
Cohesion: 0.17
Nodes (12): Frontend redesign prompt, Impeccable agent interface, Bolder refinement, Scoped amplification, Colorize, Semantic color roles, Craft deprecated alias, Ordinary visual work routing (+4 more)

### Community 84 - "Interface Performance Optimization"
Cohesion: 0.50
Nodes (4): Core Web Vitals, Interface Performance Optimization, Progressive Enhancement, Technical Interface Enhancement

### Community 85 - "Apache License 2.0"
Cohesion: 0.50
Nodes (4): Apache License 2.0, Copyright license, Patent license, Redistribution notices

### Community 86 - "Graphify media transcription"
Cohesion: 0.50
Nodes (4): Document transcripts, Domain hint prompt, Graphify media transcription, Whisper

### Community 87 - "Project graphify rules"
Cohesion: 0.50
Nodes (4): Graph first codebase navigation, Post edit graph update, Project graphify rules, Wiki navigation

### Community 88 - "tileCatalog.ts"
Cohesion: 0.12
Nodes (22): DiscardTile(), DiscardTileProps, TileBack(), TileFace(), TileFaceProps, ALL_TILE_FACES, animalFiles, animalNames (+14 more)

### Community 89 - "AllBonusChainRandomSource"
Cohesion: 0.10
Nodes (11): AllBonusChainRandomSource, DealerTwoInitialBonusRandomSource, FinalLiveBonusRandomSource, IdentityRandomSource, InitialBonusRandomSource, T, Deal one raw bonus, then provide a regular opposite-end replacement., Put one bonus at the final live position and the other bonuses in reserve. (+3 more)

### Community 90 - "White dragon tile"
Cohesion: 0.50
Nodes (4): Blank central field, Blue geometric frame, Rounded pale tile with beveled border, White dragon tile

### Community 91 - "Bamboo flower tile"
Cohesion: 0.50
Nodes (4): Bamboo flower tile, Pink numeral 4, Rounded pale tile with beveled border, Segmented green bamboo

### Community 92 - "Chrysanthemum flower tile"
Cohesion: 0.50
Nodes (4): Chrysanthemum flower tile, Pink chrysanthemum blossom, Pink numeral 3, Rounded pale tile with beveled border

### Community 93 - "Orchid flower tile"
Cohesion: 0.50
Nodes (4): Green orchid linework, Orchid flower tile, Pink numeral 2, Rounded pale tile with beveled border

### Community 94 - "Plum flower tile"
Cohesion: 0.50
Nodes (4): Pink numeral 1, Pink plum blossom, Plum flower tile, Rounded pale tile with beveled border

### Community 95 - "Mouse animal tile"
Cohesion: 0.50
Nodes (4): Blue numeral 2, Green mouse with spiral tail, Mouse animal tile, Rounded pale tile with beveled border

### Community 96 - "Rooster animal tile"
Cohesion: 0.50
Nodes (4): Blue numeral 4, Green rooster with pink comb, Rooster animal tile, Rounded pale tile with beveled border

### Community 97 - "Autumn season tile"
Cohesion: 0.50
Nodes (4): Autumn season tile, Blue numeral 3, Green foliage and pink circular motif, Rounded pale tile with beveled border

### Community 98 - "Spring season tile"
Cohesion: 0.50
Nodes (4): Blue numeral 1, Pink curled spring blossom, Rounded pale tile with beveled border, Spring season tile

### Community 99 - "Summer season tile"
Cohesion: 0.50
Nodes (4): Blue numeral 2, Pink interlocking floral loops, Rounded pale tile with beveled border, Summer season tile

### Community 100 - "Winter season tile"
Cohesion: 0.50
Nodes (4): Blue numeral 4, Pink flower and sweeping foliage, Rounded pale tile with beveled border, Winter season tile

### Community 101 - "Five Characters Mahjong Tile"
Cohesion: 0.67
Nodes (3): Characters Suit, Five Characters Mahjong Tile, Rounded Beveled Tile Face

### Community 102 - "Six Characters Mahjong Tile"
Cohesion: 0.67
Nodes (3): Characters Suit, Rounded Beveled Tile Face, Six Characters Mahjong Tile

### Community 103 - "Seven Characters Mahjong Tile"
Cohesion: 0.67
Nodes (3): Characters Suit, Rounded Beveled Tile Face, Seven Characters Mahjong Tile

### Community 104 - "Eight Characters Mahjong Tile"
Cohesion: 0.67
Nodes (3): Characters Suit, Eight Characters Mahjong Tile, Rounded Beveled Tile Face

### Community 105 - "Nine Characters Mahjong Tile"
Cohesion: 0.67
Nodes (3): Characters Suit, Nine Characters Mahjong Tile, Rounded Beveled Tile Face

### Community 106 - "One Dot Mahjong Tile"
Cohesion: 0.67
Nodes (3): Dots Suit, One Dot Mahjong Tile, Rounded Beveled Tile Face

### Community 107 - "Two Dots Mahjong Tile"
Cohesion: 0.67
Nodes (3): Dots Suit, Rounded Beveled Tile Face, Two Dots Mahjong Tile

### Community 108 - "Three Dots Mahjong Tile"
Cohesion: 0.67
Nodes (3): Dots Suit, Rounded Beveled Tile Face, Three Dots Mahjong Tile

### Community 109 - "Four Dots Mahjong Tile"
Cohesion: 0.67
Nodes (3): Dots Suit, Four Dots Mahjong Tile, Rounded Beveled Tile Face

### Community 110 - "Five Dots Mahjong Tile"
Cohesion: 0.67
Nodes (3): Dots Suit, Five Dots Mahjong Tile, Rounded Beveled Tile Face

### Community 111 - "Six Dots Mahjong Tile"
Cohesion: 0.67
Nodes (3): Dots Suit, Rounded Beveled Tile Face, Six Dots Mahjong Tile

### Community 112 - "Seven Dots Mahjong Tile"
Cohesion: 0.67
Nodes (3): Dots Suit, Rounded Beveled Tile Face, Seven Dots Mahjong Tile

### Community 113 - "Eight Dots Mahjong Tile"
Cohesion: 0.67
Nodes (3): Dots Suit, Eight Dots Mahjong Tile, Rounded Beveled Tile Face

### Community 114 - "Nine Dots Mahjong Tile"
Cohesion: 0.67
Nodes (3): Dots Suit, Nine Dots Mahjong Tile, Rounded Beveled Tile Face

### Community 115 - "Green Dragon Mahjong Tile"
Cohesion: 0.67
Nodes (3): Dragon Honor Tiles, Green Dragon Mahjong Tile, Rounded Beveled Tile Face

### Community 116 - "Red Dragon Mahjong Tile"
Cohesion: 0.67
Nodes (3): Dragon Honor Tiles, Red Dragon Mahjong Tile, Rounded Beveled Tile Face

### Community 117 - "East wind tile"
Cohesion: 0.67
Nodes (3): Blue East character, East wind tile, Rounded pale tile with beveled border

### Community 118 - "North wind tile"
Cohesion: 0.67
Nodes (3): Blue North character, North wind tile, Rounded pale tile with beveled border

### Community 119 - "South wind tile"
Cohesion: 0.67
Nodes (3): Blue South character, Rounded pale tile with beveled border, South wind tile

### Community 120 - "West wind tile"
Cohesion: 0.67
Nodes (3): Blue West character, Rounded pale tile with beveled border, West wind tile

### Community 121 - "PlayerPresenceRecord"
Cohesion: 0.12
Nodes (12): PlayerPresenceRecord, Durable disconnected state for one active authentication generation., _validate_player_presence(), Apply one public presence change and bump its version at most once., Persist disconnected state for an active authentication generation. The…, Clear durable disconnected state for an active socket identity., Atomically clear disconnected state for active socket identities., Return disconnected state for active players and generations only. (+4 more)

## Knowledge Gaps
- **337 isolated node(s):** `name`, `version`, `private`, `node`, `build` (+332 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 731 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **27 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RoomState` connect `RoomState` to `GameModel`, `PlayerId`, `SeatId`, `RoomGameplay`, `game/__init__.py`, `test_game_setup.py`, `persistence/__init__.py`, `engine.py`, `CorruptRoomStateError`, `kernel.py`, `PlayerRecord`, `RoomKernel`, `test_game_claims.py`, `test_persistence.py`, `RoomServiceError`, `GameConfig`, `repository.py`, `model_validator`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Are the 26 inferred relationships involving `RoomState` (e.g. with `choose_automated_action()` and `_complete_tie()`) actually correct?**
  _`RoomState` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 43 inferred relationships involving `SeatId` (e.g. with `Chow` and `Continue`) actually correct?**
  _`SeatId` has 43 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `RoomRepository` (e.g. with `CorruptRoomStateError` and `PlayerProjectionError`) actually correct?**
  _`RoomRepository` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `PlayerId` (e.g. with `ObservationBuilder` and `ProjectionBuilder`) actually correct?**
  _`PlayerId` has 10 INFERRED edges - model-reasoned connections that need verification._
- **What connects `name`, `version`, `private` to the rest of the system?**
  _337 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `live-browser.js` be split into smaller, more focused modules?**
  _Cohesion score 0.02795638803466592 - nodes in this community are weakly interconnected._