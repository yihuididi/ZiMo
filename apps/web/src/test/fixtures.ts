import type {
  OpaqueActionDescriptor,
  PublicRoomView,
  PublicTileView,
  TileFace,
} from "../lib/types";

export function roomView(
  overrides: Partial<PublicRoomView> = {},
): PublicRoomView {
  return {
    apiVersion: "1",
    roomId: "room-a",
    revision: 7,
    presenceVersion: 0,
    status: "WAITING_FOR_PLAYERS",
    rulesetId: "singapore",
    rulesetVersion: "0.1.0",
    stateSchemaVersion: 2,
    capabilities: [
      "multiplayerLobby",
      "roomEvents",
      "hibernatingWebSockets",
    ],
    config: {
      shooterMode: false,
      minimumFan: 1,
      maximumFan: 5,
      payoutTable: [1, 2, 4, 8, 16, 32],
      kongOnePayment: 2,
      kongThreePayment: 2,
      completeAnimalSetPayment: 4,
      completeFlowerSetPayment: 4,
      completeSeasonSetPayment: 4,
      animalPairPayment: 2,
      flowerSeasonPairPayment: 2,
      initialThirteenPairPayment: 4,
      freshDiscardThreshold: 4,
      freshKongThreshold: 7,
      sevenPairsEnabled: false,
      freshKongPayAllEnabled: false,
      kongFourRobberyEnabled: false,
      concealedSelfDrawBonusEnabled: false,
      automaticDragonWinsEnabled: true,
      automaticWindWinsEnabled: true,
      extraSelfDrawPoints: 0,
    },
    viewerPlayerId: "player-host",
    serverTimeMs: 1_700_000_000_000,
    deadlineMs: null,
    windowId: null,
    players: [
      {
        playerId: "player-host",
        displayName: "Mei",
        role: "HOST",
        ready: false,
        connectionStatus: "CONNECTED",
        disconnectExpiresAtMs: null,
      },
    ],
    seats: [
      {
        view: "opponent",
        seatId: "seat-3",
        slot: 3,
        wind: null,
        occupant: null,
        concealedTileCount: 0,
        hasDrawnTile: false,
        melds: [],
        bonusTiles: [],
      },
      {
        view: "self",
        seatId: "seat-0",
        slot: 0,
        wind: null,
        occupant: {
          controllerType: "external",
          displayName: "Mei",
          playerId: "player-host",
          role: "HOST",
          ready: false,
        },
        concealedTiles: [],
        drawnTile: null,
        melds: [],
        bonusTiles: [],
      },
      {
        view: "opponent",
        seatId: "seat-2",
        slot: 2,
        wind: null,
        occupant: {
          controllerType: "automated",
          displayName: "Bot Bamboo",
          playerId: null,
          role: null,
          ready: true,
        },
        concealedTileCount: 0,
        hasDrawnTile: false,
        melds: [],
        bonusTiles: [],
      },
      {
        view: "opponent",
        seatId: "seat-1",
        slot: 1,
        wind: null,
        occupant: null,
        concealedTileCount: 0,
        hasDrawnTile: false,
        melds: [],
        bonusTiles: [],
      },
    ],
    game: null,
    actions: [
      {
        actionId: "opaque-ready-id",
        label: "Ready",
        enabled: true,
        tone: "primary",
        disabledReason: null,
        presentationSlot: "roomActions",
      },
      {
        actionId: "opaque-rotate-id",
        label: "Create New Invitation Link",
        enabled: true,
        tone: null,
        disabledReason: null,
        presentationSlot: "invitation",
      },
    ],
    ...overrides,
  };
}

export function publicTile(face: TileFace): PublicTileView {
  return { face };
}

export function discardActions(
  concealedTileCount: number,
  includeDrawn = true,
): OpaqueActionDescriptor[] {
  const actions: OpaqueActionDescriptor[] = Array.from(
    { length: concealedTileCount },
    (_, index) => ({
      actionId: `opaque-discard-${index}`,
      label: `Discard tile ${index + 1}`,
      enabled: true,
      tone: "neutral",
      disabledReason: null,
      presentationSlot: "concealedTile",
      presentationIndex: index,
    }),
  );
  if (includeDrawn) {
    actions.push({
      actionId: "opaque-discard-drawn",
      label: "Discard drawn tile",
      enabled: true,
      tone: "neutral",
      disabledReason: null,
      presentationSlot: "drawnTile",
      presentationIndex: null,
    });
  }
  return actions;
}

