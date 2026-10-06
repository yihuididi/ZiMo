import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { updateConfig } from "../../../lib/api";
import { roomView } from "../../../test/fixtures";
import { RulesCard } from "./RulesCard";

vi.mock("../../../lib/api", () => ({ updateConfig: vi.fn() }));

function show(view = roomView({ capabilities: ["ruleVariations", "bao"] })) {
  const onSaved = vi.fn();
  render(<RulesCard view={view} roomId={view.roomId} playerToken="test-token" onSaved={onSaved} />);
  return onSaved;
}

describe("Unified rules settings", () => {
  it("saves every variation through the existing revisioned endpoint", async () => {
    const view = roomView({ capabilities: ["ruleVariations", "bao"] });
    vi.mocked(updateConfig).mockResolvedValue({ type: "view", view });
    const saved = show(view);
    fireEvent.click(screen.getByText("Edit rules"));
    fireEvent.click(screen.getByLabelText(/Seven Pairs/));
    fireEvent.click(screen.getByLabelText("Fresh Kong pay-all near the end"));
    fireEvent.click(screen.getByLabelText("Kong-4 robbery for 13 Wonders"));
    fireEvent.click(screen.getByLabelText("Concealed self-draw · 1 extra fan"));
    fireEvent.click(screen.getByLabelText("Automatic Dragon-set wins"));
    fireEvent.change(screen.getByLabelText("Fresh Kong threshold"), { target: { value: "9" } });
    fireEvent.change(screen.getByLabelText("Extra self-draw points, each opponent"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Save rules" }));
    await waitFor(() => expect(saved).toHaveBeenCalledWith(view));
    expect(updateConfig).toHaveBeenLastCalledWith(view.roomId, "test-token", view.revision, expect.objectContaining({
      sevenPairsEnabled: true, freshKongPayAllEnabled: true, kongFourRobberyEnabled: true,
      concealedSelfDrawBonusEnabled: true, automaticDragonWinsEnabled: false,
      automaticWindWinsEnabled: true, freshKongThreshold: 9, extraSelfDrawPoints: 3,
    }));
  });

  it("keeps ready-room settings read-only and explains how to edit", () => {
    show(roomView({ status: "READY", capabilities: ["ruleVariations"] }));
    expect(screen.queryByRole("button", { name: "Save rules" })).not.toBeInTheDocument();
    expect(screen.getByText("Unready before editing rules.")).toBeVisible();
    expect(screen.getByText("Rule variations")).toBeVisible();
  });

  it("does not expose editing to members or unadvertised variation controls", () => {
    show(roomView({ viewerPlayerId: "member", capabilities: ["ruleVariations"] }));
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });
});
