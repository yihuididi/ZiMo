import { useEffect, useId, useState } from "react";

import { makeInviteUrl } from "../../../lib/invite";
import type { OpaqueActionDescriptor } from "../../../lib/types";
import type { CommandOperation } from "../roomCommandReducer";

interface InvitePanelProps {
  roomId: string;
  inviteToken: string | undefined;
  action: OpaqueActionDescriptor;
  operation: CommandOperation | undefined;
  onRunAction: (action: OpaqueActionDescriptor) => void;
}

type CopyState = "idle" | "copied" | "error";

export function InvitePanel({
  roomId,
  inviteToken,
  action,
  operation,
  onRunAction,
}: InvitePanelProps) {
  const [copyState, setCopyState] = useState<CopyState>("idle");
  const disabledReasonId = useId();
  const isSubmitting = operation?.phase === "submitting";

  useEffect(() => {
    setCopyState("idle");
  }, [inviteToken]);

  async function copyInvitation() {
    if (!inviteToken) return;
    try {
      await navigator.clipboard.writeText(makeInviteUrl(roomId, inviteToken));
      setCopyState("copied");
    } catch {
      setCopyState("error");
    }
  }

  return (
    <section className="panel invite-panel" aria-labelledby="invite-heading">
      <p className="step-label">Host invitation</p>
      <h2 id="invite-heading">
        {inviteToken ? "Invite players" : "Create an invitation link"}
      </h2>
      <p>
        {inviteToken
          ? "Anyone with this private link can request an open seat."
          : "This browser cannot recover the previous host’s private link. Create a new one to invite players."}
      </p>
      <div className="invite-actions">
        {inviteToken && (
          <button
            className="secondary-action full-width"
            type="button"
            onClick={copyInvitation}
          >
            {copyState === "copied"
              ? "Invitation copied"
              : "Copy invitation link"}
          </button>
        )}
        <button
          aria-busy={isSubmitting || undefined}
          aria-describedby={
            action.disabledReason ? disabledReasonId : undefined
          }
          className="secondary-action full-width"
          type="button"
          disabled={!action.enabled || Boolean(operation)}
          onClick={() => onRunAction(action)}
        >
          {isSubmitting ? "Working…" : action.label}
        </button>
      </div>
      <p className="fine-print">
        Creating a new invitation link invalidates every previous link.
      </p>
      {action.disabledReason && (
        <p className="disabled-reason" id={disabledReasonId}>
          {action.disabledReason}
        </p>
      )}
      <span className="sr-only" role="status" aria-atomic="true">
        {copyState === "copied" ? "Invitation link copied." : ""}
      </span>
      {copyState === "error" && (
        <p className="message error" role="alert">
          Could not copy the invitation. Check clipboard access.
        </p>
      )}
    </section>
  );
}
