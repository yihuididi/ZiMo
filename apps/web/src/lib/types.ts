export type RoomStatus =
  | "CREATED"
  | "WAITING_FOR_PLAYERS"
  | "READY"
  | "IN_MATCH"
  | "FINISHED";

export type PlayerRole = "HOST" | "MEMBER";
export type PlayerConnectionStatus = "CONNECTED" | "DISCONNECTED";
export type Wind = "EAST" | "SOUTH" | "WEST" | "NORTH";

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
  presentationSlot: "roomActions" | "invitation";
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
  concealedTiles: unknown[];
  drawnTile: unknown | null;
  melds: unknown[];
  bonusTiles: unknown[];
}

export interface OpponentSeatView extends BaseSeatView {
  view: "opponent";
  concealedTileCount: number;
  hasDrawnTile: boolean;
  melds: unknown[];
  bonusTiles: unknown[];
}

export type PublicSeatView = SelfSeatView | OpponentSeatView;

export interface PublicGameView {
  status: "PENDING_SETUP" | "ACTIVE" | "FINISHED";
  prevailingWind: Wind;
  dealerSeatId: string | null;
  phase: unknown | null;
  liveWallTileCount: number;
  reserveWallTileCount: number;
  discards: unknown[];
  balances: unknown[];
  result: unknown | null;
  matchResult: unknown | null;
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
  capabilities: string[];
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
