/**
 * Servicio de chat de voz — grabación, VAD y reproducción en el navegador.
 *
 * P5-07 (absorbe S-00): la voz a texto, el chat y el texto a voz pasan por el BACKEND
 * (`services/asistenteApi.ts`, con la sesión de Firebase). Aquí ya no hay ninguna llave de
 * proveedor de IA ni una sola llamada directa a uno: lo vigila `sinLlavesLLM.test.ts`.
 */

import { sintetizarVoz, transcribirAudio, type MensajeAsistente } from './asistenteApi';

/** Mensaje del historial del agente (forma de Chat Completions, ver `asistenteApi`). */
export type ChatMessage = MensajeAsistente;

// ── Estado interno de grabación y reproducción ──

let mediaRecorder: MediaRecorder | null = null;
let recordedChunks: Blob[] = [];

let currentAudioSource: AudioBufferSourceNode | null = null;
let currentAudioCtx: AudioContext | null = null;

// ── 1. VOZ A TEXTO (backend) ──

/** El error de `apiFetch` ya es legible (sesión, límite, tamaño): se deja pasar tal cual. */
export function transcribeAudio(audioBlob: Blob): Promise<string> {
  return transcribirAudio(audioBlob);
}

// ── 2. TEXTO A VOZ (backend) ──

export async function speakText(text: string): Promise<void> {
  try {
    stopSpeaking();
    const arrayBuffer = await sintetizarVoz(text);
    const audioCtx = new AudioContext();
    currentAudioCtx = audioCtx;

    const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
    const source = audioCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioCtx.destination);
    currentAudioSource = source;

    return new Promise<void>((resolve) => {
      source.onended = () => {
        currentAudioSource = null;
        currentAudioCtx = null;
        resolve();
      };
      source.start();
    });
  } catch (e) {
    currentAudioSource = null;
    currentAudioCtx = null;
    throw e;
  }
}

export function stopSpeaking(): void {
  if (currentAudioSource) {
    try { currentAudioSource.stop(); } catch { /* ya detenido */ }
    currentAudioSource = null;
  }
  if (currentAudioCtx) {
    try { currentAudioCtx.close(); } catch { /* ya cerrado */ }
    currentAudioCtx = null;
  }
}

// ── 3. GRABACIÓN DE AUDIO ──

function getSupportedMimeType(): string {
  if (MediaRecorder.isTypeSupported('audio/webm')) return 'audio/webm';
  if (MediaRecorder.isTypeSupported('audio/ogg')) return 'audio/ogg';
  return '';
}

export async function startRecording(): Promise<void> {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = getSupportedMimeType();

    recordedChunks = [];
    mediaRecorder = mimeType
      ? new MediaRecorder(stream, { mimeType })
      : new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) recordedChunks.push(e.data);
    };

    mediaRecorder.start();
  } catch {
    throw new Error('No se pudo acceder al micrófono. Verifica los permisos del navegador.');
  }
}

export async function stopRecording(): Promise<Blob> {
  return new Promise((resolve, reject) => {
    if (!mediaRecorder || mediaRecorder.state === 'inactive') {
      reject(new Error('No hay grabación activa.'));
      return;
    }

    mediaRecorder.onstop = () => {
      const mimeType = mediaRecorder?.mimeType || 'audio/webm';
      const blob = new Blob(recordedChunks, { type: mimeType });
      recordedChunks = [];

      // Liberar tracks del micrófono
      mediaRecorder?.stream.getTracks().forEach((t) => t.stop());
      mediaRecorder = null;

      resolve(blob);
    };

    mediaRecorder.stop();
  });
}

// ── 4. VAD SIMPLE (detección de silencio) ──

let vadAudioCtx: AudioContext | null = null;
let vadStream: MediaStream | null = null;
let vadAnimFrame: number | null = null;

export function detectSilence(onSilence: () => void, threshold: number = 2000): () => void {
  let silenceStart: number | null = null;
  let stopped = false;

  (async () => {
    try {
      vadStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      vadAudioCtx = new AudioContext();

      const source = vadAudioCtx.createMediaStreamSource(vadStream);
      const analyser = vadAudioCtx.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const SILENCE_THRESHOLD = 15; // amplitud mínima para considerar "sonido"

      const check = () => {
        if (stopped) return;

        analyser.getByteFrequencyData(dataArray);
        const avg = dataArray.reduce((sum, v) => sum + v, 0) / dataArray.length;

        if (avg < SILENCE_THRESHOLD) {
          if (silenceStart === null) silenceStart = Date.now();
          else if (Date.now() - silenceStart >= threshold) {
            onSilence();
            silenceStart = null; // resetear para no llamar repetido
          }
        } else {
          silenceStart = null;
        }

        vadAnimFrame = requestAnimationFrame(check);
      };

      vadAnimFrame = requestAnimationFrame(check);
    } catch {
      // Sin acceso al micrófono — VAD no funciona
    }
  })();

  // Retorna función de cleanup
  return () => {
    stopped = true;
    if (vadAnimFrame !== null) cancelAnimationFrame(vadAnimFrame);
    vadStream?.getTracks().forEach((t) => t.stop());
    vadStream = null;
    if (vadAudioCtx) {
      try { vadAudioCtx.close(); } catch { /* ya cerrado */ }
      vadAudioCtx = null;
    }
    vadAnimFrame = null;
  };
}
