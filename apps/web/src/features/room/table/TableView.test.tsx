import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PublicRoomView } from "../../../lib/types";
import { activeTableView } from "../../../test/fixtures";
import type { CommandOperation } from "../roomCommandReducer";
import { positionSeats, TableView } from "./TableView";

function renderTable(
  view: PublicRoomView = activeTableView(),
  options: {
    operationsByActionId?: Record<string, CommandOperation>;
    recoverableOperations?: Array<
      Extract<CommandOperation, { phase: "retryable" }>
    >;
  } = {},
) {
  const onRunAction = vi.fn();
  const onRetryAction = vi.fn();
  render(
    <MemoryRouter>
      <TableView
        view={view}
        connection={{ status: "connected", error: null }}
        roomWarning={null}
        operationsByActionId={options.operationsByActionId ?? {}}
        recoverableOperations={options.recoverableOperations ?? []}
        feedback={[]}
        onRunAction={onRunAction}
        onRetryAction={onRetryAction}
      />
    </MemoryRouter>,
  );
  return { onRunAction, onRetryAction };
}

describe("Milestone 3 table", () => {
  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it("positions every seat relative to the viewer rather than absolute wind", () => {
    const positioned = positionSeats(activeTableView().seats);
    expect(positioned.bottom?.seatId).toBe("seat-2");
    expect(positioned.right?.seatId).toBe("seat-3");
    expect(positioned.top?.seatId).toBe("seat-0");
    expect(positioned.left?.seatId).toBe("seat-1");
  });

  it("renders the authoritative table, concealment, bonuses, and server-order hand", () => {
    const view = activeTableView();
    renderTable(view);

    expect(screen.getByRole("heading", { name: "Mahjong table" })).toHaveFocus();
    expect(document.title).toBe("Your turn · ZiMo Mahjong");
    expect(screen.getByLabelText("Bot Plum, top seat")).toBeVisible();
    expect(screen.getByLabelText("Wei, right seat")).toBeVisible();
    expect(screen.getByLabelText("Bot Orchid, left seat")).toBeVisible();
    expect(screen.getByLabelText("Your seat, bottom seat")).toBeVisible();

    const leftSeat = screen.getByLabelText("Bot Orchid, left seat");
    expect(leftSeat).toHaveTextContent("East · Bot");
    expect(within(leftSeat).getByText("Dealer")).toBeVisible();
    expect(screen.getByLabelText("Your seat, bottom seat")).toHaveTextContent("Active");
    expect(screen.getByText("Disconnected")).toBeVisible();

    expect(screen.getAllByLabelText("13 concealed tiles")).toHaveLength(2);
    expect(
      screen.getByLabelText("13 concealed tiles and a separate drawn tile"),
    ).toBeVisible();
    expect(document.querySelectorAll(".tile-back")).toHaveLength(40);
    expect(screen.getByRole("img", { name: "Cat Animal" })).toBeVisible();
    expect(screen.getByRole("img", { name: "Plum Flower 1" })).toBeVisible();

    const discardButtons = screen.getAllByRole("button", { name: /^Discard / });
    expect(discardButtons.map((button) => button.getAttribute("aria-label"))).toEqual([
      "Discard 9 Characters",
      "Discard 1 Dot",
      "Discard 4 Bamboo",
      "Discard Red Dragon",
    ]);
    expect(discardButtons[3]).toHaveClass("tile-separated");

    const wall = screen.getByLabelText("Wall tile counts");
    expect(wall).toHaveTextContent("Live wall 67");
    expect(wall).toHaveTextContent("Reserve 15");
    expect(wall).toHaveTextContent("Prevailing EAST");
    expect(screen.getByText("#1")).toBeVisible();
    expect(screen.getByText("#2")).toBeVisible();
    expect(screen.getByRole("img", { name: "7 Dots" })).toBeVisible();
    expect(screen.getByRole("img", { name: "North Wind" })).toBeVisible();

    expect(screen.getByLabelText("Preview limitations")).toHaveTextContent(
      "Claims and melds, wins, scoring and payments, settings, and additional hands",
    );
    expect(document.body.innerHTML).not.toContain("opaque-discard");
    expect(document.body.innerHTML).not.toContain("tileId");
  });

  it("runs only the opaque action bound to the selected tile position", () => {
    const view = activeTableView();
    const { onRunAction } = renderTable(view);

    fireEvent.click(screen.getByRole("button", { name: "Discard 1 Dot" }));

    expect(onRunAction).toHaveBeenCalledOnce();
    expect(onRunAction).toHaveBeenCalledWith(view.actions[1]);
  });

  it("fails the whole discard group closed when one mapping is missing", () => {
    const malformed = activeTableView({
      actions: activeTableView().actions.filter(
        (action) => action.presentationSlot !== "drawnTile",
      ),
    });
    const { onRunAction } = renderTable(malformed);

    expect(
      screen.getByText("Discard choices are refreshing. Wait for the next table update."),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: /^Discard / })).not.toBeInTheDocument();
    expect(onRunAction).not.toHaveBeenCalled();
  });

  it("renders a non-active viewer without inventing discard controls", () => {
    renderTable(activeTableView({ actions: [] }));
    expect(screen.queryByRole("button", { name: /^Discard / })).not.toBeInTheDocument();
    expect(screen.queryByText(/Discard choices are refreshing/)).not.toBeInTheDocument();
  });

  it("locks every tile while one gameplay command is unresolved and keeps retry global", () => {
    const retryable: Extract<CommandOperation, { phase: "retryable" }> = {
      command: {
        commandId: "command-1",
        actionId: "opaque-discard-0",
        expectedRevision: 12,
      },
      label: "Discard 9 Characters",
      slot: "concealedTile",
      phase: "retryable",
      retryMessage: "The result is unknown. You can retry this command safely.",
    };
    const { onRetryAction } = renderTable(activeTableView(), {
      operationsByActionId: { "opaque-discard-0": retryable },
      recoverableOperations: [retryable],
    });

    for (const button of screen.getAllByRole("button", { name: /^Discard / })) {
      expect(button).toBeDisabled();
    }
    expect(screen.getByText(/discard result is unknown/i)).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Retry Discard 9 Characters safely" }),
    );
    expect(onRetryAction).toHaveBeenCalledWith("opaque-discard-0");
  });

  it("shows a monotonic server-anchored countdown then waits in Resolving", () => {
    vi.useFakeTimers();
    const base = activeTableView();
    const windowView = activeTableView({
      actions: [],
      serverTimeMs: 10_000,
      deadlineMs: 13_000,
      windowId: "window-secret",
      game: {
        ...base.game!,
        phase: {
          type: "discardClaims",
          activeSeatId: null,
          windowId: "window-secret",
          discardSequence: 2,
          declaringSeatId: null,
        },
      },
    });
    const { onRunAction } = renderTable(windowView);

    expect(screen.getByRole("timer")).toHaveTextContent("3.0s");
    act(() => vi.advanceTimersByTime(2_950));
    expect(screen.getByRole("timer")).toHaveTextContent("0.1s");
    act(() => vi.advanceTimersByTime(50));
    expect(screen.getByRole("timer")).toHaveTextContent("Resolving…");
    expect(onRunAction).not.toHaveBeenCalled();
    expect(document.body.innerHTML).not.toContain("window-secret");
  });

  it("renders wall exhaustion as a terminal preview tie with no next-hand action", () => {
    const base = activeTableView();
    renderTable(
      activeTableView({
        status: "FINISHED",
        actions: [],
        game: {
          ...base.game!,
          status: "FINISHED",
          phase: {
            type: "complete",
            activeSeatId: null,
            windowId: null,
            discardSequence: null,
            declaringSeatId: null,
          },
          liveWallTileCount: 0,
          result: {
            outcome: "TIE",
            winnerSeatId: null,
            providerSeatId: null,
            winSource: null,
            fan: 0,
            fanAwards: [],
            payments: [],
            reason: "Wall exhausted",
          },
          matchResult: {
            finalBalances: base.game!.balances,
            winningSeatIds: [],
            completedAtMs: 20_000,
            reason: "Wall exhausted",
          },
        },
      }),
    );

    expect(screen.getByText("Preview complete")).toBeVisible();
    expect(screen.getByText(/ends in a tie/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /next hand/i })).not.toBeInTheDocument();
    expect(document.title).toBe("Preview complete · ZiMo Mahjong");
  });
});
