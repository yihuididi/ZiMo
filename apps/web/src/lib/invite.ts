const INVITE_PARAMETER = "invite";

export function readInviteToken(hash: string): string | null {
  const value = new URLSearchParams(hash.replace(/^#/, "")).get(
    INVITE_PARAMETER,
  );
  return value?.trim() || null;
}

export function scrubInviteFragment(): void {
  if (!window.location.hash) return;
  window.history.replaceState(
    window.history.state,
    "",
    `${window.location.pathname}${window.location.search}`,
  );
}

export function makeInvitePath(roomId: string, inviteToken: string): string {
  return `/rooms/${encodeURIComponent(roomId)}#${INVITE_PARAMETER}=${encodeURIComponent(inviteToken)}`;
}

export function makeInviteUrl(roomId: string, inviteToken: string): string {
  return new URL(makeInvitePath(roomId, inviteToken), window.location.origin)
    .href;
}

export function parseInviteLink(value: string): {
  roomId: string;
  inviteToken: string;
} | null {
  try {
    const url = new URL(value.trim(), window.location.origin);
    const match = /^\/rooms\/([^/]+)\/?$/.exec(url.pathname);
    const inviteToken = readInviteToken(url.hash);
    if (!match || !inviteToken) return null;
    return { roomId: decodeURIComponent(match[1]), inviteToken };
  } catch {
    return null;
  }
}
