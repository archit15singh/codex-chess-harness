import { createHash, randomUUID } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join, resolve, sep } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';

const standby = 'Chess standby';
const gameplay = 'Chess board';
const capture = 'Chess window';
const commands = ['status', 'windows', 'prepare', 'crop', 'preview', 'standby', 'board', 'mute', 'start', 'stop'];

function sha256(value) {
  return createHash('sha256').update(value).digest('base64');
}

async function connect() {
  const configPath = join(homedir(), 'Library/Application Support/obs-studio/plugin_config/obs-websocket/config.json');
  const config = process.env.OBS_CONTROL_PASSWORD ? {} : JSON.parse(await readFile(configPath, 'utf8'));
  const password = process.env.OBS_CONTROL_PASSWORD || config.server_password;
  const port = Number(process.env.OBS_CONTROL_PORT || config.server_port || 4455);
  if (!password || !Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error('Set a valid OBS WebSocket password and port.');
  }
  const socket = new WebSocket(`ws://127.0.0.1:${port}`);
  const pending = new Map();
  let resolveReady;
  let rejectReady;
  const ready = new Promise((resolve, reject) => {
    resolveReady = resolve;
    rejectReady = reject;
  });
  const helloTimeout = setTimeout(() => {
    rejectReady(new Error('OBS WebSocket authentication timed out.'));
    socket.close();
  }, 5000);
  function disconnected() {
    const error = new Error('OBS WebSocket connection failed or closed.');
    rejectReady(error);
    for (const finish of pending.values()) finish(error);
  }
  socket.addEventListener('error', disconnected);
  socket.addEventListener('close', disconnected);
  socket.addEventListener('message', event => {
    const { op, d } = JSON.parse(event.data);
    if (op === 0) {
      if (!d.authentication) {
        rejectReady(new Error('Enable authentication in OBS WebSocket settings.'));
        socket.close();
        return;
      }
      const secret = sha256(password + d.authentication.salt);
      socket.send(JSON.stringify({ op: 1, d: { rpcVersion: 1, eventSubscriptions: 0,
        authentication: sha256(secret + d.authentication.challenge) } }));
    }
    if (op === 2) resolveReady();
    if (op === 7) pending.get(d.requestId)?.(null, d);
  });
  try {
    await ready;
  } finally {
    clearTimeout(helloTimeout);
  }
  function call(requestType, requestData = {}) {
    if (socket.readyState !== WebSocket.OPEN) throw new Error('OBS WebSocket is closed.');
    return new Promise((resolve, reject) => {
      const requestId = randomUUID();
      const timeout = setTimeout(() => finish(new Error(`${requestType} timed out.`)), 5000);
      function finish(error, result) {
        clearTimeout(timeout);
        pending.delete(requestId);
        if (error) reject(error);
        else if (!result.requestStatus.result) {
          reject(new Error(`${requestType} failed with OBS status ${result.requestStatus.code}.`));
        } else resolve(result.responseData ?? {});
      }
      pending.set(requestId, finish);
      try {
        socket.send(JSON.stringify({ op: 6, d: { requestType, requestId, requestData } }));
      } catch (error) {
        finish(error);
      }
    });
  }
  return { call, close: () => socket.close() };
}

function numbers(args, length, min = 0) {
  if (args.length !== length || args.some(value => !/^\d+$/.test(value) ||
      !Number.isSafeInteger(Number(value)) || Number(value) < min)) {
    throw new Error(`Expected ${length} integer arguments, each at least ${min}.`);
  }
  return args.map(Number);
}

