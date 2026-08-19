from __future__ import annotations

import json
import sqlite3
from dataclasses import replace

import pytest

from app.game import (
    AutomatedSeatController,
    ClaimKind,
    CommandId,
    DiscardClaimsPhase,
    DiscardState,
    ExternalSeatController,
    FanAward,
    HandId,
    HandOutcome,
    HandResult,
    HandState,
    MatchId,
    MatchState,
    Payment,
    PendingClaim,
    PhysicalTile,
    PlayerHand,
    PlayerId,
    PlayerRole,
    PlayerState,
    PolicyId,
    RoomId,
    RoomState,
    RoomStatus,
    SeatBalance,
    SeatId,
    SeatState,
    TileDrawn,
    TileFace,
    TileFamily,
    TileId,
    WallState,
    WinSource,
    WindowId,
    standard_seats,
)
from app.persistence import (
    CorruptRoomStateError,
    PlayerProjectionError,
    PlayerRecord,
    PlayerPresenceRecord,
    ProcessedCommandConflictError,
    ProcessedCommandRecord,
    ProjectedAuditEvent,
    RevisionConflictError,
    RoomInitializedAuditPayload,
    RoomCredentialRecord,
    RoomRepository,
    RoomStateCommittedAuditPayload,
    SQLiteSqlExecutor,
    SocketTicketRecord,
    SocketTicketUnavailableError,
    UnsupportedSchemaVersionError,
)
from app.room import RoomOrchestrator


EXPECTED_TABLES = {
    "_sql_schema_migrations",
    "events",
    "player_presence",
    "players",
    "processed_commands",
    "room_credentials",
    "room_presence",
    "room_state",
    "socket_tickets",
}
TOKEN_HASH = "a" * 64
TICKET_HASH = "b" * 64
PRIVATE_SENTINEL = "PRIVATE-CONCEALED-SENTINEL"


def room_state(*, revision: int = 0, updated_at_ms: int = 1_000) -> RoomState:
    return RoomState(
        room_id=RoomId("room-persistence-test"),
        revision=revision,
        seats=standard_seats(),
        created_at_ms=1_000,
        updated_at_ms=updated_at_ms,
    )


def player_room_state(
    *,
    revision: int = 0,
    updated_at_ms: int = 1_000,
    player_id: str = "player-1",
    display_name: str = "East",
) -> RoomState:
    seats = list(standard_seats())
    seats[0] = SeatState(
        seat_id=SeatId("seat-0"),
        slot=0,
        controller=ExternalSeatController(player_id=PlayerId(player_id)),
        occupant_name=display_name,
    )
    player = PlayerState(
        player_id=PlayerId(player_id),
        display_name=display_name,
        role=PlayerRole.HOST,
        ready=False,
        joined_at_ms=1_000,
    )
    return RoomState(
        room_id=RoomId("room-persistence-test"),
        revision=revision,
        status=RoomStatus.CREATED,
        seats=tuple(seats),
        players=(player,),
        created_at_ms=1_000,
        updated_at_ms=updated_at_ms,
    )


def player_record(
    *,
    player_id: str = "player-1",
    display_name: str = "East",
    token_hash: str = TOKEN_HASH,
    auth_generation: int = 0,
    updated_at_ms: int = 1_000,
    left_at_ms: int | None = None,
) -> PlayerRecord:
    return PlayerRecord(
        player_id=player_id,
        seat_id="seat-0",
        display_name=display_name,
        role="HOST",
        controller_json=json.dumps({"type": "external", "playerId": player_id}),
        token_hash=token_hash,
        auth_generation=auth_generation,
        joined_at_ms=1_000,
        updated_at_ms=updated_at_ms,
        left_at_ms=left_at_ms,
    )


def initialized_event(state: RoomState, timestamp: int) -> ProjectedAuditEvent:
    return ProjectedAuditEvent(
        payload=RoomInitializedAuditPayload(
            room_id=str(state.room_id), revision=state.revision
        ),
        created_at_ms=timestamp,
    )


def committed_event(state: RoomState, timestamp: int) -> ProjectedAuditEvent:
    return ProjectedAuditEvent(
        payload=RoomStateCommittedAuditPayload(
            room_id=str(state.room_id),
            previous_revision=state.revision - 1,
            revision=state.revision,
        ),
        created_at_ms=timestamp,
    )


def processed_command(
    *,
    revision: int = 0,
    player_id: str = "player-1",
    command_id: str = "command-1",
) -> ProcessedCommandRecord:
    return ProcessedCommandRecord(
        player_id=player_id,
        command_id=command_id,
        request_fingerprint="sha256:request-one",
        revision=revision,
        result_json=json.dumps({"ok": True, "revision": revision}),
        processed_at_ms=1_100 + revision,
    )


def socket_ticket(
    *,
    ticket_hash: str = TICKET_HASH,
    player_id: str = "player-1",
    auth_generation: int = 0,
) -> SocketTicketRecord:
    return SocketTicketRecord(
        ticket_hash=ticket_hash,
        player_id=player_id,
        auth_generation=auth_generation,
        created_at_ms=1_000,
        expires_at_ms=31_000,
    )


