# Graph Report - ZiMo  (2026-09-29)

## Corpus Check
- 243 files · ~420,380 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 22 file(s) not represented in the graph (top: .toml 5, (none) 5, .css 4)

## Summary
- 2569 nodes · 8470 edges · 95 communities (86 shown, 9 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 537 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Browser Design Capture
- Game Setup Engine
- Lobby State Actions
- Live Session Restoration
- Private Player Projections
- Live Editing Controls
- Gameplay Domain Actions
- Stored State Validation
- Room Rules Configuration
- Screenshot Rendering Library
- Persistence Integration Tests
- Persistence Record Encoding
- Browser Toolbar Controls
- Page Chat Voice
- Bot Policies Randomness
- Game Privacy Invariants
- Worker Integration Tests
- HTTP API Transport
- Tile Catalog Types
- Room Lobby Tests
- Global Browser Toolbar
- Room Command Contracts
- Mahjong Table Rendering
- Durable Room Broadcasting
- Application Page Navigation
- Frontend Package Dependencies
- Live Variant Mounting
- Room Orchestrator Tests
- Lobby Command Presentation
- Room Network Hooks
- Game Claim Resolution
- Worker Runtime Harness
- Persistent Room Records
- SQL Execution Adapters
- Gameplay Action Catalog
- Architecture Boundary Tests
- Durable Room Transport
- Hand State Validation
- Manual Edit Queue
- Atomic Persistence Commits
- Rules Registry Extensibility
- Room Authentication Replay
- Deterministic Deck Fixtures
- Browser Session Storage
- Authoritative View Tests
- Worker Entry Configuration
- Svelte Injection Anchors
- Request Authentication Middleware
- Current ZiMo Architecture
- TypeScript Compiler Settings
- Browser Session Journal
- Redacted Error Observability
- Persistence Error Types
- Room Presence Commands
- Web Interface Guidance
- Browser Annotation Pins
- Browser DOM Utilities
- Workspace Package Scripts
- Lobby Service Errors
- Mahjong Implementation Roadmap
- Live Editing Durability
- Graphify Extraction Workflow
- ZiMo Product Requirements
- Audit Event Serialization
- Room Invitation Interface
- Native Interface Guidance
- Design Artifact Maintenance
- Gameplay Deadline Tests
- Bamboo Tile Artwork
- Character Tile Artwork
- Dot Tile Artwork
- Visual Identity Motion
- Seat Connection Status
- Design Critique Simplification
- Live Scope Filtering
- Design Quality Checks
- Impeccable CLI Bootstrap
- Visual Direction Planning
- Inline Text Editing
- Canonical Game Serialization
- Immutable Random Shuffling
- CORS Error Redaction
- Worker Probe Transport
- Animal Tile Artwork
- Flower Tile Artwork
- Season Tile Artwork
- Wind Tile Artwork
- Dragon Tile Artwork
- Raster Asset Production
- Manual Edit Atomicity
- Canonical Room Serialization
- Concealed Tile Artwork
- Testing Skill License
- Playwright Testing Guidance
- API Package Metadata

## God Nodes (most connected - your core abstractions)
1. `RoomState` - 148 edges
2. `SeatId` - 127 edges
3. `GameModel` - 98 edges
4. `RoomRepository` - 85 edges
5. `PlayerId` - 68 edges
6. `SingaporeGameEngine` - 63 edges
7. `WindowId` - 44 edges
8. `GameConfig` - 40 edges
9. `validate_room()` - 39 edges
10. `HandState` - 38 edges

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

## Communities (95 total, 9 thin omitted)

### Community 0 - "Browser Design Capture"
Cohesion: 0.03
Nodes (146): addManualContextText(), applyGlobalBarLabelState(), applyPlaceholderSizingStyles(), averageRgb01(), bindEditBadgeProxy(), bufferToBase64(), buildCollapsible(), buildColorModels() (+138 more)

### Community 1 - "Game Setup Engine"
Cohesion: 0.07
Nodes (74): KongKind, StrEnum, claim_actions(), concealed_kongs(), DomainAction, Pure claim catalogues and arrival-order-independent resolution., winning_claim(), MatchCompletionRequested (+66 more)

### Community 2 - "Lobby State Actions"
Cohesion: 0.09
Nodes (62): PlayerId, PlayerState, SeatState, _action_id(), _add_bots(), apply_lobby_action(), _can_start(), catalog_lobby_actions() (+54 more)

### Community 3 - "Live Session Restoration"
Cohesion: 0.06
Nodes (86): applyParamDefaults(), applyParamValue(), applyPlaceholderDimensions(), applySavedSessionMeta(), clampVariantIndex(), clearHandled(), clearSession(), closedClipPath() (+78 more)

### Community 4 - "Private Player Projections"
Cohesion: 0.09
Nodes (58): GameModel, Shared modelling and canonical-serialization primitives for the game domain., Immutable, strict base model used by every persisted domain value. Attribute…, Immutable Singapore Mahjong configuration values., Requests for orchestration work emitted by pure game transitions., ProjectionBuilder, Pure, platform-neutral Singapore Mahjong domain foundation., ExternalSeatController (+50 more)

### Community 5 - "Live Editing Controls"
Cohesion: 0.09
Nodes (71): abandonForeignSession(), abortSvelteComponentInjection(), applyEditing(), beginNewLiveConfiguration(), cancelEditing(), cancelEditingToPicking(), cancelInsertConfigure(), cleanup() (+63 more)

### Community 6 - "Gameplay Domain Actions"
Cohesion: 0.11
Nodes (40): Chow, Continue, DeclareWin, Discard, Draw, FinishHand, Kong, parse_domain_action_json() (+32 more)

### Community 7 - "Stored State Validation"
Cohesion: 0.06
Nodes (32): CorruptRoomStateError, ProcessedCommandConflictError, Raised when canonical state and its indexed metadata disagree., Raised when a command id is reused for a different request., PlayerRecord, A projected event after the repository assigns its public sequence., Canonical state together with the duplicated indexed metadata., Authentication data plus a queryable projection of a room player. (+24 more)

### Community 8 - "Room Rules Configuration"
Cohesion: 0.06
Nodes (27): canonical_json(), BaseModel, Canonicalize an arbitrary Pydantic model using the domain convention., Public capabilities of the Singapore game., GameConfig, model_validator, Normalized settings reserved for future Singapore game features., GameEngine (+19 more)

### Community 9 - "Screenshot Rendering Library"
Cohesion: 0.09
Nodes (55): ae(), be(), bt(), Ce(), s(), Ct(), de(), dt() (+47 more)

### Community 10 - "Persistence Integration Tests"
Cohesion: 0.10
Nodes (51): CommandId, Return the four stable empty table slots used by new rooms., standard_seats(), Allow-listed public fact that a canonical room was initialized., RoomInitializedAuditPayload, Adapter for a CPython ``sqlite3.Connection``. The connection is switched to…, SQLiteSqlExecutor, committed_event() (+43 more)

### Community 11 - "Persistence Record Encoding"
Cohesion: 0.11
Nodes (41): Stable persistence failures with application-level meaning., Raised when storage was written by a newer or inconsistent schema., UnsupportedSchemaVersionError, Stable public facade for Mahjong room persistence. The Worker loads this module…, _canonicalize_json_text(), _identity_text(), _now_ms(), _optional_text() (+33 more)

### Community 12 - "Browser Toolbar Controls"
Cohesion: 0.08
Nodes (54): actionLabel(), applyConfigureBarChrome(), bindConfigureCountPillTooltip(), bindConfigureInlineControlHover(), bindConfigureModifierPillHover(), buildConfigureActionControl(), buildConfigureCountControl(), buildConfigureRow() (+46 more)

### Community 13 - "Page Chat Voice"
Cohesion: 0.07
Nodes (54): agentHasWorkInFlight(), armPageChatForTyping(), attachSteerFocusDebug(), attachSteerFocusGuard(), buildSteerProcessingDots(), buildSteerQueueHint(), clearSteerAwaitTimer(), clearSteerFocusRecoverTimer() (+46 more)

### Community 14 - "Bot Policies Randomness"
Cohesion: 0.07
Nodes (31): AutomatedPolicy, AutomatedPolicySelector, choose_automated_action(), NoLegalActionsError, DomainAction, Protocol, RuntimeError, RandomBotPolicy (+23 more)

### Community 15 - "Game Privacy Invariants"
Cohesion: 0.10
Nodes (28): HandResult, MatchId, MatchState, Payment, PendingClaim, PlayerHand, model_validator, Logical face shared by one or more uniquely identified physical tiles. (+20 more)

### Community 16 - "Worker Integration Tests"
Cohesion: 0.06
Nodes (39): devDependencies, vitest, wrangler, ws, engines, node, vitest, name (+31 more)

### Community 17 - "HTTP API Transport"
Cohesion: 0.11
Nodes (45): api_problem_handler(), CommandRequest, create_room(), CreateRoomRequest, _error_response(), _existing_room_stub(), get_events(), get_room() (+37 more)

### Community 18 - "Tile Catalog Types"
Cohesion: 0.05
Nodes (45): ALL_TILE_FACES, animalFiles, animalNames, bonusNumbers, flowerNames, ranks, seasonNames, suitedLabel() (+37 more)

### Community 19 - "Room Lobby Tests"
Cohesion: 0.11
Nodes (11): FixedClock, descriptor_id(), DeterministicCapabilities, DeterministicIds, RoomCommandTests, RoomCreationAndAuthenticationTests, RoomOrchestratorTestCase, RoomPresenceTests (+3 more)

### Community 20 - "Global Browser Toolbar"
Cohesion: 0.08
Nodes (41): agentStatusText(), barPaletteForTheme(), brandMarkSvg(), buildDesignHeader(), buildParamsPanel(), cursorForInsertAxis(), designPanelCss(), detectPageTheme() (+33 more)

### Community 21 - "Room Command Contracts"
Cohesion: 0.12
Nodes (29): canonical_json(), command_fingerprint(), project_event(), CommandResult, Canonical validation, hashing, and projection helpers for room services., stored_command_result(), Room creation, lobby commands, event projection, and socket tickets., Authenticate for transport preflight without projecting a room view. (+21 more)

### Community 22 - "Mahjong Table Rendering"
Cohesion: 0.11
Nodes (32): BonusTiles(), DiscardRiver(), Melds(), occupantName(), OpponentHand(), PhaseStatus(), positions, positionSeats() (+24 more)

### Community 23 - "Durable Room Broadcasting"
Cohesion: 0.11
Nodes (16): _close_socket(), GameRoom, initialize_schema(), Any, Run, then schedule and push every commit before returning., Point the room's sole alarm at its earliest durable deadline., Rediscover live identities without relying on in-memory socket state., Atomically reconcile live sockets restored after a wake or upgrade. (+8 more)

### Community 24 - "Application Page Navigation"
Cohesion: 0.18
Nodes (25): BrandLink(), PageHeading(), PageHeadingProps, AuthenticatedRoom(), LoadingRoom(), JoinRoom(), handleJoin(), LobbyView() (+17 more)

### Community 25 - "Frontend Package Dependencies"
Cohesion: 0.05
Nodes (36): dependencies, react, react-dom, react-router-dom, @supabase/supabase-js, devDependencies, jsdom, @testing-library/dom (+28 more)

### Community 26 - "Live Variant Mounting"
Cohesion: 0.08
Nodes (33): acceptedDomAlreadyClean(), applyOriginalAttrsToSvelteAnchor(), captureAndEmit(), checkpointPayload(), clearHandledWrapperReloadStamp(), commitAcceptedSvelteComponentToDom(), compileShader(), componentModuleCandidates() (+25 more)

### Community 27 - "Room Orchestrator Tests"
Cohesion: 0.11
Nodes (12): Compose command and presence use cases around one repository/cache owner., RoomOrchestrator, MultiplayerClaimTests, DeterministicCapabilities, DeterministicIds, DuplicateFaceRandomSource, MutableClock, Valid deterministic permutation with seat zero and first legal choices. (+4 more)

### Community 28 - "Lobby Command Presentation"
Cohesion: 0.15
Nodes (27): CommandStatus(), CommandStatusProps, CopyState, InvitePanel(), copyInvitation(), InvitePanelProps, LobbyViewProps, ActionEntry() (+19 more)

### Community 29 - "Room Network Hooks"
Cohesion: 0.15
Nodes (22): useRoomCommands(), RETRY_DELAYS_MS, MockWebSocket, useRoomSocket(), UseRoomSocketOptions, apiBaseUrl, ApiError, createRoom() (+14 more)

### Community 30 - "Game Claim Resolution"
Cohesion: 0.12
Nodes (13): PendingDeadline, Canonical room-owned deadline for the active discard window., canonicalize_room_snapshot(), deserialize_room_state(), Canonical room snapshot encoding helpers., serialize_room_state(), ArrangedDeck, ClaimTests (+5 more)

### Community 31 - "Worker Runtime Harness"
Cohesion: 0.09
Nodes (13): _json(), _MutableTestClock, Any, Reconstruct a pending window, then run the real alarm at N-1/N., Make one existing grace deadline due, then run the real alarm path., Run production batch reconciliation after test-controlled eviction., Real time by default, with explicit boundary control for one test RPC., Make the host the dealer and every automated decision reproducible. (+5 more)

### Community 32 - "Persistent Room Records"
Cohesion: 0.15
Nodes (16): PlayerPresenceRecord, ProcessedCommandRecord, ProjectedAuditEvent, An allow-listed, secret-free event ready for public audit storage., Durable disconnected state for one active authentication generation., A durable idempotency result scoped to one room-local player., A hashed, single-use WebSocket ticket projection., Hashed, rotatable room invite capability; raw values never persist. (+8 more)

### Community 33 - "SQL Execution Adapters"
Cohesion: 0.09
Nodes (14): Any, CloudflareSqlExecutor, one(), Any, Protocol, _T, The complete SQL surface used by the room repository. ``exec`` intentionally…, Execute one SQL statement and return a cursor-like value. (+6 more)

### Community 34 - "Gameplay Action Catalog"
Cohesion: 0.15
Nodes (9): _CataloguedGameplayAction, _project_gameplay_event(), DomainAction, DomainEvent, Consume room-owned effects without exposing an intermediate state., Gameplay-side use cases layered on a :class:`RoomKernel`., Idempotently resolve the active window at its exact deadline., RoomGameplay (+1 more)

### Community 35 - "Architecture Boundary Tests"
Cohesion: 0.09
Nodes (14): is_server_ready(), main(), Start one or more servers, wait for them to be ready, run a command, then clean…, Wait for server to be ready by polling the port., PureDomainBoundaryTests, argparse, ast, importlib (+6 more)

### Community 36 - "Durable Room Transport"
Cohesion: 0.21
Nodes (22): WorkerResponse, Cloudflare Durable Object adapter for one authoritative room., _room_view_frame(), Stable Cloudflare Worker and Durable Object export facade., canonical_data(), canonical_json(), method_text(), parse_bearer() (+14 more)

### Community 37 - "Hand State Validation"
Cohesion: 0.13
Nodes (17): _collect_held_tiles(), ConnectionId, DomainId, HandState, Canonical immutable room, match, hand, and tile state., Runtime-branded immutable identity that persists as a JSON string., _validate_claimed_meld_provenance(), _validate_hand_phase_references() (+9 more)

### Community 38 - "Manual Edit Queue"
Cohesion: 0.19
Nodes (24): clearStoredManualApplyState(), fetchPendingCount(), handleManualEditActivity(), hidePendingApplyDock(), manualApplyLoadingText(), manualApplyStateKey(), manualEditEventForCurrentPage(), numberOrNull() (+16 more)

### Community 39 - "Atomic Persistence Commits"
Cohesion: 0.18
Nodes (23): PlayerProjectionError, Raised when authentication projections disagree with canonical state., _canonical_json_value(), commit(), _external_roster_signature(), _merge_player_lifecycle(), Any, Cross-record and canonical snapshot invariants for room persistence. (+15 more)

### Community 40 - "Rules Registry Extensibility"
Cohesion: 0.11
Nodes (10): Validate and return the immutable normalized configuration., rules_for_id(), AlternateEngine, AlternateRules, GameConfig, A registered ruleset controls engine creation and room metadata., test_registered_ruleset_selects_engine_for_new_and_reloaded_rooms(), test_unknown_ruleset_is_rejected() (+2 more)

### Community 41 - "Room Authentication Replay"
Cohesion: 0.11
Nodes (6): capability_hash(), derive_rotated_invite(), CommandResult, Sample the injected clock once for a complete incoming operation., Own the mutable repository cache and atomic commit boundary., RoomKernel

### Community 42 - "Deterministic Deck Fixtures"
Cohesion: 0.10
Nodes (11): AllBonusChainRandomSource, DealerTwoInitialBonusRandomSource, FinalLiveBonusRandomSource, IdentityRandomSource, InitialBonusRandomSource, T, Deal one raw bonus, then provide a regular opposite-end replacement., Put one bonus at the final live position and the other bonuses in reserve. (+3 more)

### Community 43 - "Browser Session Storage"
Cohesion: 0.24
Nodes (19): browserStorage(), clearRoomSession(), InviteTokenRemoval, listStoredRooms(), loadRoomSession(), parsePersistedSession(), publicSession(), readFrom() (+11 more)

### Community 44 - "Authoritative View Tests"
Cohesion: 0.18
Nodes (16): App(), emitSocketView(), openHostLobby(), openMemberLobby(), openPromotedHostLobby(), socketHarness, viewWithDisconnectedMember(), shouldAcceptRoomView() (+8 more)

### Community 45 - "Worker Entry Configuration"
Cohesion: 0.16
Nodes (13): Any, BaseModel, _read_environment_value(), Settings, create_supabase_client(), Create the shared client when both public Supabase values are configured., Default, Any (+5 more)

### Community 46 - "Svelte Injection Anchors"
Cohesion: 0.16
Nodes (19): buildSvelteExpressionTextMap(), buildSveltePropValuesFromLiveElement(), buildSveltePropValuesV2(), cloneWithoutElements(), collectTextNodes(), collectVisibleTexts(), cssEscapeIdent(), elementMatchesOriginalMarkup() (+11 more)

### Community 47 - "Request Authentication Middleware"
Cohesion: 0.15
Nodes (9): ConfigRequest, EnvironmentCORSMiddleware, Any, Resolve the one allowed frontend origin from the Worker environment., Prevent all room responses, including errors, from being cached., Authenticate protected room routes before FastAPI parses their bodies., RoomBearerMiddleware, RoomNoStoreMiddleware (+1 more)

### Community 48 - "Current ZiMo Architecture"
Cohesion: 0.18
Nodes (19): ZiMo web entry shell, Kong/Pong before Chow, Durable three-second claim window, Room-scoped bearer credentials, Cloudflare main-branch deployment, ZiMo Mahjong current implementation, FastAPI Cloudflare Python Worker, GAME_ROOM Durable Object (+11 more)

### Community 49 - "TypeScript Compiler Settings"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, allowSyntheticDefaultImports, esModuleInterop, forceConsistentCasingInFileNames, isolatedModules, jsx, lib (+10 more)

### Community 50 - "Browser Session Journal"
Cohesion: 0.21
Nodes (15): createLiveBrowserSessionState(), clearHandled(), clearScrollY(), clearSession(), isHandled(), loadSession(), markHandled(), nextCheckpointRevision() (+7 more)

### Community 51 - "Redacted Error Observability"
Cohesion: 0.15
Nodes (12): log_unexpected(), Secret-safe structured logging for redacted unexpected failures., Log an allow-listed boundary and exception category, never its values.…, CapturingLogger, test_http_boundary_keeps_redacted_response_and_logs_once(), test_logging_failure_never_replaces_public_error(), test_unexpected_log_is_structured_and_excludes_exception_values(), test_unexpected_log_normalizes_untrusted_operation_and_exception_type() (+4 more)

### Community 52 - "Persistence Error Types"
Cohesion: 0.11
Nodes (14): PersistenceError, RuntimeError, Raised when a Durable Object has already been initialized., Raised when a commit is attempted before room initialization., Raised when an optimistic compare-and-swap revision is stale., Raised when a socket ticket is unknown, expired, stale, or consumed., Base class for repository failures with stable application meaning., RevisionConflictError (+6 more)

### Community 53 - "Room Presence Commands"
Cohesion: 0.17
Nodes (11): Any, require_non_negative_int(), require_text(), CommandResult, Persist a final-socket close and its canonical lobby consequences., Return the earliest pending pre-match disconnect deadline., Idempotently evict due pre-match players that remain offline., Presence-side use cases layered on a :class:`RoomKernel`. (+3 more)

### Community 54 - "Web Interface Guidance"
Cohesion: 0.12
Nodes (17): Impeccable app interface metadata, Content-driven breakpoints, Web adaptation playbook, Audit Health Score, Technical web audit, Scoped visual amplification, Preserve scoped visual system, Actionable error messages (+9 more)

### Community 55 - "Browser Annotation Pins"
Cohesion: 0.20
Nodes (17): beginEditPin(), buildAnnotationsForCapture(), buildPinElement(), cancelEditingPin(), clampPlaceholderSize(), finalizeEditingPin(), initAnnotOverlay(), localCoords() (+9 more)

### Community 56 - "Browser DOM Utilities"
Cohesion: 0.17
Nodes (10): createLiveBrowserDomHelpers(), cssId(), liveUiRoot(), makeFrozenAnchor(), own(), pickable(), rectIsUsableAnchor(), uiAppend() (+2 more)

### Community 57 - "Workspace Package Scripts"
Cohesion: 0.12
Nodes (15): engines, node, name, private, scripts, build:api, build:web, check (+7 more)

### Community 58 - "Lobby Service Errors"
Cohesion: 0.20
Nodes (8): lobby_service_error(), parse_complete_config(), GameConfig, PublicRoomView, Project after the caller has already advanced and sampled time., RuntimeError, Base for every expected, client-safe room-service rejection., RoomServiceError

### Community 59 - "Mahjong Implementation Roadmap"
Cohesion: 0.26
Nodes (14): Bao liabilities and variations planned for Milestone 7, Commit before broadcast, Persisted SeatController descriptors, Nine-milestone Mahjong roadmap, Pure transition engine, Roster and configuration freeze at start, Sixteen dealer rotations planned for Milestone 8, Seat-specific PlayerObservation (+6 more)

### Community 60 - "Live Editing Durability"
Cohesion: 0.19
Nodes (13): Live browser variant editing, Durable live-edit session journal, Live mode project configuration, Onboarding and time to value, Time to first value, Measured frontend optimization, Measure optimize and remeasure, Overdrive technical interface effects (+5 more)

### Community 61 - "Graphify Extraction Workflow"
Cohesion: 0.15
Nodes (13): URL ingestion and file watching, Graph exports and benchmark, Extraction confidence provenance, Semantic extraction schema, GitHub cloning and cross-repository merge, Post-commit graph maintenance, Graph vocabulary expansion and traversal, Constrained vocabulary expansion (+5 more)

### Community 62 - "ZiMo Product Requirements"
Cohesion: 0.18
Nodes (11): Operate mode interface design, Earned familiarity, Owner-selected Mahjong tile artwork, Friends who know Singapore Mahjong, Visible preview capability limits, ZiMo product requirements, Pinned preview ruleset versions, ZiMo Mahjong Milestone 4 preview (+3 more)

### Community 63 - "Audit Event Serialization"
Cohesion: 0.20
Nodes (8): _audit_payload_json(), GameplayAuditPayload, LobbyAuditPayload, _parse_audit_payload(), Allow-listed public lobby fact with canonical, secret-free details., Allow-listed public gameplay fact with no hidden tile identifiers., test_gameplay_audit_allowlist_keeps_only_public_scalar_facts(), SafeAuditPayload

### Community 64 - "Room Invitation Interface"
Cohesion: 0.25
Nodes (9): AuthenticatedRoomProps, JoinRoomProps, RulesCard(), UseInviteCapabilityOptions, UseRoomCommandsOptions, PersistedRoomSession, RoomSession, PlayerRole (+1 more)

### Community 65 - "Native Interface Guidance"
Cohesion: 0.33
Nodes (10): Native adaptation playbook, Native size classes, Android platform guidance, Material Design 3, Technical native audit, Native platform conformance, iOS platform guidance, Apple Human Interface Guidelines (+2 more)

### Community 66 - "Design Artifact Maintenance"
Cohesion: 0.29
Nodes (10): Deprecated craft alias, Documenter fallback role, Shipped artifact as documentation authority, Impeccable artifact maintenance, Schema drift versus truth drift, DESIGN.md normative token schema, Design sidecar schema version 2, Design system documentation (+2 more)

### Community 68 - "Bamboo Tile Artwork"
Cohesion: 0.20
Nodes (10): One bamboo: green bird on a branch, Bamboo suit, Two bamboo: two green vertical stalk symbols, Three bamboo: blue upper stalk and two green lower stalks, Four bamboo: two blue and two green stalk symbols, Five bamboo: pink center stalk with blue and green corners, Six bamboo: two rows of three green stalks, Seven bamboo: pink upper stalk and six green-blue stalks (+2 more)

### Community 69 - "Character Tile Artwork"
Cohesion: 0.20
Nodes (10): One character: blue one numeral above pink wan character, Character suit, Two characters: blue two numeral above pink wan character, Three characters: blue three numeral above pink wan character, Four characters: blue four numeral above pink wan character, Five characters: blue five numeral above pink wan character, Six characters: blue six numeral above pink wan character, Seven characters: blue seven numeral above pink wan character (+2 more)

### Community 70 - "Dot Tile Artwork"
Cohesion: 0.20
Nodes (10): One dot: large concentric blue-green-pink floral medallion, Dot suit, Two dots: green upper and blue lower floral circles, Three dots: blue, pink, green floral circles on a diagonal, Four dots: alternating blue and green floral circles at corners, Five dots: pink center with blue and green corner circles, Six dots: two green and four pink floral circles, Seven dots: three diagonal green and four pink circles (+2 more)

### Community 71 - "Visual Identity Motion"
Cohesion: 0.22
Nodes (9): Apache License 2.0, Apache License 2.0, Frontend Design skill, Subject-specific visual identity, The Elements of Typographic Style, Purposeful animation playbook, Reduced-motion alternatives, Product-specific delight thesis (+1 more)

### Community 72 - "Seat Connection Status"
Cohesion: 0.36
Nodes (7): DisconnectedStatus(), DisconnectedStatusProps, formatCountdown(), remainingDisconnectSeconds(), seatDescription(), SeatList(), PublicSeatView

### Community 73 - "Design Critique Simplification"
Cohesion: 0.25
Nodes (8): Cognitive load assessment, Cowan 2001 working-memory research, Independent design critique, Independent design and detector assessments, Nielsen usability heuristics, Interface simplification, Progressive disclosure, Bounded visual verification

### Community 74 - "Live Scope Filtering"
Cohesion: 0.52
Nodes (6): globToRegex(), matchesScope(), normalizeIgnoreRule(), normalizeIgnoreValue(), pageCandidates(), resolveDetectIgnores()

### Community 75 - "Design Quality Checks"
Cohesion: 0.33
Nodes (6): Craft floor, Craft quality floor, Finish reviewer fallback role, Recapture, rebuild, fix, ship, Immediate and Stop detector tiers, Design detector hooks

### Community 76 - "Impeccable CLI Bootstrap"
Cohesion: 0.60
Nodes (5): impeccable script, check_download(), fetch_url(), probe_ok(), setup_help()

### Community 77 - "Visual Direction Planning"
Cohesion: 0.40
Nodes (5): Direction contract, New visual work direction workflow, Shape design brief discovery, Approved composition spec, Visualize approved composition workflow

### Community 78 - "Inline Text Editing"
Cohesion: 0.40
Nodes (5): collectEditableTextRows(), visit(), enableInlineEdit(), onInlineInput(), wrapMixedContentTextNodes()

### Community 79 - "Canonical Game Serialization"
Cohesion: 0.40
Nodes (3): Any, Return the canonical JSON-ready representation of this model., Serialize with stable key ordering and no insignificant whitespace.

### Community 81 - "CORS Error Redaction"
Cohesion: 0.40
Nodes (4): Keep rejected preflights on the same redacted error contract., SafeCORSMiddleware, CORSMiddleware, Headers

### Community 82 - "Worker Probe Transport"
Cohesion: 0.70
Nodes (4): exactJsonBody(), fetch(), jsonTextResponse(), roomStub()

### Community 83 - "Animal Tile Artwork"
Cohesion: 0.40
Nodes (5): Animal bonus tiles, Cat animal tile: green cat, pink Chinese cat character, blue 1, Centipede animal tile: green segmented insect, pink character, blue 3, Mouse animal tile: green mouse, pink Chinese mouse character, blue 2, Rooster animal tile: green rooster with pink comb, Chinese character, blue 4

### Community 84 - "Flower Tile Artwork"
Cohesion: 0.40
Nodes (5): Bamboo flower tile: green bamboo illustration, blue character, pink 4, Flower bonus tiles, Chrysanthemum flower tile: pink blossom, green leaves, pink 3, Orchid flower tile: green curved plant illustration and pink 2, Plum flower tile: pink blossom, green branches, pink 1

### Community 85 - "Season Tile Artwork"
Cohesion: 0.40
Nodes (5): Autumn season tile: pink autumn character, green foliage, blue 3, Season bonus tiles, Spring season tile: pink spring character and blossom, green leaves, blue 1, Summer season tile: pink summer character and flower, green stems, blue 2, Winter season tile: pink winter character and blossom, green plant, blue 4

### Community 86 - "Wind Tile Artwork"
Cohesion: 0.40
Nodes (5): East wind tile: large blue east Chinese character, Wind honor tiles, North wind tile: large blue north Chinese character, South wind tile: large blue south Chinese character, West wind tile: large blue west Chinese character

### Community 87 - "Dragon Tile Artwork"
Cohesion: 0.50
Nodes (4): Green dragon: large green fa Chinese character, Dragon honor tiles, Red dragon: large pink zhong Chinese character, White dragon: blue double rectangular border with blank center

## Knowledge Gaps
- **200 isolated node(s):** `name`, `version`, `private`, `node`, `build` (+195 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 587 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RoomState` connect `Room Rules Configuration` to `Persistent Room Records`, `Game Setup Engine`, `Lobby State Actions`, `Gameplay Action Catalog`, `Private Player Projections`, `Hand State Validation`, `Gameplay Domain Actions`, `Stored State Validation`, `Atomic Persistence Commits`, `Room Authentication Replay`, `Rules Registry Extensibility`, `Persistence Record Encoding`, `Persistence Integration Tests`, `Bot Policies Randomness`, `Game Privacy Invariants`, `Room Command Contracts`, `Game Claim Resolution`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Why does `RoomRepository` connect `Stored State Validation` to `Persistent Room Records`, `SQL Execution Adapters`, `Atomic Persistence Commits`, `Persistence Integration Tests`, `Persistence Record Encoding`, `Bot Policies Randomness`, `Persistence Error Types`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Why does `RoomOrchestrator` connect `Room Orchestrator Tests` to `Gameplay Action Catalog`, `Gameplay Deadline Tests`, `Durable Room Transport`, `Rules Registry Extensibility`, `Room Authentication Replay`, `Persistence Integration Tests`, `Room Lobby Tests`, `Room Command Contracts`, `Room Presence Commands`, `Durable Room Broadcasting`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `RoomState` (e.g. with `choose_automated_action()` and `_complete_tie()`) actually correct?**
  _`RoomState` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 43 inferred relationships involving `SeatId` (e.g. with `Chow` and `Continue`) actually correct?**
  _`SeatId` has 43 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `RoomRepository` (e.g. with `CorruptRoomStateError` and `PlayerProjectionError`) actually correct?**
  _`RoomRepository` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `PlayerId` (e.g. with `ObservationBuilder` and `ProjectionBuilder`) actually correct?**
  _`PlayerId` has 10 INFERRED edges - model-reasoned connections that need verification._
## Extraction accounting

Semantic extraction used the host session. Token usage was not metered; zero counters indicate unavailable accounting, not zero consumption. All detected documents and images were inspected.

## Graph integrity limitations

The extraction diagnostic found 219 dangling-endpoint edges, 28 self-loop edges, and 505 same-endpoint relationships collapsed by the default undirected graph. No missing-endpoint edges were found. See graph-health.json for the complete diagnostic. Inferred cross-file links are hypotheses, including similarly named session functions in bundled tooling and application code.

## Query benchmark

Graphify measured 128,450 words (approximately 171,266 naive tokens), an average query cost of 24,859 tokens, and a 6.9x reduction. Its benchmark corpus estimate differs from the initial detector estimate of 420,380 words; these are tool estimates, not measured session usage.
