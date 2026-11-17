import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

import { createController } from '../controller.mjs';

test('records intent, clicks, observation and human readback in order', async () => {
  const root = await mkdtemp(join(tmpdir(), 'chess-harness-'));
  try {
    const points = [];
    const dir = join(root, 'game');
    const app = {
      getScreenshot: async () => Buffer.from('synthetic screenshot'),
      click: async point => points.push(point),
    };
    const controller = await createController(app, dir);
    await assert.rejects(controller.click('e2e4', [10, 20]), /Capture/);
    const pre = await controller.observe();
    const post = await controller.click('e2e4', [10, 20], [10, 40]);
    assert.deepEqual(points, [[10, 20], [10, 40]]);
    await assert.rejects(controller.click('second', [10, 20]), /Verify/);
    await assert.rejects(controller.verify('accepted', pre, 'old frame'), /latest/);
    await controller.verify('accepted', post, 'Pawn seen on e4');
    const entries = (await readFile(join(dir, 'actions.jsonl'), 'utf8')).trim().split('\n')
      .map(line => JSON.parse(line));
    assert.deepEqual(entries.map(entry => entry.phase), ['intent', 'clicked', 'observed', 'verified']);
    assert(entries.every(entry => entry.id === entries[0].id));
    assert.deepEqual(entries[0].pre, pre.ref);
    assert.deepEqual(entries.at(-1).evidence, post.ref);
  } finally {
    await rm(root, { force: true, recursive: true });
  }
});

test('uncertain clicks require fresh observation and a readback before recovery', async () => {
  const root = await mkdtemp(join(tmpdir(), 'chess-harness-'));
  try {
    const app = {
      getScreenshot: async () => [{ bytes: Buffer.from('synthetic screenshot') }],
      click: async () => { throw new Error('interrupted'); },
    };
    const controller = await createController(app, join(root, 'game'));
    const pre = await controller.observe();
    await assert.rejects(controller.click('e2e4', [10, 20]), /interrupted/);
    await assert.rejects(controller.verify('uncertain', pre, 'old frame'), /latest/);
    await assert.rejects(controller.click('e2e4', [10, 20]), /Verify/);
    await controller.verify('uncertain', await controller.observe(), 'Screen inspected after interruption');
  } finally {
    await rm(root, { force: true, recursive: true });
  }
});