def tile(tile_id: str, rank: int) -> PhysicalTile:
    return PhysicalTile(
        tile_id=TileId(tile_id),
        face=TileFace(family=TileFamily.CHARACTERS, value=rank),
    )


def rich_room_state() -> RoomState:
    seat_ids = tuple(SeatId(f"seat-{slot}") for slot in range(4))
    player = PlayerState(
        player_id=PlayerId("player-1"),
        display_name="East",
        role=PlayerRole.HOST,
        ready=True,
        joined_at_ms=1_000,
    )
    seats = (
        SeatState(
            seat_id=seat_ids[0],
            slot=0,
            controller=ExternalSeatController(player_id=player.player_id),
            occupant_name="East",
        ),
        *(
            SeatState(
                seat_id=seat_ids[slot],
                slot=slot,
                controller=AutomatedSeatController(
                    policy_id=PolicyId(f"random-{slot}")
                ),
                occupant_name=f"Bot {slot}",
            )
            for slot in range(1, 4)
        ),
    )
    payment = Payment(
        sequence=1,
        payer_seat_id=seat_ids[0],
        recipient_seat_id=seat_ids[1],
        amount=2,
        reason="foundation payment sentinel",
    )
    completed_result = HandResult(
        outcome=HandOutcome.WIN,
        winner_seat_id=seat_ids[1],
        provider_seat_id=seat_ids[0],
        win_source=WinSource.DISCARD,
        fan=2,
        fan_awards=(FanAward(name="foundation fan sentinel", fan=2),),
        payments=(payment,),
    )
    hand = HandState(
        hand_id=HandId("hand-active"),
        phase=DiscardClaimsPhase(
            window_id=WindowId("window-claim-sentinel"),
            discard_sequence=1,
            eligible_seat_ids=(seat_ids[1], seat_ids[2]),
        ),
        wall=WallState(
            live_tiles=(tile("wall-live-sentinel", 1),),
            reserve_tiles=(tile("wall-reserve-sentinel", 2),),
        ),
        player_hands=(
            PlayerHand(
                seat_id=seat_ids[0],
                concealed_tiles=(tile(PRIVATE_SENTINEL, 3),),
                initial_tile_ids=(TileId(PRIVATE_SENTINEL),),
            ),
            PlayerHand(
                seat_id=seat_ids[1],
                concealed_tiles=(tile("south-concealed-sentinel", 4),),
            ),
            PlayerHand(seat_id=seat_ids[2]),
            PlayerHand(seat_id=seat_ids[3]),
        ),
        discards=(
            DiscardState(
                sequence=1,
                tile=tile("discard-public-sentinel", 5),
                discarded_by_seat_id=seat_ids[0],
            ),
        ),
        pending_claims=(
            PendingClaim(
                window_id=WindowId("window-claim-sentinel"),
                seat_id=seat_ids[1],
                kind=ClaimKind.PONG,
                tile_ids=(TileId("claim-a-sentinel"), TileId("claim-b-sentinel")),
            ),
        ),
        payments=(payment,),
    )
    match = MatchState(
        match_id=MatchId("match-foundation"),
        dealer_seat_id=seat_ids[0],
        current_hand=hand,
        hand_history=(completed_result,),
        balances=tuple(SeatBalance(seat_id=seat_id) for seat_id in seat_ids),
    )
    return RoomState(
        room_id=RoomId("room-persistence-test"),
        status=RoomStatus.IN_MATCH,
        seats=seats,
        players=(player,),
        match=match,
        created_at_ms=1_000,
        updated_at_ms=1_000,
    )


@pytest.fixture
def database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    yield connection
    connection.close()


@pytest.fixture
def repository(database: sqlite3.Connection) -> RoomRepository:
    result = RoomRepository.from_sqlite(database)
    result.initialize_schema(applied_at_ms=900)
    return result


def scalar(connection: sqlite3.Connection, statement: str) -> object:
    row = connection.execute(statement).fetchone()
    assert row is not None
    return row[0]


