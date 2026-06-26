import type { Coaching, GameState, History, Style } from "./types";

const JSON_HEADERS = { "Content-Type": "application/json" };

async function post<T>(url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: JSON_HEADERS,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
  return r.json() as Promise<T>;
}

export async function getStyles(): Promise<Style[]> {
  const r = await fetch("/api/styles");
  if (!r.ok) throw new Error(`${r.status}`);
  return (await r.json()).styles as Style[];
}

export function newGame(style: string, seed?: number) {
  return post<{ game_id: string; state: GameState }>("/api/games", { style, seed });
}

export function act(gid: string, kind: string, amount = 0) {
  return post<{ game_id: string; state: GameState }>(`/api/games/${gid}/action`, { kind, amount });
}

export function nextHand(gid: string) {
  return post<{ game_id: string; state: GameState }>(`/api/games/${gid}/next`);
}

export async function getCoaching(gid: string): Promise<Coaching> {
  const r = await fetch(`/api/games/${gid}/coaching`);
  if (!r.ok) throw new Error(`${r.status}`);
  return (await r.json()).coaching as Coaching;
}

export async function getHistory(gid: string): Promise<History> {
  const r = await fetch(`/api/games/${gid}/history`);
  if (!r.ok) throw new Error(`${r.status}`);
  return (await r.json()) as History;
}

export async function getNarratorAvailable(): Promise<boolean> {
  try {
    const r = await fetch("/api/narrator");
    if (!r.ok) return false;
    return Boolean((await r.json()).available);
  } catch {
    return false;
  }
}

export async function getNarration(gid: string): Promise<string | null> {
  const r = await fetch(`/api/games/${gid}/narration`);
  if (!r.ok) throw new Error(`${r.status}`);
  return (await r.json()).narration as string | null;
}
