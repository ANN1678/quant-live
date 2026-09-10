// data/ の中身を、ビルドのときに読む。エンジンが書いたものをそのまま映すだけにする。
import fs from 'node:fs';
import path from 'node:path';

const DATA = path.resolve(process.cwd(), 'data');

function readJson<T>(name: string, fallback: T): T {
  const p = path.join(DATA, name);
  if (!fs.existsSync(p)) return fallback;
  try {
    return JSON.parse(fs.readFileSync(p, 'utf-8')) as T;
  } catch {
    return fallback;
  }
}

function readJsonl<T>(name: string): T[] {
  const p = path.join(DATA, name);
  if (!fs.existsSync(p)) return [];
  return fs.readFileSync(p, 'utf-8').split('\n')
    .filter((l) => l.trim())
    .map((l) => JSON.parse(l) as T);
}

export type Summary = any;
export type Market = any;

export const summary = readJson<Summary>('summary.json', null);
export const market = readJson<Market>('market.json', { pairs: {} });
export const equity = readJson<any>('equity.json', { start: 1000000, curve: [] });
export const backtest = readJson<any>('backtest.json', null);
export const predictions = readJsonl<any>('predictions.jsonl');
export const results = readJsonl<any>('results.jsonl');
export const trades = readJsonl<any>('trades.jsonl');

export const PAIR_LABEL: Record<string, string> = {
  btc_jpy: 'ビットコイン',
  eth_jpy: 'イーサリアム',
};

export const DIRECTION_LABEL: Record<string, string> = {
  up: '上',
  down: '下',
  none: '見送り',
};

export function yen(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—';
  return Math.round(n).toLocaleString('ja-JP');
}

export function pct(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined) return '—';
  return `${n > 0 ? '+' : ''}${n.toFixed(digits)}%`;
}

export function jst(iso: string | number | null | undefined): string {
  if (iso === null || iso === undefined) return '—';
  const d = typeof iso === 'number' ? new Date(iso) : new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return new Intl.DateTimeFormat('ja-JP', {
    timeZone: 'Asia/Tokyo', month: 'numeric', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  }).format(d);
}