export function activeTableView(
  overrides: Partial<PublicRoomView> = {},
): PublicRoomView {
  const concealedTiles = [
    publicTile({ family: "CHARACTERS", value: 9 }),
    publicTile({ family: "DOTS", value: 1 }),
    publicTile({ family: "BAMBOO", value: 4 }),
  ];
  return roomView({
    revision: 12,
    status: "IN_MATCH",
    rulesetVersion: "0.2.0",
    stateSchemaVersion: 3,
    capabilities: [
      "multiplayerLobby",
      "roomEvents",
      "hibernatingWebSockets",
      "drawDiscard",
      "bonusTiles",
      "discardWindow",
    ],
    players: [
      {
        playerId: "player-host",
        displayName: "Mei",
        role: "HOST",
        ready: true,
        connectionStatus: "CONNECTED",
        disconnectExpiresAtMs: null,
      },
      {
        playerId: "player-wei",
        displayName: "Wei",
        role: "MEMBER",
        ready: true,
        connectionStatus: "DISCONNECTED",
        disconnectExpiresAtMs: null,
      },
    ],
    seats: [
      {
        view: "opponent",
        seatId: "seat-1",
        slot: 1,
        wind: "EAST",
        occupant: {
          controllerType: "automated",
          displayName: "Bot Orchid",
          playerId: null,
          role: null,
          ready: true,
        },
        concealedTileCount: 13,
        hasDrawnTile: false,
        melds: [],
        bonusTiles: [publicTile({ family: "ANIMAL", value: "CAT" })],
      },
      {
        view: "opponent",
        seatId: "seat-3",
        slot: 3,
        wind: "WEST",
        occupant: {
          controllerType: "external",
          displayName: "Wei",
          playerId: "player-wei",
          role: "MEMBER",
          ready: true,
        },
        concealedTileCount: 13,
        hasDrawnTile: true,
        melds: [],
        bonusTiles: [],
      },
      {
        view: "self",
        seatId: "seat-2",
        slot: 2,
        wind: "SOUTH",
        occupant: {
          controllerType: "external",
          displayName: "Mei",
          playerId: "player-host",
          role: "HOST",
          ready: true,
        },
        concealedTiles,
        drawnTile: publicTile({ family: "DRAGON", value: "RED" }),
        melds: [],
        bonusTiles: [publicTile({ family: "FLOWER", value: 1 })],
      },
      {
        view: "opponent",
        seatId: "seat-0",
        slot: 0,
        wind: "NORTH",
        occupant: {
          controllerType: "automated",
          displayName: "Bot Plum",
          playerId: null,
          role: null,
          ready: true,
        },
        concealedTileCount: 13,
        hasDrawnTile: false,
        melds: [],
        bonusTiles: [],
      },
    ],
    game: {
      status: "ACTIVE",
      prevailingWind: "EAST",
      dealerSeatId: "seat-1",
      phase: {
        type: "awaitingDiscard",
        activeSeatId: "seat-2",
        windowId: null,
        discardSequence: null,
        declaringSeatId: null,
      },
      liveWallTileCount: 67,
      reserveWallTileCount: 15,
      discards: [
        {
          sequence: 1,
          tile: publicTile({ family: "DOTS", value: 7 }),
          discardedBySeatId: "seat-0",
          claimedBySeatId: null,
          claimKind: null,
        },
        {
          sequence: 2,
          tile: publicTile({ family: "WIND", value: "NORTH" }),
          discardedBySeatId: "seat-1",
          claimedBySeatId: null,
          claimKind: null,
        },
      ],
      balances: [
        { seatId: "seat-0", points: 0 },
        { seatId: "seat-1", points: 0 },
        { seatId: "seat-2", points: 0 },
        { seatId: "seat-3", points: 0 },
      ],
      result: null,
      matchResult: null,
    },
    actions: discardActions(concealedTiles.length),
    ...overrides,
  });
}
