export type RoomStatus =
  | "CREATED"
  | "WAITING_FOR_PLAYERS"
  | "READY"
  | "IN_MATCH"
  | "FINISHED";

export type PlayerRole = "HOST" | "MEMBER";
export type PlayerConnectionStatus = "CONNECTED" | "DISCONNECTED";
export type Wind = "EAST" | "SOUTH" | "WEST" | "NORTH";
export type RoomCapability =
  | "multiplayerLobby"
  | "roomEvents"
  | "hibernatingWebSockets"
  | "drawDiscard"
  | "bonusTiles"
  | "discardWindow";

export type TileRank = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9;
export type BonusNumber = 1 | 2 | 3 | 4;
export type TileFamily =
  | "CHARACTERS"
  | "BAMBOO"
  | "DOTS"
  | "WIND"
  | "DRAGON"
  | "FLOWER"
  | "SEASON"
  | "ANIMAL";

export type TileFace =
  | {
      family: "CHARACTERS" | "BAMBOO" | "DOTS";
      value: TileRank;
    }
  | { family: "WIND"; value: Wind }
  | { family: "DRAGON"; value: "RED" | "GREEN" | "WHITE" }
  | { family: "FLOWER" | "SEASON"; value: BonusNumber }
  | {
      family: "ANIMAL";
      value: "CAT" | "MOUSE" | "ROOSTER" | "CENTIPEDE";
    };

export interface PublicTileView {
  face: TileFace;
}

export type MeldKind = "CHOW" | "PONG" | "KONG";
export type ClaimKind = MeldKind | "WIN" | "PASS";

export interface PublicExposedMeldView {
  visibility: "exposed";
  kind: MeldKind;
  tiles: PublicTileView[];
  claimedFromSeatId: string | null;
  discardSequence: number | null;
}

export interface PublicConcealedMeldView {
  visibility: "concealed";
  kind: MeldKind;
  tileCount: number;
}

export type PublicMeldView =
  | PublicExposedMeldView
  | PublicConcealedMeldView;

export interface PublicDiscardView {
  sequence: number;
  tile: PublicTileView;
  discardedBySeatId: string;
  claimedBySeatId: string | null;
  claimKind: ClaimKind | null;
}

export type PhaseType =
  | "setup"
  | "awaitingDraw"
  | "awaitingDiscard"
  | "discardClaims"
  | "kongReplacement"
  | "kongRobbery"
  | "complete";

export interface PhaseObservation {
  type: PhaseType;
  activeSeatId: string | null;
  windowId: string | null;
  discardSequence: number | null;
  declaringSeatId: string | null;
}

export interface SeatBalance {
  seatId: string;
  points: number;
}

export interface FanAward {
  name: string;
  fan: number;
}

export interface Payment {
  sequence: number;
  payerSeatId: string;
  recipientSeatId: string;
  amount: number;
  reason: string;
}

export interface HandResult {
  outcome: "WIN" | "TIE" | "ABORTED";
  winnerSeatId: string | null;
  providerSeatId: string | null;
  winSource: "SELF_DRAW" | "DISCARD" | "ROBBED_KONG" | null;
  fan: number;
  fanAwards: FanAward[];
  payments: Payment[];
  reason: string | null;
}

export interface MatchResult {
  finalBalances: SeatBalance[];
  winningSeatIds: string[];
  completedAtMs: number;
  reason: string | null;
}

export interface GameConfig {
  shooterMode: boolean;
  minimumFan: number;
  maximumFan: number;
  payoutTable: number[];
  kongOnePayment: number;
  kongThreePayment: number;
  completeAnimalSetPayment: number;
  completeFlowerSetPayment: number;
  completeSeasonSetPayment: number;
  animalPairPayment: number;
  flowerSeasonPairPayment: number;
  initialThirteenPairPayment: number;
  freshDiscardThreshold: number;
  freshKongThreshold: number;
  sevenPairsEnabled: boolean;
  freshKongPayAllEnabled: boolean;
  kongFourRobberyEnabled: boolean;
  concealedSelfDrawBonusEnabled: boolean;
  automaticDragonWinsEnabled: boolean;
  automaticWindWinsEnabled: boolean;
  extraSelfDrawPoints: number;
}

export interface OpaqueActionDescriptor {
  actionId: string;
  label: string;
  enabled: boolean;
  tone?: "primary" | "neutral" | "danger" | null;
  disabledReason?: string | null;
  presentationSlot:
    | "roomActions"
    | "invitation"
    | "concealedTile"
    | "drawnTile";
  presentationIndex?: number | null;
}

export interface PublicPlayerView {
  playerId: string;
  displayName: string;
  role: PlayerRole;
  ready: boolean;
  connectionStatus: PlayerConnectionStatus;
  disconnectExpiresAtMs: number | null;
}

export interface PublicOccupantView {
  controllerType: "external" | "automated";
  displayName: string | null;
  playerId: string | null;
  role: PlayerRole | null;
  ready: boolean | null;
}

interface BaseSeatView {
  seatId: string;
  slot: number;
  wind: Wind | null;
  occupant: PublicOccupantView | null;
}

export interface SelfSeatView extends BaseSeatView {
  view: "self";
  concealedTiles: PublicTileView[];
  drawnTile: PublicTileView | null;
  melds: PublicMeldView[];
  bonusTiles: PublicTileView[];
}

export interface OpponentSeatView extends BaseSeatView {
  view: "opponent";
  concealedTileCount: number;
  hasDrawnTile: boolean;
  melds: PublicMeldView[];
  bonusTiles: PublicTileView[];
}

export type PublicSeatView = SelfSeatView | OpponentSeatView;

export interface PublicGameView {
  status: "PENDING_SETUP" | "ACTIVE" | "FINISHED";
  prevailingWind: Wind;
  dealerSeatId: string | null;
  phase: PhaseObservation | null;
  liveWallTileCount: number;
  reserveWallTileCount: number;
  discards: PublicDiscardView[];
  balances: SeatBalance[];
  result: HandResult | null;
  matchResult: MatchResult | null;
}

export interface PublicRoomView {
  apiVersion: "1";
  roomId: string;
  revision: number;
  presenceVersion: number;
  status: RoomStatus;
  rulesetId: string;
  rulesetVersion: string;
  stateSchemaVersion: number;
  capabilities: RoomCapability[];
  config: GameConfig;
  viewerPlayerId: string;
  serverTimeMs: number;
  deadlineMs: number | null;
  windowId: string | null;
  players: PublicPlayerView[];
  seats: PublicSeatView[];
  game: PublicGameView | null;
  actions: OpaqueActionDescriptor[];
}

export interface RoomCredentialsResponse {
  roomId: string;
  playerId: string;
  playerToken: string;
  view: PublicRoomView;
}

export interface CreateRoomResponse extends RoomCredentialsResponse {
  inviteToken: string;
}

export type CommandResponse =
  | {
      type: "view";
      view: PublicRoomView;
      inviteToken?: string;
    }
  | {
      type: "sessionEnded";
      revision: number;
    };

export interface SocketTicketResponse {
  ticket: string;
  expiresAtMs: number;
}

export interface ProjectedRoomEvent {
  publicSequence: number;
  revision: number;
  type: string;
  payload: Record<string, unknown>;
  createdAtMs: number;
}

export interface EventsResponse {
  events: ProjectedRoomEvent[];
  nextSequence: number;
}

export interface RoomSocketMessage {
  type: "roomView";
  view: PublicRoomView;
}
