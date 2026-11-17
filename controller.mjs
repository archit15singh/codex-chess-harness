import { createHash, randomUUID } from 'node:crypto';
import { appendFile, mkdir, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';

// The caller owns the visible browser and judges every position and click.
export async function createController(app, evidenceDirectory) {
  const root = resolve(evidenceDirectory);
  await mkdir(root, { mode: 0o700 });
  const ledger = join(root, 'actions.jsonl');
  let latest;
  let pending;
  let active = false;

  async function log(event) {
    await appendFile(ledger, JSON.stringify({ at: new Date().toISOString(), ...event }) + '\n', {
      mode: 0o600,
    });
  }

  async function capture() {
    const screenshot = await app.getScreenshot({ emit: false });
    const source = typeof screenshot[0] === 'number' ? screenshot : screenshot[0]?.bytes;
    if (!source?.length) throw new Error('Brave returned no screenshot');
    const capturedAt = new Date().toISOString();
    const bytes = Buffer.from(source);
    const file = randomUUID() + '.png';
    await writeFile(join(root, file), bytes, { mode: 0o600, flag: 'wx' });
    const ref = { file, sha256: createHash('sha256').update(bytes).digest('hex') };
    latest = { ref, capturedAt };
    return { bytes, ...latest };
  }

  async function observe() {
    if (active) throw new Error('Browser action in progress');
    active = true;
    try {
      return await capture();
    } finally {
      active = false;
    }
  }

  async function click(label, ...points) {
    if (active || pending) throw new Error('Verify the previous action before clicking');
    if (!latest) throw new Error('Capture the board before clicking');
    if (!label || points.length < 1 || points.length > 2 || points.some(
      point => !Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite)
    )) throw new Error('Provide a move label and one or two visible coordinates');

    active = true;
    const id = randomUUID();
    const pre = latest;
    try {
      await log({ id, label, phase: 'intent', points, pre: pre.ref, observedAt: pre.capturedAt });
      pending = { id, label };
      latest = undefined;
      for (const point of points) await app.click(point);
      await log({ id, label, phase: 'clicked' });
      const post = await capture();
      await log({ id, label, phase: 'observed', post: post.ref, observedAt: post.capturedAt });
      return post;
    } catch (error) {
      await log({ id, label, phase: 'error', message: String(error) });
      throw error;
    } finally {
      active = false;
    }
  }

  async function verify(status, observation, note) {
    if (active || !pending || !note || !latest || observation?.ref !== latest.ref ||
        !['accepted', 'rejected', 'uncertain'].includes(status)) {
      throw new Error('Verify a pending action against the latest screenshot with a note');
    }
    active = true;
    try {
      await log({ ...pending, phase: 'verified', status, evidence: latest.ref, note });
      pending = undefined;
    } finally {
      active = false;
    }
  }

  return { observe, click, verify };
}