async function run(call, command, args) {
  const streaming = () => call('GetStreamStatus');
  const listScenes = () => call('GetSceneList');
  const program = sceneName => call('SetCurrentProgramScene', { sceneName });
  const sceneItems = sceneName => call('GetSceneItemList', { sceneName });
  const inputName = capture;
  const windowInventory = () => call('GetInputPropertiesListPropertyItems', { inputName, propertyName: 'window' });

  async function idle() {
    const status = await streaming();
    if (status.outputActive || status.outputReconnecting) {
      throw new Error('Switch to standby and stop the stream before changing capture settings.');
    }
  }

  async function globals() {
    return [...new Set(Object.values(await call('GetSpecialInputs')).filter(Boolean))];
  }

  async function checkAudio(includeCapture = false) {
    const names = await globals();
    if (includeCapture) names.push(inputName);
    for (const inputName of names) {
      if (!(await call('GetInputMute', { inputName })).inputMuted) {
        throw new Error('An OBS broadcast audio input is still unmuted.');
      }
    }
  }

  async function boardItem() {
    const { sceneItems: items } = await sceneItems(gameplay);
    if (items.length !== 1 || items[0].sourceName !== capture || !items[0].sceneItemEnabled) {
      throw new Error('Gameplay scene must contain exactly one enabled chess window.');
    }
    return { sceneName: gameplay, sceneItemId: items[0].sceneItemId };
  }

  if (command === 'status') {
    const { obsVersion, obsWebSocketVersion } = await call('GetVersion');
    const { currentProgramSceneName, scenes } = await listScenes();
    const { outputActive, outputReconnecting } = await streaming();
    return { obsVersion, obsWebSocketVersion, currentProgramSceneName,
      scenes: scenes.map(scene => scene.sceneName), outputActive, outputReconnecting };
  }
  if (command === 'standby') {
    const { sceneItems: items } = await sceneItems(standby);
    if (items.length) throw new Error('Standby scene must be empty.');
    await program(standby);
    if ((await listScenes()).currentProgramSceneName !== standby) throw new Error('Standby switch was not verified.');
    return { program: standby };
  }
  if (command === 'stop') {
    const { outputActive, outputReconnecting } = await streaming();
    if (outputActive || outputReconnecting) await call('StopStream');
    return streaming();
  }
  if (command === 'start') {
    const { currentProgramSceneName } = await listScenes();
    if (currentProgramSceneName !== standby || (await sceneItems(standby)).sceneItems.length) {
      throw new Error('Select the empty Chess standby scene before starting.');
    }
    await checkAudio();
    const stream = await streaming();
    if (!stream.outputActive && !stream.outputReconnecting) await call('StartStream');
    return streaming();
  }
  if (command === 'mute') {
    await idle();
    const names = await globals();
    if ((await call('GetInputList')).inputs.some(input => input.inputName === capture)) names.push(inputName);
    for (const inputName of names) await call('SetInputMute', { inputName, inputMuted: true });
    await checkAudio(names.includes(capture));
    return { muted: names.length };
  }
  if (command === 'board') {
    await checkAudio(true);
    const item = await boardItem();
    const { inputSettings } = await call('GetInputSettings', { inputName });
    const { sceneItemTransform: transform } = await call('GetSceneItemTransform', item);
    if (inputSettings.type !== 1 || !inputSettings.window ||
        [transform.cropLeft, transform.cropTop, transform.cropRight, transform.cropBottom].some(edge => !(edge > 0)) ||
        !(transform.sourceWidth > transform.cropLeft + transform.cropRight) ||
        !(transform.sourceHeight > transform.cropTop + transform.cropBottom)) {
      throw new Error('Verify the selected window and its four-sided board crop before switching.');
    }
    await program(gameplay);
    if ((await listScenes()).currentProgramSceneName !== gameplay) throw new Error('Gameplay switch was not verified.');
    return { program: gameplay };
  }
  if (command === 'preview') {
    const output = resolve(args[0]);
    if (!output.startsWith(resolve('evidence/private') + sep) || !output.endsWith('.png')) {
      throw new Error('Save OBS previews as new PNG files under evidence/private/.');
    }
    const item = await boardItem();
    const { studioModeEnabled } = await call('GetStudioModeEnabled');
    if (!studioModeEnabled) await call('SetStudioModeEnabled', { studioModeEnabled: true });
    const { currentPreviewSceneName } = await call('GetCurrentPreviewScene');
    try {
      await call('SetCurrentPreviewScene', { sceneName: gameplay });
      await delay(700);
      const { sceneItemTransform } = await call('GetSceneItemTransform', item);
      const { imageData } = await call('GetSourceScreenshot', { sourceName: gameplay, imageFormat: 'png', imageWidth: 540 });
      const png = imageData.replace(/^data:image\/png;base64,/, '');
      await writeFile(output, Buffer.from(png, 'base64'), { flag: 'wx', mode: 0o600 });
      return { saved: true, transform: sceneItemTransform };
    } finally {
      if (studioModeEnabled) await call('SetCurrentPreviewScene', { sceneName: currentPreviewSceneName });
      else await call('SetStudioModeEnabled', { studioModeEnabled: false });
    }
  }

  if (command === 'crop') {
    if ((await listScenes()).currentProgramSceneName !== standby) await idle();
    const [cropLeft, cropTop, cropRight, cropBottom] = numbers(args, 4, 1);
    const item = await boardItem();
    const { sceneItemTransform: old } = await call('GetSceneItemTransform', item);
    const width = old.sourceWidth - cropLeft - cropRight;
    const height = old.sourceHeight - cropTop - cropBottom;
    if (!(width > 0 && height > 0)) throw new Error('The crop must have positive area in the current source.');
    const { baseWidth, baseHeight } = await call('GetVideoSettings');
    const scale = Math.min(baseWidth / width, baseHeight / height);
    await call('SetSceneItemTransform', { ...item, sceneItemTransform: {
      cropLeft, cropTop, cropRight, cropBottom, scaleX: scale, scaleY: scale,
      positionX: (baseWidth - width * scale) / 2, positionY: (baseHeight - height * scale) / 2,
      rotation: 0, alignment: 5, boundsType: 'OBS_BOUNDS_NONE',
    } });
    return { transform: (await call('GetSceneItemTransform', item)).sceneItemTransform };
  }

  await idle();
  const windowId = command === 'prepare' ? numbers(args, 1, 1)[0] : undefined;
  const { scenes } = await listScenes();
  for (const sceneName of [standby, gameplay]) {
    if (!scenes.some(scene => scene.sceneName === sceneName)) await call('CreateScene', { sceneName });
  }
  const { inputs } = await call('GetInputList');
  if (!inputs.some(input => input.inputName === capture)) {
    await call('CreateInput', { sceneName: gameplay, inputName,
      inputKind: 'screen_capture', inputSettings: { type: 1, show_hidden_windows: true, show_cursor: false },
      sceneItemEnabled: true });
    await call('SetInputMute', { inputName, inputMuted: true });
  }
  const { propertyItems } = await windowInventory();
  if (command === 'windows') {
    return propertyItems.filter(item => item.itemEnabled !== false && item.itemName.startsWith('[Brave Browser]'));
  }
  if (!propertyItems.some(item => item.itemEnabled !== false &&
      item.itemName.startsWith('[Brave Browser]') && Number(item.itemValue) === windowId)) {
    throw new Error('The selected window is absent from OBS’s Brave window inventory.');
  }
  await call('SetInputSettings', { inputName, inputSettings: { type: 1, window: windowId }, overlay: true });
  await call('SetInputMute', { inputName, inputMuted: true });
  await boardItem();
  const { inputSettings } = await call('GetInputSettings', { inputName });
  if (inputSettings.window !== windowId || inputSettings.type !== 1) throw new Error('OBS window readback did not match.');
  return { windowId };
}

const [command, ...args] = process.argv.slice(2);
if (command === '--help') {
  console.log('Usage: node obs.mjs status | windows | prepare WINDOW_ID | crop L T R B | preview PRIVATE_PNG | standby | board | mute | start | stop');
} else {
  try {
    const expected = { prepare: 1, crop: 4, preview: 1 }[command] ?? 0;
    if (!commands.includes(command) || args.length !== expected) throw new Error('Invalid arguments. Run with --help.');
    const connection = await connect();
    try {
      console.log(JSON.stringify(await run(connection.call, command, args), null, 2));
    } finally {
      connection.close();
    }
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
