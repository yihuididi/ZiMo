import { useEffect, useState, type FormEvent } from "react";

import { updateConfig } from "../../../lib/api";
import type { GameConfig, PublicRoomView } from "../../../lib/types";

const paymentFields: { key: keyof GameConfig; label: string }[] = [
  { key: "kongOnePayment", label: "Kong-1, each opponent" },
  { key: "kongThreePayment", label: "Kong-3, each opponent" },
  { key: "completeAnimalSetPayment", label: "Complete animal set" },
  { key: "completeFlowerSetPayment", label: "Complete flower set" },
  { key: "completeSeasonSetPayment", label: "Complete season set" },
  { key: "animalPairPayment", label: "Animal pair" },
  { key: "flowerSeasonPairPayment", label: "Flower and season pair" },
  { key: "initialThirteenPairPayment", label: "Pair from raw initial 13" },
];

const variationFields = [
  { key: "sevenPairsEnabled", label: "Seven Pairs · 3 fan; quads count as two pairs" },
  { key: "freshKongPayAllEnabled", label: "Fresh Kong pay-all near the end" },
  { key: "kongFourRobberyEnabled", label: "Kong-4 robbery for 13 Wonders" },
  { key: "concealedSelfDrawBonusEnabled", label: "Concealed self-draw · 1 extra fan" },
  { key: "automaticDragonWinsEnabled", label: "Automatic Dragon-set wins" },
  { key: "automaticWindWinsEnabled", label: "Automatic Wind-set wins" },
] as const;

interface RulesCardProps {
  view: PublicRoomView;
  roomId: string;
  playerToken: string;
  onSaved: (view: PublicRoomView) => void;
}

export function RulesCard({ view, roomId, playerToken, onSaved }: RulesCardProps) {
  const host = view.players.some(player => player.playerId === view.viewerPlayerId && player.role === "HOST");
  const editable = host && view.status === "WAITING_FOR_PLAYERS";
  const variations = view.capabilities.includes("ruleVariations");
  const [draft, setDraft] = useState<GameConfig>(view.config);
  const [tableText, setTableText] = useState(view.config.payoutTable.join(", "));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const configStamp = JSON.stringify(view.config);
  useEffect(() => {
    setDraft(view.config);
    setTableText(view.config.payoutTable.join(", "));
  }, [configStamp]);

  const setNumber = (key: keyof GameConfig, value: string) => {
    setDraft(current => ({ ...current, [key]: Number(value) }));
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    const payoutTable = tableText.split(",").map(part => Number(part.trim()));
    if (payoutTable.length !== draft.maximumFan + 1 || payoutTable.some(value => !Number.isSafeInteger(value) || value <= 0)) {
      setError(`Enter ${draft.maximumFan + 1} positive payouts, for fan 0 through ${draft.maximumFan}.`);
      return;
    }
    setSaving(true);
    try {
      const response = await updateConfig(roomId, playerToken, view.revision, { ...draft, payoutTable });
      onSaved(response.view);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Settings could not be saved. Refresh the room and try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="panel rules-panel" aria-labelledby="rules-heading">
      <div className="panel-heading">
        <h2 id="rules-heading">Singapore Mahjong rules</h2>
        <span className="read-only-chip">{host ? "Host settings" : "Host controlled"}</span>
      </div>
      <p className="fine-print">Settings freeze when the match starts. Saving changes clears everyone’s ready state.</p>
      <dl className="rules-list">
        <div><dt>Fan range</dt><dd>{view.config.minimumFan}–{view.config.maximumFan}</dd></div>
        <div><dt>Shooter</dt><dd>{view.config.shooterMode ? "On" : "Off"}</dd></div>
        <div><dt>Payouts, fan 0 onward</dt><dd>{view.config.payoutTable.join(" · ")}</dd></div>
      </dl>
      <details className="rules-editor">
        <summary>Immediate payment amounts</summary>
        <dl className="rules-list">{paymentFields.map(field => <div key={field.key}>
          <dt>{field.label}</dt><dd>{view.config[field.key] as number}</dd>
        </div>)}</dl>
        <p className="fine-print">A matching flower and season pair pays from all opponents for the holder’s wind, or from the matching wind holder otherwise. The raw initial 13 rate applies when both tiles began in that hand.</p>
      </details>
      {host && !editable && <p className="fine-print">Unready before editing rules.</p>}
      {variations && <details className="rules-editor"><summary>Rule variations</summary>
        <dl className="rules-list">{variationFields.map(field => <div key={field.key}><dt>{field.label}</dt><dd>{view.config[field.key] ? "On" : "Off"}</dd></div>)}
          <div><dt>Fresh winning discard below</dt><dd>{view.config.freshDiscardThreshold} playable tiles</dd></div>
          <div><dt>Fresh Kong below</dt><dd>{view.config.freshKongThreshold} playable tiles</dd></div>
          <div><dt>Extra self-draw points, each opponent</dt><dd>{view.config.extraSelfDrawPoints}</dd></div>
        </dl>
      </details>}
      {editable && <details className="rules-editor">
        <summary>Edit rules</summary>
        <form onSubmit={save}>
          <label className="rules-toggle"><input type="checkbox" checked={draft.shooterMode} onChange={event => setDraft(current => ({ ...current, shooterMode: event.target.checked }))} /> Shooter mode</label>
          <div className="rules-fields">
            <label>Minimum fan<input type="number" min="1" max={draft.maximumFan} value={draft.minimumFan} onChange={event => setNumber("minimumFan", event.target.value)} required /></label>
            <label>Maximum fan<input type="number" min={draft.minimumFan} value={draft.maximumFan} onChange={event => setNumber("maximumFan", event.target.value)} required /></label>
            <label className="rules-wide">Payout table, fan 0 through maximum<input value={tableText} onChange={event => setTableText(event.target.value)} aria-describedby="payout-help" required /></label>
            <p id="payout-help" className="fine-print rules-wide">Comma-separated amounts. Default: 1, 2, 4, 8, 16, 32.</p>
            {paymentFields.map(field => <label key={field.key}>{field.label}<input type="number" min="1" value={draft[field.key] as number} onChange={event => setNumber(field.key, event.target.value)} required /></label>)}
            <label>Fresh discard threshold<input type="number" min="1" value={draft.freshDiscardThreshold} onChange={event => setNumber("freshDiscardThreshold", event.target.value)} required /></label>
          </div>
          {variations && <fieldset className="rules-fields"><legend>Rule variations</legend>
            {variationFields.map(field => <label className="rules-toggle rules-wide" key={field.key}><input type="checkbox" checked={draft[field.key]} onChange={event => setDraft(current => ({ ...current, [field.key]: event.target.checked }))} />{field.label}</label>)}
            <label>Fresh Kong threshold<input type="number" min="1" disabled={!draft.freshKongPayAllEnabled} value={draft.freshKongThreshold} onChange={event => setNumber("freshKongThreshold", event.target.value)} required /></label>
            <label>Extra self-draw points, each opponent<input type="number" min="0" value={draft.extraSelfDrawPoints} onChange={event => setNumber("extraSelfDrawPoints", event.target.value)} required /></label>
            <p className="fine-print rules-wide">Fresh means never previously discarded, including claimed discards. Thresholds count playable tiles, excluding the reserve. Turning off automatic honor wins keeps their Bao liability until a complete hand wins.</p>
          </fieldset>}
          {error && <p className="message error" role="alert">{error}</p>}
          <button className="primary-action" type="submit" disabled={saving} aria-busy={saving}>{saving ? "Saving…" : "Save rules"}</button>
        </form>
      </details>}
    </section>
  );
}