def test_schema_has_exact_tables_and_migration_is_idempotent(
    database: sqlite3.Connection,
) -> None:
    repository = RoomRepository.from_sqlite(database)
    repository.initialize_schema(applied_at_ms=900)
    repository.initialize_schema(applied_at_ms=999)

    tables = {
        row[0]
        for row in database.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            """
        )
    }
    assert tables == EXPECTED_TABLES
    assert database.execute(
        "SELECT id, name, applied_at_ms FROM _sql_schema_migrations"
    ).fetchall() == [
        (1, "milestone_1_foundation", 900),
        (2, "milestone_2_room_security", 900),
        (3, "milestone_2_player_presence", 900),
    ]


def test_schema_ignores_cloudflare_runtime_internal_tables(
    database: sqlite3.Connection,
) -> None:
    database.execute("CREATE TABLE _cf_METADATA (key TEXT PRIMARY KEY)")
    database.execute("CREATE TABLE __cf_LEGACY_METADATA (key TEXT PRIMARY KEY)")

    repository = RoomRepository.from_sqlite(database)
    repository.initialize_schema(applied_at_ms=900)
    repository.initialize_schema(applied_at_ms=901)

    assert repository.presence_version() == 0


@pytest.mark.parametrize(
    ("tamper_sql", "message"),
    (
        (
            "UPDATE _sql_schema_migrations SET id = 4 WHERE id = 3",
            "migration history",
        ),
        (
            "UPDATE _sql_schema_migrations SET name = 'forged'",
            "migration history",
        ),
        (
            "DELETE FROM _sql_schema_migrations",
            "recorded migration",
        ),
        (
            "DROP TABLE _sql_schema_migrations",
            "without migration history",
        ),
        (
            "DROP TABLE events",
            "missing=.*events",
        ),
        (
            "CREATE TABLE unexpected_projection (id INTEGER)",
            "unexpected=.*unexpected_projection",
        ),
    ),
)
def test_schema_rejects_tampered_history_or_application_table_set(
    repository: RoomRepository,
    database: sqlite3.Connection,
    tamper_sql: str,
    message: str,
) -> None:
    database.execute(tamper_sql)

    with pytest.raises(UnsupportedSchemaVersionError, match=message):
        repository.initialize_schema(applied_at_ms=999)


def test_durable_storage_adapter_uses_synchronous_sql_contract(
    database: sqlite3.Connection,
) -> None:
    sqlite_executor = SQLiteSqlExecutor(database)

    class DurableStorageFacade:
        sql = sqlite_executor
        transactionSync = sqlite_executor.transaction

    repository = RoomRepository.from_durable_storage(DurableStorageFacade())
    repository.initialize_schema(applied_at_ms=900)
    repository.create_room(room_state())

    assert repository.load_room() == room_state()


def test_schema_create_and_cas_each_use_one_non_nested_transaction(
    database: sqlite3.Connection,
) -> None:
    sqlite_executor = SQLiteSqlExecutor(database)

    class CountingExecutor:
        def __init__(self) -> None:
            self.transaction_calls = 0
            self.depth = 0
            self.maximum_depth = 0

        def exec(self, statement: str, *bindings: object) -> object:
            return sqlite_executor.exec(statement, *bindings)

        def transaction(self, callback):  # type: ignore[no-untyped-def]
            self.transaction_calls += 1

            def observed():  # type: ignore[no-untyped-def]
                self.depth += 1
                self.maximum_depth = max(self.maximum_depth, self.depth)
                try:
                    return callback()
                finally:
                    self.depth -= 1

            return sqlite_executor.transaction(observed)

    executor = CountingExecutor()
    repository = RoomRepository(executor)
    repository.initialize_schema(applied_at_ms=900)
    assert executor.transaction_calls == 1

    initial = room_state()
    repository.create_room(initial)
    assert executor.transaction_calls == 2

    revised_data = initial.model_dump()
    revised_data.update(revision=1, updated_at_ms=1_001)
    repository.compare_and_swap(0, RoomState.model_validate(revised_data))
    assert executor.transaction_calls == 3
    assert executor.maximum_depth == 1


def test_presence_is_revision_neutral_generation_bound_and_reconnect_clears_it(
    repository: RoomRepository,
) -> None:
    state = player_room_state()
    repository.create_room(state, players=(player_record(),))
    assert repository.presence_version() == 0
    disconnected = PlayerPresenceRecord(
        player_id="player-1",
        auth_generation=0,
        disconnected_at_ms=1_100,
        disconnect_expires_at_ms=301_100,
    )

    assert repository.set_player_disconnected(disconnected) is True
    assert repository.presence_version() == 1
    assert repository.load_room() == state
    assert repository.list_player_presence() == (disconnected,)
    assert repository.next_presence_alarm_ms() == 301_100

    # A duplicate close cannot silently extend the grace period.
    assert repository.set_player_disconnected(
        replace(
            disconnected,
            disconnected_at_ms=2_000,
            disconnect_expires_at_ms=302_000,
        )
    ) is False
    assert repository.presence_version() == 1
    assert repository.list_player_presence() == (disconnected,)

    assert repository.set_player_connected("player-1", 1) is False
    assert repository.presence_version() == 1
    assert repository.set_player_connected("player-1", 0) is True
    assert repository.presence_version() == 2
    assert repository.list_player_presence() == ()
    assert repository.next_presence_alarm_ms() is None


def test_presence_mutations_share_room_commit_and_roll_back_atomically(
    repository: RoomRepository,
) -> None:
    initial = player_room_state()
    repository.create_room(
        initial,
        players=(player_record(),),
        processed_commands=(processed_command(),),
    )
    presence = PlayerPresenceRecord(
        player_id="player-1",
        auth_generation=0,
        disconnected_at_ms=1_100,
        disconnect_expires_at_ms=301_100,
    )
    data = initial.model_dump()
    data.update(revision=1, updated_at_ms=1_100)
    revised = RoomState.model_validate(data)
    duplicate = ProcessedCommandRecord(
        player_id="player-1",
        command_id="command-1",
        request_fingerprint="sha256:conflict",
        revision=1,
        result_json='{"ok":false}',
        processed_at_ms=1_100,
    )

    with pytest.raises(ProcessedCommandConflictError):
        repository.commit(
            revised,
            expected_revision=0,
            upsert_player_presence=presence,
            processed_commands=(duplicate,),
        )
    assert repository.load_room() == initial
    assert repository.list_player_presence() == ()
    assert repository.presence_version() == 0

    repository.commit(
        revised,
        expected_revision=0,
        upsert_player_presence=presence,
    )
    assert repository.load_room() == revised
    assert repository.list_player_presence() == (presence,)
    assert repository.presence_version() == 1

    next_data = revised.model_dump()
    next_data.update(revision=2, updated_at_ms=1_200)
    reconnected = RoomState.model_validate(next_data)
    repository.commit(
        reconnected,
        expected_revision=1,
        clear_player_presence=(("player-1", 0),),
    )
    assert repository.load_room() == reconnected
    assert repository.list_player_presence() == ()
    assert repository.presence_version() == 2
    assert repository.set_players_connected((("player-1", 0),)) is False
    assert repository.presence_version() == 2


def test_v2_to_v3_migration_seeds_active_players_with_a_grace_period(
    database: sqlite3.Connection,
) -> None:
    repository = RoomRepository.from_sqlite(database)
    repository.initialize_schema(applied_at_ms=900)
    repository.create_room(
        player_room_state(),
        players=(player_record(),),
    )
    database.execute("DROP TABLE player_presence")
    database.execute("DROP TABLE room_presence")
    database.execute("DELETE FROM _sql_schema_migrations WHERE id = 3")

    repository.initialize_schema(applied_at_ms=5_000)

    assert repository.list_player_presence() == (
        PlayerPresenceRecord(
            player_id="player-1",
            auth_generation=0,
            disconnected_at_ms=5_000,
            disconnect_expires_at_ms=305_000,
        ),
    )
    assert repository.presence_version() == 1
    assert repository.next_presence_alarm_ms() == 305_000


def test_v2_to_v3_migration_freezes_presence_for_finished_rooms(
    database: sqlite3.Connection,
) -> None:
    repository = RoomRepository.from_sqlite(database)
    repository.initialize_schema(applied_at_ms=900)
    data = player_room_state().model_dump()
    data["status"] = RoomStatus.FINISHED
    finished = RoomState.model_validate(data)
    repository.create_room(finished, players=(player_record(),))
    database.execute("DROP TABLE player_presence")
    database.execute("DROP TABLE room_presence")
    database.execute("DELETE FROM _sql_schema_migrations WHERE id = 3")

    repository.initialize_schema(applied_at_ms=5_000)

    assert repository.list_player_presence() == (
        PlayerPresenceRecord(
            player_id="player-1",
            auth_generation=0,
            disconnected_at_ms=5_000,
            disconnect_expires_at_ms=None,
        ),
    )
    assert repository.next_presence_alarm_ms() is None


def test_room_commit_cleans_revoked_presence_and_freezes_match_deadlines(
    repository: RoomRepository,
) -> None:
    initial = player_room_state()
    repository.create_room(initial, players=(player_record(),))
    presence = PlayerPresenceRecord(
        player_id="player-1",
        auth_generation=0,
        disconnected_at_ms=1_100,
        disconnect_expires_at_ms=301_100,
    )
    repository.set_player_disconnected(presence)
    finished_data = initial.model_dump()
    finished_data.update(
        revision=1,
        status=RoomStatus.FINISHED,
        seats=standard_seats(),
        players=(),
        updated_at_ms=1_200,
    )
    finished = RoomState.model_validate(finished_data)
    repository.compare_and_swap(0, finished, players=())
    assert repository.list_player_presence() == ()
    assert repository.presence_version() == 2


def test_in_match_commit_nulls_disconnect_deadlines(
    database: sqlite3.Connection,
) -> None:
    repository = RoomRepository.from_sqlite(database)
    repository.initialize_schema(applied_at_ms=900)
    initial = rich_room_state()
    repository.create_room(initial, players=(player_record(),))
    repository.set_player_disconnected(
        PlayerPresenceRecord(
            player_id="player-1",
            auth_generation=0,
            disconnected_at_ms=1_100,
            disconnect_expires_at_ms=301_100,
        )
    )
    data = initial.model_dump()
    data.update(revision=1, updated_at_ms=1_200)
    revised = RoomState.model_validate(data)
    repository.compare_and_swap(
        0,
        revised,
        players=(player_record(updated_at_ms=1_200),),
    )

    assert repository.list_player_presence() == (
        PlayerPresenceRecord(
            player_id="player-1",
            auth_generation=0,
            disconnected_at_ms=1_100,
            disconnect_expires_at_ms=None,
        ),
    )
    assert repository.next_presence_alarm_ms() is None
    assert repository.presence_version() == 2


def test_create_and_load_round_trip_exact_canonical_state(
    repository: RoomRepository, database: sqlite3.Connection
) -> None:
    initial = rich_room_state()
    repository.create_room(initial, players=(player_record(),))

    loaded = repository.load_room()
    assert loaded == initial
    assert loaded is not initial

    row = database.execute(
        """
        SELECT snapshot_json, ruleset_id, ruleset_version,
               state_schema_version, revision, config_json,
               created_at_ms, updated_at_ms
        FROM room_state
        """
    ).fetchone()
    assert row is not None
    assert row[0] == initial.canonical_json()
    assert row[1:5] == ("singapore", "0.1.0", 2, 0)
    assert json.loads(row[5]) == initial.config.canonical_data()
    assert row[6:] == (1_000, 1_000)
    assert loaded.match is not None
    assert loaded.match.current_hand is not None
    assert isinstance(loaded.match.current_hand.phase, DiscardClaimsPhase)
    assert loaded.match.current_hand.pending_claims == (
        initial.match.current_hand.pending_claims  # type: ignore[union-attr]
    )
    assert loaded.match.current_hand.payments == (
        initial.match.current_hand.payments  # type: ignore[union-attr]
    )
    assert loaded.match.hand_history[0].payments == (
        initial.match.hand_history[0].payments  # type: ignore[union-attr]
    )
    assert PRIVATE_SENTINEL in row[0]


def test_create_and_cas_reject_unvalidated_model_bypasses_before_writes(
    repository: RoomRepository, database: sqlite3.Connection
) -> None:
    valid_initial = room_state()
    constructed = RoomState.model_construct(
        **{**valid_initial.__dict__, "room_id": "room-persistence-test"}
    )
    assert constructed.canonical_json() == valid_initial.canonical_json()

    with pytest.raises(ValueError, match="strict canonical reconstruction"):
        repository.create_room(constructed)
    assert scalar(database, "SELECT COUNT(*) FROM room_state") == 0

    repository.create_room(valid_initial)
    invalid_revision = room_state(revision=1, updated_at_ms=1_001).model_copy(
        update={"status": RoomStatus.IN_MATCH}
    )
    with pytest.raises(ValueError, match="strict domain validation"):
        repository.compare_and_swap(0, invalid_revision)

    assert repository.load_room() == valid_initial
    assert scalar(database, "SELECT COUNT(*) FROM events") == 0


def test_compare_and_swap_persists_projections_and_rejects_stale_revision(
    repository: RoomRepository,
) -> None:
    initial = player_room_state()
    repository.create_room(initial, players=(player_record(),))
    revised = player_room_state(revision=1, updated_at_ms=1_001)

    repository.compare_and_swap(
        0,
        revised,
        events=(committed_event(revised, 1_001),),
        processed_commands=(processed_command(revision=1),),
        socket_tickets=(socket_ticket(),),
    )

    assert repository.load_room() == revised
    assert [event.public_sequence for event in repository.list_events()] == [1]
    assert repository.get_processed_command("player-1", "command-1") == (
        processed_command(revision=1)
    )
    assert repository.get_socket_ticket(TICKET_HASH) == socket_ticket()

    with pytest.raises(RevisionConflictError) as caught:
        repository.compare_and_swap(0, revised)
    assert caught.value.expected_revision == 0
    assert caught.value.actual_revision == 1


def test_failed_projection_write_rolls_back_state_players_events_and_command(
    repository: RoomRepository, database: sqlite3.Connection
) -> None:
    initial = player_room_state()
    repository.create_room(
        initial,
        players=(player_record(),),
        events=(initialized_event(initial, 1_000),),
        processed_commands=(processed_command(),),
    )
    revised = player_room_state(revision=1, updated_at_ms=1_001)
    duplicate_key = ProcessedCommandRecord(
        player_id="player-1",
        command_id="command-1",
        request_fingerprint="sha256:different",
        revision=1,
        result_json='{"ok":false}',
        processed_at_ms=1_101,
    )

    with pytest.raises(ProcessedCommandConflictError):
        repository.compare_and_swap(
            0,
            revised,
            players=(player_record(),),
            events=(committed_event(revised, 1_001),),
            processed_commands=(duplicate_key,),
        )

    assert repository.load_room() == initial
    assert [event.event_type for event in repository.list_events()] == [
        "roomInitialized"
    ]
    assert database.execute("SELECT player_id FROM players").fetchall() == [
        ("player-1",)
    ]
    assert scalar(database, "SELECT COUNT(*) FROM processed_commands") == 1


def test_projection_json_is_canonicalized_before_storage(
    repository: RoomRepository, database: sqlite3.Connection
) -> None:
    initial = player_room_state()
    repository.create_room(
        initial,
        players=(player_record(),),
        events=(initialized_event(initial, 1_000),),
        processed_commands=(processed_command(),),
    )

    assert scalar(database, "SELECT controller_json FROM players") == (
        '{"playerId":"player-1","type":"external"}'
    )
    assert scalar(database, "SELECT event_json FROM events") == (
        '{"revision":0,"roomId":"room-persistence-test","type":"roomInitialized"}'
    )
    assert scalar(database, "SELECT result_json FROM processed_commands") == (
        '{"ok":true,"revision":0}'
    )


def test_audit_boundary_rejects_raw_domain_and_secret_bearing_payloads(
    repository: RoomRepository, database: sqlite3.Connection
) -> None:
    private_domain_event = TileDrawn(
        seat_id=SeatId("seat-0"),
        tile=tile(PRIVATE_SENTINEL, 9),
    )
    with pytest.raises(TypeError, match="allow-listed"):
        ProjectedAuditEvent(  # type: ignore[arg-type]
            payload=private_domain_event,
            created_at_ms=1_000,
        )
    with pytest.raises(TypeError, match="allow-listed"):
        ProjectedAuditEvent(  # type: ignore[arg-type]
            payload={"type": "roomInitialized", "token": PRIVATE_SENTINEL},
            created_at_ms=1_000,
        )

    initial = room_state()
    mismatched = ProjectedAuditEvent(
        payload=RoomInitializedAuditPayload(
            room_id=PRIVATE_SENTINEL,
            revision=0,
        ),
        created_at_ms=1_000,
    )
    with pytest.raises(ValueError, match="identity/revision"):
        repository.create_room(initial, events=(mismatched,))

    assert scalar(database, "SELECT COUNT(*) FROM room_state") == 0
    assert scalar(database, "SELECT COUNT(*) FROM events") == 0


def test_list_events_validates_canonical_room_revision_and_chronology(
    repository: RoomRepository, database: sqlite3.Connection
) -> None:
    initial = room_state()
    repository.create_room(initial, events=(initialized_event(initial, 1_000),))
    revised = room_state(revision=1, updated_at_ms=1_001)
    repository.compare_and_swap(
        0,
        revised,
        events=(committed_event(revised, 1_001),),
    )
    originals = database.execute(
        """
        SELECT public_sequence, revision, event_type, event_json, created_at_ms
        FROM events ORDER BY public_sequence
        """
    ).fetchall()
    assert [event.revision for event in repository.list_events()] == [0, 1]

    wrong_room = json.dumps(
        {"revision": 0, "roomId": "other-room", "type": "roomInitialized"},
        separators=(",", ":"),
        sort_keys=True,
    )
    database.execute(
        "UPDATE events SET event_json = ? WHERE public_sequence = 1",
        (wrong_room,),
    )
    with pytest.raises(CorruptRoomStateError, match="room_id"):
        repository.list_events()

    database.execute("DELETE FROM events")
    database.executemany(
        """
        INSERT INTO events (
            public_sequence, revision, event_type, event_json, created_at_ms
        ) VALUES (?, ?, ?, ?, ?)
        """,
        originals,
    )
    future_payload = json.dumps(
        {
            "previousRevision": 1,
            "revision": 2,
            "roomId": str(revised.room_id),
            "type": "roomStateCommitted",
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    database.execute(
        """
        UPDATE events SET revision = 2, event_json = ?
        WHERE public_sequence = 2
        """,
        (future_payload,),
    )
    with pytest.raises(CorruptRoomStateError, match="exceeds"):
        repository.list_events()

    database.execute("DELETE FROM events")
    database.executemany(
        """
        INSERT INTO events (
            public_sequence, revision, event_type, event_json, created_at_ms
        ) VALUES (?, ?, ?, ?, ?)
        """,
        originals,
    )
    database.execute(
        "UPDATE events SET created_at_ms = 999 WHERE public_sequence = 2"
    )
    with pytest.raises(CorruptRoomStateError, match="timestamps"):
        repository.list_events()


def test_players_projection_must_exactly_match_external_roster(
    repository: RoomRepository, database: sqlite3.Connection
) -> None:
    initial = player_room_state()
    with pytest.raises(PlayerProjectionError, match="exactly match"):
        repository.create_room(initial)
    assert scalar(database, "SELECT COUNT(*) FROM room_state") == 0

    mismatched = replace(player_record(), display_name="Not East")
    with pytest.raises(PlayerProjectionError, match="display_name"):
        repository.create_room(initial, players=(mismatched,))
    assert scalar(database, "SELECT COUNT(*) FROM room_state") == 0

    repository.create_room(initial, players=(player_record(),))
    assert database.execute(
        "SELECT player_id, seat_id, display_name, role FROM players"
    ).fetchall() == [("player-1", "seat-0", "East", "HOST")]


def test_roster_change_revokes_and_retains_historical_player_security_rows(
    repository: RoomRepository, database: sqlite3.Connection
) -> None:
    initial = player_room_state()
    original = player_record(auth_generation=2)
    original_command = processed_command()
    original_ticket = socket_ticket(auth_generation=2)
    repository.create_room(
        initial,
        players=(original,),
        processed_commands=(original_command,),
        socket_tickets=(original_ticket,),
    )
    revised = player_room_state(
        revision=1,
        updated_at_ms=1_001,
        player_id="player-2",
        display_name="New East",
    )

    with pytest.raises(PlayerProjectionError, match="roster changes"):
        repository.compare_and_swap(0, revised)
    assert repository.load_room() == initial
    assert scalar(database, "SELECT player_id FROM players") == "player-1"

    repository.compare_and_swap(
        0,
        revised,
        players=(
            player_record(
                player_id="player-2",
                display_name="New East",
                token_hash="c" * 64,
            ),
        ),
        events=(committed_event(revised, 1_001),),
    )
    assert repository.load_room() == revised
    assert database.execute(
        """
        SELECT player_id, auth_generation, updated_at_ms, left_at_ms
        FROM players ORDER BY player_id
        """
    ).fetchall() == [
        ("player-1", 3, 1_001, 1_001),
        ("player-2", 0, 1_000, None),
    ]
    assert repository.get_processed_command("player-1", "command-1") is None
    assert repository.get_socket_ticket(TICKET_HASH) is None

    revised_again = player_room_state(
        revision=2,
        updated_at_ms=1_002,
        player_id="player-2",
        display_name="New East",
    )
    rotated = player_record(
        player_id="player-2",
        display_name="New East",
        token_hash="d" * 64,
        auth_generation=1,
        updated_at_ms=1_002,
    )
    repository.compare_and_swap(1, revised_again, players=(rotated,))
    assert database.execute(
        "SELECT player_id, left_at_ms FROM players ORDER BY player_id"
    ).fetchall() == [("player-1", 1_001), ("player-2", None)]

    next_state = player_room_state(
        revision=3,
        updated_at_ms=1_003,
        player_id="player-2",
        display_name="New East",
    )
    with pytest.raises(PlayerProjectionError, match="active player"):
        repository.compare_and_swap(
            2,
            next_state,
            players=(rotated,),
            processed_commands=(
                processed_command(
                    revision=3,
                    player_id="player-1",
                    command_id="revoked-command",
                ),
            ),
        )
    with pytest.raises(PlayerProjectionError, match="active player"):
        repository.compare_and_swap(
            2,
            next_state,
            players=(rotated,),
            socket_tickets=(
                socket_ticket(
                    ticket_hash="e" * 64,
                    player_id="player-1",
                    auth_generation=3,
                ),
            ),
        )
    assert repository.load_room() == revised_again


def test_cas_validates_retained_player_projection_before_commit(
    repository: RoomRepository, database: sqlite3.Connection
) -> None:
    initial = player_room_state()
    repository.create_room(initial, players=(player_record(),))
    database.execute("UPDATE players SET display_name = 'Tampered'")
    revised = player_room_state(revision=1, updated_at_ms=1_001)

    with pytest.raises(PlayerProjectionError, match="display_name"):
        repository.compare_and_swap(0, revised)
    assert repository.load_room() == initial


def test_cas_rejects_player_security_regression_and_mismatched_references(
    repository: RoomRepository,
) -> None:
    initial = player_room_state(updated_at_ms=2_000)
    current_player = player_record(auth_generation=2, updated_at_ms=2_000)
    repository.create_room(initial, players=(current_player,))
    revised = player_room_state(revision=1, updated_at_ms=2_001)

    bad_players = (
        replace(current_player, auth_generation=1, updated_at_ms=2_001),
        replace(current_player, updated_at_ms=1_999),
    )
    for bad_player in bad_players:
        with pytest.raises(PlayerProjectionError, match="cannot regress"):
            repository.compare_and_swap(0, revised, players=(bad_player,))
        assert repository.load_room() == initial

    with pytest.raises(PlayerProjectionError, match="auth_generation"):
        repository.compare_and_swap(
            0,
            revised,
            socket_tickets=(socket_ticket(auth_generation=1),),
        )
    with pytest.raises(PlayerProjectionError, match="active player"):
        repository.compare_and_swap(
            0,
            revised,
            processed_commands=(
                processed_command(revision=1, player_id="not-in-room"),
            ),
        )
    assert repository.load_room() == initial


def test_token_and_ticket_hashes_require_sha256_hex_in_python_and_sql(
    repository: RoomRepository, database: sqlite3.Connection
) -> None:
    for invalid_hash in ("a" * 63, "A" * 64, "z" * 64):
        with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
            replace(player_record(), token_hash=invalid_hash)
        with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
            replace(socket_ticket(), ticket_hash=invalid_hash)

    with pytest.raises(sqlite3.IntegrityError):
        database.execute(
            """
            INSERT INTO players (
                player_id, seat_id, display_name, role, controller_json,
                token_hash, auth_generation, joined_at_ms, updated_at_ms, left_at_ms
            ) VALUES ('player-x', 'seat-0', 'X', 'HOST', '{}', 'short', 0, 0, 0, NULL)
            """
        )
    with pytest.raises(sqlite3.IntegrityError):
        database.execute(
            """
            INSERT INTO socket_tickets (
                ticket_hash, player_id, auth_generation, expires_at_ms,
                created_at_ms, consumed_at_ms
            ) VALUES ('UPPERCASE', 'player-x', 0, 1000, 0, NULL)
            """
        )


def test_branded_ids_are_normalized_before_sql_bindings() -> None:
    player = replace(
        player_record(),
        player_id=PlayerId("player-1"),
        seat_id=SeatId("seat-0"),
    )
    command = replace(
        processed_command(),
        player_id=PlayerId("player-1"),
        command_id=CommandId("command-1"),
    )
    payload = RoomInitializedAuditPayload(
        room_id=RoomId("room-persistence-test"),
        revision=0,
    )

    assert type(player.player_id) is str
    assert type(player.seat_id) is str
    assert type(command.player_id) is str
    assert type(command.command_id) is str
    assert type(payload.room_id) is str


def test_cas_freezes_metadata_and_requires_monotonic_timestamps(
    repository: RoomRepository, database: sqlite3.Connection
) -> None:
    initial = room_state(updated_at_ms=2_000)
    repository.create_room(initial)
    revised = room_state(revision=1, updated_at_ms=2_001)
    mutations = {
        "room_id": RoomId("other-room"),
        "ruleset_id": "other-rules",
        "ruleset_version": "99.0.0",
        "state_schema_version": 3,
        "created_at_ms": 999,
    }
    for field, value in mutations.items():
        with pytest.raises(ValueError):
            repository.compare_and_swap(
                0,
                revised.model_copy(update={field: value}),
            )
        assert repository.load_room() == initial

    backwards = room_state(revision=1, updated_at_ms=1_500)
    with pytest.raises(ValueError, match="backwards"):
        repository.compare_and_swap(0, backwards)
    assert repository.load_room() == initial

    database.execute("UPDATE room_state SET ruleset_version = 'corrupt-index'")
    with pytest.raises(CorruptRoomStateError, match="ruleset_version"):
        repository.compare_and_swap(0, revised)


def test_processed_command_reuse_requires_same_request_fingerprint(
    repository: RoomRepository,
) -> None:
    command = processed_command()
    initial = player_room_state()
    repository.create_room(
        initial,
        players=(player_record(),),
        processed_commands=(command,),
    )

    assert repository.reuse_processed_command(
        "player-1",
        "command-1",
        request_fingerprint="sha256:request-one",
    ) == command
    with pytest.raises(ProcessedCommandConflictError):
        repository.reuse_processed_command(
            "player-1",
            "command-1",
            request_fingerprint="sha256:another-request",
        )
    assert (
        repository.reuse_processed_command(
            "player-1", "unknown", request_fingerprint="sha256:new"
        )
        is None
    )


def test_second_orchestrator_reconstructs_from_room_state_only(
    repository: RoomRepository, database: sqlite3.Connection
) -> None:
    initial = rich_room_state()
    first = RoomOrchestrator(repository)
    initialized = first.initialize_room(
        initial.canonical_json(),
        players=(player_record(),),
        events=(initialized_event(initial, 1_000),),
        processed_commands=(processed_command(),),
        socket_tickets=(socket_ticket(),),
    )
    assert initialized.canonical_json() == initial.canonical_json()

    for table in ("players", "events", "processed_commands", "socket_tickets"):
        database.execute(f"DELETE FROM {table}")

    second = RoomOrchestrator(repository)
    reconstructed = second.load_room()
    assert reconstructed is not None
    assert reconstructed.canonical_json() == initial.canonical_json()
    assert second.cached_state == initial
    assert first.cached_state == initial


def test_load_rejects_indexed_metadata_that_disagrees_with_snapshot(
    repository: RoomRepository, database: sqlite3.Connection
) -> None:
    repository.create_room(room_state())
    database.execute("UPDATE room_state SET ruleset_version = '99.0.0'")

    with pytest.raises(CorruptRoomStateError, match="ruleset_version"):
        repository.load_room()


def test_room_invite_credentials_rotate_atomically(
    repository: RoomRepository,
) -> None:
    initial = player_room_state()
    first = RoomCredentialRecord("e" * 64, 0, 1_000, 1_000)
    repository.create_room(
        initial,
        players=(player_record(),),
        room_credentials=first,
    )
    assert repository.load_room_credentials() == first

    revised = player_room_state(revision=1, updated_at_ms=1_001)
    second = RoomCredentialRecord("f" * 64, 1, 1_000, 1_001)
    repository.commit(
        revised,
        expected_revision=0,
        room_credentials=second,
    )
    assert repository.load_room_credentials() == second

    bad = RoomCredentialRecord("1" * 64, 3, 1_000, 1_002)
    next_state = player_room_state(revision=2, updated_at_ms=1_002)
    with pytest.raises(PlayerProjectionError, match="generation"):
        repository.commit(
            next_state,
            expected_revision=1,
            room_credentials=bad,
        )
    assert repository.load_room().revision == 1
    assert repository.load_room_credentials() == second


def test_auth_and_socket_ticket_transactions_are_revision_neutral(
    repository: RoomRepository,
) -> None:
    initial = player_room_state()
    player = player_record()
    repository.create_room(initial, players=(player,))

    assert repository.authenticate_player(TOKEN_HASH) == player
    assert repository.authenticate_player("0" * 64) is None

    ticket = SocketTicketRecord(
        ticket_hash=TICKET_HASH,
        player_id=player.player_id,
        auth_generation=player.auth_generation,
        created_at_ms=1_000,
        expires_at_ms=1_100,
    )
    repository.create_socket_ticket(ticket)
    consumed = repository.consume_socket_ticket(
        TICKET_HASH, consumed_at_ms=1_099
    )
    assert consumed.consumed_at_ms == 1_099
    assert repository.load_room().revision == 0
    with pytest.raises(SocketTicketUnavailableError):
        repository.consume_socket_ticket(TICKET_HASH, consumed_at_ms=1_099)

    expired = SocketTicketRecord(
        ticket_hash="9" * 64,
        player_id=player.player_id,
        auth_generation=player.auth_generation,
        created_at_ms=1_200,
        expires_at_ms=1_300,
    )
    repository.create_socket_ticket(expired)
    with pytest.raises(SocketTicketUnavailableError):
        repository.consume_socket_ticket("9" * 64, consumed_at_ms=1_300)
    assert repository.cleanup_socket_tickets(now_ms=1_300) == 1
    assert repository.load_room().revision == 0
