# Graph Report - ZiMo  (2026-09-25)

## Corpus Check
- 239 files · ~419,596 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 22 file(s) not represented in the graph (top: .toml 5, (none) 5, .css 4)

## Summary
- 2682 nodes · 8197 edges · 151 communities (118 shown, 33 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 445 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Browser Design Rendering
- Lobby State Transitions
- Mahjong Turn Engine
- Live Variant Sessions
- Game State Invariants
- Live Editing Controls
- Automated Seat Controllers
- Private Player Observations
- Persistence Validation
- Persistence Integration Tests
- Screenshot Rendering Library
- Room Command Dispatch
- Design Configuration Bar
- Page Chat Interface
- Domain Actions Events
- SQLite Schema Migrations
- Worker Integration Tests
- HTTP Room API
- Singapore Rules Configuration
- Global Design Controls
- Durable Room Lifecycle
- Room Gameplay Tests
- React Page Navigation
- Web Build Dependencies
- Lobby Command Feedback
- Audit Record Validation
- Live Variant Acceptance
- Interface Design Guidance
- Room Command Tests
- Table Interaction Bindings
- Frontend Contract Types
- Room API Networking
- Worker Test Harness
- Pure Domain Interfaces
- Worker Transport Boundaries
- Branded Domain Identities
- Gameplay Action Catalogs
- Tile Rendering Catalog
- Manual Edit Recovery
- Player Presence Persistence
- Browser Room Sessions
- Socket Ticket Authentication
- Room Kernel Security
- Worker Environment Configuration
- Atomic Room Commits
- Svelte Injection Anchors
- HTTP Security Middleware
- Bonus Draw Test Fixtures
- TypeScript Compiler Configuration
- Live Session Storage
- Secret Safe Observability
- Visual Annotation Tools
- Authoritative View Reconciliation
- Platform Adaptation Guidance
- Live Browser DOM
- Workspace Build Scripts
- Package Boundary Tests
- Mahjong Product Roadmap
- Visual Design Discovery
- Current Preview Architecture
- Graphify Incremental Updates
- Frontend Session Contracts
- ZiMo Product Artwork
- Canonical State Recovery
- Lobby Seat Status
- Graphify Extraction Pipeline
- Local Test Servers
- Graphify Export Formats
- Semantic Extraction Schema
- Knowledge Graph Traversal
- Browser Scope Filters
- Deterministic Test Dependencies
- Frontend Design Principles
- Typography Assessment
- Graphify Ingestion Watching
- Impeccable Script Setup
- Web Testing Practices
- Repository Graph Merging
- Inline Text Editing
- Canonical Model Serialization
- CORS Error Handling
- Authenticated Room Views
- Worker Probe Fixtures
- Impeccable Agent Interface
- Interface Performance Guidance
- Apache License Terms
- Media Transcription Pipeline
- Project Graph Navigation
- Browser Test Examples
- Worker Runtime Exports
- White Dragon Artwork
- Bamboo Flower Artwork
- Chrysanthemum Flower Artwork
- Orchid Flower Artwork
- Plum Flower Artwork
- Mouse Tile Artwork
- Rooster Tile Artwork
- Autumn Season Artwork
- Spring Season Artwork
- Summer Season Artwork
- Winter Season Artwork
- Five Characters Artwork
- Six Characters Artwork
- Seven Characters Artwork
- Eight Characters Artwork
- Nine Characters Artwork
- One Dot Artwork
- Two Dots Artwork
- Three Dots Artwork
- Four Dots Artwork
- Five Dots Artwork
- Six Dots Artwork
- Seven Dots Artwork
- Eight Dots Artwork
- Nine Dots Artwork
- Green Dragon Artwork
- Red Dragon Artwork
- East Wind Artwork
- North Wind Artwork
- South Wind Artwork
- West Wind Artwork
- Bolder Design Refinement
- Semantic Color Roles
- Legacy Craft Routing
- Independent Design Critique
- Reference Asset Production
- Design System Documentation
- Manual Edit Atomicity
- Reusable Design Tokens
- Familiar Interface Operation
- Snapshot Version Two
- Snapshot Version Three
- Canonical Data Types
- Web Application Entry
- Green Tile Back
- One Bamboo Artwork
- Two Bamboo Artwork
- Three Bamboo Artwork
- Four Bamboo Artwork
- Five Bamboo Artwork
- Six Bamboo Artwork
- Seven Bamboo Artwork
- Eight Bamboo Artwork
- Nine Bamboo Artwork
- Cat Tile Artwork
- Centipede Tile Artwork
- One Character Artwork
- Two Characters Artwork
- Three Characters Artwork
- Four Characters Artwork
- Mahjong API Package

## God Nodes (most connected - your core abstractions)
1. `RoomState` - 138 edges
2. `SeatId` - 110 edges
3. `GameModel` - 95 edges
4. `RoomRepository` - 87 edges
5. `PlayerId` - 71 edges
6. `MilestoneThreeEngine` - 54 edges
7. `WindowId` - 46 edges
8. `validate_milestone_three_room()` - 38 edges
9. `GameConfig` - 35 edges
10. `GameRoom` - 33 edges

## Surprising Connections (you probably didn't know these)
- `Web Application Testing` --semantically_similar_to--> `CPython Pyodide and workerd testing`  [INFERRED] [semantically similar]
  .agents/skills/webapp-testing/SKILL.md → README.md
- `GameRoom Durable Object` --semantically_similar_to--> `GAME_ROOM Durable Object`  [INFERRED] [semantically similar]
  PLAN.md → README.md
- `Canonical room_state snapshot` --semantically_similar_to--> `SQLite room_state snapshot`  [INFERRED] [semantically similar]
  PLAN.md → README.md
- `One hand draw discard preview` --semantically_similar_to--> `Capability gated preview`  [INFERRED] [semantically similar]
  PRODUCT.md → PLAN.md
- `Owner selected mahjong tile artwork` --semantically_similar_to--> `FluffyStuff Riichi Mahjong Tiles`  [INFERRED] [semantically similar]
  PRODUCT.md → THIRD_PARTY_NOTICES.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Server authoritative room stack** — readme_react_cloudflare_pages_frontend, readme_fastapi_python_worker, readme_game_room_durable_object, readme_sqlite_room_state_snapshot, readme_hibernating_websockets [EXTRACTED 1.00]

## Communities (151 total, 33 thin omitted)

### Community 0 - "Browser Design Rendering"
Cohesion: 0.03
Nodes (146): addManualContextText(), applyGlobalBarLabelState(), applyPlaceholderSizingStyles(), averageRgb01(), bindEditBadgeProxy(), bufferToBase64(), buildCollapsible(), buildColorModels() (+138 more)

### Community 1 - "Lobby State Transitions"
Cohesion: 0.07
Nodes (71): ProjectionBuilder, PlayerId, PlayerState, SeatState, OpaqueActionDescriptor, model_validator, Presentation-only handle resolved to a domain action by orchestration., _action_id() (+63 more)

### Community 2 - "Mahjong Turn Engine"
Cohesion: 0.07
Nodes (66): MatchCompletionRequested, Ask room orchestration to finalize a clock-free completed preview., _complete_tie(), _discard_window_id(), finalize_completed_preview(), _first_hand_id(), IllegalGameActionError, InvalidGameStateError (+58 more)

### Community 3 - "Live Variant Sessions"
Cohesion: 0.06
Nodes (86): applyParamDefaults(), applyParamValue(), applyPlaceholderDimensions(), applySavedSessionMeta(), clampVariantIndex(), clearHandled(), clearSession(), closedClipPath() (+78 more)

### Community 4 - "Game State Invariants"
Cohesion: 0.08
Nodes (47): _collect_held_tiles(), DiscardClaimsPhase, DiscardState, FanAward, HandId, HandResult, HandState, MatchId (+39 more)

### Community 5 - "Live Editing Controls"
Cohesion: 0.09
Nodes (71): abandonForeignSession(), abortSvelteComponentInjection(), applyEditing(), beginNewLiveConfiguration(), cancelEditing(), cancelEditingToPicking(), cancelInsertConfigure(), cleanup() (+63 more)

### Community 6 - "Automated Seat Controllers"
Cohesion: 0.07
Nodes (37): AutomatedPolicy, AutomatedPolicySelector, choose_automated_action(), NoLegalActionsError, DomainAction, Protocol, RuntimeError, RandomBotPolicy (+29 more)

### Community 7 - "Private Player Observations"
Cohesion: 0.08
Nodes (50): capabilities_for_ruleset_version(), Ruleset-versioned public capability metadata., Immutable Singapore Mahjong configuration values., AwaitingDrawPhase, ClaimKind, KongReplacementPhase, KongRobberyPhase, MeldKind (+42 more)

### Community 8 - "Persistence Validation"
Cohesion: 0.10
Nodes (54): PersistenceError, PlayerProjectionError, ProcessedCommandConflictError, RuntimeError, Stable persistence failures with application-level meaning., Raised when a Durable Object has already been initialized., Raised when a commit is attempted before room initialization., Raised when an optimistic compare-and-swap revision is stale. (+46 more)

### Community 9 - "Persistence Integration Tests"
Cohesion: 0.11
Nodes (52): Any, Apply all application SQL migrations exactly once., Synchronous repository for one room per SQL database., RoomRepository, committed_event(), database(), downgrade_stored_snapshot_to_v2(), initialized_event() (+44 more)

### Community 10 - "Screenshot Rendering Library"
Cohesion: 0.09
Nodes (55): ae(), be(), bt(), Ce(), s(), Ct(), de(), dt() (+47 more)

### Community 11 - "Room Command Dispatch"
Cohesion: 0.10
Nodes (37): canonical_json(), command_fingerprint(), derive_rotated_invite(), lobby_service_error(), parse_complete_config(), project_event(), Any, CommandResult (+29 more)

### Community 12 - "Design Configuration Bar"
Cohesion: 0.08
Nodes (54): actionLabel(), applyConfigureBarChrome(), bindConfigureCountPillTooltip(), bindConfigureInlineControlHover(), bindConfigureModifierPillHover(), buildConfigureActionControl(), buildConfigureCountControl(), buildConfigureRow() (+46 more)

### Community 13 - "Page Chat Interface"
Cohesion: 0.07
Nodes (54): agentHasWorkInFlight(), armPageChatForTyping(), attachSteerFocusDebug(), attachSteerFocusGuard(), buildSteerProcessingDots(), buildSteerQueueHint(), clearSteerAwaitTimer(), clearSteerFocusRecoverTimer() (+46 more)

### Community 14 - "Domain Actions Events"
Cohesion: 0.11
Nodes (38): Chow, Continue, DeclareWin, Discard, Draw, Kong, KongKind, parse_domain_action_json() (+30 more)

### Community 15 - "SQLite Schema Migrations"
Cohesion: 0.08
Nodes (33): CorruptRoomStateError, Raised when canonical state and its indexed metadata disagree., Raised when storage was written by a newer or inconsistent schema., UnsupportedSchemaVersionError, _now_ms(), application_table_names(), initialize_schema(), migrate() (+25 more)

### Community 16 - "Worker Integration Tests"
Cohesion: 0.06
Nodes (39): devDependencies, vitest, wrangler, ws, engines, node, vitest, name (+31 more)

### Community 17 - "HTTP Room API"
Cohesion: 0.11
Nodes (45): api_problem_handler(), CommandRequest, create_room(), CreateRoomRequest, _error_response(), _existing_room_stub(), get_events(), get_room() (+37 more)

### Community 18 - "Singapore Rules Configuration"
Cohesion: 0.07
Nodes (21): canonical_json(), BaseModel, Canonicalize an arbitrary Pydantic model using the domain convention., GameConfig, model_validator, The complete normalized configuration shape reserved by the roadmap. Milestone…, Validate and return the immutable normalized configuration., model_validator (+13 more)

### Community 19 - "Global Design Controls"
Cohesion: 0.08
Nodes (41): agentStatusText(), barPaletteForTheme(), brandMarkSvg(), buildDesignHeader(), buildParamsPanel(), cursorForInsertAxis(), designPanelCss(), detectPageTheme() (+33 more)

### Community 20 - "Durable Room Lifecycle"
Cohesion: 0.10
Nodes (17): _close_socket(), GameRoom, initialize_schema(), Any, Run, then schedule and push every commit before returning., Point the room's sole alarm at its earliest durable deadline., Compatibility alias for test-only Milestone 2 probes., Rediscover live identities without relying on in-memory socket state. (+9 more)

### Community 21 - "Room Gameplay Tests"
Cohesion: 0.08
Nodes (16): Compose command and presence use cases around one repository/cache owner., RoomOrchestrator, action_for_slot(), DeterministicCapabilities, DeterministicIds, DuplicateFaceRandomSource, MutableClock, Valid deterministic permutation with seat zero and first legal choices. (+8 more)

### Community 22 - "React Page Navigation"
Cohesion: 0.14
Nodes (26): App(), BrandLink(), PageHeading(), PageHeadingProps, LoadingRoom(), JoinRoom(), handleJoin(), LobbyView() (+18 more)

### Community 23 - "Web Build Dependencies"
Cohesion: 0.05
Nodes (36): dependencies, react, react-dom, react-router-dom, @supabase/supabase-js, devDependencies, jsdom, @testing-library/dom (+28 more)

### Community 24 - "Lobby Command Feedback"
Cohesion: 0.13
Nodes (28): CommandStatus(), CommandStatusProps, CopyState, InvitePanel(), copyInvitation(), InvitePanelProps, LobbyViewProps, ActionEntryProps (+20 more)

### Community 25 - "Audit Record Validation"
Cohesion: 0.10
Nodes (25): _audit_payload_json(), _canonical_json_value(), _canonicalize_json_text(), GameplayAuditPayload, _identity_text(), LobbyAuditPayload, _optional_text(), _parse_audit_payload() (+17 more)

### Community 26 - "Live Variant Acceptance"
Cohesion: 0.08
Nodes (33): acceptedDomAlreadyClean(), applyOriginalAttrsToSvelteAnchor(), captureAndEmit(), checkpointPayload(), clearHandledWrapperReloadStamp(), commitAcceptedSvelteComponentToDom(), compileShader(), componentModuleCandidates() (+25 more)

### Community 27 - "Interface Design Guidance"
Cohesion: 0.07
Nodes (32): Earned Delight, Emotional Moment, Design Simplification, Progressive Disclosure, Artifact Drift Repair, Schema Drift, DESIGN.md, Design System Documentation (+24 more)

### Community 28 - "Room Command Tests"
Cohesion: 0.17
Nodes (7): descriptor_id(), RoomCommandTests, RoomCreationAndAuthenticationTests, RoomOrchestratorTestCase, RoomPresenceTests, RoomTicketsEventsAndAtomicityTests, sha256()

### Community 29 - "Table Interaction Bindings"
Cohesion: 0.11
Nodes (21): BonusTiles(), DiscardRiver(), occupantName(), PhaseStatus(), positions, positionSeats(), SeatHeader(), TablePosition (+13 more)

### Community 30 - "Frontend Contract Types"
Cohesion: 0.07
Nodes (30): BaseSeatView, ClaimKind, CommandResponse, CreateRoomResponse, EventsResponse, FanAward, GameConfig, HandResult (+22 more)

### Community 31 - "Room API Networking"
Cohesion: 0.16
Nodes (20): RETRY_DELAYS_MS, MockWebSocket, useRoomSocket(), apiBaseUrl, ApiError, createRoom(), createSocketTicket(), ErrorEnvelope (+12 more)

### Community 32 - "Worker Test Harness"
Cohesion: 0.09
Nodes (13): _json(), _MutableTestClock, Any, Reconstruct a pending window, then run the real alarm at N-1/N., Make one existing grace deadline due, then run the real alarm path., Run production batch reconciliation after test-controlled eviction., Real time by default, with explicit boundary control for one test RPC., Make the host the dealer and every automated decision reproducible. (+5 more)

### Community 33 - "Pure Domain Interfaces"
Cohesion: 0.14
Nodes (13): GameEngine, GameplayUnavailableError, legal_actions(), MilestoneOneEngine, ObservationBuilder, DomainAction, Protocol, RuntimeError (+5 more)

### Community 34 - "Worker Transport Boundaries"
Cohesion: 0.21
Nodes (22): WorkerResponse, Cloudflare Durable Object adapter for one authoritative room., _room_view_frame(), Stable Cloudflare Worker and Durable Object export facade., canonical_data(), canonical_json(), method_text(), parse_bearer() (+14 more)

### Community 35 - "Branded Domain Identities"
Cohesion: 0.11
Nodes (13): CommandId, ConnectionId, DomainId, ExternalSeatController, Runtime-branded immutable identity that persists as a JSON string., Return the four stable empty table slots used by new rooms., RoomId, standard_seats() (+5 more)

### Community 36 - "Gameplay Action Catalogs"
Cohesion: 0.16
Nodes (9): _CataloguedGameplayAction, _project_gameplay_event(), DomainAction, DomainEvent, Consume room-owned effects without exposing an intermediate state., Gameplay-side use cases layered on a :class:`RoomKernel`., Idempotently resolve the active window at its exact deadline., RoomGameplay (+1 more)

### Community 37 - "Tile Rendering Catalog"
Cohesion: 0.12
Nodes (22): DiscardTile(), DiscardTileProps, TileBack(), TileFace(), TileFaceProps, ALL_TILE_FACES, animalFiles, animalNames (+14 more)

### Community 38 - "Manual Edit Recovery"
Cohesion: 0.19
Nodes (24): clearStoredManualApplyState(), fetchPendingCount(), handleManualEditActivity(), hidePendingApplyDock(), manualApplyLoadingText(), manualApplyStateKey(), manualEditEventForCurrentPage(), numberOrNull() (+16 more)

### Community 39 - "Player Presence Persistence"
Cohesion: 0.11
Nodes (13): _player_presence_from_row(), PlayerPresenceRecord, Durable disconnected state for one active authentication generation., Apply one public presence change and bump its version at most once., Persist disconnected state for an active authentication generation. The…, Clear durable disconnected state for an active socket identity., Atomically clear disconnected state for active socket identities., Return disconnected state for active players and generations only. (+5 more)

### Community 40 - "Browser Room Sessions"
Cohesion: 0.21
Nodes (21): AuthenticatedRoom(), useInviteCapability(), browserStorage(), clearRoomSession(), InviteTokenRemoval, listStoredRooms(), loadRoomSession(), parsePersistedSession() (+13 more)

### Community 41 - "Socket Ticket Authentication"
Cohesion: 0.12
Nodes (11): A hashed, single-use WebSocket ticket projection., _require_sha256_hex(), SocketTicketRecord, _validate_socket_ticket(), Atomically authenticate an active token against canonical membership., Issue a ticket atomically without changing the canonical revision., Atomically consume an unexpired ticket for an active auth generation., Delete expired and consumed ticket rows without advancing revision. (+3 more)

### Community 42 - "Room Kernel Security"
Cohesion: 0.12
Nodes (5): capability_hash(), CommandResult, Sample the injected clock once for a complete incoming operation., Own the mutable repository cache and atomic commit boundary., RoomKernel

### Community 43 - "Worker Environment Configuration"
Cohesion: 0.16
Nodes (13): Any, BaseModel, _read_environment_value(), Settings, create_supabase_client(), Create the shared client when both public Supabase values are configured., Default, Any (+5 more)

### Community 44 - "Atomic Room Commits"
Cohesion: 0.15
Nodes (8): ProcessedCommandRecord, ProjectedAuditEvent, An allow-listed, secret-free event ready for public audit storage., A durable idempotency result scoped to one room-local player., Hashed, rotatable room invite capability; raw values never persist., RoomCredentialRecord, _validate_room_credential(), Keyword-oriented alias for :meth:`compare_and_swap`.

### Community 45 - "Svelte Injection Anchors"
Cohesion: 0.16
Nodes (19): buildSvelteExpressionTextMap(), buildSveltePropValuesFromLiveElement(), buildSveltePropValuesV2(), cloneWithoutElements(), collectTextNodes(), collectVisibleTexts(), cssEscapeIdent(), elementMatchesOriginalMarkup() (+11 more)

### Community 46 - "HTTP Security Middleware"
Cohesion: 0.15
Nodes (9): ConfigRequest, EnvironmentCORSMiddleware, Any, Resolve the one allowed frontend origin from the Worker environment., Prevent all room responses, including errors, from being cached., Authenticate protected room routes before FastAPI parses their bodies., RoomBearerMiddleware, RoomNoStoreMiddleware (+1 more)

### Community 47 - "Bonus Draw Test Fixtures"
Cohesion: 0.12
Nodes (9): AllBonusChainRandomSource, DealerTwoInitialBonusRandomSource, FinalLiveBonusRandomSource, InitialBonusRandomSource, T, Deal one raw bonus, then provide a regular opposite-end replacement., Put one bonus at the final live position and the other bonuses in reserve., Exercise dealer-relative initial exposure and a bonus replacement. (+1 more)

### Community 48 - "TypeScript Compiler Configuration"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, allowSyntheticDefaultImports, esModuleInterop, forceConsistentCasingInFileNames, isolatedModules, jsx, lib (+10 more)

### Community 49 - "Live Session Storage"
Cohesion: 0.21
Nodes (15): createLiveBrowserSessionState(), clearHandled(), clearScrollY(), clearSession(), isHandled(), loadSession(), markHandled(), nextCheckpointRevision() (+7 more)

### Community 50 - "Secret Safe Observability"
Cohesion: 0.15
Nodes (12): log_unexpected(), Secret-safe structured logging for redacted unexpected failures., Log an allow-listed boundary and exception category, never its values.…, CapturingLogger, test_http_boundary_keeps_redacted_response_and_logs_once(), test_logging_failure_never_replaces_public_error(), test_unexpected_log_is_structured_and_excludes_exception_values(), test_unexpected_log_normalizes_untrusted_operation_and_exception_type() (+4 more)

### Community 51 - "Visual Annotation Tools"
Cohesion: 0.20
Nodes (17): beginEditPin(), buildAnnotationsForCapture(), buildPinElement(), cancelEditingPin(), clampPlaceholderSize(), finalizeEditingPin(), initAnnotOverlay(), localCoords() (+9 more)

### Community 52 - "Authoritative View Reconciliation"
Cohesion: 0.22
Nodes (13): emitSocketView(), openHostLobby(), openMemberLobby(), openPromotedHostLobby(), socketHarness, viewWithDisconnectedMember(), shouldAcceptRoomView(), useAuthoritativeRoomView() (+5 more)

### Community 53 - "Platform Adaptation Guidance"
Cohesion: 0.12
Nodes (16): Context appropriate responsive design, Native adaptation, Platform size classes, Web adaptation, Android platform, Material Design 3, Motion thesis, Purposeful animation (+8 more)

### Community 54 - "Live Browser DOM"
Cohesion: 0.17
Nodes (10): createLiveBrowserDomHelpers(), cssId(), liveUiRoot(), makeFrozenAnchor(), own(), pickable(), rectIsUsableAnchor(), uiAppend() (+2 more)

### Community 55 - "Workspace Build Scripts"
Cohesion: 0.12
Nodes (15): engines, node, name, private, scripts, build:api, build:web, check (+7 more)

### Community 56 - "Package Boundary Tests"
Cohesion: 0.16
Nodes (6): PureDomainBoundaryTests, ast, importlib, os, pathlib, sys

### Community 57 - "Mahjong Product Roadmap"
Cohesion: 0.22
Nodes (14): Bao liability, Default fan evaluation, Frozen GameConfig, Full match progression, GameRoom Durable Object, Nine milestone Mahjong roadmap, Opaque action catalogs, PlayerObservation (+6 more)

### Community 58 - "Visual Design Discovery"
Cohesion: 0.17
Nodes (12): Discovery interview, Job and audience, Scope and boundaries, Selected direction, Shape design brief, States and ranges, Approved comp, PRODUCT.md and DESIGN.md (+4 more)

### Community 59 - "Current Preview Architecture"
Cohesion: 0.21
Nodes (12): Canonical room_state snapshot, FastAPI Python Worker, Five minute lobby disconnect removal, GAME_ROOM Durable Object, Hibernating WebSockets, Invitation fragment capability, localStorage room credentials, Milestone 3 implementation (+4 more)

### Community 60 - "Graphify Incremental Updates"
Cohesion: 0.20
Nodes (10): AST only updates, CLAUDE.md integration, Graphify project integration, Post commit hook, Changed file detection, Cluster only rebuild, Deleted source pruning, Graphify incremental updates (+2 more)

### Community 61 - "Frontend Session Contracts"
Cohesion: 0.29
Nodes (9): AuthenticatedRoomProps, JoinRoomProps, UseInviteCapabilityOptions, UseRoomCommandsOptions, UseRoomSocketOptions, PersistedRoomSession, RoomSession, PlayerRole (+1 more)

### Community 62 - "ZiMo Product Artwork"
Cohesion: 0.20
Nodes (10): Capability gated preview, Friends familiar with Singapore Mahjong, One hand draw discard preview, Owner selected mahjong tile artwork, Saved browser room access, ZiMo private Singapore Mahjong, CC0 public domain dedication, FluffyStuff Riichi Mahjong Tiles (+2 more)

### Community 63 - "Canonical State Recovery"
Cohesion: 0.33
Nodes (5): A projected event after the repository assigns its public sequence., StoredAuditEvent, Reconstruct the room from ``room_state`` and no auxiliary table., Validate the public log against canonical room identity and chronology., _validate_stored_event_history()

### Community 64 - "Lobby Seat Status"
Cohesion: 0.33
Nodes (7): DisconnectedStatus(), DisconnectedStatusProps, formatCountdown(), remainingDisconnectSeconds(), seatDescription(), SeatList(), PublicSeatView

### Community 65 - "Graphify Extraction Pipeline"
Cohesion: 0.25
Nodes (8): Community detection, Graph health diagnostics, Graph report, Graphify knowledge graph, GraphRAG JSON, Interactive HTML, Semantic extraction, Structural AST extraction

### Community 66 - "Local Test Servers"
Cohesion: 0.29
Nodes (7): is_server_ready(), main(), Start one or more servers, wait for them to be ready, run a command, then clean…, Wait for server to be ready by polling the port., argparse, socket, subprocess

### Community 67 - "Graphify Export Formats"
Cohesion: 0.29
Nodes (7): FalkorDB, Graphify exports, GraphML, MCP server, Neo4j Cypher, Token reduction benchmark, Wiki export

### Community 68 - "Semantic Extraction Schema"
Cohesion: 0.29
Nodes (7): AMBIGUOUS confidence, Deterministic node IDs, EXTRACTED confidence, Hyperedges, INFERRED confidence, Semantic extraction schema, Source attribution

### Community 69 - "Knowledge Graph Traversal"
Cohesion: 0.29
Nodes (7): Breadth first traversal, Constrained vocabulary expansion, Depth first traversal, Graphify query traversal, Reflections lessons, Saved query feedback, Shortest path

### Community 70 - "Browser Scope Filters"
Cohesion: 0.52
Nodes (6): globToRegex(), matchesScope(), normalizeIgnoreRule(), normalizeIgnoreValue(), pageCandidates(), resolveDetectIgnores()

### Community 72 - "Frontend Design Principles"
Cohesion: 0.33
Nodes (6): Apache License 2.0, Copyright and patent grants, Frontend Design, Subject grounded visual identity, Interface clarification, Message hierarchy

### Community 73 - "Typography Assessment"
Cohesion: 0.33
Nodes (6): Mechanical type scan, Metric compatible fallbacks, Reading measure 45 to 75 characters, Role scale, Typeset typography, Typographic assessment

### Community 74 - "Graphify Ingestion Watching"
Cohesion: 0.33
Nodes (6): AST rebuild, Debounced watcher, Graphify ingestion and watching, Markdown conversion, Semantic update flag, URL ingestion

### Community 75 - "Impeccable Script Setup"
Cohesion: 0.60
Nodes (5): impeccable script, check_download(), fetch_url(), probe_ok(), setup_help()

### Community 76 - "Web Testing Practices"
Cohesion: 0.40
Nodes (5): Network idle wait, Python Playwright, Rendered DOM reconnaissance, Web Application Testing, CPython Pyodide and workerd testing

### Community 77 - "Repository Graph Merging"
Cohesion: 0.40
Nodes (5): Cross repository graph, GitHub clone cache, Graphify repository merging, Per folder extraction, Repository provenance

### Community 78 - "Inline Text Editing"
Cohesion: 0.40
Nodes (5): collectEditableTextRows(), visit(), enableInlineEdit(), onInlineInput(), wrapMixedContentTextNodes()

### Community 79 - "Canonical Model Serialization"
Cohesion: 0.40
Nodes (3): Any, Return the canonical JSON-ready representation of this model., Serialize with stable key ordering and no insignificant whitespace.

### Community 80 - "CORS Error Handling"
Cohesion: 0.40
Nodes (4): Keep rejected preflights on the same redacted error contract., SafeCORSMiddleware, CORSMiddleware, Headers

### Community 82 - "Worker Probe Fixtures"
Cohesion: 0.70
Nodes (4): exactJsonBody(), fetch(), jsonTextResponse(), roomStub()

### Community 83 - "Impeccable Agent Interface"
Cohesion: 0.50
Nodes (4): Frontend redesign prompt, Impeccable agent interface, Frontend design workflow, Impeccable

### Community 84 - "Interface Performance Guidance"
Cohesion: 0.50
Nodes (4): Core Web Vitals, Interface Performance Optimization, Progressive Enhancement, Technical Interface Enhancement

### Community 85 - "Apache License Terms"
Cohesion: 0.50
Nodes (4): Apache License 2.0, Copyright license, Patent license, Redistribution notices

### Community 86 - "Media Transcription Pipeline"
Cohesion: 0.50
Nodes (4): Document transcripts, Domain hint prompt, Graphify media transcription, Whisper

### Community 87 - "Project Graph Navigation"
Cohesion: 0.50
Nodes (4): Graph first codebase navigation, Post edit graph update, Project graphify rules, Wiki navigation

### Community 89 - "Worker Runtime Exports"
Cohesion: 0.50
Nodes (3): Test-only Python Worker exports for Durable Object storage acceptance tests.…, main, time

### Community 90 - "White Dragon Artwork"
Cohesion: 0.50
Nodes (4): Blank central field, Blue geometric frame, Rounded pale tile with beveled border, White dragon tile

### Community 91 - "Bamboo Flower Artwork"
Cohesion: 0.50
Nodes (4): Bamboo flower tile, Pink numeral 4, Rounded pale tile with beveled border, Segmented green bamboo

### Community 92 - "Chrysanthemum Flower Artwork"
Cohesion: 0.50
Nodes (4): Chrysanthemum flower tile, Pink chrysanthemum blossom, Pink numeral 3, Rounded pale tile with beveled border

### Community 93 - "Orchid Flower Artwork"
Cohesion: 0.50
Nodes (4): Green orchid linework, Orchid flower tile, Pink numeral 2, Rounded pale tile with beveled border

### Community 94 - "Plum Flower Artwork"
Cohesion: 0.50
Nodes (4): Pink numeral 1, Pink plum blossom, Plum flower tile, Rounded pale tile with beveled border

### Community 95 - "Mouse Tile Artwork"
Cohesion: 0.50
Nodes (4): Blue numeral 2, Green mouse with spiral tail, Mouse animal tile, Rounded pale tile with beveled border

### Community 96 - "Rooster Tile Artwork"
Cohesion: 0.50
Nodes (4): Blue numeral 4, Green rooster with pink comb, Rooster animal tile, Rounded pale tile with beveled border

### Community 97 - "Autumn Season Artwork"
Cohesion: 0.50
Nodes (4): Autumn season tile, Blue numeral 3, Green foliage and pink circular motif, Rounded pale tile with beveled border

### Community 98 - "Spring Season Artwork"
Cohesion: 0.50
Nodes (4): Blue numeral 1, Pink curled spring blossom, Rounded pale tile with beveled border, Spring season tile

### Community 99 - "Summer Season Artwork"
Cohesion: 0.50
Nodes (4): Blue numeral 2, Pink interlocking floral loops, Rounded pale tile with beveled border, Summer season tile

### Community 100 - "Winter Season Artwork"
Cohesion: 0.50
Nodes (4): Blue numeral 4, Pink flower and sweeping foliage, Rounded pale tile with beveled border, Winter season tile

### Community 101 - "Five Characters Artwork"
Cohesion: 0.67
Nodes (3): Characters Suit, Five Characters Mahjong Tile, Rounded Beveled Tile Face

### Community 102 - "Six Characters Artwork"
Cohesion: 0.67
Nodes (3): Characters Suit, Rounded Beveled Tile Face, Six Characters Mahjong Tile

### Community 103 - "Seven Characters Artwork"
Cohesion: 0.67
Nodes (3): Characters Suit, Rounded Beveled Tile Face, Seven Characters Mahjong Tile

### Community 104 - "Eight Characters Artwork"
Cohesion: 0.67
Nodes (3): Characters Suit, Eight Characters Mahjong Tile, Rounded Beveled Tile Face

### Community 105 - "Nine Characters Artwork"
Cohesion: 0.67
Nodes (3): Characters Suit, Nine Characters Mahjong Tile, Rounded Beveled Tile Face

### Community 106 - "One Dot Artwork"
Cohesion: 0.67
Nodes (3): Dots Suit, One Dot Mahjong Tile, Rounded Beveled Tile Face

### Community 107 - "Two Dots Artwork"
Cohesion: 0.67
Nodes (3): Dots Suit, Rounded Beveled Tile Face, Two Dots Mahjong Tile

### Community 108 - "Three Dots Artwork"
Cohesion: 0.67
Nodes (3): Dots Suit, Rounded Beveled Tile Face, Three Dots Mahjong Tile

### Community 109 - "Four Dots Artwork"
Cohesion: 0.67
Nodes (3): Dots Suit, Four Dots Mahjong Tile, Rounded Beveled Tile Face

### Community 110 - "Five Dots Artwork"
Cohesion: 0.67
Nodes (3): Dots Suit, Five Dots Mahjong Tile, Rounded Beveled Tile Face

### Community 111 - "Six Dots Artwork"
Cohesion: 0.67
Nodes (3): Dots Suit, Rounded Beveled Tile Face, Six Dots Mahjong Tile

### Community 112 - "Seven Dots Artwork"
Cohesion: 0.67
Nodes (3): Dots Suit, Rounded Beveled Tile Face, Seven Dots Mahjong Tile

### Community 113 - "Eight Dots Artwork"
Cohesion: 0.67
Nodes (3): Dots Suit, Eight Dots Mahjong Tile, Rounded Beveled Tile Face

### Community 114 - "Nine Dots Artwork"
Cohesion: 0.67
Nodes (3): Dots Suit, Nine Dots Mahjong Tile, Rounded Beveled Tile Face

### Community 115 - "Green Dragon Artwork"
Cohesion: 0.67
Nodes (3): Dragon Honor Tiles, Green Dragon Mahjong Tile, Rounded Beveled Tile Face

### Community 116 - "Red Dragon Artwork"
Cohesion: 0.67
Nodes (3): Dragon Honor Tiles, Red Dragon Mahjong Tile, Rounded Beveled Tile Face

### Community 117 - "East Wind Artwork"
Cohesion: 0.67
Nodes (3): Blue East character, East wind tile, Rounded pale tile with beveled border

### Community 118 - "North Wind Artwork"
Cohesion: 0.67
Nodes (3): Blue North character, North wind tile, Rounded pale tile with beveled border

### Community 119 - "South Wind Artwork"
Cohesion: 0.67
Nodes (3): Blue South character, Rounded pale tile with beveled border, South wind tile

### Community 120 - "West Wind Artwork"
Cohesion: 0.67
Nodes (3): Blue West character, Rounded pale tile with beveled border, West wind tile

## Knowledge Gaps
- **332 isolated node(s):** `name`, `version`, `private`, `node`, `build` (+327 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 723 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **33 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RoomState` connect `Pure Domain Interfaces` to `Lobby State Transitions`, `Mahjong Turn Engine`, `Branded Domain Identities`, `Game State Invariants`, `Gameplay Action Catalogs`, `Automated Seat Controllers`, `Private Player Observations`, `Persistence Validation`, `Persistence Integration Tests`, `Room Kernel Security`, `Room Command Dispatch`, `Atomic Room Commits`, `Domain Actions Events`, `SQLite Schema Migrations`, `Singapore Rules Configuration`, `Audit Record Validation`, `Canonical State Recovery`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Why does `Web Application Testing` connect `Web Testing Practices` to `Local Test Servers`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Why does `CPython Pyodide and workerd testing` connect `Web Testing Practices` to `Current Preview Architecture`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Are the 26 inferred relationships involving `RoomState` (e.g. with `choose_automated_action()` and `_complete_tie()`) actually correct?**
  _`RoomState` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 38 inferred relationships involving `SeatId` (e.g. with `Chow` and `Continue`) actually correct?**
  _`SeatId` has 38 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `RoomRepository` (e.g. with `CorruptRoomStateError` and `PlayerProjectionError`) actually correct?**
  _`RoomRepository` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `PlayerId` (e.g. with `ObservationBuilder` and `ProjectionBuilder`) actually correct?**
  _`PlayerId` has 10 INFERRED edges - model-reasoned connections that need verification._
## Token Accounting Note

Semantic extraction used host-session agents. Actual agent token usage is unavailable through this tool interface; the reported zero counters are placeholders, not a claim of zero token use. AST extraction uses no LLM tokens.

## Graph Health Warning

Read-only extraction diagnostics found 215 dangling-endpoint edges, 30 self-loops, and 479 relationships collapsed in the undirected representation (469 in a directed representation). No missing-endpoint edges. The graph remains usable but may be incomplete; see graph-health.json for full counts.
