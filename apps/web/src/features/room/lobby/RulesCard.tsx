import type { PublicRoomView } from "../../../lib/types";

export function RulesCard({ view }: { view: PublicRoomView }) {
  const flag = (enabled: boolean) => (enabled ? "Enabled" : "Disabled");
  return (
    <section className="panel rules-panel" aria-labelledby="rules-heading">
      <div className="panel-heading">
        <div>
          <p className="step-label">Preview ruleset</p>
          <h2 id="rules-heading">Singapore Mahjong</h2>
        </div>
        <span className="read-only-chip">Read only</span>
      </div>
      <dl className="rules-list">
        <div>
          <dt>Ruleset</dt>
          <dd>
            {view.rulesetId} · v{view.rulesetVersion}
          </dd>
        </div>
        <div>
          <dt>Fan range</dt>
          <dd>
            {view.config.minimumFan}–{view.config.maximumFan} fan
          </dd>
        </div>
        <div>
          <dt>Shooter mode</dt>
          <dd>{view.config.shooterMode ? "On" : "Off"}</dd>
        </div>
        <div>
          <dt>Payouts</dt>
          <dd>{view.config.payoutTable.join(" · ")}</dd>
        </div>
      </dl>
      <div className="rule-details">
        <details>
          <summary>Payments and bonuses</summary>
          <dl>
            <div>
              <dt>Kong (one payer)</dt>
              <dd>{view.config.kongOnePayment}</dd>
            </div>
            <div>
              <dt>Kong (three payers)</dt>
              <dd>{view.config.kongThreePayment}</dd>
            </div>
            <div>
              <dt>Complete animals</dt>
              <dd>{view.config.completeAnimalSetPayment}</dd>
            </div>
            <div>
              <dt>Complete flowers</dt>
              <dd>{view.config.completeFlowerSetPayment}</dd>
            </div>
            <div>
              <dt>Complete seasons</dt>
              <dd>{view.config.completeSeasonSetPayment}</dd>
            </div>
            <div>
              <dt>Animal pair</dt>
              <dd>{view.config.animalPairPayment}</dd>
            </div>
            <div>
              <dt>Flower/season pair</dt>
              <dd>{view.config.flowerSeasonPairPayment}</dd>
            </div>
            <div>
              <dt>Initial thirteen pair</dt>
              <dd>{view.config.initialThirteenPairPayment}</dd>
            </div>
          </dl>
        </details>
        <details>
          <summary>Thresholds and variations</summary>
          <dl>
            <div>
              <dt>Fresh discard threshold</dt>
              <dd>{view.config.freshDiscardThreshold}</dd>
            </div>
            <div>
              <dt>Fresh Kong threshold</dt>
              <dd>{view.config.freshKongThreshold}</dd>
            </div>
            <div>
              <dt>Seven pairs</dt>
              <dd>{flag(view.config.sevenPairsEnabled)}</dd>
            </div>
            <div>
              <dt>Fresh Kong pays all</dt>
              <dd>{flag(view.config.freshKongPayAllEnabled)}</dd>
            </div>
            <div>
              <dt>Rob a four-tile Kong</dt>
              <dd>{flag(view.config.kongFourRobberyEnabled)}</dd>
            </div>
            <div>
              <dt>Concealed self-draw bonus</dt>
              <dd>{flag(view.config.concealedSelfDrawBonusEnabled)}</dd>
            </div>
            <div>
              <dt>Automatic dragon wins</dt>
              <dd>{flag(view.config.automaticDragonWinsEnabled)}</dd>
            </div>
            <div>
              <dt>Automatic wind wins</dt>
              <dd>{flag(view.config.automaticWindWinsEnabled)}</dd>
            </div>
            <div>
              <dt>Extra self-draw points</dt>
              <dd>{view.config.extraSelfDrawPoints}</dd>
            </div>
          </dl>
        </details>
      </div>
      <p className="fine-print">
        Settings are fixed for this preview milestone and freeze when the match
        starts.
      </p>
    </section>
  );
}
